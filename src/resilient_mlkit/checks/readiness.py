"""Phase 3 — CORRECTNESS.

Run order is set in ``PHASE_ORDER`` and is not numerical: R9 first, because the
licence gate is the cheapest check here and the most decisive. Everything after
it is ordered cheapest-and-most-decisive-first.

Two checks in this phase are the ones that actually catch fabricated science.
R5 refuses any synthetic, simulated or formula-derived row in val or test, and
R4 refuses a metric that cannot reproduce an analytically known answer. Between
them they catch the failure mode where a model scores beautifully against a
target it computed from its own inputs.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from ..core import policy
from ..core.repo import BindingError, Repo
from ..core.result import CheckResult, Status
from . import RunContext, check

PHASE = "readiness"

REQUIRED_REGION = "us-west-2"

#: The loosest tolerance R4 will accept, whatever a binding asks for. A
#: known-answer test compares against an analytic value, so anything beyond
#: floating-point noise means the metric is wrong, not imprecise.
MAX_METRIC_TOL = 1e-6

#: Region tokens that are a defect if they appear in training-plane config.
_FOREIGN_REGIONS = (
    "us-east-1", "us-east-2", "us-west-1", "eu-west-1", "eu-west-2",
    "eu-central-1", "ap-southeast-1", "ap-southeast-2", "ap-northeast-1",
)


@check("R9", PHASE, "LICENCE_GATE — no unlisted source or checkpoint, NOTICE.md current")
def r9_licence_gate(repo: Repo, ctx: RunContext) -> CheckResult:
    allowlist = policy.load(repo)
    if not allowlist.exists:
        return CheckResult.escalated(
            "R9", PHASE,
            f"{policy.ALLOWLIST_RELPATH} does not exist; only a human signatory "
            "may create it",
        )
    if allowlist.parse_error:
        return CheckResult.failed("R9", PHASE, allowlist.parse_error)

    defects = allowlist.defective_entries()
    if defects:
        first = list(defects.items())[:3]
        return CheckResult.failed(
            "R9", PHASE,
            "allowlist entries are structurally invalid: "
            + "; ".join(f"{k}: {', '.join(v)}" for k, v in first),
            {"defective": defects},
        )

    sources, err = policy.manifest_sources(repo)
    if err:
        return CheckResult.na("R9", PHASE, err)
    if not sources:
        # An empty manifest satisfies every "no unlisted source" test
        # vacuously. Passing the licence gate by declaring no data is the one
        # way to make R9 meaningless, so it is explicitly not a pass.
        return CheckResult.na(
            "R9", PHASE,
            "manifest resolved to zero sources; a licence gate over an empty "
            "manifest measures nothing",
        )

    unlisted = [s for s in sources if allowlist.verdict(s) is None]
    eval_only = [s for s in sources if allowlist.verdict(s) == "EVAL-ONLY"]
    blocked = [s for s in sources if allowlist.verdict(s) == "BLOCKED"]

    evidence = {
        "sources": len(sources),
        "unlisted": unlisted,
        "eval_only_in_manifest": eval_only,
        "blocked_in_manifest": blocked,
        "allowlist_signed": allowlist.signed,
    }

    if unlisted:
        return CheckResult.failed(
            "R9", PHASE,
            f"{len(unlisted)} source(s) not on the allowlist: " + ", ".join(sorted(unlisted)[:5]),
            evidence,
        )
    if blocked:
        return CheckResult.failed(
            "R9", PHASE, "BLOCKED source(s) in the manifest: " + ", ".join(sorted(blocked)), evidence
        )
    if eval_only:
        return CheckResult.failed(
            "R9", PHASE,
            "EVAL-ONLY source(s) present in a training manifest: " + ", ".join(sorted(eval_only)),
            evidence,
        )

    # NOTICE.md must be regenerable to exactly what is on disk, or it has drifted.
    notice_path = repo.path / "NOTICE.md"
    expected = policy.render_notice(repo, allowlist)
    if not notice_path.is_file():
        return CheckResult.failed("R9", PHASE, "NOTICE.md is absent; run `mlkit notice`", evidence)
    if notice_path.read_text() != expected:
        return CheckResult.failed(
            "R9", PHASE, "NOTICE.md is stale relative to the allowlist; run `mlkit notice`", evidence
        )

    if not allowlist.signed:
        return CheckResult.escalated(
            "R9", PHASE,
            "manifest is clean against the allowlist, but the allowlist is unsigned",
            evidence,
        )
    return CheckResult.passed("R9", PHASE, evidence)


@check("R1", PHASE, "CHECKPOINT_PROVENANCE — every checkpoint has URI, hash and licence")
def r1_checkpoint_provenance(repo: Repo, ctx: RunContext) -> CheckResult:
    try:
        fn = repo.resolve("checkpoint_provenance")
    except BindingError as exc:
        return CheckResult.na("R1", PHASE, str(exc))
    try:
        records = dict(fn())
    except Exception as exc:  # noqa: BLE001
        return CheckResult.failed(
            "R1", PHASE, f"checkpoint_provenance raised {type(exc).__name__}: {exc}"
        )
    if not records:
        return CheckResult.failed("R1", PHASE, "no checkpoints declared")

    incomplete: dict[str, list[str]] = {}
    for name, rec in records.items():
        rec = rec or {}
        missing = [f for f in ("uri", "sha256", "licence_url") if not str(rec.get(f) or "").strip()]
        if missing:
            incomplete[str(name)] = missing
    if incomplete:
        return CheckResult.failed(
            "R1", PHASE,
            "checkpoints without full provenance: "
            + "; ".join(f"{k} missing {','.join(v)}" for k, v in list(incomplete.items())[:3]),
            {"incomplete": incomplete},
        )
    return CheckResult.passed("R1", PHASE, {"checkpoints": len(records)})


@check("R2", PHASE, "OVERFIT_ONE_BATCH — recorded under the readiness gate")
def r2_overfit(repo: Repo, ctx: RunContext) -> CheckResult:
    from .triage import t2_overfit_one_batch

    result = t2_overfit_one_batch(repo, ctx)
    return CheckResult(
        check_id="R2", phase=PHASE, status=result.status,
        reason=result.reason, evidence=result.evidence,
    )


@check("R3", PHASE, "BLOCKED_SPLITS — train/val/test share no group")
def r3_blocked_splits(repo: Repo, ctx: RunContext) -> CheckResult:
    try:
        fn = repo.resolve("splits")
    except BindingError as exc:
        return CheckResult.na("R3", PHASE, str(exc))
    try:
        splits = {str(k): set(map(str, v)) for k, v in dict(fn()).items()}
    except Exception as exc:  # noqa: BLE001
        return CheckResult.failed("R3", PHASE, f"splits raised {type(exc).__name__}: {exc}")

    missing = [s for s in ("train", "val", "test") if s not in splits]
    if missing:
        return CheckResult.failed("R3", PHASE, "splits missing: " + ", ".join(missing))

    overlaps: dict[str, int] = {}
    names = ["train", "val", "test"]
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            shared = splits[a] & splits[b]
            if shared:
                overlaps[f"{a}&{b}"] = len(shared)

    evidence = {f"n_{k}": len(v) for k, v in splits.items()}
    if overlaps:
        return CheckResult.failed(
            "R3", PHASE,
            "groups appear in more than one split: "
            + ", ".join(f"{k}={v}" for k, v in overlaps.items()),
            {**evidence, "overlaps": overlaps},
        )
    if any(len(splits[s]) == 0 for s in names):
        return CheckResult.failed("R3", PHASE, "a split is empty", evidence)
    return CheckResult.passed("R3", PHASE, evidence)


@check("R4", PHASE, "METRIC_KNOWN_ANSWER — metrics reproduce analytic values")
def r4_metric_known_answer(repo: Repo, ctx: RunContext) -> CheckResult:
    try:
        fn = repo.resolve("metric_known_answer")
    except BindingError as exc:
        return CheckResult.na("R4", PHASE, str(exc))
    try:
        cases = list(fn())
    except Exception as exc:  # noqa: BLE001
        return CheckResult.failed("R4", PHASE, f"metric_known_answer raised {type(exc).__name__}: {exc}")
    if not cases:
        return CheckResult.failed("R4", PHASE, "no known-answer cases declared")

    failures: list[str] = []
    for case in cases:
        name = str(case.get("name", "<unnamed>"))
        if case.get("computed") is None or case.get("expected") is None:
            failures.append(f"{name}: case is missing 'computed' or 'expected'")
            continue
        try:
            got, want = float(case["computed"]), float(case["expected"])
        except (TypeError, ValueError):
            failures.append(f"{name}: 'computed'/'expected' are not numeric")
            continue
        # The binding may be stricter than mlkit but never looser. A subject
        # that supplies its own tolerance can pass any check by widening it,
        # which is loosening a threshold with extra steps.
        tol = min(float(case.get("tol", MAX_METRIC_TOL)), MAX_METRIC_TOL)
        if abs(got - want) > tol:
            failures.append(f"{name}: got {got:.6g}, expected {want:.6g} (tol {tol:g})")

    evidence = {"cases": len(cases), "failed": len(failures)}
    if failures:
        return CheckResult.failed(
            "R4", PHASE, "metric disagrees with known answer: " + "; ".join(failures[:3]), evidence
        )
    return CheckResult.passed("R4", PHASE, evidence)


@check("R5", PHASE, "DATA_PROVENANCE — no synthetic or formula-derived row in val/test")
def r5_data_provenance(repo: Repo, ctx: RunContext) -> CheckResult:
    try:
        fn = repo.resolve("provenance")
    except BindingError as exc:
        return CheckResult.na("R5", PHASE, str(exc))
    try:
        prov = {str(k): dict(v) for k, v in dict(fn()).items()}
    except Exception as exc:  # noqa: BLE001
        return CheckResult.failed("R5", PHASE, f"provenance raised {type(exc).__name__}: {exc}")

    missing = [s for s in ("train", "val", "test") if s not in prov]
    if missing:
        return CheckResult.failed("R5", PHASE, "provenance missing splits: " + ", ".join(missing))

    # The invariant is absolute: not a single simulated row in val or test.
    tainted: dict[str, dict[str, int]] = {}
    for split in ("val", "test"):
        bad = {
            kind: int(n)
            for kind, n in prov[split].items()
            if kind != "real" and int(n) > 0
        }
        if bad:
            tainted[split] = bad

    evidence = {split: prov[split] for split in ("train", "val", "test")}
    if tainted:
        detail = "; ".join(
            f"{split}: " + ", ".join(f"{k}={v}" for k, v in sorted(kinds.items()))
            for split, kinds in tainted.items()
        )
        return CheckResult.failed(
            "R5", PHASE,
            f"non-real rows present in evaluation splits ({detail}); the avoided-loss "
            "estimate cannot be believed against a target the pipeline generated",
            {**evidence, "tainted": tainted},
        )
    if int(prov["val"].get("real", 0)) == 0 or int(prov["test"].get("real", 0)) == 0:
        return CheckResult.failed("R5", PHASE, "val or test contains zero real rows", evidence)
    return CheckResult.passed("R5", PHASE, evidence)


@check("R6", PHASE, "DETERMINISM — same seed, byte-identical result")
def r6_determinism(repo: Repo, ctx: RunContext) -> CheckResult:
    try:
        fn = repo.resolve("deterministic_run")
    except BindingError as exc:
        return CheckResult.na("R6", PHASE, str(exc))
    try:
        first = fn(seed=1234)
        second = fn(seed=1234)
    except Exception as exc:  # noqa: BLE001
        return CheckResult.failed("R6", PHASE, f"deterministic_run raised {type(exc).__name__}: {exc}")

    a, b = repr(first), repr(second)
    if a != b:
        return CheckResult.failed(
            "R6", PHASE,
            "two runs at seed 1234 disagree; training is not reproducible",
            {"first": a[:200], "second": b[:200]},
        )
    return CheckResult.passed("R6", PHASE, {"seed": 1234, "digest_len": len(a)})


@check("R7", PHASE, "REMOTE_PARITY — us-west-2, pinned image, one entrypoint")
def r7_remote_parity(repo: Repo, ctx: RunContext) -> CheckResult:
    # Scan FIRST. A config pointing at another region is a defect that is
    # measurable right now, and returning NA because [remote] is undeclared
    # would report a present, found defect as unmeasurable.
    strays = _scan_foreign_regions(repo.path)
    remote = repo.config().get("remote") or {}
    evidence: dict[str, object] = {
        "stray_region_refs": len(strays),
        "strays": [f"{p}:{r}" for p, r in strays[:8]],
    }

    if strays:
        return CheckResult.failed(
            "R7", PHASE,
            f"{len(strays)} config file(s) reference a region other than "
            f"{REQUIRED_REGION}: " + ", ".join(f"{p}→{r}" for p, r in strays[:4]),
            evidence,
        )

    if not remote:
        return CheckResult.na(
            "R7", PHASE,
            "no [remote] section in .mlkit/repo.toml; region and image are undeclared "
            "(no foreign-region config found, but parity itself is unmeasured)",
            evidence,
        )

    problems: list[str] = []
    region = str(remote.get("region") or "")
    image = str(remote.get("image") or "")

    if region != REQUIRED_REGION:
        problems.append(f"declared region {region or '<unset>'!r} is not {REQUIRED_REGION}")
    if not image:
        problems.append("no ECR image declared")
    elif "@sha256:" not in image:
        problems.append(f"image {image!r} is not pinned by digest")
    elif f".{REQUIRED_REGION}.amazonaws.com" not in image:
        problems.append(f"image {image!r} is not in an {REQUIRED_REGION} registry")

    evidence.update({"region": region, "image": image})
    if problems:
        return CheckResult.failed("R7", PHASE, "; ".join(problems), evidence)
    return CheckResult.passed("R7", PHASE, evidence)


@check("R8", PHASE, "REPORT — readiness report generated from measured results")
def r8_report(repo: Repo, ctx: RunContext) -> CheckResult:
    prior = {k: v for k, v in ctx.prior.items() if k.startswith("R") and k != "R8"}
    if not prior:
        return CheckResult.na("R8", PHASE, "no R-check results in this run to report on")

    lines = [
        f"# Readiness report — resilient-{repo.name}",
        "",
        f"- run nonce: `{ctx.nonce}`",
        f"- git SHA: `{repo.git_sha}`",
        f"- branch: `{repo.branch}`",
        "",
        "| check | status | detail |",
        "|---|---|---|",
    ]
    from . import PHASE_ORDER

    for cid in PHASE_ORDER["readiness"]:
        if cid == "R8" or cid not in prior:
            continue
        r = prior[cid]
        detail = r.reason.replace("|", "\\|") or "measured"
        lines.append(f"| {cid} | {r.status.value} | {detail} |")
    lines.append("")

    out = repo.path / "reports" / "readiness.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines))

    counts: dict[str, int] = {}
    for r in prior.values():
        counts[r.status.value] = counts.get(r.status.value, 0) + 1
    return CheckResult.passed(
        "R8", PHASE, {"path": str(out.relative_to(repo.path)), "counts": counts}
    )


# -- helpers --------------------------------------------------------------


def _scan_foreign_regions(root: Path) -> list[tuple[str, str]]:
    """Find non-us-west-2 AWS region tokens in training-plane config.

    Scoped to config-ish files rather than the whole tree: a region string in a
    vendored SDK or a changelog is noise, and a check that cries wolf gets
    disabled.
    """
    hits: list[tuple[str, str]] = []
    patterns = ("*.yaml", "*.yml", "*.toml", "*.tf", "*.json", "*.cfg", "*.ini")
    roots = [root / "config", root / "configs", root / "terraform", root / "infra", root / "deploy"]
    for base in roots:
        if not base.is_dir():
            continue
        for pattern in patterns:
            for path in base.rglob(pattern):
                try:
                    text = path.read_text(errors="ignore")
                except OSError:
                    continue
                for region in _FOREIGN_REGIONS:
                    if region in text:
                        hits.append((str(path.relative_to(root)), region))
                        break
    return hits
