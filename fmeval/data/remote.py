"""Read an HDF5 file over HTTP byte ranges.

HDF5 does not need the whole file: opening the 166 GiB production trajectory touches three
ranges and reading one 256^2 frame touches ten. What it does need is *random access*, which
over HTTP means one `Range` request per region and a cache in front of them.

Measured 2026-08-27 against https://portal.nersc.gov/project/m4790/Data:

* ``Accept-Ranges: bytes``; a single-range GET returns ``206``. ``Content-Length`` is
  178271350284, exactly ``os.path.getsize`` of the CFS copy.
* Opening the file: **3 requests, 0.05 s**. Reading one frame of density, velocity and
  vorticity: **0.06-0.23 s, 10-13 requests, 2.5-3.2 MiB** at the 256 KiB block size below.
* Concurrency buys nothing: 48 parallel range GETs are no faster than one at a time
  (~13 ms each), so there is no prefetch thread here and no reason to add one.

Three findings that shape the code, each of which cost real time to discover:

1. **Any multi-range header returns the entire file.** Two ranges, three, ten, two hundred,
   or overlapping ones -- every variant measured came back ``200`` with
   ``Content-Length: 178271350284``. So this client sends exactly one range per request,
   always, and a non-206 is treated as a hard error whose body is never read. Draining that
   body would pull 166 GiB into memory and across a shared science link.
2. **Never subclass anything in ``io``.** h5py's fileobj driver prefers ``readinto``, and
   ``io.RawIOBase`` supplies one that raises a bare ``NotImplementedError`` from inside
   ``h5fd.pyx`` with no message. This is a plain class on purpose.
3. **h5py calls only ``readinto``, ``seek`` and ``tell``** (whence 0 and 2; never 1), with
   small irregular sizes -- 8, 48, 328, 512, 2096 bytes on a trivial file. Block caching is
   not an optimisation here, it is the entire design.

Why not something off the shelf: ``h5py.File(url, driver="ros3")`` raises
``ValueError: h5py was built without ROS3 support`` in this build (and ros3 is S3-only in
any case), and fsspec would add ``aiohttp`` as a hard dependency for a feature that is
meant to work out of the box. See docs/decisions.md.
"""

from __future__ import annotations

import http.client
import socket
import threading
import time
import urllib.parse
from collections import OrderedDict
from dataclasses import asdict, dataclass, field
from typing import Any

import h5py

#: One frame of a 256^2 field is 512 KiB and one velocity chunk 1 MiB. Measured at this
#: size, a frame costs 10-13 requests and 2.5-3.2 MiB against 2 MiB of payload.
DEFAULT_BLOCK_BYTES = 256 * 1024

#: LRU depth, in blocks. 128 * 256 KiB = 32 MiB, matching the readers' `chunk_cache_mb`
#: default. Note that those are two separate caches: an open remote file holds both.
DEFAULT_CACHE_BLOCKS = 128

#: No legitimate read here approaches this. A runaway guard, not a tuning knob.
MAX_REQUEST_BYTES = 64 * 1024 * 1024

#: Transient failures worth retrying the same range on. A bad status is never in here.
TRANSIENT = (
    http.client.BadStatusLine,
    http.client.IncompleteRead,
    http.client.RemoteDisconnected,
    ConnectionError,
    socket.timeout,
    OSError,
)


class RangeUnsupported(RuntimeError):
    """The server will not serve byte ranges, so HDF5 cannot be read from it."""


class RemoteFileChanged(RuntimeError):
    """The file was replaced while it was being read."""


@dataclass
class RemoteStats:
    """What the transport did, for the run folder's provenance."""

    requests: int = 0
    retries: int = 0
    bytes_fetched: int = 0
    cache_hits: int = 0
    wall_seconds: float = 0.0


@dataclass
class Validator:
    """What identifies the exact bytes being read."""

    etag: str | None = None
    last_modified: str | None = None
    size_bytes: int = 0

    def if_range(self) -> str | None:
        return self.etag or self.last_modified


@dataclass
class _Redirects:
    limit: int = 3
    seen: list[str] = field(default_factory=list)


