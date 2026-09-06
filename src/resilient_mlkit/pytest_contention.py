"""The pytest surface the eight repos adopt: declare a budget, date the log.

WHAT THIS IS FOR
----------------
Two separate jobs, and keeping them separate is the point.

**Job 1 — a test declares that its assertion is a wall-clock budget.** The
``wall_clock_budget`` marker and the fixture of the same name. A test that
declares one gets a ``core.contention.ContentionRecord`` attached to its report
and printed beside its result, and can ask ``core.contention.classify`` what
that record supports.

**Job 2 — the whole run says what machine it ran on.** ``pytest_report_header``
and ``pytest_terminal_summary`` print the session's own contention line at both
ends of the log. That one line is what let mlkit's PR #54 be landed correctly
on 2026-09-06: an arm whose log read ``1196.12s`` against a normal ``635.75s``
could be dated to three concurrent suites AFTERWARDS, from the log alone,
without re-running anything. A log without it cannot be judged later at all.

WHAT THIS DELIBERATELY DOES NOT DO
----------------------------------
**It never changes pytest's verdict.** Not to a pass, not to a skip, not to an
xfail. A budget test that fails, fails; what this adds is the record printed
next to it saying what the machine was doing. Three reasons, and the third
settles it:

1. A skip exits 0, so a suite that skipped a real regression is green — and the
   fleet's landing rule ("nothing only-on-branch") would then compare a real
   failure on one arm against a skip on the other and see agreement.
2. ``Status.UNMEASURABLE`` is mlkit's word for a CHECK's verdict, the thing
   ``mlkit check`` aggregates into a gate. pytest's vocabulary is a different
   vocabulary, and mapping one silently onto the other is how a status comes to
   mean two things.
3. UNMEASURABLE obliges a RE-MEASUREMENT. Nothing in a green suite obliges
   anybody to do anything.

So this adoption is honest about what it buys. It does not make a contended
suite green. It makes a contended suite **judgeable**, which is the thing that
was missing on 2026-09-06 and the thing that cost four measurements.

REGISTRATION IS OPT-IN, AND THAT IS DELIBERATE
----------------------------------------------
This module declares no ``pytest11`` entry point. All eight repos install
mlkit, and an entry point would register this plugin in all eight the next time
anyone locked — an instrument change arriving as ambient drift, which is the
first paragraph of ``CHANGELOG.md`` and the reason this package is versioned at
all. A repo adopts it in one line, in its own commit::

    # conftest.py
    pytest_plugins = ["resilient_mlkit.pytest_contention"]

or on the command line, ``-p resilient_mlkit.pytest_contention``.

TWO FACTS ABOUT pytest-timeout THAT COST A DAY, RECORDED WHERE THEY ARE READ
---------------------------------------------------------------------------
Both measured 2026-09-06. Both are why a runner-level accommodation is not
enough on its own, and neither is discoverable from a config file.

* **A test file's own ``@pytest.mark.timeout(120)`` BEATS ``--timeout`` on the
  command line.** In resilient-choco,
  ``tests/test_agrifm_cocoa_training.py::test_synthetic_training_exports_checkpoint``
  carries a 120 s marker; raising ``--timeout`` on the runner did nothing for
  it, and two suite pairs died at 17 % before the precedence was understood. A
  marker is a per-test declaration and the flag is a default; the default
  loses.
* **``timeout_method = "thread"`` cannot bound a hang that holds the
  interpreter lock.** In resilient-torrent a 180 s per-test timeout did not fire
  on a torch section that held the GIL for 79 minutes; what fired was
  ``faulthandler_timeout``, which DUMPS and does not kill. ``signal`` raises
  inside the test, so the timeout becomes one NAMED failure instead of a
  truncated session — which is also what makes failure sets comparable by name.
  Changing the METHOD is a reporting-mechanism change; changing the 120/180 s
  THRESHOLD is a rule-6 edit to a committed gate. The two must not be confused,
  and on 2026-09-06 choco changed the first and left the second alone.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from .core.contention import ContentionRecord, WallClockBudget, classify

if TYPE_CHECKING:  # pragma: no cover - typing only
    from collections.abc import Iterator

#: The marker name a test uses to declare that its assertion is wall time.
MARKER = "wall_clock_budget"

#: Attribute under which a node's records live between the call phase and the
#: report phase. A list: one test may open several spans.
RECORDS_ATTR = "_mlkit_contention_records"

#: Attribute on ``Config`` holding the session's own open span.
SESSION_SPAN_ATTR = "_mlkit_session_span"

#: Attribute on an ``Item`` holding the span opened for a MARKED test. A
#: different name from the session's: two spellings of one attribute is one of
#: them silently not being read, which ``core/result.py`` records as E-M21.
ITEM_SPAN_ATTR = "_mlkit_item_span"

#: The name under which a record reaches ``report.user_properties``, and from
#: there JUnit XML.
PROPERTY = "mlkit_contention"

#: The session has no declared budget the way a test does. "The suite should
#: take under X seconds" is exactly the fabricated expected range CLAUDE.md
#: rule 2 forbids, so the session span is opened against this nominal budget
#: and ITS VERDICT IS NEVER READ — only its record is, and a record is a
#: measurement. The number exists so that one ``WallClockBudget`` type produces
#: both kinds of span.
SESSION_NOMINAL_BUDGET_S = 1.0


def pytest_configure(config: pytest.Config) -> None:
    """Register the marker, and open the session's span.

    The marker must be registered or ``--strict-markers`` rejects every test
    that uses it — which is the correct behaviour for an unregistered marker,
    and the reason this lives here rather than in each adopting repo's ini
    where it would be a second declaration of one fact.
    """
    config.addinivalue_line(
        "markers",
        f"{MARKER}(seconds): this test's assertion is a WALL-CLOCK budget of "
        "`seconds`. Attaches a contention record (load, CPU-vs-wall, "
        "elapsed-vs-budget) to the report so a failure can be dated to the "
        "machine afterwards. It does NOT change the test's verdict.",
    )
    budget = WallClockBudget(
        seconds=SESSION_NOMINAL_BUDGET_S, what="pytest session"
    )
    setattr(config, SESSION_SPAN_ATTR, budget.measure())


def session_record(config: pytest.Config, *, close: bool) -> ContentionRecord | None:
    """The session's contention record, or None if ``configure`` never ran.

    ``close=False`` PEEKS: it reads the machine now and leaves the session
    clock running. The header calls it that way, and the distinction is
    load-bearing — a header that closed the span would leave the summary at the
    end of the log reporting a session that lasted milliseconds.
    """
    span = getattr(config, SESSION_SPAN_ATTR, None)
    if span is None:  # pragma: no cover - configure always runs first
        return None
    record: ContentionRecord = span.close() if close else span.peek()
    return record


def pytest_report_header(config: pytest.Config) -> list[str]:
    """The load the session STARTED under, at the top of the log.

    Printed at the start as well as the end because a run that is killed
    mid-way never reaches the summary — and a killed arm is exactly the arm
    somebody will later need to date. torrent's 79-minute stall was killed.
    """
    record = session_record(config, close=False)
    if record is None:  # pragma: no cover - configure always runs first
        return []
    per_cpu = record.load1_start / record.cpu_count
    return [
        (
            f"mlkit contention: {record.cpu_count} cpu, load1 "
            f"{record.load1_start:.2f} ({per_cpu:.2f}/cpu) at session start. A "
            "by-name comparison against an arm run at materially different load "
            "is VOID — see docs/CONTENDED_MEASUREMENT.md"
        )
    ]


def pytest_terminal_summary(
    terminalreporter: Any, exitstatus: int, config: pytest.Config
) -> None:
    """The session's whole contention record, as the last thing in the log."""
    record = session_record(config, close=True)
    if record is None:  # pragma: no cover - configure always runs first
        return
    terminalreporter.write_sep("-", "mlkit contention record")
    terminalreporter.write_line(
        f"session wall {record.wall_s:.2f}s, cpu {record.cpu_s:.2f}s (self "
        f"{record.self_cpu_s:.2f}s + reaped children "
        f"{record.children_cpu_s:.2f}s, ratio {record.cpu_ratio:.2f}), load1 "
        f"{record.load1_start:.2f} -> {record.load1_end:.2f} on "
        f"{record.cpu_count} cpu, load5 {record.load5_end:.2f}, load15 "
        f"{record.load15_end:.2f}"
    )
    terminalreporter.write_line(
        "arms for a by-name comparison run SEQUENTIALLY; a comparison between "
        "arms at materially different load is VOID and is re-measured, not "
        "explained"
    )


