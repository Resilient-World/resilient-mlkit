# Pre-registration — making D2 and E1 bindable without making them weaker

Written and committed as the **first commit** on branch
`feat/m-d2e1-declared-contract`, off `main` at `6921e9a`, **before any edit to
`src/`**. The commit order is the evidence that the rule preceded the result.

## The finding this answers

Round 8's adjudication (§2.4) measured that `resilient-fray`'s D2 and E1 are
`NA` — no `placebo_test` and no `scaling_probe` binding in its
`.mlkit/repo.toml` — at the branch head and at main. The hard stops the
training run reported were the trainer's own in-script constructions: genuine,
honestly computed, and **not the fleet's gates**.

Two contract mismatches block an honest binding, and both are mlkit's, not the
adopter's:

1. **D2 is two-sided at a null of exactly zero.** `checks/decision.py` halts
   when `lo > 0 or hi < 0`. fray's placebo estimand is *skill against the
   persistence floor*, whose no-signal value is not zero: a shuffled-target run
   is expected to be far **worse** than the floor. Its placebo CI is
   `[-71.998, -53.146]`, so `hi < 0` — binding that honest surrogate under the
   name `placebo_test` would trip a **spurious fleet-wide hard stop**.
2. **E1 requires the fractions `{0.01, 0.10, 0.25}` and nothing else.** fray's
   probe measured 10% and 25% only. Under mlkit's own relative rule the curve
   is comfortably not flat — `(-138.13969 − −151.29137) / |−151.29137|` =
   `+0.08692947918972509`, i.e. **+8.69%**, against a 1% bar — so E1 would
   **FAIL on contract, not on substance**.

Neither is fixed by an adopter. Both are fixed by giving mlkit a way for an
adopter to **declare** its estimand's halt region and its fraction ladder, in
committed data, and then judging against the declaration.

## What is being built

Two optional sections in `.mlkit/repo.toml`, read **from committed state** via
`core.artifact.load` — the discipline `docs/ESCALATIONS.md` E-M21/E-M23 forced
on D3's nominal coverage level, for the same reason: a standard the subject
supplies at measurement time is not a standard.

```toml
[placebo]                       # D2
estimand   = "skill against the persistence floor, lb/ac"
null_value = 0.0                # the value the estimand takes under no signal
indicts    = "above"            # "either" (default) | "above" | "below"

[scaling]                       # E1
fractions  = [0.01, 0.10, 0.25] # this repo's ladder; the top two carry the verdict
```

## The invariants this may not break, stated before the code exists

These are the falsification conditions. If the implementation cannot hold all
of them, the finding is reported and **no threshold, range, holdout or existing
test is moved** (CLAUDE.md rule 6).

**I1 — an undeclared repo sees no change at all.** With neither section
present, D2 and E1 must produce byte-identical verdicts, evidence and reason
strings to `main` at `6921e9a`, under every flag including `--allow-dirty`. The
entire existing suite (`tests/test_decision_controls.py`,
`tests/test_economics_controls.py`) must pass unmodified. **No test that exists
on main is edited.**

**I2 — the defaults ARE the current rule.** `null_value` defaults to `0.0`,
`indicts` defaults to `"either"`, `fractions` defaults to `(0.01, 0.10, 0.25)`.
Every fallback — absent section, malformed working tree, dirty checkout with
the section deleted — must land on the default, i.e. on the **strictest**
setting. A repo may never reach a looser rule by breaking something.

**I3 — the declaration is COMMITTED or it does not exist.** A section present
in the working tree and absent from `HEAD:.mlkit/repo.toml` is an `NA` naming
the file, never a silent default and never a pass. A binding whose module body
rewrites the config at import time cannot move the standard.

**I4 — a one-sided halt region costs something.** `indicts` may not depart from
`"either"`, and `null_value` may not depart from `0.0`, unless the repo also
declares a non-empty `estimand` in the same committed table. An anonymous
exemption is refused.

**I5 — the exemption must point the same way as the claim.** Under a one-sided
declaration the sign of the binding's `reference_effect` must lie on the
**indicting** side. A repo that exempts the direction its own product claim
lives in has exempted the only direction D2 was testing, and that is a FAIL.
(Under the default two-sided declaration the sign is not read, exactly as
today: `abs()` as on main.)

**I6 — the power bar is untouched.** `half_width >= reference` remains a FAIL
without `halt`, at the same strict boundary, on every path. The non-finite
guards on `estimate`, `ci_low`, `ci_high` and `reference_effect` remain, and
run in the same order relative to the halt.

**I7 — a declared ladder may not buy a pass by widening its own top step.**
The verdict is the relative gain between the **top two** rungs. Two structural
refusals, both FAILs of the declaration:
* the top rung must be **≥ 0.25** — E1 asks whether the run you would actually
  buy is worth buying, and a ladder topping out at 5% never asks it;
