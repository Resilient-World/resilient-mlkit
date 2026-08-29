"""SV-3-PORTFOLIO-EXIT — the portfolio's exit code, and a header that counts.

Two defects in one function, both of the same family: a statement about the
portfolio that nothing derived and nothing checked.

**The exit code.** ``_cmd_portfolio`` ended ``return 0``. ``README.md:144``
says exit ``1`` means "something failed (CI gates on this)". For
``--portfolio`` that was false: a BLOCKED repo rendered in the table, printed
its reason, and exited green. Any CI job gating on this command gated on
nothing. The README states the contract correctly; the code is what was wrong,
and the code is what moved.

**The header.** The readiness column was labelled ``"R(9,10,11,1-8)"`` by
hand. That names eleven checks. Twelve run — R12 joined ``PHASE_ORDER`` and the
string did not follow, because nothing compared them. It is now derived by
compressing ``PHASE_ORDER`` into runs, so the label cannot disagree with the
cell beneath it.

The pairs below force each guard and then prove it silent on the legitimate
case. ``resolve`` is given hand-built results, never a model repo.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from resilient_mlkit.checks import PHASE_ORDER, PHASES
from resilient_mlkit.core.repo import Repo
from resilient_mlkit.core.result import CheckResult, Status
from resilient_mlkit.portfolio import (
    AWAITING,
    BLOCKED,
    IN_PROGRESS,
    READY,
    READY_PENDING_KEYS,
    RepoState,
    exit_code,
    gating_ids,
    phase_header,
    render_portfolio,
    resolve,
)

HUMAN_ONLY = ("S5", "D1", "D4", "D5", "E4", "E5")


def _phase_of(check_id: str) -> str:
    return next(p for p, ids in PHASE_ORDER.items() if check_id in ids)


def _repo(tmp_path: Path, name: str) -> Repo:
    path = tmp_path / name
    path.mkdir(parents=True, exist_ok=True)
    return Repo(name=name, path=path)


def _all_passing() -> dict[str, CheckResult]:
    """Every gating check PASS. The only input that may resolve READY."""
    return {
        cid: CheckResult.passed(cid, _phase_of(cid), {"fixture": True})
        for cid in gating_ids()
    }


def _ready(tmp_path: Path, name: str) -> RepoState:
    state = resolve(_repo(tmp_path, name), _all_passing())
    assert state.state == READY, state.reason
    return state


def _blocked(tmp_path: Path, name: str) -> RepoState:
    results = _all_passing()
    results["R9"] = CheckResult.failed("R9", "readiness", "fixture licence defect")
    state = resolve(_repo(tmp_path, name), results)
    assert state.state == BLOCKED, state.reason
    return state


def _awaiting(tmp_path: Path, name: str) -> RepoState:
    results = _all_passing()
    for cid in HUMAN_ONLY:
        results[cid] = CheckResult(
            cid, _phase_of(cid), Status.ESCALATED, "reserved to the signatory", {}
        )
    state = resolve(_repo(tmp_path, name), results)
    assert state.state == AWAITING, state.reason
    return state


def _in_progress(tmp_path: Path, name: str) -> RepoState:
    results = _all_passing()
    del results["R5"]
    state = resolve(_repo(tmp_path, name), results)
    assert state.state == IN_PROGRESS, state.reason
    return state


# -- exit code: the pair -------------------------------------------------


def test_all_ready_exits_zero(tmp_path: Path) -> None:
    """Negative half: the one input that is genuinely green exits green."""
    assert exit_code([_ready(tmp_path, "a"), _ready(tmp_path, "b")]) == 0


def test_one_blocked_repo_exits_nonzero(tmp_path: Path) -> None:
    """Positive half: a single BLOCKED repo among passing ones fails the run.

    This is the case that used to exit 0, and it is the case the README says
    CI gates on.
    """
    states = [_ready(tmp_path, "a"), _blocked(tmp_path, "b"), _ready(tmp_path, "c")]
    assert exit_code(states) == 1


def test_hard_stop_exits_one(tmp_path: Path) -> None:
    """A hard stop is BLOCKED and must not be able to exit green by any route."""
    results = _all_passing()
    results["D2"] = CheckResult.failed(
        "D2", "decision", "placebo CI excludes zero", {"halt": True}
    )
    state = resolve(_repo(tmp_path, "b"), results)
    assert state.halted
    assert exit_code([state]) == 1


def test_incomplete_and_awaiting_are_distinguished(tmp_path: Path) -> None:
    """NA/unmeasured (3) is not the same number as awaiting a signature (4).

    Structurally distinct from PASS and from FAIL, and from each other -- the
    whole point of the ladder. If these collapsed to one code, "nobody could
    measure this" and "this is waiting on a person" would read alike in CI.
    """
    assert exit_code([_in_progress(tmp_path, "a")]) == 3
    assert exit_code([_awaiting(tmp_path, "b")]) == 4
    # Worst wins: unmeasured outranks a pending signature, exactly as `resolve`
    # orders them for a single repo.
    assert exit_code([_awaiting(tmp_path, "b"), _in_progress(tmp_path, "a")]) == 3
    assert exit_code([_blocked(tmp_path, "c"), _in_progress(tmp_path, "a")]) == 1


def test_empty_portfolio_is_not_a_pass() -> None:
    """A report over no repos measured nothing; green would be the defect."""
    assert exit_code([]) != 0


def test_unrecognised_state_fails_closed(tmp_path: Path) -> None:
    """A state this module does not know has not been shown to be a pass."""
    state = _ready(tmp_path, "a")
    state.state = "SOMETHING-NEW"
    assert exit_code([state]) == 1


def test_ready_pending_keys_is_nonzero(tmp_path: Path) -> None:
    """Wired and waiting on a credential is materially ready and still not 0.

    A run cannot start without the key, so CI must not read this as green.
    """
    results = _all_passing()
    results["S3"] = CheckResult.deferred(
        "S3", "selection", "AWS_SECRET/copernicus", "wired; awaiting the key"
    )
    state = resolve(_repo(tmp_path, "a"), results)
    assert state.state == READY_PENDING_KEYS, state.reason
    assert exit_code([state]) == 4


# -- header: derived, and counting the phase it labels --------------------


@pytest.mark.parametrize("phase", PHASES)
def test_header_names_as_many_checks_as_the_phase_runs(phase: str) -> None:
    """Every integer the header names, expanded, is exactly the phase's ids.

    This is the assertion the hand-written string could not satisfy: it holds
    the LABEL against ``PHASE_ORDER`` rather than against another string.
    """
    header = phase_header(phase)
    named: set[int] = set()
    for lo, hi in re.findall(r"(\d+)(?:-(\d+))?", header):
        named.update(range(int(lo), int(hi or lo) + 1))
    declared = {int(cid.lstrip("TSRDE")) for cid in PHASE_ORDER[phase]}
    assert named == declared, f"{header} names {sorted(named)}, phase runs {sorted(declared)}"


def test_readiness_header_covers_r12() -> None:
    """The specific regression: R12 joined the phase and the label did not."""
    assert phase_header("readiness") == "R(9-12,1-8)"
    assert len(PHASE_ORDER["readiness"]) == 12


def test_header_preserves_run_order_not_sorted_order() -> None:
    """R9 first is a claim readiness makes; a sorted header would deny it."""
    assert phase_header("readiness").index("9") < phase_header("readiness").index("1-8")


def test_rendered_table_uses_the_derived_headers(tmp_path: Path) -> None:
    out = render_portfolio([_ready(tmp_path, "a")], "TEST-NONCE")
    for phase in PHASES:
        assert phase_header(phase) in out
    assert "R(9,10,11,1-8)" not in out
