# COMMITTED-READS — results

Answers `reports/COMMITTED_READS_PREREGISTRATION.md`, rule by rule and pair by
pair. Written after the runs it reports; nothing here was decided after seeing
an outcome.

**Authorization:** A-1 — local CPU. Nothing was fitted, no fleet run was made,
and no test arm was read.

**Environment.** `.venv/bin/python` 3.14.6, pytest 9.1.1, macOS (darwin 25.6.0),
branch `feat/loop-mlkit-1` off `main` at `96769ec`.

## The measured runs

| run | command | result |
|---|---|---|
| pre-change baseline, at `96769ec` | `pytest tests/test_fleet.py tests/test_fabricated_defaults.py tests/test_promotion_state.py -q --timeout=180` | **132 passed** |
| post-change, same three files | same command | **132 passed** |
| new controls | `pytest tests/test_committed_reads.py -q --timeout=180` | **20 passed** |
| everything touching a changed module | `pytest tests/test_committed_reads.py tests/test_fleet.py tests/test_promotion_state.py tests/test_fabricated_defaults.py tests/test_version_declaration.py tests/test_nonfinite_controls.py tests/test_ci_workflow.py -q --timeout=180` | **202 passed** |

No full suite was run; a full run is recommended in the PR and not made here.

## The controls, and the mutation that proves each can fire

A control that passes is evidence only if it would have failed. Each mutation
below was applied to the working tree, the new control file was run, the mutant
reverted, and the file re-run clean. Counts are of `tests/test_committed_reads.py`.

| mutation | fails | which |
|---|---|---|
| `load()` reverted to working-tree reads, marker not set (the pre-change behaviour) | **7** | CR1-fires, CR2-fires, CR4-marked-row, CR4-derivation, CR4-absent-column, CR5-working-tree-bytes, CR5-render |
| `refuse_uncommitted()` returns instead of raising | **3** | CR4-resolve, CR4-marked-row, CR4-absent-column |
| the PASS-may-not-be-allow-dirty invariant removed from `CheckResult.__post_init__` | **1** | CR4-PASS |
| `_compare` sets `allow_dirty=False` (launders the marker through the one derived column) | **1** | CR4-derivation |
| — none — | **0** | 20 passed |

### CR-1, the dirty artifact

* **FIRES.** `test_CR1_fires_a_dirty_artifact_does_not_yield_the_working_tree_number`:
  a committed artifact's working-tree copy is rewritten to `74.16097783177521`.
  `ref.dirty` is `True`, `ref.error` carries `not committed at HEAD`, the
  document is never parsed, the score cell is NA, and the string
  `74.16097783177521` appears in neither `row.to_dict()` nor `markdown_table`.
* **SILENT.** `test_CR1_stays_silent_the_same_artifact_clean_reads_the_committed_number`:
  untouched, the same repo returns the committed figure with
  `read_from == "HEAD"` and no error.
* **The mutation form of the same claim.**
  `test_CR1_an_uncommitted_edit_is_invisible_to_the_reader` corrupts the file
  after its commit and shows the committed sha256 unmoved, with a negative
  control asserting the corruption really is on disk — without that line the
  test would also pass against a reader that had stopped reading the file.

### CR-2, present on no ref at all — the E-M12 shape

* **FIRES.** `test_CR2_fires_an_artifact_on_no_ref_is_NA_naming_the_file`: the
  reason contains both `not committed` and the relpath, the cell renders as
  `NA (…)` rather than a value, and the working-tree figure reaches no table.
* **SILENT.** `test_CR2_stays_silent_a_committed_artifact_carries_no_such_reason`:
  no cell of a committed row carries the phrase.
* **Kept distinct.** `test_CR2_an_artifact_in_no_tree_at_all_still_says_where_it_looked`:
  "absent everywhere" still says `artifact not found` and specifically does NOT
  say `not committed at HEAD`. The two findings have different remedies — write
  it, versus commit it — and collapsing them would cost the reader the remedy.

### CR-3, no regression on the ordinary case

* **SILENT.** `test_CR3_a_committed_clean_artifact_loads_byte_identically`
  asserts the sha256 and byte count against `hashlib.sha256` of the file's own
  bytes and the parsed document against `json.loads` of them — the claim is made
  against the file, not against a recorded constant.
