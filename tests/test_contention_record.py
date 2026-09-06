"""The contention record and the UNMEASURABLE predicate (E-M40).

The predicate is four conditions and it is stated in
``reports/CONTENTION_PREREGISTRATION.md`` §3, written and committed before the
module existed so it could not be shaped to fit a reading. This file holds each
condition separately, holds the conjunction, and holds the two properties that
make the facility safe to have at all:

* **UNMEASURABLE is never a PASS.** Swept, not inspected.
* **The thresholds cannot be moved in the permissive direction** through the
  public API. Moving them toward strictness is allowed and tested; moving them
  the other way is refused by name, because that is the only edit that could
  turn this facility into the universal excuse it is designed not to be.
"""

from __future__ import annotations

import dataclasses
import time

import pytest

from resilient_mlkit.core.contention import (
    CONTENDED_KEY,
    LOAD_PER_CPU,
    MAX_CPU_RATIO,
    UNCONTENDED_CLOCK,
    ContendedWallClock,
    ContentionRecord,
    WallClockBudget,
    classify,
    result,
)
from resilient_mlkit.core.result import InputUnavailable, Status

#: A 10-CPU host, which is the host every incident in the preregistration was
#: measured on. Records below are built from it by keyword so that each test
#: changes exactly the axis it is about.
CPUS = 10


def record(
    *,
    budget_s: float = 1.0,
    wall_s: float = 2.0,
    self_cpu_s: float = 0.0,
    children_cpu_s: float = 0.0,
    load1: float = 20.0,
    cpu_count: int = CPUS,
    max_cpu_ratio: float = MAX_CPU_RATIO,
    load_per_cpu: float = LOAD_PER_CPU,
) -> ContentionRecord:
    """A record with one axis varied. Defaults are a contended, missed budget."""
    return ContentionRecord(
        what="a child process",
        budget_s=budget_s,
        wall_s=wall_s,
        self_cpu_s=self_cpu_s,
        children_cpu_s=children_cpu_s,
        load1_start=load1,
        load5_start=load1,
        load15_start=load1,
        load1_end=load1,
        load5_end=load1,
        load15_end=load1,
        cpu_count=cpu_count,
        max_cpu_ratio=max_cpu_ratio,
        load_per_cpu=load_per_cpu,
        captured_at="2026-09-06T00:00:00+00:00",
    )


# -- the four conditions, one at a time ------------------------------------


def test_c2_a_met_budget_is_a_pass_however_loaded_the_machine() -> None:
    """Contention never CREATES a verdict; it only withholds one."""
    assert classify(record(wall_s=0.5, load1=200.0)) is Status.PASS


def test_c3_a_missed_budget_while_burning_cpu_is_a_real_fail() -> None:
    """The FIRES case. A regression that works tracks its own wall clock."""
    r = record(wall_s=2.0, self_cpu_s=1.9, load1=200.0)
    assert r.cpu_ratio > MAX_CPU_RATIO
    assert classify(r) is Status.FAIL


def test_c3_counts_the_cpu_of_reaped_children_not_only_this_process() -> None:
    """The mlkit incident is a test that SHELLS OUT; the child's CPU is the signal."""
    r = record(wall_s=2.0, self_cpu_s=0.05, children_cpu_s=1.9, load1=200.0)
    assert r.cpu_s == pytest.approx(1.95)
    assert classify(r) is Status.FAIL


def test_c4_a_missed_budget_on_a_quiet_machine_is_a_real_fail() -> None:
    """A sleeping regression, measured quiet, is a FAIL and not an excuse."""
    r = record(wall_s=2.0, self_cpu_s=0.0, load1=1.0)
    assert r.waiting
    assert not r.loaded
    assert classify(r) is Status.FAIL


def test_all_four_together_are_the_only_route_to_unmeasurable() -> None:
    """Missed, waiting, loaded — and only then."""
    r = record(wall_s=2.0, self_cpu_s=0.05, load1=20.0)
    assert r.over_budget and r.waiting and r.loaded
    assert classify(r) is Status.UNMEASURABLE


def test_the_load_threshold_is_per_cpu_not_absolute() -> None:
    """Load 12 is contended on 10 CPUs and quiet on 64."""
    assert classify(record(load1=12.0, cpu_count=10)) is Status.UNMEASURABLE
    assert classify(record(load1=12.0, cpu_count=64)) is Status.FAIL


