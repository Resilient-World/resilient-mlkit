"""Phase 5 — ECONOMICS.

E1 is the highest-leverage check in the package. If the scaling curve is flat
between 10% and 25% of the data, the full run buys nothing: the bottleneck is
labels, not compute, and spending the GPU budget is the wrong move however
cheap the spot price looks. That is a hard stop, not a tradeoff.

E3's remedy clause matters as much as its threshold. If GPU utilisation is
below the floor because the dataloader is starving it, the fix is FSx for
Lustre or Mountpoint for S3 -- never a larger instance. Buying compute to solve
an I/O problem is the most common way a credit allocation evaporates.

THE LADDER IS DECLARABLE; THE THRESHOLD IS NOT
----------------------------------------------
``{0.01, 0.10, 0.25}`` was hard-coded here, and round 8 measured what that
costs. ``resilient-fray``'s probe measured 10% and 25%; under mlkit's own
relative rule its curve is comfortably not flat (+8.69%, from -151.29137 to
-138.13969 oriented larger-is-better), and E1 would have FAILED IT ON
CONTRACT rather than on substance -- for the absence of a 1% rung. So fray
never bound ``scaling_probe``, E1 read NA, and the hard stop that exists to
protect the GPU budget was not armed at all. A gate an adopter cannot bind is
not a strict gate; it is an absent one.

A repo may now declare its own ``[scaling] fractions`` ladder, and the verdict
is taken between its TOP TWO rungs. Two structural refusals stop that from
being a way to buy a pass, and both are refusals OF THE DECLARATION, before any
curve is read:

* the top rung may not sit below ``MIN_TOP_FRACTION``. E1 asks whether the run
  you would actually buy is worth buying, and a ladder topping out at 5% never
  asks it;
* the top two rungs may be no further apart than mlkit's own,
  ``MAX_TOP_STEP`` = ``0.25 / 0.10``. A ladder of ``[0.01, 0.02, 0.25]`` asks
  whether 12.5x the data helps, which almost anything passes.

``FLATNESS_EPSILON`` itself stays mlkit's and is not declarable, for the reason
D3's tolerance is clamped: a subject that sets its own pass mark sets no pass
mark.
"""

from __future__ import annotations

import math
from itertools import pairwise

from ..core import declaration
from ..core.repo import BindingError, Repo
from ..core.result import ALLOW_DIRTY_KEY, CheckResult, CredentialRequired
from . import RunContext, check

PHASE = "economics"

#: Below this, the GPU is idling and the run is buying wall-clock, not learning.
GPU_UTIL_FLOOR = 0.80

#: Relative improvement between the top two rungs of the ladder below which the
#: curve is flat. mlkit's, not the subject's, and not declarable.
FLATNESS_EPSILON = 0.01

#: The ``.mlkit/repo.toml`` section carrying E1's fraction ladder as data --
#: ``[scaling]`` / ``fractions = [0.01, 0.10, 0.25]`` -- beside the
#: ``scaling_probe`` binding it adjudicates. Optional: a repo that declares
#: nothing is judged on ``DEFAULT_FRACTIONS``, which is the ladder E1 required
#: before the section existed.
SCALING_SECTION = "scaling"

#: Every key ``[scaling]`` may carry.
SCALING_KEYS = frozenset({"fractions"})

#: The ladder E1 requires of a repo that has declared none.
DEFAULT_FRACTIONS: tuple[float, ...] = (0.01, 0.10, 0.25)

#: Fewest rungs a declared ladder may have. Three, because that is what
#: ``DEFAULT_FRACTIONS`` is: two carry the verdict and the third is the anchor a
#: binding orients its metric against (``tests/test_economics_controls.py``'s
#: orientation pair uses it for exactly that). "A two-point curve cannot answer
#: the question" is a refusal E1 already makes; declaring a ladder may not be a
#: way around it.
MIN_RUNGS = 3

#: A declared ladder's top rung may not sit below mlkit's own.
MIN_TOP_FRACTION = 0.25

