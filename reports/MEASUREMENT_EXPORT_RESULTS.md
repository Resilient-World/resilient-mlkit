# Results — the exported measurement primitive, and torrent's model of record

Answers `reports/MEASUREMENT_EXPORT_PREREGISTRATION.md`, committed `9ee3a35`
before the module, the tests or the regeneration existed. Branch
`feat/loop-mlkit-4`, off `main` at `0b29e63`.

Authorization A-1: local CPU only. Nothing was fitted, no cloud call, no spend,
no GPU. No test arm was read in any repo — every figure below comes from a
committed artifact or from a pure-Python fixture in a `tmp_path`.

## Provenance

Measured with `.venv/bin/python -m pytest <file> -q --timeout=180` on
Python 3.14.6, pytest 9.1.1, `resilient-mlkit` 0.5.0. The fleet regeneration
was run with this repo's own `.venv/bin/mlkit portfolio --out …`. There is no
seed to record: nothing here is stochastic.

| File | sha256 |
|---|---|
| `src/resilient_mlkit/measurement.py` | `79820f3b09d7b9b032b4b7db41c9d077645aae45e257362f69a4200107341f42` |
| `tests/test_measurement_primitive.py` | `c2693da1b1d231d449306ae68a502c17f8be83ea401c222a8fdcf8e93f44599c` |
| `tests/test_torrent_model_of_record.py` | `3d3a41cfa5bdc09a4a9fbdc0fd8cd8e56db627116ae3c18d75b63c74ba247df4` |
| `src/resilient_mlkit/fleet_adapters.py` | `ac2864a3d476955a51b00da0c9f66ac40eee15ff4df477b02e8e60f692a84000` |

| Suite | Result |
|---|---|
| `tests/test_measurement_primitive.py` | **35 passed** |
| `tests/test_torrent_model_of_record.py` | **8 passed** |
| the 133 pre-registered control pairs (5 files) | **133 passed** in 12.83 s — unchanged |
| regression set: `test_fleet`, `test_committed_reads`, `test_promotion_state`, `test_version_declaration`, `test_derivation` | **129 passed** |

`ruff 0.16.5` and `mypy 2.3.1` clean on every file this branch touches. Two
`ruff` findings and one `mypy` finding stand in
`src/resilient_mlkit/core/served_reimplementation.py`; both predate this branch
and neither file is touched here.

No full suite was run. Recommended before merge, not run here:
`.venv/bin/python -m pytest -q --timeout=180`.

## MEASUREMENT-EXPORT — what the controls found

`src/resilient_mlkit/measurement.py` is new and additive. Nothing in `core/`,
`checks/` or `portfolio.py` was edited.

| # | Control | Result |
|---|---|---|
| MX-1 | `Measured.unmeasured(...)` | `passed False`, `status NA`, `value None`; assigning `passed` raises `AttributeError` — the state cannot be spelled, not merely corrected |
| MX-2 | NA with a blank reason | `FabricationError`, "requires a reason"; **silent** on an NA that carries one |
| MX-3 | PASS with no metrics | `FabricationError`, "PASS requires evidence"; **silent** on a PASS with metrics |
| MX-4 | PASS whose metrics carry `allow_dirty_read` | `UncommittedRead`; **silent** — an NA may still record the marker, which is what makes the NA correct |
| MX-5 | rendering | all six statuses render pairwise-distinct, each asserted in its own test; only PASS leads with `PASS`; `to_dict` keeps `unmeasured_reason` off a PASS |
| MX-6 | equivalence over all six statuses | status, reason, metrics and passed-ness agree cell-for-cell with the same construction through `core.result`, and `to_result()` round-trips into a real `CheckResult`. A coverage test fails if a seventh status is ever added without extending the battery, and a negative control proves the comparison can distinguish two statuses rather than comparing an object with itself |
| MX-8 | `Status` identity | `measurement.Status is core.result.Status`, six members, in order. Not a copy that agrees — the same object |

The honest part of MX-6: the equivalence is **structural, not coincidental**.
Every constructor in the new module calls `CheckResult`'s own named constructor
and reads the result back, so there is no second implementation to drift. The
battery is there to keep a future edit from introducing one.

### What adopting this would change at the three copy sites

Recorded because "purely a rename" would be a claim, and it is false. Stated in
full in the module docstring:

