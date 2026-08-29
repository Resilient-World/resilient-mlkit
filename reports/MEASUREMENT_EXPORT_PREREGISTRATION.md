# Pre-registration — the exported measurement primitive, and torrent's model of record

Written and committed **before** the module, the tests or the regeneration
below existed, so the commit order shows the rule preceding the result. Branch
`feat/loop-mlkit-4`, off `main` at `0b29e63`.

Authorization A-1: local CPU only. Nothing is fitted, no cloud call, no spend.

## Two changes, both inside mlkit

### MEASUREMENT-EXPORT — the repo-facing primitive that has been copied instead of imported

`src/resilient_mlkit/core/result.py` is the canonical definition of what a
verdict may claim: six statuses, a mandatory reason on every non-PASS, a PASS
that cannot exist without evidence, and a PASS that cannot rest on an
`--allow-dirty` read. Three repos need that vocabulary at gate sites and none
of them import it. They carry hand-written copies:

* `resilient-blackout` `resilient_blackout/validation/unmeasured.py`
  (`Unmeasured`, `GateUnmeasured`, `MetricUnmeasured`, `ValidationUnmeasured`,
  `EstimateResult` — three states)
* `resilient-triage` `src/resilient_triage/measurement.py`
  (`GateUnmeasured`, `Status`, `Measured` — three states)
* `resilient-choco` `src/registry/promotion_gate.py` and
  `src/validation/_report.py` — the design both of the above say they mirrored

The copies have already diverged from each other and all three have collapsed
the six states into three. `core/result.py`'s own docstring states the cost of
that collapse: DEFERRED exists because folding it into NA "makes the portfolio
lie in the expensive direction" — "the dataloader raises ImportError" and "the
dataloader runs, reaches the API, and needs a key" are not the same distance
from a training run, and a table that renders them identically cannot answer
the only question the portfolio is for.

mlkit currently offers no public surface a repo can import to get that
vocabulary. `resilient_mlkit/__init__.py` exports `CheckResult`, `Status` and
`CredentialRequired`; `CheckResult` is shaped for a *portfolio check* — it
requires a `check_id` and a `phase` and lands in `.mlkit/results/` — not for a
*gate inside a repo's own validation code*, which is the shape all three copies
took. So the copies are not laziness; there was nothing to import.

**The change.** Add `src/resilient_mlkit/measurement.py`: a public,
repo-facing module exposing the `Measured` / `Unmeasured` gate vocabulary the
copies use, carrying the canonical **six-state** `Status` re-exported from
`core.result` — not a fourth definition of it. Every constructor delegates to
`core.result.CheckResult`'s own named constructor, so the exported surface
cannot drift from the canonical one without the equivalence test below
failing.

**Purely additive.** No existing check, threshold, gate file or `Status`
semantic changes. Nothing in `core/`, `checks/` or `portfolio.py` is edited.
The other three repos are **not** edited this iteration: blackout and triage
carry open colleague PRs, and choco has one too. Convergence is by import in a
later iteration; this change makes the import exist and names the three copy
sites in the module docstring so the later iteration has one place to look.

### TORRENT-RECORD — a stale `Absent` reason that is no longer true

`src/resilient_mlkit/fleet_adapters.py:190,233` declares torrent's
`model_of_record` column `Absent`, with the recorded reason that no committed
JSON artifact in resilient-torrent declares a model of record and that "the
ridge is named as the record in prose only".

That reason has expired. `resilient-torrent` `main` now carries
`models/hydrology_ridge/model.json` (verified read-only on 2026-08-29 with
`git -C resilient-torrent cat-file -e main:models/hydrology_ridge/model.json`
and `HEAD:` likewise — present on both; `HEAD` is `main` at `c597cc5`). It
records `served_model`, `promoted_at`, the coefficient sha256 it pins, and
`path_reemission.check_id: TORRENT-L4-PATHS`. mlkit already knows this file
exists — `scripts/verify_served_hash_parity.py` names it explicitly as one of
the three sidecar-pinned champions.

An `Absent` whose reason is false is worse than a missing column: it is a
written claim about another repo that a reader has no reason to re-check.

**The change.** Declare a `record` artifact on both torrent adapters and point
`model_of_record` at `record:served_model`. Nothing else in either adapter
moves. `served_model` and not `name` because `served_model` is the identifier
the other torrent artifacts already use for the same object — it is verbatim
the `left.name` of `row_parity_ridge_vs_melstm_val.json`, which is the bar the
second row's network is measured against.

## Controls — each must fire, and must stay silent on the legitimate case

A check with only one half of a pair measures nothing. Both halves are
required, and each state is asserted separately rather than in a loop whose
failure would name no state.

### The primitive

