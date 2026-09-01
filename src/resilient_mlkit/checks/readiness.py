"""Phase 3 — CORRECTNESS.

Run order is set in ``PHASE_ORDER`` and is not numerical: R9 first, because the
licence gate is the cheapest check here and the most decisive. Everything after
it is ordered cheapest-and-most-decisive-first.

Three checks in this phase are the ones that actually catch fabricated science.
R5 refuses any synthetic, simulated or formula-derived row in val or test, and
R4 refuses a metric that cannot reproduce an analytically known answer. Between
them they catch the failure mode where a model scores beautifully against a
target it computed from its own inputs.

R10 catches the failure mode neither of them can reach. R3, R4 and R5 all work
through declared bindings, which means they only ever see the label panel and
the metric implementations a repo chose to expose. An adversarial sweep in
August 2026 found seventeen defects of one shape -- a measured quantity given a
plausible numeric default that then satisfied the gate consuming it -- and
every one of them lived in code no readiness check reached. R10 walks the
declared source tree with ``ast`` instead of importing anything, so it sees the
trainer's own feature path.

R11 closes the last gap in that argument. R10 walks the trees a repo DECLARES,
and resilient-choco PR #160 shipped fabricated data under ``scripts/`` --
outside the declared trees, outside that repo's own generated-paths guard, and
past fifty-one green tests. R11 walks every Python file in the repo and looks
for one shape only: a value drawn from an RNG, flowed into a data record, and
stamped with a provenance field claiming the record was observed. That stamp
is what makes it a fabrication rather than a fixture, and it is what R5 counts
rows by -- so R11 runs before R5, because when it fires, R5 is counting with a
ruler somebody drew.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from ..core import (
    environment,
    fabricated_targets,
    fabrication,
    metric_registry,
    policy,
    report,
    served_reimplementation,
)
from ..core.repo import BindingError, Repo
from ..core.result import CheckResult, CredentialRequired
from . import RunContext, check

PHASE = "readiness"

REQUIRED_REGION = "us-west-2"

#: The loosest tolerance R4 will accept, whatever a binding asks for. A
#: known-answer test compares against an analytic value, so anything beyond
#: floating-point noise means the metric is wrong, not imprecise.
MAX_METRIC_TOL = 1e-6

#: Fewest groups an evaluation split may contain and still be a blocked split.
#: Two is the absolute floor -- with one group there is no contrast at all, and
#: any spatial claim reduces to a claim about that single site. This is a floor,
#: not a target: two groups is thin, and R3 passing at two says only that the
#: split is structurally blocked, never that the holdout is adequately powered.
MIN_HOLDOUT_GROUPS = 2

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
    except CredentialRequired:
        raise
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


class SplitsUnreadable(RuntimeError):
    """A ``splits`` binding did not return a mapping of split → group ids.

    Carries the reason AND the evidence, because both were already part of R3's
    verdict and a refusal that loses its evidence on the way through a helper
    is a weaker refusal than the one it replaced.
    """

    def __init__(self, reason: str, evidence: dict[str, Any] | None = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.evidence: dict[str, Any] = dict(evidence or {})


def normalise_splits(raw: Any) -> dict[str, set[str]]:
    """``{split: {group id, …}}`` from a ``splits`` binding's return value.

    Extracted from R3 so that D6 — which ties a repo's declared resampling
    blocks to the same binding — reads it through the SAME parser. Two readings
    of "what the splits binding said" is the rule-7 failure mode inside one
    package: the character-splitting defect below would have to be found and
    fixed twice, and the second copy is the one nobody remembers to fix.

    A str (or bytes) is iterable, so ``set(map(str, v))`` accepts one and
    silently splits it into CHARACTERS. That is not a type quibble: a binding
    returning ``{"train": "abc", "val": "de", "test": "fg"}`` was reported PASS
    with ``n_train=3, n_val=2, n_test=2`` -- the letters of 'abc' counted as
    three sites, disjoint, above the holdout floor, and indistinguishable in
    the table from a real blocked split. It fails loudly on long strings, which
    share characters, and silently on short ones, so the defect appears only
    where it does damage. Refused explicitly rather than coerced: mlkit does
    not get to decide that one string means one group.
    """
    mapping = dict(raw)
    stringy = {
        str(k): type(v).__name__
        for k, v in mapping.items()
        if isinstance(v, str | bytes)
    }
    if stringy:
        raise SplitsUnreadable(
            "splits must map each split to a collection of group ids, but "
            + ", ".join(f"{k} is a {t}" for k, t in sorted(stringy.items()))
            + "; a string would be iterated by character and counted as one "
            "group per letter",
            {"non_collection_splits": stringy},
        )
    return {str(k): set(map(str, v)) for k, v in mapping.items()}


@check("R3", PHASE, "BLOCKED_SPLITS — train/val/test share no group")
def r3_blocked_splits(repo: Repo, ctx: RunContext) -> CheckResult:
    try:
        fn = repo.resolve("splits")
    except BindingError as exc:
        return CheckResult.na("R3", PHASE, str(exc))
    try:
        splits = normalise_splits(fn())
    except SplitsUnreadable as exc:
        return CheckResult.failed("R3", PHASE, exc.reason, exc.evidence)
    except CredentialRequired:
        raise
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

    # Disjointness alone is not a blocked split. A holdout containing ONE group
    # is trivially disjoint and measures nothing: it cannot separate "this model
    # generalises across sites" from "the single held-out site happens to be
    # easy". Without this, the cheapest way to turn an R3 FAIL into a PASS is to
    # shrink the holdout until only one group remains -- which is holdout
    # narrowing, the thing CLAUDE.md rule 6 forbids, arriving as a green check.
    thin = {s: len(splits[s]) for s in ("val", "test") if len(splits[s]) < MIN_HOLDOUT_GROUPS}
    if thin:
        return CheckResult.failed(
            "R3", PHASE,
            "holdout too thin to be a blocked split: "
            + ", ".join(f"{k} has {v} group(s), need >= {MIN_HOLDOUT_GROUPS}" for k, v in thin.items())
            + "; a single-group holdout is disjoint but uninformative",
            {**evidence, "min_holdout_groups": MIN_HOLDOUT_GROUPS},
        )
    return CheckResult.passed("R3", PHASE, evidence)


@check("R4", PHASE, "METRIC_KNOWN_ANSWER — metrics reproduce analytic values")
def r4_metric_known_answer(repo: Repo, ctx: RunContext) -> CheckResult:
    try:
        fn = repo.resolve("metric_known_answer")
    except BindingError as exc:
        return CheckResult.na("R4", PHASE, str(exc))
    try:
        cases = list(fn())
    except CredentialRequired:
        raise
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
        # A metric that came back NaN reproduces nothing, but every comparison
        # a NaN takes part in is False, so `abs(got - want) > tol` was False and
        # the case passed. Same defect class as the D2/E1 hard stops.
        if not math.isfinite(got) or not math.isfinite(want):
            failures.append(
                f"{name}: 'computed'/'expected' are not finite (got {got}, expected {want})"
            )
            continue
        # The binding may be stricter than mlkit but never looser. A subject
        # that supplies its own tolerance can pass any check by widening it,
        # which is loosening a threshold with extra steps.
        declared_tol = float(case.get("tol", MAX_METRIC_TOL))
        # `min(nan, x)` is nan, so a NaN tolerance defeats the clamp entirely
        # and accepts any disagreement at all. Refused before it is clamped.
        if not math.isfinite(declared_tol):
            failures.append(f"{name}: declared tol is not finite ({declared_tol})")
            continue
        tol = min(declared_tol, MAX_METRIC_TOL)
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
    except CredentialRequired:
        raise
    except Exception as exc:  # noqa: BLE001
        return CheckResult.failed("R5", PHASE, f"provenance raised {type(exc).__name__}: {exc}")

    missing = [s for s in ("train", "val", "test") if s not in prov]
    if missing:
        return CheckResult.failed("R5", PHASE, "provenance missing splits: " + ", ".join(missing))

    # A histogram of ROW COUNTS, or the invariant below is arithmetic about
    # nothing. Two ways that went wrong, both silent, both measured:
    #
    #   {"real": 1.5, "synthetic": 0.5} -- a repo reporting PROPORTIONS. int()
    #   truncates, so int(0.5) == 0 cleared the taint test and int(1.5) == 1
    #   satisfied "at least one real row": a val split one third simulated,
    #   reported PASS.
    #
    #   {"real": 100, "synthetic": -5} -- a counter that had gone negative.
    #   -5 > 0 is False, so a broken count read as a clean holdout.
    #
    # Both are refused here rather than coerced, because the correct reading of
    # a count mlkit does not understand is "unknown", and an unknown count in
    # an evaluation split cannot clear the one invariant that is absolute.
    counts: dict[str, dict[str, int]] = {}
    malformed: list[str] = []
    for split in ("train", "val", "test"):
        counts[split] = {}
        for kind, raw in prov[split].items():
            try:
                n = float(raw)
            except (TypeError, ValueError):
                malformed.append(f"{split}.{kind}={raw!r} is not a number")
                continue
            # `float()` accepts NaN and the infinities, including as the
            # strings "nan"/"inf", and `int()` then raises out of the check --
            # ValueError for a NaN, OverflowError for an infinity. That is the
            # same defect this guard exists to close, one step further out:
            # the check stops naming the split and the kind and names an
            # interpreter error instead. NaN in particular is what a pandas or
            # numpy count becomes when a groupby or a reindex misses a kind.
            if not math.isfinite(n):
                malformed.append(f"{split}.{kind}={raw!r} is not a finite row count")
                continue
            if n != int(n) or n < 0:
                malformed.append(
                    f"{split}.{kind}={raw!r} is not a whole non-negative row count"
                )
                continue
            counts[split][str(kind)] = int(n)
    if malformed:
        return CheckResult.failed(
            "R5", PHASE,
            "provenance must report whole row counts per kind, and "
            + "; ".join(malformed[:4])
            + "; a count mlkit cannot read is an unknown, and an unknown cannot "
            "clear the val/test invariant",
            {"malformed": malformed},
        )

    # The invariant is absolute: not a single simulated row in val or test.
    tainted: dict[str, dict[str, int]] = {}
    for split in ("val", "test"):
        bad = {kind: n for kind, n in counts[split].items() if kind != "real" and n > 0}
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
    if counts["val"].get("real", 0) == 0 or counts["test"].get("real", 0) == 0:
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
    except CredentialRequired:
        raise
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


#: Most findings printed into a FAIL reason. The rest live in the evidence and
#: in the written report; a reason that runs to fifty lines sets the column
#: width for the whole portfolio table and gets skimmed instead of read.
R10_REASON_FINDINGS = 4

#: Where R10 writes the full finding list, relative to the repo root.
R10_REPORT_RELPATH = "reports/fabricated_defaults.md"


@check("R10", PHASE, "FABRICATED_DEFAULTS — no measured quantity takes a plausible default")
def r10_fabricated_defaults(repo: Repo, ctx: RunContext) -> CheckResult:
    """Walk the declared source tree for fabricated defaults.

    The defect: a measured quantity is given a plausible numeric default when
    its real input is absent, and that default then satisfies the gate that
    consumes it. The gate reports PASS having measured nothing.

    This check imports nothing from the repo. It parses, which means it works
    on code no binding exposes -- including the trainer's feature path, where
    every defect of this class found in August 2026 was living precisely
    because R3 and R5 only ever see the label panel.

    NA, not PASS, when the repo declares no source tree. A check that walks
    nothing and reports green is the same defect it was written to catch.

    E-038: the set of names this walk treats as measurements is DERIVED from
    the adopter -- :func:`metric_registry.derive` reads the repo's own
    figure-producing callables out of the same declared trees -- and is no
    longer mlkit's word list alone. Three verdicts, structurally distinct:

    * a finding at a name mlkit's vocabulary knows -> FAIL, exactly as before;
    * a finding whose only measured name came from the adopter's registry ->
      NA quoting the name, because mlkit cannot read that name's polarity and
      so cannot say the literal is the value that passes the gate. Before
      E-038 this case was SILENCE, which is the one answer that is wrong;
    * a registry derivation that came back empty over a tree that has Python
      files -> NA. An empty registry is evidence the derivation did not run,
      not evidence of a repo without metrics, and falling back to the word
      list there is E-038 restored.
    """
    source = repo.config().get("source") or {}
    declared = [str(t).strip() for t in (source.get("trees") or []) if str(t).strip()]
    if not declared:
        return CheckResult.na(
            "R10", PHASE,
            "no [source] trees declared in .mlkit/repo.toml; there is nothing to walk, "
            "so the absence of fabricated defaults is unmeasured (add e.g. "
            'trees = ["src", "scripts"])',
        )

    roots: list[Path] = []
    absent: list[str] = []
    for tree in declared:
        candidate = repo.path / tree
        if candidate.is_dir():
            roots.append(candidate)
        else:
            absent.append(tree)
    if not roots:
        return CheckResult.na(
            "R10", PHASE,
            f"declared source tree(s) {', '.join(declared)} do not exist under {repo.path}",
        )

    registry = metric_registry.derive(roots, base=repo.path)
    findings = fabrication.scan_tree(roots, base=repo.path, registry=registry)
    files = sum(1 for _ in fabrication.iter_python_files(roots))

    unclassified = [
        f for f in findings if f.severity == fabrication.UNCLASSIFIED_NAME
    ]
    satisfying = [f for f in findings if f.severity == "SATISFIES_GATE"]
    publishing = [
        f for f in findings
        if f.severity not in ("SATISFIES_GATE", fabrication.UNCLASSIFIED_NAME)
    ]
    defects = satisfying + publishing

    report_path = repo.path / R10_REPORT_RELPATH
    _write_r10_report(report_path, repo, ctx, findings, files, declared, registry)

    evidence = {
        "trees": declared,
        "files_walked": files,
        "findings": len(findings),
        "satisfies_gate": len(satisfying),
        "publishes_unmeasured": len(publishing),
        "unclassified_name": len(unclassified),
        "report": str(report_path.relative_to(repo.path)),
        "top": [
            f.to_dict()
            for f in (satisfying or publishing or unclassified)[:R10_REASON_FINDINGS]
        ],
        "metric_registry": registry.to_dict(),
    }
    if absent:
        evidence["declared_but_absent"] = [str(a) for a in absent]

    if not files:
        return CheckResult.na(
            "R10", PHASE,
            f"declared tree(s) {', '.join(declared)} contain no Python source to walk",
            evidence,
        )

    if registry.refusal:
        return CheckResult.na("R10", PHASE, registry.refusal, evidence)

    if defects:
        head = (satisfying or publishing)[:R10_REASON_FINDINGS]
        detail = "; ".join(
            f"{f.path}:{f.line} {f.symbol}={f.literal} ({f.shape} → {f.sink})" for f in head
        )
        more = len(defects) - len(head)
        trailer = f"; +{more} more in {R10_REPORT_RELPATH}" if more > 0 else ""
        if unclassified:
            trailer += (
                f"; and {len(unclassified)} further site(s) at metric name(s) this "
                f"repo declares but mlkit cannot classify — see {R10_REPORT_RELPATH}"
            )
        return CheckResult.failed(
            "R10", PHASE,
            f"{len(defects)} fabricated default(s) reach a gate, metric or report "
            f"({len(satisfying)} of them satisfy the gate that consumes them): {detail}"
            + trailer,
            evidence,
        )

    if unclassified:
        head = unclassified[:R10_REASON_FINDINGS]
        detail = "; ".join(
            f"{f.path}:{f.line} {f.symbol}={f.literal} ({f.shape} → {f.sink})" for f in head
        )
        more = len(unclassified) - len(head)
        return CheckResult.na(
            "R10", PHASE,
            f"{len(unclassified)} plausible literal(s) stand at metric name(s) THIS REPO "
            f"declares by computing them, which mlkit's own vocabulary cannot classify, "
            f"so no polarity can be read and neither PASS nor FAIL is earned: {detail}"
            + (f"; +{more} more in {R10_REPORT_RELPATH}" if more > 0 else ""),
            evidence,
        )
    return CheckResult.passed("R10", PHASE, evidence)


def _write_r10_report(
    path: Path,
    repo: Repo,
    ctx: RunContext,
    findings: list[fabrication.Finding],
    files: int,
    trees: list[str],
    registry: metric_registry.MetricRegistry | None = None,
) -> None:
    """Write every finding out, because a truncated reason is not evidence."""
    registry = registry or metric_registry.MetricRegistry()
    lines = [
        f"# Fabricated defaults (R10) — resilient-{repo.name}",
        "",
        f"- run nonce: `{ctx.nonce}`",
        f"- git SHA: `{repo.git_sha}`",
        f"- trees walked: {', '.join(f'`{t}`' for t in trees)} ({files} file(s))",
        f"- findings: {len(findings)}",
        "",
        "`SATISFIES_GATE` marks a default that is the value which would PASS the",
        "gate consuming it. `PUBLISHES_UNMEASURED` marks one that would fail its",
        "gate but is still emitted as though it were a measurement.",
        "`UNCLASSIFIED_NAME` marks neither: the symbol is a metric name THIS REPO",
        "declares by computing it, mlkit's own vocabulary has no opinion on it, so",
        "no polarity can be read and no verdict is asserted. R10 renders NA.",
        "",
        "| severity | file:line | symbol | value | shape | sink |",
        "|---|---|---|---|---|---|",
    ]
    for f in findings:
        lines.append(
            f"| {f.severity} | `{f.path}:{f.line}` | `{f.symbol}` | `{f.literal}` | "
            f"{f.shape} | {f.sink} |"
        )
    if not findings:
        lines.append("| — | — | — | — | — | (none) |")
    lines.append("")
    # The derivation is disclosed in full, because a name universe nobody can
    # read is the same problem as a name universe nobody can extend (E-038).
    lines += [
        "## The metric-name universe this run checked",
        "",
        "Derived from this repo's OWN figure-producing callables in the trees above,",
        "not from a word list inside mlkit. See `core/metric_registry.py`.",
        "",
        f"- names derived: {len(registry.names)}",
        (
            f"- of those, already in mlkit's vocabulary (the anchor): "
            f"{len(registry.known)} — {', '.join(sorted(registry.known)) or '(none)'}"
        ),
        f"- of those, unclassifiable by mlkit: {len(registry.unclassified)}",
        f"- derivation refusal: {registry.refusal or '(none)'}",
        "",
    ]
    if registry.unclassified:
        lines += ["| derived name mlkit cannot classify | declared at |", "|---|---|"]
        for key in sorted(registry.unclassified):
            lines.append(f"| `{key}` | {registry.origins.get(key, '—')} |")
        lines.append("")
    # Unguarded on purpose: this report is produced by parsing source, not by
    # importing the repo, so it is measured correctly from any interpreter.
    # See core/report.py, "WHAT IS NOT GUARDED, AND WHY".
    report.guarded_write(
        path, "\n".join(lines), probe=None, depends_on_bindings=False,
        nonce=ctx.nonce, git_sha=repo.git_sha,
    )


#: Where R11 writes the full finding list, relative to the repo root.
R11_REPORT_RELPATH = "reports/fabricated_targets.md"

#: Most findings printed into a FAIL reason; the rest live in the report.
R11_REASON_FINDINGS = 3


@check("R11", PHASE, "FABRICATED_TARGETS — no RNG-derived row stamped as observed")
def r11_fabricated_targets(repo: Repo, ctx: RunContext) -> CheckResult:
    """Walk every Python file in the repo for fabricated targets.

    The defect: a value is drawn from a random number generator, flows into
    the numbers written onto a data record, and that record is stamped with a
    provenance field its own construction contradicts. The stamp is the
    defect -- the same code stamped ``synthetic`` is a fixture -- and it
    compounds, because R5 counts rows BY that field and will count these as
    real.

    Three ways a stamp can be false, and the check must answer all three or it
    is defeated by naming. A value that CLAIMS observation. A value, or a
    record, that claims observation and declares simulation at once -- which
    used to be an exemption and was therefore the cheapest evasion available.
    And a source label naming an external dataset on a record whose every
    value was manufactured in this process, which is the shape that let a
    loader drawing all eight of its fields from ``self.rng`` sit behind
    ``source="era5_land"`` and report zero findings.

    Deliberately NOT scoped to ``[source] trees``. R10 is, and that is right
    for R10; here the declared-tree list is precisely the surface an author
    controls, and the incident this check exists for (resilient-choco PR #160,
    five files under ``scripts/``) lived entirely outside it. There is
    therefore no NA path for an undeclared tree: every repo has Python files,
    so every repo is measurable here.
    """
    registry = fabricated_targets.load_source_registry(repo.path)
    findings = fabricated_targets.scan_repo(repo.path, registry)
    files = fabricated_targets.count_python_files([repo.path])

    by_rule: dict[str, int] = {}
    for f in findings:
        by_rule[f.rule] = by_rule.get(f.rule, 0) + 1
    # The NA lane. An UNREADABLE_STAMP finding is not a fabrication and not a
    # clean record: it is a record this instrument could not adjudicate. It
    # must not be counted as a defect and it must not be counted as a pass.
    scanned = findings
    unreadable = [
        f for f in scanned if f.severity == fabricated_targets.UNREADABLE_STAMP
    ]
    findings = [
        f for f in scanned if f.severity != fabricated_targets.UNREADABLE_STAMP
    ]
    targets = [f for f in findings if f.severity == fabricated_targets.TARGET_FABRICATED]
    inputs = [f for f in findings if f.severity != fabricated_targets.TARGET_FABRICATED]
    in_holdout = [f for f in findings if f.split.lower() in {"val", "test", "valid", "validation"}]

    report_path = repo.path / R11_REPORT_RELPATH
    _write_r11_report(report_path, repo, ctx, scanned, files, registry)

    evidence = {
        "files_walked": files,
        # WHICH registry the value-side source rule adjudicated against, and
        # whether there was one at all. Reported rather than assumed: without
        # this, renaming docs/allowlist.yaml turns half of CONTRADICTED_SOURCE
        # off and R11 goes on printing PASS with nothing to say it lost a
        # conjunct. R9 and T5 ESCALATE on the same absence; this is the line
        # that makes it visible HERE, where it changes what was measured.
        "source_registry": {
            "path": registry.path,
            "present": registry.present,
            "entries": len(registry.entries),
            "parse_error": registry.parse_error,
        },
        "findings": len(findings),
        "unreadable_stamp": len(unreadable),
        "target_fabricated": len(targets),
        "input_fabricated": len(inputs),
        "stamped_into_holdout": len(in_holdout),
        "by_rule": by_rule,
        "report": str(report_path.relative_to(repo.path)),
        "top": [f.to_dict() for f in (targets or inputs)[:R11_REASON_FINDINGS]],
    }

    if not files:
        # A repo with no Python source at all. Not a pass: a walk over nothing
        # that reports green is the defect this instrument exists to catch,
        # applied to the instrument.
        return CheckResult.na(
            "R11", PHASE,
            f"no Python files found under {repo.path}; the absence of fabricated "
            "targets is unmeasured, not established",
            evidence,
        )

    if findings:
        head = (targets or inputs)[:R11_REASON_FINDINGS]
        detail = "; ".join(
            f'{f.path}:{f.line} {f.field} <- {f.origin_call} stamped '
            f'{f.claim_field}="{f.claim_value}" [{f.rule}]'
            for f in head
        )
        more = len(findings) - len(head)
        holdout = (
            f"; {len(in_holdout)} of them declare a val/test split, which is R5's "
            "invariant broken at the source"
            if in_holdout else ""
        )
        return CheckResult.failed(
            "R11", PHASE,
            f"{len(findings)} record(s) built from an RNG draw carry a provenance "
            f"stamp their own construction contradicts ({len(targets)} of them "
            f"fabricate the target itself): {detail}{holdout}"
            + (f"; +{more} more in {R11_REPORT_RELPATH}" if more > 0 else ""),
            evidence,
        )
    if unreadable:
        detail = "; ".join(
            f'{f.path}:{f.line} {f.field} <- {f.origin_call} declares '
            f'{f.claim_field}={f.claim_value}'
            for f in unreadable[:R11_REASON_FINDINGS]
        )
        more = len(unreadable) - min(len(unreadable), R11_REASON_FINDINGS)
        return CheckResult.na(
            "R11", PHASE,
            f"{len(unreadable)} wholly-manufactured record(s) with a drawn target "
            "declare a provenance value this check cannot resolve to a string, so "
            "their provenance is UNADJUDICATED rather than clean: " + detail
            + (f"; +{more} more in {R11_REPORT_RELPATH}" if more > 0 else ""),
            evidence,
        )
    return CheckResult.passed("R11", PHASE, evidence)


def _write_r11_report(
    path: Path,
    repo: Repo,
    ctx: RunContext,
    findings: list[fabricated_targets.Finding],
    files: int,
    registry: fabricated_targets.SourceRegistry,
) -> None:
    """Write every finding out, because a truncated reason is not evidence."""
    lines = [
        f"# Fabricated targets (R11) — resilient-{repo.name}",
        "",
        f"- run nonce: `{ctx.nonce}`",
        f"- git SHA: `{repo.git_sha}`",
        (f"- files walked: {files} (every `.py` in the repo, excluding vendored "
         "directories and `tests/`)"),
        # Broken out, because the two numbers mean different things and a
        # single total would let an NA row be read as a defect (or a defect
        # be diluted by NA rows). These match the check's own `findings` and
        # `unreadable_stamp` evidence keys exactly.
        (f"- findings: {sum(1 for f in findings if f.severity != fabricated_targets.UNREADABLE_STAMP)}"
         f" (defects) + {sum(1 for f in findings if f.severity == fabricated_targets.UNREADABLE_STAMP)}"
         " unadjudicated (`UNREADABLE_STAMP`, see below — these do not fail"
         " this check, they take it to NA)"),
        (f"- real-source registry: `{registry.path}` — "
         + (f"{len(registry.entries)} signed entries"
            if registry.present else "ABSENT")
         + (f" (parse error: {registry.parse_error})" if registry.parse_error else "")
         + ". The value-side half of `CONTRADICTED_SOURCE` adjudicates against"
           " it, so an absent registry means that half measured nothing here."),
        "",
        "Each row is a record whose numbers can be traced back to a random draw and",
        "whose provenance stamp does not say so. The `claim` column is the specific",
        "field that makes it a fabrication rather than an honestly-labelled",
        "simulation.",
        "",
        "The `rule` column says WHY the stamp is false, and the answers are",
        "not interchangeable:",
        "",
        "- `OBSERVED_STAMP` — the value claims observation outright (`\"observed_ccc\"`).",
        "- `CONTRADICTED_STAMP` — the same value, or the same record, both claims",
        "  observation and declares simulation. R5 counts by ONE field, so a second",
        "  field saying `synthetic` does not make the first one true.",
        "- `CONTRADICTED_SOURCE` — the stamp names an external dataset, and every",
        "  value on the record was manufactured inside this process: RNG draws,",
        "  literals, and arithmetic over a loop index. Nothing on the record came",
        "  from the named source because nothing on it came from anywhere. The",
        "  stamp is recognised either by its FIELD NAME (a declared provenance",
        "  field) or, whatever it is called, by its VALUE — see `matched on`.",
        "",
        "`matched on` says what made a value a source claim when its field name did",
        "not: `allowlist:<entry>` means the value reproduces two or more parts of a",
        "product this repo's own signed `docs/allowlist.yaml` records as real;",
        "`observed-token:<token>` means the value claims observation outright. Blank",
        "means the field name was itself a declared provenance field.",
        "",
        "`TARGET_FABRICATED` marks a draw reaching the field a model is trained to",
        "predict. `INPUT_FABRICATED` marks one reaching another data field of the",
        "same stamped record.",
        "",
        "`UNREADABLE_STAMP` is NOT a defect row and does not fail this check. It",
        "marks a record that is wholly manufactured with a drawn TARGET, whose only",
        "source-naming field holds an expression this check cannot resolve to a",
        "string (`source=f\"era5_{region}\"`, `source=FEEDS[which]`). Its provenance",
        "is UNADJUDICATED, not clean — so R11 reports NA rather than PASS, and the",
        "`claim` column quotes the expression verbatim. Resolving the value, or",
        "declaring the record's provenance beside it, returns this check to a",
        "verdict. A repo with only these rows has not failed; it has not been",
        "measured.",
        "",
        "| rule | severity | record | field | drawn at | claim | matched on | split | drawn fields | corroborating |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for f in findings:
        corroborating = ", ".join(f"`{c}`" for c in f.corroborating) or "—"
        lines.append(
            f"| {f.rule} | {f.severity} | `{f.path}:{f.line}` | `{f.field}` | "
            f"`{f.origin_symbol}` = `{f.origin_call}` (line {f.origin_line}) | "
            f'`{f.claim_field}="{f.claim_value}"` | '
            f'{f"`{f.matched_on}`" if f.matched_on else "field name"} | '
            f'{f.split or "—"} | '
            f"{f.tainted_fields}/{f.data_fields} | {corroborating} |"
        )
    if not findings:
        lines.append("| — | — | — | — | — | — | — | — | — | (none) |")
    lines.append("")
    # Unguarded: static analysis, no repo imports. See core/report.py.
    report.guarded_write(
        path, "\n".join(lines), probe=None, depends_on_bindings=False,
        nonce=ctx.nonce, git_sha=repo.git_sha,
    )


#: Where R12 writes the full finding list, relative to the repo root.
R12_REPORT_RELPATH = "reports/served_contract.md"

#: Most findings printed into a FAIL reason; the rest live in the report.
R12_REASON_FINDINGS = 3


@check("R12", PHASE, "SERVED_CONTRACT — no local re-implementation of the served model")
def r12_served_contract(repo: Repo, ctx: RunContext) -> CheckResult:
    """Walk every Python file for a served-model contract implemented locally.

    R11's question one layer up. Rule 7 says eight local copies of a gate is
    eight different definitions of "ready", which is the same as none; measured
    2026-08-29 the fleet had one definition of "ready" and THREE of "served",
    including two files with the same name and different SHAs. R12 asks whether
    a file decides what is served — is this the artifact that was measured, may
    this challenger be promoted, which arm may be scored — without routing
    through ``core.served``.

    Scoped like R11 rather than like R10: every Python file in the repo, not
    the trees ``[source] trees`` declares. Serving code lives under
    ``scripts/`` and ``benchmarks/`` in three of the repos it is aimed at, and
    a check that trusts the declared-tree list cannot see a definition that
    lives outside it.

    The exemption is a USE, not a name and not an import. A file that binds a
    name from the contract — directly, or through one module in the same repo
    that does — AND references that name is silent whatever shapes it carries,
    so adopting the contract is what clears this check, and a repo that wants a
    thin typed wrapper over ``ServedModel`` may keep one.

    That it is a use rather than an import is the E-035 repair. The exemption
    used to be the import statement alone, and resilient-fray measured what
    that bought: one unused ``from resilient_mlkit.core.served import ...``
    line took ``src/registry/promotion_gate.py`` from 4 findings to 0 without
    changing a decision it makes. See
    ``core/served_reimplementation.py``'s "THE EXEMPTION" section.
    """
    findings, files = served_reimplementation.scan_repo(repo.path)

    reimplemented = [
        f for f in findings
        if f.severity == served_reimplementation.REIMPLEMENTED
    ]
    adjacent = [f for f in findings if f not in reimplemented]
    touched: list[str] = []
    for f in findings:
        if f.path not in touched:
            touched.append(f.path)

    report_path = repo.path / R12_REPORT_RELPATH
    _write_r12_report(report_path, repo, ctx, findings, files)

    evidence = {
        "files_walked": files,
        "findings": len(findings),
        "contract_reimplemented": len(reimplemented),
        "serving_adjacent": len(adjacent),
        "files_named": touched,
        "contract_module": served_reimplementation.CONTRACT_MODULE,
        "report": str(report_path.relative_to(repo.path)),
        "top": [f.to_dict() for f in (reimplemented or adjacent)[:R12_REASON_FINDINGS]],
    }

    if not files:
        # Same reasoning as R11: a walk over nothing that reports green is the
        # defect this instrument exists to catch, applied to the instrument.
        return CheckResult.na(
            "R12", PHASE,
            f"no Python files found under {repo.path}; the absence of a locally "
            "re-implemented served contract is unmeasured, not established",
            evidence,
        )

    if findings:
        head = (reimplemented or adjacent)[:R12_REASON_FINDINGS]
        detail = "; ".join(f"{f.path}:{f.line} {f.clause} {f.symbol}" for f in head)
        more = len(findings) - len(head)
        return CheckResult.failed(
            "R12", PHASE,
            f"{len(findings)} local implementation(s) of the served-model contract "
            f"across {len(touched)} file(s) ({len(reimplemented)} decide a contract "
            f"clause rather than merely shaping one), none using "
            f"{served_reimplementation.CONTRACT_MODULE}: {detail}"
            + (f"; +{more} more in {R12_REPORT_RELPATH}" if more > 0 else ""),
            evidence,
        )
    return CheckResult.passed("R12", PHASE, evidence)


def _write_r12_report(
    path: Path,
    repo: Repo,
    ctx: RunContext,
    findings: list[served_reimplementation.Finding],
    files: int,
) -> None:
    """Write every finding out, because a truncated reason is not evidence."""
    lines = [
        f"# Served-model contract (R12) — resilient-{repo.name}",
        "",
        f"- run nonce: `{ctx.nonce}`",
        f"- git SHA: `{repo.git_sha}`",
        (f"- files walked: {files} (every `.py` in the repo, excluding vendored "
         "directories and `tests/`)"),
        f"- contract: `{served_reimplementation.CONTRACT_MODULE}`",
        f"- findings: {len(findings)}",
        "",
        "Each row is a place where this repo answers, in its own code, a question",
        "the served-model contract exists to answer once: is this the artifact that",
        "was measured, is this the data it was measured on, may this challenger be",
        "promoted, and which arm may be served.",
        "",
        "`CONTRACT_REIMPLEMENTED` marks a clause the file DECIDES. `SERVING_ADJACENT`",
        "marks a serving type defined locally without the contract behind it — the",
        "shape of a second definition rather than a decision it makes.",
        "",
        "A file that USES a name it took from the contract — directly, or through",
        "one module in this repo that imports it — produces no row here whatever",
        "shapes it carries. An import nobody references exempts nothing (E-035).",
        "Adoption is what clears this check; renaming is not, and neither is a",
        "dead import line.",
        "",
        "| severity | clause | file | symbol | why it matters |",
        "|---|---|---|---|---|",
    ]
    for f in findings:
        detail = f.detail.replace("|", "\\|")
        lines.append(
            f"| {f.severity} | {f.clause} | `{f.path}:{f.line}` | `{f.symbol}` | {detail} |"
        )
    if not findings:
        lines.append("| — | — | — | — | (none) |")
    lines.append("")
    # Unguarded: static analysis, no repo imports. See core/report.py.
    report.guarded_write(
        path, "\n".join(lines), probe=None, depends_on_bindings=False,
        nonce=ctx.nonce, git_sha=repo.git_sha,
    )


@check("R8", PHASE, "REPORT — readiness report generated from measured results")
def r8_report(repo: Repo, ctx: RunContext) -> CheckResult:
    prior = {k: v for k, v in ctx.prior.items() if k.startswith("R") and k != "R8"}
    if not prior:
        return CheckResult.na("R8", PHASE, "no R-check results in this run to report on")

    # Ask, before composing anything, whether this interpreter could have
    # measured any of it. A numpy-less python3.14 regenerated this exact file
    # in at least four repos in August 2026, replacing measured PASSes with
    # ModuleNotFoundError (resilient-chokepoint docs/ESCALATIONS.md E-019).
    # Every one of those results was individually honest -- the check really
    # did fail to run -- and the aggregate was still a lie, because the
    # composite reads as a statement about the repo when it is a statement
    # about the shell.
    #
    # assess(), not probe(): the import probe alone misses a lazily-importing
    # binding, which imports cleanly from a broken interpreter and fails only
    # when called. Measured 2026-08-28 from a numpy-less python 3.14.6,
    # resilient-surge reported MEASURABLE on 11 of 11 bindings from an
    # interpreter that cannot run any of them. The results this run already
    # produced are the stronger evidence, and they cost nothing extra.
    probe = environment.assess(repo, prior)

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
    written = report.guarded_write(
        out, "\n".join(lines),
        probe=probe, depends_on_bindings=True,
        nonce=ctx.nonce, git_sha=repo.git_sha,
    )

    counts: dict[str, int] = {}
    for r in prior.values():
        counts[r.status.value] = counts.get(r.status.value, 0) + 1

    evidence = {
        "path": str(out.relative_to(repo.path)),
        "counts": counts,
        "environment": probe.to_dict(),
        "write": written.to_dict(),
    }

    if not written.written:
        # NA, never FAIL. "This environment cannot measure this repo" is not a
        # verdict on the repo, and recording it as one would put a red mark on
        # eight repos every time somebody ran mlkit from the wrong shell --
        # which is how a gate stops being read.
        return CheckResult.na("R8", PHASE, written.reason, evidence)

    return CheckResult.passed("R8", PHASE, evidence)


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
