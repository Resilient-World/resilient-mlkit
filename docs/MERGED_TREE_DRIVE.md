# The merged-tree drive, and "MERGED is not in main" — the adopter recipe

*Plan v3 §7 M-3 and brief item (4). Written 2026-09-04 from the campaign
record, not from memory; every incident below is quoted from `STATE.md` with its
date.*

## Why a single-PR review cannot see these

Three defects this week existed **only in the combination** of two changes that
were each correct on their own branch:

| date | what | where it was found |
|---|---|---|
| 2026-09-04 | torrent E-069: `src/torrent/mlops/hard_stops.py:48` at `cec1c48` quoted the D2 clause that was TRUE on its branch's CLAUDE.md; S-5 reached `main` via #178 and never reached that branch; on the merged tree the sentence was stale and the S-5 scanner exited 1 | by hand, on a merged tree |
| 2026-09-04 | chokepoint #122 edited `.mlkit/repo.toml` (adding D6's binding) and moved the sha256 the S-5 register pinned for `CP-D2-ABOVE`: scanner rc 0 → 1 on the merged tree | by hand, on a merged tree |
| 2026-09-04 (third time) | fray #106 / chokepoint #127 / torrent #182 all reported **MERGED** while `main` was unchanged — their base was the S-5.1 branch, so they merged into *that* | `git merge-base --is-ancestor`, by hand |

"MERGED" is a status word. The fact is ancestry.

## Recipe 1 — drive the merged tree before calling a stacked PR landed

```
# from the PR's checkout, base = the ref it will actually land on
mlkit check --phase readiness --repo torrent --merged-with origin/main --json-out reports/merged_drive.readiness.json
mlkit check --phase decision  --repo torrent --merged-with origin/main --json-out reports/merged_drive.decision.json
```

What it does: builds the merge of HEAD with `origin/main` as a **synthetic
commit** (`git merge-tree --write-tree`, then `git commit-tree` with both
parents), checks it out into a **temporary detached worktree**, drives the phase
there, and prints the table under a stamp:

```
MERGED-TREE DRIVE  head=e494ab511595  base=origin/main@3bf16dd0b0c8
  merge tree c512abf5e470…  synthetic commit 7a…  (parents: head, base; no branch moved; discarded after the drive)
  (results NOT saved to .mlkit/results/: this tree is on no branch)
```

What it refuses: **a conflict**. Exit 2, the conflicted paths named, nothing
driven, nothing left behind. mlkit never resolves one — with any strategy —
because the rule this fleet paid for is *resolve the HUNK, then audit the
refusal counts both ways*, which is a person's job.

