# E-M42 RESULTS — every reading, against the acceptance rule fixed beforehand

Read with `reports/E_M42_REPORT_HEADER_PREREGISTRATION.md`, which fixed the
acceptance rule, the arms and the version rule as this branch's first commit.
Every number here is a reading; nothing is recalled.

## 1. THE INVENTORY — where mlkit can write a path into text it produces

Static, AST-based, over `src/resilient_mlkit`: every f-string interpolation of
a name that is or is built from a filesystem `Path`. **57 sites.** They are not
57 defects — most interpolate a REPO-RELATIVE path (which is the blessed shape)
or go to a terminal. The ones that can reach an artifact a repo commits:

| site | verdict |
|---|---|
| `identity.running_code_is_covered_or_reason` `{me}` | **DEFECT — repaired.** Absolute path of the loaded module, into `unavailable` → `context_line()` → the `mlkit build:` header of every stamped report |
| `identity.running_code_is_covered_or_reason` `{root}` ×2 | **DEFECT — repaired.** Absolute package root, same path to the same header |
| `identity.digest_tree` reasons | already `root_as_kind` (M-5) |
| `identity._vcs_of_installed_dist` reasons | already `root_as_kind` / "a local `file://` directory" (M-5) |
| `identity.one_tree_or_reason` | already `root_as_kind` (M-5) |
| `BuildIdentity.context_line` / `to_dict` | already `root_kind` + `root_name` (M-5) |
| `identity.verify_report` `could not read {p}` | **not a defect.** `mlkit identity --verify` prints it to a terminal, and `p` is the path the CALLER typed. Echoing a caller's own argument back is what tells them which file they asked about; it reaches no artifact |
| `report._render_refusal` (`.UNMEASURABLE.md`) | writes no path of its own; now guarded anyway |
| `artifact.py`, `fleet.py`, `merged.py`, `served.py`, `readiness.py`, `register.py`, `declaration.py`, `fabrication.py`, `fabricated_targets.py`, `selection.py`, `cli.py` | repo-relative or terminal-only; none reaches a stamped report with an absolute value, and all report text is now behind the writer's refusal |

**And one PRODUCER defect, which is the reason this is a fleet fix.**
`core.report.guarded_write` — the single funnel for the four stamped reports —
wrote them with a bare `path.write_text`. mlkit has owned
`core.artifact.machine_paths_in_text` and `write_text_artifact` (which refuses
on it) since M-5, and **the artifact mlkit puts into eight repositories went
through neither**. Fixing only the three identity sites would fix three sites;
putting the existing refusal on the writer removes the class.

## 2. THE PREMISE, CORRECTED BY MEASUREMENT

