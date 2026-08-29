"""The check registry.

Twenty-seven checks across five phases. The registry is the single place that
knows what exists, what phase it belongs to, and -- importantly -- what order
it runs in, because for readiness that order is not numerical.
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
PHASE_ORDER: dict[str, list[str]] = {
    "triage": ["T1", "T2", "T3", "T4", "T5"],
    "selection": ["S1", "S2", "S3", "S4", "S5"],
    "readiness": ["R9", "R10", "R11", "R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8"],
    "decision": ["D1", "D2", "D3", "D4", "D5"],
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


def for_phase(phase: str) -> list[CheckSpec]:
    if phase not in PHASE_ORDER:
        raise KeyError(f"unknown phase {phase!r}; expected one of {PHASES}")
    return [_REGISTRY[cid] for cid in PHASE_ORDER[phase] if cid in _REGISTRY]


def all_check_ids() -> list[str]:
    out: list[str] = []
    for phase in PHASES:
        out.extend(PHASE_ORDER[phase])
    return out


def load_all() -> None:
    """Import every check module so the registry is populated."""
    from . import decision, economics, readiness, selection, triage  # noqa: F401
