# Post-merge verification of #38 / #40 / #41 on `main`

The merges landed; the proof did not. The agent that executed them was killed by a
session limit **during** its verification step, so `main` carried three PRs that
touched `checks/decision.py`, `core/served.py`, `checks/readiness.py` and
`core/coverage_evidence.py` in overlapping regions, merged inside 85 seconds of each
other, with the integration proof never re-run afterwards. This file is that proof,
run against `main` and nothing else. Nothing here changes a gate, a threshold, a
range or a test.

- verified commit: `9d4e8780245d6fc5e9fa5a804a5fab747705c3e6` (`origin/main`, confirmed by `git ls-remote`)
- build: `resilient_mlkit 0.6.0`, `0.6.0+src.a9c4e75e71a4`,
  sha256 `a9c4e75e71a4d6f87a49a0a70e26d497a4e22ee2698b9208a93edd7f15a6ca61` over 33 shipped files
- interpreter: python 3.14.6, fresh clone from the remote, `pip install -e ".[test]"`

## 0. The tree under test is the tree that was measured

Every driver below asserts `module.__file__` before it reports anything, because this
campaign has already been fooled once by verifying an installed copy and returning a
plausible pass. The suite run additionally carries a `pytest_configure` plugin that
asserts the resolved path of all five modules the merges touched, inside the test
process:

```
__file__ OK resilient_mlkit                        -> <clone>/src/resilient_mlkit/__init__.py
__file__ OK resilient_mlkit.checks.decision        -> <clone>/src/resilient_mlkit/checks/decision.py
__file__ OK resilient_mlkit.core.served            -> <clone>/src/resilient_mlkit/core/served.py
__file__ OK resilient_mlkit.core.coverage_evidence -> <clone>/src/resilient_mlkit/core/coverage_evidence.py
__file__ OK resilient_mlkit.checks.readiness       -> <clone>/src/resilient_mlkit/checks/readiness.py
__version__ = 0.6.0
```

## 1. Suite count against the 1195 baseline #43 claims

`1195 passed, 0 failed, 0 skipped in 74.89s` — **matches the baseline exactly.**
Re-run under the `__file__`-asserting plugin: `1195 passed in 73.28s`.
Targeted re-run of the ten suites covering the four merge-touched modules:
`395 passed`.

### The count is conditional on a sibling checkout, and that is worth writing down

`tests/test_torrent_model_of_record.py` reads a real `resilient-torrent` checkout at
`<portfolio root>/resilient-torrent` and skips on `(TORRENT_ROOT / ".git").exists()`.
Three of the 1195 are those tests. A first run of this verification, in a scratch
directory that happened to contain a **git worktree stub** for `resilient-torrent`
(`.git` is a *file* whose `gitdir:` points at a checkout this environment cannot
read), scored `3 failed, 1192 passed`: the guard saw a `.git` that exists, declined
to skip, and the three tests failed reporting artifacts "absent from HEAD".

The 1192/1195 delta was NOT mlkit. Same commit, same suite, same interpreter, with a
genuine `resilient-torrent` clone as the sibling instead: `1195 passed`. Recorded
here rather than repaired, because tightening a skip guard is a change to a test and
this verification does not make them.

## 2. D2 and E1 control pairs, driven on the merged result

`scripts/d2e1_control_pairs.py` (library) and `scripts/d2e1_control_pairs_cli.sh`
(`mlkit check`, a separate process — a same-block artifact is not an independent
witness). Both agree:

| arm | input | D2 | E1 |
|---|---|---|---|
| A | UNDECLARED, fray's honest measured figures | `FAIL` **halt** (the documented naive-binding trap) | `FAIL` on contract, no halt |
| B | DECLARED, the same figures — honest input | `PASS` **silent** | `PASS` **silent** |
| C | DECLARED, a placebo that beats the floor + a curve flat 10%→25% | `FAIL` **HALT** | `FAIL` **HALT** |

Arm C, verbatim from the merged tree:

```
D2  placebo estimate 17 with CI [8, 26] excludes zero, on the 'above' side this repo
    declared indicting; the estimator is capturing something other than the
    intervention. HARD STOP — do not tune, do not scale, do not schedule a training run.
E1  curve is flat between 10% and 25% (gain +0.250% <= 1.0%); the bottleneck is labels,
    not compute. HARD STOP — do not scale.
```

Both halts still FIRE on a genuinely leaking placebo and a genuinely flat curve, and
stay SILENT on honest declared input, after the three merges. The declared-estimand
contract from #35 is present and load-bearing on `main`: `PLACEBO_SECTION`,
`PLACEBO_KEYS`, `INDICTS_ABOVE`, `INDICTS_BELOW`, `INDICTS_EITHER`, `DEFAULT_NULL`,
`HaltRegion`, `read_halt_region` — 8 symbols, all reached by arm B, which is the arm
that only passes because the declaration exists.

## 3. #40's evidence-based CI assertion, driven

