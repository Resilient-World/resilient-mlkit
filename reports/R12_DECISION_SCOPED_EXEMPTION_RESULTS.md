# R12 — THE SERVED-CONTRACT EXEMPTION, SCOPED TO THE DECISION — RESULTS

**Driven 2026-09-06 against `reports/R12_DECISION_SCOPED_EXEMPTION_PREREGISTRATION.md`
(commit `c12c5cd`, the first commit of this branch, written before any source
change).** Driver: `scripts/r12_decision_scoped_drive.py`, committed before the
change so the before-drive and the after-drive are the same code on the same
shapes.

Builds, so no figure here is attributable to "some mlkit":

| side | build stamp |
|---|---|
| before — `main` `1d9df13` | `0.7.0+src.8dd1b5f6046d` |
| after — this branch, as landed | `1.0.0+src.2de05d676b69` |

The first after-drive ran at `0.7.0+src.4a17b84cb853`, before the version bump
this document's own measurement then justified. The artifacts were RE-DRIVEN on
the final tree rather than restamped, and every row is byte-identical between
the two; only the stamp moves. The `r12_served_contract` verdicts in A5 were
taken at the earlier stamp and are unaffected — the rows they count are the same
rows.

Clones, all fresh from the remote on 2026-09-06:

| repo | head |
|---|---|
| `resilient-torrent` | `39977c66327716ad860177c6279780736171c5b1` |
| `resilient-fray` | `5440702ca861a34b11db64e7571d1835f264c22e` |
| `resilient-chokepoint` | `ddb87faf2b4f1d44f70350657e9b3e27d51d169e` |

---

## A1 / A2 / A3 — E-079's three shapes, reproduced and then repaired

Whole-repo scans of `resilient-torrent`, 597 files walked in every row.
`reports/R12_DECISION_SCOPED_{BEFORE,AFTER}.json` carry the machine record.

| shape | before | after |
|---|---|---|
| **A** the defect as authored — a local `D6_DECIDING_ARM = "val"`, no `core.served` name in the file | 1 | 3 |
| **B** the repair — the arm obtained through `ServeArms.require` | 0 | 2 |
| **C** the repair PLUS the constant restored AND USED, helper left dead | **0** | **3** |

**E-079's table reproduces exactly on the before side (1 / 0 / 0), nine months
of drift later and in a different clone.** The row that matters is C, and the
row inside C that matters is `mlkit_bindings.py:2854 SERVE_ARM
D6_DECIDING_ARM` — absent before, present after. That is A1.

A2 and A3 are the same rows read the other way. Shape B does not report
`D6_DECIDING_ARM` in either drive: **the repair torrent actually shipped stays
silent**, which is the property that had to survive. Shape A reports it in
both.

The two extra rows every after-column carries are **not** the shape under test:
they are `scripts/hydrology/run_operational_information_set.py:88 ARMS` and
`src/torrent/hydrology/candidate_promotion.py:124 DECIDING_ARM`, which are real
sites on torrent `main` that the file-scoped exemption was hiding. They are the
subject of A5 below and of **E-M38**. Read A1/A2/A3 as the presence or absence
of `D6_DECIDING_ARM` at `mlkit_bindings.py`, which is the one thing the three
shapes differ in:

| shape | `mlkit_bindings.py` `D6_DECIDING_ARM` reported? before → after |
|---|---|
| A | yes → yes |
| B | no → no |
| C | **no → yes** |

## A4 — fray's E-035 dead-import shape still reports its findings

`src/registry/promotion_gate.py` replaced by its pre-adoption blob
(`81f453f`, the parent of the P0-6 adoption commit `fc4eaa4`, found by content
rather than typed), with and without E-035's own one line
`from resilient_mlkit.core.served import challenger_decision  # noqa: F401`.
283 files walked in every row.

| shape | rows IN `src/registry/promotion_gate.py`, before | after |
|---|---|---|
| pre-adoption blob, no dead import | 4 | 4 |
| **plus the dead import** | **4** | **4** |

The four are E-035's own four, at the lines it published:
`PromotionResult`, `_record`, `evaluate_promotion`, `run_promotion_gate`.
**The dead import bought nothing before this branch and buys nothing after it.**
E-035 is not re-opened.

