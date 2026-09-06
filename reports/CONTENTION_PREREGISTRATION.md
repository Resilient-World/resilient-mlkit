# Contended measurement — PREREGISTRATION (E-M40)

Written **before** any implementation exists, and committed on its own so that
the acceptance rules and the three control arms cannot be adjusted afterwards
to fit whatever the code turned out to do. The results go to
`reports/CONTENTION_RESULTS.md` and `reports/CONTENTION_CONTROL_ARMS.json`.

Date: 2026-09-06. Base: `main` `0fcae1f785028822d264e334530f9f8f6b7eca35` (v1.3.0).

---

## 1. The defect

**A test or gate whose verdict depends on how busy the machine was.** Four
instances, all measured on 2026-09-06 on one 10-CPU host, all recorded in the
lane records they were measured in:

1. **mlkit, this repo.** `tests/test_pytest_timeout_active.py::
   test_positive_control_a_sleeping_test_fails_on_timeout` gives a child pytest
   **10 s of wall time** (`SUBPROCESS_CEILING_S`). Run against three concurrent
   suites the arm took **1196.12 s** against a normal **635.75 s** and that test
   read **rc 1** — a result that would have blocked landing PR #54. The same
   tree, the same runner, on a quiet machine: **1307 passed, rc 0, 101.02 s**.
   The tell that dated the cause to contention rather than to the tree: the
   concurrent arm ALSO failed the same file's **negative** control
   (`test_negative_control_a_fast_test_passes_under_the_same_limit`), and a fast
   test cannot be made slow by a source change.
2. **resilient-choco.** The **same tree run twice** produced failure sets
   differing by **five names**, every one a `pytest-timeout` at the 120 s / 180 s
   boundary. Separately: a test file's own `@pytest.mark.timeout(120)` **beats**
   `--timeout` on the command line, so a runner-level accommodation silently
   does not apply to the test that most needs it.
3. **resilient-torrent.** `timeout_method = "thread"` cannot bound a hang that
   holds the interpreter lock; a 180 s per-test timeout killed a whole suite at
   17 % under load; a **79-minute** "stall" at 70 % and a "hung" readiness
   regeneration both **vanished at low load** (the full suite runs in 13.6
   minutes on a quiet machine).
4. **resilient-arabica.** A three-stream parallel plan produced a **phantom**
   failure in one arm — a test that shells out with a 120 s budget and takes
   36 s alone. It was discarded and re-run uncontended.

What all four have in common: **the assertion is a wall-clock budget, and wall
clock is not a property of the tree.** The verdict that came out was not PASS
and it was not FAIL. It was *nothing*, reported as FAIL.

## 2. What is built (in mlkit, because rule 7 forbids eight local copies)

1. **A contention record.** `core.contention.ContentionRecord` — captured at the
   moment of a timing-sensitive measurement: 1/5/15-minute load average at the
   start and at the end of the span, CPU count, the process's own CPU time
   **and its reaped children's**, the wall time, and the elapsed-vs-budget
   ratio. Standard library only (`os.getloadavg`, `os.times`,
   `time.monotonic`), no new dependency, no network, no file written by
   default.
2. **A classifier** returning a status from the vocabulary the fleet already
   has (`core.result.Status`): **PASS / FAIL / UNMEASURABLE**. The predicate for
   UNMEASURABLE is declared in §3 below, before it exists.
3. **A pytest surface**: a `wall_clock_budget` marker and fixture by which a
   test declares *my assertion is a wall-clock budget*, and a session hook that
   writes the whole run's contention record into the run's own log, so that any
   arm's log can be dated afterwards — which is exactly what let the mlkit
   landing above be judged correctly.
4. **A measurement protocol**, written into `docs/CONTENDED_MEASUREMENT.md` as
   the fleet's rule.

## 3. THE PREDICATE, declared up front and deliberately narrow

`classify(record)` returns **`Status.UNMEASURABLE` only when ALL FOUR hold**:

| # | condition | why it is here |
|---|---|---|
| **C1** | **The assertion IS a wall-clock budget.** Structural: `UNMEASURABLE` is reachable only through `WallClockBudget`, which cannot be constructed without a positive `budget_s` declared **before** the span runs. There is no other call path, and no flag that routes a non-timing assertion through it. | A universal excuse is one that any assertion can reach. This one cannot be reached by a correctness assertion at all. |
| **C2** | **The budget was missed**: `wall_s > budget_s`. | A met budget is `PASS`. Contention never *creates* a verdict. |
| **C3** | **The process was waiting, not working**: `cpu_ratio = (self_cpu_s + children_cpu_s) / wall_s <= 0.5`. | A regression that burns CPU tracks its own wall clock. `0.5` is declared here, before measurement, and means *the span spent more time off-CPU than on it*. |
| **C4** | **The machine was demonstrably loaded**: `max(load1_start, load1_end) >= 1.0 × cpu_count`. | One runnable process per CPU is the point at which a runnable process begins to wait for one. `1.0` is declared here, before measurement. |

**Everything else with `wall_s > budget_s` is a real `FAIL`.** In particular a
budget missed on a quiet machine is FAIL whatever the CPU ratio, and a budget
missed while the process was burning CPU is FAIL whatever the load.

Both constants are module constants with these values. **Lowering either of
them in a consumer repo to turn a FAIL into an UNMEASURABLE is a CLAUDE.md
rule-6 violation** and the record carries the thresholds it actually used so
that such a lowering is visible in the artifact rather than in the diff.

