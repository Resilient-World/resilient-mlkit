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
