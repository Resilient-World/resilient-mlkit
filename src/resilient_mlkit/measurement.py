"""The repo-facing measurement primitive. **This is the import that replaces the copies.**

WHAT THIS IS FOR
----------------
A gate inside a model repo needs a small vocabulary: a verdict that cannot
claim a number nobody measured, and a way to say "unmeasured, and here is why"
that can never be mistaken for a pass. ``core.result`` has defined that
vocabulary for the whole portfolio since the beginning, but it has never been
importable at a *gate site*: ``CheckResult`` is shaped for a portfolio check —
it wants a ``check_id`` and a ``phase``, and it lands in ``.mlkit/results/`` —
not for a function inside ``validation/`` that has just failed to find its
input.

So three repos wrote the vocabulary out by hand instead. That is CLAUDE.md
rule 7's exact failure mode, and it is not laziness on their part: there was
nothing to import. This module is the thing to import.

THE COPIES THIS SUPERSEDES
--------------------------
Named here so a later iteration converging them has one place to look. **This
iteration edits none of them** — blackout, triage and choco all carry open
colleague PRs, and a shared primitive is adopted by the repo that owns the
call sites, not pushed into it from outside.

* ``resilient-blackout`` ``resilient_blackout/validation/unmeasured.py`` —
  ``Unmeasured``, ``GateUnmeasured``, ``MetricUnmeasured``,
  ``ValidationUnmeasured``, ``EstimateResult``.
* ``resilient-triage`` ``src/resilient_triage/measurement.py`` —
  ``GateUnmeasured``, ``Status``, ``Measured``.
* ``resilient-choco`` ``src/registry/promotion_gate.py`` (``GateUnmeasured``)
  and ``src/validation/_report.py`` (``ValidationUnmeasured``,
  ``ValidationResult``) — the design the other two say they mirrored.

Every name those five modules define is exported here, so a repo can converge
by changing an import rather than by rewriting its call sites.

WHY SIX STATES AND NOT THREE
----------------------------
All three copies collapsed the portfolio's six statuses into three
(PASS/FAIL/NA). ``core.result.Status``'s own docstring says what that costs,
and it is worth repeating at the surface a repo will actually import:

    DEFERRED exists because collapsing it into NA makes the portfolio lie in
    the expensive direction. "The dataloader raises ImportError" and "the
    dataloader runs, reaches the API, and needs a key" are not the same
    distance from a productive training run, and a table that renders them
    identically cannot answer the only question that matters: how close is
    this repo to a real run.

STALE and ESCALATED carry the same kind of information — measured against a
different tree, and reserved to the human signatory — and a three-state gate
has to render both as NA or as FAIL, both of which are false.

So ``Status`` here is not a new enum that happens to agree. It **is**
``core.result.Status``, re-exported: ``measurement.Status is
core.result.Status`` is asserted in ``tests/test_measurement_primitive.py``. A
fourth definition of "ready" is the thing this module exists to prevent, and
defining one inside the module that prevents it would be a joke.

NOTHING IS RE-IMPLEMENTED HERE
------------------------------
Every constructor below delegates to ``CheckResult``'s own named constructor
and reads its result back. The structural refusals — a non-PASS with no
reason, a PASS with no evidence, a PASS resting on an ``--allow-dirty`` read,
credential redaction — are enforced by ``core.result`` and are inherited, not
restated. That is deliberate: a second implementation that "agrees" is a second
implementation, and the parametrized equivalence test in
``tests/test_measurement_primitive.py`` exists to keep this one from becoming
that. It is the discipline of ``scripts/verify_served_hash_parity.py`` — which
checks that adopting mlkit's contract does not silently redefine an identity a
repo already recorded — applied to a verdict instead of a digest.

WHAT ADOPTING THIS CHANGES AT EACH COPY SITE
--------------------------------------------
Stated plainly, because "purely a rename" would be a claim, and it is false:

* **A PASS must carry evidence.** ``core.result`` refuses a PASS with an empty
  ``metrics`` dict — "a pass with nothing measured behind it is
  indistinguishable from a fabricated one". None of the three copies enforces
  that. A repo adopting this will find any evidence-free PASS it has, which is
  the point.
* **NA keeps its metrics.** triage's copy drops ``metrics`` on NA; this does
  not, because ``core.result`` treats evidence on a non-PASS as the record of
  what *was* measured before the wall (``CheckResult.deferred`` depends on
  exactly that). An NA still emits no *figure for the gate* — ``value`` is
  ``None`` — so nothing downstream can copy a number out of it.
* **Reasons are redacted and length-bounded** on the way in, by
  ``core.result.redact``. A gate that interpolates an exception into its reason
  no longer has to remember rule 13.
* **``passed`` is derived, never assigned.** In all three copies ``passed`` is
  a constructor argument that ``__post_init__`` then corrects. Here it is a
  read-only property of the status, so "NA that passed" is not a state that can
  be built and then fixed; it cannot be spelled. The PASS constructor is
  therefore called ``Measured.ok``, leaving ``passed`` to mean the question a
  reader asks rather than a value a caller sets.

USAGE
-----
::

    from resilient_mlkit.measurement import Measured, GateUnmeasured, Status

    def coverage_gate(rows) -> Measured:
        if not rows:
            return Measured.unmeasured(
                "conformal_coverage",
                reason="no scored rows: the calibration split is empty",
                gate_description="empirical coverage ≥ 0.9",
            )
        covered = sum(r.inside for r in rows) / len(rows)
        if covered < 0.9:
            return Measured.failed(
                "conformal_coverage",
                reason=f"empirical coverage {covered:.4f} < 0.9",
                metrics={"coverage": covered, "n_rows": len(rows)},
            )
        return Measured.ok(
            "conformal_coverage", metrics={"coverage": covered, "n_rows": len(rows)}
        )

``GateUnmeasured`` is the other half, for the call sites that return a single
figure and must not be allowed to return a plausible default instead::

    if variance == 0.0:
        raise GateUnmeasured("constant series: a correlation is undefined here")

A gate that hands mlkit its verdict calls ``to_result(check_id, phase)`` and
gets a real ``CheckResult`` back.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .core.result import (
    ALLOW_DIRTY_KEY,
    MAX_REASON,
    CheckResult,
    CredentialRequired,
    FabricationError,
    Status,
    UncommittedRead,
    redact,
)

__all__ = [
    "ALLOW_DIRTY_KEY",
    "MAX_REASON",
    "MEASURED_STATUSES",
    "CheckResult",
    "CredentialRequired",
    "FabricationError",
    "GateUnmeasured",
    "Measured",
    "MetricUnmeasured",
    "Status",
    "UncommittedRead",
    "Unmeasured",
    "ValidationUnmeasured",
    "redact",
]

#: The phase a gate inside a repo reports under when it has not been told one.
#: ``CheckResult`` requires a phase because the portfolio table is grouped by
#: one; a repo-local gate is not part of any phase, and saying so is better
#: than borrowing a phase letter that means something else.
REPO_GATE_PHASE = "repo-gate"

#: The two statuses that mean "a measurement happened and a verdict came out of
#: it". Everything else is a statement about why one did not, and the
#: distinction is the whole reason NA must not render like PASS.
MEASURED_STATUSES = frozenset({Status.PASS, Status.FAIL})

#: How each status renders as a leading token. Six distinct tokens, and the
#: four non-verdict ones each say what kind of not-measured they are, so a
#: reader scanning a column cannot mistake one for another or for a pass.
_RENDER_TOKEN = {
    Status.PASS: "PASS",
    Status.FAIL: "FAIL",
    Status.NA: "NA (unmeasured)",
    Status.DEFERRED: "DEFERRED (wired, awaiting a credential)",
    Status.STALE: "STALE (measured against another tree)",
    Status.ESCALATED: "ESCALATED (reserved to the signatory)",
}


class Unmeasured(RuntimeError):
    """Base for every "this figure was never measured" signal.

    Raised instead of substituting a default. The three copies this module
    supersedes all define this family; it is exported under the same names so
    converging is an import change rather than a rewrite.
    """


class GateUnmeasured(Unmeasured):
    """A gate's input artifact is absent or unusable, so its figure is unmeasured.

    A gate that invents the number it gates on reports confidence about
    something nobody measured. An unmeasured gate is recorded NA with its
    reason and never passes (CLAUDE.md rules 1 and 2).
    """


class MetricUnmeasured(Unmeasured):
    """A reported metric has no measurement behind it.

    Raised instead of returning the value that would satisfy the metric's
    consumer — a coverage of ``1.0`` from an empty history, a loss of ``0.0``
    from an empty epoch list, a correlation of ``0.0`` from a constant series.
    """


class ValidationUnmeasured(Unmeasured):
    """A benchmark's input artifact is absent or synthetic, so its figure is unmeasured."""