#: Widest ratio between a declared ladder's top two rungs, which is exactly the
#: ratio mlkit's own ladder asks: 0.25 / 0.10, and that division is 2.5 exactly
#: in IEEE-754 doubles rather than approximately.
MAX_TOP_STEP = 0.25 / 0.10

#: Float-representation allowance on the ratio above, and emphatically not a
#: tolerance: a repo writing 0.1 and 0.25 should not be refused because the
#: quotient of two decimals it did not choose the binary expansion of lands one
#: ulp high. Anything a person could mean by "a wider step" is orders of
#: magnitude above this.
TOP_STEP_EPS = 1e-9


def read_fraction_ladder(
    repo: Repo, ctx: RunContext
) -> tuple[tuple[float, ...] | None, dict[str, object], str, str]:
    """``(fractions, ladder_evidence, na_reason, fail_reason)``.

    Three outcomes, same shape and same reasoning as
    ``checks.decision.read_halt_region``: an UNCOMMITTED ladder is an NA (the
    standard is in nobody's git history), a MALFORMED one is a FAIL (mlkit
    cannot read it as a ladder at all), and no ladder is neither -- it is
    ``DEFAULT_FRACTIONS``, silently, because that is what the whole fleet runs
    under today.
    """
    decl = declaration.read(repo, SCALING_SECTION, allow_dirty=ctx.allow_dirty)
    if decl.uncommitted:
        return None, {}, (
            f"SCALING_UNDECLARED_AT_HEAD: {decl.detail}. The fraction ladder decides "
            "which two points E1's hard stop is measured between, so it is read from "
            "the blob at HEAD and not from the working tree. Commit it, or pass "
            "--allow-dirty for a diagnosis that cannot reach a PASS"
        ), ""
    if not decl.declared:
        return DEFAULT_FRACTIONS, {"fractions": list(DEFAULT_FRACTIONS)}, "", ""

    shape = declaration.table_and_keys(decl, SCALING_KEYS)
    if shape:
        return None, {}, "", f"SCALING_MALFORMED: {shape}"

    raw = dict(decl.value).get("fractions")
    if not isinstance(raw, list):
        kind = "absent" if raw is None else f"a {type(raw).__name__}"
        return None, {}, "", (
            f"SCALING_MALFORMED: [{SCALING_SECTION}] fractions is {kind}; declare the "
            "ladder as an array of fractions of the data, e.g. "
            "`fractions = [0.01, 0.10, 0.25]`"
        )

    rungs: list[float] = []
    for index, item in enumerate(raw):
        value, problem = declaration.finite_number(
            item, f"[{SCALING_SECTION}] fractions[{index}]"
        )
        if value is None:
            return None, {}, "", f"SCALING_MALFORMED: {problem}"
        if not 0.0 < value <= 1.0:
            return None, {}, "", (
                f"SCALING_MALFORMED: [{SCALING_SECTION}] fractions[{index}] is {value!r}; "
                "each rung is a FRACTION of the data and must lie in (0, 1] -- 0.25 for "
                "a quarter, not 25"
            )
        rungs.append(value)

    if len(rungs) < MIN_RUNGS:
        return None, {}, "", (
            f"SCALING_MALFORMED: [{SCALING_SECTION}] declares {len(rungs)} rung(s); E1 "
            f"needs at least {MIN_RUNGS}. Two points cannot answer the question, and "
            "declaring a ladder is not a way around that refusal"
        )
    if any(b <= a for a, b in pairwise(rungs)):
        return None, {}, "", (
            f"SCALING_MALFORMED: [{SCALING_SECTION}] fractions {rungs} is not strictly "
            "increasing; E1 reads the LAST two rungs as the top of the ladder, so an "
            "unordered list would silently move which comparison the hard stop is taken on"
        )

    second, top = rungs[-2], rungs[-1]
    if top < MIN_TOP_FRACTION:
        return None, {}, "", (
            f"SCALING_TOP_TOO_LOW: [{SCALING_SECTION}] tops out at {top:.4g}, below "
            f"mlkit's {MIN_TOP_FRACTION:.4g}. E1 asks whether the run you would actually "
            "buy is worth buying; a ladder that stops short of a quarter of the data "
            "never asks it, and a curve still rising at 5% says nothing about 25%"
        )
    if top / second > MAX_TOP_STEP + TOP_STEP_EPS:
        return None, {}, "", (
            f"SCALING_TOP_STEP_TOO_WIDE: [{SCALING_SECTION}]'s top two rungs are "
            f"{second:.4g} and {top:.4g}, a step of {top / second:.4g}x against mlkit's "
            f"{MAX_TOP_STEP:.4g}x. The verdict is the relative gain across that step, so "
            "widening it is the one way a declared ladder could make a flat curve look "
            "steep -- more data always buys something if you ask for enough more"
        )
    ladder: dict[str, object] = {
        "fractions": list(rungs),
        "scaling_declared_in": decl.source,
    }
    if decl.allow_dirty:
        ladder[ALLOW_DIRTY_KEY] = True
    return tuple(rungs), ladder, "", ""


