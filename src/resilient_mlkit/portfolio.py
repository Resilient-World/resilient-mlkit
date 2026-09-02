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
from .core.artifact import refuse_uncommitted
from .core.repo import Repo
from .core.result import ALLOW_DIRTY_KEY, CheckResult, Status
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


#: Exit code per terminal state, in the order one outranks another: first match
#: wins. Deliberately the SAME ladder ``cli.cmd_check`` uses for statuses, so
#: the two commands cannot disagree about what a number off this tool means --
#: 1 is a failure, 3 is incomplete, 4 is waiting on a person.
#:
#: ``_cmd_portfolio`` used to ``return 0`` unconditionally, which made
#: ``README.md``'s "1 something failed (CI gates on this)" false for
#: ``--portfolio``: a BLOCKED repo rendered in the table and exited green, so
#: any CI job gating on this command gated on nothing. The README states the
#: contract correctly and is not edited; this is the code being brought to it.
STATE_EXIT_CODES: tuple[tuple[str, int], ...] = (
    (BLOCKED, 1),
    (IN_PROGRESS, 3),
    (READY_PENDING_KEYS, 4),
    (AWAITING, 4),
    (READY, 0),
)

#: What an unrecognised terminal state exits. Fail closed: a state this module
#: does not know about has not been shown to be a pass, and the alternative --
#: falling through to 0 -- is the defect being fixed, one layer down.
UNKNOWN_STATE_EXIT = 1


def exit_code(states: list[RepoState]) -> int:
    """The worst resolved state across the portfolio, as an exit code.

    Empty input exits 1 rather than 0. A portfolio report over no repos is not
    a clean portfolio; it is a report that measured nothing, and
    ``scripts/verify_served_hash_parity.py`` already sets the precedent that a
    green report over nothing is the defect rather than the pass.
    """
    if not states:
        return UNKNOWN_STATE_EXIT
    present = {st.state for st in states}
    # A hard stop is a BLOCKED by construction in `resolve`, but assert it here
    # too: a hard stop reaching this function under any other label is a bug in
    # `resolve`, and it must not be able to exit 0 while that bug exists.
    if any(st.halted for st in states):
        return 1
    unknown = present - {name for name, _ in STATE_EXIT_CODES}
    if unknown:
        return UNKNOWN_STATE_EXIT
    for name, code in STATE_EXIT_CODES:
        if name in present:
            return code
    return UNKNOWN_STATE_EXIT


def phase_header(phase: str) -> str:
    """A phase's column header, DERIVED from ``PHASE_ORDER``.

    The headers were hand-written strings, and the readiness one had gone stale
    in place: ``"R(9,10,11,1-8)"`` names one id fewer than
    ``PHASE_ORDER["readiness"]`` holds, having not been updated when R12 joined
    it. A header is a count, and this package's own rule is that a count is
    obtained by counting -- so the header now expands from the registry and the
    literal is gone. ``tests/test_portfolio_exit.py`` holds every integer a
    header names against the ids the phase actually runs.

    Ids are compressed into runs of consecutive numbers **in the order the
    phase runs them**, because that order is itself a claim readiness makes
    (R9 first, R8 last) and a sorted header would quietly deny it. One run
    renders bare (``T1-5``); more than one is parenthesised (``R(9-12,1-8)``).
    Anything that is not a shared-prefix-plus-integer falls back to listing the
    ids, which is longer and always true.
    """
    ids = PHASE_ORDER[phase]
    if not ids:
        return phase.upper()
    prefix = ids[0].rstrip("0123456789")
    parts: list[tuple[str, str]] = []
    for cid in ids:
        stem = cid.rstrip("0123456789")
        num = cid[len(stem):]
        if stem != prefix or not num:
            return ",".join(ids)
        parts.append((stem, num))

    runs: list[list[int]] = []
    for _, num in parts:
        n = int(num)
        if runs and n == runs[-1][-1] + 1:
            runs[-1].append(n)
        else:
            runs.append([n])
    rendered = ",".join(f"{r[0]}-{r[-1]}" if len(r) > 1 else str(r[0]) for r in runs)
    return f"{prefix}{rendered}" if len(runs) == 1 else f"{prefix}({rendered})"


def resolve(repo: Repo, results: dict[str, CheckResult]) -> RepoState:
    """Decide a repo's terminal state from its measured results.

    Raises ``UncommittedRead`` if any result carries ``ALLOW_DIRTY_KEY`` --
    evidence read from the working tree under ``core.artifact``'s diagnosis-only
    escape hatch. A terminal state is the most consequential thing this package
    emits, and it must not be computable from bytes that are in nobody's git
    history. The refusal is here rather than at the call sites because every
    caller that wants a state comes through this function, and a check placed in
    one caller is a check the next caller forgets to make.

    ``CheckResult.__post_init__`` already refuses a marked PASS, so this catches
    the rest: a marked FAIL that would BLOCK a repo, or a marked NA whose reason
    a reader would take as measured coverage. "Nobody could check this" and
    "this was checked" must not resolve to the same table cell.
    """
    for cid in sorted(results):
        refuse_uncommitted(
            bool(results[cid].evidence.get(ALLOW_DIRTY_KEY)),
            f"check {cid} of {repo.name}",
        )
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
        # Cells and headers are both generated from PHASES x PHASE_ORDER, so a
        # column cannot come to be labelled with one phase and filled from
        # another -- which is how the readiness header came to name eleven
        # checks beside a cell rendering twelve.
        rows.append(
            [
                st.repo.name,
                st.repo.short_sha or "-",
                *(compact(st.results, PHASE_ORDER[p]) for p in PHASES),
                st.state,
            ]
        )
    table = render(
        rows,
        ["REPO", "SHA", *(phase_header(p) for p in PHASES), "STATE"],
    )

    lines = [table, "", LEGEND, ""]
    lines.append("Why each repo is where it is:")
    for st in states:
        lines.append(f"  {st.repo.name:<11} {st.state:<16} {st.reason}")
    lines.append("")
    lines.append(f"run nonce: {nonce}")
    # E-M24 residual. This IS a readiness table -- the `R(9-12,1-8)` column is
    # R1-R12 -- and it is the one that is COMPOSED from `.mlkit/results/*.json`
    # rather than measured in the process that prints it. So it needs both
    # halves of "which mlkit": this line names the build that RENDERED it, and
    # `core/store.py` stales any PASS whose stored build is not this one, which
    # is what stops the table from carrying another build's verdicts silently.
    from .core import identity

    lines.extend(identity.header_lines())
    return "\n".join(lines)