### What UNMEASURABLE means, and what it may never do

* It is **not a PASS**. It never satisfies a gate, it carries no `halt` key,
  and `GateAggregate` counts it as unmeasured.
* It is **not a FAIL**, and it never *downgrades* one: the only inputs it can
  reach are ones where a wall-clock budget was missed while the process was
  demonstrably waiting on a demonstrably loaded machine.
* **It obliges a re-measurement.** It is a statement that this arm produced no
  reading, not that the reading was fine.

## 4. Acceptance rules

The facility ships **only if every one of A1–A6 reads as stated.** If A1 cannot
be made to hold — if a genuine regression cannot be distinguished from
contention — then the classifier is **withdrawn** and only the record-and-report
half ships (capture the evidence, print it beside the result, classify
nothing). A facility that cannot tell a regression from contention must never
be allowed to downgrade a FAIL.

* **A1 — FIRES.** A *genuine* slowdown introduced into the code under test — a
  real `O(n²)` that burns CPU — measured on a **quiet** machine, must classify
  **FAIL**, not UNMEASURABLE, because CPU time tracks wall time (C3 fails).
* **A2 — SILENT-AS-UNMEASURABLE.** The **same test, unchanged code**, under
  synthetic load, whose span waits rather than works, must classify
  **UNMEASURABLE** and carry the contention record that says why.
* **A3 — CHECK-NOT-DEAD.** With the facility removed (the classifier bypassed,
  leaving the bare budget assertion) **and** with its threshold mutated in the
  most permissive direction available (`LOAD_PER_CPU` driven to `0.0`, so C4 is
  satisfied by any machine at all), the **A1 arm still reads FAIL**. A control
  that cannot be broken is not measuring anything.
* **A4 — NEVER A PASS.** No input whatsoever makes `classify` return PASS for a
  missed budget. Asserted over a swept grid of records, not by inspection.
* **A5 — THE PYTEST SURFACE NEVER SOFTENS A VERDICT.** The marker and fixture
  do not convert a failing test into a pass, a skip or an xfail. pytest's own
  verdict is untouched; what the surface adds is the record printed beside it.
* **A6 — LANDING.** Full mlkit suite + `ruff check src tests scripts` +
  `mypy src/resilient_mlkit` on the merged tree against a `main` baseline **in
  one clone**, failure sets **by name**; land only if nothing is
  only-on-branch and lint/type findings stay at zero. Arms run **sequentially**,
  each recording its own contention record.

## 5. The three control arms, named before they are driven

Driven by `scripts/contention_control_drive.py`; output committed as
`reports/CONTENTION_CONTROL_ARMS.json` and read back by a test so the committed
artifact cannot drift from the code.

| arm | code under test | machine | REQUIRED verdict |
|---|---|---|---|
| **FIRES** | a real `O(n²)` loop that burns CPU past the budget | quiet | `FAIL` |
| **SILENT** | unchanged code, a span that waits | synthetic load raised above `cpu_count` | `UNMEASURABLE` + record |
| **NOT-DEAD** | the FIRES arm again, classifier bypassed *and* `LOAD_PER_CPU` mutated to `0.0` | quiet | `FAIL` both ways |

Synthetic load is raised by this drive's **own** child processes, recorded by
PID, and killed by that recorded PID only — never by name pattern.

## 6. Residuals, declared BEFORE measuring rather than discovered afterwards

1. **A sleeping regression on a loaded machine is not distinguishable by this
   record.** `time.sleep(30)` newly introduced into the code under test and a
   30 s wait for a busy CPU produce the same record: near-zero CPU, high load.
   That arm reads UNMEASURABLE, which is **not a pass**, and the protocol
   (§4 A2, `docs/CONTENDED_MEASUREMENT.md`) obliges a re-measurement on a quiet
   machine — where C4 fails and the same code reads FAIL. This is the declared
   price of the load axis, not a defect found later.
2. **The classifier does not model how much slowdown a given load explains.**
   A 1000× overrun at load `1.1 × cpu_count` satisfies C1–C4 and reads
   UNMEASURABLE. Inventing a "load explains N×" formula would be a fabricated
   expected range (rule 2), so none is invented; the record carries
   `budget_ratio` and `load_per_cpu` so a reader can see the pair.
3. **`os.getloadavg()` is a decaying average over the preceding minute.** A span
   much shorter than a minute is judged partly on load that preceded it. Both
   endpoints are recorded; the classifier takes the max, which is the direction
   that declares UNMEASURABLE more readily and is therefore the direction the
   controls must and do police.
4. **`os.times()` counts only children that have been reaped.** A subprocess
   still running when the span closes contributes no CPU, which biases
   `cpu_ratio` down (towards UNMEASURABLE). The pytest surface's own span closes
   after `subprocess.run` returns, which reaps; a caller who does otherwise is
   told so in the docstring.
5. **No sampling.** The record is two instants, not a time series. A span that
   was quiet for 90 % of its length and contended at both ends is recorded as
   contended.

## 7. Rules this lane binds itself to

* Nothing in `tests/`, no threshold, no range and no holdout is edited to make
  a check pass (rule 6). The `120`/`180` s markers in the consumer repos are
  **not** touched by this lane at all: consumer repos rev-pin mlkit and are not
  this lane's to modify. Adoption instructions are written out per repo instead.
* No credential is printed, logged or written (rule 13).
* mlkit PR #45 is not touched.
* Every number in the results file is measured by running the code in this
  clone, with `resilient_mlkit.__file__` asserted to resolve inside it.
