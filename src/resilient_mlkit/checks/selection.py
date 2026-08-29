"""Phase 2 — SELECTION.

The register lives in ``docs/selection.yaml`` (machine-readable) while
``docs/SELECTION.md`` documents the protocol for humans. Splitting them is
deliberate: parsing prose for structured determinations is how a gate ends up
passing on a well-formatted paragraph that says nothing.

The tier rule is the one worth defending hardest: no Tier-2 foundation model
enters a training config until it has beaten a Tier-1 domain-specific baseline
on this repo's own spatially blocked holdout. A register without a Tier-1
baseline is incomplete however strong its Tier-2 entries look.
"""

from __future__ import annotations

import urllib.error
import urllib.request
from typing import Any

from ..core import artifact
from ..core.repo import Repo
from ..core.result import ALLOW_DIRTY_KEY, CheckResult
from . import RunContext, check

PHASE = "selection"

SELECTION_RELPATH = "docs/selection.yaml"

#: Fields a task spec must pin down before candidates mean anything.
REQUIRED_TASK_SPEC = (
    "objective",
    "unit_of_analysis",
    "label_definition",
    "holdout",
    "primary_metric",
    "decision_threshold",
)

#: Per-source fields S4 requires. Each exists because omitting it has cost
#: somebody a training run at some point.
REQUIRED_SOURCE_FIELDS = (
    "uri",
    "licence_url",
    "retrieval_date",
    "verdict",
    "coverage_vs_aoi",
    "native_resolution",
    "revisit",
    "latency",
    "gb",
    "us_west_2",
    "staging_cost",
)


def _load(repo: Repo, ctx: RunContext) -> tuple[dict[str, Any] | None, str, bool]:
    """The register, READ FROM COMMITTED STATE. Returns (data, error, marked).

    This used to be ``(repo.path / SELECTION_RELPATH).read_text()``: S1-S4
    parsed the working tree and emitted PASS from it, with no committed-read
    discipline of any kind. That is precisely the shape ``docs/ESCALATIONS.md``
    E-M12 records -- a verdict quoting bytes that are in nobody's git history,
    so the reader it is quoted to cannot fetch what it passed on -- and
    ``core.artifact`` exists to prevent it. The check pipeline simply never
    used it: nothing under ``checks/`` imported the module, which is why
    ``CheckResult.__post_init__``'s marked-PASS refusal and
    ``portfolio.resolve()``'s had no producer and could not fire.

    The third element is that producer. It is True when the register was read
    through the ``--allow-dirty`` escape hatch, and every result built from it
    must carry it into ``evidence`` under ``ALLOW_DIRTY_KEY`` -- see
    :func:`_evidence`. Without the flag an uncommitted register is an NA naming
    the file, which is the ``core.artifact`` contract and not a new judgement.
    """
    ref = artifact.load(repo, SELECTION_RELPATH, allow_dirty=ctx.allow_dirty)
    marked = ref.allow_dirty_read
    if ref.error:
        # The reader's diagnosis is kept verbatim, and the two cases a reader of
        # this phase acts on differently are named in this phase's own words in
        # front of it. "Nobody has written a register" and "the register does
        # not parse" send an operator to different places, and a reason that
        # made them read alike would cost that.
        if ref.path is None:
            return None, f"{SELECTION_RELPATH} does not exist — {ref.error}", marked
        if ref.document is None and _is_parse_failure(ref.error):
            return (
                None,
                f"{SELECTION_RELPATH} is malformed YAML: {ref.error}",
                marked,
            )
        return None, ref.error, marked
    data = ref.document
    if data is None:
        data = {}
    if not isinstance(data, dict):
        return None, f"{SELECTION_RELPATH} top level is not a mapping", marked
    return data, "", marked


#: ``core.artifact`` reports a parse failure as ``"<ExceptionType>: <message>"``
#: and a committed-read refusal with its own NOT_COMMITTED prefix. Distinguishing
#: them on the PyYAML exception names is narrower than matching on the absence of
#: the prefix: a reason this phase relabels as "malformed YAML" must actually be
#: a YAML parse failure, not the next error class the reader learns to report.
_YAML_ERRORS = ("ParserError", "ScannerError", "ComposerError", "ConstructorError",
                "ReaderError", "YAMLError", "UnicodeDecodeError")


