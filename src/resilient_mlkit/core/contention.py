"""Was the machine busy while this wall-clock budget was measured?

WHY THIS EXISTS
---------------
``core/environment.py`` separates "this environment cannot measure this repo"
from "this repo failed", because rendering them identically overwrites the
second with the first. This module is the same separation on the time axis,
and it was written the day four measurements were lost to the missing half.

All four were measured on 2026-09-06, on one 10-CPU host:

* **mlkit, this repo.** ``tests/test_pytest_timeout_active.py::
  test_positive_control_a_sleeping_test_fails_on_timeout`` gives a child pytest
  10 s of WALL time. Against three concurrent suites the arm took 1196.12 s
  where a quiet arm takes 635.75 s, and that test read rc 1 -- a result that
  would have blocked landing PR #54. The same tree, the same runner, quiet:
  1307 passed, rc 0, 101.02 s. What dated the cause to the host rather than to
  the tree was the same file's NEGATIVE control failing in a neighbouring arm:
  a fast test cannot be made slow by a source change.
* **resilient-choco.** The SAME TREE run TWICE produced failure sets five names
  apart, every one a ``pytest-timeout`` at the 120/180 s boundary.
* **resilient-torrent.** A 79-minute "stall" and a "hung" readiness
  regeneration both vanished at low load; the suite runs in 13.6 minutes quiet.
* **resilient-arabica.** A three-stream parallel plan produced a phantom
  failure in a test that shells out with a 120 s budget and takes 36 s alone.

The fact the instrument was missing:

    A wall-clock budget missed on a busy machine is not a fact about the tree.
    It is not a PASS and it is not a FAIL. It is a measurement that did not
    happen, and the only honest verdict is the one this portfolio already has
    a word for.

WHAT MAKES THIS SAFE TO HAVE AT ALL
-----------------------------------
The danger of a facility like this is obvious and it is the whole design
problem: an excuse that any red result can reach is worse than no excuse,
because it converts every real regression into a shrug. Four things hold it
narrow, and they are stated in ``reports/CONTENTION_PREREGISTRATION.md``
before the code that implements them was written:

**C1 — the assertion must BE a wall-clock budget, structurally.**
``Status.UNMEASURABLE`` is reachable from here only through
:class:`WallClockBudget`, which cannot be built without a positive budget
declared BEFORE the span runs. There is no flag, no keyword and no subclass
that routes a correctness assertion through this module. An assertion about a
number a model produced cannot reach it at all.

**C2 — the budget must actually have been missed.** A met budget is PASS, on a
quiet machine and on a melting one alike. Contention never creates a verdict,
it only withholds one.

**C3 — the process must have been WAITING, not WORKING.**
``cpu_ratio = (self + reaped children CPU) / wall <= MAX_CPU_RATIO``. A
regression that burns CPU tracks its own wall clock and fails here, which is
what makes arm A1 of the preregistration (a real ``O(n²)`` on a quiet machine)
come out FAIL rather than UNMEASURABLE.

**C4 — the machine must have been demonstrably loaded.**
``max(load1_start, load1_end) >= LOAD_PER_CPU * cpu_count``. One runnable
process per CPU is the point at which a runnable process starts waiting for
one.

Everything else that misses its budget is a real FAIL.

WHAT THIS DOES NOT CLAIM
------------------------
Declared in the preregistration before measuring, and repeated here because a
residual that lives only in a report is a residual nobody reads:

1. **A sleeping regression on a loaded machine is not distinguishable by this
   record.** A newly introduced ``time.sleep(30)`` and a 30 s wait for a busy
   CPU produce the same evidence: no CPU burned, high load. That reads
   UNMEASURABLE -- which is NOT a pass -- and the protocol
   (``docs/CONTENDED_MEASUREMENT.md``) obliges re-measurement on a quiet
   machine, where C4 fails and the same code reads FAIL. This is the declared
   price of the load axis.
2. **No model of how much slowdown a given load explains.** A 1000× overrun at
   1.1 × cpu_count satisfies C1-C4. Inventing a "load explains N×" curve would
   be a fabricated expected range (CLAUDE.md rule 2), so none is invented; the
   record carries ``budget_ratio`` and ``load_per_cpu_observed`` side by side
   so a reader can see the pair and judge.
3. **``os.getloadavg()`` decays over the preceding minute**, so a short span is
   judged partly on load that preceded it. Both endpoints are recorded and the
   classifier takes the MAX -- the direction that declares UNMEASURABLE more
   readily, and therefore the direction the controls police.
4. **``os.times()`` counts only REAPED children.** A subprocess still running
   when the span closes contributes no CPU and biases ``cpu_ratio`` down,
   toward UNMEASURABLE. Close the span after ``subprocess.run`` returns.
5. **Two instants, not a time series.** A span quiet in the middle and
   contended at both ends records as contended.

The two thresholds are constants below, and every record carries the values it
was judged against. Lowering either in an adopting repo to turn a FAIL into an
UNMEASURABLE is a CLAUDE.md rule-6 edit, and the artifact shows it.
"""

