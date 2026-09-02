# Amendment 1 to the dependence-unit preregistration — the crosscut carve-out becomes proportional and fail-closed

Written **before** any source file was edited on `fix/m-d6-crosscut-proportional`.
This file is the **first commit on that branch**; the parent is
`origin/feat/dependence-unit-contract` @ `24f23b86b600b1cd18f3a4c3c7fc8bdbd48a01ac`,
whose own first commit is the preregistration this amends
(`fefdc5e`, `reports/DEPENDENCE_UNIT_PREREGISTRATION.md`, parent `origin/main`
@ `6921e9af146faad69ca09ed546c607d7e484e560`).

- branch: `fix/m-d6-crosscut-proportional`
- base: `feat/dependence-unit-contract` @ `24f23b8` (PR #32, **open, unmerged**).
  That PR owns `src/resilient_mlkit/core/served.py`; this branch is stacked on
  it rather than editing the same file in parallel from `main`.
- compute: **no fits, no sweeps, no fine-tunes, no data reads, no network.**
  The only executions are pytest and `scripts/d6_crosscut_drive.py`, which
  builds fixture repos in a temp directory and calls `D6`. No model repo is
  written. **No ledgered test read is opened or approached** — fray's
  unseen-year and chokepoint's `h=1`/`h=3`/`h=14` arms are untouched and no
  code path added here can reach one.
- **This amendment is strictly stricter.** It moves no threshold, widens no
  range, narrows no holdout, and weakens, edits or deletes no test — on `main`
  or on the base branch. §4 states and §6 measures the containment claim: every
  assignment the base refuses, the head refuses, for the same named reason.

---

## 1. The escape being closed, and how it was found

The wave-1 adversarial verifier of PR #32 accepted the branch **with a caveat
that the PR's own residuals did not name**, recorded in `scratchpad/loop/STATE.md`
(2026-09-01):

> `UNIT_CROSSCUTS_ARMS` silences `DEPENDENCE_UNIT_TOO_FINE` unconditionally, and
> the verifier drove fray with COUNTY units -> crosscutting, refusal SILENT, D6
> PASS — the wrong answer, since only the crop-year unit produces the honest
> interval. Worse, the crosscut test is EXISTENTIAL not proportional: flipping
> ONE val row's `unit_key` to collide with a train row made the refusal vanish
> for all 1,364 others. That is a one-word escape from the check in the very
> repo the finding came from.

Re-driven by this branch's author at the base sha before a line was written,
through `D6` and the real binding path (`scripts/d6_crosscut_drive.py`,
recording committed as `reports/D6_CROSSCUT_BASE.json`):

| shape driven at `24f23b8` | `relation` | `refusal` | **D6** |
|---|---|---|---|
| fray as run — crop-year blocks, ROW units | `UNIT_FINER_THAN_BLOCK` | `DEPENDENCE_UNIT_TOO_FINE` | FAIL |
| **fray — crop-year blocks, COUNTY units** (the verifier's drive) | `UNIT_CROSSCUTS_ARMS` | `NA` | **PASS** |
| **fray as run + ONE colliding `unit_key`** (1 row of 1,365) | `UNIT_CROSSCUTS_ARMS` | `NA` | **PASS** |
| fray repaired — CROP-YEAR units | `UNIT_IS_THE_BLOCK` | `NA` | PASS |
| chokepoint — date blocks, CORRIDOR units | `UNIT_CROSSCUTS_ARMS` | `NA` | PASS |

Rows 2 and 3 are the defect. Row 3 is the sharper statement of it: the panel
that FAILS in row 1 is turned into a PASS by editing **one field of one row**.

## 2. The superseded rule, quoted in full

Nothing below is paraphrase. This is what is being replaced.

**From `reports/DEPENDENCE_UNIT_PREREGISTRATION.md` §2.3, third bullet:**

> * `UNIT_CROSSCUTS_ARMS` — the unit's keys appear in more than one arm, so it
>   is an axis the split does not partition at all. chokepoint's corridor.

**From `reports/DEPENDENCE_UNIT_PREREGISTRATION.md` §2.4, in full:**

> 4. **What this contract does NOT establish, stated here so it is not read as
>    more than it is.** `UNIT_CROSSCUTS_ARMS` is *recorded*, not blessed. A
>    corridor bootstrap does not account for the temporal axis the time-blocked
>    split partitions, and this instrument does not claim it does. What it does
>    is force both numbers into the record side by side — the units resampled and
>    the blocks in the arm that were not — so that a reader of chokepoint's
>    ladder sees `n_units = 28, n_blocks_in_arm = <k>` rather than "corridor
>    bootstrap". Refusing the crosscutting case as well would refuse the
>    convention the adjudication endorsed, on a rule the adjudication did not
>    support, and inventing that standard here is not this branch's to do.

**From `reports/DEPENDENCE_UNIT_PREREGISTRATION.md` §3, H3:**

> * **H3 (silent on chokepoint's convention).** Corridor keys present in `train`,
>   `val` and `test` yield no refusal and relation `UNIT_CROSSCUTS_ARMS`, with
>   `n_blocks_in_arm` reported beside `n_units`.

**From `src/resilient_mlkit/core/served.py` @ `24f23b8`, the code itself
(the constructing expression, the relation ladder and the refusal clause):**

```python
        crosscutting = sorted(
            u for u in blocks_of_unit if len(arms_of_unit.get(u, set())) > 1
        )
        split_blocks = sorted(b for b, units in units_of_block.items() if len(units) > 1)
        split_units = sorted(u for u, blocks in blocks_of_unit.items() if len(blocks) > 1)

        if crosscutting:
            relation = UNIT_CROSSCUTS_ARMS
        elif split_blocks and split_units:
            relation = UNIT_CROSSCUTS_BLOCK
        elif split_blocks:
            relation = UNIT_FINER_THAN_BLOCK
        elif split_units:
            relation = UNIT_COARSER_THAN_BLOCK
        else:
            relation = UNIT_IS_THE_BLOCK
```

```python
        elif not crosscutting and split_blocks:
            refusal = DEPENDENCE_UNIT_TOO_FINE
```

**And the constant's own docstring:**

```python
#: At least one resampled unit's rows appear in more than one arm, so the unit
#: is an axis the split does not partition. chokepoint's corridor.
UNIT_CROSSCUTS_ARMS = "UNIT_CROSSCUTS_ARMS"
```

The first four words of that comment — **"At least one"** — are the defect,
written down in the constant's own documentation and shipped anyway.

**What was wrong with it.** The carve-out is sound as a *statement about a
unit*: an axis the split does not partition at all is not manufactured out of
the holdout's own blocks. The defect is that it was implemented as a statement
about the *declaration*, quantified **existentially over keys**. `if
crosscutting:` asks "does ANY key appear in two arms", and one key answering yes
re-labels every other key in the arm. The carve-out's justification does not
transfer to the units that are **not** on that axis, and those units are where
the refusal was meant to look.

## 3. The replacement rule, stated before it is coded

> **Classify each unit key, not the declaration.** A unit key present in the
> deciding arm is **crosscutting** when its rows appear in more than one arm,
> and **arm-local** when they do not.
>
> A block of the holdout policy, in the deciding arm, is **split by the
> arm-local mass** when the arm's rows in that block are covered by more than
> one unit **and at least one of those units is arm-local**.
>
> **If any block in the deciding arm is split by the arm-local mass, the
> declaration refuses with `DEPENDENCE_UNIT_TOO_FINE`.** The carve-out is not
> available to it, because the piece of that block that was drawn as an
> independent replicate is not on an axis the split failed to partition — it
> lives entirely inside the arm, which is exactly the shape the refusal exists
> for.
>
> **`UNIT_CROSSCUTS_ARMS` is reported only when the arm-local mass is empty** —
> when *every* unit resampled in the deciding arm crosscuts the split. That is
> chokepoint's corridor bootstrap and it keeps its documented behaviour,
> unchanged, refusal-free, with `n_blocks_in_arm` beside `n_units_in_arm`.
>
> **Otherwise the relation is the relation of the arm-local mass**, computed by
> the same three questions the base already asks (does a block span more than
> one arm-local unit; does an arm-local unit span more than one block), so a
> single colliding key cannot change the relation the other keys produce.

Four derived facts are added to the declaration and to `to_dict()`, so the
proportion is in the record and not only in the branch:
`n_units_crosscutting_arms`, `n_units_local_to_arm`,
`n_blocks_split_by_local_units`, `n_blocks_split_by_crosscutting_units`. Like
every other derived fact they are `init=False` and unspellable by a caller.

**No new relation constant and no new refusal constant.** `RELATIONS` keeps its
five members in order; the four refusals keep theirs. The refusal ladder keeps
its order — `BLOCKS_STRADDLE_ARMS`, `SINGLE_UNIT`, `DEPENDENCE_UNIT_TOO_FINE`,
`UNIT_LABEL_CONTRADICTS_CONTENT` — and only the third clause's predicate
changes.

## 4. The containment claim, stated so it can be falsified

> **Every assignment that refuses at `24f23b8` refuses at the head, with the
> same refusal constant.** The change is a strict widening of the refusing set.

The argument, before the measurement: when no unit in the deciding arm
crosscuts, every unit is arm-local, so "blocks split across units" and "blocks
split by the arm-local mass" are the same set, and the new predicate reduces to
the old one. The clauses above and below it are untouched, and the relation
questions are unchanged on a panel with no crosscutting units. §6/H10 drives
this rather than resting on it.

## 5. Hypotheses, stated before measuring

* **H8 (Control A — must fire).** The fray COUNTY-unit drive that the base
  records as `D6 PASS` refuses at the head by name: `DEPENDENCE_UNIT_TOO_FINE`,
  `D6 FAIL`.
* **H9 (Control A — must fire).** fray as run with **one** val `unit_key`
  collided into a train key refuses at the head, and its `relation` is the same
  value the un-mutated fray-as-run panel produces. One key does not move the
  relation of the other 1,364.
* **H10 (Control B — must stay silent).** fray repaired (crop-year units) still
  `D6 PASS`, `UNIT_IS_THE_BLOCK`. The chokepoint corridor shape — every corridor
  in `train`, `val` and `test` — still `D6 PASS`, still `UNIT_CROSSCUTS_ARMS`,
  still `28` units beside `20` blocks. The `UNIT_LABEL_CONTRADICTS_CONTENT`
  remutation of it still refuses with that constant and still names
  `UNIT_CROSSCUTS_ARMS` in its detail.
* **H11 (nothing else moves).** The full mlkit suite is green at the head, and
  every test in it passes unedited. No file under `.mlkit/`, no threshold, no
  range and no holdout differs from the base; `git diff` proves it.
* **H12 (not dead).** Each of the four new derived fields is a `TypeError`
  naming the argument when a caller tries to spell it.
* **H13 (the boundary, recorded not asserted).** chokepoint's carve-out shape
  **plus one corridor that exists only in `val`** refuses at the head and passes
  at the base. This is the narrowing, at its own edge, driven so that the cost
  of the change is in the record next to its benefit.

## 6. What would falsify this work

- H8 or H9 failing: the escape is not closed.
- **H10 failing: the change refuses chokepoint's convention**, which is the R12
  failure mode the original preregistration named ("adopting the check would not
  clear it") and would be a reason to withdraw this branch rather than to argue
  with the control.
- H11 failing: any existing test changing verdict, or any gate file moving.
- H10's containment half failing: any assignment refusing at the base and not at
  the head. That would make this an EDIT to the rule rather than a tightening,
  and rule 6 forbids it.

## 7. Explicitly out of scope, and the residual hole named rather than hidden

- **The carve-out is narrowed, not removed, and the hole it leaves is real.** A
  declaration in which *every* unit crosscuts every arm is still refusal-free,
  and that is still a shape in which a unit can be finer than the policy's
  blocks inside the arm — chokepoint's corridor is exactly such a shape and is
  endorsed, so the two are not distinguishable by anything measured in this
  round. **This branch does not claim to close that case**, for the reason the
  original preregistration gave and this amendment does not overturn: no
  measurement here supports the standard that would refuse it. What the head
  adds is that `n_blocks_split_by_crosscutting_units` is now printed in the
  record beside it, so a reader of a passing declaration can see how many of the
  policy's blocks the carve-out is carrying.
- **No adopter repo is edited.** fray and chokepoint adopt on their own
  branches. No file any other open mlkit PR touches is edited here: #31, #33,
  #34, #35 and #36 between them own `core/identity.py`, `core/store.py`,
  `core/table.py`, `portfolio.py`, `checks/readiness.py`, `checks/economics.py`,
  `core/declaration.py`, `spine/mlkit/repo.toml`, `spine/docs/*`, `README.md`
  and `tests/test_promotion_state.py`; `docs/ESCALATIONS.md` and `CHANGELOG.md`
  are shared and are **appended to only**.
- **No R12 clause, no threshold on unit counts, no tag, no version bump.**
- **No test that exists on `main` or on the base branch is weakened, edited or
  deleted.** `tests/test_dependence_unit.py` is not modified at all; the new
  assertions live in a new file.