#40 deleted `test_the_workflow_does_not_claim_a_run_it_never_had` (a literal-string
assertion) in favour of `test_the_workflow_describes_its_own_execution_from_evidence`.
The predicate was driven on the real committed header and on six mutations:

| input | verdict |
|---|---|
| the real committed `.github/workflows/ci.yml` header | **ACCEPTED** — 6 citations, dated |
| header denying a run it had (`UNVERIFIED AS COMMITTED`) | CAUGHT |
| the same denial as a synonym (`has never executed`) | CAUGHT |
| **another repo's run** (`resilient-fray/actions/runs/1234`) | **REJECTED** — 0 citations |
| unsourced green claim, no denial and no citation | CAUGHT |
| real header with the denial re-injected | CAUGHT (check is not dead) |
| real header with every citation stripped | CAUGHT |
| real header with the retrieval date stripped | CAUGHT |

The citations are not merely well-formed, they are true. Every run id the header
cites was resolved against the live API: `33499020378` (main `6921e9a`, success),
`33562502701`, `33560677454`, `33558666743` — all `completed`/`success`. CI has also
genuinely run on the merged head itself: run `33602017658`, sha `9d4e878`, success,
2026-09-02T07:07:19Z. The header's former denial is therefore false and its deletion
is a strengthening, as #40 claimed.

## 4. Readiness regenerated, never restamped

`mlkit check --phase readiness` was run twice against **one** set of fleet checkouts,
reset to `HEAD` between runs: once with pre-merge `main` (`6921e9a`, mlkit 0.5.0) and
once with post-merge `main` (`9d4e878`, mlkit 0.6.0).

**Across all 96 cells (8 repos x 12 checks): 0 status changes, 0 detail changes.**
Both runs: `FAIL=42  NA=39  PASS=15`. What moved is the build stamp and nothing else —
`mlkit 0.5.0` to `mlkit 0.6.0` in the header, and `measured by mlkit:
0.6.0+src.a9c4e75e71a4` now appearing in the artifacts. That is exactly #40's claim
and no more.

Regeneration did not restamp. R8 refused in every repo and said so in the artifact it
did write:

> `readiness.md` is unchanged at sha256 `0faaddb5...`. Whatever it says was measured
> by whichever interpreter last wrote it; this run did not touch it.

`git diff -- reports/readiness.md` is empty in every repo afterwards. This interpreter
cannot import `torch`/`pandas`, so R1–R6 are unmeasurable here and the refusal is the
correct outcome; the readiness comparison above is therefore load-bearing for R9–R12
(which ran genuinely) and is a comparison of refusals for R1–R8.

## 5. #43 carries nothing that is not already on `main`

Confirmed from the tree, not from the `DO-NOT-MERGE` title.

```
main tree:  d9307bd45ba665fd531c1efd370527a35b6e82ce
pr43 tree:  d9307bd45ba665fd531c1efd370527a35b6e82ce
git diff --name-only main origin/pr43   ->  0 files
git merge-tree $(git merge-base main origin/pr43) main origin/pr43  ->  empty
```

`origin/pr43` (`0870f2a`) is **byte-identical in tree** to `main`. Its three
commits above the merge base are merge commits only. Merging it would re-apply
landed content and change no file. Nothing it carries needs rescuing. It should stay
open, or be closed — it must not be merged.

Incidentally this settles a second question. PR #38's own merge commit `d907e6f4` is
**not** an ancestor of `main`: it was merged into `feat/dependence-unit-contract`,
which had itself already merged to `main` as #32 twelve minutes earlier. #38's
content nevertheless reached `main`, by way of its head branch tip `210f192`, which
*is* an ancestor. The identical trees above are the proof that no #38 content is
missing.

## 6. The hard stops are NOT ARMED in any adopter — read this before scheduling a run

Measured, at each repo's `main`, through `mlkit check`, not inferred:

| repo | sha | D2 | E1 |
|---|---|---|---|
| fray | `ec17a72` | **NA** — no `placebo_test` binding in `.mlkit/repo.toml` | **NA** — no `scaling_probe` binding |
| chokepoint | `5a61e01` | **NA** — no `placebo_test` binding | **NA** — no `scaling_probe` binding |
| torrent | `373d935` | **NA** — no `placebo_test` binding | **NA** — no `scaling_probe` binding |

The only occurrences of those two names in any of the three `.mlkit/repo.toml` files
are inside a comment block documenting the binding shapes (lines 31 and 33 of each).
There is no `[bindings]` entry, no `[placebo]` section and no `[scaling]` section in
any of them.

mlkit's D2 and E1 are implemented, tested, and — as §2 shows — demonstrably able to
fire. They are armed in **zero** adopters. An overnight training result produced
under this configuration would have no working hard stops behind it, and could not be
trusted on that ground alone regardless of what it reported. This is a fact about the
three model repos, not about this merge, and it is written here because a report that
omitted it would be the more dangerous artifact.
