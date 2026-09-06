"""The three control arms, and the committed artifact of driving them (E-M40).

WHY THIS FILE IS NOT SIMPLY "RUN THE DRIVE SCRIPT"
--------------------------------------------------
The three arms of ``reports/CONTENTION_PREREGISTRATION.md`` §5 are driven for
real by ``scripts/contention_control_drive.py`` — including a SILENT arm that
deliberately raises the host's load average with its own children. That drive
belongs in a script and its output belongs in a committed artifact, because
raising a machine's load average is exactly the thing this package tells the
fleet not to do while somebody else is measuring.

What lives HERE is the half that must run on every machine, in every CI job,
without making the box busy — and it is arranged so that no assertion in this
file can flake on a loaded runner. The technique is stated rather than hidden:

* the SUBJECT is real. Real CPU is burned; a real span waits. CPU seconds and
  wall seconds are measured, never supplied.
* the MACHINE is varied by substituting the load reading on the measured
  record. That is the only way to ask "and what would this same span have
  classified as on a quiet machine?" inside a suite that does not control the
  machine it runs on. Every substitution below says which fields it replaced.

The substitution is safe in the direction that matters because the load axis is
the one axis that cannot be forged in the dangerous direction by accident: a
substituted QUIET reading can only make the classifier stricter.

There is also one assertion that holds on any machine with nothing substituted,
and it is the facility's own central claim:

    a span that burned CPU is either classified as WORKING — or the machine was
    demonstrably loaded, and the record says so.
"""

from __future__ import annotations

import dataclasses
import json
import time
from pathlib import Path

from resilient_mlkit.core.contention import (
    LOAD_PER_CPU,
    MAX_CPU_RATIO,
    ContentionRecord,
    WallClockBudget,
    classify,
)
from resilient_mlkit.core.result import Status

ROOT = Path(__file__).resolve().parent.parent
ARTIFACT = ROOT / "reports" / "CONTENTION_CONTROL_ARMS.json"

#: CPU seconds the FIRES subject burns. Large enough that its own CPU time is
#: unambiguous against timer resolution, small enough that this file is not
#: itself a slow test.
FIRES_CPU_TARGET_S = 0.5

#: The budget both arms are held to. Deliberately far below what either span
#: takes, so that C2 (the budget was missed) is never the question here — the
#: question is only ever what the machine was doing.
CONTROL_BUDGET_S = 0.01


def _quiet(record: ContentionRecord) -> ContentionRecord:
    """The same measured span, judged against a machine at load zero."""
    return dataclasses.replace(
        record, load1_start=0.0, load1_end=0.0, load5_end=0.0, load15_end=0.0
    )


def _loaded(record: ContentionRecord) -> ContentionRecord:
    """The same measured span, judged against a machine at 2 runnable per CPU."""
    busy = 2.0 * LOAD_PER_CPU * record.cpu_count
    return dataclasses.replace(record, load1_start=busy, load1_end=busy)


def _burn(seconds: float) -> ContentionRecord:
    """A REAL O(n²)-shaped slowdown: burn CPU until the CPU clock says so.

    Bounded by CPU time rather than wall time on purpose. On a loaded machine a
    wall-bounded loop burns less CPU and the subject would quietly become a
    different subject; a CPU-bounded loop burns the same work whatever else the
    host is doing, which is what makes this control mean the same thing on a
    quiet runner and a busy one.
    """
    budget = WallClockBudget(seconds=CONTROL_BUDGET_S, what="a regressed O(n^2)")
    with budget.measure() as span:
        start = time.process_time()
        total = 0
        while time.process_time() - start < seconds:
            for j in range(10_000):
                total += j
    assert total > 0
    return span.record


def _wait(seconds: float) -> ContentionRecord:
    """Unchanged code whose span WAITS: no CPU burned, wall time spent."""
    budget = WallClockBudget(seconds=CONTROL_BUDGET_S, what="an unchanged child")
    with budget.measure() as span:
        time.sleep(seconds)
    return span.record


# -- ARM 1: FIRES -----------------------------------------------------------


def test_fires_a_real_cpu_burning_slowdown_classifies_as_fail_not_unmeasurable() -> None:
    """A1. The regression burns CPU, so CPU time tracks wall time and it FAILS.

    Load reading substituted with a quiet machine's; CPU and wall are measured.
    """
    burned = _burn(FIRES_CPU_TARGET_S)
    assert burned.cpu_s >= FIRES_CPU_TARGET_S * 0.8, burned.one_line()
    assert burned.over_budget, burned.one_line()
    assert classify(_quiet(burned)) is Status.FAIL, burned.one_line()