class BudgetSpans:
    """What the ``wall_clock_budget`` fixture hands a test.

    Call it to open a span. Every span opened is closed when the test ends and
    its record kept on the node, so the report hook can print it beside the
    result::

        def test_child_pytest_is_bounded(wall_clock_budget):
            with wall_clock_budget(10.0, "child pytest run") as span:
                proc = subprocess.run(argv, timeout=10)
            assert proc.returncode != 0, span.record.one_line()

    ``classify(span.record)`` answers what the record supports. That is
    information for the test author and for the reader of the log; this class
    never acts on it, because acting on it would mean changing a verdict.
    """

    def __init__(self, node: pytest.Item) -> None:
        self._node = node
        self._spans: list[Any] = []
        self.records: list[ContentionRecord] = []

    def __call__(self, seconds: float, what: str = "") -> Any:
        budget = WallClockBudget(
            seconds=seconds, what=what or f"{self._node.name} wall-clock budget"
        )
        span = budget.measure()
        self._spans.append(span)
        return span

    def finish(self) -> list[ContentionRecord]:
        """Close every span the test opened; keep the records on the node."""
        self.records = [span.record for span in self._spans]
        existing: list[ContentionRecord] = list(
            getattr(self._node, RECORDS_ATTR, [])
        )
        setattr(self._node, RECORDS_ATTR, existing + self.records)
        return self.records


