# Measuring on a machine somebody else is using

**This is the fleet's rule, not advice.** It is written to be read by an agent
under deadline pressure, so every clause says what to DO and what is FORBIDDEN,
and none of it depends on judgement about how busy is busy.

Instrument: `resilient_mlkit.core.contention`. Pytest surface:
`resilient_mlkit.pytest_contention`. Preregistration and driven controls:
`reports/CONTENTION_PREREGISTRATION.md`, `reports/CONTENTION_CONTROL_ARMS.json`,
`reports/CONTENTION_RESULTS.md`. Escalation: `docs/ESCALATIONS.md` **E-M40**.

---

## 1. The rule

> **Suite arms for a by-name comparison are run SEQUENTIALLY, never
> concurrently. Each arm records its contention record. A by-name comparison
> between arms run at materially different load is VOID and must be
> RE-MEASURED, not explained.**

"Materially different" is not left to taste. Two arms are at materially
different load when either arm's 1-minute load average is at or above
`LOAD_PER_CPU × cpu_count` (one runnable process per core — the default is
`1.0`, so on a 10-CPU host that is load 10) and the other's is not.

"Re-measured, not explained" means: run the arm again on a quiet machine and
report THAT reading. It does not mean writing a paragraph about why the failure
was probably contention. A paragraph is not a measurement.

## 2. The worked example this rule is made of

**resilient-choco, 2026-09-06.** The suite was run twice **on the same tree** —
the new `main` at `a2e85c2`, whose tree is byte-identical to #184's head tree
`1246ece5`, verified as the same git object. Two runs of one tree can differ by
nothing.

```
run 1   wt-184      tree 1246ece5   7 failed, 1230 passed   (1:02:34)
run 2   wt-newmain  tree 1246ece5   8 failed, 1229 passed   (0:56:18)

failure names differing between two runs of the IDENTICAL tree: 5
  only in run 2: test_api_scenario_online.py::test_online_update_latency_under_5ms
                 test_attrici_counterfactual.py::test_fast_counterfactual_removes_trend
                 test_typing_ratchet.py::test_mypy_strict_module[api.schemas]
  only in run 1: test_api_scenario_online.py::test_10k_shift_coverage_gate
                 test_cqr.py::test_cqr_end_to_end_coverage_on_synthetic_panel
```

**The flake floor of that suite on that host was FIVE NAMES.** The
`main`-vs-#184 difference that the landing decision rested on was THREE names —
*smaller than the churn of one tree against itself*. Every differing name was a
`pytest-timeout` at the 120/180 s boundary or a latency assertion. None was a
semantic assertion.

Two conclusions, and the second is the one agents get wrong:

1. A by-name difference smaller than the measured flake floor is **not
   evidence**. Measure the floor before trusting a difference near it.
2. The right response to a difference at the boundary is to **re-drive the
   differing node ids on both trees** — which choco did, and which flipped the
   direction of all three.

Three more instances of the same defect, all 2026-09-06:

* **mlkit** (this repo). `test_positive_control_a_sleeping_test_fails_on_timeout`
  gives a child pytest **10 s of wall time**. Under three concurrent suites the
  arm took **1196.12 s** against a normal **635.75 s** and that test read rc 1 —
  which would have blocked landing PR #54. Re-run quiet: **1307 passed, rc 0, in
  101.02 s**. What dated the cause was the same file's **negative** control
  failing in the neighbouring arm: *a fast test cannot be made slow by a source
  change.*
* **resilient-torrent.** A 79-minute "stall" at 70 % and a "hung" readiness
  regeneration both vanished at low load; the suite runs in 13.6 minutes quiet.
* **resilient-arabica.** A three-stream parallel plan produced a phantom
  timeout failure — a test that shells out with a 120 s budget and takes 36 s
  alone. It was discarded and re-run uncontended.

## 3. What the instrument gives you, and what it refuses to give you

`core.contention.classify(record)` returns exactly one of:

| verdict | when | what it obliges |
|---|---|---|
| **PASS** | the budget was met | nothing |
| **FAIL** | the budget was missed and **either** the process was burning CPU **or** the machine was quiet | fix the code |
| **UNMEASURABLE** | the budget was missed **and** the process was waiting (`cpu_ratio ≤ 0.5`) **and** the machine was loaded (`load1 ≥ 1.0 × cpu_count`) | **re-measure on a quiet machine** |

**UNMEASURABLE is not a pass.** It satisfies no gate, carries no `halt` key,
and the portfolio reads it as unmeasured. It is a statement that this arm
produced no reading — not that the reading was fine.

**UNMEASURABLE never downgrades a FAIL.** The only records it can reach are
ones where a declared wall-clock budget was missed while the process was
demonstrably waiting on a demonstrably loaded machine. It is unreachable from
an assertion about a number: `Status.UNMEASURABLE` is produced here only via
`WallClockBudget`, which cannot exist without a positive budget declared before
the span ran.

**The thresholds may only be moved toward strictness.** `WallClockBudget`
refuses a lowered `load_per_cpu` or a raised `max_cpu_ratio` by name, citing
CLAUDE.md rule 6, and every record carries the thresholds it was judged
against — so a fork that forced them by editing `core/contention.py` is visible
in the artifact and not only in a diff.

