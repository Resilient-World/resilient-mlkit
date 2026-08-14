"""Phase 4 — DECISION VALIDITY.

D2 is the strongest check in the package. Run the full pipeline on a
pre-intervention period, or with treatment assignment permuted, and the
avoided-loss estimate must come back indistinguishable from zero. If it does
not, the estimator is capturing something other than the intervention, and no
amount of tuning fixes that -- so a D2 failure is a hard stop for the repo
rather than a finding to work around. It costs cents on a Processing Job and
can invalidate a model before a single GPU-hour is bought.
"""

from __future__ import annotations

from ..core.repo import BindingError, Repo
from ..core.result import CheckResult
from . import RunContext, check

PHASE = "decision"

#: Loosest coverage tolerance D3 accepts, whatever a binding asks for.
MAX_COVERAGE_TOL = 0.05

#: Below this, the binomial standard error alone exceeds the tolerance, so the
#: measurement cannot support the verdict either way.
MIN_COVERAGE_N = 100


@check("D1", PHASE, "COUNTERFACTUAL_SPEC — human sign-off", human_only=True)
def d1_counterfactual_spec(repo: Repo, ctx: RunContext) -> CheckResult:
    return CheckResult.escalated(
        "D1", PHASE,
        "D1 specifies what the counterfactual means commercially and is reserved "
        "to the signatory; the agent may not write it",
    )


@check("D2", PHASE, "PLACEBO_TEST — estimate indistinguishable from zero")
def d2_placebo_test(repo: Repo, ctx: RunContext) -> CheckResult:
    try:
        fn = repo.resolve("placebo_test")
    except BindingError as exc:
        return CheckResult.na(
            "D2", PHASE,
            f"{exc}; the placebo run is a SageMaker Processing Job and the training "
            "plane has not been bootstrapped",
        )
    try:
        out = dict(fn())
    except Exception as exc:  # noqa: BLE001
        return CheckResult.failed("D2", PHASE, f"placebo_test raised {type(exc).__name__}: {exc}")

    for field in ("estimate", "ci_low", "ci_high"):
        if field not in out:
            return CheckResult.failed("D2", PHASE, f"placebo_test did not report {field}")

    estimate = float(out["estimate"])
    lo, hi = float(out["ci_low"]), float(out["ci_high"])
    evidence = {"estimate": estimate, "ci_low": lo, "ci_high": hi, "run": out.get("run_id", "")}

    # Distinguishable from zero == the interval excludes zero.
    if lo > 0 or hi < 0:
        return CheckResult.failed(
            "D2", PHASE,
            f"placebo estimate {estimate:.6g} with CI [{lo:.6g}, {hi:.6g}] excludes zero; "
            "the estimator is capturing something other than the intervention. "
            "HARD STOP — do not tune, do not scale, do not schedule a training run.",
            {**evidence, "halt": True},
        )

    # Containing zero is necessary but nowhere near sufficient. An interval
    # wide enough to contain everything contains zero too, and would sail
    # through the package's self-described strongest check while proving
    # nothing. Passing requires enough power to have detected the effect the
    # real run claims -- otherwise this is a null result and a no-power result
    # wearing the same face.
    reference = out.get("reference_effect")
    if reference is None:
        return CheckResult.na(
            "D2", PHASE,
            "placebo interval contains zero, but no reference_effect was reported, "
            "so a true null cannot be told apart from a test with no power. "
            "Report the real-run effect size this placebo must be able to detect.",
            evidence,
        )
    reference = abs(float(reference))
    half_width = (hi - lo) / 2.0
    evidence.update({"reference_effect": reference, "ci_half_width": half_width})
    if reference == 0 or half_width >= reference:
        return CheckResult.failed(
            "D2", PHASE,
            f"placebo CI half-width {half_width:.6g} is not smaller than the reference "
            f"effect {reference:.6g}; the test could not have detected the real effect, "
            "so containing zero is uninformative",
            evidence,
        )
    return CheckResult.passed("D2", PHASE, evidence)


@check("D3", PHASE, "UNCERTAINTY_COVERAGE — empirical coverage matches nominal")
def d3_uncertainty_coverage(repo: Repo, ctx: RunContext) -> CheckResult:
    try:
        fn = repo.resolve("coverage")
    except BindingError as exc:
        return CheckResult.na(
            "D3", PHASE,
            f"{exc}; coverage is measured on the blocked holdout via a Processing Job "
            "and the training plane has not been bootstrapped",
        )
    try:
        out = dict(fn())
    except Exception as exc:  # noqa: BLE001
        return CheckResult.failed("D3", PHASE, f"coverage raised {type(exc).__name__}: {exc}")

    for field in ("nominal", "empirical", "n"):
        if field not in out:
            return CheckResult.failed("D3", PHASE, f"coverage did not report {field}")

    nominal, empirical, n = float(out["nominal"]), float(out["empirical"]), int(out["n"])
    # mlkit owns this tolerance. A binding may ask for something stricter but
    # never looser -- a subject that sets its own pass mark sets no pass mark.
    tol = min(float(out.get("tol", MAX_COVERAGE_TOL)), MAX_COVERAGE_TOL)
    evidence = {"nominal": nominal, "empirical": empirical, "n": n, "tol": tol}

    if n < MIN_COVERAGE_N:
        return CheckResult.na(
            "D3", PHASE,
            f"n={n} is too small to measure coverage to ±{tol:.2f}; "
            f"need at least {MIN_COVERAGE_N} held-out points",
            evidence,
        )

    if abs(empirical - nominal) > tol:
        return CheckResult.failed(
            "D3", PHASE,
            f"empirical coverage {empirical:.3f} vs nominal {nominal:.3f} on n={n} "
            f"exceeds tolerance {tol:.3f}; the prediction intervals do not mean what they say",
            evidence,
        )
    return CheckResult.passed("D3", PHASE, evidence)


@check("D4", PHASE, "SENSITIVITY — human sign-off", human_only=True)
def d4_sensitivity(repo: Repo, ctx: RunContext) -> CheckResult:
    return CheckResult.escalated(
        "D4", PHASE, "D4 is reserved to the signatory; the agent may not write it"
    )


@check("D5", PHASE, "EXTERNAL_ANCHOR — human sign-off", human_only=True)
def d5_external_anchor(repo: Repo, ctx: RunContext) -> CheckResult:
    return CheckResult.escalated(
        "D5", PHASE, "D5 is reserved to the signatory; the agent may not write it"
    )