@check("E1", PHASE, "SCALING_PROBE — declared fraction ladder, not flat at the top")
def e1_scaling_probe(repo: Repo, ctx: RunContext) -> CheckResult:
    try:
        fn = repo.resolve("scaling_probe")
    except BindingError as exc:
        return CheckResult.na(
            "E1", PHASE,
            f"{exc}; scaling probes run as SageMaker jobs and the training plane has "
            "not been bootstrapped",
        )

    fractions, ladder, na_reason, fail_reason = read_fraction_ladder(repo, ctx)
    if fractions is None:
        return (
            CheckResult.na("E1", PHASE, na_reason)
            if na_reason
            else CheckResult.failed("E1", PHASE, fail_reason)
        )

    try:
        curve = {float(k): float(v) for k, v in dict(fn()).items()}
    except CredentialRequired:
        raise
    except Exception as exc:  # noqa: BLE001
        return CheckResult.failed("E1", PHASE, f"scaling_probe raised {type(exc).__name__}: {exc}")

    missing = [f for f in fractions if f not in curve]
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
            {"curve": curve, "non_finite_at": non_finite, **ladder},
        )

    # The TOP TWO rungs of whichever ladder is in force. With no declaration
    # that is `curve[0.10], curve[0.25]` -- the same two lookups, now named by
    # where they sit on the ladder rather than by two literals only mlkit knew.
    second, top = fractions[-2], fractions[-1]
    at_second, at_top = curve[second], curve[top]
    # Curve values are "better is larger" by contract; the binding is
    # responsible for orienting its own metric before reporting it.
    gain = (at_top - at_second) / abs(at_second) if at_second else 0.0
    evidence: dict[str, object] = {
        "curve": curve,
        "gain_top_two": gain,
        "from_fraction": second,
        "to_fraction": top,
        **ladder,
    }
    # `gain_10_to_25` is kept -- and ONLY -- where the name is literally true.
    # Under a declared ladder of [0.02, 0.20, 0.50] a key called `gain_10_to_25`
    # would be a fabricated label on a real number, which is the failure mode
    # CLAUDE.md rule 2 is about: a plausible figure does not get checked. Every
    # reader wanting the number unconditionally reads `gain_top_two`, which says
    # what it is, beside `from_fraction`/`to_fraction`, which say between what.
    if (second, top) == (0.10, 0.25):
        evidence["gain_10_to_25"] = gain

    if gain <= FLATNESS_EPSILON:
        return CheckResult.failed(
            "E1", PHASE,
            f"curve is flat between {second:.0%} and {top:.0%} "
            f"(gain {gain:+.3%} <= {FLATNESS_EPSILON:.1%}); "
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

    # `nan < GPU_UTIL_FLOOR` is False, so a utilisation figure that did not
    # resolve cleared the floor -- the same defect class the E1 guard above
    # refuses. A profiler that reported nothing has not reported 100%.
    if not math.isfinite(util):
        return CheckResult.failed(
            "E3", PHASE,
            "efficiency reported a non-finite gpu_util; a utilisation that did not "
            "resolve to a number has not been measured and cannot clear the floor",
            evidence,
        )
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
