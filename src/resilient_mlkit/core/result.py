"""Check results.

The single most important invariant in this package lives here: a result may
not claim a number it did not measure, and it may not be unmeasured without
saying why. Both are enforced structurally in ``__post_init__`` rather than by
convention, because convention is exactly what fails under deadline pressure.

A third joins them: a PASS may not rest on a number read from the working tree
under ``core.artifact``'s ``allow_dirty`` escape hatch. A figure that is in
nobody's git history cannot be fetched by the reader it is quoted to, which
makes it unfalsifiable in exactly the way a fabricated one is -- see
``UncommittedRead`` and ``docs/ESCALATIONS.md`` E-M12.
"""

from __future__ import annotations

import copy as _copy
import datetime as _dt
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

#: Longest reason we will print. Reasons land in tables that get pasted into
#: transcripts and PRs, and an untruncated traceback sets the column width for
#: the whole table.
MAX_REASON = 400

#: Patterns whose *values* must never reach a transcript. Checks interpolate
#: raw exception text into reasons, and cloud SDK errors routinely quote the
#: failing request -- presigned URLs carry X-Amz-Security-Token, and an
#: HTTP 401 body can echo an Authorization header. CLAUDE.md rule 13 makes a
#: secret in a transcript a stopping point, so redaction is structural here
#: rather than left to each call site to remember.
_SECRET_PATTERNS = (
    re.compile(r"(?i)\b(X-Amz-Security-Token|X-Amz-Signature|X-Amz-Credential)=([^\s&\"']+)"),
    re.compile(r"(?i)\b(authorization|bearer|api[_-]?key|access[_-]?token|password|passwd|secret)"
               r"([\"']?\s*[:=]\s*[\"']?)([^\s,&\"';]+)"),
    re.compile(r"\b((?:AKIA|ASIA)[0-9A-Z]{16})\b"),
    re.compile(r"(?i)\b(gh[pousr]_[A-Za-z0-9]{20,})\b"),
)


def redact(text: str) -> str:
    """Strip anything that looks like a credential, then bound the length."""
    for pattern in _SECRET_PATTERNS:
        if pattern.groups >= 3:
            text = pattern.sub(r"\1\2<redacted>", text)
        else:
            text = pattern.sub(
                lambda m: f"{m.group(1)}=<redacted>" if m.lastindex and m.lastindex >= 2
                else "<redacted>",
                text,
            )
    if len(text) > MAX_REASON:
        text = text[: MAX_REASON - 15].rstrip() + " …[truncated]"
    return text


class Status(str, Enum):
    """The six terminal statuses a check may report.

    There is deliberately no ``SKIP`` and no ``WARN``. A check either measured
    something and formed a verdict (PASS/FAIL), could not measure and says why
    (NA), was wired and exercised but stops at a credential the signatory will
    supply (DEFERRED), measured against a different tree than the one checked
    out (STALE), or is reserved to a human signatory (ESCALATED).

    DEFERRED exists because collapsing it into NA makes the portfolio lie in
    the expensive direction. "The dataloader raises ImportError" and "the
    dataloader runs, reaches the API, and needs a key" are not the same
    distance from a productive training run, and a table that renders them
    identically cannot answer the only question that matters: how close is
    this repo to a real run.
    """

    PASS = "PASS"
    FAIL = "FAIL"
    NA = "NA"
    DEFERRED = "DEFERRED"
    STALE = "STALE"
    ESCALATED = "ESCALATED"

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.value


#: Statuses that must carry a human-readable reason. A bare "NA" is worse than
#: no check at all: it looks like coverage and carries no information.
_REASON_REQUIRED = {
    Status.FAIL, Status.NA, Status.DEFERRED, Status.STALE, Status.ESCALATED,
}