def test_fires_stays_a_fail_even_on_a_machine_at_twice_one_process_per_cpu() -> None:
    """The load half of the predicate cannot rescue a process that was working.

    This is the assertion that keeps the facility from becoming an excuse: a
    real regression is still a FAIL on a demonstrably contended host, because
    C3 fails independently of C4.

    Written as a branch rather than a skip so that it asserts something on
    every machine. If this host took more than half of the span's wall time
    away, the span genuinely was waiting and the record must say the host was
    loaded — which is the other half of the same claim, not an exemption from
    it.
    """
    burned = _burn(FIRES_CPU_TARGET_S)
    loaded = _loaded(burned)
    assert loaded.loaded
    if burned.cpu_ratio > MAX_CPU_RATIO:
        assert classify(loaded) is Status.FAIL, loaded.one_line()
    else:
        assert burned.loaded, burned.one_line()


def test_a_span_that_burned_cpu_is_working_unless_the_machine_says_otherwise() -> None:
    """The one assertion here with NOTHING substituted, on any machine.

    Either the CPU-bound span classifies as working, or the record itself
    testifies that this host was loaded past the declared threshold. There is no
    third outcome, and if this ever fails the facility's central claim is wrong.
    """
    burned = _burn(FIRES_CPU_TARGET_S)
    assert (not burned.waiting) or burned.loaded, burned.one_line()


# -- ARM 2: SILENT-AS-UNMEASURABLE ------------------------------------------


def test_silent_the_same_waiting_span_is_unmeasurable_loaded_and_fail_quiet() -> None:
    """A2, and the pair is the whole design in four lines.

    ONE measured span — unchanged code that waits — judged against two
    machines. Loaded: UNMEASURABLE, with the record. Quiet: FAIL. The verdict
    moves with the machine and the code never moved, which is precisely the
    defect this facility exists to stop being reported as a fact about a tree.
    """
    waited = _wait(0.05)
    assert waited.over_budget and waited.waiting, waited.one_line()
    assert classify(_loaded(waited)) is Status.UNMEASURABLE, waited.one_line()
    assert classify(_quiet(waited)) is Status.FAIL, waited.one_line()


def test_silent_never_reaches_unmeasurable_when_the_budget_was_MET() -> None:
    """However loaded the machine, a met budget is a PASS and not an excuse."""
    budget = WallClockBudget(seconds=3600.0, what="a fast unchanged child")
    with budget.measure() as span:
        time.sleep(0.01)
    assert classify(_loaded(span.record)) is Status.PASS


# -- ARM 3: CHECK-NOT-DEAD --------------------------------------------------


def test_not_dead_n1_with_the_facility_removed_the_fires_arm_still_fires() -> None:
    """The bare assertion every one of today's four incidents actually made."""
    burned = _burn(FIRES_CPU_TARGET_S)
    assert burned.wall_s > burned.budget_s


def test_not_dead_n2_destroying_the_load_condition_does_not_save_the_regression() -> None:
    """C4 mutated to its most permissive value: every machine counts as loaded."""
    burned = _burn(FIRES_CPU_TARGET_S)
    mutated = dataclasses.replace(_quiet(burned), load_per_cpu=0.0)
    assert mutated.loaded, "the mutation did not take effect; the arm proves nothing"
    assert classify(mutated) is Status.FAIL, mutated.one_line()


def test_not_dead_n3_destroying_the_cpu_condition_does_not_save_it_on_a_quiet_host() -> None:
    """C3 mutated to its most permissive value, and the regression still FAILS.

    Two things hold it, and the first was found by driving the arm rather than
    by reasoning about it: a span that saturates a core records ``cpu_ratio``
    slightly ABOVE 1.0 (``os.times`` resolution against ``time.monotonic``), so
    even ``max_cpu_ratio = 1.0`` — the largest value the type permits — often
    cannot make it count as waiting at all. And on a quiet host C4 fails
    anyway. Either way the verdict is FAIL.
    """
    burned = _burn(FIRES_CPU_TARGET_S)
    mutated = dataclasses.replace(_quiet(burned), max_cpu_ratio=1.0)
    assert classify(mutated) is Status.FAIL, mutated.one_line()
    assert (not mutated.waiting) or (not mutated.loaded), mutated.one_line()


