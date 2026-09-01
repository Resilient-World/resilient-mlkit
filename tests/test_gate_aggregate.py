"""M-03 — the gate verdict nobody can assign (HOLE 2c, mlkit side).

WHAT THIS REPLACES, MEASURED IN THE ADOPTER
-------------------------------------------
``resilient-fray/src/registry/promotion_gate.py`` hand-rolled the type mlkit
did not have: a mutable ``GateResult`` at ``:401``, initialised
``GateResult(passed=True)`` at ``:851``, narrowed check by check with ``&=``.
Three properties of that shape, each on its own enough to make the verdict
untrustworthy:

* it starts at TRUE and is argued down, so a loop that does not run, an
  exception swallowed before the first ``&=``, or a check silently skipped all
  leave a PASS standing;
* ``passed`` is a stored field and can simply be assigned;
* ``&=`` collapses three statuses into two, and NA has to become one of them.

The absence of this type in mlkit is why fray had to write one — rule 7's
failure mode ("eight local copies of a gate is eight different definitions of
ready, which is the same as none") arriving one layer up. This file is the
control set for the replacement; the fray-side adoption is M-07, not here.

At 8517341, ``hasattr(resilient_mlkit.core.result, "GateAggregate")`` was
False.
"""

from __future__ import annotations

import dataclasses
import json

import pytest

import resilient_mlkit.core.result as result_module
from resilient_mlkit.core.result import (
    CheckResult,
    GateAggregate,
    GateAggregateError,
    Status,
)

RESULT_MODULE_FILE = result_module.__file__


def test_the_suite_is_driving_this_tree_s_core_result():
    assert RESULT_MODULE_FILE.endswith("resilient_mlkit/core/result.py")
    assert "site-packages" not in RESULT_MODULE_FILE


def ok(check_id: str) -> CheckResult:
    return CheckResult.passed(check_id, "phase-1", {"n": 1})


def bad(check_id: str) -> CheckResult:
    return CheckResult.failed(check_id, "phase-1", "it lost")


def na(check_id: str) -> CheckResult:
    return CheckResult.na(check_id, "phase-1", "no data pulled")


# ---------------------------------------------------------------------------
# CONTROL A — the states the type exists to refuse
# ---------------------------------------------------------------------------
def test_control_a_a_gate_over_zero_checks_is_refused_not_passed():
    """`all([])` is True. A gate that ran nothing would pass everything."""
    with pytest.raises(GateAggregateError, match="aggregates no check"):
        GateAggregate(gate="promotion", results=())


def test_control_a_the_verdict_cannot_be_assigned():
    """`passed` is a property over the results; there is no field to set."""
    agg = GateAggregate(gate="promotion", results=(ok("R1"), bad("R2")))
    assert agg.passed is False
    with pytest.raises(dataclasses.FrozenInstanceError):
        agg.passed = True  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        agg.results = (ok("R1"),)  # type: ignore[misc]
    assert agg.passed is False


def test_control_a_one_fail_decides_the_gate_and_nothing_can_override_it():
    agg = GateAggregate(
        gate="promotion", results=(ok("R1"), ok("R2"), bad("R3"), ok("R4"))
    )
    assert agg.passed is False
    assert agg.blocking == ("R3",)
    # The results tuple is immutable, so there is no `&=`-style accumulator to
    # skip and no element to swap for a passing one.
    with pytest.raises(TypeError):
        agg.results[2] = ok("R3")  # type: ignore[index]
    assert agg.passed is False


def test_control_a_an_na_is_not_a_pass():
    """The readiness semantics this package documents on Status, enforced.

    `not any(FAIL)` would make this True. `all(PASS)` makes it False, which is
    the honest answer: nobody measured R2.
    """
    agg = GateAggregate(gate="promotion", results=(ok("R1"), na("R2")))
    assert agg.passed is False
    assert agg.blocking == ("R2",)


@pytest.mark.parametrize(
    "status",
    [Status.NA, Status.DEFERRED, Status.STALE, Status.ESCALATED],
)
def test_control_a_no_non_pass_status_is_a_pass(status):
    r = CheckResult("R2", "phase-1", status, "a reason", {"n": 1})
    agg = GateAggregate(gate="promotion", results=(ok("R1"), r))
    assert agg.passed is False


def test_control_a_the_same_check_twice_is_refused():
    """Two answers to one question, and iteration order would pick the winner."""
    with pytest.raises(GateAggregateError, match="more than once"):
        GateAggregate(gate="promotion", results=(ok("R1"), bad("R1")))


def test_control_a_a_bare_bool_cannot_be_posted_in_as_a_check():
    """A verdict formed elsewhere is not a check this gate ran."""
    with pytest.raises(GateAggregateError, match="bool"):
        GateAggregate(gate="promotion", results=(ok("R1"), True))  # type: ignore[arg-type]


def test_control_a_an_unnamed_gate_is_refused():
    with pytest.raises(GateAggregateError, match="must name the gate"):
        GateAggregate(gate="  ", results=(ok("R1"),))


# ---------------------------------------------------------------------------
# CONTROL B — the honest verdicts, unchanged
# ---------------------------------------------------------------------------
def test_control_b_all_pass_is_a_pass():
    agg = GateAggregate(gate="promotion", results=(ok("R1"), ok("R2"), ok("R3")))
    assert agg.passed is True
    assert agg.blocking == ()
    assert agg.counts == {"PASS": 3}


def test_control_b_a_single_passing_check_is_a_legitimate_gate():
    """The refusal is about ZERO checks, not about small gates."""
    assert GateAggregate(gate="promotion", results=(ok("R1"),)).passed is True


def test_control_b_the_verdict_is_recomputed_not_remembered():
    """Two reads of `passed` cannot disagree, and neither is cached from a field."""
    agg = GateAggregate(gate="promotion", results=(ok("R1"), na("R2")))
    assert agg.passed is agg.passed is False
    assert "passed" not in {f.name for f in dataclasses.fields(agg)}


def test_control_b_it_reports_who_blocked_and_in_what_state():
    agg = GateAggregate(
        gate="promotion", results=(ok("R1"), na("R2"), bad("R3"))
    )
    assert agg.statuses == {
        "R1": Status.PASS, "R2": Status.NA, "R3": Status.FAIL
    }
    assert agg.counts == {"PASS": 1, "NA": 1, "FAIL": 1}
    assert agg.result("R2").status is Status.NA
    assert agg.result("R9") is None


def test_control_b_it_serialises_and_the_verdict_survives_json():
    agg = GateAggregate(gate="promotion", results=(ok("R1"), bad("R2")))
    payload = agg.to_dict()
    assert payload["gate"] == "promotion"
    assert payload["passed"] is False
    assert payload["n_checks"] == 2
    assert payload["blocking"] == ["R2"]
    assert json.loads(json.dumps(payload)) == payload


def test_control_b_it_accepts_any_iterable_of_results_and_freezes_it():
    """A caller's list is copied into a tuple, so their later edits do not land."""
    rows = [ok("R1"), ok("R2")]
    agg = GateAggregate(gate="promotion", results=rows)
    rows.append(bad("R3"))
    assert agg.passed is True
    assert len(agg.results) == 2


def test_control_b_the_aggregated_results_are_themselves_still_sealed():
    """M-02's seal travels: you cannot edit a member to change the verdict."""
    from resilient_mlkit.core.result import VerdictSealed

    agg = GateAggregate(gate="promotion", results=(ok("R1"), bad("R2")))
    with pytest.raises(VerdictSealed):
        agg.results[1].status = Status.PASS
    assert agg.passed is False
