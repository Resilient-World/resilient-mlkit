#!/usr/bin/env python3
"""Drive the three control arms of reports/CONTENTION_PREREGISTRATION.md §5.

One subject, three machines' worth of conditions, and the same classifier
throughout. The subject is deliberately the SHAPE of the defect that caused
this module to exist: a parent process that shells out to a child and waits,
with a wall-clock budget on the child. mlkit's own
``test_positive_control_a_sleeping_test_fails_on_timeout`` is that shape, and
so is arabica's phantom failure.

    FIRES   a GENUINE regression is introduced into the child (a real O(n^2),
            a bigger n) and the machine is quiet -> must classify FAIL,
            because the child BURNS CPU and CPU time tracks wall time.

    SILENT  the child is UNCHANGED and the machine is put under synthetic
            load -> must classify UNMEASURABLE, with the record.

    NOT-DEAD four sub-arms that damage the facility and re-ask FIRES:
            N1 the facility REMOVED (the bare budget assertion);
            N2 C4 destroyed (load_per_cpu -> 0.0: every machine counts loaded);
            N3 C3 destroyed (max_cpu_ratio -> 1.0: every process counts waiting);
            N4 BOTH destroyed.
            N1 and N2 must still read FAIL. N3 and N4 are driven and reported
            as measured -- the point of driving them is that the answer is
            recorded rather than assumed.

The budget for the unchanged child is NOT invented. It is measured on the
quiet machine first and set to ``BUDGET_MULTIPLE`` times that reading, and
both numbers are written into the artifact.

Synthetic load is made by this script's OWN children, each PID recorded at
launch and killed by that recorded PID only -- never by name pattern, which is
how one lane killed another lane's suite leg on 2026-09-06.

Usage::

    python scripts/contention_control_drive.py --out reports/CONTENTION_CONTROL_ARMS.json
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from resilient_mlkit.core import contention as ct
from resilient_mlkit.core.result import Status

#: The child's work: sum of a triangular double loop, an honest O(n^2).
#: ``N_BASELINE`` is the unchanged code. ``N_REGRESSED`` is the genuine
#: slowdown a developer might introduce without noticing -- same code, one
#: constant larger, and it burns CPU for it.
N_BASELINE = 3000
N_REGRESSED = 12000

#: The budget for the unchanged child, as a multiple of its measured quiet
#: wall time. Declared here rather than as an absolute number of seconds
#: because an absolute number would be a figure nobody measured on this host.
BUDGET_MULTIPLE = 1.5

#: Synthetic-load workers, as a multiple of the CPU count.
LOAD_WORKERS_PER_CPU = 2

#: How long to wait for the 1-minute load average to cross the threshold, and
#: how often to look. ``getloadavg`` is an EWMA over the preceding minute, so
#: crossing takes tens of seconds however many workers are started.
LOAD_RAMP_CEILING_S = 240.0
LOAD_POLL_S = 5.0

CHILD = (
    "import sys\n"
    "n = int(sys.argv[1])\n"
    "total = 0\n"
    "for i in range(n):\n"
    "    for j in range(i):\n"
    "        total += j\n"
    "print(total)\n"
)

BUSY = (
    "import time\n"
    "end = time.monotonic() + float(__import__('sys').argv[1])\n"
    "x = 0\n"
    "while time.monotonic() < end:\n"
    "    x += 1\n"
)


def _nice_prefix(level: int) -> list[str]:
    """``nice -n LEVEL`` as an argv prefix, or nothing when not asked for.

    An argv prefix rather than ``preexec_fn``: ruff's PLW1509 is right that a
    ``preexec_fn`` is unsafe in a process that may use threads, and this drive
    has no business being the exception.
    """
    if not level:
        return []
    nice = shutil.which("nice")
    if nice is None:  # pragma: no cover - POSIX hosts all have it
        return []
    return [nice, "-n", str(level)]


def run_child(
    n: int, budget_s: float, what: str, *, nice_level: int = 0
) -> ct.ContentionRecord:
    """Run the child once under a declared budget and return the record.

    The span closes AFTER ``subprocess.run`` returns, which is after the child
    has been reaped -- the condition ``os.times()`` needs before it will report
    the child's CPU (``core/contention.py`` residual 4).

    ``nice_level`` exists for the SILENT arm and is disclosed rather than
    hidden. This drive raises a real load average on a machine where other
    lanes are measuring, so its load workers run at low priority; the child
    measured against them is given the SAME low priority, so that it genuinely
    contends with them instead of walking past them. Load average counts
    runnable processes regardless of priority, so C4 sees the real number, and
    the child's wall and CPU are measured, not modelled.
    """
    budget = ct.WallClockBudget(seconds=budget_s, what=what)
    with budget.measure() as span:
        subprocess.run(
            [*_nice_prefix(nice_level), sys.executable, "-c", CHILD, str(n)],
            check=True,
            capture_output=True,
            text=True,
        )
    return span.record


def arm(name: str, record: ct.ContentionRecord, required: str | None) -> dict[str, Any]:
    """One arm's row: what was measured, what it classified, what was required."""
    status = ct.classify(record)
    row: dict[str, Any] = {
        "arm": name,
        "classified": status.value,
        "required": required,
        "agrees": None if required is None else status.value == required,
        # Measured, not assumed from the arm's name. The FIRES arm is only the
        # FIRES arm if the machine really was below the declared threshold
        # while it ran, and a label saying "quiet" is not a measurement.
        "machine_quiet": not record.loaded,
        "record": record.to_dict(),
        "one_line": record.one_line(),
    }
    return row


