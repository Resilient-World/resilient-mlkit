"""Result persistence and staleness.

A check result is only meaningful against the tree it was measured on. Storing
the git SHA alongside every result is what lets ``mlkit`` distinguish "this
passed" from "this passed, three commits ago, before you touched the loader".
The second one is STALE, and the readiness gate treats it as not passing.

THE INSTRUMENT IS THE OTHER HALF OF THAT SENTENCE (E-M24 residual)
------------------------------------------------------------------
A result is meaningful against the tree it was measured on **and the mlkit
that measured it**, and only the first was recorded here. E-M24 stamped every
report mlkit *writes*; this file holds the verdicts mlkit *keeps*, and
``mlkit check --portfolio`` renders a full readiness table out of them —
``R(9-12,1-8) PPPPPPPPPPPP  READY-TO-TRAIN`` — with the exit code ``README.md``
says CI gates on.

Measured 2026-09-01, two package trees differing by one byte in
``checks/readiness.py``: 27 PASSes were written by build
``0.5.0+src.b1686b22efc6`` and, at an unchanged repo SHA, read back by build
``0.5.0+src.48480b572359`` as live PASSes, rendering ``READY-TO-TRAIN`` at
exit 0. Nothing in the table, the store, or the exit code named either build.
That is exactly the finding E-M24 records — "readiness under whichever mlkit
happened to be installed, and nothing says which" — in the one readiness table
the stamping pass did not reach.

So the build identity is stored beside the git SHA and checked on read, by the
same rule and for the same reason: a PASS that cannot be tied to the
instrument in front of us is STALE, including a PASS from before this was
recorded at all. A FAIL is never staled — an older instrument's failure is
still a reason to look.
"""

from __future__ import annotations

import json
from pathlib import Path

from . import identity
from .repo import Repo
from .result import CheckResult, Status

#: Payload key holding the stamp of the mlkit build that measured the results
#: in the file. One constant, read by the writer and the reader.
BUILD_KEY = "mlkit_build"


def _results_path(repo: Repo, phase: str) -> Path:
    return repo.path / ".mlkit" / "results" / f"{phase}.json"


def save(repo: Repo, phase: str, results: list[CheckResult]) -> Path:
    """Write results for one phase, keyed by check id."""
    path = _results_path(repo, phase)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "repo": repo.name,
        "phase": phase,
        "git_sha": repo.git_sha,
        # Which mlkit produced these verdicts (E-M24 residual). Written at
        # file level rather than per result because every result in one file
        # comes from one process, and a per-result copy would be a second
        # place for the same fact to disagree with itself.
        BUILD_KEY: identity.build_identity().stamp,
        "results": {r.check_id: r.to_dict() for r in results},
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return path


def load(repo: Repo, phase: str) -> list[CheckResult]:
    """Read stored results for a phase, marking anything measured at another SHA STALE.

    Staleness is computed on read rather than on write, because the tree can
    move underneath a stored result at any time and the only moment that
    matters is when someone asks.
    """
    path = _results_path(repo, phase)
    if not path.is_file():
        return []
    try:
        payload = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        # A corrupt results file must not read as "not yet run". That would
        # turn data loss into apparent absence of work, which is the quietest
        # possible way to lose a failure.
        return [
            CheckResult.failed(
                cid, phase,
                f"stored results at {path.name} are unreadable ({exc}); re-run this phase",
            )
            for cid in _expected_ids(phase)
        ]

    current = repo.git_sha
    stored_build = payload.get(BUILD_KEY)
    installed_build = identity.build_identity().stamp
    out: list[CheckResult] = []
    for raw in (payload.get("results") or {}).values():
        result = CheckResult.from_dict(raw)
        result = _stale_if_moved(result, current)
        out.append(_stale_if_instrument_moved(result, stored_build, installed_build))
    return out