@pytest.fixture
def wall_clock_budget(request: pytest.FixtureRequest) -> Iterator[BudgetSpans]:
    """Declare that an assertion in this test is a wall-clock budget."""
    spans = BudgetSpans(request.node)
    yield spans
    spans.finish()


def declared_budget(node: pytest.Item) -> float | None:
    """The seconds a ``wall_clock_budget`` MARKER declares, if it declares any."""
    marker = node.get_closest_marker(MARKER)
    if marker is None:
        return None
    if marker.args:
        return float(marker.args[0])
    seconds = marker.kwargs.get("seconds")
    return None if seconds is None else float(seconds)


def pytest_runtest_setup(item: pytest.Item) -> None:
    """Open a span for a MARKED test, covering its setup and call.

    Setup is inside the span deliberately: a fixture that builds a fixture that
    reads a file is time the test spent waiting for this machine like any
    other, and excluding it would understate exactly the quantity being
    measured. Teardown is outside, because it runs after the verdict.

    This hook returns nothing and touches no outcome. Neither does the
    ``makereport`` hook that closes the span. That is the whole of this
    plugin's interaction with pytest's own verdict, and
    ``tests/test_contention_pytest_surface.py`` asserts it by execution.
    """
    seconds = declared_budget(item)
    if seconds is None:
        return
    budget = WallClockBudget(seconds=seconds, what=item.name)
    setattr(item, ITEM_SPAN_ATTR, budget.measure())


def pytest_runtest_makereport(item: pytest.Item, call: Any) -> None:
    """Close the marked span, and attach every record to the report.

    A plain hook, not a wrapper: it returns ``None``, so it cannot influence
    the outcome pytest computes. It only appends to ``user_properties``, which
    the report carries and JUnit XML renders.
    """
    if call.when != "call":
        return
    span = getattr(item, ITEM_SPAN_ATTR, None)
    if span is not None:
        existing: list[ContentionRecord] = list(getattr(item, RECORDS_ATTR, []))
        setattr(item, RECORDS_ATTR, [*existing, span.record])
    for record in getattr(item, RECORDS_ATTR, []):
        item.user_properties.append((PROPERTY, record.to_dict()))
        item.user_properties.append(
            (f"{PROPERTY}_supports", classify(record).value)
        )


def pytest_report_teststatus(report: Any, config: pytest.Config) -> None:
    """Explicitly does nothing, and exists so that saying so is checkable.

    This is the hook a plugin would use to rewrite a failure into something
    softer. Returning ``None`` from it leaves pytest's own status untouched.
    It is implemented here, empty, so that a reader looking for the place this
    plugin downgrades a verdict finds this docstring instead of an absence —
    and so that deleting the downgrade later cannot be mistaken for never
    having had one.
    """
