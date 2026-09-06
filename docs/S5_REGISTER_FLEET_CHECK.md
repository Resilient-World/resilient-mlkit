# S-5 — the register fleet check, and the pre-landing obligation it should carry

**Status: the COMMAND is built and driven here (v1.1.0). The PIN that makes a
repo refuse a register edit without a fresh run is built here too (v1.3.0,
E-M39 amendment): the run writes a sealed artifact, and a one-line test in
each register-carrying repo asserts the artifact licenses the register at
`HEAD`.** §3 carries the artifact contract and the exact test to paste into
`resilient-fray`, `resilient-chokepoint` and `resilient-torrent`. Nothing in
mlkit edits any of them; the paste is the owning agent's. What stays the
signatory's is stated in §2 and has not moved.

## 1. What the command is for

`docs/one_sided_placebo_register.json` is **one document kept in three
repositories**. `canonical_body_sha256` exists so that a drift between the
copies fails in whichever copy drifted. It cannot do that on its own, and
torrent **E-080** measured the consequence: on 2026-09-05 there were **four live
bodies at once**, and

> Every copy was internally consistent, so `--mode check` returned
> `0 problem(s)` in all three repos, and every repo's test suite was green on the
> constant it had pinned. The invariant is BETWEEN the repos. Nothing in any repo
> can see the other two, so nothing runs it.

Each repo had repaired its own site, **zeroed its own entry** in
`source_files_quoting_the_replaced_sentence`, and written in prose that the other
repo was still stale. Both statements were false, and neither repo could ever
learn otherwise, because the only reader who could was a person holding all three
checkouts.

```
mlkit register --check-fleet --root <dir containing the resilient-* checkouts>
```

is that reader.

## 2. Why it is LOCAL, and what would have to happen for it not to be

E-080 named the obvious closure — a fleet CI job that fetches all three blobs —
and named why an agent may not build it: **the repos are private**, so such a job
needs a cross-repo credential, and **CLAUDE.md rule 13** forbids an agent putting
a credential anywhere near this. Standing CI configuration and any cost-incurring
resource are the signatory's under **rule 12**.

So the command reads checkouts that are already on the machine. It fetches
nothing, authenticates to nothing, creates nothing, and writes nothing into any
repo. **Turning it into an automatic gate is the signatory's decision**, and it
has exactly two shapes, both reserved:

* a required status check on all three repos, fed by one credentialed job; or
* making the repos readable to one another, which is the S-10 disclosure question
  already open in `docs/ESCALATIONS.md` E-M37.

Until one of those is taken, the invariant is carried by an **obligation on the
person or agent landing a register change**, which is what §3 proposes. An
obligation is weaker than a gate and this document says so plainly rather than
implying the hole is closed.

## 3. THE PIN — the artifact, the test, and the obligation that is now a check

### 3.1 The run writes a sealed, committable artifact

```
mlkit register --check-fleet --root <dir containing the resilient-* checkouts> \
      --out reports/s5_register_fleet_check.json
```

`--out` writes `artifact_document(...)`: schema
`resilient-mlkit/s5-register-fleet-check/1`; `verdict` (`PASS` / `FAIL` /
`REFUSED`) beside `ok`; the mlkit version and build that measured it; one entry
per copy compared — repo name, `HEAD`, the register's git **blob**, its stored
digest, what **every** repo's own `canonical_body_sha256` computed over it, and
the agreed digest; `identical_blob`; every problem by field; the refusal, if
any; and **`proof_sha256`**, sha256 over the artifact's own canonical body with
that field removed.

Three things about that seal, because each is a way it could have been wrong:

* It is **not a second digest of the register** (rule 7). The register's digest
  is still each repo's committed function, cross-applied. `proof_sha256` seals
  mlkit's RESULT, so an artifact retyped by hand from FAIL to PASS no longer
  verifies.
* The artifact carries **no machine path** — no `--root`, no checkout path —
  and `write_artifact` refuses to write one that would (`core.artifact.
  machine_paths`). The refusal sentence for a run over fewer than two copies
  was reworded for the same reason; the CLI prints `--root` on its own line.
* It is written for **every verdict**. A FAIL or REFUSED artifact is an honest
  record that the pin below will refuse; withholding it so a tree keeps its last
  green one would be the defect this exists to catch.

### 3.2 The pin: one test, in each register-carrying repo

```python
"""S-5: the register this repository carries at HEAD is licensed by a fleet check (E-080, mlkit E-M39)."""

from pathlib import Path

from resilient_mlkit.core import register

ROOT = Path(__file__).resolve().parents[1]


def test_s5_register_edit_carries_a_passing_fleet_check():
    assert register.verify_artifact(ROOT / register.ARTIFACT_RELPATH, ROOT) == []
```

