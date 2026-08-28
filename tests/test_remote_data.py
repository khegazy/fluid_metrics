"""Reading a trajectory over HTTP, and refusing to when the server cannot be trusted.

These run in the default suite: the server is a local one on loopback, so the whole remote
path is exercised offline. The `web` marker is reserved for tests that reach the real
portal.

The assertion that matters most is `test_a_range_ignoring_server_raises_instead_of_
downloading`. Measured against portal.nersc.gov on 2026-08-27, *any* multi-range header --
two ranges, or two hundred -- comes back `200` with `Content-Length: 178271350284`. Reading
that body would pull 166 GiB into memory and across a shared science link, so a non-206 is
a hard error whose body is never touched.
"""

from __future__ import annotations

import io

import numpy as np
import pytest

from fmeval.data._timeaxis import NonUniformTimeAxis, read_time_axis
from fmeval.data.kinet_raw import KinetRawTrajectory
from fmeval.data.remote import (
    HTTPRangeFile,
    RangeUnsupported,
    RemoteFileChanged,
)
from fmeval.data.well import WellTrajectory
from tests.fixtures_h5 import N_FRAMES, write_kinet_raw, write_well
from tests.http_fixture import serve


@pytest.fixture
def kinet_file(tmp_path):
    return write_kinet_raw(tmp_path / "kinet_raw.h5")


# --- the reader over HTTP is the reader ---------------------------------------------


@pytest.mark.parametrize(
    "writer,reader",
    [(write_kinet_raw, KinetRawTrajectory), (write_well, WellTrajectory)],
    ids=["kinet_raw", "well"],
)
def test_the_remote_reader_matches_the_local_one(tmp_path, writer, reader):
    """The same file through the same reader, over a socket instead of a filesystem.

    Bitwise, not approximate: these are the same bytes decoded by the same code, so
    anything short of equality is a transport bug.
    """
    path = writer(tmp_path / "fixture.h5")

    with serve(path) as (url, _stats), reader(path) as local, reader(url) as over_http:
        assert over_http.is_remote and not local.is_remote
        assert over_http.grid == local.grid
        assert over_http.fields == local.fields
        assert len(over_http) == len(local)
        np.testing.assert_array_equal(over_http.times, local.times)

        for t in range(N_FRAMES):
            here = local.frame(t, [f for f in local.fields if f != "distribution"])
            there = over_http.frame(t, [f for f in over_http.fields if f != "distribution"])
            assert there.time == here.time
            for name, expected in here.fields.items():
                np.testing.assert_array_equal(there.fields[name], expected, err_msg=name)


def test_the_url_is_what_provenance_records(kinet_file):
    with serve(kinet_file) as (url, _stats), KinetRawTrajectory(url) as traj:
        meta = traj.meta
        assert meta["path"] == url
        assert meta["source"] == "url"
        assert meta["remote"]["url"] == url
        assert meta["remote"]["size_bytes"] == kinet_file.stat().st_size
        assert traj.path is None, "a URL is not a Path; `.exists()` on one would be a lie"


# --- refusing a server that cannot be trusted ----------------------------------------


def test_a_range_ignoring_server_raises_instead_of_downloading(kinet_file):
    """A 200 in answer to a Range request is the whole file. It must never be read."""
    body = b"\x00" * (8 * 1024 * 1024)

    with serve(body, mode="ignore_ranges") as (url, stats):
        stream = HTTPRangeFile(url)  # the HEAD advertises ranges, as Apache's does
        with pytest.raises(RangeUnsupported, match="not 206"):
            stream.read(16)

        assert stream.stats.bytes_fetched == 0, "the client counted body bytes it should not have"
        assert stats.body_bytes_written < len(body), (
            "the server managed to send the whole body, so the client drained a response "
            "it was supposed to discard unread"
        )
        stream.close()


def test_a_server_without_accept_ranges_is_refused_at_open(kinet_file):
    """Before h5py is ever handed the object, so the failure names the real cause."""
    with serve(kinet_file, mode="no_accept_ranges") as (url, stats):
        with pytest.raises(RangeUnsupported, match="Accept-Ranges"):
            HTTPRangeFile(url)
        assert stats.range_requests == 0


def test_a_file_replaced_mid_read_raises(kinet_file):
    """Splicing two HDF5 images together would produce numbers from neither."""
    with serve(kinet_file, mode="etag_flips") as (url, _stats):
        stream = HTTPRangeFile(url, block_size=4096)
        stream.read(16)
        with pytest.raises(RemoteFileChanged, match="ETag changed"):
            stream.seek(stream.size - 4096)  # a different block, so a second request
            stream.read(4096)
        stream.close()


def test_a_dropped_connection_is_retried(kinet_file):
    """Keep-alive connections are closed by servers all the time; that is not an error."""
    with serve(kinet_file, mode="drop_once") as (url, _stats):
        with KinetRawTrajectory(url) as traj:
            assert traj.frame(1, ["density"])["density"].shape[0] == 1
            assert traj._remote.stats.retries >= 1


