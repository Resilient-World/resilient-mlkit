"""Phase 1 — TRIAGE.

Triage diagnoses; it does not repair. Every check here answers one question
about whether a repo could train at all, and answers it by running the repo's
own code against the repo's own data. Nothing here is inferred from a document.

T5 sits in triage rather than later on purpose: if a repo is training on
something that cannot be sold, that should surface on day one, before any
selection research is commissioned for it.
"""

from __future__ import annotations

import math

from ..core import policy
from ..core.repo import BindingError, Repo
from ..core.result import CheckResult, CredentialRequired
from . import RunContext, check

PHASE = "triage"


@check("T1", PHASE, "BATCH_LOAD — one real batch materialises from the real loader")
def t1_batch_load(repo: Repo, ctx: RunContext) -> CheckResult:
    try:
        fn = repo.resolve("batch")
    except BindingError as exc:
        return CheckResult.na("T1", PHASE, str(exc))

    try:
        batch = fn()
    except CredentialRequired:
        raise
    except Exception as exc:  # noqa: BLE001 - the failure IS the finding
        return CheckResult.failed(
            "T1",
            PHASE,
            f"batch binding raised {type(exc).__name__}: {exc}",
        )

    shapes = _describe(batch)
    if not shapes:
        return CheckResult.failed(
            "T1", PHASE, "batch binding returned an empty or unrecognised batch"
        )
    return CheckResult.passed("T1", PHASE, {"batch": shapes})


@check("T2", PHASE, "OVERFIT_ONE_BATCH — loss collapses on a single batch")
def t2_overfit_one_batch(repo: Repo, ctx: RunContext) -> CheckResult:
    try:
        fn = repo.resolve("overfit_one_batch")
    except BindingError as exc:
        return CheckResult.na("T2", PHASE, str(exc))

    try:
        losses = list(fn())
    except CredentialRequired:
        raise
    except Exception as exc:  # noqa: BLE001
        return CheckResult.failed(
            "T2", PHASE, f"overfit binding raised {type(exc).__name__}: {exc}"
        )

    if len(losses) < 2:
        return CheckResult.failed(
            "T2",
            PHASE,
            f"overfit binding returned {len(losses)} loss value(s); need a trajectory",
        )

    first, last = float(losses[0]), float(losses[-1])
    evidence = {
        "steps": len(losses),
        "loss_first": first,
        "loss_last": last,
        "ratio": (last / first) if first else None,
    }
    # A loss that diverged to NaN is the single most common way a training run
    # fails, and it is exactly what this check exists to catch -- but every
    # comparison a NaN takes part in is False, so `first <= 0` and
    # `last > 0.1 * first` are False together and the trajectory [2.0, nan]
    # returned PASS. Same defect class as the D2/E1 hard stops and the R5 row
    # count, refused the same way: by name, before the value is reasoned about.
    non_finite = [
        name for name, value in (("loss_first", first), ("loss_last", last))
        if not math.isfinite(value)
    ]
    if non_finite:
        return CheckResult.failed(
            "T2", PHASE,
            "overfit trajectory is not finite at " + ", ".join(non_finite)
            + "; a loss that did not resolve to a number has not collapsed, it diverged",
            evidence,
        )
    if first <= 0:
        return CheckResult.failed(
            "T2", PHASE, f"initial loss {first} is not positive; loss is misdefined",
            evidence,
        )
    # A model that cannot drive a single batch's loss down by an order of
    # magnitude has a wiring defect, not a tuning problem.
    if last > 0.1 * first:
        return CheckResult.failed(
            "T2",
            PHASE,
            f"loss fell only {first:.4g} -> {last:.4g} over {len(losses)} steps "
            "(< 10x); model cannot overfit one batch",
            evidence,
        )
    return CheckResult.passed("T2", PHASE, evidence)


@check("T3", PHASE, "WEIGHTS_STATUS — declared checkpoints resolve to real pretrained weights")
def t3_weights_status(repo: Repo, ctx: RunContext) -> CheckResult:
    try:
        fn = repo.resolve("checkpoint_status")
    except BindingError as exc:
        return CheckResult.na("T3", PHASE, str(exc))

    try:
        statuses = dict(fn())
    except CredentialRequired:
        raise
    except Exception as exc:  # noqa: BLE001
        return CheckResult.failed(
            "T3", PHASE, f"checkpoint_status binding raised {type(exc).__name__}: {exc}"
        )

    if not statuses:
        return CheckResult.failed(
            "T3", PHASE, "checkpoint_status returned no checkpoints"
        )

    not_pretrained = {
        name: state
        for name, state in statuses.items()
        if str(state).split(":")[0] != "LOADED_PRETRAINED"
    }
    if not_pretrained:
        return CheckResult.failed(
            "T3",
            PHASE,
            "checkpoints not resolving to pretrained weights: "
            + ", ".join(f"{k}={v}" for k, v in sorted(not_pretrained.items())),
            {"checkpoints": statuses},
        )
    return CheckResult.passed("T3", PHASE, {"checkpoints": statuses})


