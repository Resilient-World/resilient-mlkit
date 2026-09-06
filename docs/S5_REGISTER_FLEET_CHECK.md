# S-5 — the register fleet check, and the pre-landing obligation it should carry

**Status: the COMMAND is built and driven here. The OBLIGATION is PROPOSED, not
imposed.** The paragraph in §3 is written to be pasted into `resilient-fray`,
`resilient-chokepoint` and `resilient-torrent` by the agents who own those
repos. Nothing in this branch edits any of them.

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

## 3. THE PROPOSED TEXT, for the three repos to paste

Suggested home in each repo: **`docs/one_sided_placebo_register.md`**, which all
three already carry and which is the first thing a person editing the register
reads. A one-line cross-reference from wherever the repo keeps its agent-facing
landing rules (`AGENTS.md` in fray; the equivalent section elsewhere) would help
and is not required for the obligation to bind.

> ### Pre-landing obligation: the register is one document in three repositories
>
> `docs/one_sided_placebo_register.json` is byte-identical in `resilient-fray`,
> `resilient-chokepoint` and `resilient-torrent`. Its `canonical_body_sha256`
> makes an *internal* edit visible; it cannot make a *divergence* visible,
> because each copy can be internally consistent while the three disagree. That
> is not hypothetical: on 2026-09-05 four bodies were live at once, every repo's
> `--mode check` reported `0 problem(s)`, and each repo had recorded in prose
> that a sibling was the stale one. All of those statements were false
> (**E-080**, filed as E-079 here).
>
> **Therefore: no change that touches `docs/one_sided_placebo_register.json` may
> be landed in this repository until**
>
> ```
> mlkit register --check-fleet --root <dir containing the resilient-* checkouts>
> ```
>
> **has been run on a tree where this branch is checked out alongside the other
> two repositories' `main`s, and has exited 0.** Paste its output into the pull
> request. It reads each copy from `HEAD`, so the branch must be committed, and
> the sibling checkouts must be at the `main`s the change is going to meet.
>
> * Exit **0** — the copies are one document.
> * Exit **1** — they are not. The output names the field. **A divergence has no
>   innocent party**: do not "fix" the sibling copies to match this one without
>   establishing which value the document is meant to carry.
> * Exit **2** — the run measured nothing (fewer than two copies present, or a
>   copy could not be read). This is **not** a pass. Get the other checkouts and
>   run it again.
>
> A register change lands in three repositories or in none. If the three pull
> requests cannot be landed close together, land none of them: a copy on `main`
> that its siblings do not carry is the exact state this obligation exists to
> prevent, and it is invisible from inside any one repo.

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
  fixtures that need no sibling checkout present.