| # | Forced condition | Required outcome |
|---|---|---|
| MX-1 | `Measured.unmeasured(reason=…)` | `passed is False`, `status is Status.NA` |
| MX-2 | NA constructed with an empty reason | raises `FabricationError` |
| MX-3 | PASS constructed with no metrics | raises `FabricationError` |
| MX-4 | PASS whose metrics carry the `allow_dirty` marker | raises `UncommittedRead` |
| MX-5 | `render()` of all six states | six pairwise-distinct strings; each state asserted in its own test, and no non-PASS rendering may begin with `PASS` |
| MX-6 | every one of the six states, parametrized | the exported surface's status, reason and passed-ness agree cell-for-cell with the same construction through `core.result` |
| MX-7 | **silence** — a legitimate PASS with metrics | constructs, `passed is True`, `to_result()` is a `CheckResult` with `Status.PASS` |
| MX-8 | **silence** — `Status` is the same object as `core.result.Status` | identity, not a copy: `measurement.Status is core.result.Status` and `len(Status) == 6` |

MX-6 is the adoption-parity discipline of
`scripts/verify_served_hash_parity.py` applied in miniature: that script exists
because adopting a shared contract must not silently redefine an identity a
repo already recorded. Here the identity is a verdict.

### The adapter

| # | Forced condition | Required outcome |
|---|---|---|
| TR-1 | the torrent `record` artifact repointed at a path that does not exist | `model_of_record` is NA, and the NA reason names the missing path — no default, no previous value |
| TR-2 | the pointer repointed at a key the artifact does not carry | NA naming the pointer |
| TR-3 | **silence** — resolution against the real committed `models/hydrology_ridge/model.json` | `model_of_record` measured, value `ridge_with_observed_discharge`, provenance naming the file |
| TR-4 | **silence** — regenerate the whole fleet table with mlkit's own runner before and after the adapter edit, same moment, same checkouts | the only cells that differ are torrent's two `model_of_record` cells |

TR-3 reads a real sibling repo, so it is skipped rather than failed when the
checkout is not present — a test that silently passes on an absent repo is the
defect this suite has shipped before, so the skip must be explicit and must
name the path it looked for.

## Predictions, recorded before the run

1. TR-4's before/after diff touches torrent's two `model_of_record` cells and
   the torrent provenance rows that gain the new `record` artifact. **No other
   repo's cell moves.**
2. The regenerated table will nonetheless differ from the committed
   `portfolio/FLEET_VERDICTS.md` in many non-torrent cells, because the eight
   checkouts have moved since that file was generated (it records arabica at
   `feat/observed-panel-and-fabrication-gates`, blackout at `e021-decision`,
   triage at `e028-decision`; most are now on `main`). That drift is not
   attributable to this change, which is why the before/after pair is measured
   at one moment against one set of checkouts rather than against the committed
   file.
3. Because of prediction 2, **`portfolio/FLEET_VERDICTS.md` is not overwritten
   in this change.** Overwriting it here would bundle ten unrelated cell
   movements into a PR about a measurement primitive, and would break
   `tests/test_fleet.py::test_the_declared_branches_match_the_committed_provenance_table`,
   which holds `BRANCH_ONLY_EVIDENCE` against the branch column of that
   committed table. Regenerating it is its own change, with its own reading of
   what moved and why; it is escalated in `docs/ESCALATIONS.md` rather than
   done as a side effect here. If prediction 2 turns out false — if the
   regenerated table differs from the committed one only in torrent's cells —
   then the file is regenerated in place and this paragraph is the record of
   the rule that decided it.

## Falsification — what would make this work wrong

* If the exported primitive had to weaken any rule in `core/result.py` to be
  usable at a repo gate site, the export is wrong and the finding is reported
  rather than tuned around. Thresholds, gates and holdouts are not touched
  (CLAUDE.md rule 6).
* If `models/hydrology_ridge/model.json` turned out not to be committed on
  torrent's `main`, TORRENT-RECORD is abandoned and the existing `Absent`
  stands — a stale reason is repaired by measurement, not by a better-sounding
  reason.
* If the before/after regeneration moved a non-torrent cell, the adapter change
  is reverted and the movement is the finding.

## Must not change, captured before the work

| File | sha256 at `0b29e63` |
|---|---|
| `src/resilient_mlkit/core/result.py` | `54860a0e968019ac444c70b7f056bfccdac3107fcfd2522adae1fc258bceeb14` |
| `reports/R12_RESULTS.md` | `904b5fa94018f044dc50c020ded836faa6e339367927e3c6798de76b484f7289` |
| `portfolio/FLEET_VERDICTS.md` | `e984c8151cc3687fd5fd298b4036984b37afdca002057b02db671ce1832dd104` |
| `portfolio/FLEET_VERDICTS.json` | `ba3b0ef5d71e2a5f8ac8a5495dd59fa1767e745f6cd336147f53c0b5b312f4a3` |

The 133 pre-registered control pairs of
`reports/CONTROL_PAIR_RESULTS.md` are re-run at the end and must still be 133
passing. No test expectation in this suite is edited.
