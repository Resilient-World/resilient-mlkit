#!/usr/bin/env python3
"""Does every committed champion pin in the fleet still reproduce its own digest?

WHY THIS EXISTS
---------------
The refactor's prime directive is that behaviour must not change. For a served
model the behaviour that must not change is its IDENTITY: every committed
champion record in the fleet carries a sha256 that its own repo's local hashing
produced. If mlkit's contract computed that digest even slightly differently --
a different separator, a different key ordering, ``allow_nan`` left at its
default -- then adopting the contract would make those records fail their own
load-time check, and the fix would look like "update the recorded hash", which
is exactly how a provenance chain gets quietly rewritten.

So this asserts the identity directly, recomputing each digest with
``resilient_mlkit.core.served`` and comparing it to the hash the record already
carries. No repo module is imported and no repo file is modified; this reads
JSON, reads bytes, and runs read-only ``git`` commands.

TWO KINDS OF PIN, AND WHY THEY ARE NOT THE SAME PROPERTY
--------------------------------------------------------
This script used to accept exactly one shape: a JSON under ``models/`` with a
**top-level** ``artifact_sha256``. Three repos pin their champion in a shape it
could not see, and each was therefore rendered ``NA`` with the reason *"this
repo serves nothing hash-pinned yet"* -- a claim about the repo that the
scanner had not measured and that was, for all three, false:

* ``resilient-arabica`` ``models/yield_model_of_record/model.json``
* ``resilient-torrent``  ``models/hydrology_ridge/model.json``
* ``resilient-surge``    ``data/model_registry/per_lead_anchor_ols/model.json``
  -- under a root this script never visited at all.

Both shapes are now discovered, and they are labelled and counted separately,
because they assert different things and collapsing them would overstate the
weaker one:

``canonical_self_hash``
    The record hashes ITSELF: a top-level ``artifact_sha256`` over the record's
    own canonical JSON with the hash field excluded. Tamper with any field and
    the record stops verifying. Checked with ``canonical_payload_sha256``.

``sidecar_coefficient_digest``
    The record pins a DIFFERENT FILE's bytes: a top-level ``artifact`` object
    carrying ``path`` and ``sha256``. Checked with ``sha256_file`` over the
    bytes at that path. This is strictly weaker -- the coefficients cannot be
    swapped without detection, but the record wrapped around them is itself
    unpinned, so its metrics, splits and provenance prose can be edited freely
    without any digest moving. The report says which kind each row is so that a
    reader cannot mistake the second for the first.

Only the TOP-LEVEL ``artifact`` object is followed. Digests nested deeper --
torrent's ``committed_val_row.artifact_sha256``, for instance -- are a
different claim about a different file and are deliberately not swept in here.

WHERE IT LOOKS
--------------
``models/`` and ``data/model_registry/`` in the repo's own checkout. If the
checkout yields nothing, linked worktrees are searched in ``git worktree
list`` order and the first tree that yields candidates answers, with the tree
recorded on every row it produced. ``core/artifact.py`` documents the same
convention and the reason for it: several repos keep the branch carrying their
measurements in a linked worktree, and reporting "serves nothing" for those
would be true of one checkout and false about the repo. A row sourced
off-checkout is evidence about that worktree and is flagged.

Authorization: A-1 -- local CPU, no cloud, no GPU, no spend. Nothing is fitted.

Usage:
    python scripts/verify_served_hash_parity.py [--root DIR] [--out FILE]

Exit code 0 when every artifact compared reproduced, 2 otherwise, and 2 also
when nothing was compared at all: a parity report over nothing that prints
green is the defect this script exists to catch, applied to the script.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from resilient_mlkit import __version__
from resilient_mlkit.core import identity as identity_mod
from resilient_mlkit.core.repo import PORTFOLIO, find_root
from resilient_mlkit.core.served import (
    HASH_KEY,
    canonical_payload_sha256,
    sha256_file,
)

#: Directories that hold a checkout's scratch copies rather than its tree. A
#: worktree carries a byte-identical duplicate of the same artifact, which would
#: inflate the count without adding evidence.
SKIP_PARTS = frozenset({".git", ".venv", "node_modules", ".worktrees", "__pycache__"})

#: Where a champion record may live. ``models/`` was the only one, which is why
#: resilient-surge -- whose registry is at the second -- was never visited.
ARTIFACT_ROOTS = ("models", "data/model_registry")

#: The record hashes itself. Strongest form: no field can be edited undetected.
KIND_SELF = "canonical_self_hash"
#: The record pins another file's bytes. Weaker: the record itself is unpinned.
KIND_SIDECAR = "sidecar_coefficient_digest"

#: What the two kinds mean, carried in the report so a reader does not have to
#: come back to this file to know whether a MATCH pinned the record or only its
#: coefficients.
KIND_MEANS = {
    KIND_SELF: (
        f"top-level {HASH_KEY} over the record's own canonical JSON with the hash "
        "field excluded; recomputed with core.served.canonical_payload_sha256. "
        "Every field of the record is covered by this digest."
    ),
    KIND_SIDECAR: (
        "top-level artifact.sha256 over the bytes of the separate file at "
        "artifact.path; recomputed with core.served.sha256_file. WEAKER than a "
        "self-hash: the coefficients cannot be swapped undetected, but the record "
        "wrapped around them carries no digest of itself, so its metrics, splits "
        "and provenance prose can be edited without this digest moving."
    ),
}


@dataclass(frozen=True)
class Candidate:
    """One champion record found on disk, with the shape it pins in."""

    path: Path
    kind: str
    payload: dict


def git_sha(path: Path) -> str:
    out = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "HEAD"],
        capture_output=True, text=True, check=False,
    )
    return out.stdout.strip() if out.returncode == 0 else ""


def git_branch(path: Path) -> str:
    out = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True, text=True, check=False,
    )
    return out.stdout.strip() if out.returncode == 0 else ""


def linked_worktrees(repo: Path) -> list[Path]:
    """Every linked worktree of ``repo``, excluding the root checkout itself."""
    out = subprocess.run(
        ["git", "-C", str(repo), "worktree", "list", "--porcelain"],
        capture_output=True, text=True, check=False,
    )
    if out.returncode != 0:
        return []
    root = repo.resolve()
    found: list[Path] = []
    for line in out.stdout.splitlines():
        if not line.startswith("worktree "):
            continue
        candidate = Path(line[len("worktree "):]).resolve()
        if candidate != root and candidate.is_dir():
            found.append(candidate)
    return found


def classify(payload: object) -> str | None:
    """Which pin shape this document carries, or None if it carries neither.

    Order matters only in that a document carrying both would be reported as a
    self-hash, which is the stronger and therefore the more demanding claim to
    hold it to.
    """
    if not isinstance(payload, dict):
        return None
    if payload.get(HASH_KEY):
        return KIND_SELF
    artifact = payload.get("artifact")
    if isinstance(artifact, dict) and artifact.get("sha256") and artifact.get("path"):
        return KIND_SIDECAR
    return None


def scan_tree(tree: Path) -> list[Candidate]:
    """Every champion record under ``tree``'s artifact roots, in path order."""
    found: list[Candidate] = []
    for root in ARTIFACT_ROOTS:
        base = tree / root
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*.json")):
            # Relative to the tree being scanned, never the absolute path. The
            # absolute form silently defeated the worktree fallback: a linked
            # worktree at `<repo>/.worktrees/<name>` has ".worktrees" in every
            # descendant's parts, so every candidate inside it was skipped and
            # the repo rendered NA -- the same vanishing this script is being
            # fixed to stop doing.
            if SKIP_PARTS & set(path.relative_to(tree).parts):
                continue
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            kind = classify(payload)
            if kind:
                found.append(Candidate(path=path, kind=kind, payload=payload))
    return found


