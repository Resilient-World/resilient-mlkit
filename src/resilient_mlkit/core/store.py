"""Result persistence and staleness.

A check result is only meaningful against the tree it was measured on. Storing
the git SHA alongside every result is what lets ``mlkit`` distinguish "this
passed" from "this passed, three commits ago, before you touched the loader".
The second one is STALE, and the readiness gate treats it as not passing.
"""

from __future__ import annotations

import json
from pathlib import Path

from .repo import Repo
from .result import CheckResult, Status


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
    out: list[CheckResult] = []
    for raw in (payload.get("results") or {}).values():
        result = CheckResult.from_dict(raw)
        out.append(_stale_if_moved(result, current))
    return out


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
