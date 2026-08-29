"""Terminal-state resolution and the portfolio table.

A repo is in exactly one of three terminal states, and the rules that pick it
are the whole point of this module:

* **BLOCKED** — something failed, or a hard stop fired. Needs a one-line reason
  in ``docs/BLOCKERS.md``.
* **AWAITING-SIGNOFF** — nothing failed, nothing is unmeasured, and what remains
  is reserved to a human signatory. Needs an open item in
  ``docs/ESCALATIONS.md``.
* **READY-TO-TRAIN** — every gating check passes.

The gating set is every check the registry places in the four non-triage
phases, and it is DERIVED rather than listed: ``gating_ids()`` reads
``checks.PHASE_ORDER``, and the size of the set is whatever that returns. No
count is written here on purpose. This docstring used to list the phases and
end with a remembered total -- "S1-S5, R1-R11, D1-D5, E1-E5: twenty-six" -- and
it went on saying it after R12 joined ``PHASE_ORDER``, so the module that
defines the gating set described a set one check smaller than the one it
returns. ``checks/__init__.py``'s own docstring
records the rule that prevents it: a count is obtained by counting, never by
remembering. ``tests/test_promotion_state.py`` now holds any count of checks
stated in this file against ``len(gating_ids())``.

Triage (T1–T5) is deliberately outside the gating set -- triage diagnoses and
reorders the queue, it does not gate. A triage FAIL still blocks, because a
measured failure blocks wherever it is found; it simply is not part of the
"everything passes" test.

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
#: Everything measurable passes; what is left is a key someone must paste in.
#: Distinguished from IN-PROGRESS because the remaining work is procurement,
#: not engineering, and from READY-TO-TRAIN because the run cannot start yet.
READY_PENDING_KEYS = "READY-PENDING-KEYS"
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


#: Phases whose checks gate READY-TO-TRAIN. Triage is diagnostic, not a gate.
GATING_PHASES = ("selection", "readiness", "decision", "economics")


def gating_ids() -> list[str]:
    return [cid for phase in GATING_PHASES for cid in PHASE_ORDER[phase]]


def resolve(repo: Repo, results: dict[str, CheckResult]) -> RepoState:
    """Decide a repo's terminal state from its measured results."""
    all_ids = gating_ids()

    halts = [r for r in results.values() if r.evidence.get("halt")]
    if halts:
        h = halts[0]
        return RepoState(repo, results, BLOCKED, f"{h.check_id} hard stop: {h.reason}")

    # Scan every result, not just the gating set: a measured failure blocks
    # wherever it is found, and a triage FAIL is still a failure.
    ordered = [cid for phase in PHASES for cid in PHASE_ORDER[phase]]
    fails = [results[c] for c in ordered if c in results and results[c].status is Status.FAIL]
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
    deferred = [
        results[c] for c in all_ids if c in results and results[c].status is Status.DEFERRED
    ]

    # NA means "could not be measured here". If a check could not be measured
    # and nobody has escalated it, the repo is still mid-flight -- calling that
    # terminal would be the portfolio lying about its own coverage.
    #
    # Precedence matters here and is easy to get backwards. The checks the
    # registry marks `human_only` ALWAYS report ESCALATED, so letting escalation
    # win would make every repo read AWAITING-SIGNOFF -- "done, just needs a
    # signature" -- the moment it has run its phases, however little was
    # actually measured.
    # Unmeasured work outranks a pending signature.
    if missing or na:
        outstanding = len(missing) + len(na)
        detail = ""
        if na:
            detail = f"; first unmeasurable: {na[0].check_id} ({na[0].reason[:60]})"
        elif missing:
            detail = f"; not yet run: {', '.join(missing[:5])}"
        suffix = f", {len(escalated)} also await sign-off" if escalated else ""
        keys = f", {len(deferred)} wired awaiting keys" if deferred else ""
        return RepoState(
            repo, results, IN_PROGRESS,
            f"{outstanding} of {len(all_ids)} check(s) unmeasured{detail}{suffix}{keys}",
        )

    # Nothing failed, nothing is unmeasured. What remains is a credential the
    # signatory will supply, a signature, or both. A repo here is materially
    # ready: its code paths run end to end and stop only at a boundary that is
    # a procurement step rather than an engineering one.
    if deferred:
        creds = sorted({str(d.evidence.get("credential", "?")) for d in deferred})
        sign = f"; {len(escalated)} also await sign-off" if escalated else ""
        return RepoState(
            repo, results, READY_PENDING_KEYS,
            f"{len(deferred)} check(s) wired and awaiting: {', '.join(creds)}{sign}",
        )

    if escalated:
        return RepoState(
            repo, results, AWAITING,
            f"{len(escalated)} check(s) reserved to the signatory: "
            + ", ".join(e.check_id for e in escalated),
        )

    return RepoState(repo, results, READY, f"all {len(all_ids)} gating checks pass")


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
        ["REPO", "SHA", "T1-5", "S1-5", "R(9,10,11,1-8)", "D1-5", "E1-5", "STATE"],
    )

    lines = [table, "", LEGEND, ""]
    lines.append("Why each repo is where it is:")
    for st in states:
        lines.append(f"  {st.repo.name:<11} {st.state:<16} {st.reason}")
    lines.append("")
    lines.append(f"run nonce: {nonce}")
    return "\n".join(lines)