def locate(repo: Path) -> tuple[list[Candidate], Path, str]:
    """Candidates, the tree they came from, and the worktree marker for the rows.

    The repo's own checkout answers if it can. Only if it yields nothing at all
    is a linked worktree consulted -- so a worktree can add evidence where there
    was none and can never shadow or duplicate the checkout's own.
    """
    own = scan_tree(repo)
    if own:
        return own, repo, ""
    for tree in linked_worktrees(repo):
        found = scan_tree(tree)
        if found:
            return found, tree, str(tree)
    return [], repo, ""


def compare(candidate: Candidate, tree: Path) -> dict[str, object]:
    """One row: the digest the record carries beside the digest recomputed now.

    A sidecar whose referenced file is not on disk is ``NA``, never ``MATCH``
    and never ``DIFFER``. An unresolvable pin is unmeasured -- it is not equal
    to the bytes and it is not different from them, because there are no bytes.
    """
    row: dict[str, object] = {
        "artifact": str(candidate.path.relative_to(tree)),
        "kind": candidate.kind,
    }
    if candidate.kind == KIND_SELF:
        recorded = str(candidate.payload[HASH_KEY])
        recomputed = canonical_payload_sha256(candidate.payload)
        row.update({
            "pins": "this record's own canonical JSON",
            "verified_with": "core.served.canonical_payload_sha256",
            "recorded_sha256": recorded,
            "recomputed_sha256": recomputed,
            "status": "MATCH" if recorded == recomputed else "DIFFER",
        })
        return row

    artifact = candidate.payload["artifact"]
    relpath = str(artifact["path"])
    recorded = str(artifact["sha256"])
    referenced = tree / relpath
    row.update({
        "pins": relpath,
        "verified_with": "core.served.sha256_file",
        "recorded_sha256": recorded,
    })
    if not referenced.is_file():
        row.update({
            "status": "NA",
            "reason": (
                f"the record pins {relpath} and no file is there under {tree}; the "
                "digest is unresolvable, which is unmeasured rather than unequal"
            ),
        })
        return row
    recomputed = sha256_file(referenced)
    row.update({
        "recomputed_sha256": recomputed,
        "referenced_bytes": referenced.stat().st_size,
        "status": "MATCH" if recorded == recomputed else "DIFFER",
    })
    return row


