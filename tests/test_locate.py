"""Where a dataset config's `path` resolves to, and why.

The rule these tests pin is that a local copy always wins. Falling back to the network
while the data sits on the filesystem would turn a one-second read into a network-bound
one, and nothing in a result folder would say so.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from fmeval.data.locate import (
    DATA_TOKEN,
    default_data_url,
    is_url,
    resolve_dataset_path,
)

URL = "https://portal.nersc.gov/project/m4790/Data"
RELATIVE = "kinet/doubly_periodic/sys_Re-5e4/D2Q9_shape-256-256_T-10000_H-dc804f.h5"


@pytest.fixture
def root(tmp_path):
    return tmp_path / "datasets"


def test_a_present_local_copy_wins(root):
    """Even with a URL configured. A network read must never be chosen silently."""
    local = root / RELATIVE
    local.parent.mkdir(parents=True)
    local.write_bytes(b"")

    found = resolve_dataset_path(f"{DATA_TOKEN}/{RELATIVE}", root, data_url=URL)

    assert found.source == "local"
    assert found.target == local
    assert found.url == f"{URL}/{RELATIVE}", "the mirror is still reported, just not used"


def test_a_missing_local_copy_falls_back_to_the_published_url(root):
    found = resolve_dataset_path(f"{DATA_TOKEN}/{RELATIVE}", root, data_url=URL)

    assert found.source == "url"
    assert found.target == f"{URL}/{RELATIVE}"
    assert is_url(found.target)


def test_an_already_resolved_path_works_too(root):
    """`evaluate.py` hands over a path Hydra has already expanded; `exemplars.py` does not."""
    found = resolve_dataset_path(root / RELATIVE, root, data_url=URL)
    assert found.target == f"{URL}/{RELATIVE}"


def test_the_url_is_built_from_the_relative_path_not_the_token(tmp_path):
    """`paths.data=/somewhere/else` is a documented override, so the token is not always
    what stands in front of the file."""
    root = tmp_path / "elsewhere"
    found = resolve_dataset_path(root / RELATIVE, root, data_url=URL)
    assert found.target == f"{URL}/{RELATIVE}"


def test_a_symlinked_root_still_derives_the_mirror(tmp_path):
    """`datasets` is a symlink on NERSC, and a path may name either side of it."""
    real = tmp_path / "cfs" / "Data"
    (real / RELATIVE).parent.mkdir(parents=True)
    link = tmp_path / "datasets"
    link.symlink_to(real)

    found = resolve_dataset_path(real / RELATIVE, link, data_url=URL)
    assert found.target == f"{URL}/{RELATIVE}"


def test_each_segment_is_quoted(root):
    """A filename with a space or a `#` truncates a raw URL."""
    found = resolve_dataset_path(f"{DATA_TOKEN}/a b/c#d.h5", root, data_url=URL)
    assert found.target == f"{URL}/a%20b/c%23d.h5"


def test_a_path_outside_the_data_root_refuses_to_guess_a_url(tmp_path):
    """There is no mirror for it, so a derived URL would be a fabrication that 404s."""
    with pytest.raises(FileNotFoundError, match="not under `paths.data`"):
        resolve_dataset_path(tmp_path / "stray" / "x.h5", tmp_path / "datasets", data_url=URL)


def test_a_null_data_url_restores_the_old_failure(root):
    with pytest.raises(FileNotFoundError, match="`paths.data_url` is null"):
        resolve_dataset_path(f"{DATA_TOKEN}/{RELATIVE}", root, data_url=None)


def test_allow_url_false_never_reaches_the_network(root):
    with pytest.raises(FileNotFoundError, match="local copy only"):
        resolve_dataset_path(f"{DATA_TOKEN}/{RELATIVE}", root, data_url=URL, allow_url=False)


def test_a_missing_root_still_explains_the_symlink(root):
    """The first thing a new user hits, and the reason this message exists at all."""
    with pytest.raises(FileNotFoundError, match="ln -s /global/cfs/cdirs/m4790/Data datasets"):
        resolve_dataset_path(f"{DATA_TOKEN}/{RELATIVE}", root, data_url=None)


def test_the_message_names_the_file_and_the_local_path(root):
    with pytest.raises(FileNotFoundError) as excinfo:
        resolve_dataset_path(f"{DATA_TOKEN}/{RELATIVE}", root, data_url=None)
    message = str(excinfo.value)
    assert "D2Q9_shape-256-256_T-10000_H-dc804f.h5" in message
    assert str(root / RELATIVE) in message


def test_is_url_rejects_a_path():
    assert not is_url(Path("/global/cfs/cdirs/m4790/Data/x.h5"))
    assert is_url("http://example.invalid/x.h5")


def test_the_committed_default_url_is_readable_without_hydra():
    """`paths.data` interpolates ${hydra:runtime.cwd} and would raise; this key must not."""
    assert default_data_url() == URL
