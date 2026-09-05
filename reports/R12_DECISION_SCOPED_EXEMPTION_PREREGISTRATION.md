# R12 — THE SERVED-CONTRACT EXEMPTION, SCOPED TO THE DECISION — PREREGISTRATION

**Written 2026-09-06, BEFORE any source change on this branch. First commit of
`fix/e-079-served-exemption-scoped-to-the-decision`, based on `main` `1d9df13`.**
Plan item: `plan-v4.md` §1.9, first bullet. Escalation: **resilient-torrent
E-079** (`docs/ESCALATIONS.md`, raised 2026-09-05, status OPEN, a proposal about
mlkit and not a change to it, because mlkit is not that repo's to edit).

## The defect, as torrent measured it and quoted verbatim

> The exemption is **file-scoped**: once a file binds and USES a `core.served`
> name anywhere, a local serve-arm constant elsewhere in the same file is no
> longer reported — even when that constant is the value actually used. So the
> scanner falling silent does not establish that the arm flows through the
> contract; a single conforming helper anywhere in the file buys silence for
> every serve-arm decision in it.

torrent's table, driven three ways on `mlkit_bindings.py` (E-079):

| tree | findings | files walked |
|---|---|---|
| PR #190 as authored (local constant, no `ServeArms`) | **1** | 588 |
| the repair (arm obtained via `require`) | 0 | 588 |
| the repair **plus the constant restored and used**, helper left dead | **0** | 588 |

The third row is the defect. It is the same shape fray recorded at **E-035**,
where a dead import took a file from 4 findings to 0 without changing a single
decision — repaired then for the *import*, and left open for the *file*.

## What changes (fixed here, before it is written)

`core.served_reimplementation`'s exemption stops being a property of the FILE
and becomes a property of the DECISION, **for the `SERVE_ARM` clause only**:

> A serve-arm site is exempt where **the value it decides is derived from a
> bound `core.served` name** — directly, through the one permitted level of
> repo-local indirection, or through a module-level binding or helper in the
> same file whose own value is so derived — and **not** where such a name
> merely appears somewhere else in the file.

The other five clauses (`SELF_HASH`, `PROVENANCE`, `PROMOTION_VERDICT`,
`CHAMPION_RECORD`, `SHADOW_ROUTER`) keep the file-scoped exemption they have
today, unchanged. This branch does not widen or re-scope them; E-079 is about
the serve arm, and a change that also re-scoped the promotion clause would be a
second change wearing this one's clothes.

**Direction of the change, stated so it can be checked:** the rule is
**strictly stronger**. It can only ADD findings — a site that was reported
before is reported after, because the file-level exemption is the only thing
being narrowed. Nothing here relaxes a threshold, widens a range, or edits a
gate to go green (CLAUDE.md rule 6). If the drive shows any finding that
existed on `main` and does not exist here, this branch is wrong and stops.

## Acceptance conditions (A1–A7), fixed now

**A1 — the third shape is reported.** On a real `resilient-torrent` clone at
its current `main`, the shape "the repair PLUS the constant restored and USED
with the `_d6_serve_arms` helper left dead" reports **exactly 1** finding, and
that finding is `clause == "SERVE_ARM"`, `severity == CONTRACT_REIMPLEMENTED`,
at `mlkit_bindings.py`, naming the restored constant. This is E-079's row 3
going 0 → 1.

**A2 — the repair stays silent.** The same clone with `mlkit_bindings.py`
exactly as `main` has it (the arm obtained through `ServeArms.require`) reports
**0** findings, repo-wide. A repair that fired here would have bought A1 by
breaking adoption, which the module docstring forbids.

**A3 — the defect as authored stays reported.** The shape "a module-level
`D6_DECIDING_ARM = "val"` and no `core.served` name in the file" reports
**exactly 1** finding, `SERVE_ARM`, at `mlkit_bindings.py` — E-079's row 1,
unmoved.

**A4 — fray's E-035 dead-import shape still reports its findings.** On a real
`resilient-fray` clone, with `src/registry/promotion_gate.py` replaced by its
pre-adoption blob (`fc4eaa4^` = `81f453f`) plus the one line
`from resilient_mlkit.core.served import challenger_decision  # noqa: F401`,
the file is still named and its finding count is **not lower** than the same
pre-adoption blob without that line. E-035 must not be re-opened by this
branch.

**A5 — the three mains do not move except where E-079 says they must.** Repo-wide
scans of `resilient-torrent`, `resilient-fray` and `resilient-chokepoint` at
their current `main`s produce, after the change, a finding set that is a
**superset** of the set before it, by `(path, line, clause, symbol)`. Any row
that disappears is a regression and stops this branch. Any row that APPEARS is
reported here with its file and line, and is not silenced.

**A6 — the fleet blast radius is measured, not assumed.** The same
before/after superset comparison is run over all fourteen `resilient-*`
checkouts on this machine, and every added row is listed in the results
document with its file, line and symbol. The version bump is chosen FROM that
measurement against `CHANGELOG.md`'s own scale ("major — an existing check
changes verdict on unchanged code"), not before it.

**A7 — the suite.** `python -m pytest tests -q` on the merged tree, in the same
clone as the `main` baseline, differs from the baseline only by (a) tests this
branch adds and (b) tests this branch updates, each of which is named in the
results document with the reason it moved. The baseline is
**1272 passed, 3 skipped** at `1d9df13` (measured 2026-09-06 in this clone,
`PYTHONPATH=<clone>/src`, mlkit resolving to `0.7.0` in this clone). No
`-k` filter is a gate.

## The controls, and the shape of each pair

Every control below is driven BOTH WAYS, because a control that cannot fire is
not a control.

* **C1 FIRES / C2 SILENT — the E-079 pair.** C1 is A1's shape (constant used,
  helper dead) and must report. C2 is A2's shape (arm through `require`) and
  must not. The variable between them is one expression: what
  `d6_deciding_arm()` returns.