@dataclass
class Measured:
    """One repo-local gate outcome, over the portfolio's six statuses.

    Construct through the named constructors; they read as claims and they
    make the reason non-optional where it matters. Direct construction is
    validated identically, because both routes end at ``CheckResult``.

    ``passed`` is a property, not a field: there is no way to build an NA that
    passes and then correct it, which is how all three hand copies had to spell
    the same invariant.
    """

    name: str
    status: Status = Status.PASS
    metrics: dict[str, Any] = field(default_factory=dict)
    reason: str = ""
    gate_description: str = ""
    notes: list[str] = field(default_factory=list)
    #: Only used when this is handed to mlkit as a ``CheckResult``.
    phase: str = REPO_GATE_PHASE

    def __post_init__(self) -> None:
        # Every structural rule lives in core.result and is applied by building
        # one. Nothing is re-checked here: a second copy of the rule is a
        # second definition of it, which is the defect this module retires.
        result = CheckResult(
            check_id=self.name,
            phase=self.phase,
            status=self.status,
            reason=self.reason,
            evidence=dict(self.metrics),
        )
        self.status = result.status
        self.reason = result.reason
        self.metrics = dict(result.evidence)
        self.notes = list(self.notes)

    # -- what a reader of the outcome asks it ------------------------------

    @property
    def passed(self) -> bool:
        """True only for PASS. Every other status is not a pass, including NA."""
        return self.status is Status.PASS

    @property
    def measured(self) -> bool:
        """True when a measurement happened and a verdict came out of it."""
        return self.status in MEASURED_STATUSES

    @property
    def unmeasured_reason(self) -> str | None:
        """Why no verdict was reached, or ``None`` when one was.

        The three-state copies expose this for NA alone, because NA is the only
        not-measured status they have. Here it covers all four, which is the
        point: a caller that branches on "is there a reason instead of a
        verdict" keeps working, and gains DEFERRED, STALE and ESCALATED without
        having to render them as NA.
        """
        return None if self.measured else self.reason

    @property
    def value(self) -> None:
        """There is no single figure on a gate outcome; ask ``metrics``.

        Present so that a call site which used to read a substituted default
        gets ``None`` rather than a number. A default is what this whole family
        of types exists to make unspellable.
        """
        return None

    def render(self) -> str:
        """One line, with the status token first and six tokens that differ.

        The fleet's NA-distinctness rule in one method: an unmeasured gate must
        not render like a gate that cleared the bar, and must not render like
        one that failed either. Asserted state by state in
        ``tests/test_measurement_primitive.py``.
        """
        head = f"{_RENDER_TOKEN[self.status]} {self.name}"
        tail = self.reason if self.reason else _summarise(self.metrics)
        return f"{head} — {tail}" if tail else head

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "name": self.name,
            "status": self.status.value,
            "passed": self.passed,
            "measured": self.measured,
            "metrics": self.metrics,
            "rendered": self.render(),
        }
        if self.gate_description:
            out["gate"] = self.gate_description
        if self.reason:
            out["reason"] = self.reason
        if not self.measured:
            out["unmeasured_reason"] = self.reason
        if self.notes:
            out["notes"] = list(self.notes)
        return out

    def to_result(self, check_id: str = "", phase: str = "") -> CheckResult:
        """Hand this to mlkit as a portfolio ``CheckResult``.

        The status, the reason and the evidence cross unchanged; only the
        identifiers a portfolio check needs are supplied here.
        """
        return CheckResult(
            check_id=check_id or self.name,
            phase=phase or self.phase,
            status=self.status,
            reason=self.reason,
            evidence=dict(self.metrics),
        )

    # -- constructors, each delegating to core.result ----------------------

    @classmethod
    def from_result(
        cls,
        result: CheckResult,
        *,
        gate_description: str = "",
        notes: list[str] | None = None,
    ) -> Measured:
        """Wrap a ``CheckResult``. The only route the constructors below take."""
        return cls(
            name=result.check_id,
            status=result.status,
            metrics=dict(result.evidence),
            reason=result.reason,
            gate_description=gate_description,
            notes=list(notes or []),
            phase=result.phase,
        )

    @classmethod
    def ok(
        cls,
        name: str,
        *,
        metrics: dict[str, Any],
        reason: str = "",
        gate_description: str = "",
        notes: list[str] | None = None,
        phase: str = REPO_GATE_PHASE,
    ) -> Measured:
        return cls.from_result(
            CheckResult.passed(name, phase, dict(metrics), reason),
            gate_description=gate_description,
            notes=notes,
        )

    @classmethod
    def failed(
        cls,
        name: str,
        *,
        reason: str,
        metrics: dict[str, Any] | None = None,
        gate_description: str = "",
        notes: list[str] | None = None,
        phase: str = REPO_GATE_PHASE,
    ) -> Measured:
        return cls.from_result(
            CheckResult.failed(name, phase, reason, dict(metrics or {})),
            gate_description=gate_description,
            notes=notes,
        )

    @classmethod
    def unmeasured(
        cls,
        name: str,
        *,
        reason: str,
        metrics: dict[str, Any] | None = None,
        gate_description: str = "",
        notes: list[str] | None = None,
        phase: str = REPO_GATE_PHASE,
    ) -> Measured:
        """NA: the measurement could not be taken, and here is why.

        Never the right answer for "the gate would have failed". Metrics may be
        attached and record what *was* measured before the wall; the gate's own
        figure is ``None`` either way.
        """
        return cls.from_result(
            CheckResult.na(name, phase, reason, dict(metrics or {})),
            gate_description=gate_description,
            notes=notes,
        )

    @classmethod
    def deferred(
        cls,
        name: str,
        *,
        credential: str,
        detail: str = "",
        metrics: dict[str, Any] | None = None,
        gate_description: str = "",
        notes: list[str] | None = None,
        phase: str = REPO_GATE_PHASE,
    ) -> Measured:
        """Wired and exercised; stops at a credential the signatory will supply.

        The state the three-state copies cannot express. Use it only after the
        gate has done everything it can without the key — raising it earlier
        turns a real defect into apparent progress.
        """
        return cls.from_result(
            CheckResult.deferred(name, phase, credential, detail, dict(metrics or {})),
            gate_description=gate_description,
            notes=notes,
        )

    @classmethod
    def stale(
        cls,
        name: str,
        *,
        reason: str,
        metrics: dict[str, Any] | None = None,
        gate_description: str = "",
        notes: list[str] | None = None,
        phase: str = REPO_GATE_PHASE,
    ) -> Measured:
        """Measured, but against a different tree than the one checked out."""
        return cls.from_result(
            CheckResult(name, phase, Status.STALE, reason, dict(metrics or {})),
            gate_description=gate_description,
            notes=notes,
        )

    @classmethod
    def escalated(
        cls,
        name: str,
        *,
        reason: str,
        metrics: dict[str, Any] | None = None,
        gate_description: str = "",
        notes: list[str] | None = None,
        phase: str = REPO_GATE_PHASE,
    ) -> Measured:
        """Reserved to the human signatory (CLAUDE.md rule 12)."""
        return cls.from_result(
            CheckResult.escalated(name, phase, reason, dict(metrics or {})),
            gate_description=gate_description,
            notes=notes,
        )


def _summarise(metrics: dict[str, Any]) -> str:
    """The metrics of a PASS, short enough for a table cell."""
    if not metrics:
        return ""
    parts = [f"{k}={v!r}" for k, v in list(metrics.items())[:4]]
    if len(metrics) > 4:
        parts.append(f"…+{len(metrics) - 4} more")
    return ", ".join(parts)
