"""Controls for the terminal-state resolver — the function that grants promotion.

Every check in this package exists to feed one decision: `portfolio.resolve`,
which turns a bag of results into READY-TO-TRAIN, READY-PENDING-KEYS,
AWAITING-SIGNOFF, IN-PROGRESS or BLOCKED. A check that fires correctly into a
resolver that then reads the wrong word off it has caught nothing, so this is
the last place a bad result can still become a promotion, and it had no tests.

The pairs here are about precedence, because precedence is where a resolver
goes wrong quietly. Two orderings carry the weight, and both are easy to get
backwards:

* **unmeasured outranks a pending signature.** Six checks are reserved to the
  signatory and ALWAYS report ESCALATED. If escalation won, every repo would
  read AWAITING-SIGNOFF — "done, just needs a countersignature" — the moment it
  had run its phases, however little was actually measured. The pair is an NA
  beside an ESCALATED (IN-PROGRESS) against an ESCALATED alone (AWAITING).

* **a measured failure blocks wherever it is found, but only the gating set
  decides readiness.** Triage diagnoses and is deliberately outside the gating
  set; a triage FAIL still blocks. The pair is a triage FAIL (BLOCKED) against a
  triage NA (which must NOT hold a repo back), and without both, "triage is not
  a gate" and "triage is ignored" are the same code.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from resilient_mlkit.checks import PHASE_ORDER
from resilient_mlkit.core.repo import Repo
from resilient_mlkit.core.result import CheckResult
from resilient_mlkit.portfolio import (
    AWAITING,
    BLOCKED,
    IN_PROGRESS,
    READY,
    READY_PENDING_KEYS,
    gating_ids,
    resolve,
)

#: The six checks reserved to the human signatory (CLAUDE.md rule 12). They
#: always report ESCALATED, which is why escalation must not outrank NA.
HUMAN_ONLY = ("S5", "D1", "D4", "D5", "E4", "E5")


@pytest.fixture
def repo(tmp_path: Path) -> Repo:
    return Repo(name="fixturerepo", path=tmp_path)


def _phase_of(check_id: str) -> str:
    return next(p for p, ids in PHASE_ORDER.items() if check_id in ids)


def _all_passing() -> dict[str, CheckResult]:
    """A result for every gating check, all PASS. The only route to READY."""
    return {
        cid: CheckResult.passed(cid, _phase_of(cid), {"measured": True})
        for cid in gating_ids()
    }


# -- the shape of the gating set ------------------------------------------


def test_the_gating_set_is_the_four_non_triage_phases() -> None:
    """Pinned because widening or narrowing it silently redefines READY.

    The literal moved from 26 to 27 when R12 (``SERVED_CONTRACT``) joined the
    readiness phase. That is what this tripwire is for: adding a gating check
    redefines READY for every repo, and it should not be possible to do it
    without editing this line and saying so. R12 is a gating check on purpose —
    a repo whose serving path defines "promotable" for itself is not ready to
    train against a bar it can reinterpret.

    This is the ONLY place the number is written. The READY message below reads
    it back from ``gating_ids()`` rather than repeating it, because two copies
    of a count is how the version literal went stale in E-M08.
    """
    ids = gating_ids()
    assert len(ids) == 27
    assert set(PHASE_ORDER["triage"]).isdisjoint(ids), "triage diagnoses; it does not gate"
    for cid in HUMAN_ONLY:
        assert cid in ids, f"{cid} is reserved to the signatory and must still gate"


# -- READY: FIRES / SILENT -------------------------------------------------


def test_negative_control_every_gating_check_passing_is_READY(repo: Repo) -> None:
    """SILENT: the one input that may produce READY. Without it nothing below means anything."""
    state = resolve(repo, _all_passing())
    assert state.state == READY
    assert f"all {len(gating_ids())} gating checks pass" in state.reason


def test_positive_control_one_missing_gating_result_is_not_READY(repo: Repo) -> None:
    """FIRES: a check that never ran is unmeasured, not clean."""
    results = _all_passing()
    del results["R5"]
    state = resolve(repo, results)
    assert state.state == IN_PROGRESS
    assert "R5" in state.reason


def test_positive_control_one_NA_in_the_gating_set_is_not_READY(repo: Repo) -> None:
    """FIRES: 'could not be measured here' can never be counted as a pass."""
    results = _all_passing()
    results["R5"] = CheckResult.na("R5", "readiness", "no provenance binding declared")
    state = resolve(repo, results)
    assert state.state == IN_PROGRESS
    assert "first unmeasurable: R5" in state.reason


# -- precedence: unmeasured outranks a pending signature -------------------


def test_positive_control_an_NA_beside_an_ESCALATED_is_IN_PROGRESS(repo: Repo) -> None:
    """FIRES: the precedence that is easy to get backwards, and expensive when it is.

    If escalation won here the repo would read AWAITING-SIGNOFF — a state that
    says the engineering is finished — while one of its gating checks had
    measured nothing at all.
    """
    results = _all_passing()
    results["R3"] = CheckResult.na("R3", "readiness", "no splits binding declared")
    for cid in HUMAN_ONLY:
        results[cid] = CheckResult.escalated(cid, _phase_of(cid), "reserved to the signatory")
    state = resolve(repo, results)
    assert state.state == IN_PROGRESS
    assert "also await sign-off" in state.reason


def test_negative_control_ESCALATED_alone_is_AWAITING_SIGNOFF(repo: Repo) -> None:
    """SILENT: nothing unmeasured, so a pending signature is the whole story.

    The pair for the test above. Without it, "unmeasured outranks escalation"
    would be satisfied by a resolver that never returns AWAITING at all.
    """
    results = _all_passing()
    for cid in HUMAN_ONLY:
        results[cid] = CheckResult.escalated(cid, _phase_of(cid), "reserved to the signatory")
    state = resolve(repo, results)
    assert state.state == AWAITING
    for cid in HUMAN_ONLY:
        assert cid in state.reason


def test_negative_control_DEFERRED_alone_is_READY_PENDING_KEYS(repo: Repo) -> None:
    """SILENT: wired end to end and stopped at a key. Not READY, and not unmeasured."""
    results = _all_passing()
    results["R7"] = CheckResult.deferred(
        "R7", "readiness", "CDSAPI_KEY", "request built; key consumed at the boundary",
        {"exercised": "request built"},
    )
    state = resolve(repo, results)
    assert state.state == READY_PENDING_KEYS
    assert "CDSAPI_KEY" in state.reason


def test_positive_control_DEFERRED_beside_an_NA_is_still_IN_PROGRESS(repo: Repo) -> None:
    """FIRES: a key pending does not excuse a check that measured nothing."""
    results = _all_passing()
    results["R7"] = CheckResult.deferred(
        "R7", "readiness", "CDSAPI_KEY", "request built", {"exercised": "request built"}
    )
    results["R3"] = CheckResult.na("R3", "readiness", "no splits binding declared")
    state = resolve(repo, results)
    assert state.state == IN_PROGRESS
    assert "wired awaiting keys" in state.reason


# -- a measured failure blocks wherever it is found ------------------------


def test_positive_control_one_FAIL_in_the_gating_set_is_BLOCKED(repo: Repo) -> None:
    """FIRES: and the reason must carry the failing check's own words."""
    results = _all_passing()
    results["R5"] = CheckResult.failed(
        "R5", "readiness", "non-real rows present in evaluation splits (val: synthetic=1)"
    )
    state = resolve(repo, results)
    assert state.state == BLOCKED
    assert state.reason.startswith("R5 failed:")
    assert "synthetic=1" in state.reason