### The residual you must know before you use it

**A sleeping regression on a loaded machine is not distinguishable from
contention by this record.** A newly introduced `time.sleep(30)` and a 30 s wait
for a busy CPU look the same: no CPU burned, high load. That arm reads
UNMEASURABLE — and the obligation UNMEASURABLE carries is exactly what closes
the hole: re-measure on a quiet machine, where the load condition fails and the
same code reads **FAIL**. The four other declared residuals are in
`core/contention.py`'s module docstring and in the preregistration §6.

## 4. The pytest surface

```python
# conftest.py — the whole adoption
pytest_plugins = ["resilient_mlkit.pytest_contention"]
```

or `-p resilient_mlkit.pytest_contention` on the command line. There is **no
`pytest11` entry point**, deliberately: all eight repos install mlkit, and an
entry point would register this in all eight on the next lock — an instrument
change arriving as ambient drift.

What you get:

* **`@pytest.mark.wall_clock_budget(seconds)`** — declares that this test's
  assertion is a wall-clock budget. The plugin measures the test's setup+call
  span and attaches the contention record to the report and to
  `user_properties` (so JUnit XML carries it).
* **the `wall_clock_budget` fixture** — for a test that wants the span around a
  specific block:

  ```python
  def test_child_pytest_is_bounded(wall_clock_budget):
      with wall_clock_budget(10.0, "child pytest run") as span:
          proc = subprocess.run(argv, timeout=10)
      assert proc.returncode != 0, span.record.one_line()
  ```

* **a session contention line at the top AND the bottom of the log.** The top,
  because a run that is killed never reaches the summary — and a killed arm is
  exactly the one somebody needs to date later.

**The plugin never changes pytest's verdict.** Not to a pass, not to a skip,
not to an xfail. A failing budget test fails. This is asserted by execution:
`tests/test_contention_pytest_surface.py` runs the same file with and without
the plugin, under identical configuration, and requires the exit codes to
match. The reason is blunt — a skip exits 0, and the fleet's landing rule
("nothing only-on-branch") would then read a real regression on one arm against
a skip on the other and see agreement.

## 5. Two facts about pytest-timeout that cost a day

Both measured 2026-09-06. Neither is discoverable by reading a config file.

* **A test file's own `@pytest.mark.timeout(120)` BEATS `--timeout` on the
  command line.** choco's `tests/test_agrifm_cocoa_training.py::test_synthetic_training_exports_checkpoint`
  carries a 120 s marker; raising `--timeout` on the runner did nothing for it,
  and two suite pairs died at 17 % before the precedence was understood. A
  marker is a per-test declaration; the flag is a default, and the default
  loses. **So a runner-level accommodation silently does not apply to the test
  that most needs it.**
* **`timeout_method = "thread"` cannot bound a hang that holds the interpreter
  lock.** In torrent a 180 s per-test timeout did not fire on a torch section
  that held the GIL for 79 minutes; the timer thread cannot run. What fired was
  `faulthandler_timeout`, which DUMPS and does not kill. Under `signal` the
  timeout raises inside the test, so it becomes **one named failure** instead of
  a truncated session — which is also what makes failure sets comparable by
  name.

**The permitted repair and the forbidden one.** Changing the timeout METHOD
(`-o timeout_method=signal`, `-o faulthandler_timeout=0`) is a change to the
REPORTING MECHANISM: it selects no test, changes no assertion, and leaves every
declared threshold in force. Applying it identically to every arm is allowed and
is what choco did. Changing the 120 s or 180 s THRESHOLD, or deleting or
xfailing the test, is a **rule-6 edit to a committed gate and is forbidden**.

## 6. The procedure, as steps

1. **One clone per comparison.** Never `git checkout --detach` in a clone
   another process is measuring. On 2026-09-06 a killed leg's pytest child was
   reparented to PID 1 and went on running against a tree that had been checked
   out from under it, while still labelled with the other arm's name; both arms
   were contaminated and both had to be re-driven.
2. **Assert the binding first.** Print the package's `__file__` at the head of
   every arm's log and confirm it resolves inside the clone being measured.
3. **Run arms one at a time.** Record each arm's contention line. Do not start
   arm B while arm A is running, and do not start either while another lane is
   running a suite on the same host.
4. **Compare failure sets BY NAME**, never counts.
5. **Before trusting a small by-name difference, measure the flake floor**: run
   one arm's tree twice and diff those two failure sets. A difference no larger
   than the floor is not evidence (choco: floor 5, difference 3).
6. **Re-drive every differing node id on both trees.** A difference that flips
   direction on re-measurement is a host artefact.
7. **If the arms ran at materially different load, the comparison is VOID.**
   Re-measure. Keep the contended log — do not delete it — and label it, as
   `logs/pytest.pr2.loaded-machine.log` was.
8. **Never kill by name pattern.** Kill only a PID you recorded at launch. On
   2026-09-06 a wait loop of the form `until ! pgrep -f "<pattern>"` matched the
   waiting shell's own command line and deadlocked, and the cleanup that
   followed killed another lane's suite leg because its driver was named
   `run-arm.sh` and the pattern was `-arm.sh`.