#: Evidence key marking a value that descends from a read of the WORKING TREE
#: rather than of the repo's committed state -- ``core.artifact.load(...,
#: allow_dirty=True)``, the diagnosis-only escape hatch.
#:
#: The constant lives here rather than in ``core.artifact`` for a dependency
#: reason and a design reason. The dependency reason: ``core.artifact`` imports
#: this module, so the reverse import would be a cycle. The design reason: the
#: marker's whole purpose is to be REFUSED, and this is the module that refuses
#: it. A marker defined next to what produces it is documentation; a marker
#: defined next to what rejects it is a gate.
ALLOW_DIRTY_KEY = "allow_dirty_read"


class FabricationError(RuntimeError):
    """Raised when a check tries to report a value it did not measure."""


class UncommittedRead(FabricationError):
    """Raised when a value read from the working tree is offered as a verdict.

    A subclass of ``FabricationError`` on purpose: quoting a number that is in
    nobody's git history is the same failure as quoting one nobody measured.
    Both are figures a reader cannot go and check, and the reason a reader
    cannot check them is the only thing that differs.

    ``docs/ESCALATIONS.md`` E-M12 is the case that named this: a fleet row read
    out of an untracked, gitignored working-tree file. The instrument recorded
    the fact in a provenance column and printed the number anyway.
    """


class VerdictSealed(FabricationError):
    """Raised when a verdict that has already been decided is edited.

    A subclass of ``FabricationError`` for the same reason ``UncommittedRead``
    is: the output is a figure nobody measured. Here the figure is the verdict
    itself.

    ``__post_init__`` below holds this package's most load-bearing invariants,
    and until 2026-08-31 it held them exactly once, at construction. Measured
    at 8517341 with the module's own ``__file__`` asserted::

        r = CheckResult.failed("R99", "phase-1", "a real failure")
        r.status = Status.PASS      # succeeded
        r.evidence = {}             # succeeded
        r.to_dict()["status"]       # 'PASS'

    The guard was not weak. It was in the wrong place on the timeline.

    ``measurement.Measured`` met this defect from the other side
    (``measurement.py:100,293``) and repaired it by RE-VALIDATING on
    assignment. That is right there and wrong here: re-validation only refuses
    states that are structurally illegal, so a FAIL carrying evidence flipped
    to a PASS carrying the same evidence re-validates cleanly and is still a
    forged verdict. A ``CheckResult`` is the record of one measurement that
    already happened, so the answer is a seal, not a re-check.
    """


#: Fields that ARE the verdict. Sealed the moment construction finishes: there
#: is no legitimate reason for any of them to change afterwards, and a
#: re-measurement is a new CheckResult rather than an edit to an old one.
_VERDICT_FIELDS = frozenset(
    {"check_id", "phase", "status", "reason", "evidence", "measured_at"}
)

#: Fields the RUNNER applies after construction, because the check that formed
#: the verdict does not know them -- ``cli.py:117-119`` and ``:134-136``. They
#: are writable once, from unset to a value. Re-stamping an already-stamped
#: result with a DIFFERENT value is refused: a result relabelled onto another
#: repo or another SHA is a different claim about a different tree.
_STAMP_FIELDS = frozenset({"repo", "git_sha", "nonce"})

#: The attribute that records whether construction finished. It is not a field
#: of the verdict, but it decides whether the verdict's fields are guarded, so
#: it is refused on the same terms (E-M21). Named once, here, because both
#: :class:`SealedEvidence` and :class:`CheckResult` have to refuse it and two
#: spellings of one attribute name is one of them silently not refusing.
_SEAL_FLAG = "_sealed"