* **SILENT.** `test_CR3_a_jsonl_ledger_is_still_parsed_line_by_line`. `_parse`
  switched on `path.suffix`; committed reads hand it bytes and no path, so the
  switch moved to the relpath. A ledger's value is its line count, and a ledger
  parsed as one record would report the wrong one silently.
* **The existing controls.** `tests/test_fleet.py`'s artifact and result control
  pairs pass at the same count as before the change: **132 → 132** on the
  identical three-file command.

### CR-4, an allow-dirty number cannot become a verdict

Four exits, all held:

* `CheckResult.__post_init__` raises on a PASS carrying the marker
  (`test_CR4_fires_a_PASS_carrying_the_marker_cannot_be_constructed`), and
  accepts the identical PASS without it.
* `portfolio.resolve()` raises rather than computing a terminal state
  (`test_CR4_fires_resolve_refuses_a_result_carrying_the_allow_dirty_marker`),
  and resolves the identical unmarked result to `IN-PROGRESS` as before.
* `markdown_table()` and `FleetRow.to_dict()` both raise
  (`test_CR4_fires_a_marked_row_can_be_neither_printed_nor_serialised`) — both,
  because a consumer that cannot print a row will read the same number out of
  the JSON twin.
* The marker survives derivation (`test_CR4_the_marker_survives_derivation`):
  `beats` is arithmetic over two working-tree figures and is still a
  working-tree verdict.

The paired silence that matters most is
`test_CR4_stays_silent_an_unmarked_row_prints_and_serialises`: `allow_dirty=True`
over a CLEAN repo marks nothing and refuses nothing. **The flag is not the
marker.** What marks a row is a read that actually came off the working tree.

### CR-5, the hatch works, outside the verdict path

* **SILENT.** `load(..., allow_dirty=True)` over the never-committed file
  returns its document, its sha256 and its byte count, with
  `read_from == "working tree"`.
* **SILENT.** `Cell.render()` still prints the figure for a human: the marker
  refuses verdicts, not eyes. A marker that blocked rendering would close the
  hatch in fact while leaving it open in the help text.
* **BOTH.** `test_CR5_the_cli_diagnosis_path_prints_and_refuses`: the figure is
  in stdout, the refusal is in stderr, the exit code is **2**, and the output
  contains no `|` — deliberately not the table's shape, so nothing printed here
  can be pasted where a table is expected. `_fleet_diagnosis` is exercised
  directly rather than through `main()` because reading the eight live checkouts
  is not authorised in this iteration.

## What must not change, proven unchanged

sha256 after the change, against the pre-registered baseline:

    e984c8151cc3687fd5fd298b4036984b37afdca002057b02db671ce1832dd104  portfolio/FLEET_VERDICTS.md
    ba3b0ef5d71e2a5f8ac8a5495dd59fa1767e745f6cd336147f53c0b5b312f4a3  portfolio/FLEET_VERDICTS.json
    90a469ab3e820a61b4bfd96b7ab8c2c9d4f7f078421714876c59fd4b53b55943  portfolio/MODEL_QUALITY.md
    2d28b7e66a4d3044e92750342965667a3fc5ddae983a8fcc52e75da1a2c7a77b  tests/test_version_declaration.py

All four identical to the baseline recorded before any edit. `git diff
origin/main -- portfolio/ tests/test_version_declaration.py` is empty.

* **Gate thresholds.** `git diff origin/main -- src/resilient_mlkit/checks/` is
  empty. No check file was opened.
* **`core/result.py`.** The diff is purely additive — `git diff origin/main --
  src/resilient_mlkit/core/result.py` contains no removed line. PASS-requires-evidence,
  NA-requires-reason and the six-status enum are byte-identical; one invariant
  was added beside them.
* **`CHANGELOG.md` retractions.** The `v0.5.0` retraction paragraph and the
  seven-check table are untouched; the new section was appended to the same
  entry. `tests/test_version_declaration.py` passes unmodified (**17 passed**
  within the 202).
* **Version.** `__version__` stays `0.5.0`. No tag was created.
* **The existing control pairs.** `tests/test_fleet.py` gained assertions in two
  controls and a commit step in four; the run count is unchanged at 132 on the
  pre-registered three-file command, and no assertion was deleted or weakened.

## Honest negatives and limits

