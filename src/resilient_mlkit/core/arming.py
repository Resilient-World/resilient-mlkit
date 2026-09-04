"""What an adopter's hard-stops module renders, defined ONCE (rule 7; M-1).

``resilient-torrent``'s ``src/torrent/mlops/hard_stops.py`` and
``resilient-chokepoint``'s ``src/resilient_chokepoint/mlops/hard_stops.py`` each
compute, locally, what "armed" and "halt required" mean for a D2/E1 result::

    "armed": bool(declared) and status in {"PASS", "FAIL"},
    "halt_required": status == "FAIL",

That was right when a check had six statuses. With a seventh --
``Status.UNMEASURABLE``, an armed check whose declared input this machine
cannot supply -- both lines go quietly wrong in the same direction: an
UNMEASURABLE D2 reads as *not armed* (the declaration exists, mlkit reached
a verdict on it, and the verdict is that the machine cannot measure it) and as
*no halt required* (the run may not start). Two repos correcting two copies
is how eight definitions of "ready" happen, so the rule lives here and the
adopters import it.

The three fields are deliberately separate, because they are three facts:

* ``armed`` -- the declaration exists and mlkit reached a terminal verdict on
  it. PASS, FAIL and UNMEASURABLE are all verdicts about an armed stop; NA is
  not (no binding, or a declaration mlkit could not read).
* ``halt_required`` -- the run may not start. True for FAIL (the stop fired)
  AND for UNMEASURABLE (the stop is armed and could not be read; a run taken
  now would be taken with a tripwire nobody could see).
* ``indicted`` -- the pipeline is at fault. True ONLY for FAIL. An
  UNMEASURABLE stop indicts nothing; that is the whole reason it is not FAIL.
"""

from __future__ import annotations

from dataclasses import dataclass

from .result import Status

#: Statuses that are verdicts ABOUT an armed stop.
ARMED_STATUSES: frozenset[Status] = frozenset(
    {Status.PASS, Status.FAIL, Status.UNMEASURABLE}
)

#: Statuses under which the run may not start.
HALTING_STATUSES: frozenset[Status] = frozenset({Status.FAIL, Status.UNMEASURABLE})


@dataclass(frozen=True)
class ArmState:
    """The three facts an adopter's hard-stops block renders per stop."""

    declared: bool
    status: Status
    armed: bool
    halt_required: bool
    indicted: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "declared": self.declared,
            "status": self.status.value,
            "armed": self.armed,
            "halt_required": self.halt_required,
            "indicted": self.indicted,
        }


def arm_state(declared: bool, status: Status | str) -> ArmState:
    """The single definition of armed / halt_required / indicted.

    Args:
        declared: whether ``.mlkit/repo.toml`` declares the binding the stop is
            rendered from (``Repo.binding(name) is not None``).
        status: the mlkit check's terminal status for that stop.
    """
    st = Status(status) if isinstance(status, str) else status
    armed = bool(declared) and st in ARMED_STATUSES
    return ArmState(
        declared=bool(declared),
        status=st,
        armed=armed,
        halt_required=armed and st in HALTING_STATUSES,
        indicted=armed and st is Status.FAIL,
    )
