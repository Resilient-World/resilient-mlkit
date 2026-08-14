"""Terminal-state resolution and the portfolio table.

A repo is in exactly one of three terminal states, and the rules that pick it
are the whole point of this module:

* **BLOCKED** — something failed, or a hard stop fired. Needs a one-line reason
  in ``docs/BLOCKERS.md``.
* **AWAITING-SIGNOFF** — nothing failed, but at least one check is reserved to
  a human signatory or waits on one. Needs an open item in
  ``docs/ESCALATIONS.md``.
* **READY-TO-TRAIN** — all 25 checks pass.

Worth stating plainly, because it surprises people: READY-TO-TRAIN is not
reachable by the agent. S5, D1, D4, D5, E4 and E5 are reserved to the human
signatory and always report ESCALATED, so the best state the agent can drive a
repo to on its own is AWAITING-SIGNOFF. That is by design -- these are legal
and billing exposures, not code changes.
"""

from __future__ import annotations

from dataclasses import dataclass

from .checks import PHASE_ORDER, PHASES
from .core.repo import Repo
from .core.result import CheckResult, Status
from .core.table import compact

READY = "READY-TO-TRAIN"
BLOCKED = "BLOCKED"
AWAITING = "AWAITING-SIGNOFF"
IN_PROGRESS = "IN-PROGRESS"


@dataclass
class RepoState:
    repo: Repo
    results: dict[str, CheckResult]
    state: str
    reason: str

    @property
    def halted(self) -> bool:
        return any(r.evidence.get("halt") for r in self.results.values())


def resolve(repo: Repo, results: dict[str, CheckResult]) -> RepoState:
    """Decide a repo's terminal state from its measured results."""
    all_ids = [cid for phase in PHASES for cid in PHASE_ORDER[phase]]

    halts = [r for r in results.values() if r.evidence.get("halt")]
    if halts:
        h = halts[0]
        return RepoState(repo, results, BLOCKED, f"{h.check_id} hard stop: {h.reason}")

    fails = [results[c] for c in all_ids if c in results and results[c].status is Status.FAIL]
    if fails:
        return RepoState(
            repo, results, BLOCKED,
            f"{fails[0].check_id} failed: {fails[0].reason}"
            + (f" (+{len(fails) - 1} more)" if len(fails) > 1 else ""),
        )

    missing = [c for c in all_ids if c not in results]
    stale = [results[c] for c in all_ids if c in results and results[c].status is Status.STALE]
    if stale:
        return RepoState(
            repo, results, IN_PROGRESS,
            f"{len(stale)} stale result(s); re-run {', '.join(s.check_id for s in stale[:4])}",
        )

    escalated = [
        results[c] for c in all_ids if c in results and results[c].status is Status.ESCALATED
    ]
    na = [results[c] for c in all_ids if c in results and results[c].status is Status.NA]

    # NA means "could not be measured here". If a check could not be measured
    # and nobody has escalated it, the repo is still mid-flight -- calling that
    # terminal would be the portfolio lying about its own coverage.
    if missing or na:
        blockers = len(missing) + len(na)
        detail = ""
        if na:
            detail = f"; first unmeasurable: {na[0].check_id} ({na[0].reason[:60]})"
        elif missing:
            detail = f"; not yet run: {', '.join(missing[:5])}"
        if escalated:
            return RepoState(
                repo, results, AWAITING,
                f"{len(escalated)} check(s) await sign-off, {blockers} not yet measured{detail}",
            )
        return RepoState(repo, results, IN_PROGRESS, f"{blockers} check(s) outstanding{detail}")

    if escalated:
        return RepoState(
            repo, results, AWAITING,
            f"{len(escalated)} check(s) reserved to the signatory: "
            + ", ".join(e.check_id for e in escalated),
        )

    return RepoState(repo, results, READY, "all 25 checks pass")


def render_portfolio(states: list[RepoState], nonce: str) -> str:
    """The table printed at the end of every turn."""
    from .core.table import LEGEND, render

    rows = []
    for st in states:
        rows.append(
            [
                st.repo.name,
                st.repo.short_sha or "-",
                compact(st.results, PHASE_ORDER["triage"]),
                compact(st.results, PHASE_ORDER["selection"]),
                compact(st.results, PHASE_ORDER["readiness"]),
                compact(st.results, PHASE_ORDER["decision"]),
                compact(st.results, PHASE_ORDER["economics"]),
                st.state,
            ]
        )
    table = render(
        rows,
        ["REPO", "SHA", "T1-5", "S1-5", "R(9,1-8)", "D1-5", "E1-5", "STATE"],
    )

    lines = [table, "", LEGEND, ""]
    lines.append("Why each repo is where it is:")
    for st in states:
        lines.append(f"  {st.repo.name:<11} {st.state:<16} {st.reason}")
    lines.append("")
    lines.append(f"run nonce: {nonce}")
    return "\n".join(lines)
