# Results — the crosscut carve-out, proportional and fail-closed

Every figure below was produced by running the code. The preregistration this
answers is `reports/DEPENDENCE_UNIT_PREREGISTRATION_AMENDMENT_1.md`, committed
as the **first commit on this branch** (`dc54c71`) before any source file was
edited. Nothing here was typed by hand from memory, and no figure from any real
run appears in this file.

- branch: `fix/m-d6-crosscut-proportional`
- base: `feat/dependence-unit-contract` @ `24f23b86b600b1cd18f3a4c3c7fc8bdbd48a01ac`
  (PR #32, open and unmerged; it owns `core/served.py` and this branch is
  stacked on it rather than editing the same file in parallel from `main`)
- `origin/main` @ `6921e9af146faad69ca09ed546c607d7e484e560`, confirmed by
  `git ls-remote` this session
- interpreter: `/Users/david/Downloads/Claude Code/resilient-mlkit/.venv/bin/python`, 3.14.6
- lint / types at the versions `.github/workflows/ci.yml` pins:
  `ruff check src tests scripts` → **all checks passed**;
  `mypy src/resilient_mlkit` → **no issues, 29 source files**
- **binding asserted in every driver.** `scripts/d6_crosscut_drive.py` asserts
  `__file__` for `core.served`, `checks.decision` and `checks`;
  `scripts/d6_containment_enumerate.py` and both test files assert it for
  `core.served`. `resilient_mlkit` is installed into eight virtualenvs on this
  machine, so a green run without that assertion says nothing about this tree.
- **compute**: no fits, no sweeps, no fine-tunes, no data reads, no network. One
  detached worktree at the base sha, deleted afterwards. **No ledgered test read
  was opened or approached** — fray's unseen-year arm and chokepoint's `h=1`,
  `h=3` and `h=14` arms are untouched, and no code path added here can reach
  one.

---

## 1. The suite — H11, taken first

| | suite |
|---|---|
| base `24f23b8`, its own worktree | **977 passed** |
| this branch, before the new test file | **977 passed** |
| this branch, with `tests/test_dependence_unit_crosscut.py` | **991 passed** in 58.95s |

991 = 977 + 14. **`tests/test_dependence_unit.py` is not modified by this branch
— not a line, not a parametrize entry** — and neither is any other existing
test. `git diff --name-status 24f23b8..HEAD` is the proof and is reproduced in
§5.

## 2. CONTROL A — the escape, before and after, through the real binding path

`scripts/d6_crosscut_drive.py` builds a fixture repo on disk with a
`resampling_declaration` binding and a `splits` binding, resolves them the way
`Repo.resolve` does, and calls `d6_resampling_unit`. It was run once with `src/`
still at the base's semantics (`reports/D6_CROSSCUT_BASE.json`, driven at
`dc54c71`, the prereg commit, which changes no source file) and once at the head
(`reports/D6_CROSSCUT_HEAD.json`).