def test_only_one_range_is_ever_requested(kinet_file):
    """The rule that keeps this client structurally clear of the 200-full-body path."""
    with serve(kinet_file) as (url, stats), KinetRawTrajectory(url) as traj:
        for t in range(N_FRAMES):
            traj.frame(t, ["density", "velocity"])

    assert stats.ranges_seen, "no range requests were recorded; the spy did not fire"
    for header in stats.ranges_seen:
        assert "," not in header, f"a multi-range header was sent: {header!r}"


def test_an_unbounded_read_is_refused(kinet_file):
    """`read(-1)` on the production trajectory is 166 GiB. HDF5 never asks for one."""
    with serve(kinet_file) as (url, _stats):
        stream = HTTPRangeFile(url)
        with pytest.raises(ValueError, match="unbounded read"):
            stream.read(-1)
        stream.close()


def test_the_client_is_not_an_io_subclass(kinet_file):
    """`io.RawIOBase` supplies a `readinto` that raises a bare NotImplementedError.

    h5py prefers `readinto` over `read`, so inheriting one is fatal and the traceback
    points into h5fd.pyx with no message. Measured; see fmeval/data/remote.py.
    """
    with serve(kinet_file) as (url, _stats):
        stream = HTTPRangeFile(url)
        assert not isinstance(stream, io.IOBase)
        assert hasattr(stream, "readinto")
        stream.close()


# --- the clock -----------------------------------------------------------------------


def test_a_non_uniform_clock_is_refused_rather_than_smoothed(tmp_path):
    """A reconstruction that disagrees with the file must fail, not quietly win."""
    times = np.arange(N_FRAMES, dtype=np.float64) * 0.25
    times[3] += 1e-9
    path = write_kinet_raw(tmp_path / "wobbly.h5", times=times)

    with serve(path) as (url, _stats):
        with pytest.raises(NonUniformTimeAxis, match=r"time\[3\]"):
            KinetRawTrajectory(url)


def test_the_clock_can_still_be_read_in_full_on_request(tmp_path):
    """The escape hatch, for a file whose clock is genuinely irregular."""
    times = np.arange(N_FRAMES, dtype=np.float64) * 0.25
    times[3] += 1e-9
    path = write_kinet_raw(tmp_path / "wobbly.h5", times=times)

    with serve(path) as (url, _stats), KinetRawTrajectory(url, time_axis="read") as traj:
        np.testing.assert_array_equal(traj.times, times)


def test_a_local_clock_is_never_reconstructed(kinet_file):
    """Local reads keep their previous behaviour exactly: the file is the authority."""
    import h5py

    with h5py.File(kinet_file, "r") as handle:
        direct = read_time_axis(handle["time"], remote=False)
        np.testing.assert_array_equal(direct, handle["time"][:])


def test_a_contiguous_clock_is_read_directly_even_remotely(tmp_path):
    """The Well layout stores it contiguously, so one range GET fetches the whole axis."""
    import h5py

    path = write_well(tmp_path / "well.h5")
    with h5py.File(path, "r") as handle:
        assert handle["dimensions/time"].chunks is None
        axis = read_time_axis(handle["dimensions/time"], remote=True)
        np.testing.assert_array_equal(axis, handle["dimensions/time"][:])


def test_opening_and_iterating_never_slices_a_chunked_clock(kinet_file):
    """The guard the existing time-axis spy cannot see.

    ``test_never_slices_the_time_axis`` in tests/test_loader_contract.py filters recorded
    keys with ``len(key) >= 3`` to reach the time position of a ``(sim, C, T, *spatial)``
    read. A 1-D ``time[:]`` arrives as the key ``(slice(None),)`` -- length one -- so it
    is invisible there, and it is the single most expensive read in this package:
    ``time`` is chunked ``(1,)`` with its 10001 chunks interleaved 17.8 MiB apart across
    the 166 GiB production file, so slicing it whole is 9938 requests, 297 s and 2.5 GiB
    to fetch 80 KB. See fmeval/data/_timeaxis.py.
    """
    import h5py

    seen: list[tuple[str, object]] = []
    original = h5py.Dataset.__getitem__

    def spy(self, key):
        seen.append((self.name, key))
        return original(self, key)

    h5py.Dataset.__getitem__ = spy
    try:
        with serve(kinet_file) as (url, _stats), KinetRawTrajectory(url) as traj:
            assert traj._file["time"].chunks is not None, "fixture stopped chunking the clock"
            n = len(traj)
            for _ in traj.iter_frames(["density"]):
                pass
    finally:
        h5py.Dataset.__getitem__ = original

    clock_reads = [key for name, key in seen if name.rsplit("/", 1)[-1] == "time"]
    assert clock_reads, "no reads of the clock were recorded; the spy did not fire"
    for key in clock_reads:
        span = len(range(*key.indices(n))) if isinstance(key, slice) else 1
        assert span <= 2, (
            f"the clock was read with {key!r}, spanning {span} of {n} entries. That "
            "dataset is chunked one element per chunk, so a full slice costs 9938 "
            "requests and 297 s on the production trajectory. See fmeval/data/_timeaxis.py."
        )
