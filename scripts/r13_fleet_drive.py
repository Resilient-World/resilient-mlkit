"""Drive R13 (QUOTED RULE PARITY) on named adopter worktrees, and on a merged tree.

The M-2 drive of record. Reads NOTHING from a working tree that a binding
would read; R13 imports nothing from the repo, so a bare interpreter is the
right interpreter here. Every figure printed is the check's own evidence.

Usage::

    python scripts/r13_fleet_drive.py --tree fray=/path/to/fray-main ... \
        --merged torrent=/path/to/torrent-clone:cec1c48:5052c71 --out reports/R13_FLEET_DRIVE.json

``--merged NAME=PATH:HEAD:BASE`` builds the merge of HEAD with BASE through
``core.merged`` (the M-3 machinery: synthetic commit, temporary worktree,
refused on conflict), drives R13 on it, and removes the worktree. The historical
E-069 case is ``torrent=<clone>:cec1c48:5052c71``.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import sys
from pathlib import Path

import resilient_mlkit
from resilient_mlkit.checks import RunContext
from resilient_mlkit.checks.parity import r13_quoted_rule_parity
from resilient_mlkit.core import identity, merged
from resilient_mlkit.core.repo import Repo


def _assert_this_checkout() -> str:
    here = Path(__file__).resolve().parents[1] / "src"
    at = Path(resilient_mlkit.__file__).resolve()
    if not at.is_relative_to(here):
        raise SystemExit(f"resilient_mlkit imported from {at}, not from {here}; refusing to drive")
    return str(at)


def _drive(name: str, path: Path, label: str) -> dict:
    repo = Repo(name, path)
    ctx = RunContext(nonce="r13-fleet-drive", root=path.parent, offline=True)
    result = r13_quoted_rule_parity(repo, ctx)
    ev = dict(result.evidence)
    return {
        "label": label,
        "repo": name,
        "path": str(path),
        "git_sha": repo.git_sha,
        "status": result.status.value,
        "reason": result.reason,
        "files_scanned": ev.get("files_scanned"),
        "findings": ev.get("findings", []),
        "registered_sites": ev.get("registered_sites", []),
        "enforcement_sites": ev.get("enforcement_sites", []),
        "artifact_counts": ev.get("artifact_counts", {}),
        "superseded_clauses": ev.get("superseded_clauses", []),
        "clauses": ev.get("clauses", []),
        "claude_md_sha256": ev.get("claude_md_sha256"),
    }


def _partial_merge(clone: Path, base: str, head: str) -> merged.MergedTree:
    """git's partial merge tree, conflict markers and all; nothing resolved."""
    import subprocess

    def git(*a: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(["git", "-C", str(clone), *a], capture_output=True, text=True, check=False)

    head_sha = merged.resolve_ref(clone, head)
    base_sha = merged.resolve_ref(clone, base)
    head_tree = git("rev-parse", f"{head_sha}^{{tree}}").stdout.strip()
    out = git("merge-tree", "--write-tree", "--name-only", base_sha, head_sha)
    tree = out.stdout.splitlines()[0].strip()
    commit = git(
        "commit-tree", tree, "-p", head_sha, "-p", base_sha,
        "-m", f"r13 drive: PARTIAL merge of {head} with {base}; conflicts left unresolved",
    ).stdout.strip()
    return merged.MergedTree(clone, head_sha, head_tree, base, base_sha, tree, commit)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tree", action="append", default=[], metavar="NAME=PATH")
    ap.add_argument("--merged", action="append", default=[], metavar="NAME=PATH:HEAD:BASE")
    ap.add_argument("--out", help="write the JSON record here")
    ap.add_argument("--out-md", help="render the record as markdown here (generated; never hand-edit)")
    args = ap.parse_args(argv)

    mlkit_at = _assert_this_checkout()
    rows: list[dict] = []
    for spec in args.tree:
        name, _, path = spec.partition("=")
        rows.append(_drive(name, Path(path).resolve(), f"{name}@{Path(path).name}"))
    for spec in args.merged:
        name, _, rest = spec.partition("=")
        path, head, base = rest.split(":")
        clone = Path(path).resolve()
        try:
            m = merged.build(clone, base, head)
            conflicted: list[str] = []
        except merged.MergeConflict as exc:
            # The historical pair (torrent cec1c48 + 5052c71) conflicts on
            # .gitignore -- the conflict the landers resolved "as a union" by
            # hand (STATE.md 2026-09-04). mlkit REFUSES to resolve it, and this
            # drive does not either: it checks out git's PARTIAL merge tree
            # with the conflict markers left in place, records the conflicted
            # paths, and drives R13 -- which never reads .gitignore -- on it.
            # Any conflicted path R13 WOULD read makes this reproduction
            # invalid, and that is checked below rather than assumed.
            conflicted = list(exc.paths)
            readable = {p for p in conflicted if not p.endswith(".gitignore")}
            if readable:
                raise SystemExit(
                    f"historical merge {head}+{base} conflicts in {sorted(readable)}, "
                    "which R13 may read; refusing to drive a partial tree"
                )
            m = _partial_merge(clone, base, head)
        wt = merged.checkout(m)
        try:
            row = _drive(name, wt, f"{name}@merge({head}+{base})")
        finally:
            merged.remove(m, wt)
        row["merged_tree"] = {**m.stamp(), "conflicted_paths_left_unresolved": conflicted}
        rows.append(row)

    record = {
        "artifact_schema": "resilient-mlkit/r13-fleet-drive/1",
        "generated_by": "scripts/r13_fleet_drive.py",
        "generated_at_utc": _dt.datetime.now(_dt.UTC).isoformat(timespec="seconds"),
        "mlkit_version": resilient_mlkit.__version__,
        "mlkit_build": identity.build_identity().to_dict(),
        "mlkit_file": mlkit_at,
        "rows": rows,
    }
    for row in rows:
        print(f"== {row['label']}  sha={row['git_sha'][:12]}  R13 {row['status']}  "
              f"files={row['files_scanned']}  findings={len(row['findings'])}  "
              f"registered={len(row['registered_sites'])}  enforcement={len(row['enforcement_sites'])}  "
              f"artifacts={row['artifact_counts']}")
        for f in row["findings"]:
            print(f"   FINDING {f['kind']} {f['path']}:{f['line']} [{f['clause']}] \"{f['window']}\"")
        for f in row["registered_sites"]:
            print(f"   registered {f['kind']} {f['path']}:{f['line']} [{f['clause']}]")
        for f in row["enforcement_sites"]:
            print(f"   enforcement {f['kind']} {f['path']}:{f['line']} [{f['clause']}]")
        print(f"   superseded: {[(c['marker'], c['source'][:12]) for c in row['superseded_clauses']]}")
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(record, indent=1) + "\n")
        print(f"wrote {out}", file=sys.stderr)
    if args.out_md:
        out_md = Path(args.out_md)
        out_md.parent.mkdir(parents=True, exist_ok=True)
        out_md.write_text(render_markdown(record))
        print(f"wrote {out_md}", file=sys.stderr)
    return 0