def test_the_boundary_is_inclusive_on_both_declared_thresholds() -> None:
    """Exactly at the threshold counts as contended, and exactly at the ratio as waiting.

    Stated by a test rather than left to a reader of ``>=`` vs ``>``: a
    boundary nobody wrote down is a boundary two people will read differently.
    """
    assert classify(record(load1=float(CPUS), self_cpu_s=0.0)) is Status.UNMEASURABLE
    at_ratio = record(wall_s=2.0, self_cpu_s=1.0, load1=20.0)
    assert at_ratio.cpu_ratio == pytest.approx(MAX_CPU_RATIO)
    assert classify(at_ratio) is Status.UNMEASURABLE


# -- A4: UNMEASURABLE is never a PASS, swept rather than asserted by eye ----


def test_a4_no_record_that_missed_its_budget_can_classify_as_pass() -> None:
    """Swept over the whole grid the classifier can see.

    The acceptance rule this holds (preregistration §4 A4) is the one that
    makes the facility safe: whatever the machine was doing, a missed budget
    never renders as a met one.
    """
    seen = set()
    for wall in (1.001, 1.5, 10.0, 1000.0):
        for cpu in (0.0, 0.1, 0.5, 0.999, 1.0, 4.0):
            for load in (0.0, 1.0, 9.99, 10.0, 100.0):
                r = record(budget_s=1.0, wall_s=wall, self_cpu_s=cpu * wall, load1=load)
                status = classify(r)
                assert status is not Status.PASS, r.one_line()
                seen.add(status)
    assert seen == {Status.FAIL, Status.UNMEASURABLE}


def test_a4_an_unmeasurable_result_carries_no_halt_key_and_is_not_a_pass() -> None:
    """The portfolio must read it as unmeasured, never as satisfied."""
    res = result("X9", "phase-1", record(wall_s=2.0, self_cpu_s=0.0, load1=20.0))
    assert res.status is Status.UNMEASURABLE
    assert "halt" not in res.evidence
    assert res.evidence[CONTENDED_KEY] is True
    assert res.evidence["input"] == UNCONTENDED_CLOCK
    assert "NOT A FINDING" in res.reason


def test_a_fail_result_says_WHICH_contention_condition_it_fails() -> None:
    """A FAIL that does not mention the machine invites the next reader to wonder."""
    working = result("X9", "phase-1", record(wall_s=2.0, self_cpu_s=1.9, load1=200.0))
    assert working.status is Status.FAIL
    assert "WORKING, not waiting" in working.reason

    quiet = result("X9", "phase-1", record(wall_s=2.0, self_cpu_s=0.0, load1=1.0))
    assert quiet.status is Status.FAIL
    assert "QUIET" in quiet.reason


def test_a_passing_budget_reports_the_measurement_it_passed_on() -> None:
    res = result("X9", "phase-1", record(wall_s=0.5, load1=200.0))
    assert res.status is Status.PASS
    assert res.evidence["wall_s"] == pytest.approx(0.5)


# -- the thresholds may only move toward strictness -------------------------


@pytest.mark.parametrize(
    "kwargs",
    [
        {"load_per_cpu": 0.0},
        {"load_per_cpu": LOAD_PER_CPU - 0.01},
        {"max_cpu_ratio": 1.0},
        {"max_cpu_ratio": MAX_CPU_RATIO + 0.01},
    ],
)
def test_the_permissive_direction_is_refused_by_name(kwargs: dict[str, float]) -> None:
    """Every mutation that would WIDEN UNMEASURABLE is unconstructible."""
    with pytest.raises(ValueError, match="rule 6"):
        WallClockBudget(seconds=1.0, what="a child", **kwargs)


@pytest.mark.parametrize(
    "kwargs", [{"load_per_cpu": 4.0}, {"max_cpu_ratio": 0.1}, {"max_cpu_ratio": 0.0}]
)
def test_the_strict_direction_is_allowed(kwargs: dict[str, float]) -> None:
    """A repo may demand more evidence before it will call anything unmeasurable."""
    budget = WallClockBudget(seconds=1.0, what="a child", **kwargs)
    for key, value in kwargs.items():
        assert getattr(budget, key) == value