def raise_load(
    workers: int, hold_s: float, *, nice_level: int = 0
) -> tuple[list[int], float, float]:
    """Start ``workers`` busy children; wait for load1 to cross the threshold.

    Returns (pids, load1 reached, seconds waited). Every PID is returned so the
    caller can kill exactly these and nothing else.
    """
    pids: list[int] = []
    for _ in range(workers):
        proc = subprocess.Popen(
            [*_nice_prefix(nice_level), sys.executable, "-c", BUSY, str(hold_s)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        pids.append(proc.pid)
    cpu_count = max(1, os.cpu_count() or 1)
    target = ct.LOAD_PER_CPU * cpu_count
    started = time.monotonic()
    load1 = os.getloadavg()[0]
    while load1 < target and time.monotonic() - started < LOAD_RAMP_CEILING_S:
        time.sleep(LOAD_POLL_S)
        load1 = os.getloadavg()[0]
    return pids, load1, time.monotonic() - started


def kill_recorded(pids: list[int]) -> list[int]:
    """Kill exactly the PIDs recorded at launch. Never a name pattern."""
    killed = []
    for pid in pids:
        try:
            os.kill(pid, signal.SIGTERM)
            killed.append(pid)
        except ProcessLookupError:
            pass
    for pid in pids:
        try:
            os.waitpid(pid, 0)
        except ChildProcessError:
            pass
    return killed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument(
        "--nice",
        type=int,
        default=19,
        help=(
            "scheduling priority for the synthetic-load workers AND for the "
            "child measured against them. Defaults to 19 so this drive does "
            "not steal CPU from another lane's suite while it runs."
        ),
    )
    parser.add_argument(
        "--skip-load",
        action="store_true",
        help="drive FIRES and NOT-DEAD only; do not raise synthetic load",
    )
    args = parser.parse_args()

    import resilient_mlkit

    out: dict[str, Any] = {
        "preregistration": "reports/CONTENTION_PREREGISTRATION.md",
        "driven_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "mlkit_file": resilient_mlkit.__file__,
        "mlkit_version": resilient_mlkit.__version__,
        # The build, beside the version, because the version cannot identify a
        # build: E-M24 measured two mlkit trees 40 commits apart both declaring
        # one version string. tests/test_build_identity.py enforces the pairing
        # and caught this payload before it landed.
        "mlkit_build": resilient_mlkit.__build__,
        "cpu_count": max(1, os.cpu_count() or 1),
        "thresholds": {
            "MAX_CPU_RATIO": ct.MAX_CPU_RATIO,
            "LOAD_PER_CPU": ct.LOAD_PER_CPU,
        },
        "subject": {
            "shape": "a parent that shells out and waits, with a budget on the child",
            "n_baseline": N_BASELINE,
            "n_regressed": N_REGRESSED,
            "budget_multiple": BUDGET_MULTIPLE,
        },
        "arms": [],
    }

    # -- the quiet baseline the budget is derived from ---------------------
    # Measured, not chosen. A budget picked out of the air is the fabricated
    # expected range rule 2 forbids.
    warm = run_child(N_BASELINE, 3600.0, "baseline warm-up (budget not read)")
    quiet = run_child(N_BASELINE, 3600.0, "unchanged child, baseline")
    budget_s = quiet.wall_s * BUDGET_MULTIPLE
    out["baseline"] = {
        "warm_up_wall_s": round(warm.wall_s, 6),
        "quiet_wall_s": round(quiet.wall_s, 6),
        "derived_budget_s": round(budget_s, 6),
        "record": quiet.to_dict(),
    }

    # -- CONTROL: the unchanged child under the derived budget, quiet ------
    # Not one of the three arms, and it is here because without it the FIRES
    # arm is equally consistent with "this harness fails everything".
    unchanged_quiet = run_child(N_BASELINE, budget_s, "unchanged child")
    out["arms"].append(
        arm("NEGATIVE (unchanged child)", unchanged_quiet, Status.PASS.value)
    )

    # -- ARM 1: FIRES ------------------------------------------------------
    fires = run_child(N_REGRESSED, budget_s, "REGRESSED child (real O(n^2))")
    out["arms"].append(arm("FIRES", fires, Status.FAIL.value))

    # -- ARM 3: NOT-DEAD, driven on the FIRES record -----------------------
    # N1: the facility REMOVED. What is left is the bare assertion every one of
    # today's four incidents actually made: wall > budget is a failure.
    bare = fires.wall_s > fires.budget_s
    out["arms"].append(
        {
            "arm": "NOT-DEAD N1 (facility removed: bare budget assertion)",
            "classified": "FAIL" if bare else "PASS",
            "required": "FAIL",
            "agrees": bare,
            "machine_quiet": not fires.loaded,
            "record": fires.to_dict(),
            "one_line": fires.one_line(),
        }
    )
    # N2/N3/N4: the thresholds MUTATED. The public API refuses both mutations
    # (WallClockBudget.__post_init__), so they are applied to the record
    # directly -- which is what a fork that edited core/contention.py would
    # produce, and the mutated values stay visible in every row below.
    for label, kwargs, required in (
        ("NOT-DEAD N2 (C4 destroyed: load_per_cpu=0.0)", {"load_per_cpu": 0.0}, "FAIL"),
        ("NOT-DEAD N3 (C3 destroyed: max_cpu_ratio=1.0)", {"max_cpu_ratio": 1.0}, None),
        (
            "NOT-DEAD N4 (both destroyed)",
            {"load_per_cpu": 0.0, "max_cpu_ratio": 1.0},
            None,
        ),
    ):
        mutated = dataclasses.replace(fires, **kwargs)
        out["arms"].append(arm(label, mutated, required))

    # The same mutations REFUSED through the public API, which is what an
    # adopting repo would have to get past to reach them.
    refusals = []
    for kwargs in ({"load_per_cpu": 0.0}, {"max_cpu_ratio": 1.0}):
        try:
            ct.WallClockBudget(seconds=1.0, what="mutation attempt", **kwargs)
        except ValueError as exc:
            refusals.append({"mutation": kwargs, "refused": True, "message": str(exc)})
        else:  # pragma: no cover - a constructed permissive budget is the defect
            refusals.append({"mutation": kwargs, "refused": False, "message": ""})
    out["threshold_mutation_refused_by_api"] = refusals

    # -- ARM 2: SILENT-AS-UNMEASURABLE -------------------------------------
    if args.skip_load:
        out["arms"].append(
            {
                "arm": "SILENT",
                "classified": "NOT DRIVEN",
                "required": Status.UNMEASURABLE.value,
                "agrees": None,
                "machine_quiet": None,
                "record": {},
                "one_line": "--skip-load was passed; no synthetic load was raised",
            }
        )
    else:
        cpu_count = max(1, os.cpu_count() or 1)
        workers = LOAD_WORKERS_PER_CPU * cpu_count
        hold_s = LOAD_RAMP_CEILING_S + 120.0
        window_start = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        pids, load_reached, waited = raise_load(
            workers, hold_s, nice_level=args.nice
        )
        try:
            loaded = run_child(
                N_BASELINE,
                budget_s,
                "unchanged child, UNDER LOAD",
                nice_level=args.nice,
            )
        finally:
            killed = kill_recorded(pids)
        window_end = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        out["synthetic_load"] = {
            "workers": workers,
            "nice_level": args.nice,
            "pids": pids,
            "killed": killed,
            "load1_reached": load_reached,
            "ramp_seconds": round(waited, 1),
            "window_start_utc": window_start,
            "window_end_utc": window_end,
            "note": (
                "this window raised host load deliberately; any other arm on "
                "this machine overlapping it is datable from these timestamps, "
                "which is the whole point of the facility"
            ),
        }
        out["arms"].append(arm("SILENT", loaded, Status.UNMEASURABLE.value))

    # The FIRES arm's whole claim is "a genuine regression FAILS on a QUIET
    # machine". Driven on a loaded one it may still read FAIL -- it did, at
    # load 14.34 on 2026-09-06 -- but that is a different and weaker statement,
    # and an artifact that did not say so would let a label stand in for a
    # measurement. So this is computed from the record and it GATES the drive:
    # a FIRES arm measured on a loaded host makes the run disagree, and the
    # protocol's own answer applies to the protocol's own controls -- re-measure.
    fires_row = next(row for row in out["arms"] if row["arm"] == "FIRES")
    out["fires_measured_on_a_quiet_machine"] = bool(fires_row["machine_quiet"])

    disagreements = [
        row["arm"]
        for row in out["arms"]
        if row.get("required") is not None and not row.get("agrees")
    ]
    if not out["fires_measured_on_a_quiet_machine"]:
        disagreements.append("FIRES was not measured on a quiet machine")
    out["all_required_arms_agree"] = not disagreements
    out["disagreements"] = disagreements

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    for row in out["arms"]:
        print(
            f"{row['arm']:<52} {row['classified']:<13} "
            f"required={row['required']} agrees={row['agrees']}"
        )
    print(f"\nwritten: {args.out}")
    return 0 if out["all_required_arms_agree"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