| claim | reading |
|---|---|
| arabica's four stamped reports carry an absolute path | **TRUE.** `/private/tmp/claude-501/…/land2/arabica-unlock/mlkit-inst/resilient_mlkit`, all four, on `origin/main` |
| it is written by `core/identity.py:header_lines()` | **TRUE, at the revision arabica pins** (`3bf16dd0`, mlkit `0.6.0`), where `context_line` interpolated `self.root` |
| therefore every stamped repo carries it, today | **FALSE.** M-5 (`6ca1691`, PRs #49/#50, 2026-09-04) replaced the directory with `root_kind` + `root_name`; `3bf16dd0` is an ancestor of it |
| so nothing is left to fix | **FALSE.** The sourceless-install branch still wrote two raw absolute paths into the same line, and the writer refused nothing |

## 3. THE CONTROL ARMS — `reports/E_M42_HEADER_CONTROL_ARMS.json`

Every arm renders in a SUBPROCESS against a materialised package tree, in an
interpreter with **no mlkit distribution installed**: an editable install's
import hook beats `PYTHONPATH`, and the first pass of this drive measured the
clone's own tree four times while reporting success.

| arm | condition | required | read |
|---|---|---|---|
| **A1a** | source-tree import, dirs 17 and 13 components deep | identical, 0 paths | **identical, 0** ✔ |
| **A1b** | **sourceless install**, same two dirs | identical, 0 paths | **identical, 0** ✔ |
| **A2** | two mlkit revisions | headers **DIFFER** | `2.0.0+src.9aae44e332dd` vs `2.0.0+src.047617173ece` ✔ |
| **A3** | **NOT-DEAD**: `identity.py` reverted to `main`, A1b re-driven | must FAIL | **headers DIFFER and carry 4 machine-path tokens** ✔ |
| **P1** | a report naming a machine, offered to the writer | REFUSED, prior byte-identical | refused; prior sha256 unchanged ✔ |
| **P2** | a clean report | written unchanged | written ✔ |

A1a is the arm that passes on `main` too — it pins what M-5 already won. **A1b
is the arm that fails on `main`**, and A3 is that failure driven deliberately.

**The record redacts every machine-path token to its length.** A3's headers ARE
machine paths by construction and this artifact is committed; the first drive
wrote them out verbatim and `machine_paths_in_text` over the record caught it.
The control artifact was, for one run, the defect it controls for.

"Machine path" is judged throughout by `core.artifact.machine_paths_in_text` —
mlkit's own discriminator. A control carrying its own definition of the defect
measures its own definition.

## 4. A4 — THE FLEET, BEFORE AND AFTER, AND NOTHING MOVED

Eight repos at their remote mains, cloned fresh; **five phases each**
(`triage`, `selection`, `readiness`, `decision`, `economics`); one interpreter,
`PYTHONPATH` switched between `origin/main`'s package tree and this branch's;
`resilient_mlkit.__file__` asserted inside the named tree at the head of each
arm; every clone restored to pristine between arms; arms run SEQUENTIALLY.

```
fray cc8f4355   torrent dc6e577a   chokepoint 246e91b2   choco 1a096ca0
arabica c0484718   surge 398fb034   blackout 0ec856d0   triage 9cae0cba
```

```
rows BEFORE 272   rows AFTER 272
added 0   removed 0   STATUS moved 0   reason-only moved 1
```

| repo | BEFORE | AFTER | |
|---|---|---|---|
| fray | ESCALATED 6, FAIL 12, NA 9, PASS 7 | identical | |
| torrent | ESCALATED 6, FAIL 2, NA 23, PASS 3 | identical | |
| chokepoint | ESCALATED 6, FAIL 16, NA 8, PASS 4 | identical | |
| choco | ESCALATED 6, FAIL 16, NA 9, PASS 3 | identical | |
| arabica | ESCALATED 6, FAIL 16, NA 9, PASS 3 | identical | |
| surge | ESCALATED 6, FAIL 12, NA 13, PASS 3 | identical | |
| blackout | ESCALATED 6, FAIL 1, NA 22, PASS 5 | identical | |
| triage | ESCALATED 6, FAIL 2, NA 24, PASS 2 | identical | |

**Zero adjudicated rows added, removed or changed.** This is a producer fix,
and the acceptance rule said it stops here if a row moves.

### The one reason string that moved — and it is a real finding

`fray / readiness / R8`, status **NA** both ways (R8 is the report-write row):

```
BEFORE  refused to write readiness.md from an unmeasurable environment: …
AFTER   refused to write readiness.md: 1 token(s) in the rendered report name an
        absolute directory on the machine that generated it … (at line:col 20:365)
```

The offender, identified by driving it: **fray's own R5 binding reason**, which
ends `… it is derived and gitignored, so a fresh checkout does not carry it.
Path: /private/tmp/…` — truncated by mlkit's reason limit at 33 characters, but
a machine path all the same. **This is fray's string, not mlkit's.** It is left
for fray; no consumer repository was touched. It would have landed in fray's
committed `reports/readiness.md` on any regeneration from a working checkout,
which is exactly the class the fleet has been repairing repo by repo tonight.

(fray's `.gitignore:74 /reports/*` means the refusal file lands untracked
there, so it is visible to the operator and not to `git status` on tracked
files.)

### The report TEXT, compared

22 reports written across the fleet in both arms. Modulo the run nonce and the
build stamp — both of which legitimately differ because the mlkit tree differs
— **15 are byte-identical and 7 differ by exactly one added line**:

```
+- files under a declared tree the derivation could not READ: 0
```

on every one of the seven `fabricated_defaults.md`. That is E-038's restored
disclosure, it reads `0` everywhere, and **no finding row moved on any repo.**

## 5. E-038 — THE LOST VERIFY COMMIT, ESTABLISHED AND RESTORED

```
PR #20   MERGED 2026-08-31T04:13:41Z   mergeCommit 1170a7edf9db…
git merge-base --is-ancestor 1170a7e origin/main   NO
git merge-base --is-ancestor 63682f4 origin/main   NO    the verify commit
git merge-base --is-ancestor b1cc706 origin/main   YES   its parent
git merge-base --is-ancestor 3b7ee52 origin/main   YES   the E-038 fix itself
git diff --stat b1cc706 63682f4   4 files, +341/-7
```

**Exactly one commit of a merged PR is missing.** Its predecessors are on
`main`, so this is not a branch that never landed; it landed and was later
lost. Read on `main`'s tree rather than inferred from the diff, all three of
its repairs were absent: `if registry.refusal: return na` stood at
`readiness.py:858` ahead of `if defects:` at 861; `metric_registry.py:442` read
every file unguarded; and no `could not READ` line existed anywhere.

Restored, adapted (the surrounding code moved through E-M41), with ten tests
driving each defect both ways. **The self-only-callable disclosure was
RE-MEASURED** at today's eight mains rather than carried over, because E-M41's
D1/D2 moved every registry size — and the old conclusion is withdrawn:

| repo | registry, shipped | admitting self-only | R10 findings |
|---|---|---|---|
| fray | 58 | 60 (+2) | 0 → 0 |
| torrent | 145 | 164 (+19) | 7 → 19 |
| chokepoint | 117 | 125 (+8) | **0 → 1, PASS → NA** |
| choco | 119 | 128 (+9) | 12 → 12 |
| arabica | 148 | 168 (+20) | 9 → 10 |
| surge | 92 | 101 (+9) | 16 → 16 |
| blackout | 101 | 105 (+4) | 15 → 16 |
| triage | 103 | 120 (+17) | 14 → 15, and `known` 2 → **3** |

The old text said no repo's verdict was bought by the exclusion. **Today one
is** — chokepoint's R10 would move PASS → NA
(`training/data_module.py:176 minority_fraction=0.0`, `UNCLASSIFIED_NAME`) —
and triage's widened universe drags in a name mlkit's built-in vocabulary
already classifies, which is the precision cost that keeps the exclusion.

## 6. THE SUITE, RUFF AND MYPY

See the PR body for the landed arms. One reading that belongs here because it
is about `main` and not about this branch: **mlkit's own `ruff` job was RED on
`main`** — run `34088101903`, the CI for the merge of #57: pytest 3.11 PASS,
pytest 3.12 PASS, mypy PASS, **ruff FAIL in 6 s**, 3 findings at the pinned
`ruff==0.16.5`. Unlike the private repos' red CI (3–5 s, `"steps": []`, nothing
executed), this job ran and the findings are real. Repaired here,
semantics-preserving, because a gate that is red before a branch starts cannot
tell that branch's findings from the ones already there.

