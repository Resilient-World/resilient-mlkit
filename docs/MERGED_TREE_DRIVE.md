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

Limits, said plainly: the temporary worktree holds **committed content only**.
No gitignored staged panel travels with it, so a binding-dependent check renders
what it renders on any clean clone — with M-1, `UNMEASURABLE` once the binding
raises `InputUnavailable`. The AST-walking checks (R10/R11/R12) and the
committed-declaration checks (D2's `[placebo]`, D3's `[coverage]`, E1's
`[scaling]`) measure exactly as they do on the branch.

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
| A1–A3 | ancestry | a commit merged into a feature branch is NOT CONTAINED in main (exit 1) and CONTAINED in the feature branch (exit 0); an unresolvable ref exits 2 |
