"""Check results.

The single most important invariant in this package lives here: a result may
not claim a number it did not measure, and it may not be unmeasured without
saying why. Both are enforced structurally in ``__post_init__`` rather than by
convention, because convention is exactly what fails under deadline pressure.
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
    """The five terminal statuses a check may report.

    There is deliberately no ``SKIP`` and no ``WARN``. A check either measured
    something and formed a verdict (PASS/FAIL), could not measure and says why
    (NA), measured against a different tree than the one checked out (STALE),
    or is reserved to a human signatory (ESCALATED).
    """

    PASS = "PASS"
    FAIL = "FAIL"
    NA = "NA"
    STALE = "STALE"
    ESCALATED = "ESCALATED"

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.value


#: Statuses that must carry a human-readable reason. A bare "NA" is worse than
#: no check at all: it looks like coverage and carries no information.
_REASON_REQUIRED = {Status.FAIL, Status.NA, Status.STALE, Status.ESCALATED}


class FabricationError(RuntimeError):
    """Raised when a check tries to report a value it did not measure."""


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
        if not self.measured_at:
            self.measured_at = _dt.datetime.now(_dt.timezone.utc).isoformat(
                timespec="seconds"
            )

    # -- constructors -----------------------------------------------------
    # Named constructors exist so that call sites read as claims, and so that
    # the reason argument is never optional where it matters.

    @classmethod
    def passed(
        cls, check_id: str, phase: str, evidence: dict[str, Any], reason: str = ""
    ) -> "CheckResult":
        return cls(check_id, phase, Status.PASS, reason, evidence)

    @classmethod
    def failed(
        cls,
        check_id: str,
        phase: str,
        reason: str,
        evidence: dict[str, Any] | None = None,
    ) -> "CheckResult":
        return cls(check_id, phase, Status.FAIL, reason, evidence or {})

    @classmethod
    def na(
        cls,
        check_id: str,
        phase: str,
        reason: str,
        evidence: dict[str, Any] | None = None,
    ) -> "CheckResult":
        """Not measurable here, and here is why.

        NA is the correct output when the environment cannot support the
        measurement -- no data pulled, no GPU, no credentials. It is never the
        correct output for "the check would have failed".
        """
        return cls(check_id, phase, Status.NA, reason, evidence or {})

    @classmethod
    def escalated(
        cls,
        check_id: str,
        phase: str,
        reason: str,
        evidence: dict[str, Any] | None = None,
    ) -> "CheckResult":
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
    def from_dict(cls, d: dict[str, Any]) -> "CheckResult":
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
