"""Phase 5 — ECONOMICS.

E1 is the highest-leverage check in the package. If the scaling curve is flat
between 10% and 25% of the data, the full run buys nothing: the bottleneck is
labels, not compute, and spending the GPU budget is the wrong move however
cheap the spot price looks. That is a hard stop, not a tradeoff.

E3's remedy clause matters as much as its threshold. If GPU utilisation is
below the floor because the dataloader is starving it, the fix is FSx for
Lustre or Mountpoint for S3 -- never a larger instance. Buying compute to solve
an I/O problem is the most common way a credit allocation evaporates.
"""

from __future__ import annotations

import math

from ..core.repo import BindingError, Repo
from ..core.result import CheckResult, CredentialRequired
from . import RunContext, check

PHASE = "economics"

#: Below this, the GPU is idling and the run is buying wall-clock, not learning.
GPU_UTIL_FLOOR = 0.80

#: Relative improvement from 10% to 25% of data below which the curve is flat.
FLATNESS_EPSILON = 0.01


@check("E1", PHASE, "SCALING_PROBE — 1/10/25% curve, not flat at the top")
def e1_scaling_probe(repo: Repo, ctx: RunContext) -> CheckResult:
    try:
        fn = repo.resolve("scaling_probe")
    except BindingError as exc:
        return CheckResult.na(
            "E1", PHASE,
            f"{exc}; scaling probes run as SageMaker jobs and the training plane has "
            "not been bootstrapped",
        )
    try:
        curve = {float(k): float(v) for k, v in dict(fn()).items()}
    except CredentialRequired:
        raise
    except Exception as exc:  # noqa: BLE001
        return CheckResult.failed("E1", PHASE, f"scaling_probe raised {type(exc).__name__}: {exc}")

    missing = [f for f in (0.01, 0.10, 0.25) if f not in curve]
    if missing:
        return CheckResult.failed(
            "E1", PHASE, "scaling curve missing fractions: " + ", ".join(str(m) for m in missing)
        )

    # A fraction that is present but did not resolve to a number is not a
    # point on a curve. `float()` accepts NaN and the infinities, including as
    # the strings "nan"/"inf"; NaN is truthy, so it takes the dividing branch
    # below, and `nan <= FLATNESS_EPSILON` is False -- which switches this hard
    # stop off entirely. An infinity is worse: the gain reads +inf and the
    # flattest possible probe is reported as the steepest. Refused by naming
    # the fraction, the same way R5 refuses a non-finite row count.
    non_finite = [str(frac) for frac in sorted(curve) if not math.isfinite(curve[frac])]
    if non_finite:
        return CheckResult.failed(
            "E1", PHASE,
            "scaling curve is not finite at fraction(s) " + ", ".join(non_finite)
            + "; a probe that did not resolve to a number at every fraction has not "
            "measured a curve, and must not be read as a rising one",
            {"curve": curve, "non_finite_at": non_finite},
        )

    at10, at25 = curve[0.10], curve[0.25]
    # Curve values are "better is larger" by contract; the binding is
    # responsible for orienting its own metric before reporting it.
    gain = (at25 - at10) / abs(at10) if at10 else 0.0
    evidence = {"curve": curve, "gain_10_to_25": gain}

    if gain <= FLATNESS_EPSILON:
        return CheckResult.failed(
            "E1", PHASE,
            f"curve is flat between 10% and 25% (gain {gain:+.3%} <= {FLATNESS_EPSILON:.1%}); "
            "the bottleneck is labels, not compute. HARD STOP — do not scale.",
            {**evidence, "halt": True},
        )
    return CheckResult.passed("E1", PHASE, evidence)


@check("E2", PHASE, "HPARAM_SANITY — LR range test and batch/throughput curve")
def e2_hparam_sanity(repo: Repo, ctx: RunContext) -> CheckResult:
    try:
        fn = repo.resolve("hparam_sanity")
    except BindingError as exc:
        return CheckResult.na(
            "E2", PHASE,
            f"{exc}; the sweep runs on SageMaker AMT and the training plane has not "
            "been bootstrapped",
        )
    try:
        out = dict(fn())
    except CredentialRequired:
        raise
    except Exception as exc:  # noqa: BLE001
        return CheckResult.failed("E2", PHASE, f"hparam_sanity raised {type(exc).__name__}: {exc}")

    missing = [f for f in ("lr_range", "throughput_curve", "winning_config") if f not in out]
    if missing:
        return CheckResult.failed("E2", PHASE, "hparam_sanity did not report: " + ", ".join(missing))
    if not out.get("mlflow_run_id"):
        return CheckResult.failed(
            "E2", PHASE, "no MLflow run id; the sweep must be logged to be evidence"
        )
    return CheckResult.passed(
        "E2", PHASE,
        {
            "lr_range": out["lr_range"],
            "throughput_points": len(out["throughput_curve"] or []),
            "winning_config": out["winning_config"],
            "mlflow_run_id": out["mlflow_run_id"],
        },
    )


@check("E3", PHASE, "EFFICIENCY_FLOOR — GPU >= 80% with a profiler trace")
def e3_efficiency_floor(repo: Repo, ctx: RunContext) -> CheckResult:
    try:
        fn = repo.resolve("efficiency")
    except BindingError as exc:
        return CheckResult.na(
            "E3", PHASE,
            f"{exc}; utilisation is measured on a SageMaker job and the training plane "
            "has not been bootstrapped",
        )
    try:
        out = dict(fn())
    except CredentialRequired:
        raise
    except Exception as exc:  # noqa: BLE001
        return CheckResult.failed("E3", PHASE, f"efficiency raised {type(exc).__name__}: {exc}")

    if "gpu_util" not in out:
        return CheckResult.failed("E3", PHASE, "efficiency did not report gpu_util")
    if not out.get("profiler_trace"):
        return CheckResult.failed(
            "E3", PHASE, "no profiler trace attached; a utilisation number without a trace is a claim"
        )

    util = float(out["gpu_util"])
    dataloader_bound = bool(out.get("dataloader_bound", False))
    evidence = {
        "gpu_util": util,
        "profiler_trace": out["profiler_trace"],
        "dataloader_bound": dataloader_bound,
    }

    if util < GPU_UTIL_FLOOR:
        remedy = (
            "the dataloader is the bottleneck; the remedy is FSx for Lustre or "
            "Mountpoint for S3, not a larger instance type"
            if dataloader_bound
            else "cause not attributed to the dataloader; profile before changing anything"
        )
        return CheckResult.failed(
            "E3", PHASE,
            f"GPU utilisation {util:.1%} is below the {GPU_UTIL_FLOOR:.0%} floor; {remedy}",
            evidence,
        )
    return CheckResult.passed("E3", PHASE, evidence)


@check("E4", PHASE, "CREDIT_BUDGET_AND_KILL — human sign-off", human_only=True)
def e4_credit_budget(repo: Repo, ctx: RunContext) -> CheckResult:
    return CheckResult.escalated(
        "E4", PHASE,
        "E4 allocates credits and wires a Budgets alarm — a billing action reserved "
        "to the signatory",
    )


@check("E5", PHASE, "RUN_HYPOTHESIS — human sign-off", human_only=True)
def e5_run_hypothesis(repo: Repo, ctx: RunContext) -> CheckResult:
    return CheckResult.escalated(
        "E5", PHASE,
        "E5 states what each run will teach and what would change your mind; it is "
        "human-written by design",
    )
