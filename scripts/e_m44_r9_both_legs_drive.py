"""Drive E-M44's control arms and write ``reports/E_M44_R9_BOTH_LEGS_ARMS.json``.

The subject is one ``return``. ``r9_licence_gate`` owns two licence
obligations -- no unlisted or wrongly-licensed source in the manifest, AND
every attribution obligation rendered into ``NOTICE.md`` -- and it returned on
the first, so the second was unreachable on any repo that had a manifest
finding. On 2026-09-07 that was hiding undischarged attribution obligations in
three of the four repos that had them.

Every arm builds a throwaway repository, runs R9 against it in a
**subprocess**, and records the status and the reason. Subprocesses because
arm **N9** needs ``checks/readiness.py`` and ``core/policy.py`` from a
DIFFERENT revision, and because each arm can then assert, in its own
interpreter, that ``resilient_mlkit.__file__`` resolves inside the tree the arm
names -- exit 9 otherwise. An editable install otherwise serves one tree to
every arm and the drive reports agreement having measured one thing N times.

ARMS, fixed in ``reports/E_M43_M44_GATE_DEFECT_PREREGISTRATION.md`` §2 before
any of them was driven:

==== ==================================================== ==========================
arm   fixture                                              required
==== ==================================================== ==========================
N1    BLOCKED source + stale NOTICE                        FAIL, BOTH clauses
N2    BLOCKED source + current NOTICE                      FAIL, reason identical to main's
N3    clean manifest + stale NOTICE                        FAIL (not WARN, not NA)
N4    clean manifest + current NOTICE                      PASS
N5    defective entry + stale NOTICE (the surge shape)      FAIL, BOTH clauses
N6    manifest binding raises + stale NOTICE               FAIL, and says the leg was not measured
N7    manifest binding raises + current NOTICE             NA, reason identical to main's
N8    NOTICE.md absent, obligations exist                  FAIL, names the obligations
N9    NOT-DEAD: readiness.py + policy.py at --not-dead-rev N1/N5 lose the NOTICE clause, N6 is NA
==== ==================================================== ==========================

N2 and N7 are the arms that stop the repair from being a widening. A check that
grew a new way to fail has to be shown NOT failing everything else it touches,
and byte-identical is the only version of that claim worth making.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from resilient_mlkit.core import policy

#: Modules the NOT-DEAD arm takes from another revision. Both, not just
#: `readiness.py`: `policy.notice_gap` is new here, so a tree with the old
#: check and the new policy would be a mixture nobody ships.
NOT_DEAD_MODULES = ("checks/readiness.py", "core/policy.py")

#: Run one R9 against one repo and print its result as JSON. Kept as source
#: text rather than a module so the arm's interpreter imports nothing from this
#: checkout except the package tree the arm names.
DRIVE = """
import json, pathlib, sys
import resilient_mlkit as m
want = pathlib.Path(sys.argv[1]).resolve()
got = pathlib.Path(m.__file__).resolve()
if want not in got.parents:
    sys.exit(9)
from resilient_mlkit import checks as checks_pkg
from resilient_mlkit.checks import RunContext
from resilient_mlkit.checks.readiness import r9_licence_gate
from resilient_mlkit.core.repo import Repo
checks_pkg.load_all()
repo = Repo(name="fixturerepo", path=pathlib.Path(sys.argv[2]))
ctx = RunContext(nonce="ARM0000000", root=pathlib.Path(sys.argv[2]).parent, offline=True)
r = r9_licence_gate(repo, ctx)
print(json.dumps({"status": r.status.value, "reason": r.reason,
                  "evidence_keys": sorted(r.evidence)}))