from __future__ import annotations

import datetime as _dt
import os
import time
from dataclasses import dataclass
from types import TracebackType
from typing import Any, Self

from .result import CheckResult, InputUnavailable, Status

#: C3's threshold. A span whose CPU time (its own plus its reaped children's)
#: is at most this fraction of its wall time spent more time off-CPU than on
#: it. Above it, the code was WORKING, and a slow worker is a regression
#: whatever else was running on the box.
#:
#: 0.5 is declared in reports/CONTENTION_PREREGISTRATION.md §3 before this
#: module existed, so that it could not be chosen to fit a control arm's
#: reading. It is not a knob: see the module docstring's last paragraph.
MAX_CPU_RATIO = 0.5

#: C4's threshold, in runnable processes per CPU. At 1.0 there is one runnable
#: process for every core, which is where a runnable process begins to wait for
#: one. Declared with MAX_CPU_RATIO, before this module existed.
LOAD_PER_CPU = 1.0

#: Evidence key marking a record produced by this module. Present on every
#: UNMEASURABLE built here, so a reader scanning evidence can tell a contended
#: clock from an absent panel without reading the reason string.
CONTENDED_KEY = "contended_wall_clock"

#: The declared input a contended budget could not read. It is a real input in
#: the ``InputUnavailable`` sense: the check is armed, its declaration
#: resolved, and the byte it cannot get is a clock that nobody else is using.
UNCONTENDED_CLOCK = "an uncontended wall clock"


def _cpu_seconds() -> tuple[float, float]:
    """(this process's CPU, its reaped children's CPU), both user+system.

    ``os.times()`` rather than ``time.process_time()`` because the defect this
    module exists for is a test that SHELLS OUT: mlkit's own positive control
    hands a child pytest 10 s of wall time, and the child's CPU is the whole
    signal. ``process_time()`` cannot see it. Residual 4 in the module
    docstring is the cost of that choice.
    """
    t = os.times()
    return t.user + t.system, t.children_user + t.children_system


def _load_average() -> tuple[float, float, float]:
    """The 1/5/15-minute load averages, or ``(0.0, 0.0, 0.0)`` where absent.

    ``os.getloadavg()`` raises ``OSError`` on platforms that do not keep one.
    Zeroes are the right fallback and not a silent one: they make C4 false, so
    a platform with no load average NEVER reports UNMEASURABLE and every missed
    budget on it stays a FAIL. The failure mode of the fallback is the strict
    direction.
    """
    try:
        one, five, fifteen = os.getloadavg()
    except (OSError, AttributeError):  # pragma: no cover - platform-dependent
        return 0.0, 0.0, 0.0
    return one, five, fifteen