def test_a_budget_must_be_positive_and_must_name_what_it_bounds() -> None:
    with pytest.raises(ValueError, match="must be positive"):
        WallClockBudget(seconds=0.0, what="a child")
    with pytest.raises(ValueError, match="must be positive"):
        WallClockBudget(seconds=-1.0, what="a child")
    with pytest.raises(ValueError, match="must name what it bounds"):
        WallClockBudget(seconds=1.0, what="   ")


def test_every_record_carries_the_thresholds_it_was_judged_against() -> None:
    """So a mutation forced by editing the module is legible in the artifact."""
    r = record(max_cpu_ratio=0.2, load_per_cpu=3.0)
    as_dict = r.to_dict()
    assert as_dict["max_cpu_ratio"] == 0.2
    assert as_dict["load_per_cpu"] == 3.0


# -- the fallback when the platform keeps no load average -------------------


def test_absent_load_average_makes_unmeasurable_unreachable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The fallback fails in the STRICT direction, and that is deliberate.

    A platform with no ``getloadavg`` records zeroes, C4 is false, and every
    missed budget on it stays a FAIL. The alternative fallback — assuming
    contention when the machine will not say — would make the excuse available
    on exactly the hosts that cannot be checked.
    """

    def _no_load() -> tuple[float, float, float]:
        raise OSError("this platform keeps no load average")

    monkeypatch.setattr("resilient_mlkit.core.contention.os.getloadavg", _no_load)
    budget = WallClockBudget(seconds=0.001, what="a slow span")
    with budget.measure() as span:
        time.sleep(0.02)
    assert span.record.load1 == 0.0
    assert classify(span.record) is Status.FAIL


# -- span mechanics ---------------------------------------------------------


def test_peek_does_not_stop_the_clock_and_close_is_idempotent() -> None:
    """A defect found in this module's first draft, kept as a control.

    The pytest surface prints a contention line in the report HEADER. If that
    read had closed the session span, the summary line at the END of the log
    would have reported a session lasting milliseconds — the log would have
    carried a number that looked like a measurement and was not.
    """
    budget = WallClockBudget(seconds=60.0, what="a session")
    span = budget.measure()
    time.sleep(0.05)
    early = span.peek()
    time.sleep(0.05)
    later = span.peek()
    assert later.wall_s > early.wall_s
    first_close = span.close()
    time.sleep(0.05)
    assert span.close() is first_close
    assert span.record is first_close


def test_a_span_that_raised_still_produced_a_record() -> None:
    """A span that raised still measured a machine, and the record is often why."""
    budget = WallClockBudget(seconds=0.001, what="a raising span")
    span = budget.measure()
    with pytest.raises(RuntimeError), span:
        time.sleep(0.01)
        raise RuntimeError("the body failed")
    assert span.record.wall_s > 0.0


def test_the_one_line_names_every_number_the_verdict_rests_on() -> None:
    """This line is the deliverable: it is what dates an arm's log afterwards."""
    line = record(wall_s=2.0, self_cpu_s=0.1, load1=20.0).one_line()
    for fragment in ("wall", "budget", "cpu", "ratio", "load1", "cpu_ratio<=", "load/cpu>="):
        assert fragment in line, line


def test_contended_wall_clock_is_an_input_unavailable() -> None:
    """So the runner, the renderer and CheckResult already know how to show it."""
    exc = ContendedWallClock(record(wall_s=2.0, self_cpu_s=0.0, load1=20.0))
    assert isinstance(exc, InputUnavailable)
    assert exc.input == UNCONTENDED_CLOCK
    assert exc.to_evidence()[CONTENDED_KEY] is True
    assert "re-measure this arm on a quiet machine" in exc.reason


def test_derived_readings_are_arithmetic_a_reader_can_check() -> None:
    r = record(budget_s=2.0, wall_s=8.0, self_cpu_s=1.0, children_cpu_s=1.0, load1=5.0)
    assert r.cpu_s == pytest.approx(2.0)
    assert r.cpu_ratio == pytest.approx(0.25)
    assert r.budget_ratio == pytest.approx(4.0)
    assert r.load_per_cpu_observed == pytest.approx(0.5)


def test_a_record_is_frozen() -> None:
    """Evidence that can be edited after the verdict is evidence of nothing."""
    r = record()
    with pytest.raises(dataclasses.FrozenInstanceError):
        r.wall_s = 0.0  # type: ignore[misc]