## 7. WHAT WAS NOT DONE, AND WHY

1. **arabica's four committed reports still carry the path.** They were written
   by mlkit `0.6.0` at `3bf16dd0`, which is what arabica pins. Only arabica can
   change them, in a pin-moving PR with an A/B on every gate row. Not this
   lane's, and no consumer repository was pushed to.
2. **fray's R5 binding reason is not repaired.** It is fray's source. Named
   here and in `loop/repair/mlkit-header-adoption.md`; not touched.
3. **No `<report>.NAMES_A_MACHINE.md` is written into any consumer repo by this
   lane.** The fleet drive ran in throwaway clones.
4. **No gate file, threshold, range or holdout edited. No allowlist. No D1/D4/
   D5, E4/E5, S5 record, IAM or billing. No tag cut** — E-M08, the signatory's.
5. **`STAMP_PREFIX`, `DIGEST_CHARS`, `digest_tree` and `shipped_files` are
   byte-unchanged.** Five repos parse that token in a committed test; a test in
   this branch asserts the shape and recomputes the digest construction by hand.
6. **The refusal reports positions, not tokens.** A reader who needs the token
   gets it from `MachinePathRefused` on the terminal. That is deliberate and it
   is a cost: the committed record alone does not name the offender.
7. **`#45` untouched.** It remains the only other open PR.