@dataclass(frozen=True)
class ContentionRecord:
    """What the machine was doing while one wall-clock budget was measured.

    Frozen, because it is the evidence a verdict rests on and evidence that can
    be edited after the verdict is evidence of nothing -- the argument
    ``core.result.VerdictSealed`` makes at length for ``CheckResult``.

    Every field is measured. Nothing here is estimated, and the two thresholds
    are carried WITH the reading so that a record read back out of a committed
    artifact can be re-judged without guessing which constants judged it.
    """

    #: What was budgeted, in the caller's words. Goes into the reason line.
    what: str
    #: The declared budget, in seconds. Always > 0: see ``WallClockBudget``.
    budget_s: float
    #: Measured wall time of the span, from ``time.monotonic``.
    wall_s: float
    #: This process's own user+system CPU over the span.
    self_cpu_s: float
    #: The user+system CPU of children REAPED during the span (residual 4).
    children_cpu_s: float
    #: Load averages sampled when the span opened.
    load1_start: float
    load5_start: float
    load15_start: float
    #: Load averages sampled when the span closed.
    load1_end: float
    load5_end: float
    load15_end: float
    #: ``os.cpu_count()``, or 1 when the platform will not say.
    cpu_count: int
    #: The thresholds this record is to be judged against.
    max_cpu_ratio: float = MAX_CPU_RATIO
    load_per_cpu: float = LOAD_PER_CPU
    #: UTC, seconds resolution, taken when the span closed.
    captured_at: str = ""

    # -- derived readings, all pure functions of the fields above ----------

    @property
    def cpu_s(self) -> float:
        """Total CPU attributable to the span: this process plus its children."""
        return self.self_cpu_s + self.children_cpu_s

    @property
    def cpu_ratio(self) -> float:
        """CPU seconds per wall second. ~1.0 working, ~0.0 waiting.

        Can exceed 1.0 legitimately (threads, or several children), which is
        emphatically not contention and reads as WORKING.
        """
        if self.wall_s <= 0.0:
            return 0.0
        return self.cpu_s / self.wall_s

    @property
    def budget_ratio(self) -> float:
        """Wall time as a multiple of the budget. > 1.0 means the budget was missed."""
        if self.budget_s <= 0.0:  # pragma: no cover - unconstructible, see below
            return 0.0
        return self.wall_s / self.budget_s

    @property
    def load1(self) -> float:
        """The 1-minute load this record is judged on: the MAX of both endpoints.

        The max, not the mean, because the question is whether the span COULD
        have been made to wait, and a spike at either end is enough. Residual 3
        records that this is the permissive direction on this axis, which is
        why the other three conditions exist and why the controls drive it.
        """
        return max(self.load1_start, self.load1_end)

    @property
    def load_per_cpu_observed(self) -> float:
        """``load1`` divided by the CPU count: runnable processes per core."""
        if self.cpu_count <= 0:  # pragma: no cover - cpu_count is clamped to >= 1
            return 0.0
        return self.load1 / self.cpu_count

    @property
    def over_budget(self) -> bool:
        """C2: was the declared budget actually missed?"""
        return self.wall_s > self.budget_s

    @property
    def waiting(self) -> bool:
        """C3: was the span off-CPU for most of its length?"""
        return self.cpu_ratio <= self.max_cpu_ratio

    @property
    def loaded(self) -> bool:
        """C4: were there at least ``load_per_cpu`` runnable processes per core?"""
        return self.load1 >= self.load_per_cpu * self.cpu_count

    def to_dict(self) -> dict[str, Any]:
        """The record as it lands in evidence, in a committed artifact, and in a log.

        Derived values are written out rather than left to the reader to
        recompute, because the reader is usually a human comparing two arms in
        a terminal, and a ratio nobody computes is a ratio nobody checks.
        """
        return {
            "what": self.what,
            "budget_s": round(self.budget_s, 6),
            "wall_s": round(self.wall_s, 6),
            "self_cpu_s": round(self.self_cpu_s, 6),
            "children_cpu_s": round(self.children_cpu_s, 6),
            "cpu_s": round(self.cpu_s, 6),
            "cpu_ratio": round(self.cpu_ratio, 6),
            "budget_ratio": round(self.budget_ratio, 6),
            "load1_start": self.load1_start,
            "load5_start": self.load5_start,
            "load15_start": self.load15_start,
            "load1_end": self.load1_end,
            "load5_end": self.load5_end,
            "load15_end": self.load15_end,
            "load1": self.load1,
            "cpu_count": self.cpu_count,
            "load_per_cpu_observed": round(self.load_per_cpu_observed, 6),
            "max_cpu_ratio": self.max_cpu_ratio,
            "load_per_cpu": self.load_per_cpu,
            "over_budget": self.over_budget,
            "waiting": self.waiting,
            "loaded": self.loaded,
            "captured_at": self.captured_at,
        }

    def one_line(self) -> str:
        """The single line that dates an arm's log afterwards.

        This is the deliverable that saved the mlkit landing: a log carrying
        this line can be judged weeks later without re-running anything, and a
        log without it cannot be judged at all.
        """
        return (
            f"CONTENTION {self.what}: wall {self.wall_s:.2f}s "
            f"budget {self.budget_s:.2f}s (x{self.budget_ratio:.2f}) "
            f"cpu {self.cpu_s:.2f}s (ratio {self.cpu_ratio:.2f}) "
            f"load1 {self.load1_start:.2f}->{self.load1_end:.2f} "
            f"on {self.cpu_count} cpu ({self.load_per_cpu_observed:.2f}/cpu) "
            f"thresholds cpu_ratio<={self.max_cpu_ratio} "
            f"load/cpu>={self.load_per_cpu}"
        )


