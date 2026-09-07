# Contended measurement — RESULTS (E-M40)

Every number here was produced by running the code in this repo. The machine:
10 CPUs, macOS, 2026-09-06, with two other lanes running their own suites
throughout (their load is visible in the readings and is not filtered out).
Preregistration: `reports/CONTENTION_PREREGISTRATION.md`, committed at
`93e40a2` **before** any source file existed. Raw drive:
`reports/CONTENTION_CONTROL_ARMS.json`.

## The three control arms, driven

`scripts/contention_control_drive.py`, one subject throughout: **a parent that
shells out to a child and waits, with a wall-clock budget on the child** — the
shape of mlkit's own positive control and of arabica's phantom failure. The
child is an honest `O(n²)` triangular sum; the "genuine regression" is the same
code with `n` raised from 3,000 to 12,000.

The budget is **not invented**. It is `1.5 ×` the child's measured quiet wall
time: quiet run `0.3855 s`, so **budget `0.5783 s`**.

| arm | code | machine (load1 / 10 cpu) | wall | cpu (ratio) | verdict | required |
|---|---|---|---|---|---|---|
| NEGATIVE | unchanged | 6.11 (0.61/cpu) | 0.40 s | 0.38 s (0.95) | **PASS** | PASS ✔ |
| **FIRES** | **regressed O(n²)** | 6.11→6.33 (0.63/cpu) | 6.46 s (×11.18) | 6.39 s (**0.99**) | **FAIL** | FAIL ✔ |
| **SILENT** | **unchanged** | **13.23 (1.32/cpu)** | 1.94 s (×3.36) | 0.54 s (**0.28**) | **UNMEASURABLE** | UNMEASURABLE ✔ |

**That is the discrimination, in three rows.** The same unchanged child reads
PASS on the quiet machine and UNMEASURABLE on the loaded one — its wall time
went from 0.39 s to 1.94 s while it did the same work. The regressed child reads
FAIL on the *quiet* machine, because it burned 6.39 s of CPU for its 6.46 s of
wall and a process that is working is not a process that is waiting.

`all_required_arms_agree: true`, `disagreements: []`.

### CHECK-NOT-DEAD, four sub-arms on the FIRES record

| sub-arm | what was damaged | verdict |
|---|---|---|
| **N1** | the facility **removed** — the bare `wall > budget` assertion | **FAIL** ✔ |
| **N2** | **C4 destroyed** (`load_per_cpu → 0.0`: every machine counts as loaded) | **FAIL** ✔ |
| **N3** | **C3 destroyed** (`max_cpu_ratio → 1.0`: every process counts as waiting) | **FAIL** ✔ |
| **N4** | **both destroyed** | **UNMEASURABLE** — reported, not hidden |

N2 is the one that matters most: **removing the entire load condition does not
save a CPU-burning regression**, because C3 decides it on its own. N4 is what a
dead check looks like, and it is why both mutations are refused at construction:

```
WallClockBudget(seconds=1.0, what=..., load_per_cpu=0.0)   -> ValueError ... "(CLAUDE.md rule 6)"
WallClockBudget(seconds=1.0, what=..., max_cpu_ratio=1.0)  -> ValueError ... "(CLAUDE.md rule 6)"
```

Both refusals are recorded in the artifact
(`threshold_mutation_refused_by_api`), and every record carries the thresholds
it was judged against, so a fork that forced them by editing
`core/contention.py` shows the forced values in its own output.

**Found by driving N3 rather than by reasoning about it:** a span that saturates
a core records `cpu_ratio` slightly **above** 1.0 (`os.times` resolution against
`time.monotonic`), so even the largest value the type permits often cannot make
it count as waiting at all. The subprocess subject reads 0.99 and the in-process
burn in `tests/test_contention_controls.py` reads above 1.0; both are pinned.

### The synthetic load, disclosed

20 workers at `nice -n 19`, PIDs recorded at launch and **all 20 killed by those
recorded PIDs**; window `2026-09-06T23:58:20Z → 23:58:32Z` (12 s), load1 reached
**13.23**. Low priority, and the measured child was given the **same** low
priority so that it genuinely contended with the workers rather than walking
past them — load average counts runnable processes regardless of priority, so C4
saw the real number and the child's wall and CPU are measured, not modelled.
Two other lanes were running suites on this host; the window is published so
that any anomaly of theirs inside it is datable, which is the facility applied
to itself.

## Suite, ruff and mypy

Measured in this clone with `resilient_mlkit.__file__` asserted inside it.
Full readings, arms run sequentially, are in
`loop/repair/mlkit-contention.md` (the lane record) and reproduced in the PR.

## What could NOT be made to distinguish itself

Declared in the preregistration §6 before measuring, and unchanged by the
measurements:

1. **A sleeping regression on a loaded machine.** `time.sleep(30)` newly
   introduced into the code under test and a 30 s wait for a busy CPU produce
   the same record. That arm reads UNMEASURABLE — **not a pass** — and the
   protocol obliges a re-measurement on a quiet machine, where C4 fails and the
   same code reads FAIL. This is the declared price of the load axis and it is
   why the classifier's UNMEASURABLE had to be an obligation rather than a
   verdict.
2. **How much slowdown a given load explains** is not modelled. A 1000× overrun
   at 1.1 × cpu_count satisfies the predicate. Inventing a curve would be a
   fabricated expected range (rule 2), so none was invented; `budget_ratio` and
   `load_per_cpu_observed` are printed side by side instead.
3. `os.getloadavg()` decays over the preceding minute, so a short span is judged
   partly on load that preceded it. Both endpoints are recorded; the classifier
   takes the max, the permissive direction on that axis, which is why the other
   three conditions exist and why N2 is driven.
4. `os.times()` counts only **reaped** children.
5. Two instants, not a time series.
