"""What the spine is, and whether the eight repos still have it.

The spine is authored once in ``resilient-mlkit/spine/`` and synced outward by
``scripts/sync_spine.py``. Every canonical file carries a ``CANONICAL`` banner
saying where it came from, because editing the copy inside a model repo is a
mistake the next sync silently reverts.

This module holds the DECLARATION -- which files are canonical, which are seeds,
what the banner is -- so that the syncer and the drift check cannot disagree
about it. Two definitions of "canonical" is the same as none, which is the
lesson R7 already paid for in the model repos.

REPORT-ONLY
-----------
Nothing here writes into a model repo. Drift is a fact to report, and the
decision to overwrite eight repos from this one is a decision, not a
side effect of running a check. ``sync_spine.py`` remains the only thing that
writes, and it still refuses to overwrite a file it did not author.
"""

from __future__ import annotations

import difflib
import hashlib
from dataclasses import dataclass
from pathlib import Path

#: The banner every canonical file carries. Its ABSENCE is what tells the
#: syncer a file is hand-written and must not be overwritten.
MARKER = "CANONICAL"

#: How much of a file is searched for the banner. Matches the syncer.
MARKER_WINDOW = 4000

#: Authored in the spine, overwritten on every sync. ``(spine path, repo path)``.
CANONICAL_FILES: tuple[tuple[str, str], ...] = (
    ("CLAUDE.md", "CLAUDE.md"),
    ("docs/DATA_POLICY.md", "docs/DATA_POLICY.md"),
    ("docs/SELECTION.md", "docs/SELECTION.md"),
    ("docs/READINESS.md", "docs/READINESS.md"),
    ("docs/DECISION_VALIDITY.md", "docs/DECISION_VALIDITY.md"),
    ("docs/RUN_ECONOMICS.md", "docs/RUN_ECONOMICS.md"),
)

#: Written once if absent, then owned by the repo and NEVER overwritten.
#: Escalations and blockers accumulate per repo, repo.toml gains that repo's
#: bindings, and the allowlist gains determinations a human signed -- treating
#: any of these as canonical would revert exactly the work that matters most.
SEED_FILES: tuple[tuple[str, str], ...] = (
    ("docs/ESCALATIONS.md", "docs/ESCALATIONS.md"),
    ("docs/BLOCKERS.md", "docs/BLOCKERS.md"),
    ("docs/allowlist.yaml", "docs/allowlist.yaml"),
    ("mlkit/repo.toml", ".mlkit/repo.toml"),
)

# -- verdicts ------------------------------------------------------------

#: Deployed copy is byte-identical to the spine.
IN_SYNC = "IN-SYNC"
#: Deployed copy carries the banner but its bytes have moved away from the spine.
DRIFTED = "DRIFTED"
#: No deployed copy at all. The repo has never been synced, or it was deleted.
ABSENT = "ABSENT"
#: A file exists at the destination WITHOUT the banner. The syncer refuses to
#: touch it, so it is not drift -- it is a hand-written file occupying a
#: canonical filename, which is a different and more permanent problem.
UNCLAIMED = "UNCLAIMED"
#: The spine itself has no such file. An adapter-side defect, reported as one.
NO_SPINE_SOURCE = "NO-SPINE-SOURCE"


@dataclass(frozen=True)
class FileDrift:
    """One canonical file, in one repo."""

    repo: str
    relpath: str
    verdict: str
    spine_sha256: str = ""
    deployed_sha256: str = ""
    #: Number of changed lines (added + removed) between spine and deployed.
    changed_lines: int = 0
    #: First few changed lines, for a reader who wants to know what moved.
    sample: tuple[str, ...] = ()
    detail: str = ""

    @property
    def clean(self) -> bool:
        return self.verdict == IN_SYNC

    def to_dict(self) -> dict[str, object]:
        return {
            "repo": self.repo,
            "relpath": self.relpath,
            "verdict": self.verdict,
            "spine_sha256": self.spine_sha256 or None,
            "deployed_sha256": self.deployed_sha256 or None,
            "changed_lines": self.changed_lines,
            "sample": list(self.sample),
            "detail": self.detail or None,
        }


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def has_banner(text: str) -> bool:
    """True when this file claims to be a synced canonical copy."""
    return MARKER in text[:MARKER_WINDOW]


def compare(
    spine_root: Path, repo_name: str, repo_root: Path, *, max_sample: int = 6
) -> list[FileDrift]:
    """Compare every canonical file in one repo against the spine. Reads only."""
    out: list[FileDrift] = []
    for src_rel, dest_rel in CANONICAL_FILES:
        src = spine_root / src_rel
        dest = repo_root / dest_rel
        if not src.is_file():
            out.append(
                FileDrift(
                    repo_name, dest_rel, NO_SPINE_SOURCE,
                    detail=f"spine/{src_rel} does not exist; there is nothing to compare against",
                )
            )
            continue
        want = src.read_text(errors="replace")
        want_sha = _sha(want)
        if not dest.is_file():
            out.append(
                FileDrift(
                    repo_name, dest_rel, ABSENT, spine_sha256=want_sha,
                    detail=f"{dest_rel} does not exist in this repo; it has never been synced here",
                )
            )
            continue
        got = dest.read_text(errors="replace")
        got_sha = _sha(got)
        if got_sha == want_sha:
            out.append(FileDrift(repo_name, dest_rel, IN_SYNC, want_sha, got_sha))
            continue
        if not has_banner(got):
            out.append(
                FileDrift(
                    repo_name, dest_rel, UNCLAIMED, want_sha, got_sha,
                    detail=(
                        f"{dest_rel} exists but carries no {MARKER} banner in its first "
                        f"{MARKER_WINDOW} characters, so sync_spine.py will not overwrite it. "
                        "This is a hand-written file on a canonical filename, not drift."
                    ),
                )
            )
            continue
        diff = [
            line
            for line in difflib.unified_diff(
                want.splitlines(), got.splitlines(), lineterm="", n=0
            )
            if line[:1] in "+-" and not line.startswith(("+++", "---"))
        ]
        out.append(
            FileDrift(
                repo_name, dest_rel, DRIFTED, want_sha, got_sha,
                changed_lines=len(diff),
                sample=tuple(line[:160] for line in diff[:max_sample]),
                detail=(
                    f"deployed copy carries the {MARKER} banner but has moved "
                    f"{len(diff)} line(s) away from spine/{src_rel}; the next "
                    "sync would revert it"
                ),
            )
        )
    return out


def summarise(drifts: list[FileDrift]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for d in drifts:
        counts[d.verdict] = counts.get(d.verdict, 0) + 1
    return counts
