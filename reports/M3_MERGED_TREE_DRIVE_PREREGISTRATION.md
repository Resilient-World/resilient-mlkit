# M-3 — the merged-tree drive as a required control, and "MERGED is not in main": PREREGISTRATION

**Written 2026-09-04, BEFORE any code on this branch. First commit of
`feat/v3-m3-merged-tree-drive`, based on M-1's head `e494ab5` (PR #46).** Plan
item: `sota-plan-v3.md` §7 M-3, and the brief's item (4): the ancestry check
as a published adopter recipe.

## The defect, paid for three times this week (STATE.md, not recalled)

1. **Stacked PRs reported MERGED while `main` was unchanged.** 2026-09-04:
   "Merging #106/#127/#182 returned MERGED for all three, and ANCESTRY SAID NO:
   their base is the S-5.1 branch, so they merged INTO THAT BRANCH, not main.
   fray main was still b180012." Third occurrence; caught each time by
   `git merge-base --is-ancestor`, by hand.
2. **A defect existing only in the combination of two individually-correct
   changes** (torrent E-069): `src/torrent/mlops/hard_stops.py:48` at `cec1c48`
   quoted the D2 clause that was TRUE on its own branch's CLAUDE.md; S-5 reached
   `main` via #178 (`5052c71`) and never reached that branch; on the merged tree
   the sentence was stale and the S-5 scanner exited 1. "No single-PR review
   could see it; only a merged-tree drive."
3. **chokepoint #122 broke the register's own toml pin** on the merged tree:
   scanner rc 0 → 1.

Every one of these was found by a person constructing the merged tree and
driving it. Nothing in the instrument does that.

## What changes (fixed now)

1. `mlkit check --phase P --merged-with <base-ref>`: for each selected repo,
   builds the merge of HEAD with `<base-ref>` as a **synthetic commit** —
   `git merge-tree --write-tree <base> <head>` → `git commit-tree` with both
   parents — checks it out into a **temporary detached worktree**, drives the
   phase there, and prints the table under a stamp naming `head_sha`,
   `base_ref`, `base_sha`, `merge_tree` and the synthetic commit. **A conflict
   is refused (exit 2), never resolved**; the conflicted paths are printed.
   Nothing is written into the real repo's `.mlkit/results/` or `reports/`; the
   worktree is removed afterwards. `--json-out PATH` writes the stamped
   results.
2. `mlkit ancestry --base <ref> <commit>...` (`--path DIR` or `--root/--repo`):
   per commit, `CONTAINED` / `NOT CONTAINED` by `git merge-base --is-ancestor`,
   exit 1 if any is not contained, exit 2 on an unresolvable ref, `--json`.
   This is the check the campaign record ran by hand after every stacked merge,
   as an adopter recipe (README + `docs/MERGED_TREE_DRIVE.md`).

Nothing else moves: no check changes verdict, no threshold, no test deletion.

## Acceptance — controls fixed before the code, driven both ways

| id | direction | fixture | required |
|---|---|---|---|
| T1 | FIRES ONLY ON THE MERGE | a git repo with `ancestor`; `base` adds `[placebo] estimand=…, indicts="below"` to `.mlkit/repo.toml`; `head` (from `ancestor`) adds a `placebo_test` binding whose payload PASSes under the default region with `reference_effect > 0` | plain drive of `head`: D2 **PASS**; plain drive of `base`: D2 **NA** (no binding); `--merged-with base` on `head`: D2 **FAIL** `PLACEBO_EXEMPTS_THE_CLAIM`. Exit codes: 3 / 3 / 1 |
| T2 | REFUSES, NEVER RESOLVES | `base` and `head` edit the same line of `.mlkit/repo.toml` | exit **2**; the conflicted path named; no worktree left behind; no result written anywhere |
| T3 | SILENT WHEN THE MERGE IS THE BRANCH | `base` is an ancestor of `head` | merged tree oid == head tree oid; every status equal to a plain drive of `head`; the stamp says so |
| T4 | NO SIDE EFFECT | after T1 | the real repo's `.mlkit/results/` is absent/unchanged (sha256 of the directory listing), `git worktree list` is back to one entry, no dangling worktree dir |
| T5 | STAMP | `--json-out` | file carries `head_sha`, `base_ref`, `base_sha`, `merge_tree`, `merge_commit`, `phase`, results; the merge commit's parents are exactly `[head_sha, base_sha]` |
| A1 | CONTAINED | commit on `main` | `mlkit ancestry --base main <sha>` → CONTAINED, exit 0 |
| A2 | NOT CONTAINED | commit on a side branch merged into a *third* branch (the #106/#127/#182 shape) | NOT CONTAINED in `main`, exit **1**; CONTAINED in the third branch |
| A3 | UNRESOLVABLE | a ref that does not exist | exit **2**, nothing asserted |
| R1 | REAL | this PR's own head merged with `origin/main` (`3bf16dd`) | tree == head tree (T3 for real, since the stack is linear on main) — recorded in the PR body |

**Falsifier:** a `--merged-with` drive whose statuses differ from the plain
drive when the merged tree equals the branch tree means the command measures
something other than the tree; a conflict that is "resolved" by any strategy
is a stop.

## What is NA, said now

The E-069 reproduction on torrent `cec1c48` merged with `5052c71` needs the
check that sees a stale quotation (R13, plan M-2), which does not exist on this
branch. The merged **tree** for that pair is constructed here as a mechanics
demonstration (stamp + both parents) and the R13 verdict on it belongs to M-2's
controls. Binding-dependent checks on a merged worktree run without any
gitignored staged data (the worktree holds committed content only) — with M-1
that renders UNMEASURABLE once adopters raise `InputUnavailable`; today it
renders as it does on any clean clone.