* **C3 SILENT — adoption is not broken.** A file that takes its arm policy FROM
  the contract (`SERVEABLE_ARMS = ServeArms(open={...})`) and refuses on it
  stays silent, in every import spelling the module already recognises: the
  `from X import f` form, the dotted `import X.Y.Z` form, the `as` form, and
  the one permitted level of repo-local indirection. If any of these fired,
  the repair would have closed the evasion by making the contract unusable.
* **C4 FIRES — one level of local indirection is honoured but not free.** A
  file whose arm constant is `_arms()` where `_arms()` returns the contract's
  `ServeArms` is silent; the same file with `_arms()` returning a bare tuple
  fires. The variable is where the value comes from, not how many statements
  it took to get there.
* **C5 CHECK-NOT-DEAD.** Reverting the new predicate to the file-scoped
  exemption must fail exactly the FIRES halves and nothing else. Recorded by
  running the new tests against the unrepaired predicate.

## What this branch does NOT claim, and does not do

* It does not claim a silent `SERVE_ARM` clause means the arm is served
  correctly. R12 is an `ast` walk; the gap between "the value is derived from
  the contract" and "the contract decides" is stated in the module docstring
  and is not closed here.
* It does not touch the other five clauses, `core.served` itself, any repo's
  tree, any gate threshold, or any committed measurement.
* It performs nothing reserved by CLAUDE.md rule 12. No allowlist entry, no
  decision record, no IAM, billing or cost-incurring resource.
* No ledgered holdout read is taken, spent or touched: this is a static AST
  walk over source files and opens no split.

## The prediction, written before the drive

torrent `main` and fray `main` both scan to **0 findings** today (measured
2026-09-06 in these clones, `files_walked` 597 and 283). The expectation is
that both stay at 0 after the change, because torrent's repair takes the arm
through `require` and fray's promotion gate carries no module-level arm
constant. The expectation for the wider fleet is that one or more of the eleven
stale checkouts gains a row, because a file-scoped exemption over an arm
constant is a common shape. **The measurement decides, and whatever it says is
what the results document records.**