class HTTPRangeFile:
    """A seekable, read-only file over HTTP byte ranges, for h5py's fileobj driver.

    Not thread-safe by construction, so every public method takes a lock. h5py's own
    global lock already serialises today's use; the lock here means a future caller that
    reads two frames concurrently cannot silently interleave `seek` and `readinto`.
    """

    def __init__(
        self,
        url: str,
        *,
        block_size: int = DEFAULT_BLOCK_BYTES,
        cache_blocks: int = DEFAULT_CACHE_BLOCKS,
        timeout: float = 30.0,
        retries: int = 3,
    ) -> None:
        """Open the URL and learn its size, without fetching any of its content.

        Raises:
            FileNotFoundError: On 404.
            PermissionError: On 401 or 403.
            RangeUnsupported: If the server does not advertise byte ranges, or does not
                say how large the file is.
        """
        if block_size < 1:
            raise ValueError(f"block_size must be positive, got {block_size}")
        self.url = url
        self.block_size = int(block_size)
        self.cache_blocks = int(cache_blocks)
        self.timeout = float(timeout)
        self.retries = int(retries)

        self._lock = threading.RLock()
        self._blocks: OrderedDict[int, bytes] = OrderedDict()
        self._conn: http.client.HTTPConnection | None = None
        self._pos = 0
        self._closed = False
        self.stats = RemoteStats()

        self._host, self._target, self._https = _split(url)
        self.validator = self._head()
        self.size = self.validator.size_bytes

    # --- the surface h5py's fileobj driver touches -----------------------------------

    def readinto(self, buffer) -> int:
        """Fill `buffer` from the current position. Returns the number of bytes written.

        Must loop until the buffer is full or the file ends: HDF5 reads a short return as
        an undiagnosable read error rather than as a short read.
        """
        view = memoryview(buffer).cast("B")
        with self._lock:
            data = self._read_bytes(self._pos, len(view))
            view[: len(data)] = data
            self._pos += len(data)
            return len(data)

    def read(self, size: int = -1) -> bytes:
        """Kept for the fallback path h5py takes when `readinto` is absent."""
        with self._lock:
            if size is None or size < 0:
                raise ValueError(
                    "refusing an unbounded read: on this file that is 166 GiB. "
                    "HDF5 never asks for one."
                )
            data = self._read_bytes(self._pos, size)
            self._pos += len(data)
            return data

    def seek(self, offset: int, whence: int = 0) -> int:
        with self._lock:
            if whence == 0:
                target = offset
            elif whence == 1:
                target = self._pos + offset
            elif whence == 2:
                target = self.size + offset  # how h5py learns the file size
            else:
                raise ValueError(f"invalid whence {whence!r}")
            self._pos = max(0, int(target))
            return self._pos

    def tell(self) -> int:
        return self._pos

    # --- ours ------------------------------------------------------------------------

    def close(self) -> None:
        """Idempotent."""
        with self._lock:
            self._closed = True
            self._blocks.clear()
            self._drop_connection()

    def provenance(self) -> dict[str, Any]:
        """What to record about this read in a run folder."""
        record: dict[str, Any] = {
            "url": self.url,
            "block_size": self.block_size,
            **{k: v for k, v in asdict(self.validator).items() if v is not None},
        }
        record.update(asdict(self.stats))
        record["wall_seconds"] = round(record["wall_seconds"], 3)
        return record

    def __enter__(self) -> HTTPRangeFile:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # --- transport -------------------------------------------------------------------

    def _connect(self) -> http.client.HTTPConnection:
        if self._conn is None:
            factory = (
                http.client.HTTPSConnection if self._https else http.client.HTTPConnection
            )
            self._conn = factory(self._host, timeout=self.timeout)
        return self._conn

    def _drop_connection(self) -> None:
        if self._conn is not None:
            try:
                self._conn.close()
            except OSError:
                pass
            self._conn = None

    def _head(self) -> Validator:
        """One HEAD, following a bounded number of redirects, pinning the final URL."""
        redirects = _Redirects()
        while True:
            response = self._request("HEAD", {})
            try:
                status = response.status
                headers = response.headers
                response.read()  # a HEAD body is empty; drains the connection for reuse
            finally:
                pass

            if status in (301, 302, 303, 307, 308):
                location = headers.get("Location")
                if not location or len(redirects.seen) >= redirects.limit:
                    self._drop_connection()
                    raise RangeUnsupported(
                        f"{self.url}: {len(redirects.seen)} redirects without a final "
                        "resource"
                    )
                redirects.seen.append(location)
                self.url = urllib.parse.urljoin(self.url, location)
                self._drop_connection()
                self._host, self._target, self._https = _split(self.url)
                continue

            if status == 404:
                self._drop_connection()
                raise FileNotFoundError(f"{self.url} returned 404")
            if status in (401, 403):
                self._drop_connection()
                raise PermissionError(f"{self.url} returned {status}")
            if status != 200:
                self._drop_connection()
                raise RangeUnsupported(f"{self.url}: HEAD returned {status}")

            length = headers.get("Content-Length")
            if length is None:
                raise RangeUnsupported(
                    f"{self.url}: no Content-Length, so the file size is unknown and "
                    "HDF5 cannot seek to the end of it."
                )
            accept = (headers.get("Accept-Ranges") or "").lower()
            if "bytes" not in accept:
                raise RangeUnsupported(
                    f"{self.url}: Accept-Ranges is {accept or 'absent'!r}, not 'bytes'. "
                    "Reading HDF5 from it would mean downloading the whole file for "
                    "every read."
                )
            return Validator(
                etag=headers.get("ETag"),
                last_modified=headers.get("Last-Modified"),
                size_bytes=int(length),
            )

    def _request(self, method: str, headers: dict[str, str]):
        """One request on the keep-alive connection, reconnecting once if it was dropped."""
        base = {"Accept-Encoding": "identity", **headers}
        for attempt in range(2):
            try:
                conn = self._connect()
                conn.request(method, self._target, headers=base)
                return conn.getresponse()
            except TRANSIENT:
                # A keep-alive connection closed by the far end is routine, not a fault:
                # reconnect once and reissue. Counted, so provenance shows it happened.
                self._drop_connection()
                self.stats.retries += 1
                if attempt:
                    raise
        raise AssertionError("unreachable")

    def _fetch(self, start: int, stop: int) -> bytes:
        """GET exactly one byte range, inclusive of both ends.

        One range per request, always. Measured: this server answers *any* multi-range
        header -- even two ranges -- with 200 and the whole 166 GiB body.
        """
        if stop < start:
            return b""
        span = stop - start + 1
        if span > MAX_REQUEST_BYTES:
            raise ValueError(
                f"refusing a {span} byte request at offset {start}: over the "
                f"{MAX_REQUEST_BYTES} byte guard. Nothing HDF5 asks for is this large."
            )

        headers = {"Range": f"bytes={start}-{stop}"}
        if_range = self.validator.if_range()
        if if_range:
            # If the file is replaced mid-read the server answers 200 rather than 206,
            # which trips the check below -- instead of splicing bytes from two different
            # HDF5 images into one file and reporting numbers from neither.
            headers["If-Range"] = if_range

        last: Exception | None = None
        for attempt in range(self.retries):
            started = time.perf_counter()
            try:
                response = self._request("GET", headers)
                if response.status != 206:
                    # A 200 here is the ENTIRE file. The body is never read: the socket is
                    # dropped with it unsent. Check the status line, never Content-Length
                    # -- a legitimate multi-range 206 carries no Content-Length at all.
                    status = response.status
                    self._drop_connection()
                    raise RangeUnsupported(
                        f"{self.url}: a range request for bytes {start}-{stop} returned "
                        f"{status}, not 206. A 200 is the whole file ({self.size} bytes), "
                        "so the response was discarded unread. The server is ignoring "
                        "Range headers, or the file changed while it was being read."
                    )
                data = response.read()
                self._check_content_range(response.headers.get("Content-Range"), start)
                self._check_validator(response.headers)
                if len(data) != span:
                    raise http.client.IncompleteRead(data, span - len(data))
            except (RangeUnsupported, RemoteFileChanged):
                raise  # decisions by the server, not accidents. Never retried.
            except TRANSIENT as exc:
                last = exc
                self._drop_connection()
                self.stats.retries += 1
                time.sleep(min(0.5 * 2**attempt, 2.0))
                continue
            finally:
                self.stats.wall_seconds += time.perf_counter() - started

            self.stats.requests += 1
            self.stats.bytes_fetched += len(data)
            return data

        raise ConnectionError(
            f"{self.url}: bytes {start}-{stop} failed after {self.retries} attempts"
        ) from last

    def _check_content_range(self, header: str | None, start: int) -> None:
        if not header:
            return
        try:
            spec, total = header.split()[-1].split("/")
            first = int(spec.split("-")[0])
        except (ValueError, IndexError):
            raise RemoteFileChanged(f"{self.url}: unparseable Content-Range {header!r}") from None
        if first != start:
            raise RemoteFileChanged(
                f"{self.url}: asked for bytes from {start}, got {first}"
            )
        if total != "*" and int(total) != self.size:
            raise RemoteFileChanged(
                f"{self.url}: was {self.size} bytes at open, now {total}"
            )

    def _check_validator(self, headers) -> None:
        etag = headers.get("ETag")
        modified = headers.get("Last-Modified")
        if self.validator.etag and etag and etag != self.validator.etag:
            raise RemoteFileChanged(
                f"{self.url}: ETag changed from {self.validator.etag} to {etag} "
                "mid-read. The file was replaced; the bytes read so far are from a "
                "different version and cannot be combined with these."
            )
        if (
            self.validator.last_modified
            and modified
            and modified != self.validator.last_modified
        ):
            raise RemoteFileChanged(
                f"{self.url}: Last-Modified changed from {self.validator.last_modified} "
                f"to {modified} mid-read."
            )

    # --- block cache -----------------------------------------------------------------

    def _block(self, index: int) -> bytes:
        cached = self._blocks.get(index)
        if cached is not None:
            self._blocks.move_to_end(index)
            self.stats.cache_hits += 1
            return cached
        start = index * self.block_size
        data = self._fetch(start, min(start + self.block_size, self.size) - 1)
        self._store(index, data)
        return data

    def _store(self, index: int, data: bytes) -> None:
        self._blocks[index] = data
        self._blocks.move_to_end(index)
        while len(self._blocks) > self.cache_blocks:
            self._blocks.popitem(last=False)

    def _prefetch(self, first: int, last_index: int) -> None:
        """Fetch a run of consecutive missing blocks as ONE range, then split it.

        The alternative -- one request per block -- is what makes a naive implementation
        slow, and a multi-range header is not an option here at all.
        """
        runs: list[tuple[int, int]] = []
        run: list[int] = []
        for index in range(first, last_index + 1):
            if index in self._blocks:
                if run:
                    runs.append((run[0], run[-1]))
                    run = []
                continue
            if run and (index - run[0] + 1) * self.block_size > MAX_REQUEST_BYTES:
                runs.append((run[0], run[-1]))
                run = []
            run.append(index)
        if run:
            runs.append((run[0], run[-1]))

        for lo, hi in runs:
            if lo == hi:
                self._block(lo)
                continue
            start = lo * self.block_size
            stop = min((hi + 1) * self.block_size, self.size) - 1
            data = self._fetch(start, stop)
            for offset, index in enumerate(range(lo, hi + 1)):
                chunk = data[offset * self.block_size : (offset + 1) * self.block_size]
                if chunk:
                    self._store(index, chunk)

    def _read_bytes(self, offset: int, count: int) -> bytes:
        if self._closed:
            raise ValueError("read from a closed HTTPRangeFile")
        if count <= 0 or offset >= self.size:
            return b""
        count = min(count, self.size - offset)
        first = offset // self.block_size
        last_index = (offset + count - 1) // self.block_size
        self._prefetch(first, last_index)

        out = bytearray()
        position = offset
        while len(out) < count:
            index = position // self.block_size
            within = position - index * self.block_size
            block = self._block(index)
            take = min(count - len(out), len(block) - within)
            if take <= 0:
                break  # short block at EOF
            out += block[within : within + take]
            position += take
        return bytes(out)


def _split(url: str) -> tuple[str, str, bool]:
    """Host, request target and whether TLS is in use."""
    parts = urllib.parse.urlsplit(url)
    if parts.scheme not in ("http", "https"):
        raise ValueError(f"not an HTTP URL: {url!r}")
    target = parts.path or "/"
    if parts.query:
        target = f"{target}?{parts.query}"
    return parts.netloc, target, parts.scheme == "https"


def open_h5(url: str, *, chunk_cache_mb: int = 32, **kwargs: Any) -> tuple[h5py.File, HTTPRangeFile]:
    """Open a remote HDF5 file. Both handles are returned; both must be closed.

    `chunk_cache_mb` is h5py's chunk cache and is *separate* from the block cache in
    `HTTPRangeFile`, so an open remote file holds both -- 32 MiB each by default.
    """
    stream = HTTPRangeFile(url, **kwargs)
    try:
        handle = h5py.File(stream, "r", rdcc_nbytes=chunk_cache_mb * 2**20, rdcc_nslots=10007)
    except Exception:
        stream.close()
        raise
    return handle, stream