def _stale_if_instrument_moved(
    result: CheckResult, stored: object, installed: str
) -> CheckResult:
    """Mark a PASS STALE when it cannot be tied to the mlkit in front of us.

    Three cases, and the third is the one E-M24 is about:

    * the file records no build at all — written before this was recorded, or
      by something that is not ``save()``. Staled for the same reason a result
      with no git SHA is staled: it cannot be tied to anything;
    * the mlkit running here cannot name its own identity (split package,
      unreadable tree). No equality may be asserted from an unknown operand,
      so no PASS may be carried forward on one;
    * the builds are both known and different. ``0.5.0+src.b1686b22efc6``
      measured it and ``0.5.0+src.48480b572359`` is asking — two builds whose
      ``checks/readiness.py`` differs and whose ``__version__`` does not.

    Only PASS and ESCALATED are staled, matching :func:`_stale_if_moved`
    exactly: a FAIL measured by an older instrument is still a reason to look,
    and hiding it behind STALE would be strictly worse than reporting it.
    """
    if result.status not in (Status.PASS, Status.ESCALATED):
        return result

    unknown_here = installed.endswith(identity.UNKNOWN_DIGEST)
    if isinstance(stored, str) and stored and stored == installed and not unknown_here:
        return result

    if not isinstance(stored, str) or not stored:
        reason = (
            "stored results record no mlkit build, so this result cannot be tied "
            f"to the instrument that produced it (installed: {installed}); re-run"
        )
    elif unknown_here:
        reason = (
            f"the result was measured by mlkit {stored}, and the mlkit installed "
            "here cannot name its own identity, so the two cannot be compared; "
            "re-run"
        )
    else:
        reason = (
            f"measured by mlkit {stored}, the mlkit installed here is "
            f"{installed}; the gate source differs between builds that declare "
            "the same version (E-M24), so this verdict is not this instrument's; "
            "re-run"
        )
    return CheckResult(
        check_id=result.check_id,
        phase=result.phase,
        status=Status.STALE,
        reason=reason,
        evidence=result.evidence,
        repo=result.repo,
        git_sha=result.git_sha,
        nonce=result.nonce,
        measured_at=result.measured_at,
    )


def _stale_if_moved(result: CheckResult, current: str) -> CheckResult:
    """Mark a result STALE when it cannot be tied to the tree in front of us.

    Two cases, and the second is the one that bites: an explicit SHA mismatch,
    and a result with no SHA at all. The latter happens outside a git worktree
    or when `git` fails, and treating it as valid lets a PASS survive arbitrary
    changes to the code it supposedly measured.
    """
    # Only statuses that read as progress are staled. A FAIL from an older SHA
    # is still a reason to look, and hiding it behind STALE would be worse.
    if result.status not in (Status.PASS, Status.ESCALATED):
        return result

    if result.git_sha and current and result.git_sha == current:
        return result

    if not result.git_sha or not current:
        reason = (
            "result carries no git SHA (not a git worktree, or git failed), so it "
            "cannot be tied to the tree being checked; re-run"
        )
    else:
        reason = (
            f"measured at {result.git_sha[:7]}, HEAD is now {current[:7]}; "
            "re-run to revalidate"
        )
    return CheckResult(
        check_id=result.check_id,
        phase=result.phase,
        status=Status.STALE,
        reason=reason,
        evidence=result.evidence,
        repo=result.repo,
        git_sha=result.git_sha,
        nonce=result.nonce,
        measured_at=result.measured_at,
    )


def _expected_ids(phase: str) -> list[str]:
    from ..checks import PHASE_ORDER

    return PHASE_ORDER.get(phase, [])


def load_all(repo: Repo, phases: tuple[str, ...]) -> dict[str, CheckResult]:
    """Every stored result for a repo across phases, keyed by check id."""
    merged: dict[str, CheckResult] = {}
    for phase in phases:
        for result in load(repo, phase):
            merged[result.check_id] = result
    return merged