def test_positive_control_a_triage_FAIL_blocks_even_though_triage_does_not_gate(
    repo: Repo,
) -> None:
    """FIRES: outside the gating set is not outside the truth.

    Every gating check passes here. The only failure is in triage, which is not
    part of the "everything passes" test — and the repo is still BLOCKED,
    because a measured failure is a measured failure.
    """
    results = _all_passing()
    results["T2"] = CheckResult.failed("T2", "triage", "one-batch overfit did not converge")
    state = resolve(repo, results)
    assert state.state == BLOCKED
    assert "T2 failed" in state.reason


def test_negative_control_a_triage_NA_does_not_hold_a_repo_back(repo: Repo) -> None:
    """SILENT: the pair that keeps triage diagnostic rather than ignored.

    Without this control, "a triage FAIL blocks" and "triage is scanned for
    everything" are the same implementation, and a repo would sit at IN-PROGRESS
    forever over a diagnostic that was never meant to gate.
    """
    results = _all_passing()
    results["T4"] = CheckResult.na("T4", "triage", "no GPU on this host")
    state = resolve(repo, results)
    assert state.state == READY


def test_a_second_failure_is_counted_not_hidden(repo: Repo) -> None:
    """The reason names one check and says how many more there are."""
    results = _all_passing()
    results["R3"] = CheckResult.failed("R3", "readiness", "groups appear in more than one split")
    results["R5"] = CheckResult.failed("R5", "readiness", "non-real rows in val")
    state = resolve(repo, results)
    assert state.state == BLOCKED
    assert "R3 failed" in state.reason and "+1 more" in state.reason


# -- hard stops outrank everything ----------------------------------------


def test_positive_control_a_halt_outranks_a_full_set_of_passes(repo: Repo) -> None:
    """FIRES: D2 and E1 hard stops are not fixable by tuning the thing that failed.

    The halt is carried in evidence rather than in the status, so a check can
    halt the repo while reporting its own measured verdict. This must beat every
    other branch, including an otherwise complete set of passes.
    """
    results = _all_passing()
    results["D2"] = CheckResult.passed(
        "D2", "decision",
        {"halt": True, "placebo_ci": [0.4, 0.9]},
        "placebo estimate's CI excludes zero",
    )
    state = resolve(repo, results)
    assert state.state == BLOCKED
    assert state.reason.startswith("D2 hard stop:")
    assert state.halted is True


def test_negative_control_no_halt_flag_leaves_the_verdict_alone(repo: Repo) -> None:
    """SILENT: evidence that merely mentions a placebo is not a hard stop."""
    results = _all_passing()
    results["D2"] = CheckResult.passed("D2", "decision", {"placebo_ci": [-0.2, 0.3]})
    state = resolve(repo, results)
    assert state.state == READY
    assert state.halted is False


def test_positive_control_a_halt_outranks_a_FAIL_and_names_the_hard_stop(repo: Repo) -> None:
    """FIRES: a hard stop and a failure together must report the hard stop.

    They are not the same instruction. A FAIL says fix it; a hard stop says the
    planned run cannot buy what it was meant to buy, and no amount of fixing the
    failing check changes that.
    """
    results = _all_passing()
    results["R5"] = CheckResult.failed("R5", "readiness", "non-real rows in val")
    results["E1"] = CheckResult.passed(
        "E1", "economics", {"halt": True}, "scaling curve flat between 10% and 25%"
    )
    state = resolve(repo, results)
    assert state.state == BLOCKED
    assert "hard stop" in state.reason
