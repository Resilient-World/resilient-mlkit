"""E-038's verification, RESTORED — and driven both ways (E-M42 §7).

WHY THIS FILE EXISTS TWICE.

PR #20, *"VERIFY E-038: the R10 registry repair STANDS; two defects in it
repaired"*, is recorded MERGED (2026-08-31T04:13:41Z, merge commit
``1170a7ed``). It is not on ``main``::

    git merge-base --is-ancestor 1170a7e origin/main   ->  NO
    git merge-base --is-ancestor 63682f4 origin/main   ->  NO   the verify commit
    git merge-base --is-ancestor b1cc706 origin/main   ->  YES  its parent
    git merge-base --is-ancestor 3b7ee52 origin/main   ->  YES  the E-038 fix

Exactly one commit of a merged PR is missing — ``+341/-7`` across four files,
this file among them. The commits under it are present, so this is not a branch
that never landed: it landed and was later lost. Read on ``main``'s tree the
day E-M42 was opened, all three of its repairs were genuinely gone, and this
file is the control that says so in both directions.

The three, each with a control that FIRES on the unrepaired behaviour:

1. **ORDER.** ``r10_fabricated_defaults`` adjudicated the derivation refusal
   BEFORE the defect lane, so a repo with a measured ``SATISFIES_GATE`` default
   AND a broken derivation was reported **NA** — "could not measure" standing
   in for "measured, and it is wrong", with ``satisfies_gate: 1`` sitting in
   the evidence unmentioned.
2. **THE UNGUARDED READ.** ``metric_registry.derive`` read every file without a
   guard, so one unreadable file under a DECLARED tree — a dangling symlink is
   enough — took R10 out with a ``FileNotFoundError`` where the scanner beside
   it skips the same file.
3. **THE DISCLOSURE.** The R10 report said nothing about files the derivation
   could not read, so a skipped file was silent.

Restored rather than cherry-picked: the surrounding code moved through E-M41
(``Finding.reason``/``repair``, the ``[metrics]`` table, D1/D2), and the
self-only figure in the module docstring is RE-MEASURED at today's fleet mains
rather than carried over — the old one's conclusion no longer holds.
"""

from __future__ import annotations

import os
import textwrap
from pathlib import Path

import pytest

from resilient_mlkit.checks import RunContext
from resilient_mlkit.checks.readiness import r10_fabricated_defaults
from resilient_mlkit.core import metric_registry
from resilient_mlkit.core.repo import Repo

REPO_TOML = """\
[repo]
name = "fixture"

[source]
trees = ["src"]
"""


def make_repo(tmp_path: Path, files: dict[str, str]) -> Repo:
    root = tmp_path / "resilient-fixture"
    (root / ".mlkit").mkdir(parents=True)
    (root / ".mlkit" / "repo.toml").write_text(REPO_TOML)
    for rel, body in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(textwrap.dedent(body))
    return Repo("fixture", root)


def ctx_for(repo: Repo) -> RunContext:
    return RunContext(root=repo.path.parent, nonce="e038-verify", offline=True)


# A default that SATISFIES the gate consuming it: rmse is in mlkit's built-in
# vocabulary, lower is better, and 0.0 is the value that would pass.
SATISFYING = """\
    def score(a, b):
        if not a:
            return {"rmse": 0.0}
        return {"rmse": sum(a) / len(b)}
"""


# -- defect 1: ORDER ---------------------------------------------------------


def _break_the_derivation(monkeypatch):
    """Force `derive` to refuse, the way a broken anchor does."""
    monkeypatch.setattr(
        metric_registry, "_anchor_failure",
        lambda: "the derivation probe did not round-trip; this universe is not trusted",
    )


def test_a_measured_defect_is_not_hidden_behind_a_broken_derivation(tmp_path, monkeypatch):
    """The repaired ORDER: FAIL, and the refusal carried into the reason."""
    repo = make_repo(tmp_path, {"src/score.py": SATISFYING})
    _break_the_derivation(monkeypatch)

    result = r10_fabricated_defaults(repo, ctx_for(repo))

    assert result.status == "FAIL", result.reason
    assert result.evidence["satisfies_gate"] >= 1
    # The refusal is NOT dropped: it rides in the reason, first, so a truncated
    # reason keeps "there may be more than this".
    assert "ALSO unmeasured" in result.reason
    assert "evidence.metric_registry.refusal" in result.reason


def test_the_refusal_still_produces_na_on_its_own_when_nothing_was_measured(
    tmp_path, monkeypatch
):
    """CONTROL, other direction. Remove the defect and the NA must come back."""
    repo = make_repo(tmp_path, {"src/clean.py": "def score(a, b):\n    return sum(a) / len(b)\n"})
    _break_the_derivation(monkeypatch)

    result = r10_fabricated_defaults(repo, ctx_for(repo))

    assert result.status == "NA"
    assert "not trusted" in result.reason


def test_control_the_unrepaired_order_would_have_reported_na(tmp_path, monkeypatch):
    """FIRES: the pre-repair ordering, applied to the same tree, gives NA.

    Driven rather than described. The unrepaired code returned the refusal NA
    before looking at `defects`, so this reproduces that decision from the
    evidence the repaired check publishes and asserts the two disagree — which
    is the whole claim, and it is a claim about a verdict, not about wording.
    """
    repo = make_repo(tmp_path, {"src/score.py": SATISFYING})
    _break_the_derivation(monkeypatch)

    repaired = r10_fabricated_defaults(repo, ctx_for(repo))
    registry = metric_registry.derive([repo.path / "src"], base=repo.path)

    unrepaired_status = "NA" if registry.refusal else repaired.status

    assert registry.refusal, "the fixture must actually break the derivation"
    assert unrepaired_status == "NA"
    assert repaired.status == "FAIL"
    assert unrepaired_status != repaired.status