class SealedEvidence(dict):
    """The evidence of a constructed result: readable, and closed to mutation.

    A seal that refused only ``r.evidence = {}`` would be defeated by
    ``r.evidence.clear()`` -- the same state, reached through a method call
    ``__setattr__`` never sees. ``measurement.py`` states that residual as OPEN
    for its own metrics dict; this closes it for ``CheckResult``.

    It is a ``dict`` subclass rather than a ``MappingProxyType`` so that
    ``isinstance(evidence, dict)``, ``json.dumps`` and ``dataclasses.asdict``
    all keep working across the eight repos that read it.

    The seal is one level deep, and that limit is deliberate and disclosed:
    ``evidence["curve"][0.25] = 9`` edits a plain dict the caller put inside.
    Deep-freezing arbitrary evidence would change the type of every nested
    structure the fleet stores, which is a blast radius this repair did not
    measure. What is closed is the verdict: no nested edit can change
    ``status``, add or remove a top-level evidence key, or turn an
    empty-evidence result into a passing one. Pinned by
    ``tests/test_result_sealed.py::test_residual_a_nested_evidence_value_is_still_mutable_in_place``,
    which fails the day the residual closes.
    """

    __slots__ = ("_sealed",)

    def seal(self) -> SealedEvidence:
        object.__setattr__(self, "_sealed", True)
        return self

    def __setattr__(self, name: str, value: Any) -> None:
        """Refuse ordinary assignment to the flag that decides the refusals.

        E-M21. Every mutating method above asks ``_sealed`` whether to refuse,
        and until 2026-08-31 nothing asked who was allowed to answer: this class
        declares ``__slots__ = ("_sealed",)`` and inherited ``dict``'s
        ``__setattr__``, so ``evidence._sealed = False`` re-opened the mapping
        and ``evidence["forged"] = True`` then landed. A guard whose caller can
        clear its own precondition is not a guard.

        :meth:`seal` and the copy hooks use ``object.__setattr__``, so the
        legitimate path is unaffected.
        """
        if name == _SEAL_FLAG and getattr(self, _SEAL_FLAG, False):
            raise VerdictSealed(
                "refusing to assign '_sealed' on the evidence of a CheckResult "
                "whose verdict has already been formed. This flag is what every "
                "refusal in this mapping reads; clearing it is not an edit to "
                "the evidence, it is an edit to whether the evidence can be "
                "edited. Re-measure and build a new CheckResult."
            )
        super().__setattr__(name, value)

    def _refuse(self, operation: str) -> None:
        if getattr(self, "_sealed", False):
            raise VerdictSealed(
                f"refusing {operation}: this evidence belongs to a CheckResult "
                "whose verdict has already been formed. A PASS rests on what was "
                "measured, and editing the measurement afterwards leaves a record "
                "that reads as though the edited figure is what the check saw. "
                "Re-measure and build a new CheckResult."
            )

    def __setitem__(self, key: Any, value: Any) -> None:
        self._refuse(f"evidence[{key!r}] = {value!r}")
        super().__setitem__(key, value)

    def __delitem__(self, key: Any) -> None:
        self._refuse(f"del evidence[{key!r}]")
        super().__delitem__(key)

    def clear(self) -> None:
        self._refuse("evidence.clear()")
        super().clear()

    def pop(self, *args: Any) -> Any:
        self._refuse("evidence.pop(...)")
        return super().pop(*args)

    def popitem(self) -> Any:
        self._refuse("evidence.popitem()")
        return super().popitem()

    def setdefault(self, *args: Any) -> Any:
        self._refuse("evidence.setdefault(...)")
        return super().setdefault(*args)

    def update(self, *args: Any, **kwargs: Any) -> None:
        self._refuse("evidence.update(...)")
        super().update(*args, **kwargs)

    def __ior__(self, other: Any) -> SealedEvidence:
        self._refuse("evidence |= ...")
        return super().__ior__(other)  # type: ignore[return-value]

    # `copy`'s generic reconstruction restores the ``_sealed`` slot BEFORE it
    # replays the items, so a sealed instance refuses its own reconstruction
    # and `copy.deepcopy(a_result)` raises. Both hooks below rebuild the
    # mapping first and seal after, and the clone keeps the seal: a copy of a
    # formed verdict is still a formed verdict, and a copy that could be edited
    # would be the escape hatch this class exists to close.
    def __copy__(self) -> SealedEvidence:
        clone = SealedEvidence(dict(self))
        return clone.seal() if getattr(self, "_sealed", False) else clone

    def __deepcopy__(self, memo: dict[int, Any]) -> SealedEvidence:
        clone = SealedEvidence(
            {k: _copy.deepcopy(v, memo) for k, v in self.items()}
        )
        return clone.seal() if getattr(self, "_sealed", False) else clone


