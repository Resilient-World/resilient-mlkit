# M-1 — a first-class ENVIRONMENT-REFUSAL state for armed checks: PREREGISTRATION

**Written 2026-09-04, BEFORE any code on this branch. This is the branch's first
commit.** Plan item: `sota-plan-v3.md` §7 M-1. Base: `main` at `3bf16dd`, where
the full suite is **1195 passed** (driven in this checkout, python 3.12.13,
`resilient_mlkit.__file__` asserted to be this tree's `src/`).

## The defect, as measured in the adopters (not recalled)

Three adopters, three shapes of one fact:

* torrent `main` `d34649f`: D2 renders **FAIL** with the reason text
  "ENVIRONMENT REFUSAL, NOT A PLACEBO FINDING: the staged Caravan subset could not
  be read" (`mlkit_bindings.py:1912`, `PlaceboRefused`). The binding's own
  docstring says why it chose FAIL: *"mlkit has no NA channel for a binding that
  raises"*. Correct fail-closed behaviour, rendered as an indictment.
* chokepoint `main` `512ab25`: R2/R3/R5/R6 refuse on pin mismatch from any clone
  without the pinned parquet (STATE 2026-09-03: "a clean clone has the sidecars
  and no panel bytes, so R2/R3/R5/R6 refuse and readiness reads 5/12").
* fray `main` `76f0dde`: E1 raises `TemporalSplitIdentityMismatch` and returns no
  curve when the NASS extract's bytes differ from the pin.

`core/result.py:60-83` has six terminal statuses and "deliberately no SKIP and no
WARN". NA is what "no binding declared" renders as, so an armed stop that cannot
read its inputs has no honest status: FAIL indicts the pipeline, NA reads as
unarmed. A hard stop that is **armed but cannot read its inputs** is a fourth
thing and needs its own word.

## What changes (fixed now; the diff is held to this list)

1. `Status.UNMEASURABLE` — a seventh terminal status, reason-required. The word
   `core/environment.py` already uses for the interpreter-level fact, applied to a
   single check.
2. `core.result.InputUnavailable(reason, *, input, pin_expected, pin_observed,
   evidence)` — a typed exception a binding raises **only after** it has resolved
   its declaration and reached the byte it cannot read. The `CredentialRequired`
   discipline applies verbatim: raising earlier, to dodge a check that would have
   failed for another reason, is the failure this status exists to avoid.
3. The runner (`cli._run_phase`) maps `InputUnavailable` to
   `CheckResult.unmeasurable(...)` carrying `input`, `pin_expected`,
   `pin_observed` in evidence. Every check that today does
   `except CredentialRequired: raise` re-raises `InputUnavailable` the same way.
4. **Premature refusal is refused by name.** An `InputUnavailable` raised while
   the binding's MODULE is being imported (i.e. before `Repo.resolve` has
   returned the declared callable) is a `PrematureInputRefusal` and renders
   **FAIL**, never UNMEASURABLE.
5. `environment.from_results()` extends its discriminator: a result whose status
   is UNMEASURABLE makes the run's environment probe UNMEASURABLE, with both
   digests in the probe's bindings map. `report.guarded_write` therefore refuses
   to overwrite a binding-dependent report (readiness.md today; an adopter's
   hard_stops.md through the same writer) from such a run. The existing rule is
   untouched: a missing module that resolves inside the repo is still a repo
   defect and still FAILs.
6. `portfolio.resolve`: UNMEASURABLE is "unmeasured" — the repo is IN_PROGRESS,
   never READY and never BLOCKED (nothing is indicted). `cmd_check` exits 3 on it,
   as for NA. Table glyph `U`, legend and README status table updated.
7. `core.arming.arm_state(declared, status)` — ONE definition of what an
   adopter's hard-stops module renders: `armed = declared and status in
   {PASS, FAIL, UNMEASURABLE}`; `halt_required = status in {FAIL,
   UNMEASURABLE}`; `indicted = status is FAIL`. torrent's and chokepoint's
   `hard_stops.py` each compute this locally today (rule 7).

Nothing else moves. No threshold, no ladder, no halt region, no test deletion.

## Acceptance — controls fixed before the code, driven both ways

| id | direction | fixture | required |
|---|---|---|---|
| C1 | FIRES | `placebo_test` binding resolves its declaration, then raises `InputUnavailable(input="staged panel", pin_expected=A, pin_observed=B)` | D2 status **UNMEASURABLE**; reason names `A` and `B`; evidence carries `input`, `pin_expected`, `pin_observed`; evidence has **no** `halt` key; `portfolio.resolve` → IN_PROGRESS; `cmd_check` exit **3** |
| C2 | SILENT | same fixture with the bytes present | D2 **PASS** with evidence equal to the pre-branch PASS on the same payload (byte-identical `to_dict()` minus `measured_at`) |
| C3 | OTHER DIRECTION | binding module raises `ImportError` of the repo's own module | **FAIL**, unchanged from today (the suppression-in-the-other-direction trap `environment.py` documents) |
| C4 | REFUSED BY NAME | binding module raises `InputUnavailable` at import time | **FAIL** whose reason names `PREMATURE_INPUT_REFUSAL`; never UNMEASURABLE |
| C5 | FIRES / SILENT | E1: the C1/C2 pair on `scaling_probe` | same statuses as C1/C2 |
| C6 | FIRES | `environment.from_results` over a result set holding one UNMEASURABLE row | probe verdict UNMEASURABLE; `guarded_write` refuses; prior report sha256 unchanged; refusal file written |
| C7 | SILENT | `from_results` over a result set with a FAIL whose reason names a repo-local missing module | probe NOT unmeasurable (repo defect stays a defect) |
| C8 | CHECK-NOT-DEAD | the runner's `InputUnavailable` clause removed (monkeypatched to the generic handler) | C1's fixture renders FAIL "unhandled exception" — proving the new clause is what produces the status |
| C9 | STRUCTURAL | `CheckResult(status=UNMEASURABLE, reason="")` | `FabricationError` (reason required); `GateAggregate.passed` is False over it; `Status` still has no SKIP/WARN |

**Falsifier (from the plan):** if any existing PASS/FAIL row changes status on the
machine that holds the bytes, the discriminator is wrong. Operationalised here
as: the 1195-test baseline stays green with **zero test deletions**, and the
adopter-shaped fixture (C2) is byte-identical to its pre-branch verdict.

## What is NA on this machine, said now

The three adopters' D2/E1 cannot be driven for real here: there is no staged
PortWatch parquet, no NASS extract, no Caravan subset and no repo venv on this
machine, and a bare interpreter makes mlkit refuse (correctly). The per-adopter
A/B the plan asks for ("on a clone without the panel, D2 renders UNMEASURABLE
naming the pin; on the machine with it, PASS byte-identical") is therefore
reproduced on adopter-shaped FIXTURES in this repo's suite, and the real
adoption rides on each repo's next repin PR (§8, "adoption in the three repos
rides on their next repin PR each"). That is stated as a limit, not hidden.