1. **The choco row was not re-measured, and this report claims no figure about
   it.** `portfolio/FLEET_VERDICTS.md` stands as committed. What the choco row
   will render under committed reads is stated in `CHANGELOG.md` as a
   consequence of the code, not as a measurement, and the re-measurement that
   would make it a measurement is E-M10's and the signatory's.
2. **Nothing was measured about the other seven repos' artifacts.** The
   `16 of 17 resolve` probe is E-M12's, retrieved from `docs/ESCALATIONS.md`,
   not re-run here.
3. **No full test suite was run**, per the compute instruction. The focused runs
   above cover every module this branch changes and every module that imports
   one. A full run is recommended before the tag.
4. **The dirty policy is a choice, and a stricter one than it had to be.** A
   file whose working tree differs from HEAD *could* have been served from HEAD
   and still been reproducible. It is refused instead, on the ground that the
   operator generating the table is at that moment editing away from the figure
   it would print. That is a judgement, it is recorded here as one, and
   `--allow-dirty` exists so that it costs nobody their diagnosis.

## CR-6 — adversarial verification, and two things the first pass got wrong

Added by a verification pass that attacked the claims above by running them,
not by reading them. Everything in the table at the top of this file reproduced
digit for digit (132 → 132, 20, 202). Two findings did not.

### 1. Two of the four "verdict paths" had no producer

The first pass claimed the allow-dirty marker "propagates to every `Cell` …
**and to `CheckResult.evidence[ALLOW_DIRTY_KEY]`**", and counted four refusals.
The propagation to `CheckResult.evidence` does not exist and no code performs
it. `core.artifact` is imported by `core/fleet.py` alone; nothing under
`checks/` imports it; `read_row` is called only by the `portfolio` command,
while `portfolio.resolve()` is fed by `core/store.py`. The fleet reader and the
check pipeline are **disjoint call graphs**.

Measured, by mutation: disabling BOTH `CheckResult.__post_init__`'s marked-PASS
refusal and `portfolio.resolve()`'s, then running every other focused test file
(`test_fleet`, `test_promotion_state`, `test_fabricated_defaults`,
`test_version_declaration`, `test_nonfinite_controls`, `test_ci_workflow`) →
**182 passed**. The only two tests that notice are the two CR-4 controls that
construct `evidence={ALLOW_DIRTY_KEY: True}` **by hand**.

Those guards are kept — the first check that learns to read an artifact will
need them. But they are **forward guards with no producer**, not evidence that
the verdict path is closed, and the docstring that described them as closed has
been corrected in `src/resilient_mlkit/core/artifact.py`. A guard with no
producer presented as a live refusal is the disclosure-shaped error this branch
was written to stop making.

### 2. Two emitters of a figure did not refuse

`markdown_table` and `FleetRow.to_dict` refused a marked row. `provenance_block`
and `counts` did not, and both emit a figure:

* `provenance_block` printed the **sha256 and byte count of working-tree bytes**
  — the column that exists to make a number checkable, naming bytes no reader
  can fetch.
* `counts` returned `cells_measured`, which `cli._render_fleet_markdown` writes
  into the document verbatim as `cells measured: **N**`.

Neither was reachable with a marked row through today's CLI, because
`cmd_fleet` returns into `_fleet_diagnosis` before either runs. That is an
**ordering**, and an ordering is what the next caller changes. Both now call
`refuse_uncommitted`, matching the rationale already written at
`FleetRow.to_dict`: the refusal belongs at the emitter, not at the caller.

Five controls added (`CR6`), each mutation-proven: reverting the two refusals
fails exactly the two FIRES halves; softening the corrected docstring, or making
a `checks/` module import `core.artifact`, fails the reachability control.

### End-to-end, through the real CLI

The first pass exercised `--allow-dirty` through `_fleet_diagnosis()` directly
and recorded that as a limit. It was closed here, against a synthetic root in
the scratchpad (never the live eight checkouts), with an artifact in the exact
E-M12 shape — on disk, on no ref — at `arabica`'s declared path and pointers:

| run | exit | the figure `91919.191919` |
|---|---|---|
| `portfolio --root S` | 1 | absent from stdout |
| `portfolio --root S --json` | 1 | absent from the payload |
| `portfolio --root S --out F.md` | 1 | absent from `F.md` **and** `F.json` |
| `portfolio --root S --allow-dirty` | 2 | in stdout only; no `\|`, nothing written |
| `portfolio --root S --allow-dirty --out G.md` | 2 | **no file created** |
| same artifact, **committed**, `--out` | 1 | **present** — served, as it must be |