def _is_parse_failure(error: str) -> bool:
    return error.split(":", 1)[0].strip() in _YAML_ERRORS


def _evidence(evidence: dict[str, Any], marked: bool) -> dict[str, Any]:
    """Carry the allow-dirty marker into a result's evidence.

    One function rather than a line at each call site, because the marker's
    whole value is that it cannot be dropped on one path out of four. A PASS
    carrying it is refused by ``CheckResult.__post_init__``; a FAIL or NA
    carrying it renders, is stored, and is refused by ``portfolio.resolve()``
    when a terminal state is asked for. Neither refusal is reachable if this
    function is not called.
    """
    if marked:
        evidence = {**evidence, ALLOW_DIRTY_KEY: True}
    return evidence


@check("S1", PHASE, "TASK_SPEC — the task is pinned down before candidates are compared")
def s1_task_spec(repo: Repo, ctx: RunContext) -> CheckResult:
    data, err, marked = _load(repo, ctx)
    if err:
        return CheckResult.na("S1", PHASE, err, _evidence({}, marked))
    assert data is not None

    spec = data.get("task_spec") or {}
    if not isinstance(spec, dict) or not spec:
        return CheckResult.failed(
            "S1", PHASE, "task_spec is absent or empty", _evidence({}, marked)
        )

    missing = [f for f in REQUIRED_TASK_SPEC if not str(spec.get(f) or "").strip()]
    if missing:
        return CheckResult.failed(
            "S1", PHASE, "task_spec missing: " + ", ".join(missing),
            _evidence({"present": sorted(k for k in spec if spec.get(k))}, marked),
        )
    return CheckResult.passed(
        "S1", PHASE, _evidence({"fields": len(REQUIRED_TASK_SPEC)}, marked)
    )


@check("S2", PHASE, "CANDIDATE_REGISTER — three mandatory tiers, each licence-identified")
def s2_candidate_register(repo: Repo, ctx: RunContext) -> CheckResult:
    data, err, marked = _load(repo, ctx)
    if err:
        return CheckResult.na("S2", PHASE, err, _evidence({}, marked))
    assert data is not None

    candidates = data.get("candidates") or []
    if not candidates:
        return CheckResult.failed(
            "S2", PHASE, "candidate register is empty", _evidence({}, marked)
        )

    tiers: dict[int, list[str]] = {}
    unlicensed: list[str] = []
    for cand in candidates:
        if not isinstance(cand, dict):
            continue
        cid = str(cand.get("id", "<unnamed>"))
        try:
            tier = int(cand.get("tier", -1))
        except (TypeError, ValueError):
            tier = -1
        tiers.setdefault(tier, []).append(cid)
        if not str(cand.get("licence_url") or "").startswith(("http://", "https://")):
            unlicensed.append(cid)

    evidence = _evidence(
        {
            "n_candidates": len(candidates),
            "tier_0": len(tiers.get(0, [])),
            "tier_1": len(tiers.get(1, [])),
            "tier_2": len(tiers.get(2, [])),
        },
        marked,
    )

    shortfalls = []
    if evidence["tier_0"] < 1:
        shortfalls.append("no Tier-0 (trivial/heuristic) entry")
    if evidence["tier_1"] < 1:
        shortfalls.append("no Tier-1 domain-specific baseline")
    if evidence["tier_2"] < 2:
        shortfalls.append(f"only {evidence['tier_2']} Tier-2 entries, need 2")
    if shortfalls:
        return CheckResult.failed(
            "S2", PHASE, "register incomplete: " + "; ".join(shortfalls), evidence
        )
    if unlicensed:
        return CheckResult.failed(
            "S2",
            PHASE,
            f"{len(unlicensed)} candidate(s) without a licence URL: "
            + ", ".join(sorted(unlicensed)[:5]),
            evidence,
        )
    return CheckResult.passed("S2", PHASE, evidence)


