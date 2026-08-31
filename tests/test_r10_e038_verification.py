"""Verification of the E-038 repair: three things it got wrong, pinned.

Written while adversarially driving ``fix/r10-metric-name-blindness-e-038`` at
``b1cc706``. The repair itself STANDS -- measured across the eight adopter
repos at their remote mains, it loses no finding, changes no severity, and adds
84; ``rmse`` planted into a clean fixture still FAILs with a byte-identical
reason. These are the three defects the drive found, each with the control that
fails if the defect returns.

1. ``metric_registry.derive`` read every file under a DECLARED tree with an
   unguarded ``read_text``, so one unreadable ``*.py`` raised out of R10.
   ``fabrication.scan_file`` catches ``OSError`` and skips, so the registry and
   the scan disagreed about which files the repo has.

2. The derivation refusal was adjudicated BEFORE the defect lane, so a broken
   derivation reported NA over a fabricated default that R10 had already
   measured and ranked ``SATISFIES_GATE``.

3. The self-only-parameter exclusion was in a code comment, not in the
   disclosure. It is a residual, not a bug; it is pinned here so it fails the
   day it closes.

Every test asserts the module binding first. This venv carries an editable
install pointing at a DIFFERENT checkout, and it has fooled agents in this repo
repeatedly.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from resilient_mlkit.checks import RunContext
from resilient_mlkit.checks.readiness import r10_fabricated_defaults
from resilient_mlkit.core import fabrication, metric_registry
from resilient_mlkit.core.repo import Repo

_EXPECTED_SRC = Path(__file__).resolve().parent.parent / "src" / "resilient_mlkit"


def test_this_suite_binds_to_the_worktree_not_an_installed_package() -> None:
    for module in (fabrication, metric_registry):
        assert Path(module.__file__).resolve().is_relative_to(_EXPECTED_SRC), (
            f"{module.__name__} bound to {module.__file__}, expected under "
            f"{_EXPECTED_SRC}"
        )


#: A fabricated default at a name mlkit's OWN word list knows. R10 must call
#: this a defect under every condition tested below.
VOCABULARY_FABRICATION = '''
import numpy as np


def rmse(predicted, observed):
    if len(observed) == 0:
        return 0.0
    return float(np.sqrt(np.mean((predicted - observed) ** 2)))
'''


def _fixture_repo(tmp_path: Path, body: str, name: str = "verify") -> Repo:
    (tmp_path / ".mlkit").mkdir()
    (tmp_path / ".mlkit" / "repo.toml").write_text(
        f'[repo]\nname = "{name}"\n\n[source]\ntrees = ["src"]\n', encoding="utf-8"
    )
    src = tmp_path / "src" / "pkg"
    src.mkdir(parents=True)
    (src / "metrics.py").write_text(body, encoding="utf-8")
    return Repo(name=name, path=tmp_path)


def _ctx(tmp_path: Path) -> RunContext:
    return RunContext(nonce="e038-verify", root=tmp_path.parent, offline=True, timeout=60)


# ---------------------------------------------------------------------------
# 1. An unreadable file under a declared tree
# ---------------------------------------------------------------------------


def test_an_unreadable_file_under_a_declared_tree_does_not_raise(
    tmp_path: Path,
) -> None:
    """The scan skips it, so the derivation must skip it too.

    Before this fix ``derive`` raised ``FileNotFoundError`` on a dangling
    ``*.py`` symlink and the harness rendered R10 as "check raised an
    unhandled exception". Fail-safe, but wrong: main reports the verdict.
    """
    repo = _fixture_repo(tmp_path, "def widget_ratio(a, b):\n    return float(a / b)\n")
    dangling = tmp_path / "src" / "pkg" / "dangling.py"
    dangling.symlink_to(tmp_path / "src" / "pkg" / "does_not_exist.py")
    assert not dangling.exists(), "fixture is not a dangling symlink"

    roots = [tmp_path / "src"]
    # The scanner's own answer, which the registry has to agree with.
    assert fabrication.scan_tree(roots, base=tmp_path) == []

    registry = metric_registry.derive(roots, base=tmp_path)
    assert registry.refusal is None, (
        "an unreadable file must NOT become a refusal: derive()'s refusal "
        "short-circuits R10 into NA, so that would be a one-symlink lever for "
        "turning a measured FAIL into 'could not measure'"
    )
    assert len(registry.unreadable) == 1, registry.unreadable
    assert "dangling.py" in registry.unreadable[0]
    assert registry.contains("widget_ratio"), "the readable file still derived"

    result = r10_fabricated_defaults(repo, _ctx(tmp_path))
    assert str(result.status) == "PASS", result.reason
    assert result.evidence["metric_registry"]["unreadable"], result.evidence
    report = (tmp_path / "reports" / "fabricated_defaults.md").read_text(encoding="utf-8")
    assert "could not READ" in report and "dangling.py" in report


def test_an_unreadable_file_does_not_hide_a_defect_in_a_readable_one(
    tmp_path: Path,
) -> None:
    """Check-not-dead for the skip: the FAIL still fires beside it."""
    repo = _fixture_repo(tmp_path, VOCABULARY_FABRICATION)
    (tmp_path / "src" / "pkg" / "dangling.py").symlink_to(tmp_path / "nowhere.py")

    result = r10_fabricated_defaults(repo, _ctx(tmp_path))
    assert str(result.status) == "FAIL", result.reason
    assert "rmse=0.0" in result.reason


# ---------------------------------------------------------------------------
# 2. A broken derivation must not swallow a measured defect
# ---------------------------------------------------------------------------


def test_a_broken_derivation_does_not_downgrade_a_measured_fail_to_na(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """FAIL outranks the refusal, and the refusal is still reported.

    ``rmse=0.0`` is adjudicated by the built-in vocabulary and by
    ``satisfies_a_gate``; neither consults the derived registry. Reporting NA
    here left ``satisfies_gate: 1`` in the evidence and no trace of it in the
    reason -- the collapse ``core.result.Status`` refuses by name.
    """
    repo = _fixture_repo(tmp_path, VOCABULARY_FABRICATION)

    intact = r10_fabricated_defaults(repo, _ctx(tmp_path))
    assert str(intact.status) == "FAIL", intact.reason

    monkeypatch.setattr(metric_registry, "_names_in", lambda source, display: {})
    assert metric_registry.derive([tmp_path / "src"], base=tmp_path).refusal is not None

    broken = r10_fabricated_defaults(repo, _ctx(tmp_path))
    assert str(broken.status) == "FAIL", (
        "a derivation that stopped running says nothing about whether a "
        f"vocabulary-named literal is fabricated; got {broken.status}"
    )
    assert "rmse=0.0" in broken.reason
    assert broken.evidence["satisfies_gate"] == 1
    assert "the derived name universe is ALSO unmeasured" in broken.reason, (
        "the refusal must survive into the FAIL reason, not be dropped: "
        + broken.reason
    )
    assert "E-038" in (broken.evidence["metric_registry"]["refusal"] or ""), (
        "and the refusal itself must be in the evidence, where truncation "
        "cannot reach it"
    )


def test_a_broken_derivation_is_still_na_when_nothing_was_measured(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The other half of the pair. Reordering must not kill the refusal lane."""
    repo = _fixture_repo(tmp_path, "def widget_ratio(a, b):\n    return float(a / b)\n")
    monkeypatch.setattr(metric_registry, "_names_in", lambda source, display: {})

    result = r10_fabricated_defaults(repo, _ctx(tmp_path))
    assert str(result.status) == "NA", result.reason
    assert "E-038" in result.reason