What it never does: write into the real repo's `.mlkit/results/` or `reports/`
(a verdict about a tree that is on no branch must not sit in the store the
branch's own verdicts are read from), or move a branch.

The stamp in `--json-out` carries `head_sha`, `base_ref`, `base_sha`,
`merge_tree`, `merge_commit`, `identical_to_head` and every result stamped with
the synthetic commit. **Paste the stamp into the PR body.** The fleet's rule:
any PR whose base is not `main`, or whose files intersect another open PR's,
carries it.

`identical_to_head: true` means the branch already contains the base — the
merged tree IS the branch tree, and the drive must equal a plain drive of HEAD
(that is asserted in `tests/test_merged_tree_drive.py::test_t3_…`).

## The worktree holds committed content only — and now says so (REPAIR, 2026-09-05)

The temporary worktree is built from **tree objects**, so it holds **committed
content only**: no gitignored staged panel travels with it. That limit was
disclosed here and in `core/merged.py` and enforced nowhere, and the adjudicator
measured the consequence. Driven against a real fray clone at `a18c447`, before
this repair:

```
D2 PASS   estimate=-0.945, ci_low=-4.239, ci_high=+2.441      ← inputs never established
D3 PASS   nominal=0.8, empirical=0.7944664031620553, n=253    ← inputs never established
D6 FAIL   resampling_declaration raised TemporalSplitIdentityMismatch …
E1 FAIL   scaling_probe raised TemporalSplitIdentityMismatch …
```

Two of those are an **environment failure rendered as a verdict**, in the shape
each repo's own `hard_stops.py` reads as a fired stop — the exact conflation
M-1's `UNMEASURABLE` exists to end, reappearing inside the tool meant to end it.
It is the same class of defect fray #115 landed: an artifact recording that a
promotion-gate re-run was NOT identical, when the re-run's inputs were absent
and it had measured nothing.

**What a repo declares.** An optional `[inputs]` table in `.mlkit/repo.toml`,
keyed by BINDING NAME, listing the repo-relative paths that binding reads:

```toml
[inputs]
placebo_test           = ["data/cache/nass_yields.json"]
coverage               = ["data/cache/nass_yields.json"]
resampling_declaration = ["data/cache/nass_yields.json"]
scaling_probe          = ["data/cache/nass_yields.json"]
metric_known_answer    = []   # reads nothing outside the committed tree
```

`[]` is a **positive declaration**, not an absence.

**What the drive now does**, and only on `--merged-with`:

| the binding | the row |
|---|---|
| declares inputs this tree carries | **driven**, renders whatever it renders |
| declares `[]` | **driven** |
| declares inputs this tree does NOT carry | **UNMEASURABLE**, naming the absent path |
| declares nothing at all | **UNMEASURABLE**, naming the binding and this recipe |

Never FAIL and never PASS. Exit stays `3` (unmeasured is not green, and is not
the FAIL exit — CI gating on `1` must not read an absent panel as a broken
repo), and no `halt` key is ever attached: nothing is indicted.

**The last row is the fail-closed direction and it has a price, stated
plainly.** The tree provably holds committed content only; whether a binding
needs more than that is a fact only the repo knows; so with no declaration mlkit
cannot *establish* that the input is present, and an unestablished input may be
rendered as unmeasured but never as a verdict. The price is that a real
merged-tree finding on an undeclared binding — E-069's own shape — renders
UNMEASURABLE until the repo adds one line of TOML. That is driven, not asserted,
in `tests/test_merged_tree_input_guard.py::test_b6_the_undeclared_refusal_masks_a_merge_defect_and_names_the_remedy`.

A plain drive is untouched: the guard is armed only on the merged worktree.
Measured on the same fray clone, pre- and post-repair plain drives of
`selection`, `readiness`, `decision` and `economics` are row-for-row identical.

The AST-walking checks (R10/R11/R12/R13) and the committed-declaration checks
(D2's `[placebo]`, D3's `[coverage]`, E1's `[scaling]`) resolve no binding and
measure exactly as they do on the branch.

## Recipe 2 — after any merge, verify containment per PR

```
git fetch origin
mlkit ancestry --path . --base origin/main <pr-head-sha> [<pr-head-sha> …]
```

```
COMMIT        SHA           VERDICT        IN
2bb9904e4…    2bb9904e4a1c  CONTAINED      origin/main@d34649f8e2b7
1fca35668…    1fca35668c0d  NOT CONTAINED  origin/main@d34649f8e2b7
```

Exit `0` only when **every** commit is contained; `1` when any is not; `2` when
a ref did not resolve (nothing is asserted — a missing ref is not "not
contained", it is a question that was not asked). `--json` for the record.

The PR-body field the plan asks for, per PR after any merge:

```
ancestry: <pr-head-sha> CONTAINED in origin/main@<sha>   (mlkit ancestry, <date>)
```

If it reads NOT CONTAINED, the PR merged into its base branch. Cascade: merge
the base branch's PR into *its* base, and re-run this until every head is
contained in `main`. That is what landing the S-5 stack took (#96 ← #104 ← #106
on fray, and the same shape on chokepoint and torrent).

## PR template lines (copy into the fleet's template)

```
### Merged-tree drive (required if base != main or files intersect another open PR)
- [ ] `mlkit check --phase <P> --merged-with origin/main` stamp pasted below
- head <sha> · base origin/main@<sha> · merge tree <oid> · identical_to_head <bool>
### Ancestry (fill in AFTER merge; "MERGED" is a status word)
- `mlkit ancestry --path . --base origin/main <head-sha>` → CONTAINED / NOT CONTAINED
```

## Controls (all in `tests/test_merged_tree_drive.py`)

| id | claim | how |
|---|---|---|
| T1 | fires **only** on the merge | D2 PASS on head, NA on base, `PLACEBO_EXEMPTS_THE_CLAIM` FAIL on the merge — E-069's shape on mlkit's own check |
| T2 | a conflict is refused, never resolved | exit 2, `.mlkit/repo.toml` named, one worktree left, no results dir |
| T3 | silent when the merge is the branch | base ∈ ancestors(head) → merge tree == head tree, statuses equal, stamp says so |
| T4/T5 | no side effect; stamp names both parents | real store untouched, HEAD unmoved, `git rev-list --parents` == `[head, base]`, results stamped with the synthetic commit |
| B1–B7 | the input guard (`tests/test_merged_tree_input_guard.py`) | undeclared → UNMEASURABLE; declared-and-absent → UNMEASURABLE naming the path; declared-and-present and `[]` → the check RUNS (check-not-dead); a plain drive unchanged; a malformed declaration refuses rather than loosens; an import-time `InputUnavailable` is still `PREMATURE_INPUT_REFUSAL` FAIL |
| A1–A3 | ancestry | a commit merged into a feature branch is NOT CONTAINED in main (exit 1) and CONTAINED in the feature branch (exit 0); an unresolvable ref exits 2 |
