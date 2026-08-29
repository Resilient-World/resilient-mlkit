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
            "evidence": self.evidence,
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
