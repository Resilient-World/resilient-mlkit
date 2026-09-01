# DECISION_VALIDITY.md — Phase 4

<!-- CANONICAL. Authored once in resilient-mlkit/spine/ and synced to all 8
     repos. -->

This phase asks whether the number the model produces means what the business
thinks it means. It runs **before** any long training run, because everything it
can invalidate costs cents to test and thousands to discover later.

## D1 `COUNTERFACTUAL_SPEC` — human sign-off

What "avoided loss" means for this model, in terms someone could disagree with:
what the counterfactual world is, who bears the loss, over what horizon, and what
would make the claim false. **Non-delegable.** `mlkit` reports D1 ESCALATED
unconditionally.

## D2 `PLACEBO_TEST` — the strongest check in the package

Run the full pipeline on a pre-intervention period, or with treatment assignment
permuted. The estimate must come back **indistinguishable from the value the
estimand takes under no signal** — its confidence interval must contain that
value. For an avoided-loss estimand that value is zero, and that is the default.

It runs as a SageMaker Processing Job for cents, logged to MLflow under this
repo's experiment, and it can invalidate a model before a single GPU-hour is
bought.

> **HARD STOP.** If the placebo estimate is distinguishable from its null, halt
> this repo immediately. State it plainly. Do not tune, do not scale, do not
> schedule a training run.
>
> A placebo that shows an effect means the estimator is capturing something
> other than the intervention. That is not a tuning problem, and adjusting the
> estimator until the placebo passes is the precise opposite of what the check
> is for.

D2 also requires `reference_effect` — the real run's effect size, measured from
the same null — and refuses an interval that is not strictly narrower than it.
An interval wide enough to contain everything contains the null too, so without
that bar a true null and a no-power test wear the same face.

### Declaring a halt region

The default null is **zero** and **both sides indict**. That is right for an
avoided-loss estimand and wrong for some others. `resilient-fray`'s placebo
estimand is *skill against the persistence floor*: a shuffled-target run is
**expected** to land far below the floor (its CI is `[-71.998, -53.146]`), and
only a placebo that BEATS the floor is leakage. Under the two-sided default that
honest surrogate would have tripped a spurious hard stop, so fray never bound it
and D2 read NA — and a gate nobody can bind is an absent one, not a strict one.

So the halt region is declarable, in `.mlkit/repo.toml`, read from the blob at
HEAD:

```toml
[placebo]
estimand   = "skill against the persistence floor, lb/ac"
null_value = 0.0
indicts    = "above"      # "either" (default) | "above" | "below"
```

**Declaring it is not free**, and the costs are the reason it is safe:

* moving `null_value` off `0.0`, or `indicts` off `"either"`, **requires a
  written `estimand`**. `mlkit` cannot adjudicate prose; what it can do is
  refuse an anonymous exemption and put the sentence in the verdict's evidence.
* under a one-sided region the **sign of `reference_effect` must lie on the
  indicting side**. A repo that exempts the direction its own product claim
  lives in has exempted the only direction D2 was testing, and that is a FAIL.
* the power bar, the non-finite refusals and their order do not move.
* an **uncommitted** declaration is NA, never a silent default; a declaration a
  binding's own module writes at import time cannot move the standard.

Absent the section, D2 is exactly the check it always was.

## D3 `UNCERTAINTY_COVERAGE`

Empirical coverage of the prediction intervals on the blocked holdout, against
nominal. A 90% interval that covers 62% of held-out outcomes is not a
conservative 90% interval; it is a wrong one, and downstream pricing built on it
is wrong by the same margin.

Measured on a Processing Job, logged to MLflow.

## D4 `SENSITIVITY` — human sign-off

Which assumptions the estimate is most sensitive to, and how far each can move
before the decision flips. **Non-delegable.**

## D5 `EXTERNAL_ANCHOR` — human sign-off

What independent, external evidence the estimate is anchored against. **Non-
delegable.**

## Passing

`mlkit check --phase decision` reports a placebo estimate with its confidence
interval, and empirical interval coverage against nominal. D1, D4 and D5 report
ESCALATED until the signatory writes them.

**Failing D2 means no GPU budget.**