**A residual found while driving A4, named and NOT repaired here.** At REPO
scope the dead-import shape reports 4 rows where the un-mutated pre-adoption
shape reports 5: the row that disappears is
`scripts/verify_cqr_gate_wiring_controls.py:120 PROMOTION_VERDICT
_promotion_gate`, in a DIFFERENT file. Cause: the route pass
(`contract_importers`) is deliberately built on `_imports_contract`, so adding
the dead import to `promotion_gate.py` makes that module a genuine re-export
route, and the control script that imports from it and uses what it took is
then exempt. The route is real at runtime — the symbol genuinely re-exports —
so this is not obviously a defect, but a dead import moving a finding in
another file is worth a reader knowing about. It is unchanged by this branch
(4 → 4 and 5 → 6, the same one-row gap on both sides) and is out of scope: it
is about the ROUTE exemption, not the serve arm. Recorded in **E-M38**.

## A5 — the three current mains: R12 goes PASS → FAIL, and this is the finding

Driven through `checks.readiness.r12_served_contract`, the check the portfolio
actually runs, in one process per side:

| repo | files | before | after |
|---|---|---|---|
| `resilient-chokepoint` | 330 | **PASS**, 0 reimplemented | **FAIL**, 6 reimplemented |
| `resilient-fray` | 283 | **PASS**, 0 | **FAIL**, 1 |
| `resilient-torrent` | 597 | **PASS**, 0 | **FAIL**, 2 |

Nine rows appear; **no row disappears anywhere**, which is A5's superset
requirement and the prereg's "strictly stronger" claim, measured rather than
asserted:

```
resilient-chokepoint
  + mlkit_bindings.py:2112                              SERVE_ARM  DAILY_FLOW_DECIDING_ARM
  + mlkit_bindings.py:2152                              SERVE_ARM  if <arm> ... raise
  + scripts/run_foundation_corridor_allocation.py:97    SERVE_ARM  ARMS
  + scripts/run_foundation_corridor_allocation.py:236   SERVE_ARM  if <arm> ... raise
  + scripts/run_foundation_per_corridor_cqr.py:97       SERVE_ARM  ARMS
  + scripts/run_foundation_per_corridor_cqr.py:203      SERVE_ARM  if <arm> ... raise
resilient-fray
  + mlkit_bindings.py:848                               SERVE_ARM  D6_DECIDING_ARM
resilient-torrent
  + scripts/hydrology/run_operational_information_set.py:88   SERVE_ARM  ARMS
  + src/torrent/hydrology/candidate_promotion.py:124          SERVE_ARM  DECIDING_ARM
```

**`candidate_promotion.py:124` is E-079's own shape, in the wild, eleven lines
below a correct adoption.** The file declares
`SERVE_ARMS = ServeArms(open=frozenset({"val"}), closed={"test": ...})` — the
contract's data, with a real reason attached — and then writes
`DECIDING_ARM = "val"` beneath it. The contract's `ServeArms` is bound and
used, so the file was silent; the value the adjudication decides on is the
constant. That is precisely the thing E-079 predicted would be invisible, found
by the repair E-079 asked for, in the repo that asked for it.

`mlkit_bindings.py:848` in fray and `mlkit_bindings.py:2112` in chokepoint are
the same shape.

**The `ARMS` rows are a different question and are reported, not adjudicated
here.** torrent's `ARMS` at `run_operational_information_set.py:88` is a dict of
EVALUATION arms (`S`, `O`, `P`, `S_d`, `P_d`, `F_d`, `F'_d`), not a train/val/
test serve arm; chokepoint's two are similar. R12's arm-CONSTANT detector has
always been name-based (`_ARM_CONSTANT_RE` matches a bare `ARMS`), and this
branch did not touch it — tightening it would REMOVE findings, which is the
direction the prereg forbids. Whether each site is a serve-arm policy or a
different sense of the word is the owning repo's call, and mlkit is not those
repos' to edit (rule 7 read the other way round). Enumerated in **E-M38** so
each owner has the list.

## A6 — the wider fleet: no row moves on any of the fourteen stale checkouts

The same before/after comparison over every `resilient-*` checkout on this
machine (3,426 files):

| tree | files | before | after | added | removed |
|---|---|---|---|---|---|
| arabica | 385 | 4 | 4 | 0 | 0 |
| backend | 437 | 6 | 6 | 0 | 0 |
| blackout | 229 | 2 | 2 | 0 | 0 |
| choco | 399 | 2 | 2 | 0 | 0 |
| chokepoint | 285 | 0 | 0 | 0 | 0 |
| fray | 235 | 0 | 0 | 0 | 0 |
| frontend | 0 | 0 | 0 | 0 | 0 |
| mentra | 49 | 0 | 0 | 0 | 0 |
| mlkit | 30 | 0 | 0 | 0 | 0 |
| provenance | 8 | 0 | 0 | 0 | 0 |
| surge | 350 | 0 | 0 | 0 | 0 |
| torrent | 551 | 0 | 0 | 0 | 0 |
| transect | 50 | 0 | 0 | 0 | 0 |
| triage | 418 | 14 | 14 | 0 | 0 |

