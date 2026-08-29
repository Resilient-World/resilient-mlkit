#!/usr/bin/env python3
"""Propagate the canonical spine into the eight model repos.

The spine is authored once in ``resilient-mlkit/spine/`` and synced outward.
Editing the copy inside a model repo is a mistake -- the next sync reverts it --
so every synced file carries a CANONICAL banner saying where it came from.

Safety rule this script will not break: **it never overwrites a file it did not
write.** A file that exists without the CANONICAL marker is reported as a
collision and left exactly as it is. Several repos ship a hand-written
NOTICE.md and a docs/ tree with real content in it, and silently replacing any
of that would destroy work to satisfy a scaffolding step.

Usage:
    python scripts/sync_spine.py [--root DIR] [--repo a,b] [--dry-run]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# The declaration of what "canonical" means lives in the package, so that this
# script and `mlkit spine` cannot disagree about it. Two definitions of
# canonical is the same as none.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from resilient_mlkit.core.repo import PORTFOLIO as REPOS
from resilient_mlkit.core.spine import CANONICAL_FILES, SEED_FILES
from resilient_mlkit.core.spine import has_banner as _has_banner


def is_ours(path: Path) -> bool:
    """True when we may overwrite an existing canonical file at ``path``."""
    try:
        return _has_banner(path.read_text(errors="ignore"))
    except OSError:
        return False


def sync_repo(
    spine: Path, repo_root: Path, name: str, dry_run: bool
) -> tuple[int, int, int, list[str]]:
    written = skipped = seeded = 0
    collisions: list[str] = []

    for src_rel, dest_rel in CANONICAL_FILES:
        src = spine / src_rel
        dest = repo_root / dest_rel
        content = src.read_text()

        if dest.exists():
            if not is_ours(dest):
                collisions.append(dest_rel)
                continue
            if dest.read_text() == content:
                skipped += 1
                continue
        if not dry_run:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(content)
        written += 1

    for src_rel, dest_rel in SEED_FILES:
        dest = repo_root / dest_rel
        if dest.exists():
            skipped += 1
            continue
        content = (spine / src_rel).read_text()
        if dest_rel == ".mlkit/repo.toml":
            content = content.replace('name = "REPLACE_ME"', f'name = "{name}"')
        if not dry_run:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(content)
        seeded += 1

    # mlkit results are local measurement state bound to a git SHA. Committing
    # them would move HEAD and instantly mark them stale, so they stay ignored.
    if not dry_run:
        gitignore = repo_root / ".gitignore"
        existing = gitignore.read_text() if gitignore.exists() else ""
        if ".mlkit/results/" not in existing:
            suffix = "" if existing.endswith("\n") or not existing else "\n"
            gitignore.write_text(
                existing + suffix + "\n# mlkit local measurement state (SHA-bound)\n.mlkit/results/\n"
            )

    return written, skipped, seeded, collisions


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=None, help="directory holding the resilient-* checkouts")
    parser.add_argument("--repo", default=None, help="comma-separated subset")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    here = Path(__file__).resolve().parent.parent
    spine = here / "spine"
    root = Path(args.root).resolve() if args.root else here.parent
    names = [r.strip() for r in args.repo.split(",")] if args.repo else list(REPOS)

    total_collisions = 0
    for name in names:
        repo_root = root / f"resilient-{name}"
        if not repo_root.is_dir():
            print(f"{name:<11} MISSING at {repo_root}")
            continue
        written, skipped, seeded, collisions = sync_repo(spine, repo_root, name, args.dry_run)
        note = f"{written} canonical, {seeded} seeded, {skipped} unchanged"
        if collisions:
            note += f", {len(collisions)} COLLISION: {', '.join(collisions)}"
            total_collisions += len(collisions)
        print(f"{name:<11} {note}")

    if total_collisions:
        print(
            f"\n{total_collisions} file(s) already existed and were not authored by this "
            "script. They were left untouched — reconcile them by hand.",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