"""

ATTRIBUTION = "Contains modified Copernicus Sentinel data, fixture text"


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True)


def _entry(source_id: str, status: str = "ALLOWED", **extra: object) -> dict:
    return {
        "id": source_id, "kind": "data", "status": status,
        "licence_url": "https://example.invalid/licence",
        "retrieval_date": "2026-09-07", "attribution": ATTRIBUTION,
        **extra,
    }


def build_repo(
    base: Path,
    *,
    entries: list[dict],
    sources: list[str],
    notice: str | None = "generated",
    binding: str | None = None,
) -> Path:
    """A committed fixture repo: allowlist, manifest, and a NOTICE.md.

    ``notice="generated"`` writes what `render_notice` produces, ``None``
    writes no file, and any other string is written verbatim as a stale one.
    ``binding`` declares a ``manifest`` binding instead of a manifest path --
    pass a module that does not exist to reproduce the shape three fleet repos
    have under an interpreter missing their dependencies.
    """
    root = base / "resilient-fixturerepo"
    (root / ".mlkit").mkdir(parents=True)
    (root / "docs").mkdir(parents=True)
    (root / "manifest.yaml").write_text(
        "sources:\n" + "".join(f"  - {s}\n" for s in sources)
    )
    config = '[repo]\nname = "fixturerepo"\n\n'
    config += (
        f'[bindings]\nmanifest = "{binding}"\n' if binding
        else '[manifest]\npath = "manifest.yaml"\n'
    )
    (root / ".mlkit" / "repo.toml").write_text(config)

    parsed = {
        e["id"]: policy.Entry(
            id=str(e["id"]), kind=str(e["kind"]), status=str(e["status"]),
            licence_url=str(e["licence_url"]), retrieval_date=str(e["retrieval_date"]),
            attribution=str(e["attribution"]),
        )
        for e in entries
    }
    lines = ["entries:"]
    for e in entries:
        lines.append(f"  - id: {e['id']}")
        for f in ("kind", "status", "licence_url", "retrieval_date", "attribution"):
            lines.append(f"    {f}: {json.dumps(e[f])}")
    lines += [
        "signature:",
        "  signed: true",
        "  signed_by: signatory@example.invalid",
        '  signed_at: "2026-09-07"',
        f'  entries_sha256: "{policy.entries_digest(parsed)}"',
    ]
    (root / policy.ALLOWLIST_RELPATH).write_text("\n".join(lines) + "\n")

    _git(base, "init", "-q", str(root))
    _git(root, "config", "user.email", "t@example.invalid")
    _git(root, "config", "user.name", "t")
    # COMMIT THE ALLOWLIST FIRST. `_verify_signature` refuses a signature over
    # a file with uncommitted changes, so rendering the NOTICE against a
    # working-tree allowlist produces the UNSIGNED provisional trailer and the
    # "generated" arms come out stale -- a fixture defect that would have read
    # as the check firing everywhere.
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "fixture")

    if notice is not None:
        from resilient_mlkit.core.repo import Repo

        repo = Repo(name="fixturerepo", path=root)
        allowlist = policy.load(repo)
        text = policy.render_notice(repo, allowlist) if notice == "generated" else notice
        (root / policy.NOTICE_RELPATH).write_text(text)
        _git(root, "add", "-A")
        _git(root, "commit", "-qm", "notice")
    return root


#: The NOTICE a "stale" arm writes. Hand-edited, with no `## <id>` section, so
#: the obligation it drops is nameable rather than merely "the bytes differ".
STALE_NOTICE = "# NOTICE\n\nhand-edited, and no longer what the allowlist says\n"


def _materialise(dst: Path, *, from_rev: str | None) -> Path:
    shutil.copytree(REPO_ROOT / "src" / "resilient_mlkit", dst / "resilient_mlkit")
    if from_rev:
        for relpath in NOT_DEAD_MODULES:
            blob = subprocess.run(
                ["git", "-C", str(REPO_ROOT), "show",
                 f"{from_rev}:src/resilient_mlkit/{relpath}"],
                capture_output=True, text=True, check=True,
            ).stdout
            target = dst / "resilient_mlkit" / relpath
            if target.read_text() == blob:
                raise SystemExit(
                    f"REFUSED: {relpath} at {from_rev} is identical to this tree's; "
                    "the NOT-DEAD arm would revert nothing"
                )
            target.write_text(blob)
    for cache in (dst / "resilient_mlkit").rglob("__pycache__"):
        shutil.rmtree(cache, ignore_errors=True)
    return dst


def _drive(tree: Path, repo: Path) -> dict:
    proc = subprocess.run(
        [sys.executable, "-c", DRIVE, str(tree), str(repo)],
        capture_output=True, text=True, check=False,
        env={"PYTHONPATH": str(tree), "PATH": "/usr/bin:/bin", "HOME": str(Path.home())},
    )
    if proc.returncode == 9:
        raise SystemExit(
            "REFUSED: resilient_mlkit does not resolve inside the named tree; "
            "every arm would measure another checkout"
        )
    if proc.returncode != 0:
        raise SystemExit(f"REFUSED: the arm crashed:\n{proc.stderr[-2000:]}")
    return json.loads(proc.stdout)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--not-dead-rev", default="origin/main")
    ap.add_argument("--out", default=str(REPO_ROOT / "reports" / "E_M44_R9_BOTH_LEGS_ARMS.json"))
    args = ap.parse_args()

    arms: list[dict] = []
    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        live = _materialise(tmpdir / "tree-live", from_rev=None)
        dead = _materialise(tmpdir / "tree-not-dead", from_rev=args.not_dead_rev)

        fixtures = {
            "N1": {"entries": [_entry("blocked-panel", "BLOCKED")],
                   "sources": ["blocked-panel"], "notice": STALE_NOTICE},
            "N2": {"entries": [_entry("blocked-panel", "BLOCKED")],
                   "sources": ["blocked-panel"], "notice": "generated"},
            "N3": {"entries": [_entry("sentinel2-l2a")],
                   "sources": ["sentinel2-l2a"], "notice": STALE_NOTICE},
            "N4": {"entries": [_entry("sentinel2-l2a")],
                   "sources": ["sentinel2-l2a"], "notice": "generated"},
            "N5": {"entries": [_entry("code-not-data", kind="code")],
                   "sources": ["code-not-data"], "notice": STALE_NOTICE},
            "N6": {"entries": [_entry("sentinel2-l2a")], "sources": ["sentinel2-l2a"],
                   "notice": STALE_NOTICE,
                   "binding": "no_module_by_this_name_for_the_arm:manifest"},
            "N7": {"entries": [_entry("sentinel2-l2a")], "sources": ["sentinel2-l2a"],
                   "notice": "generated",
                   "binding": "no_module_by_this_name_for_the_arm:manifest"},
            "N8": {"entries": [_entry("sentinel2-l2a")],
                   "sources": ["sentinel2-l2a"], "notice": None},
        }
        required = {
            "N1": "FAIL, and the reason carries BOTH legs",
            "N2": "FAIL, reason byte-identical to the not-dead tree's",
            "N3": "FAIL — not a warning, and not NA",
            "N4": "PASS",
            "N5": "FAIL, both legs, past a structurally invalid allowlist",
            "N6": "FAIL, naming the NOTICE gap and saying the manifest leg was not measured",
            "N7": "NA, reason byte-identical to the not-dead tree's",
            "N8": "FAIL, NOTICE.md absent, obligations named",
        }

        built: dict[str, Path] = {}
        for name, kw in fixtures.items():
            base = tmpdir / name.lower()
            base.mkdir()
            built[name] = build_repo(base, **kw)  # type: ignore[arg-type]

        for name, repo in built.items():
            got = _drive(live, repo)
            arms.append({
                "arm": name, "tree": "live", "required": required[name],
                "status": got["status"], "reason": got["reason"],
                "names_the_missing_ids": "sentinel2-l2a" in got["reason"]
                or "blocked-panel" in got["reason"] or "code-not-data" in got["reason"],
            })

        # N9 — NOT-DEAD. The same fixtures, the pre-E-M44 check.
        for name in ("N1", "N2", "N5", "N6", "N7"):
            got = _drive(dead, built[name])
            arms.append({
                "arm": f"N9-{name}", "tree": "not-dead",
                "required": "the NOTICE leg is invisible; N6 is NA",
                "status": got["status"], "reason": got["reason"],
                "mentions_notice": "NOTICE" in got["reason"],
            })

    payload = {
        "preregistration": "reports/E_M43_M44_GATE_DEFECT_PREREGISTRATION.md",
        "escalation": "E-M44",
        "subject": "r9_licence_gate returned before the NOTICE leg it also owns",
        "not_dead_rev_label": args.not_dead_rev,
        "not_dead_modules": list(NOT_DEAD_MODULES),
        "arms": arms,
    }
    Path(args.out).write_text(json.dumps(payload, indent=1, sort_keys=True) + "\n")
    print(f"{len(arms)} arms -> {args.out}")
    for a in arms:
        print(f"  {a['arm']:8s} {a['status']:10s} {a['reason'][:110]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
