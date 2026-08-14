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
    except json.JSONDecodeError:
        return []

    current = repo.git_sha
    out: list[CheckResult] = []
    for raw in (payload.get("results") or {}).values():
        result = CheckResult.from_dict(raw)
        if result.status is Status.PASS and result.git_sha and current:
            if result.git_sha != current:
                result = CheckResult(
                    check_id=result.check_id,
                    phase=result.phase,
                    status=Status.STALE,
                    reason=(
                        f"measured at {result.git_sha[:7]}, HEAD is now {current[:7]}; "
                        "re-run to revalidate"
                    ),
                    evidence=result.evidence,
                    repo=result.repo,
                    git_sha=result.git_sha,
                    nonce=result.nonce,
                    measured_at=result.measured_at,
                )
        out.append(result)
    return out


def load_all(repo: Repo, phases: tuple[str, ...]) -> dict[str, CheckResult]:
    """Every stored result for a repo across phases, keyed by check id."""
    merged: dict[str, CheckResult] = {}
    for phase in phases:
        for result in load(repo, phase):
            merged[result.check_id] = result
    return merged