* a PASS must carry evidence — none of the three copies enforces that;
* NA keeps its metrics (triage's copy drops them), while the gate's own figure
  is `None` either way;
* reasons are redacted and length-bounded by `core.result.redact`;
* `passed` is derived from the status rather than passed in and corrected.

**No repo was edited.** blackout (#129), triage (#94) and choco (#160) all
carry open colleague PRs; convergence is the owning repo's change, and this
branch only makes the import exist.

## TORRENT-RECORD — the two NA cells

`resilient-torrent` `models/hydrology_ridge/model.json` verified read-only on
2026-08-29 with `git cat-file -e main:<path>` and `HEAD:<path>` in that clone —
no checkout, no fetch, nothing written. Both resolve, and the blob is
byte-identical on both refs (sha256
`c93f50d40c7e9140d876cf61cec56b0c00e7bba207d670c10480786d3b6f8507`, 6,969
bytes), so the reading does not depend on which branch that repo happens to
have out.

| # | Control | Result |
|---|---|---|
| TR-1 | `record` artifact repointed at a path that does not exist | NA, reason names `models/no_such_record/model.json` |
| TR-2 | pointer repointed at `record:champion_id`, a key the artifact does not carry | NA, reason names the pointer |
| TR-1n | **silent** — same fixture, same adapter, nothing repointed | measured, `ridge_with_observed_discharge` |
| TR-3 | **silent** — the two real rows against the committed artifact | both measured, both `ridge_with_observed_discharge`, source `models/hydrology_ridge/model.json#served_model`; and the value equals the `left.name` the row-parity artifact already uses for the same object |

The declared-pair probe was re-run over all distinct `(repo, path)` pairs the
adapters name: **18 pairs, 17 resolve on the ref their note implies.** The one
that does not is choco's `main` artifact, which is E-M12 and unchanged here.

### TR-4 — the before/after regeneration

Both arms run with this repo's own `.venv/bin/mlkit portfolio`, back to back,
against one identical set of checkouts. The arms differ only in
`src/resilient_mlkit/fleet_adapters.py`: the "before" arm is `git show
main:…fleet_adapters.py` restored into place for the duration of that run.

`repos_read` is **identical** between the two payloads, which is the control
that makes the comparison mean anything — the sibling repos in this working
copy are being actively worked on and moved between two earlier attempts; the
attempt recorded here was re-run until the repo-state table matched across the
arms, and the match is asserted in `CELL_DIFF.txt`.

**Result: 2 cells moved. Both are torrent's `model_of_record`. Zero non-torrent
cells moved.**

| row | column | before | after |
|---|---|---|---|
| `torrent/melstm-10ep-n8-val` | model of record | NA — "no committed JSON artifact in resilient-torrent declares a model of record…" | `ridge_with_observed_discharge`, from `models/hydrology_ridge/model.json#served_model` |
| `torrent/ridge-vs-melstm-val` | model of record | NA — "…see the melstm-10ep-n8-val row" | `ridge_with_observed_discharge`, same source |

Counts: `cells_measured` 95 → 97, `cells_na` 13 → 11, rows unchanged at 12.
Two provenance rows are added, one per torrent entry, for the new `record`
artifact. Artifacts:

| File | sha256 |
|---|---|
| `reports/fleet_verdicts_torrent_record/BEFORE_FLEET_VERDICTS.md` | `47a777420cb2b6b6f9dee8390c3ce0f7d0eaa294e65b1efb217211747b724705` |
| `reports/fleet_verdicts_torrent_record/BEFORE_FLEET_VERDICTS.json` | `65f4da35cbdf5ea965fdc9ae97925f5fd0adbc2c7b6232a795e60da158549c57` |
| `reports/fleet_verdicts_torrent_record/AFTER_FLEET_VERDICTS.md` | `fab211bd8b0c49f17be4ea810ffaa4333a532d0866aa97abf32d967a0b28d892` |
| `reports/fleet_verdicts_torrent_record/AFTER_FLEET_VERDICTS.json` | `a4e939879b224af3fae7415a7a5604a0c6505be88d4f35d1574507d3be532259` |
| `reports/fleet_verdicts_torrent_record/CELL_DIFF.txt` | `87f0d38e010ba11134bdbf493dce8994d05dcc4fdb38dad21a05706e4cd83a49` |
| `reports/fleet_verdicts_torrent_record/TABLE.diff` | `def4dd1ab5e04dea9be3b103aa96188fbd907a4329772b2ea570ade6057a7146` |

## The prediction that held, and what it cost

Prediction 2 of the pre-registration held, and it is the honest negative of
this branch. `portfolio/FLEET_VERDICTS.md` **was not regenerated in place**,
and the DONE condition that asked for it is therefore only partly met: the
regenerated table lives under `reports/`, not at `portfolio/`.

Measured, comparing each cell's `value` between the committed payload and a
regeneration today: **twelve cells differ. Two are this branch's repair. Ten
were moved by the world** — six choco cells to NA (E-M12), two blackout
`model_of_record` cells to NA (the gate artifact is not on the branch that repo
now has out), and two torrent `test_arm_spent` cells from 1 to 5 because
torrent's holdout ledger grew from 754 to 36,787 bytes. Measured coverage falls
103 → 97.

Writing that table here would have done two things this branch has no business
doing: bundling ten unrelated movements into a change about a measurement
primitive, and breaking
`tests/test_fleet.py::test_the_declared_branches_match_the_committed_provenance_table`,
which holds `BRANCH_ONLY_EVIDENCE` against the committed table's branch column.
The second is not a test to edit — it would be failing *correctly*, because the
adapter notes were written for `e021-decision` and `e028-decision` and both
repos have moved. Fixing it means re-measuring where blackout's and triage's
evidence now lives, in two repos with open colleague PRs.

Recorded as `docs/ESCALATIONS.md` **E-M15**, with the regeneration recommended
as its own deliberate commit. `E-M03` is closed for torrent and left open for
blackout.

## Must not change — proven unchanged

| File | sha256 before | sha256 after | verdict |
|---|---|---|---|
| `src/resilient_mlkit/core/result.py` | `54860a0e968019ac444c70b7f056bfccdac3107fcfd2522adae1fc258bceeb14` | same | unchanged |
| `reports/R12_RESULTS.md` | `904b5fa94018f044dc50c020ded836faa6e339367927e3c6798de76b484f7289` | same | unchanged |
| `portfolio/FLEET_VERDICTS.md` | `e984c8151cc3687fd5fd298b4036984b37afdca002057b02db671ce1832dd104` | same | unchanged |
| `portfolio/FLEET_VERDICTS.json` | `ba3b0ef5d71e2a5f8ac8a5495dd59fa1767e745f6cd336147f53c0b5b312f4a3` | same | unchanged |

No check threshold, gate file, holdout or `Status` semantic was edited. No test
expectation in this suite was edited; the 133 pre-registered control pairs
still pass, still 133. No CI, IAM, billing or cost-incurring action was taken —
those are the signatory's (CLAUDE.md rule 12). No model repo was written to.

---

## Addendum — adversarial verification, 2026-08-29 (VERIFY-MX9, VERIFY-MX10)

This branch was re-verified by running, not by reading. Every figure above
reproduces digit for digit: all 14 sha256s in this document, the CELL_DIFF
(2 cells moved, both `torrent/model_of_record`, **non-torrent cells moved: []**,
95 → 97 measured, 13 → 11 NA, 12 rows, `repos_read` identical between arms),
the 18 declared `(repo, path)` pairs (14 on `main`, 17 on some ref, choco's
the one that resolves nowhere), torrent's record artifact
(`c93f50d40c7e…`, 6,969 bytes, byte-identical on `main:` and `HEAD:`,
`served_model` == `row_parity_ridge_vs_melstm_val.json` `left.name`), and the
four protected files. The 133 pre-registered control pairs and the 129-test
regression set were re-run **at the branch point with `PYTHONPATH` forced at
that tree** — 133 and 129 there, 133 and 129 here.

Verification found two defects in `measurement.py` and fixed them in commit
`230c6a9`; both are additive tightenings inside the new module.

1. **VERIFY-MX9.** `passed` is read-only, but `Measured` is a mutable
   dataclass: `na.status = Status.PASS` produced an evidence-free PASS
   carrying the NA's reason, reaching `passed`, `render()` and `to_dict()`
   without meeting one refusal. `__setattr__` now re-validates through
   `CheckResult` before the write lands. In-place mutation of the metrics
   dict remains outside the guard and is now stated in the docstring rather
   than implied away.
2. **VERIFY-MX10.** `gate_description` and `notes` are fields this module
   adds, do not exist on `CheckResult`, and reached `to_dict()` unredacted —
   against the docstring's claim that adopting it retires rule 13 for a gate's
   free text. Both are redacted at construction now.

Six control pairs were added (MX-9 ×4, MX-10 ×2) and proved non-vacuous: run
against `637e3be`'s `measurement.py` with `PYTHONPATH` forced at that tree,
the four FIRES fail and the two negative controls pass.

Superseding the two file digests in the table above, which the fix moved:

| File | sha256 at `230c6a9` |
|---|---|
| `src/resilient_mlkit/measurement.py` | `b037caa6b2f1b2d35ee70d284427ba8aeec0cbb42e12545c12ab9202b67aa0f3` |
| `tests/test_measurement_primitive.py` | `2377c4ba50619fb3e1761f21c34f94ff11bb421d380dffb4e3d7ca4b2098d1bf` |

`tests/test_measurement_primitive.py` is now **41 passed** (35 + 6);
`tests/test_torrent_model_of_record.py` is unchanged at **8 passed**. The four
protected files are still byte-identical to `main`, re-measured after the fix.