def render_markdown(record: dict) -> str:
    lines = [
        "# R13 QUOTED_RULE_PARITY — fleet drive",
        "",
        "**Generated by `scripts/r13_fleet_drive.py`. Do not hand-edit; re-run the script.**",
        "",
        f"- generated: `{record['generated_at_utc']}`",
        f"- mlkit: `{record['mlkit_version']}` build `{record['mlkit_build'].get('stamp', 'NA')}`",
        "",
        "| tree | sha | R13 | files | findings | registered | enforcement | artifacts tied/untied/stale |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for row in record["rows"]:
        ac = row["artifact_counts"] or {}
        lines.append(
            f"| {row['label']} | `{row['git_sha'][:12]}` | **{row['status']}** | {row['files_scanned']} | "
            f"{len(row['findings'])} | {len(row['registered_sites'])} | {len(row['enforcement_sites'])} | "
            f"{ac.get('tied', 0)}/{ac.get('untied', 0)}/{ac.get('stale', 0)} |"
        )
    lines.append("")
    for row in record["rows"]:
        lines += [f"## {row['label']} — `{row['git_sha']}`", ""]
        mt = row.get("merged_tree")
        if mt:
            lines.append(
                f"- merged tree: head `{mt['head_sha'][:12]}` + base `{mt['base_ref']}@{mt['base_sha'][:12]}` "
                f"→ tree `{mt['merge_tree'][:12]}`; conflicted paths left unresolved: "
                f"{mt.get('conflicted_paths_left_unresolved') or 'none'}"
            )
        lines.append(f"- CLAUDE.md sha256 `{(row.get('claude_md_sha256') or 'NA')[:16]}…`; "
                     f"superseded clauses: {[(c['marker'], c['source'][:12]) for c in row['superseded_clauses']]}")
        lines.append(f"- reason: {row['reason'] or 'measured; no quotation on the verdict surface'}")
        for f in row["findings"]:
            lines.append(f"- **FINDING** `{f['kind']}` `{f['path']}:{f['line']}` [{f['clause']}] — \"{f['window']}\"")
        for f in row["registered_sites"]:
            lines.append(f"- registered (disclosed by the S-5 register, not failing) `{f['kind']}` `{f['path']}:{f['line']}` [{f['clause']}]")
        for f in row["enforcement_sites"]:
            lines.append(f"- enforcement (the register's own scanner) `{f['kind']}` `{f['path']}:{f['line']}` [{f['clause']}]")
        lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