class ContendedWallClock(InputUnavailable):
    """The declared input that could not be read is an UNCONTENDED CLOCK.

    A subclass of ``InputUnavailable`` on purpose rather than a new exception
    type: the runner, the report renderer and ``CheckResult.unmeasurable``
    already know how to render one, already refuse to attach a ``halt`` key to
    it, and already state in its reason that nothing about the pipeline is
    indicted. Reimplementing any of that here would be the eight-copies defect
    CLAUDE.md rule 7 forbids, applied inside one package.

    Raised (or built and passed to :func:`result`) ONLY by this module, and
    only for a record that satisfies C1-C4.
    """

    def __init__(self, record: ContentionRecord) -> None:
        self.record = record
        super().__init__(
            f"the {record.what} budget of {record.budget_s:.2f}s was missed at "
            f"{record.wall_s:.2f}s (x{record.budget_ratio:.2f}) while this "
            f"process used {record.cpu_s:.2f}s of CPU "
            f"(ratio {record.cpu_ratio:.2f} <= {record.max_cpu_ratio}: waiting, "
            f"not working) and the 1-minute load average was "
            f"{record.load1:.2f} on {record.cpu_count} CPUs "
            f"({record.load_per_cpu_observed:.2f}/cpu >= {record.load_per_cpu}). "
            "Wall clock is not a property of the tree: re-measure this arm on a "
            "quiet machine",
            input=UNCONTENDED_CLOCK,
            evidence={CONTENDED_KEY: True, **record.to_dict()},
        )


def classify(record: ContentionRecord) -> Status:
    """PASS, FAIL or UNMEASURABLE for one wall-clock budget. The whole predicate.

    ``UNMEASURABLE`` requires **all** of C2, C3 and C4 (C1 is structural: this
    function only accepts a :class:`ContentionRecord`, which only
    :class:`WallClockBudget` produces). Anything else that missed its budget is
    a real FAIL:

    * missed on a QUIET machine -> FAIL, whatever the CPU ratio;
    * missed while BURNING CPU -> FAIL, whatever the load;
    * met -> PASS, whatever the machine was doing.

    There is deliberately no ``force``, no ``strict=False`` and no threshold
    argument here. The thresholds a record was judged against travel INSIDE the
    record, so they are visible in the evidence and in the committed artifact
    rather than in a call site; and :class:`WallClockBudget` refuses to move
    either of them in the permissive direction at all.
    """
    if not record.over_budget:
        return Status.PASS
    if record.waiting and record.loaded:
        return Status.UNMEASURABLE
    return Status.FAIL


def result(check_id: str, phase: str, record: ContentionRecord) -> CheckResult:
    """The classified record as a ``CheckResult`` the portfolio can aggregate.

    The UNMEASURABLE branch goes through ``CheckResult.unmeasurable`` and
    ``ContendedWallClock`` rather than constructing a status directly, so the
    "UNMEASURABLE HERE, NOT A FINDING" wording, the absent ``halt`` key and the
    evidence keys are the ones every other unmeasurable result in this package
    already uses.
    """
    status = classify(record)
    evidence = record.to_dict()
    if status is Status.PASS:
        return CheckResult.passed(
            check_id,
            phase,
            evidence,
            f"{record.what} finished in {record.wall_s:.2f}s within its "
            f"{record.budget_s:.2f}s budget",
        )
    if status is Status.FAIL:
        return CheckResult.failed(
            check_id,
            phase,
            f"{record.what} missed its {record.budget_s:.2f}s budget at "
            f"{record.wall_s:.2f}s (x{record.budget_ratio:.2f}). This is a real "
            f"finding: {_why_not_contention(record)}",
            evidence,
        )
    return CheckResult.unmeasurable(check_id, phase, ContendedWallClock(record))


def _why_not_contention(record: ContentionRecord) -> str:
    """The sentence a FAIL carries saying which contention condition it fails.

    A FAIL that merely does not mention contention invites the next reader to
    wonder whether the machine was busy. This says which half of the predicate
    ruled it out, using the numbers actually measured.
    """
    reasons = []
    if not record.waiting:
        reasons.append(
            f"the process was WORKING, not waiting — {record.cpu_s:.2f}s of CPU "
            f"over {record.wall_s:.2f}s of wall (ratio {record.cpu_ratio:.2f} > "
            f"{record.max_cpu_ratio})"
        )
    if not record.loaded:
        reasons.append(
            f"the machine was QUIET — 1-minute load {record.load1:.2f} on "
            f"{record.cpu_count} CPUs ({record.load_per_cpu_observed:.2f}/cpu < "
            f"{record.load_per_cpu})"
        )
    return "; ".join(reasons)