`verify_artifact` returns every reason the committed artifact does not license
`docs/one_sided_placebo_register.json` at `HEAD`, and empty is the pin holding:

| it fails when | which is |
|---|---|
| `proof_sha256` does not recompute from the body | an artifact edited by hand, or not written by `--out` |
| `verdict` is not `PASS` | a FAIL run, or a run that measured nothing (fewer than two copies) |
| fewer than two copies were compared | the same, belt and braces |
| **this repository's register blob at `HEAD` is not among the blobs the artifact compared** | **a register edit with no fresh run — the case E-M39 was about** |

So: edit the register, commit, and the test is **red in the repo that made the
edit** until `--check-fleet --out` has been re-run on that tree beside the other
two repositories and its output committed. The other two repos' pins stay green
until they too carry the edit, at which point each runs and commits its own
artifact. It reads `HEAD`, like the check it pins: an uncommitted edit does not
move it, and the same edit committed does (a test in mlkit holds that pair).

`mlkit register --verify-artifact reports/s5_register_fleet_check.json --repo .`
is the same verdict from a shell — exit 0 licensed, 1 not (reasons printed), 2
unreadable — for a landing script that wants it without importing.

### 3.3 The obligation, now that it is a check

> `docs/one_sided_placebo_register.json` is one document kept in three
> repositories. Its `canonical_body_sha256` makes an *internal* edit visible; it
> cannot make a *divergence* visible (E-080: four live bodies, every repo's
> `--mode check` reporting `0 problem(s)`).
>
> **No change that touches `docs/one_sided_placebo_register.json` lands in this
> repository unless `tests/test_s5_register_fleet_pin.py` is green on the tree
> being landed** — which means `mlkit register --check-fleet --root <checkouts>
> --out reports/s5_register_fleet_check.json` was run on this branch beside the
> other two repositories' checkouts, exited 0, and its artifact is committed.
> Exit 1 names the field: a divergence has no innocent party, so do not "fix" the
> sibling copies to match this one without establishing which value the document
> is meant to carry. Exit 2 is not a pass. **A register change lands in three
> repositories or in none.**

Suggested homes: the test at `tests/test_s5_register_fleet_pin.py`, the artifact
at `reports/s5_register_fleet_check.json`, and the paragraph above in
`docs/one_sided_placebo_register.md`, which all three repos already carry.

### 3.4 What this closes, and what it still does not

Closed: the half of E-M39 where a person forgets to run the command — the
forgetting is now a red test in the repo that edited the register.

Not closed, and still the signatory's (§2): the second half, where one repo's
`main` moves and makes a sibling's already-merged copy stale. The sibling's pin
is green (its `HEAD` blob is the one its artifact compared), and nothing an
agent may build makes the sibling see the other repo's `main` without a
credential or a disclosure decision. The sentence "three repositories or none"
is what carries that half, and it is still a sentence.

## 4. What a green run does and does not establish

**Does:** that every copy on this machine agrees, field for field, and that each
copy's stored digest is what its own committed `canonical_body_sha256` computes
over its own body — with every repo's function applied to every repo's body, so
the three implementations are checked against each other as well.

**Does not:** that the register is *correct*. A field that is wrong in the same
way in all three copies passes here and should — this measures agreement, and
agreement is not truth. Nor does it say anything about a copy that is not on this
machine: the command prints the set it compared so a reader can see what was and
was not in scope, and it refuses rather than reporting green when that set has
fewer than two members.

## 5. Where the evidence is

* `reports/S5_REGISTER_FLEET_CHECK_PREREGISTRATION.md` — acceptance B1–B8, fixed
  before the command was written.
* `reports/S5_REGISTER_FLEET_CHECK_RESULTS.md` and
  `reports/S5_REGISTER_FLEET_DRIVE.json` — the drive against real clones of the
  three current `main`s and six committed mutations.
* `scripts/s5_register_fleet_drive.py` — the driver. It clones, mutates a clone,
  and throws it away; it never writes to the checkouts it was pointed at.
* `tests/test_register_fleet.py` — the FIRES/SILENT pairs, on throwaway git
  fixtures that need no sibling checkout present; from v1.3.0 also the pin's
  pairs (an edit committed without a fresh run FIRES in that repo and only that
  repo; a forged PASS fails on its seal; a REFUSED artifact verifies nothing and
  names no path; the loop closes on a fresh run).
