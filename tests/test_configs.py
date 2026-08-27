"""The Hydra configuration must compose, and its documented overrides must work.

These are cheap and they catch a class of failure the rest of the suite cannot: a config that
only breaks when Hydra composes it, or an override form that a README promises and the config
rejects. A wrong command in the documentation is worse than none.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from hydra import compose, initialize_config_dir
from omegaconf import OmegaConf

CONFIGS = str(Path(__file__).resolve().parent.parent / "configs")


def build(*overrides: str):
    """Compose the config the way `evaluate.py` does, with CLI-style overrides.

    The HydraConfig singleton has to be installed explicitly. `hydra.main` does that for
    you, and without it `${hydra:runtime.cwd}` -- which `paths.data` depends on -- raises
    "HydraConfig was not set". Composing without it would test a configuration that never
    actually runs.
    """
    from hydra.core.hydra_config import HydraConfig

    with initialize_config_dir(config_dir=CONFIGS, version_base=None):
        cfg = compose(config_name="config", overrides=list(overrides),
                      return_hydra_config=True)
        HydraConfig.instance().set_config(cfg)
        return cfg


def test_default_config_composes():
    cfg = build()
    assert cfg.metrics
    assert cfg.dataset.name and cfg.dataset.format and cfg.dataset.path
    assert cfg.degradation.ladder
    assert cfg.seed


def test_hydra_job_chdir_is_false():
    """With chdir=true the relative datasets symlink and the package imports both break."""
    assert build().hydra.job.chdir is False


def test_hydra_output_dirs_resolve_without_a_live_hydra_context():
    """`hydra.sweep.dir` is resolved before HydraConfig exists.

    Interpolating `${paths.results}` there reaches `${hydra:runtime.cwd}` and fails with
    "HydraConfig was not set", which breaks every multirun. Keep these plain and relative.
    """
    cfg = build()
    for key in ("run.dir", "sweep.dir"):
        value = OmegaConf.select(cfg.hydra, key)
        assert "${" not in str(value), f"hydra.{key} still contains an interpolation"
        assert not str(value).startswith("/"), f"hydra.{key} should be relative"


@pytest.mark.parametrize("group,option", [
    ("dataset", "kinet_re5e4_dev"),
    ("dataset", "kinet_re5e4"),
    ("dataset", "well_re5e4"),
    ("dataset", "synthetic_ensemble_dev"),
    ("degradation", "default"),
    ("degradation", "quick"),
    ("degradation", "ensemble_miscalibration"),
    ("report", "default"),
    ("report", "none"),
])
def test_every_config_group_option_composes(group, option):
    """Every file offered as a group option must actually work when selected."""
    cfg = build(f"{group}={option}")
    assert OmegaConf.select(cfg, group) is not None


#: Directories under `configs/` that Hydra never composes, so their files are not group
#: options and cannot be checked by composing them.
#:
#: `dataset_family` holds shared fragments referenced by dataset configs rather than
#: selected on the command line. `cards` holds the settings for generating documentation
#: -- the canonical exemplar frame, which datasets a card may cite, figure DPI -- read
#: directly with OmegaConf by `python -m fmeval.cards`. Generating documentation is not an
#: experiment: it must not create a run folder or a `.hydra` directory, so it does not go
#: through Hydra at all.
NOT_HYDRA_GROUPS = {"dataset_family", "cards"}


def test_every_group_option_on_disk_is_tested(group_files=None):
    """A new config file must be added to the parametrisation above."""
    tested = {("dataset", "kinet_re5e4_dev"), ("dataset", "kinet_re5e4"),
              ("dataset", "well_re5e4"), ("dataset", "synthetic_ensemble_dev"),
              ("degradation", "default"), ("degradation", "quick"),
              ("degradation", "ensemble_miscalibration"),
              ("report", "default"), ("report", "none")}
    on_disk = {
        (d.name, f.stem)
        for d in Path(CONFIGS).iterdir() if d.is_dir() and d.name not in NOT_HYDRA_GROUPS
        for f in d.glob("*.yaml")
    }
    missing = sorted(on_disk - tested)
    assert not missing, f"add these to test_every_config_group_option_composes: {missing}"


# --- the override forms the documentation promises ------------------------------------


@pytest.mark.parametrize("override,check", [
    # The headline case: choose the metric on the command line.
    ("metrics=[mse]", lambda c: list(c.metrics) == ["mse"]),
    ("metrics=[mae,mse,nrmse]", lambda c: len(c.metrics) == 3),
    # Sizing knobs.
    ("dataset.time.reduction=100", lambda c: c.dataset.time.reduction == 100),
    ("dataset.time.start=2000", lambda c: c.dataset.time.start == 2000),
    ("dataset.time.max_frames=5", lambda c: c.dataset.time.max_frames == 5),
    ("analysis_grid.resolution=128", lambda c: c.analysis_grid.resolution == 128),
    ("analysis_grid.method=subsample", lambda c: c.analysis_grid.method == "subsample"),
    # Fields and seed.
    ("fields=[vorticity]", lambda c: list(c.fields) == ["vorticity"]),
    ("seed=1", lambda c: c.seed == 1),
    # Ladder selection.
    ("degradation.only=[translate_x]", lambda c: list(c.degradation.only) == ["translate_x"]),
    ("degradation.skip=[median_blur]", lambda c: list(c.degradation.skip) == ["median_blur"]),
    # Reporting.
    ("report.style.theme=paper", lambda c: c.report.style.theme == "paper"),
    # Data root, for someone whose data is not where the symlink points.
    ("paths.data=/tmp/data", lambda c: str(c.paths.data) == "/tmp/data"),
])
def test_documented_override_works(override, check):
    assert check(build(override)), f"override {override!r} did not take effect"


def test_nested_ladder_overrides_need_no_plus_prefix():
    """`enabled` must be declared on every entry, or overriding it is inconsistent.

    Hydra's struct mode refuses to *add* a key, so an entry that omits `enabled` can only be
    disabled with a `+` prefix while an entry that declares it cannot. Declaring it
    everywhere removes that asymmetry.
    """
    cfg = build("degradation=default",
                "degradation.ladder.gaussian_blur.enabled=false",
                "degradation.ladder.disk_blur.enabled=true",
                "degradation.ladder.gaussian_blur.severities=[1,2]")
    assert cfg.degradation.ladder.gaussian_blur.enabled is False
    assert cfg.degradation.ladder.disk_blur.enabled is True
    assert list(cfg.degradation.ladder.gaussian_blur.severities) == [1, 2]


def test_every_ladder_entry_declares_enabled():
    for option in ("default", "quick"):
        ladder = build(f"degradation={option}").degradation.ladder
        missing = [name for name, entry in ladder.items() if "enabled" not in entry]
        assert not missing, (
            f"degradation/{option}.yaml entries {missing} omit `enabled`, so a CLI override "
            "of it would need a `+` prefix on those and not on the others"
        )


def test_every_ladder_entry_names_a_registered_operator():
    from degradations import registry as deg

    deg.discover()
    for option in ("default", "quick"):
        ladder = build(f"degradation={option}").degradation.ladder
        for label, entry in ladder.items():
            op = entry.get("op", label)
            assert op in deg.REGISTRY, (
                f"degradation/{option}.yaml entry {label!r} names operator {op!r}, "
                f"which is not registered"
            )


def test_every_dataset_names_a_registered_reader():
    from fmeval.data import kinet_raw, well  # noqa: F401  (register the formats)
    from fmeval.data.base import READERS

    for option in ("kinet_re5e4_dev", "kinet_re5e4", "well_re5e4"):
        cfg = build(f"dataset={option}")
        assert cfg.dataset.format in READERS, (
            f"dataset/{option}.yaml declares format {cfg.dataset.format!r}, "
            f"which has no reader"
        )


def test_default_metrics_are_registered():
    from metrics import registry as met

    for name in build().metrics:
        met.get(name)  # raises KeyError with the available list if absent


def test_the_card_settings_are_readable_without_hydra():
    """`configs/cards/default.yaml` is read directly, so it must stand on its own.

    It is excluded from the group-composition test above because it is not a Hydra group.
    That exclusion would be a hiding place if nothing else read the file, so this checks
    the keys the generators depend on are present and that no Hydra interpolation has
    crept in -- one would resolve under `evaluate.py` and fail under `python -m
    fmeval.cards`, which is the kind of difference that shows up only in the artifact.
    """
    from omegaconf import OmegaConf

    raw = (Path(CONFIGS) / "cards" / "default.yaml").read_text()
    assert "${" not in raw, "card settings must not interpolate; nothing resolves them"

    cfg = OmegaConf.load(Path(CONFIGS) / "cards" / "default.yaml")
    assert "kinet_re5e4_dev" not in list(cfg.evidence_datasets), (
        "the dev dataset must never be a source of card evidence: it is the first 100 "
        "solver steps, before the flow develops"
    )
    assert cfg.exemplar_frame.dataset in list(cfg.evidence_datasets)
    assert int(cfg.exemplar_frame.index) >= int(cfg.evidence_window.start), (
        "the exemplar frame must lie inside the developed-flow window"
    )
    assert int(cfg.figures.dpi) > 0