@check("S3", PHASE, "EVIDENCE_RESOLVABLE — every cited URL actually resolves")
def s3_evidence_resolvable(repo: Repo, ctx: RunContext) -> CheckResult:
    data, err, marked = _load(repo, ctx)
    if err:
        return CheckResult.na("S3", PHASE, err, _evidence({}, marked))
    assert data is not None
    if ctx.offline:
        return CheckResult.na(
            "S3", PHASE, "no network available; URL resolution cannot be measured",
            _evidence({}, marked),
        )

    urls: list[str] = []
    for cand in data.get("candidates") or []:
        if not isinstance(cand, dict):
            continue
        if url := str(cand.get("licence_url") or ""):
            urls.append(url)
        for ev in cand.get("evidence") or []:
            urls.append(str(ev))
    for src in data.get("sources") or []:
        if isinstance(src, dict) and (url := str(src.get("licence_url") or "")):
            urls.append(url)

    urls = sorted({u for u in urls if u.startswith(("http://", "https://"))})
    if not urls:
        return CheckResult.na(
            "S3", PHASE, "no citable URLs in the register", _evidence({}, marked)
        )

    unresolved: dict[str, str] = {}
    for url in urls:
        code, detail = _probe(url, ctx.timeout)
        if code != 200:
            unresolved[url] = detail

    evidence = _evidence(
        {"total": len(urls), "resolved": len(urls) - len(unresolved)}, marked
    )
    if unresolved:
        return CheckResult.failed(
            "S3",
            PHASE,
            f"{len(unresolved)}/{len(urls)} URL(s) did not return 200: "
            + "; ".join(f"{u} -> {d}" for u, d in list(unresolved.items())[:4]),
            {**evidence, "unresolved": unresolved},
        )
    return CheckResult.passed("S3", PHASE, evidence)


@check("S4", PHASE, "DATA_AND_LICENCE — every source fully characterised and verdicted")
def s4_data_and_licence(repo: Repo, ctx: RunContext) -> CheckResult:
    data, err, marked = _load(repo, ctx)
    if err:
        return CheckResult.na("S4", PHASE, err, _evidence({}, marked))
    assert data is not None

    sources = data.get("sources") or []
    if not sources:
        return CheckResult.failed(
            "S4", PHASE, "no sources characterised", _evidence({}, marked)
        )

    incomplete: dict[str, list[str]] = {}
    verdicts: dict[str, int] = {}
    for src in sources:
        if not isinstance(src, dict):
            continue
        sid = str(src.get("id", "<unnamed>"))
        missing = [
            f for f in REQUIRED_SOURCE_FIELDS
            if src.get(f) is None or str(src.get(f)).strip() == ""
        ]
        if missing:
            incomplete[sid] = missing
        verdict = str(src.get("verdict") or "UNSET")
        verdicts[verdict] = verdicts.get(verdict, 0) + 1

    evidence = _evidence({"n_sources": len(sources), "verdicts": verdicts}, marked)
    if incomplete:
        first = list(incomplete.items())[:3]
        return CheckResult.failed(
            "S4",
            PHASE,
            f"{len(incomplete)} source(s) incomplete: "
            + "; ".join(f"{k} missing {','.join(v)}" for k, v in first),
            {**evidence, "incomplete": incomplete},
        )
    if verdicts.get("UNSET"):
        return CheckResult.failed(
            "S4", PHASE, f"{verdicts['UNSET']} source(s) carry no licence verdict", evidence
        )
    return CheckResult.passed("S4", PHASE, evidence)


@check("S5", PHASE, "DECISION_RECORD — human sign-off", human_only=True)
def s5_decision_record(repo: Repo, ctx: RunContext) -> CheckResult:
    return CheckResult.escalated(
        "S5",
        PHASE,
        "S5 is a human decision record and is reserved to the signatory; "
        "the agent may not write it",
    )


# -- helpers --------------------------------------------------------------


def _probe(url: str, timeout: float) -> tuple[int, str]:
    """HEAD a URL, falling back to GET.

    Plenty of licence pages -- government ones especially -- answer 403 or 405
    to HEAD while serving GET perfectly well, so a HEAD-only probe would report
    false failures against exactly the sources that matter most here.
    """
    for method in ("HEAD", "GET"):
        req = urllib.request.Request(
            url,
            method=method,
            headers={"User-Agent": "resilient-mlkit/0.1 (+licence-gate)"},
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                if resp.status == 200:
                    return 200, "ok"
                last = f"HTTP {resp.status}"
        except urllib.error.HTTPError as exc:
            last = f"HTTP {exc.code}"
        except urllib.error.URLError as exc:
            last = f"{type(exc.reason).__name__}: {exc.reason}"
        except Exception as exc:  # noqa: BLE001
            last = f"{type(exc).__name__}: {exc}"
    return 0, last