def no_candidate_reason(repo: Path) -> str:
    """What is true when the search found nothing: what was searched, not a verdict.

    The old text was "this repo serves nothing hash-pinned yet", which is a
    claim about the repo. This scanner does not measure that. It measures what
    it looked for and did not find, and that is all it now says.
    """
    return (
        "no JSON under "
        + " or ".join(f"{r}/" for r in ARTIFACT_ROOTS)
        + f" -- in the checkout or any linked worktree -- carries a top-level "
        f"{HASH_KEY} or a top-level artifact object with both path and sha256. "
        "This states what was searched for and not found; it is not a finding "
        "about what the repo serves"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=None)
    parser.add_argument(
        "--out", type=Path, default=REPO_ROOT / "reports" / "served_hash_parity.json"
    )
    args = parser.parse_args(argv)

    root = args.root or find_root(REPO_ROOT)
    rows: list[dict[str, object]] = []
    for name in PORTFOLIO:
        repo = root / f"resilient-{name}"
        if not repo.is_dir():
            rows.append({
                "repo": name,
                "status": "NA",
                "reason": f"resilient-{name} is not checked out under {root}",
            })
            continue
        candidates, tree, marker = locate(repo)
        if not candidates:
            rows.append({
                "repo": name,
                "git_sha": git_sha(repo),
                "branch": git_branch(repo),
                "status": "NA",
                "reason": no_candidate_reason(repo),
            })
            continue
        for candidate in candidates:
            row: dict[str, object] = {
                "repo": name,
                "git_sha": git_sha(tree),
                "branch": git_branch(tree),
            }
            row.update(compare(candidate, tree))
            if marker:
                row["worktree"] = marker
                row["scope_note"] = (
                    "sourced from a linked worktree, not the repo's checked-out "
                    "branch; this row is evidence about that worktree"
                )
            rows.append(row)

    compared = [r for r in rows if r["status"] in {"MATCH", "DIFFER"}]
    matched = [r for r in compared if r["status"] == "MATCH"]
    differed = [r for r in compared if r["status"] == "DIFFER"]
    unresolvable = [r for r in rows if r["status"] == "NA" and "artifact" in r]

    by_kind = {
        kind: {
            "compared": sum(1 for r in compared if r.get("kind") == kind),
            "matched": sum(1 for r in matched if r.get("kind") == kind),
            "differed": sum(1 for r in differed if r.get("kind") == kind),
            "unresolvable": sum(1 for r in unresolvable if r.get("kind") == kind),
            "means": KIND_MEANS[kind],
        }
        for kind in (KIND_SELF, KIND_SIDECAR)
    }

    report = {
        "report_type": "served_hash_parity",
        "question": (
            "does resilient_mlkit.core.served reproduce every committed champion pin "
            "in the fleet -- canonical_payload_sha256 for a record that hashes "
            "itself, sha256_file for a record that pins a separate coefficient "
            "file's bytes?"
        ),
        "generated_at": datetime.now(UTC).isoformat(),
        "mlkit_version": __version__,
        "mlkit_git_sha": git_sha(REPO_ROOT),
        # E-M24: which mlkit produced this parity verdict. `mlkit_version` is
        # equal across builds whose core/served.py differs by 386 lines, and
        # this script's whole subject is what core/served.py computes.
        "mlkit_build": identity_mod.build_identity().to_dict(),
        "python": sys.version.split()[0],
        "portfolio_root": str(root),
        "searched_roots": list(ARTIFACT_ROOTS),
        "artifacts_compared": len(compared),
        "matched": len(matched),
        "differed": len(differed),
        "unresolvable_pins": len(unresolvable),
        "by_kind": by_kind,
        "rows": rows,
        "note": (
            "The two kinds are counted separately and must not be added together as "
            "though they asserted the same thing: a canonical_self_hash covers every "
            "field of the record, a sidecar_coefficient_digest covers only the file "
            "it points at and leaves the record itself unpinned. Duplicates inside "
            ".worktrees are excluded from a tree's own scan; a linked worktree is "
            "consulted only when the checkout yields nothing, so it can add evidence "
            "and never inflate a count. An NA states what was searched for and not "
            "found -- it is not a finding about what a repo serves."
        ),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    for row in rows:
        detail = row.get("artifact", row.get("reason", ""))
        kind = f"  [{row['kind']}]" if row.get("kind") else ""
        print(f"{row['status']:>6}  {row['repo']:<12} {detail}{kind}")
    print(
        f"\ncompared {len(compared)}; matched {len(matched)}; "
        f"differed {len(differed)}; unresolvable {len(unresolvable)}"
    )
    for kind, counts in by_kind.items():
        print(f"  {kind:<28} compared {counts['compared']}  matched {counts['matched']}"
              f"  differed {counts['differed']}  unresolvable {counts['unresolvable']}")
    print(f"wrote {args.out}", file=sys.stderr)

    if not compared:
        print(
            "NO ARTIFACT COMPARED — this is not a pass. Parity is unmeasured.",
            file=sys.stderr,
        )
        return 2
    return 0 if not differed and not unresolvable else 2


if __name__ == "__main__":
    raise SystemExit(main())