class _OpenSpan:
    """One measurement in progress. Produced by :class:`WallClockBudget` only."""

    def __init__(self, budget: WallClockBudget) -> None:
        self._budget = budget
        self._load_start = _load_average()
        self._self_cpu_start, self._children_cpu_start = _cpu_seconds()
        # monotonic LAST, so that the clock starts after the bookkeeping the
        # span is not meant to be charged for.
        self._started = time.monotonic()
        self._record: ContentionRecord | None = None

    def peek(self) -> ContentionRecord:
        """A record of the span SO FAR, without stopping the clock.

        The distinction is not cosmetic and it caused a bug in this module's
        first draft: the pytest surface prints a contention line in the report
        HEADER, at session start, and if that read had closed the session span
        the summary line at the end would have reported a session lasting
        milliseconds. A peek reads; only :meth:`close` decides.
        """
        return self._snapshot()

    def close(self) -> ContentionRecord:
        """Stop the clock and take the second sample. Idempotent."""
        if self._record is None:
            self._record = self._snapshot()
        return self._record

    def _snapshot(self) -> ContentionRecord:
        """Sample the machine now and build the record. No state is changed."""
        wall = time.monotonic() - self._started
        self_cpu, children_cpu = _cpu_seconds()
        load_end = _load_average()
        return ContentionRecord(
            what=self._budget.what,
            budget_s=self._budget.seconds,
            wall_s=wall,
            self_cpu_s=self_cpu - self._self_cpu_start,
            children_cpu_s=children_cpu - self._children_cpu_start,
            load1_start=self._load_start[0],
            load5_start=self._load_start[1],
            load15_start=self._load_start[2],
            load1_end=load_end[0],
            load5_end=load_end[1],
            load15_end=load_end[2],
            cpu_count=max(1, os.cpu_count() or 1),
            max_cpu_ratio=self._budget.max_cpu_ratio,
            load_per_cpu=self._budget.load_per_cpu,
            captured_at=_dt.datetime.now(_dt.UTC).isoformat(timespec="seconds"),
        )

    @property
    def record(self) -> ContentionRecord:
        """The record, closing the span first if the caller has not."""
        return self.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        # Close on the way out even when the body raised: a span that raised
        # still measured a machine, and the record is often the reason.
        self.close()


@dataclass(frozen=True)
class WallClockBudget:
    """A declaration that an assertion's subject is WALL TIME. This is C1.

    Constructing one is the act by which a caller says "what I am about to
    assert is a budget, not a value". Nothing else in this package can produce
    a :class:`ContentionRecord`, and :func:`classify` accepts nothing else, so
    UNMEASURABLE is unreachable from an assertion about a number.

    The budget must be positive and must be declared BEFORE the span runs --
    both enforced here, because a budget chosen after the reading is not a
    budget, it is a rationalisation.

        >>> budget = WallClockBudget(seconds=10.0, what="child pytest run")
        >>> with budget.measure() as span:
        ...     pass
        >>> classify(span.record) is Status.PASS
        True
    """

    seconds: float
    what: str
    max_cpu_ratio: float = MAX_CPU_RATIO
    load_per_cpu: float = LOAD_PER_CPU

    def __post_init__(self) -> None:
        if not self.seconds > 0.0:
            raise ValueError(
                f"a wall-clock budget must be positive; got {self.seconds!r}. A "
                "zero or negative budget cannot be missed or met, so nothing it "
                "produced could be classified"
            )
        if not self.what.strip():
            raise ValueError(
                "a wall-clock budget must name what it bounds; an unnamed budget "
                "produces a record no later reader can attribute to anything"
            )
        # The thresholds may be moved, and ONLY toward strictness. Raising
        # load_per_cpu or lowering max_cpu_ratio makes UNMEASURABLE HARDER to
        # reach, which a repo may legitimately want. The other direction is the
        # only way this facility could become the universal excuse it is
        # designed not to be, so it is refused BY NAME here rather than left to
        # review to notice in a diff. A fork that wants it has to edit this
        # file, which is a CLAUDE.md rule-6 edit to a gate and reads as one.
        if not 0.0 <= self.max_cpu_ratio <= MAX_CPU_RATIO:
            raise ValueError(
                f"max_cpu_ratio must lie in [0, {MAX_CPU_RATIO}]; got "
                f"{self.max_cpu_ratio!r}. Raising it above the declared "
                "threshold would classify a process that was WORKING as one that "
                "was waiting, which is how a real regression becomes an excuse "
                "(CLAUDE.md rule 6)"
            )
        if self.load_per_cpu < LOAD_PER_CPU:
            raise ValueError(
                f"load_per_cpu must be at least {LOAD_PER_CPU}; got "
                f"{self.load_per_cpu!r}. Lowering it would let a QUIET machine "
                "satisfy the contention condition, which is how a real "
                "regression becomes an excuse (CLAUDE.md rule 6)"
            )

    def measure(self) -> _OpenSpan:
        """Open the span. Use as a context manager, or ``close()`` it yourself."""
        return _OpenSpan(self)