# -- defect 2: the unguarded read -------------------------------------------


def _plant_unreadable(root: Path) -> Path:
    """A `*.py` under the declared tree that cannot be read.

    A dangling symlink is the case that was measured. Where symlinks are not
    available the test skips rather than asserting something weaker: an
    unreadable file that can be read is not a control.
    """
    target = root / "src" / "gone.py"
    try:
        os.symlink(root / "src" / "does-not-exist.py", target)
    except (OSError, NotImplementedError):  # pragma: no cover - platform
        pytest.skip("this platform cannot create a dangling symlink")
    return target


def test_an_unreadable_file_under_a_declared_tree_is_skipped_and_disclosed(tmp_path):
    repo = make_repo(tmp_path, {"src/ok.py": "def score(a, b):\n    return sum(a) / len(b)\n"})
    _plant_unreadable(repo.path)

    registry = metric_registry.derive([repo.path / "src"], base=repo.path)

    assert registry.unreadable, "the skip must be disclosed, never silent"
    assert len(registry.unreadable) == 1
    entry = registry.unreadable[0]
    assert entry.startswith("src/gone.py: ")
    assert "Error" in entry
    # Skipped, not refused: a one-symlink lever from FAIL to "could not
    # measure" is exactly what refusing here would hand an adopter.
    assert registry.refusal is None
    assert registry.to_dict()["unreadable"] == list(registry.unreadable)


def test_r10_still_measures_the_repo_with_an_unreadable_file_in_it(tmp_path):
    """It used to RAISE. The harness rendered the crash as a FAIL with a traceback."""
    repo = make_repo(tmp_path, {"src/score.py": SATISFYING})
    _plant_unreadable(repo.path)

    result = r10_fabricated_defaults(repo, ctx_for(repo))

    assert result.status == "FAIL"
    assert result.evidence["satisfies_gate"] >= 1
    assert result.evidence["metric_registry"]["unreadable"] == ["src/gone.py: FileNotFoundError"]


def test_control_the_scanner_and_the_registry_agree_about_the_same_file(tmp_path):
    """The reason for SKIPPING rather than refusing, asserted as a fact.

    `fabrication.scan_file` catches OSError and skips. If `derive` refused, the
    two halves of R10 would disagree about which files the repo has, and the
    check would be adjudicating a universe its own scanner does not use.
    """
    from resilient_mlkit.core import fabrication

    repo = make_repo(tmp_path, {"src/ok.py": "def score(a, b):\n    return sum(a) / len(b)\n"})
    missing = _plant_unreadable(repo.path)

    assert fabrication.scan_file(missing, "src/gone.py") == []
    registry = metric_registry.derive([repo.path / "src"], base=repo.path)
    assert "score" in registry.names


def test_a_readable_tree_discloses_zero_unreadable_files(tmp_path):
    """CONTROL, other direction: the field is not always non-empty."""
    repo = make_repo(tmp_path, {"src/ok.py": "def score(a, b):\n    return sum(a) / len(b)\n"})

    registry = metric_registry.derive([repo.path / "src"], base=repo.path)

    assert registry.unreadable == ()


# -- defect 3: the disclosure in the report ---------------------------------


def test_the_r10_report_line_names_the_unreadable_files(tmp_path):
    repo = make_repo(tmp_path, {"src/score.py": SATISFYING})
    _plant_unreadable(repo.path)

    r10_fabricated_defaults(repo, ctx_for(repo))
    report_text = (repo.path / "reports" / "fabricated_defaults.md").read_text()

    assert "files under a declared tree the derivation could not READ: 1" in report_text
    assert "src/gone.py: FileNotFoundError" in report_text


def test_the_r10_report_line_is_present_and_reads_zero_on_a_clean_tree(tmp_path):
    repo = make_repo(tmp_path, {"src/score.py": SATISFYING})

    r10_fabricated_defaults(repo, ctx_for(repo))
    report_text = (repo.path / "reports" / "fabricated_defaults.md").read_text()

    assert "files under a declared tree the derivation could not READ: 0" in report_text
    assert "FileNotFoundError" not in report_text


# -- the residual the exclusion costs, pinned -------------------------------


def test_residual_a_self_only_callable_is_outside_the_registry(tmp_path):
    """A `@property` deriving a figure from instance state is NOT a metric name.

    The stated limit, pinned in BOTH directions so the disclosure in
    ``metric_registry``'s docstring cannot go stale in place: the self-only
    method stays out, and the same body with one real parameter comes in.
    """
    repo = make_repo(tmp_path, {
        "src/model.py": """\
            class Model:
                @property
                def skill(self):
                    return self.hits / self.total

                def skill_of(self, hits, total):
                    return hits / total
        """,
    })

    registry = metric_registry.derive([repo.path / "src"], base=repo.path)

    # `names` holds NORMALISED spellings; `origins` keeps the source spelling.
    assert metric_registry.normalise("skill") not in registry.names
    assert metric_registry.normalise("skill_of") in registry.names
    assert registry.origin("skill_of").startswith("skill_of <- src/model.py:")