The last row is the load-bearing one: the refusal is about commitment, not a
reader that refuses everything.

### Unchanged, re-measured independently

`portfolio/FLEET_VERDICTS.md` `e984c815…`, `.json` `ba3b0ef5…`,
`MODEL_QUALITY.md` `90a469ab…`, `tests/test_version_declaration.py` `2d28b7e6…`
— identical to the values recorded before the change. `git diff main..HEAD` over
`portfolio/`, `src/resilient_mlkit/checks/`, `docs/allowlist.yaml` and
`tests/test_version_declaration.py` is empty. No tag; `__version__` 0.5.0.

## CR-7 — the two guards with no producer now have one

A later pass was asked to decide, per refusal, between wiring a production path
that can reach it and deleting it. Both were WIRED. Neither was deleted.

### Reproducing the deadness first

Measured on this branch before changing anything, with the scanner bound by
`PYTHONPATH` and the binding printed. A stored results file is a real input to
`mlkit check --portfolio`, so both guards were fed one carrying
`evidence={"allow_dirty_read": true}`:

| input | `CheckResult.__post_init__` | `portfolio.resolve()` |
|---|---|---|
| stored PASS + marker | **REFUSED** `UncommittedRead` | — |
| stored FAIL + marker | passes (by design; only PASS is guarded) | **REFUSED** `UncommittedRead` |

So neither guard was broken. Both fire the moment the state is presented. What
did not exist was anything shipped that could present it: `checks/` imported no
artifact reader, and `mlkit check` had no `--allow-dirty` flag to read one with.
The guards were correct code behind an unreachable door.

### What the missing producer turned out to be

`checks/selection.py::_load` read `docs/selection.yaml` with
`Path.read_text()`, and S1–S4 emitted PASS from the working tree. That is the
E-M12 shape — a verdict quoting bytes in nobody's git history — sitting in the
check pipeline of the tool written to refuse it, and it is why `core.artifact`
had no caller there to mark anything. Deleting the guards would have deleted the
only thing that would have caught it.

Wired instead: `_load` reads through `core.artifact.load`, `RunContext` carries
`allow_dirty` from a new `mlkit check --allow-dirty`, `core.artifact._parse`
learned YAML, and every S1–S4 exit carries the marker into evidence through one
`_evidence()` helper. Three arms, all three measured end to end through the real
CLI on a repo whose committed register was edited in place:

| register | flag | S1 | guard |
|---|---|---|---|
| committed, clean | — | PASS | silent |
| committed, clean | `--allow-dirty` | PASS, unmarked | silent |
| edited, uncommitted | — | NA naming the file | n/a — never read for a verdict |
| edited, uncommitted | `--allow-dirty` | **FAIL** `REFUSED (--allow-dirty)` | `result.py`'s |
| edited, uncommitted, failing | `--allow-dirty` | FAIL, marked → stored → `--portfolio` | **`resolve()`'s** |

`_run_phase` now catches `UncommittedRead` explicitly. It was being buried by the
generic handler as "check raised an unhandled exception" over four frames of
traceback, which sends an operator looking for a bug in mlkit instead of
committing their register. Still a FAIL; a refusal is not a pass.

### Blast radius, measured rather than assumed

`docs/selection.yaml` exists in exactly one of the fourteen `resilient-*`
checkouts (blackout), where it is tracked and clean — so its S1–S4 behaviour is
unchanged, and everywhere else `_load` already returned NA for an absent file.

### Controls

Five added (`CR7`), each mutation-proven. Disabling both refusals fails exactly
four tests — the two CR-4 pairs that build evidence by hand and the two CR-7
pairs that reach it through the shipped check — and nothing else. Separately,
reverting `checks/selection.py` to its working-tree read fails four: the
reachability control and the three that depend on a producer existing.

The control that used to assert **no** `checks/` module imports `core.artifact`
is gone. It asserted the deadness, and a control that asserts a guard is
unreachable protects the unreachability. Its replacement,
`test_CR7_the_two_check_pipeline_guards_have_a_producer`, asserts the inverse
and names which guard goes dead if the producer is removed.
