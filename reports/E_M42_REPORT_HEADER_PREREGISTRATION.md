# E-M42 PREREGISTRATION — a report header that names a machine, and the producer that writes it

Committed as the FIRST commit of this branch, before one source byte moved.
Everything below — the acceptance rule, the arms, the version rule, and the
list of things that must NOT change — is fixed here so that none of it can be
chosen afterwards to fit a reading.

## 0. THE PREMISE HANDED TO THIS LANE, AND THE CORRECTION MEASURED BEFORE ANY EDIT

The lane was opened on: *"arabica's four stamped gate reports embed an ABSOLUTE
MACHINE PATH in their `mlkit build:` line, and the line is written by mlkit's
own `core/identity.py:header_lines()`, so every repo whose reports mlkit stamps
carries it."*

**Half of that is true and half of it is already repaired.** Measured, not
assumed, before any edit:

* **The reports do carry it.** `resilient-arabica` `origin/main`, all four
  stamped reports (`reports/fabricated_defaults.md`, `fabricated_targets.md`,
  `readiness.md`, `served_contract.md`), read through
  `gh api repos/Resilient-World/resilient-arabica/contents/…?ref=main`:

  ```
  - mlkit build: sha256 `a9c4e75e…` over 33 shipped file(s) in
    `/private/tmp/claude-501/…/scratchpad/land2/arabica-unlock/mlkit-inst/resilient_mlkit`;
    installed from vcs `3bf16dd0b0c8281a844f6d39554e5369016d4c6b`
  ```