* the top two rungs may be no further apart than mlkit's own, `0.25 / 0.10 =
  2.5` exactly in IEEE-754 doubles. A ladder of `[0.01, 0.02, 0.25]` asks
  whether 12.5× the data helps, which almost anything passes.
The flatness threshold itself (`FLATNESS_EPSILON = 0.01`, **relative**) stays
mlkit's and is **not** declarable. A subject that sets its own pass mark sets
no pass mark.

**I8 — the ladder must still be a ladder.** At least three rungs, every rung a
finite non-boolean number in `(0, 1]`, strictly increasing. `bool` is an `int`
in Python and `float("nan")` survives `float()`; both are refused on type
before anything is read out of them.

**I9 — unknown keys are refused.** An unrecognised key in `[placebo]` or
`[scaling]` is a FAIL naming it. A declaration you believe you made and did not
is the E-M21 family, and both fallbacks here happen to be strict — which is
exactly why a typo must not pass silently.

## The control pairs, specified before they are written

A pair is only a pair if both halves are present. Firing alone is consistent
with a check that fires on everything; silence alone with one that fires on
nothing. Every pair below must be exercised through a repo on disk whose
`.mlkit/repo.toml` is **committed**, resolved through `repo.resolve()` — the
same path the eight real repos take — never through a monkeypatch.

### D2 — the hard stop still fires under a declared, non-zero-null estimand

| # | Fixture | Required verdict |
|---|---|---|
| D2-N1 | `indicts="above"`, `null_value=0.0`, estimand declared; placebo CI `[+8.0, +26.0]` — the placebo **beats** the floor | FAIL **and** `evidence["halt"] is True` |
| D2-N2 | the same declaration; fray's measured CI `[-71.998, -53.146]`, `reference_effect` `+22.81138510740044` | PASS, no `halt` |
| D2-N3 | `indicts="either"`, `null_value=-62.0`; CI `[-40.0, -30.0]` excludes −62 | FAIL + `halt` |
| D2-N4 | the same declaration; CI `[-71.998, -53.146]` contains −62 | PASS, no `halt` |
| D2-N5 | `indicts="above"` with `reference_effect` **negative** | FAIL naming the sign disagreement, no `halt` (I5) |
| D2-N6 | `indicts="above"` with no `estimand` declared | FAIL, no `halt` (I4) |
| D2-N7 | the declaration only in the working tree | NA naming `.mlkit/repo.toml`, no `halt` (I3) |
| D2-N8 | binding's module body rewrites `[placebo]` at import | not PASS, and the standard used is not the one the module wrote (I3) |
| D2-N9 | **no section at all**, CI `[-1.13, -0.31]` | FAIL + `halt` — main's two-sided verdict, unmoved (I1/I2) |

D2-N1 against D2-N2 is the pair that carries the weight: the same declared
one-sided contract, one placebo that indicts and one that does not. D2-N9
against D2-N2 is the second pair: the **same interval**, halting when the repo
has declared nothing and silent when it has declared the estimand that makes
the lower side the expected one.

### E1 — the hard stop still fires under a declared ladder

| # | Fixture | Required verdict |
|---|---|---|
| E1-N1 | `fractions=[0.02, 0.20, 0.50]`; curve flat between 0.20 and 0.50 | FAIL **and** `evidence["halt"] is True` |
| E1-N2 | the same ladder, rising past the epsilon between 0.20 and 0.50 | PASS, no `halt` |
| E1-N3 | the same ladder, a rung missing from the returned curve | FAIL naming the fraction |
| E1-N4 | `fractions=[0.01, 0.02, 0.25]` — top step 12.5× | FAIL of the declaration (I7) |
| E1-N5 | `fractions=[0.01, 0.05, 0.10]` — top rung below 0.25 | FAIL of the declaration (I7) |
| E1-N6 | `fractions=[0.10, 0.25]` — two rungs | FAIL of the declaration (I8) |
| E1-N7 | `fractions=[0.25, 0.10, 0.01]` — not increasing | FAIL of the declaration (I8) |
| E1-N8 | `fractions=[0.01, 0.10, true]` | FAIL on type (I8) |
| E1-N9 | the declaration only in the working tree | NA naming `.mlkit/repo.toml` |
| E1-N10 | **no section at all**, curve flat 10%→25% | FAIL + `halt` — main's verdict, unmoved (I1/I2) |

E1-N1 against E1-N2 is the not-dead pair for the declared ladder. E1-N4/E1-N5
are the anti-gaming half: the only two ways a declared ladder could make a flat
curve look steep are refused **as declarations**, before any curve is read.

### The fray reproduction, end to end

One test drives fray's own measured figures through the whole path — committed
declaration, binding on disk, `d2_placebo_test` — and asserts PASS with no
`halt`, and one drives the un-declared repo with the same figures and asserts
the spurious hard stop that §2.4 predicted. That difference is the finding
being closed, and it is asserted rather than described.

## Predicted results, recorded before running

Recorded so a green first run reads as a blind test rather than as a clean
instrument.

* I expect the whole existing suite to pass untouched. If any existing test
  needs an edit, that is a **weakening** and the design is wrong, not the test.
* I expect D2-N5 (the sign tie) to be the branch most likely to be wrong first
  time, because `reference = abs(float(reference))` on main discards the sign
  before anything can read it, and the fix has to read the signed value while
  leaving the power bar's operand identical.
* I expect E1's `evidence["gain_10_to_25"]` key to be the thing that forces a
  decision: under a declared ladder that name would be a **fabricated label**.
  Plan: emit `gain_top_two` always, and keep `gain_10_to_25` only when the
  ladder actually is `(0.10, 0.25)`, where the name is literally true.
* I expect no change to `portfolio.resolve`, to `Status`, or to any threshold.

## What stays out of scope, and why

* **Binding fray's D2/E1.** That is a write into `resilient-fray`, and
  `baseline1.md` records that arming those bindings needs the training plane,
  which needs IAM/billing resource creation — CLAUDE.md rule 12, reserved to
  the signatory. What lands here is the contract that makes the binding
  *possible*; the escalation records what is left and who may do it.
* **Any change to D3.** It shares `.mlkit/repo.toml` and will share the
  relpath constant, and nothing else about it moves.
