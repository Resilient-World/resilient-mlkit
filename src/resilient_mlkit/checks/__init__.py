"""The check registry.

Thirty-three checks across five phases. The registry is the single place that
knows what exists, what phase it belongs to, and -- importantly -- what order
it runs in, because for readiness that order is not numerical.

That count was "twenty-seven" until R12 was added, and it had been wrong by
four since well before this branch: the registry held thirty-one. It is
corrected here by COUNTING (``len(_REGISTRY)`` after ``load_all()``), not by
remembering, which is the only way a number in a docstring is ever worth
anything.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from ..core.repo import Repo
from ..core.result import CheckResult


@dataclass
class RunContext:
    """Everything a check needs that is not the repo itself."""

    nonce: str
    root: Path
    #: Set when the caller knows there is no network / no AWS, so that checks
    #: report NA with an accurate reason instead of a confusing timeout.
    offline: bool = False
    #: ``mlkit check --allow-dirty``. A check that reads a repo artifact reads
    #: it from COMMITTED state; this is the diagnosis-only escape hatch that
    #: lets it read the working tree instead, and it is not free. Every result
    #: descending from such a read carries
    #: ``evidence[core.result.ALLOW_DIRTY_KEY]``, and that marker is refused by
    #: ``CheckResult.__post_init__`` (for a PASS) and by ``portfolio.resolve``
    #: (for everything else). The flag buys a diagnosis and structurally cannot
    #: buy a verdict, which is the same bargain ``mlkit fleet --allow-dirty``
    #: already makes for the fleet table.
    allow_dirty: bool = False
    timeout: float = 20.0
    #: Results already produced in this run, keyed by check id. The runner
    #: fills this as it goes so that a reporting check (R8) can summarise the
    #: checks that preceded it in the same run rather than reading back a
    #: possibly-stale file.
    prior: dict[str, CheckResult] = field(default_factory=dict)


CheckFn = Callable[[Repo, RunContext], CheckResult]


@dataclass(frozen=True)
class CheckSpec:
    check_id: str
    phase: str
    title: str
    fn: CheckFn
    #: True when the check is reserved to a human signatory. These always
    #: return ESCALATED; the agent may not satisfy them.
    human_only: bool = False


PHASES = ("triage", "selection", "readiness", "decision", "economics")

#: Execution order per phase.
#:
#: Readiness is deliberately NOT numerical. R9 runs first because it is the
#: cheapest check in the phase and the most decisive: a licence defect makes
#: every downstream result moot, and it is the one class of defect that gets
#: more expensive the longer you train. After that the order is
#: cheapest-and-most-decisive-first as the readiness package prescribes.
#:
#: R10 runs second on the same reasoning. It is a pure AST walk -- no imports,
#: no data, no network -- so it is the cheapest check after R9, and it is
#: decisive in the widest sense: a fabricated default invalidates every figure
#: downstream of it, including the ones the other readiness checks measure. It
#: also runs before R1-R7 because those go through declared bindings and so
#: cannot see the code R10 is looking at.
#:
#: R11 runs third, immediately after R10 and immediately before R5, and both
#: placements are deliberate. It is the same kind of walk -- ast only, no
#: imports -- so it is as cheap as R10. And it must precede R5, because when
#: R11 fires, R5's own inputs are not to be believed: R5 counts rows by the
#: provenance field that R11 has just shown to be false, so an R5 PASS
#: recorded after an R11 FAIL is a pass counted with a broken ruler. Running
#: it first means the readiness table reads in the order the defects
#: compound. R8 stays last: it reports.
#:
#: R12 runs fourth, with the other two ast walks, for the cost reason only. It
#: imports nothing and reads no data, so it belongs in the cheap group; unlike
#: R11 it has no ordering DEPENDENCY on a later check, because nothing
#: downstream counts anything by what R12 adjudicates. Its placement here is
#: therefore a scheduling choice and not an argument, and it deliberately
#: leaves R10's and R11's relative positions — and every existing check's
#: behaviour — untouched.
PHASE_ORDER: dict[str, list[str]] = {
    "triage": ["T1", "T2", "T3", "T4", "T5"],
    "selection": ["S1", "S2", "S3", "S4", "S5"],
    # R13 (M-2, 2026-09-04) sits with the other three walks that import
    # nothing: it reads committed blobs and CLAUDE.md's own history, so it is
    # as cheap as R10-R12 and measures correctly from any interpreter. Placed
    # after R12 and before R1 for the cost reason only; no existing id moves.
    "readiness": [
        "R9", "R10", "R11", "R12", "R13", "R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8",
    ],
    # D6 is appended, not inserted. Every existing decision id keeps its
    # position, so the only movement in the phase is one row at the end and a
    # denominator of six.
    "decision": ["D1", "D2", "D3", "D4", "D5", "D6"],
    "economics": ["E1", "E2", "E3", "E4", "E5"],
}

_REGISTRY: dict[str, CheckSpec] = {}


def register(spec: CheckSpec) -> CheckSpec:
    if spec.check_id in _REGISTRY:
        raise RuntimeError(f"duplicate check id {spec.check_id}")
    _REGISTRY[spec.check_id] = spec
    return spec


def check(check_id: str, phase: str, title: str, *, human_only: bool = False):
    """Decorator registering a check function."""

    def _wrap(fn: CheckFn) -> CheckFn:
        register(CheckSpec(check_id, phase, title, fn, human_only))
        return fn

    return _wrap


def get(check_id: str) -> CheckSpec:
    return _REGISTRY[check_id]


#: The reason a synthesized row carries. A constant because the test that
#: forces the row and the code that emits it must match on the same sentence
#: rather than on two hand-typed strings that drift apart.
UNREGISTERED_REASON = "declared in PHASE_ORDER but absent from registry after load_all()"


def missing_from_registry() -> list[str]:
    """Ids ``PHASE_ORDER`` declares that ``_REGISTRY`` does not hold.

    Empty on a healthy tree. ``tests/test_registry_completeness.py`` asserts
    exactly that, so the synthesized row below is a backstop against a state
    the real package is never in -- not a state anyone is meant to reach.
    """
    return [cid for cid in all_check_ids() if cid not in _REGISTRY]


def _unregistered(check_id: str, phase: str) -> CheckSpec:
    """A FAIL-shaped stand-in for a check that declared itself and never arrived.

    This function is the whole of the fix for the defect this module used to
    have. ``for_phase`` filtered on ``if cid in _REGISTRY``, so an id that
    ``PHASE_ORDER`` declares and the registry does not hold was not reported
    missing -- it stopped existing. A phase that lost a check to an import
    error, a typo in a decorator, or a module dropped from ``load_all()`` ran
    the remainder and counted the remainder.

    What that actually produced, MEASURED against ``main`` 3df724d rather than
    described -- R5 removed from ``_REGISTRY`` and a readiness phase run
    against a fixture repo::

        READINESS: 1/12 PASS  ESCALATED=1  NA=9        exit 3
        R5     -          not run

    So the denominator was never wrong (``cmd_check`` read
    ``len(PHASE_ORDER[phase])`` on that build too) and the row was not invisible
    (``core.table.phase_table`` already rendered ``not run``). One earlier
    version of this docstring said the run "printed a green ``11/11``" and
    exited 0; that baseline was written from reasoning rather than from a run
    and both halves of it are false. Corrected here rather than left standing,
    because a fabricated baseline is exactly what CLAUDE.md rule 2 forbids and
    an overstated defect makes the real one harder to see.

    The real defect, which is narrower and is what this function fixes: the
    status counts summed to eleven beside a denominator of twelve, and the
    ladder answered 3 -- "unmeasured" -- for what is an instrument fault. A
    check that declared itself and never arrived is not something the
    environment failed to support; it is the registry failing to account for
    its own parts, and it must exit 1.

    A synthesized FAIL is the right shape rather than an NA. NA means "the
    environment could not support this measurement", and that is a statement
    about the world; this is a statement about the instrument, and an
    instrument that cannot account for its own declared parts is broken, not
    unlucky.
    """

    def _fn(repo: Repo, ctx: RunContext) -> CheckResult:
        return CheckResult.failed(
            check_id,
            phase,
            UNREGISTERED_REASON,
            {
                "declared_in": "checks.PHASE_ORDER",
                "phase": phase,
                "registry_size": len(_REGISTRY),
                "registered_in_phase": [c for c in PHASE_ORDER[phase] if c in _REGISTRY],
                "remedy": (
                    "the check module either failed to import inside load_all() or no "
                    "longer registers this id. Fix the module; do not remove the id "
                    "from PHASE_ORDER to make this row go away"
                ),
            },
        )

    return CheckSpec(check_id, phase, f"{check_id} (unregistered)", _fn)


def for_phase(phase: str) -> list[CheckSpec]:
    """Every id ``PHASE_ORDER`` declares for ``phase``, in order, none dropped.

    The length of the returned list is ``len(PHASE_ORDER[phase])``, always. An
    id the registry does not hold comes back as a spec that FAILs with
    ``UNREGISTERED_REASON`` instead of being filtered out.
    """
    if phase not in PHASE_ORDER:
        raise KeyError(f"unknown phase {phase!r}; expected one of {PHASES}")
    return [
        _REGISTRY[cid] if cid in _REGISTRY else _unregistered(cid, phase)
        for cid in PHASE_ORDER[phase]
    ]


def phase_ids(phase: str) -> list[str]:
    """The ids ``PHASE_ORDER`` declares for ``phase``, read live.

    The denominator of a phase run. Callers go through this rather than
    importing ``PHASE_ORDER`` by name so that there is exactly one answer to
    "how many checks are in this phase", and so a caller cannot end up holding
    a stale binding to a dict the registry has since been asked about.
    """
    if phase not in PHASE_ORDER:
        raise KeyError(f"unknown phase {phase!r}; expected one of {PHASES}")
    return list(PHASE_ORDER[phase])


def all_check_ids() -> list[str]:
    out: list[str] = []
    for phase in PHASES:
        out.extend(PHASE_ORDER[phase])
    return out


def load_all() -> None:
    """Import every check module so the registry is populated."""
    from . import decision, economics, parity, readiness, selection, triage  # noqa: F401