@check("T4", PHASE, "LABEL_COUNTS — observed labels counted from real data")
def t4_label_counts(repo: Repo, ctx: RunContext) -> CheckResult:
    try:
        fn = repo.resolve("label_counts")
    except BindingError as exc:
        return CheckResult.na("T4", PHASE, str(exc))

    try:
        counts = dict(fn())
    except CredentialRequired:
        raise
    except Exception as exc:  # noqa: BLE001
        return CheckResult.failed(
            "T4", PHASE, f"label_counts binding raised {type(exc).__name__}: {exc}"
        )

    if not counts:
        return CheckResult.failed(
            "T4", PHASE, "label_counts returned no observed labels"
        )

    # int(float('nan')) raises ValueError, which escaped the check entirely and
    # reached the runner as an unhandled crash carrying a traceback into the
    # reason field. A count that is not a whole number is a defect this check
    # should name, not one it should die of.
    try:
        total = sum(int(v) for v in counts.values())
    except (TypeError, ValueError) as exc:
        return CheckResult.failed(
            "T4", PHASE,
            f"label_counts returned a value that is not a whole count "
            f"({type(exc).__name__}: {exc})",
            {"counts": {k: repr(v) for k, v in counts.items()}},
        )
    if total == 0:
        return CheckResult.failed(
            "T4", PHASE, "every observed-label count is zero", {"counts": counts}
        )
    return CheckResult.passed("T4", PHASE, {"counts": counts, "total": total})


@check("T5", PHASE, "LICENCE_COVERAGE — every pipeline source is on the signed allowlist")
def t5_licence_coverage(repo: Repo, ctx: RunContext) -> CheckResult:
    allowlist = policy.load(repo)

    if not allowlist.exists:
        return CheckResult.escalated(
            "T5",
            PHASE,
            f"{policy.ALLOWLIST_RELPATH} does not exist; the allowlist is signed by a "
            "human and cannot be created by the agent",
        )
    if allowlist.parse_error:
        return CheckResult.failed(
            "T5", PHASE, f"{policy.ALLOWLIST_RELPATH}: {allowlist.parse_error}"
        )

    sources, err = policy.manifest_sources(repo)
    if err:
        return CheckResult.na("T5", PHASE, err)
    if not sources:
        return CheckResult.na(
            "T5", PHASE, "manifest resolved to zero sources; nothing to licence-check"
        )

    unlisted = [s for s in sources if allowlist.verdict(s) is None]
    not_allowed = {
        s: allowlist.verdict(s)
        for s in sources
        if allowlist.verdict(s) not in (None, "ALLOWED")
    }
    evidence = {
        "sources": len(sources),
        "unlisted": unlisted,
        "not_allowed": not_allowed,
        "allowlist_signed": allowlist.signed,
    }

    if unlisted:
        return CheckResult.failed(
            "T5",
            PHASE,
            f"{len(unlisted)} source(s) absent from the allowlist: "
            + ", ".join(sorted(unlisted)[:5]),
            evidence,
        )
    if not_allowed:
        return CheckResult.failed(
            "T5",
            PHASE,
            "sources present but not ALLOWED: "
            + ", ".join(f"{k}={v}" for k, v in sorted(not_allowed.items())),
            evidence,
        )
    if not allowlist.signed:
        return CheckResult.escalated(
            "T5",
            PHASE,
            f"all {len(sources)} source(s) are listed ALLOWED, but the allowlist is "
            "unsigned; a determination nobody has signed is a proposal",
            evidence,
        )
    return CheckResult.passed("T5", PHASE, evidence)


# -- helpers --------------------------------------------------------------


def _describe(batch: object) -> dict[str, str]:
    """Describe a batch structurally without importing torch.

    mlkit is installed into every repo environment, so it must not assume a
    tensor library is present. Duck-typing on ``shape``/``dtype`` covers torch,
    numpy and xarray alike.
    """
    out: dict[str, str] = {}

    def describe_one(key: str, value: object) -> None:
        shape = getattr(value, "shape", None)
        dtype = getattr(value, "dtype", None)
        if shape is not None:
            out[key] = f"shape={tuple(shape)} dtype={dtype}"
        elif isinstance(value, (list, tuple)):
            out[key] = f"{type(value).__name__}(len={len(value)})"

    if isinstance(batch, dict):
        for key, value in batch.items():
            describe_one(str(key), value)
    elif isinstance(batch, (list, tuple)):
        for i, value in enumerate(batch):
            describe_one(f"[{i}]", value)
    else:
        describe_one("batch", batch)
    return out
