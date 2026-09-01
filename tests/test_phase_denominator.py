"""SV-2-PHASE-EXIT — the phase's denominator is PHASE_ORDER, not what ran.

CORRECTED BASELINE. An earlier version of this docstring said that ``cmd_check``
derived both the printed fraction and the exit code from the results it
collected, and that a readiness phase which lost a check printed ``11/11 PASS``
and exited ``0``. That was written from reasoning, not from a run, and it is
false. Measured against ``main`` 3df724d, with R5 dropped from ``_REGISTRY`` and
readiness run against a fixture repo::

    R5     -          not run
    READINESS: 1/12 PASS  ESCALATED=1  NA=9        exit 3

The denominator was already ``len(PHASE_ORDER[phase])`` on that build, and
``phase_table`` already rendered the missing row as ``not run``.

The real defect is narrower and is what the two guards below fix: eleven
statuses were counted beside a denominator of twelve, and the ladder answered
``3`` -- "unmeasured, stale or awaiting sign-off" -- for a registry that could
not account for its own declared parts. That is an instrument fault and must
exit ``1``.

Two guards now stand between that and a green build, and both are exercised
here in a control pair:

* ``_run_phase`` emits a FAIL for any declared id whose result did not come
  back from the loop, in ``PHASE_ORDER`` position;
* ``cmd_check`` compares the number of results aggregated against
  ``len(phase_ids(phase)) * len(repos)`` and exits ``1`` on a mismatch, before
  the status ladder is consulted.

The positive halves force each guard by making the loop lose a result. The
negative halves prove neither fires on a complete run, and that the complete
run's exit code is the one the pre-change build produced.

No model repo is read or written: every run here uses a fixture ``Repo`` on a
temp path, and ``store.save`` is redirected to the same temp path.
"""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

import pytest

from resilient_mlkit import checks as checks_pkg
from resilient_mlkit import cli
from resilient_mlkit.checks import PHASE_ORDER, CheckSpec, RunContext, phase_ids
from resilient_mlkit.cli import LOST_RESULT_REASON, _run_phase, cmd_check
from resilient_mlkit.core.repo import Repo
from resilient_mlkit.core.result import CheckResult, Status

PHASE = "readiness"


def _make_repo(root: Path, name: str = "fixture") -> Repo:
    path = root / f"resilient-{name}"
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "-C", str(path), "init", "-q"], check=True)
    return Repo(name=name, path=path)


@pytest.fixture
def repo(tmp_path: Path) -> Repo:
    return _make_repo(tmp_path)


def _args(root: Path) -> argparse.Namespace:
    return argparse.Namespace(
        root=str(root), repo="arabica", portfolio=False, phase=PHASE,
        offline=True, timeout=5.0,
    )


@pytest.fixture
def one_repo_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> argparse.Namespace:
    """A cmd_check invocation wired to exactly one fixture repo under tmp_path."""
    fixture = _make_repo(tmp_path, "arabica")
    monkeypatch.setattr(cli, "discover", lambda root: [fixture])
    monkeypatch.setattr(cli, "find_root", lambda *a, **k: tmp_path)
    return _args(tmp_path)


# -- _run_phase: the per-result guard ------------------------------------


def test_run_phase_returns_one_result_per_declared_id(repo: Repo) -> None:
    """Negative half: a complete run needs no synthesis and carries no lost row."""
    ctx = RunContext(nonce="TEST", root=repo.path.parent, offline=True, timeout=5.0)
    results = _run_phase(repo, PHASE, ctx)
    assert [r.check_id for r in results] == PHASE_ORDER[PHASE]
    assert [r for r in results if r.reason == LOST_RESULT_REASON] == []