# ---------------------------------------------------------------------------
# 3. The residual, disclosed rather than left in a comment
# ---------------------------------------------------------------------------

SELF_ONLY = '''
class Panel:
    def __init__(self, hits, total):
        self._hits = hits
        self._total = total

    @property
    def hazard_uptake_ratio(self):
        """A figure derived from instance state, from no named parameter."""
        if not self._total:
            return 0.0
        return float(self._hits / self._total)

    def hazard_uptake_share(self):
        if not self._total:
            return 0.0
        return float(self._hits / self._total)
'''


def test_residual_a_self_only_callable_is_outside_the_registry(
    tmp_path: Path,
) -> None:
    """A stated limit, pinned so it FAILS the day it closes.

    ``_computes_a_figure`` requires at least one parameter that is not
    ``self``/``cls``. A ``@property`` or zero-argument method deriving a figure
    from instance state therefore never enters the universe, and the ``0.0``
    beside it stays invisible. Measured on the fleet: nineteen further sites,
    all of them in the NA lane and none of them changing a repo's verdict --
    the number is in ``metric_registry``'s module docstring. When this
    assertion fails, UPDATE THE DISCLOSURE; do not re-pin the silence.
    """
    root = tmp_path / "src"
    (root / "pkg").mkdir(parents=True)
    (root / "pkg" / "panel.py").write_text(SELF_ONLY, encoding="utf-8")

    registry = metric_registry.derive([root], base=tmp_path)
    assert not registry.contains("hazard_uptake_ratio")
    assert not registry.contains("hazard_uptake_share")
    assert fabrication.scan_tree([root], base=tmp_path, registry=registry) == []