class CredentialRequired(RuntimeError):
    """Raised by a repo binding whose only remaining obstacle is a credential.

    A binding raises this ONLY after it has done everything it can without the
    key: imported cleanly, built its request, and reached the point where the
    credential is consumed. Raising it earlier -- to dodge a check that would
    have failed for some other reason -- converts a real defect into apparent
    progress, which is the exact failure this status was added to avoid.

    Args:
        credential: the environment variable or secret name, e.g. "CDSAPI_KEY".
        detail: what was attempted, and what will happen once the key exists.
        evidence: measurements taken before the credential boundary was hit.
    """

    def __init__(
        self,
        credential: str,
        detail: str = "",
        evidence: dict[str, Any] | None = None,
    ) -> None:
        self.credential = credential
        self.detail = detail
        self.evidence = evidence or {}
        super().__init__(f"{credential} required: {detail}" if detail else f"{credential} required")


@dataclass
class CheckResult:
    """One check, run once, against one repo at one git SHA."""

    check_id: str
    phase: str
    status: Status
    reason: str = ""
    #: Measured values only. Anything in here must have been produced by code
    #: in this process, not copied from a doc, a paper, or a memory.
    evidence: dict[str, Any] = field(default_factory=dict)
    repo: str = ""
    git_sha: str = ""
    nonce: str = ""
    measured_at: str = ""

    def __post_init__(self) -> None:
        # Open the seal explicitly for the duration of construction, and take a
        # FRESH unsealed copy of the evidence. Both matter: a caller may hand
        # in another result's already-sealed evidence mapping (the R2/T2
        # delegation in checks.readiness does exactly this), and without the
        # fresh copy `_is_sealed()` would read that inherited seal and refuse
        # this object's own construction. Copying also means a caller's dict,
        # mutated later, cannot reach a formed verdict.
        object.__setattr__(self, "_sealed", False)
        object.__setattr__(self, "evidence", SealedEvidence(dict(self.evidence)))
        if isinstance(self.status, str):
            self.status = Status(self.status)
        # Redact before anything else can read, print or persist this.
        if self.reason:
            self.reason = redact(self.reason)
        if self.status in _REASON_REQUIRED and not self.reason.strip():
            raise FabricationError(
                f"{self.check_id}: status {self.status} requires a reason. "
                "Writing an unexplained non-pass is how a portfolio table starts "
                "lying about its own coverage."
            )
        if self.status is Status.PASS and not self.evidence:
            raise FabricationError(
                f"{self.check_id}: PASS requires evidence. A pass with nothing "
                "measured behind it is indistinguishable from a fabricated one."
            )
        if self.status is Status.PASS and self.evidence.get(ALLOW_DIRTY_KEY):
            raise UncommittedRead(
                f"{self.check_id}: PASS may not rest on an --allow-dirty read. The "
                "evidence descends from working-tree bytes that are not in git at "
                "HEAD, so nobody can fetch what this passed on. Commit the "
                "artifact and re-measure, or report NA with the reason."
            )
        if not self.measured_at:
            self.measured_at = _dt.datetime.now(_dt.UTC).isoformat(
                timespec="seconds"
            )
        # Everything above is the verdict being formed. From here on it is a
        # record of a measurement that happened, and a record that can be
        # edited is a record of nothing.
        self.evidence.seal()
        object.__setattr__(self, "_sealed", True)

    def _is_sealed(self) -> bool:
        """Whether this result's verdict has been formed.

        ONE signal, set at the end of ``__post_init__``, deliberately.

        A two-signal version was written and MEASURED, and it is not here: it
        also treated "the evidence mapping is sealed" as proof of construction,
        so that ``del r.__dict__["_sealed"]`` could not re-open the object. It
        broke the R2/T2 delegation in ``checks.readiness:195``, which
        constructs a new CheckResult from ANOTHER result's evidence -- the
        dataclass ``__init__`` assigns ``evidence`` before ``measured_at``, so
        the inherited seal was live while the new object was still being built
        and refused its own construction. Six tests went red. The variant that
        survives that ordering needs a second conjunct on ``measured_at``, and
        subtle correctness inside a guard is its own defect class.

        E-M21 (verifier, 2026-08-31): the paragraph below USED TO SAY that the
        only defeats were ``__dict__`` surgery, and that the ordinary-assignment
        accident was closed. That was wrong and was measured wrong. ``_sealed``
        is neither a verdict field nor a runner stamp, so ``r._sealed = False``
        fell through ``__setattr__`` to ``object.__setattr__`` -- one ordinary
        assignment, in the same syntax as the accident, and strictly cheaper
        than either disclosed defeat -- after which ``r.status = Status.PASS``
        landed. ``SealedEvidence`` had the same hole one layer down. Both are
        now refused BY NAME, before any other clause, and the fix is one
        attribute name rather than a second signal: it does not read the
        evidence mapping's seal, so it does not resurrect the R2/T2 ordering
        break described above.

        What the two-signal version bought was raising the price of one
        ``__dict__`` reach to two. Both are ``__dict__`` surgery, which defeats
        this exactly as it defeats every frozen dataclass in this package --
        ``core.served``'s own frozen types call ``object.__setattr__`` in their
        ``__post_init__``. That is a stated limit of Python, not a hole this
        class can close, and it is a LOUD limit: nothing edits a verdict that
        way by accident, and accident is what the seal exists to stop
        (``result.status = Status.PASS``, one ordinary assignment, in a check
        module -- which now refuses). Disclosed and pinned in
        ``tests/test_result_sealed.py::test_residual_e_dict_surgery_defeats_the_seal_as_it_defeats_frozen``.
        That pin is unchanged: all three ``__dict__`` paths still land, and
        they are still the stated limit. What changed is that the list is now
        accurate -- the E-M21 pins next to it hold the ordinary-assignment
        spelling closed, so "``__dict__`` surgery" is the whole residual rather
        than the part of it somebody happened to try.
        """
        return self.__dict__.get("_sealed") is True

    def __setattr__(self, name: str, value: Any) -> None:
        """Refuse every edit to a formed verdict; allow the runner's stamps once.

        Not a re-validation. Re-validating would refuse only states that are
        structurally illegal, and the forgery this closes is legal-looking: a
        FAIL that carries evidence, flipped to a PASS carrying the same
        evidence, satisfies every clause in ``__post_init__``. See
        :class:`VerdictSealed`.
        """
        if self._is_sealed():
            # E-M21, FIRST because it is the clause that keeps the other two
            # running. `_sealed` is neither a verdict field nor a runner stamp,
            # so it fell through to `object.__setattr__` and `r._sealed = False`
            # -- one ordinary assignment, the exact syntax of the accident this
            # seal exists to stop -- re-opened the object for `r.status =
            # Status.PASS`. Strictly cheaper than either disclosed `__dict__`
            # defeat, and it does not name the machinery it is subverting.
            if name == _SEAL_FLAG:
                raise VerdictSealed(
                    f"{self.__dict__.get('check_id', '?')}: refusing to assign "
                    f"'{_SEAL_FLAG}' on a {self.__dict__.get('status')} result "
                    "that has already been formed. This flag is what the seal "
                    "reads to decide whether to refuse; clearing it is not an "
                    "edit to the verdict, it is an edit to whether the verdict "
                    "can be edited. Re-measure and build a new CheckResult."
                )
            if name in _VERDICT_FIELDS:
                raise VerdictSealed(
                    f"{self.__dict__.get('check_id', '?')}: refusing to assign "
                    f"{name!r} on a {self.__dict__.get('status')} result that has "
                    "already been formed. A verdict is the output of a "
                    "measurement, not a field to be corrected afterwards; "
                    "re-measure and build a new CheckResult."
                )
            if name in _STAMP_FIELDS:
                current = self.__dict__.get(name, "")
                if current and current != value:
                    raise VerdictSealed(
                        f"{self.__dict__.get('check_id', '?')}: refusing to "
                        f"re-stamp {name!r} from {current!r} to {value!r}. This "
                        "result was measured against one repo at one SHA; "
                        "relabelling it onto another is a different claim about a "
                        "tree nobody ran it on."
                    )
        object.__setattr__(self, name, value)

    # -- constructors -----------------------------------------------------
    # Named constructors exist so that call sites read as claims, and so that
    # the reason argument is never optional where it matters.

    @classmethod
    def passed(
        cls, check_id: str, phase: str, evidence: dict[str, Any], reason: str = ""
    ) -> CheckResult:
        return cls(check_id, phase, Status.PASS, reason, evidence)

    @classmethod
    def failed(
        cls,
        check_id: str,
        phase: str,
        reason: str,
        evidence: dict[str, Any] | None = None,
    ) -> CheckResult:
        return cls(check_id, phase, Status.FAIL, reason, evidence or {})

    @classmethod
    def na(
        cls,
        check_id: str,
        phase: str,
        reason: str,
        evidence: dict[str, Any] | None = None,
    ) -> CheckResult:
        """Not measurable here, and here is why.

        NA is the correct output when the environment cannot support the
        measurement -- no data pulled, no GPU, no credentials. It is never the
        correct output for "the check would have failed".
        """
        return cls(check_id, phase, Status.NA, reason, evidence or {})

    @classmethod
    def deferred(
        cls,
        check_id: str,
        phase: str,
        credential: str,
        detail: str,
        evidence: dict[str, Any] | None = None,
    ) -> CheckResult:
        """Wired and exercised; stops at a credential the signatory will supply.

        Not a pass, and never counted as one. What it asserts is narrow and
        checkable: this code path runs, and the only thing between it and real
        data is a key. ``evidence`` must record what was exercised, so that a
        DEFERRED cannot be used as a silent skip.
        """
        evidence = dict(evidence or {})
        evidence.setdefault("credential", credential)
        evidence["deferred"] = True
        return cls(
            check_id,
            phase,
            Status.DEFERRED,
            f"wired; awaiting {credential} — {detail}" if detail else f"wired; awaiting {credential}",
            evidence,
        )

    @classmethod
    def escalated(
        cls,
        check_id: str,
        phase: str,
        reason: str,
        evidence: dict[str, Any] | None = None,
    ) -> CheckResult:
        """Reserved to a human signatory. Drives AWAITING-SIGNOFF."""
        return cls(check_id, phase, Status.ESCALATED, reason, evidence or {})

    # -- serialisation ----------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return {
            "check_id": self.check_id,
            "phase": self.phase,
            "status": self.status.value,
            "reason": self.reason,
            # A COPY. The record hands out what it measured; it does not hand
            # out the thing it measured it into. A reader that edits its own
            # dict has edited its own dict.
            "evidence": dict(self.evidence),
            "repo": self.repo,
            "git_sha": self.git_sha,
            "nonce": self.nonce,
            "measured_at": self.measured_at,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> CheckResult:
        return cls(
            check_id=d["check_id"],
            phase=d["phase"],
            status=Status(d["status"]),
            reason=d.get("reason", ""),
            evidence=d.get("evidence", {}),
            repo=d.get("repo", ""),
            git_sha=d.get("git_sha", ""),
            nonce=d.get("nonce", ""),
            measured_at=d.get("measured_at", ""),
        )