**These are the CANONICAL checkouts and they are stale** — torrent's is 551
files against the fresh clone's 597, and it carries neither
`candidate_promotion.py` nor the #190 repair. Their unanimity is therefore
evidence about the FILE COUNT of the change (it touches nothing outside the
serve-arm clause) and NOT evidence that the fleet is unaffected. The fresh
mains in A5 are what the fleet actually is, and there the answer is nine rows.

## The version, chosen from the measurement (A6's second half)

`CHANGELOG.md`'s own scale: **"major — an existing check changes verdict on
unchanged code."** Measured above: R12 renders FAIL on three repository `main`s
that render PASS today, with not one byte of their code changed. That is the
major case exactly, so this branch bumps to **v1.0.0**. It is not a judgement
about maturity; it is the scale applied to a number.

Each repo pins mlkit by ref, so nothing goes red until a repo moves its pin —
which is what the tags exist for. No repo's pin is moved by this branch.

## A7 — the suite

One clone, `PYTHONPATH=<clone>/src`, `resilient_mlkit` resolving into it,
`python -m pytest tests -q`, no `-k` filter:

```
main   1d9df13 : 1272 passed, 3 skipped   (199.87s)
branch          : 1282 passed, 3 skipped   (231.20s)
failures ONLY on the branch : NONE
failures ONLY on main       : NONE
```

Identical failure sets — both empty — and **+10 passing**. The three skips are
the same three (`test_torrent_model_of_record.py`, which skips unless a
`resilient-torrent` checkout is the clone's sibling).

`ruff check src tests scripts` at the pinned `0.16.5`: output **byte-identical**
to `main`'s. `mypy src/resilient_mlkit`: 3 errors, **the same 3 as `main`**
(`module_bindings.py:178` ×2, `identity.py:487`), all pre-existing.

### The tests that moved, and why each moved

Five tests asserted `== []` on a file that routes its PROMOTION logic through
the contract and declares its arms as a bare local tuple. **That assertion IS
the defect**, written down: it is the E-079 shape, one fixture at a time. Each
is now a FIRES/SILENT pair in place — the SILENT half takes the ARM from the
contract as well (one substituted line, `serving(...)`), the FIRES half leaves
it local and asserts that the five shape clauses stay exempt and the arm does
not.

| test | what it now asserts |
|---|---|
| `test_a_used_import_still_exempts` | SILENT with the arm from the contract; FIRES on `SERVEABLE_ARMS` and the inline refusal with it local |
| `test_a_dotted_import_used_as_a_full_chain_still_exempts` | same, dotted spelling |
| `test_a_dotted_import_bound_with_as_still_exempts` | same, `as` spelling |
| `test_one_level_of_indirection_through_a_repo_adapter_is_exempt` | same, one repo-local route |
| `test_a_repo_local_route_taken_by_the_dotted_spelling_still_exempts` | same, dotted route |

Ten tests are added, eight of them halves of E-079 pairs. Nothing was deleted.

## C5 — CHECK-NOT-DEAD, driven

`_findings_for` reverted to the file-scoped rule it replaces
(`if file_exempt: return []`) in a throwaway worktree of this branch's head,
full suite run:

```
10 failed, 1272 passed, 3 skipped
```

The ten are **exactly the FIRES halves** — the five updated tests and
`test_e079_a_conforming_helper_does_not_exempt_the_arm_the_file_actually_uses`,
`test_e079_one_level_of_local_indirection_is_honoured_but_is_not_free`,
`test_e079_only_the_serve_arm_clause_is_decision_scoped`,
`test_e079_fires_at_repo_scope_and_through_the_check`,
`test_e079_a_dead_route_does_not_derive_an_arm`. Nothing else moves. The SILENT
halves stay green under the mutation, which is right: they do not depend on the
narrowing, so a repair that broke them would have been caught by the pair rather
than by the count.

## What this branch did not do

* It did not touch the five clauses that are not the serve arm, `core.served`
  itself, any threshold, or any repo's tree.
* It did not tighten `_ARM_CONSTANT_RE` to make the `ARMS` rows go away. That
  would remove findings, which is the direction rule 6 forbids and the prereg
  forbade.
* It performed nothing reserved by rule 12, and it read no holdout: the whole
  measurement is an AST walk over source files and opens no split.