def test_not_dead_n4_destroying_BOTH_conditions_does_kill_it_and_that_is_recorded() -> None:
    """The honest half of the control, pinned so nobody has to rediscover it.

    With C3 and C4 both mutated to their most permissive values the classifier
    stops consulting the machine at all, and whether a genuine regression still
    reads FAIL comes down to whether its CPU ratio happens to clear 1.0. Driven
    on 2026-09-06 this cut both ways: the in-process burn below saturates a
    core and survives (ratio > 1.0), while the drive script's SUBPROCESS
    subject -- the shape of the real incident, where the parent waits through
    interpreter start-up -- reads 0.98 and flips to UNMEASURABLE.
    ``reports/CONTENTION_CONTROL_ARMS.json`` carries that second reading.

    That is what a dead check looks like, and it is why:

    * ``WallClockBudget`` REFUSES both mutations by name (tested in
      ``test_contention_record.py``), so neither is reachable from an adopting
      repo's call site;
    * every record carries the thresholds it was judged against, so a fork that
      edited ``core/contention.py`` to force them is legible in the artifact
      rather than only in a diff nobody re-reads.
    """
    burned = _burn(FIRES_CPU_TARGET_S)
    dead = dataclasses.replace(_quiet(burned), max_cpu_ratio=1.0, load_per_cpu=0.0)
    # C4 is gone: every machine, including one at load zero, now counts loaded.
    assert dead.loaded
    # So the verdict no longer depends on the machine AT ALL. It depends only
    # on whether the span's CPU ratio clears 1.0 -- which is a coin this
    # facility was never meant to be decided by.
    assert (classify(dead) is Status.UNMEASURABLE) == (dead.cpu_ratio <= 1.0)
    assert dead.to_dict()["max_cpu_ratio"] == 1.0
    assert dead.to_dict()["load_per_cpu"] == 0.0


# -- the committed artifact -------------------------------------------------


def test_the_committed_control_artifact_exists_and_every_required_arm_agrees() -> None:
    """The drive's own output, read back, so it cannot drift from the code."""
    assert ARTIFACT.is_file(), (
        f"{ARTIFACT.relative_to(ROOT)} is missing. The three arms are driven by "
        "scripts/contention_control_drive.py and their output is committed; "
        "without it the preregistration's §5 is a promise rather than a record."
    )
    driven = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    assert driven["all_required_arms_agree"] is True, driven["disagreements"]
    by_name = {row["arm"]: row for row in driven["arms"]}
    assert by_name["FIRES"]["classified"] == Status.FAIL.value
    assert by_name["SILENT"]["classified"] == Status.UNMEASURABLE.value


def test_the_committed_artifact_was_driven_at_the_thresholds_this_code_declares() -> None:
    """An artifact driven under mutated thresholds may not sit in this repo.

    Without this, the arms above could all agree in a file produced by a tree
    whose constants had been widened — a green record of a check that was not
    the check.
    """
    driven = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    assert driven["thresholds"] == {
        "MAX_CPU_RATIO": MAX_CPU_RATIO,
        "LOAD_PER_CPU": LOAD_PER_CPU,
    }
    for row in driven["arms"]:
        record = row.get("record") or {}
        if not record or "NOT-DEAD" in row["arm"]:
            continue
        assert record["max_cpu_ratio"] == MAX_CPU_RATIO, row["arm"]
        assert record["load_per_cpu"] == LOAD_PER_CPU, row["arm"]


def test_the_committed_artifact_records_the_api_refusing_both_mutations() -> None:
    """The drive attempts them through the public API; both must be refused."""
    driven = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    refusals = driven["threshold_mutation_refused_by_api"]
    assert len(refusals) == 2
    assert all(row["refused"] for row in refusals), refusals


def test_the_committed_artifact_names_the_load_it_reached_and_the_pids_it_killed() -> None:
    """The SILENT arm made the machine busy; it must say when, and clean up.

    On 2026-09-06 one lane killed another lane's suite leg with a name-pattern
    kill. This drive kills only PIDs it recorded, and the artifact carries both
    the list and the window, so any other arm overlapping it is datable — which
    is the facility applied to itself.
    """
    driven = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    load = driven["synthetic_load"]
    assert load["load1_reached"] >= LOAD_PER_CPU * driven["cpu_count"], load
    assert load["pids"], load
    assert load["window_start_utc"] and load["window_end_utc"]