class GateAggregateError(FabricationError):
    """Raised when a gate verdict is claimed over checks that cannot support it."""


@dataclass(frozen=True)
class GateAggregate:
    """Many checks, one gate verdict — DERIVED, and stored nowhere.

    WHY THIS TYPE EXISTS
    --------------------
    Every repo in the fleet needs to say "did the gate pass", and every repo
    that needed it hand-rolled it. The measured instance is
    ``resilient-fray/src/registry/promotion_gate.py``: a mutable ``GateResult``
    at ``:401``, initialised ``GateResult(passed=True)`` at ``:851`` and
    narrowed check by check with ``&=``. Three properties of that shape, each
    on its own enough:

    * the verdict starts at **True** and is argued down. A loop that fails to
      run, an exception swallowed between the initialiser and the first ``&=``,
      or a check silently skipped, all leave a PASS standing;
    * ``passed`` is a stored field, so it can be assigned. Whatever the checks
      said, ``result.passed = True`` says otherwise, and nothing downstream can
      tell the two apart;
    * ``&=`` collapses three statuses into two. NA is not PASS and it is not
      FAIL, and ``bool(NA)`` has to pick one.

    Here ``passed`` is a property over a tuple of :class:`CheckResult`. There is
    no field to assign, no initial value to leave standing, and no accumulation
    step to skip: the verdict is recomputed from the results every time it is
    asked for, and a caller holding this object cannot make it disagree with
    the checks it holds.

    **NA IS NOT PASS.** ``passed`` is ``all(status is PASS)``, not
    ``not any(status is FAIL)``. That is the readiness semantics this package
    already documents on :class:`Status`: "we could not measure it" is not
    coverage, and a gate that treats it as coverage reports readiness the repo
    does not have. DEFERRED, STALE and ESCALATED are likewise not passes.

    An aggregate over ZERO checks is refused rather than reported as True. It
    is the same vacuity ``ChallengerDecision`` refuses for ``metrics=()``
    (M-02): ``all([])`` is True, so a gate that ran nothing passes everything.
    """

    gate: str
    results: tuple[CheckResult, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "results", tuple(self.results))
        if not str(self.gate).strip():
            raise GateAggregateError(
                "a gate aggregate must name the gate it is the verdict of; an "
                "unnamed verdict cannot be attributed to anything"
            )
        if not self.results:
            raise GateAggregateError(
                f"gate {self.gate!r} aggregates no check. `all([])` is True, so a "
                "verdict over an empty check set is a pass nobody measured -- the "
                "same vacuity ChallengerDecision refuses for an empty metric set."
            )
        wrong = [r for r in self.results if not isinstance(r, CheckResult)]
        if wrong:
            raise GateAggregateError(
                f"gate {self.gate!r} aggregates {[type(r).__name__ for r in wrong]}; "
                "this verdict is derived from CheckResults, and a bare bool or dict "
                "in the set is a verdict somebody formed elsewhere and posted in"
            )
        seen: dict[str, int] = {}
        for r in self.results:
            seen[r.check_id] = seen.get(r.check_id, 0) + 1
        repeated = sorted(cid for cid, n in seen.items() if n > 1)
        if repeated:
            raise GateAggregateError(
                f"gate {self.gate!r} carries {repeated} more than once. Two results "
                "for one check id are two answers to one question, and which one "
                "the verdict rests on would depend on iteration order."
            )

    @property
    def passed(self) -> bool:
        """True only when EVERY check passed. Derived; there is no field."""
        return all(r.status is Status.PASS for r in self.results)

    @property
    def statuses(self) -> dict[str, Status]:
        return {r.check_id: r.status for r in self.results}

    @property
    def blocking(self) -> tuple[str, ...]:
        """The check ids standing between this gate and a pass, in order."""
        return tuple(r.check_id for r in self.results if r.status is not Status.PASS)

    @property
    def counts(self) -> dict[str, int]:
        tally: dict[str, int] = {}
        for r in self.results:
            tally[r.status.value] = tally.get(r.status.value, 0) + 1
        return tally

    def result(self, check_id: str) -> CheckResult | None:
        for r in self.results:
            if r.check_id == check_id:
                return r
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "gate": self.gate,
            "passed": self.passed,
            "n_checks": len(self.results),
            "counts": self.counts,
            "blocking": list(self.blocking),
            "results": [r.to_dict() for r in self.results],
        }