* **But that is mlkit `0.6.0` at `3bf16dd0`, which is what arabica PINS**, and
  at that revision `BuildIdentity.context_line()` interpolated `self.root`
  directly (`identity.py:177,181` at `3bf16dd0`). **M-5 removed it on
  2026-09-04** (PRs #49 `6ca1691` / #50), replacing the directory with
  `root_kind` + `root_name`. `git merge-base --is-ancestor 3bf16dd0 main` → YES,
  and M-5 lands after it.

* **So the ordinary case is already fixed on `main` today, and this is
  measured, not read off the diff.** Two copies of `main`'s package tree at two
  different absolute paths, rendered with no mlkit dist installed:

  ```
  A  /…/scratchpad/hdr/A/a/b/c/d/e/checkout/src   header sha  → identical
  B  /…/scratchpad/hdr/B/zz/checkout/src          header sha  → identical
  both:  - mlkit build: sha256 `047617173ece…` over 41 shipped file(s) in
         `resilient_mlkit` (checkout); vcs commit NA — no installed
         resilient-mlkit distribution was found; …
  ```

  Byte-identical. No absolute path. **The premise's headline defect is not
  live on `main`.**

* **The defect IS still live at the same site, on one branch M-5 missed.**
  `identity.running_code_is_covered_or_reason()` (`identity.py:569,573`)
  interpolates **two raw absolute paths** — the file this module was loaded
  from, and the package root. Its return value becomes
  `BuildIdentity.unavailable`, which `context_line()` renders **into the
  `mlkit build:` header line of every stamped report**. Driven on `main`
  today, in a sourceless (bytecode-only) install — the exact condition that
  branch exists for — from the same two directories:

  ```
  A  - mlkit build: tree `resilient_mlkit` (checkout) was NOT hashed — the file this
       module was loaded from (`/private/tmp/…/hdr/AS/a/b/c/d/e/checkout/src/resilient_mlkit/core/identity.pyc`)
       is not among the 1 file(s) the digest would cover under /private/tmp/…/hdr/AS/a/b/c/d/e/checkout/src/resilient_mlkit; …
  B  - mlkit build: … (`/private/tmp/…/hdr/BS/zz/checkout/src/resilient_mlkit/core/identity.pyc`)
       … under /private/tmp/…/hdr/BS/zz/checkout/src/resilient_mlkit; …
  ```

  **Two absolute paths each, and the two headers DIFFER.** That is the same
  defect the premise names, at the same function, in the branch that renders
  when the digest cannot be taken — i.e. in exactly the case where the header
  is the only thing a reader has.

The correction matters for what this lane can claim. It cannot claim to remove
the path from arabica's committed reports: those were written by the revision
arabica pins, and only a pin-moving PR in arabica can change them (§5). It can
claim to remove the last site in mlkit that can put one there, and to make the
producer refuse rather than write one — which is what "at its root" means here.

## 1. THE SECOND DEFECT, AT THE PRODUCER

mlkit already owns the discriminator for this whole class:
`core.artifact.machine_paths_in_text()` and `write_text_artifact()`, shipped by
M-5, which REFUSE to write an artifact naming a machine.

**The four stamped reports do not go through it.** They are written by
`core.report.guarded_write()`, which calls `path.write_text(content)` directly
(`report.py:108`). So mlkit's own refusal has never guarded the artifacts mlkit
stamps into eight repos — the writer that would have caught the header line was
not on the path the header line takes. Any future site in mlkit that leaks a
directory into report text lands in a committed file with nothing in between.

Fixing only `identity.py` fixes one site. Putting the existing refusal on the
report writer removes the class at the producer, which is this lane's subject.

## 2. THE ACCEPTANCE RULE (fixed here; no arm is added or dropped afterwards)

The change is ACCEPTED only if **all five** hold:

**A1 — FIRES / no path.** For BOTH install conditions — (a) a source-tree
import from a deep path, (b) a **sourceless / bytecode-only** install from a
deep path — the header rendered from two DIFFERENT absolute directories is
**byte-identical**, and neither header contains any token that
`core.artifact.machine_paths_in_text()` calls a machine path. Condition (b) is
the one that fails on `main` today; (a) is included so the arm also pins what
M-5 already won.

**A2 — SILENT / still informative.** The identity still tells two genuinely
different builds apart: two package trees at two different mlkit **revisions**
render headers that **DIFFER**. A stamp that no longer identifies its build
would be worse than one carrying a path, and this arm is what stops the fix
from buying A1 by emptying the line.

**A3 — CHECK-NOT-DEAD.** With `core/identity.py` reverted to `main`'s version
and nothing else changed, **A1(b) FAILS** — the two headers differ and carry
absolute paths. An arm that passes on the unrepaired tree measures nothing.

**A4 — NO GATE ROW MOVES.** mlkit's checks driven over the fleet clones BEFORE
and AFTER, compared as sets of adjudicated rows: **zero rows added, removed or
changed.** This is a producer fix, not a judgement change. **If any row moves,
this lane STOPS and reports it rather than landing.**

**A5 — the suite.** Full mlkit suite plus `ruff` and `mypy` on the merged tree
against a `main` baseline in ONE clone, arms SEQUENTIAL, failure sets compared
BY NAME, no `-k`. Baseline is 0 failures. Nothing may be only-on-branch, and
lint/type findings must stay at zero.

**WITHDRAWAL.** If A2 cannot be met — if the only way to remove the path is to
remove information that distinguishes builds — the identity half does not ship
and the lane reports that instead. If A4 moves a row, nothing ships.

## 3. THE CONTROL ARMS, NAMED BEFORE THEY ARE DRIVEN

| arm | condition | required |
|---|---|---|
| **A1a** | source-tree import, two directories, repaired tree | headers byte-identical, 0 machine paths |
| **A1b** | **sourceless install**, two directories, repaired tree | headers byte-identical, 0 machine paths |
| **A2** | two different mlkit **revisions**, same directory | headers **DIFFER** |
| **A3** | `identity.py` reverted to `main`, arm A1b re-driven | **FAILS** (headers differ, machine paths > 0) |
| **A4** | fleet drive before/after, adjudicated rows | 0 moved |
| **P1** | a report whose text names a machine offered to the writer | **REFUSED**, prior report preserved byte-for-byte |
| **P2** | a report whose text names no machine | **written**, unchanged from today |

`P1`/`P2` are the producer half: the refusal must fire on a poisoned rendering
and stay silent on a clean one, or it is either useless or a new way to lose a
report.

## 4. WHAT MUST NOT CHANGE

* **Every adjudicated gate row**, on every fleet repo, before and after (A4).
* **Every measured figure** in any committed report or artifact in this repo or
  any other. Nothing is regenerated in a consumer repo by this lane.
* **The stamp token itself** — `STAMP_PREFIX`, the `version+src.digest` shape,
  `DIGEST_CHARS`, and what goes into `digest_tree()`. The adopter-side check
  (`verify_report`, and the pin tests in five repos) parses that line, and a
  change to it would move a check in every repo that reads it. **The digest of
  a given package tree must be byte-identical before and after this change**,
  which is asserted directly.
* **No gate file, threshold, range or holdout**, here or anywhere.
* **No allowlist entry**, no D1/D4/D5, no E4/E5, no S5 record, no IAM/billing,
  **no tag cut** (E-M08: the signatory's).
* **No consumer repository is pushed to.** The migration consequence is
  WRITTEN (§5), never performed.

## 5. THE MIGRATION IS STATED, NOT PERFORMED

Every repo's committed reports were written by the mlkit revision that repo
pins. None of them changes because of this PR. When a repo next moves its pin
to a revision at or after this one AND regenerates, its report header text
changes, so **its freshness stamp and any digest that pins a report move with
it**. That is each repo's own pin-moving PR, with an A/B on every gate row, and
this lane writes the per-repo consequence into
`loop/repair/mlkit-header-adoption.md` and pushes to no consumer.

## 6. THE VERSION RULE, DECIDED BY MEASUREMENT

`CHANGELOG.md`'s own scale: **major** — an existing check changes verdict on
unchanged code; **minor** — a new check exists, or a report or CLI surface
changes; **patch** — a defect in the instrument is fixed with no verdict change.

* The identity repair alone is a **patch**: a defect fixed, no verdict moved.
* But this branch also adds a **refusal path to the report writer** and (§7) a
  **new line to R10's report**. Both are report-surface changes, so the floor
  is **minor → v2.1.0**.
* If the A4 fleet drive shows **any check's verdict moving on unchanged repo
  code**, the scale calls that **major → v3.0.0**, and it is taken rather than
  argued down, exactly as v2.0.0 was.

Decided by the A4 reading, not by preference. `tests/test_version_declaration.py`
holds `__version__` against the newest `CHANGELOG.md` heading and is not edited.

## 7. THE SECOND SUBJECT: mlkit `main` HAS LOST THE E-038 VERIFY LINE

Recorded by the pin lane and established here on `origin/main` today rather
than repeated from the record:

```
PR #20  "VERIFY E-038: the R10 registry repair STANDS; two defects in it repaired"
        state MERGED, mergedAt 2026-08-31T04:13:41Z, mergeCommit 1170a7edf9db…
git merge-base --is-ancestor 1170a7e origin/main   ->  NO
git merge-base --is-ancestor 63682f4 origin/main   ->  NO     (the verify commit)
git merge-base --is-ancestor b1cc706 origin/main   ->  YES    (its parent)
git merge-base --is-ancestor 3b7ee52 origin/main   ->  YES    (the E-038 fix itself)
```

**Exactly one commit of a merged PR is missing from `main`** — the verify
commit, `+341/-7` across four files. The two commits under it are present, so
this is not a branch that never landed; it landed and was later lost. Read on
`main`'s tree today, three separable pieces are genuinely absent:

1. **R10 adjudicates the derivation refusal BEFORE the defect lane**
   (`readiness.py`: `if registry.refusal: return na` at line 106, `if defects:`
   at 109). A repo with a measured `SATISFIES_GATE` default and a broken
   derivation is reported **NA** — "could not measure" standing in for
   "measured, and it is wrong".
2. **`metric_registry.derive()` reads every file unguarded**
   (`metric_registry.py:442`). One unreadable file under a declared tree —
   a dangling symlink is enough — and R10 raises where the scanner beside it
   skips.
3. **The R10 report line** `files under a declared tree the derivation could
   not READ: N`, and the `unreadable` field behind it.

This lane restores the check **in its own commit, with a control that fires**,
adapted to today's tree rather than cherry-picked blind (the surrounding code
has moved through E-M41). Item 1 can move a verdict; whether it does is an A4
reading over the fleet, and it is what §6's major clause is for.

## 8. ENVIRONMENT AND PROCESS, FIXED IN ADVANCE

* Fresh plain clone; `.venv/` and `.venv-*/` in `.git/info/exclude` before the
  venvs existed; local git identity `David Izikowitz <david@resilient.world>`
  set before the first commit.
* A venv INSIDE the clone (`pip install -e ".[test]"`) with
  `resilient_mlkit.__file__` asserted to resolve inside it before any reading —
  the shared venv on this host carries an editable path to a different clone
  and would silently measure that one.
* Arms run SEQUENTIALLY. No `-k`. Failure sets compared BY NAME.
* No credential read, printed, logged or written. `#45` untouched.
* Fleet clones are read-only; nothing is pushed to any of them.
