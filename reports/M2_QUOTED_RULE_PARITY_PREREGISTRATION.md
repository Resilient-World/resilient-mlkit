# M-2 — R13 QUOTED RULE PARITY: the stale-quotation scan as a fleet check — PREREGISTRATION

**Written 2026-09-04, BEFORE any code on this branch. First commit of
`feat/v3-m2-r13-quoted-rule-parity`, based on M-3's head `b1b046e` (PR #47),
which is based on M-1 `e494ab5` (PR #46).** Plan item: `sota-plan-v3.md` §7 M-2.

## The defect (STATE.md 2026-09-04, quoted)

torrent's `src/torrent/mlops/hard_stops.py:48` at `cec1c48` stored the
pre-amendment D2 sentence. It was true on its branch, false at the merge with
S-5 (`main` `5052c71`), and "invisible to single-PR review by construction". The
S-5 scanner's stale-quotation mode caught it — on a merged tree, by hand.
chokepoint and fray still store typed copies (`src/resilient_chokepoint/mlops/
hard_stops.py:104–110`, `scripts/report_hard_stops.py:29–32`), disclosed in the
register's `source_files_quoting_the_replaced_sentence`. Each of the three repos
carries its own copy of `scripts/verify_one_sided_placebo_register.py --mode
check` to find such sites; three copies of a check is rule 7's failure mode.

## Measurements taken BEFORE writing the check, which fix its boundary

Driven on detached worktrees at the three mains (fray `76f0dde`, chokepoint
`512ab25`, torrent `d34649f`), `git grep` against `HEAD`:

1. `mlkit_bindings.py` at the root of each repo quotes **neither** clause on any
   main. The plan's surface (`src/`, `scripts/`, `mlkit_bindings.py`) therefore
   agrees with the S-5 scanner's (`[source] trees` = `src`, `scripts`) on what
   is quoted today.
2. The **superseded** D2 clause ("…confidence interval excludes zero") appears
   on chokepoint main in **committed artifacts** under `reports/benchmarks/`
   (`foundation_full_val_ladder.json`, `foundation_per_corridor_cqr.json`, their
   `.md` twins) as the labelled `claude_md_literal_reading` — a historical quote
   the E-056 repair deliberately kept — and on fray main in `reports/hard_stops.md`.
   An artifact cannot "match the current text" without being REGENERATED, and
   regenerating chokepoint's needs the pinned parquet. So `reports/` is a
   **disclosure surface**, never a verdict surface: quotations there are
   counted and listed as `tied` (the file carries the current CLAUDE.md sha256)
   or `untied`/`stale` (regenerate, never restamp), and they do not FAIL.
3. torrent main's `hard_stops.py` docstring **paraphrases** the current D2
   clause with a longest shared run of **5** consecutive words ("the
   preregistered [placebo] declaration indicts"). A "second copy" must be a
   verbatim run long enough not to be a paraphrase naming the rule's subject.
4. **Every main's S-5 scanner script quotes the current clause verbatim in its
   docstring** (lines 5–6). The S-5 scanner exempts itself by a typed path
   constant. The register names its enforcement in its own vocabulary —
   `how_this_is_enforced.scanner` = `"scripts/verify_one_sided_placebo_register.py
   --mode check"` — so R13 exempts the ENFORCEMENT file from the register, not
   from a list.
5. **fray main carries an unlisted typed copy of the E1 clause**:
   `scripts/measure_nass_condition_block.py:956` emits *"CLAUDE.md halts this
   repo on an E1 scaling curve that is flat between 10% and 25% of the data…"*
   into an artifact's `statement` field — a hand-written sentence about a rule,
   in source, emitted. The register does not list it. **The generalised
   NO-SECOND-COPY control is therefore predicted to FIRE on fray main**, and the
   plan's "silent on the three mains" holds only for the stale-quotation class.
   The prediction is written here so the drive can falsify it.

## What changes (fixed now)

**R13 — QUOTED RULE PARITY** (`checks/parity.py`), appended to the readiness
phase after R12 (an AST/text walk: imports nothing, reads committed blobs at
HEAD, never guarded by the environment probe; denominator 12 → 13).

- **Clauses.** Current = the bullets under `## Hard stops` in `CLAUDE.md` at
  HEAD (normalised: markdown emphasis and backticks stripped, whitespace
  collapsed, trailing `;.` removed; identity = the clause's `D2`/`E1` marker).
  Superseded = every distinct bullet under the same heading in every PRIOR
  committed version of `CLAUDE.md` on the tree's history (`git log --
  CLAUDE.md`), ∪ the register's `the_rule_it_replaces` when a register exists,
  minus the current ones. **Not a retyped list, in any adopter.**
- **Tokens.** lowercase alphanumeric runs (`10%` → `10`, `[placebo]` →
  `placebo`, `(S-5)` → `s`, `5`). The clause digest is sha256 over the token
  sequence, so reflowing, re-quoting or re-wrapping a quotation changes nothing.
- **STALE_QUOTATION**: a file on the verdict surface contains a window of
  **W_STALE = 4** consecutive tokens of a superseded clause that occurs in no
  current clause. (4 is the length of the register's own replaced phrase.)
- **SECOND_COPY**: a file on the verdict surface contains a window of
  **W_COPY = 8** consecutive tokens of a current clause. (Measurement 3: 8
  separates a paraphrase naming the rule from a copy of it.)
- **Verdict surface**: committed files at HEAD under the repo's `[source]
  trees` (default `src`, `scripts`) plus `mlkit_bindings.py`, text-decodable.
  **Disclosure surface**: committed files under `reports/`.
- **Exemptions, from the register at HEAD** (`docs/one_sided_placebo_register.json`,
  keyed through `repo_identity`): files in `source_files_quoting_the_replaced_
  sentence[...]` → `REGISTERED` (disclosed, counted, not failing); the path in
  `how_this_is_enforced.scanner` → `ENFORCEMENT` (same). A site that is neither
  → **FAIL**, naming file, line, class, the window and the clause it copies.
- NA only when `CLAUDE.md` or its `## Hard stops` section is absent.
- Evidence: `claude_md_sha256`, per-clause `clause_sha256`, superseded clauses
  and where they came from, findings, registered/enforcement sites, the
  disclosure listing, the window sizes.

Nothing else moves. Existing verdict rows are untouched; R13 is a new row.

## Acceptance — controls fixed before the code

| id | direction | fixture / tree | required |
|---|---|---|---|
| K1 | FIRES (historical) | torrent `cec1c48` merged with `5052c71` via `core.merged` | `STALE_QUOTATION` at `src/torrent/mlops/hard_stops.py`, register-unlisted → FAIL |
| K1′ | SILENT for that class on the branch | torrent `cec1c48` alone | no `STALE_QUOTATION` (the clause was current there); `SECOND_COPY` fires — the generalised control — and is reported as such |
| K2 | THE THREE MAINS, predicted | fray `76f0dde`, chokepoint `512ab25`, torrent `d34649f` | chokepoint: **0 problems** (2 sites REGISTERED; ENFORCEMENT exempt); torrent: **0 problems**; fray: **1 problem** — `SECOND_COPY` at `scripts/measure_nass_condition_block.py` (E1), plus REGISTERED `scripts/report_hard_stops.py`. If fray reads 0, the E1 window logic is dead; if chokepoint/torrent read >0, the exemptions are wrong |
| K3 | FIRES | a docstring quoting the current clause verbatim (author's first fix) | `SECOND_COPY` |
| K4 | REGENERATE-NOT-RESTAMP | K3's quotation reflowed over three lines, quotes swapped, markdown added | same finding, same `clause_sha256` |
| K5 | SILENT | a paraphrase sharing ≤ 5 tokens; a file mentioning "placebo" and "interval" everywhere; a two-sided halt predicate | 0 findings (the useless-scanner falsifier: 18×/25×/2× was measured and rejected by S-5.1) |
| K6 | REGISTERED / CHECK-NOT-DEAD | the K3 file listed in a register at HEAD → `REGISTERED`, PASS; the listing removed → FAIL | both |
| K7 | NA | no `CLAUDE.md` | NA naming the absence |
| K8 | DISCLOSED, NOT FAILED | a `reports/x.json` quoting a superseded clause | PASS with the artifact listed under `artifacts` as stale |
| K9 | HISTORY | a fixture whose CLAUDE.md was amended in git; a file quoting the old bullet | `STALE_QUOTATION`, and the evidence names the commit the superseded clause came from |

**Falsifier:** a scan that fires on every file quoting the word "placebo" is
the useless scanner S-5.1 measured and rejected; K5 is that falsifier.

## What is NA, said now

The three repos' `verify_one_sided_placebo_register.py --mode stale-quotations`
copies are **not retired here** — that is each repo's own change on its next
repin (rule 7 is adopted by the repo that owns the call sites). R13 is driven
on the three mains from mlkit's own checkout with a bare interpreter; that is
admissible because R13 imports nothing from the repo.
