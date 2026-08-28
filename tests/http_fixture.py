"""A local HTTP server that serves byte ranges, and several ways of getting them wrong.

Loopback only, on an ephemeral port, so the default suite exercises the whole remote path
without touching the network. The failure modes are the ones measured against the real
portal and against Apache's documented behaviour, not invented ones:

* ``ignore_ranges`` advertises ``Accept-Ranges: bytes`` and then answers a range request
  with ``200`` and the whole body. That is exactly what portal.nersc.gov does for any
  multi-range header -- measured 2026-08-27 -- and what Apache does when it declines a
  ``Range`` for any reason. Python's stock ``SimpleHTTPRequestHandler`` implements no
  ranges at all, so this is also what an ordinary static server looks like.
* ``etag_flips`` replaces the ETag partway through, the signature of a file rewritten while
  it is being read.
"""

from __future__ import annotations

import threading
from contextlib import contextmanager
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Iterator, Literal

Mode = Literal["ranges", "ignore_ranges", "no_accept_ranges", "etag_flips", "drop_once"]

ETAG = '"fixture-v1"'
ETAG_AFTER_FLIP = '"fixture-v2"'
LAST_MODIFIED = "Tue, 25 Aug 2026 20:53:11 GMT"


@dataclass
class ServeStats:
    """What the server was asked for, and what it managed to send."""

    head_requests: int = 0
    range_requests: int = 0
    body_bytes_written: int = 0
    ranges_seen: list[str] = field(default_factory=list)


def _handler(payload: bytes, mode: Mode, stats: ServeStats):
    state = {"gets": 0}
    lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *args):  # noqa: A002 - silence the default stderr spam
            pass

        def _etag(self) -> str:
            if mode != "etag_flips":
                return ETAG
            return ETAG if state["gets"] <= 1 else ETAG_AFTER_FLIP

        def do_HEAD(self):  # noqa: N802 - the stdlib dispatches on this exact name
            with lock:
                stats.head_requests += 1
            self.send_response(200)
            self.send_header("Content-Length", str(len(payload)))
            if mode != "no_accept_ranges":
                self.send_header("Accept-Ranges", "bytes")
            self.send_header("ETag", self._etag())
            self.send_header("Last-Modified", LAST_MODIFIED)
            self.end_headers()

        def do_GET(self):  # noqa: N802
            header = self.headers.get("Range")
            with lock:
                state["gets"] += 1
                if header:
                    stats.range_requests += 1
                    stats.ranges_seen.append(header)
                gets = state["gets"]

            if mode == "drop_once" and gets == 1:
                self.close_connection = True
                return  # no response at all: the client sees a dropped connection

            if header is None or mode in ("ignore_ranges", "no_accept_ranges"):
                self._send_whole_body()
                return

            start, stop = _parse_range(header, len(payload))
            body = payload[start : stop + 1]
            self.send_response(206)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Content-Range", f"bytes {start}-{stop}/{len(payload)}")
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("ETag", self._etag())
            self.send_header("Last-Modified", LAST_MODIFIED)
            self.end_headers()
            self._write(body)

        def _send_whole_body(self):
            self.send_response(200)
            self.send_header("Content-Length", str(len(payload)))
            if mode != "no_accept_ranges":
                self.send_header("Accept-Ranges", "bytes")
            self.send_header("ETag", self._etag())
            self.end_headers()
            self._write(payload)

        def _write(self, body: bytes) -> None:
            """Write in pieces, recording what actually left.

            A client that hangs up without reading -- which is precisely what this package
            does on a non-206 -- makes this fail partway, and the shortfall is the
            evidence that the body was never pulled.
            """
            sent = 0
            try:
                for offset in range(0, len(body), 64 * 1024):
                    piece = body[offset : offset + 64 * 1024]
                    self.wfile.write(piece)
                    sent += len(piece)
            except (BrokenPipeError, ConnectionResetError):
                self.close_connection = True
            finally:
                with lock:
                    stats.body_bytes_written += sent

    return Handler


def _parse_range(header: str, size: int) -> tuple[int, int]:
    spec = header.split("=", 1)[1].strip()
    first, _, last = spec.partition("-")
    start = int(first)
    stop = int(last) if last else size - 1
    return start, min(stop, size - 1)


@contextmanager
def serve(payload: bytes | Path, *, mode: Mode = "ranges") -> Iterator[tuple[str, ServeStats]]:
    """Serve `payload` over HTTP on loopback. Yields the URL and the server's stats."""
    body = payload.read_bytes() if isinstance(payload, Path) else payload
    stats = ServeStats()
    server = ThreadingHTTPServer(("127.0.0.1", 0), _handler(body, mode, stats))
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}/fixture.h5", stats
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
