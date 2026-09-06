# S-5 — `mlkit register --check-fleet`: THE CROSS-REPO INVARIANT NOTHING RUNS — PREREGISTRATION

**Written 2026-09-06, BEFORE any source change on this branch. First commit of
`feat/e-080-register-check-fleet`, based on `main` `1d9df13`.** Plan item:
`plan-v4.md` §1.9, second bullet. Escalation: **resilient-torrent E-080**
(filed as **E-079** in `resilient-fray` and `resilient-chokepoint`; one finding,
two ids, because torrent's E-079 was already taken).

## The defect, quoted from E-080

> `docs/one_sided_placebo_register.json` is one document kept in three
> repositories, and `canonical_body_sha256` exists to make a drift between the
> copies fail in whichever copy drifted. On 2026-09-05 there were **four** live
> bodies at once … **Every copy was internally consistent, so `--mode check`
> returned `0 problem(s)` in all three repos, and every repo's test suite was
> green on the constant it had pinned.** The invariant is BETWEEN the repos.
> Nothing in any repo can see the other two, so nothing runs it.

| copy | canonical body | declarations |
| --- | --- | --- |
| `resilient-fray` main `a18c447` | `a643d07e85437d33…` | 5 |
| `resilient-chokepoint` main `90a3939` | `af6b52a46aa309ea…` | 4 |
| `resilient-torrent` main `9201b68` | `cee8f587c63d950c…` | 4 |
| chokepoint PR #137 head `36e66b6` | `13d4dd8665c9991c…` | 4 |

Each repo repaired its own site, **zeroed its own entry** in
`source_files_quoting_the_replaced_sentence`, and wrote in prose that the other
one was still stale. Both statements were false and neither repo could ever
learn otherwise.

## Why this is a LOCAL command and not a CI job

E-080 named the closure — "something outside the three repos has to fetch all
three blobs and refuse when their `canonical_body_sha256` values disagree" — and
named why an agent may not build it that way: **the repos are private**, so a
cross-repo CI job needs a credential, and **CLAUDE.md rule 13 forbids an agent
putting a credential anywhere near this**. Standing CI configuration and any
cost-incurring resource are the signatory's under rule 12.

So the closure built here is a command a person or an agent runs **locally, on a
machine that already holds the checkouts**, with no credential of any kind:

    mlkit register --check-fleet --root <dir containing the resilient-* checkouts>

It reads what is already on disk. It creates nothing, fetches nothing,
authenticates to nothing, and writes nothing into any repo.

## What it does, fixed now

1. **Discovers** every `resilient-*` directory under `--root` that carries
   `docs/one_sided_placebo_register.json`.
2. **Reads each register from `HEAD`**, never from the working tree, because the
   invariant is about the document three repos will land, not about three
   scratch edits. A directory that is not a git work tree is REFUSED by name.
3. **Recomputes `canonical_body_sha256` with the register's own function** —
   each repo's committed `scripts/verify_one_sided_placebo_register.py`
   `canonical_body_sha256`, loaded from that repo's `HEAD` blob. mlkit does not
   define a second digest (rule 7). Every repo's function is applied to every
   repo's body, so the three implementations must also agree with each other;
   the S-5 re-cut of 2026-09-05 used exactly this cross-application and it is
   what makes "one answer" a measurement rather than a coincidence.
4. **FAILS on any digest or field divergence, naming the field.** Two distinct
   failures, kept distinct because they need different repairs:
   * **self-inconsistency** — a copy whose stored digest is not what its own
     function computes over its own body. The repo edited the document without
     re-deriving its digest.
   * **cross-repo divergence** — copies that are each internally consistent and
     do not agree. This is E-080's actual failure and the one every existing
     check is blind to. The field is named by its **dotted path** to the depth
     at which the copies differ, so
     `source_files_quoting_the_replaced_sentence.resilient-chokepoint` is
     reported as that, not as "the register differs".
   * `declarations` is compared **by declaration id**, not positionally, so a
     narrowing live in one copy and absent from another is reported as
     `declarations[FR-D2-NASS-45ORIGIN-ABOVE] MISSING in <repo>` — which is
     literally what E-080 found and could not see.
5. **REFUSES rather than passing** when fewer than two copies are present. A
   fleet check over one copy is not a fleet check, and reporting it green would
   be the strongest possible version of the defect.

## Acceptance conditions (B1–B8), fixed now

**B1 — the three current mains PASS.** With `--root` a directory holding fresh
clones of `resilient-fray`, `resilient-chokepoint` and `resilient-torrent` at
their current `main`s, the command exits **0**, reports **3 copies**, reports
the git blob id of each `docs/one_sided_placebo_register.json` as the same
object — expected `9f6cb2b015f2ba9ca9e8c696b310d1bd9767e738` — and reports one
canonical body across all three.

**B2 — one mutated field FAILS, naming the field.** A clone of one repo with
**exactly one field** changed and committed, its digest left as it was: the
command exits non-zero and names both the self-inconsistency and the repo.

**B3 — a mutated DIGEST alone FAILS.** The body untouched, the stored
`canonical_body_sha256` changed to any other hex string: exits non-zero, naming
`canonical_body_sha256` and the repo.

**B4 — THE CONTROL THAT MATTERS: a field changed AND the digest correctly
re-derived still FAILS, naming the field.** This is E-080's shape exactly —
every copy internally consistent, every repo's own `--mode check` green — and it
is the only failure mode that the three repos' existing machinery cannot see. If
B4 does not fire, this command adds nothing.

**B5 — the three implementations agree.** Every repo's `canonical_body_sha256`
applied to every repo's body yields one value per body. A disagreement is a
REFUSAL, not a FAIL: it means the fleet has two definitions of the digest, and
no verdict taken with either is trustworthy until that is settled.

**B6 — a single copy REFUSES.** `--root` with one register present exits 2 with
the reason named. Driven, because the tempting failure is to report "1 copy, 0
divergences, PASS".

**B7 — check-not-dead.** Each of B2, B3 and B4 is driven against the UNMUTATED
copy as its SILENT half, in the same invocation shape, so the pair is a pair.

**B8 — the suite.** `python -m pytest tests -q` on the merged tree, in the same
clone as the `main` baseline, differs from the baseline only by tests this
branch adds. Baseline: **1272 passed, 3 skipped** at `1d9df13` (measured
2026-09-06 in this clone, `PYTHONPATH=<clone>/src`). No `-k` filter is a gate.

## The pre-landing obligation: PROPOSED, not made

The plan says to document the command as a pre-landing obligation in each repo's
contributing notes and to **propose the text, because the repo edits are other
agents'**. This branch therefore writes the exact paragraph into
`docs/S5_REGISTER_FLEET_CHECK.md` in **this** repo, names the file in each
sibling it should be pasted into, and changes **nothing** in any sibling repo.
No agent here edits `resilient-fray`, `resilient-chokepoint` or
`resilient-torrent`.

## What this branch does NOT do

* It does not create, edit, or re-pin any register, any declaration, any halt
  region, or any digest in any repo. It reads and compares.
* It does not add a CI job, a scheduled task, a credential, a token, a secret, or
  any resource that costs money (rules 12 and 13).
* It prints no credential. The register carries none, and the command prints only
  register fields, digests and paths.
* It reads no holdout: the whole check is a read of committed JSON.
* If a future reader wants this enforced automatically rather than by obligation,
  that is the signatory's standing-CI decision and it is named, not taken.

## The prediction, written before the drive

The three current mains carry the **identical git blob**
`9f6cb2b015f2ba9ca9e8c696b310d1bd9767e738` (verified by `git rev-parse
HEAD:docs/one_sided_placebo_register.json` in each fresh clone on 2026-09-06),
so B1 is expected to pass and the interesting result would be it failing. B4 is
expected to fire; if it does not, the command is a restatement of what each
repo's own scanner already does and should not land.