| shape | D6 base | D6 head | relation base → head | head refusal |
|---|---|---|---|---|
| fray as run — ROW units | FAIL | FAIL | `UNIT_FINER_THAN_BLOCK` → same | `DEPENDENCE_UNIT_TOO_FINE` |
| **fray — COUNTY units** (the wave-1 verifier's drive) | **PASS** | **FAIL** | `UNIT_CROSSCUTS_ARMS` → `UNIT_CROSSCUTS_BLOCK` | **`DEPENDENCE_UNIT_TOO_FINE`** |
| **fray as run + ONE colliding `unit_key`** | **PASS** | **FAIL** | `UNIT_CROSSCUTS_ARMS` → `UNIT_FINER_THAN_BLOCK` | **`DEPENDENCE_UNIT_TOO_FINE`** |
| fray repaired — CROP-YEAR units | PASS | PASS | `UNIT_IS_THE_BLOCK` → same | — |
| chokepoint — CORRIDOR units | PASS | PASS | `UNIT_CROSSCUTS_ARMS` → same | — |
| chokepoint, label contradicts content | FAIL | FAIL | `UNIT_CROSSCUTS_ARMS` → same | `UNIT_LABEL_CONTRADICTS_CONTENT` |
| chokepoint + one **val-only** corridor | PASS | **FAIL** | `UNIT_CROSSCUTS_ARMS` → `UNIT_CROSSCUTS_BLOCK` | `DEPENDENCE_UNIT_TOO_FINE` |

Row 2 is **H8** and row 3 is **H9**, and the base column reproduces what
`scratchpad/loop/STATE.md` recorded for the wave-1 verifier exactly: county
units → crosscutting → refusal silent → **D6 PASS**, in the very repo the
finding came from.

**H9's second half — the relation does not move either.** fray as run and fray
as run with one of 1,365 val `unit_key`s collided into a train key now give the
*same* refusal and the *same* relation; only the classification counts differ:

| | `n_units_crosscutting_arms` | `n_units_local_to_arm` | relation | refusal |
|---|---:|---:|---|---|
| fray as run | 0 | 1365 | `UNIT_FINER_THAN_BLOCK` | `DEPENDENCE_UNIT_TOO_FINE` |
| + one colliding key | 1 | 1364 | `UNIT_FINER_THAN_BLOCK` | `DEPENDENCE_UNIT_TOO_FINE` |

and colliding 1, 10, 100 or 1,000 of the 1,365 keys refuses every time
(`test_H9_the_escape_does_not_scale_back_in_from_the_other_end`). There is no
count of collisions below *all of them* that buys silence.

The proportion is in the message rather than only in the branch. The head's
refusal for the county drive reads:

> the bootstrap resampled 285 'county' unit(s) inside arm 'val', but holdout
> policy 'county_year_splits' keeps whole 'crop_year' blocks in one partition
> and that arm holds 5 of them. 5 block(s) are split across units (e.g. 2016
> spans 253 units). … 48 of the 285 unit(s) in this arm do cross the split and
> 237 do not; the carve-out covers a unit the split never partitioned, and it
> does not extend to the units beside it that live entirely inside 'val'.

## 3. CONTROL B — what stayed silent

Rows 4, 5 and 6 of the table above, unchanged in status, relation and constant.
Specifically:

* **chokepoint's convention is untouched.** 28 corridors, all present in
  `train`, `val` and `test`; `n_units_crosscutting_arms = 28`,
  `n_units_local_to_arm = 0`, relation `UNIT_CROSSCUTS_ARMS`, no refusal, and
  `n_blocks_in_arm = 20` still in the record beside `n_units_in_arm = 28`. This
  is the branch's own falsification condition (Amendment 1 §6): had it moved,
  the fleet's *correct* convention would have been made unadoptable, which is
  the R12 failure mode the original preregistration named, and the instruction
  was to withdraw the branch rather than argue with the control.
* **chokepoint's REAL panel, not only the fixture.** The fixture above is built
  in this repo, so on its own it proves the narrowing is safe for a shape mlkit
  made up. Read from chokepoint's own committed artifact
  `reports/benchmarks/corridor_pooling_val.json` (that repo at its current head,
  read-only, nothing written and no arm opened):

  | arm | rows | corridors |
  |---|---:|---:|
  | train | 40,712 | **28** |
  | val | 11,704 | **28** |
  | test | 14,756 | **28** |

  All three arms carry 28 corridors, so the arm-local mass on the real panel is
  empty and the carve-out still covers it. **Stated at exactly its strength:**
  equal counts in three arms are not the same fact as the three corridor *sets*
  being identical, and that artifact reports counts, not rosters. If a corridor
  ever entered `val` without appearing in `train`, this branch would refuse
  chokepoint's bootstrap, and the way to settle it is to read the rosters when
  chokepoint wires the binding — not to assume it here.
* **fray's repair is untouched:** `UNIT_IS_THE_BLOCK`, silent, 5 units over 5
  blocks.
* **The label remutation still refuses by its own constant**, with
  `UNIT_CROSSCUTS_ARMS` still named in its detail.
* **The full suite is verdict-identical outside the changed relation:** 977 → 977
  with no test edited, +14 new.

## 4. Attacking the fix — what this found in its own work

### 4.1 The containment claim, enumerated rather than argued

Amendment 1 §4 claimed: *every assignment that refuses at the base refuses at
the head, with the same refusal constant.* `scripts/d6_containment_enumerate.py`
enumerates **209,952** assignments — 4 rows, each independently one of
2 arms × 3 block keys × 3 unit keys, under both label configurations — at the
base sha and at the head, keyed by content so the two runs line up without
either side knowing about the other. `scripts/d6_containment_diff.py` counts the
transitions. Recording: `reports/D6_CROSSCUT_CONTAINMENT.json`.

| | count |
|---|---:|
| cases enumerated | 209,952 |
| **SILENCED** (refused at base, silent at head) | **0** |
| REFUSAL_CONSTANT_MOVED | 6,912 |
| … of those, moved LATER in the ladder | **0** |
| TIGHTENED (silent at base, refuses at head) | 6,912 |
| UNCHANGED | 196,128 |
| relation moved without the verdict moving | 56,160 |

**Amendment 1 §4 is falsified as literally worded, and upheld on the verdict.**
Said plainly rather than glossed: 6,912 cases refuse on both sides under a
*different constant*, every one of them
`UNIT_LABEL_CONTRADICTS_CONTENT → DEPENDENCE_UNIT_TOO_FINE`. That is the third
clause of the ladder, which is now proportional, answering cases the fourth
clause used to catch. Every such move is to an **earlier** ladder position —
the more specific statement about the same assignment — and the diff tool
checks that direction and would have reported a move the other way. **Zero cases
go from refusing to silent.** The corrected claim, driven: *no assignment that
refuses at the base is silent at the head, and no refusal moves later in the
ladder.*

The 56,160 relation moves are all out of `UNIT_CROSSCUTS_ARMS`
(→ `UNIT_IS_THE_BLOCK` 33,696, → `UNIT_FINER_THAN_BLOCK` 16,416,
→ `UNIT_CROSSCUTS_BLOCK` 3,456, → `UNIT_COARSER_THAN_BLOCK` 2,592) on cases
whose verdict does not move. That is the intended effect: the relation is a
label on a silence, and it now describes the arm-local mass rather than being
overwritten by one crosscutting key.

### 4.2 The regression this attack found in the fix itself

The enumeration was run a third time with **one half of the fix removed** — the
`or crosscutting` added to `UNIT_LABEL_CONTRADICTS_CONTENT`. Recording:
`reports/D6_CROSSCUT_CONTAINMENT_NOT_DEAD.json`.

| | with the label half | without it |
|---|---:|---:|
| SILENCED | **0** | **2,160** |
| verdict | CONTAINED | **CONTAINMENT FALSIFIED** |

Making the relation proportional would, on its own, have **loosened a sibling
clause in the same file**. The smallest case, reduced by hand and now held as
`test_the_label_clause_did_not_go_quiet_when_the_relation_became_local`:

| row | arm | block | unit |
|---|---|---|---|
| 0 | val | 0 | u0 |
| 1 | val | 1 | u1 |
| 2 | train | 2 | u0 |

with the resampled unit labelled the same as the policy's blocking unit. At the
base: `UNIT_LABEL_CONTRADICTS_CONTENT`, relation `UNIT_CROSSCUTS_ARMS`. With the
relation made proportional and the label clause left alone: **silent**, relation
`UNIT_IS_THE_BLOCK` — the two arm-local-and-crosscutting units happen to sit one
per block. With the fix as committed: refuses, by the same constant as the base,
and the detail says why (`straddling` is empty by then, so every block of this
policy is in exactly one arm and a unit key with rows in two arms cannot be one
of them).

This is reported because it is the part of the round that nearly shipped a
regression, not despite it.

### 4.3 The other operands, checked

* `units_of_block[b] - crosscut_keys` — both sides are sets of the **canonical**
  unit spelling produced by `_canonical`, built from the same rows, so the
  subtraction compares by content and not by `repr`.
* `arms_of_unit` is built over the **whole panel** and `blocks_of_unit` over the
  **deciding arm only**, which is what makes "crosscutting" a statement about
  the split rather than about the arm. A unit key that exists in `train` and
  `test` but not in the deciding arm is not in `blocks_of_unit`, so it is
  neither classified nor counted — correct, because it was not resampled here.
* Clause order is unchanged: `BLOCKS_STRADDLE_ARMS`, then `SINGLE_UNIT`, then
  `DEPENDENCE_UNIT_TOO_FINE`, then `UNIT_LABEL_CONTRADICTS_CONTENT`. `straddling`
  being answered first is what licenses the argument in §4.2.
* The four new derived facts are `init=False` and each raises `TypeError` naming
  the argument, like the eleven before them (H12), and they are checked
  arithmetically against the counts beside them:
  `n_units_crosscutting_arms + n_units_local_to_arm == n_units_in_arm`, and the
  two block counts are disjoint subsets of `n_blocks_in_arm`.

## 5. Nothing that is a gate moved

```
$ git diff --name-status 24f23b8..HEAD
A	reports/D6_CROSSCUT_BASE.json
A	reports/D6_CROSSCUT_CONTAINMENT.json
A	reports/D6_CROSSCUT_CONTAINMENT_NOT_DEAD.json
A	reports/D6_CROSSCUT_HEAD.json
A	reports/D6_CROSSCUT_RESULTS.md
A	reports/DEPENDENCE_UNIT_PREREGISTRATION_AMENDMENT_1.md
A	scripts/d6_containment_diff.py
A	scripts/d6_containment_enumerate.py
A	scripts/d6_crosscut_drive.py
A	tests/test_dependence_unit_crosscut.py
M	CHANGELOG.md
M	docs/ESCALATIONS.md
M	src/resilient_mlkit/core/served.py
```

Ten additions, and three modifications of which two are append-only prose. The
one source file changed is `core/served.py`, which PR #32 owns and this branch
is stacked on. **No `.mlkit/` file, no threshold, no range, no holdout and no
existing test appears in that list.** `CHANGELOG.md` and `docs/ESCALATIONS.md`
are shared with the other open mlkit PRs (#31, #33, #34, #35, #36) and are
appended to only; no file any of those five PRs modifies is edited here.

## 6. What is NOT closed

**The carve-out is narrowed, not removed.** A declaration in which *every* unit
key crosscuts every arm is still refusal-free, even when those units are finer
than the policy's blocks inside the deciding arm.
`test_the_residual_hole_is_named_here_rather_than_left_to_be_discovered` drives
exactly that shape — a fray panel whose county index reaches every arm — and
asserts the silence, so that a later change which refuses it has to say what
measurement licensed the standard. chokepoint's endorsed corridor bootstrap has
the same structure, and **nothing measured in this round tells the two apart.**
What the head adds is that `n_blocks_split_by_crosscutting_units` now prints how
many of the policy's blocks a passing carve-out is carrying: 20 of 20 for
chokepoint's fixture, 5 of 5 for the fully-crossing fray shape.

**No adopter repo is edited and no repo adopts D6 here.** D6 remains NA on every
repo on disk for the reason the original preregistration predicted (H7): no repo
declares a `resampling_declaration` binding. Separately, and measured in wave 1
rather than here: fray *cannot* wire D6 for its unseen-year track as `splits`
stands — one `splits` binding, two tracks with different partitions, which D6
answers `BLOCKS_CONTRADICT_SPLITS`. Adoption is more than a `repo.toml` line and
is not attempted on this branch.