def test_run_phase_fails_the_id_whose_result_went_missing(
    repo: Repo, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Positive half: force the loop to drop R5's result; get a FAIL in R5's slot.

    The drop is injected at ``for_phase`` -- the loop is handed a spec list with
    R5 removed -- which is precisely the shape the old ``if cid in _REGISTRY``
    filter produced.
    """
    real = cli.for_phase

    def lossy(phase: str):
        return [s for s in real(phase) if s.check_id != "R5"]

    monkeypatch.setattr(cli, "for_phase", lossy)

    ctx = RunContext(nonce="TEST", root=repo.path.parent, offline=True, timeout=5.0)
    results = _run_phase(repo, PHASE, ctx)

    # Length and ORDER are both restored, not just the count.
    assert [r.check_id for r in results] == PHASE_ORDER[PHASE]
    lost = next(r for r in results if r.check_id == "R5")
    assert lost.status is Status.FAIL
    assert lost.reason == LOST_RESULT_REASON
    assert "R5" not in lost.evidence["produced"]
    # Nothing else was disturbed.
    assert [r.check_id for r in results if r.reason == LOST_RESULT_REASON] == ["R5"]


# -- cmd_check: the exit-code guard --------------------------------------


def test_complete_phase_does_not_exit_incomplete(
    one_repo_run: argparse.Namespace, capsys: pytest.CaptureFixture[str]
) -> None:
    """Negative half: a complete run reaches the status ladder, not the guard.

    On a fixture repo with no bindings every readiness check reports NA or
    ESCALATED, so the ladder's answer is 3. What matters is that it is the
    LADDER's answer: the incompleteness guard stayed silent.
    """
    code = cmd_check(one_repo_run)
    err = capsys.readouterr().err
    assert "INCOMPLETE" not in err
    assert code == 3


def test_lost_check_exits_one(
    one_repo_run: argparse.Namespace,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Positive half: a phase that cannot account for every declared check exits 1.

    ``_run_phase`` is replaced wholesale so that the guard being tested is
    ``cmd_check``'s own denominator comparison and not the backstop inside
    ``_run_phase``. Without the comparison this run prints ``11/12`` and returns
    3 -- incomplete, which reads as "unmeasured", not as "failed".
    """
    real = cli._run_phase

    def lossy(repo: Repo, phase: str, ctx: RunContext):
        return [r for r in real(repo, phase, ctx) if r.check_id != "R5"]

    monkeypatch.setattr(cli, "_run_phase", lossy)

    code = cmd_check(one_repo_run)
    captured = capsys.readouterr()
    assert code == 1
    assert "INCOMPLETE" in captured.err
    # The message has to state both sides of the comparison or it is not
    # actionable: how many came back, and how many the phase declares.
    assert f"{len(phase_ids(PHASE)) - 1} result(s)" in captured.err
    assert f"{len(phase_ids(PHASE))} declared check(s)" in captured.err


def test_lost_check_exits_one_from_a_production_shaped_defect(
    one_repo_run: argparse.Namespace,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The guard fires without replacing ``_run_phase``.

    ``test_lost_check_exits_one`` above forces ``cmd_check``'s denominator
    comparison by replacing ``_run_phase`` wholesale -- a shape production
    cannot reach, because ``_run_phase`` now backfills every declared id before
    returning. A control that only fires in a shape production never uses
    measures the test, not the code, so this is the same guard forced through a
    defect that production CAN have.

    ``_run_phase`` does not overwrite ``result.check_id`` with ``spec.check_id``.
    A check whose function returns a ``CheckResult`` carrying the wrong id -- a
    copy-paste inside a check module -- therefore leaves its declared id
    unproduced. The backfill supplies a FAIL for the declared id, the
    mislabelled row is kept rather than dropped, and the run arrives at the
    guard with one row more than the phase declares.
    """
    real_spec = checks_pkg.get("R5")

    def mislabelling(repo: Repo, ctx: RunContext) -> CheckResult:
        # The defect is CONSTRUCTED, not assigned in afterwards. This used to
        # read `result.check_id = "R5_TYPO"`, which M-02 now refuses by name
        # (`VerdictSealed`): a formed verdict is not editable. The refusal is
        # correct and the test is unchanged in what it drives -- the docstring
        # above already names the production shape as "a copy-paste inside a
        # check module", and a copy-paste writes the wrong id at the call to
        # the constructor, which is exactly what this now does. Every assertion
        # below is byte-identical.
        result = real_spec.fn(repo, ctx)
        return CheckResult(
            check_id="R5_TYPO",
            phase=result.phase,
            status=result.status,
            reason=result.reason,
            evidence=dict(result.evidence),
        )

    monkeypatch.setitem(
        checks_pkg._REGISTRY,
        "R5",
        CheckSpec("R5", PHASE, real_spec.title, mislabelling),
    )

    code = cmd_check(one_repo_run)
    err = capsys.readouterr().err
    assert code == 1
    assert "INCOMPLETE" in err
    # One row MORE than declared, not fewer: the declared id was backfilled and
    # the mislabelled row was kept. Both halves of the comparison are named.
    assert f"{len(phase_ids(PHASE)) + 1} result(s)" in err
    assert f"{len(phase_ids(PHASE))} declared check(s)" in err
