"""The ``mlkit`` command line.

This is the only thing in the portfolio permitted to emit a number. Every
metric, loss, score, coverage figure and cost in a report, a commit message or
a transcript must have come out of a run of this CLI. Anything else is a claim,
and claims are what this whole apparatus exists to stop.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import socket
import subprocess
import sys
import traceback
from pathlib import Path

from . import __version__
from . import checks as checks_pkg
from .checks import PHASE_ORDER, PHASES, RunContext, for_phase
from .core import nonce as nonce_mod
from .core import policy, store
from .core.repo import PORTFOLIO, Repo, discover, find_root
from .core.result import CheckResult, CredentialRequired, Status
from .core.table import phase_table
from .portfolio import render_portfolio, resolve


def _detect_offline(timeout: float = 2.0) -> bool:
    """Cheap reachability probe.

    Checks that report NA should say "no network" rather than surfacing a
    confusing per-URL timeout, and the distinction matters when reading a
    portfolio table cold.
    """
    try:
        socket.setdefaulttimeout(timeout)
        with socket.create_connection(("1.1.1.1", 443), timeout=timeout):
            return False
    except OSError:
        return True
    finally:
        socket.setdefaulttimeout(None)


def _select_repos(args: argparse.Namespace, root: Path) -> list[Repo]:
    found = discover(root)
    if getattr(args, "repo", None):
        wanted = {r.strip() for r in args.repo.split(",")}
        unknown = wanted - set(PORTFOLIO)
        if unknown:
            raise SystemExit(f"unknown repo(s): {', '.join(sorted(unknown))}")
        found = [r for r in found if r.name in wanted]
    return found


def _run_phase(repo: Repo, phase: str, ctx: RunContext) -> list[CheckResult]:
    """Run one phase against one repo, in the phase's prescribed order."""
    results: list[CheckResult] = []
    for spec in for_phase(phase):
        try:
            result = spec.fn(repo, ctx)
        except CredentialRequired as exc:
            # A binding that got all the way to the credential boundary has
            # told us something real. Record it as DEFERRED rather than
            # letting the generic handler bury it as a crash.
            result = CheckResult.deferred(
                spec.check_id, phase, exc.credential, exc.detail, exc.evidence
            )
        except Exception:  # noqa: BLE001 - a crashing check is a failing check
            result = CheckResult.failed(
                spec.check_id,
                phase,
                f"check raised an unhandled exception:\n{traceback.format_exc(limit=4)}",
            )
        result.repo = repo.name
        result.git_sha = repo.git_sha
        result.nonce = ctx.nonce
        ctx.prior[result.check_id] = result
        results.append(result)
    return results


def cmd_check(args: argparse.Namespace) -> int:
    checks_pkg.load_all()
    root = Path(args.root).resolve() if args.root else find_root()
    run_nonce = nonce_mod.from_env_or_mint()
    offline = args.offline if args.offline is not None else _detect_offline()

    repos = _select_repos(args, root)
    if not repos:
        print(f"no portfolio repos found under {root}", file=sys.stderr)
        return 2

    if args.portfolio:
        return _cmd_portfolio(repos, run_nonce, root)

    phase = args.phase
    if phase not in PHASES:
        print(f"unknown phase {phase!r}; expected one of {', '.join(PHASES)}", file=sys.stderr)
        return 2

    print(f"mlkit {__version__}  phase={phase}  nonce={run_nonce}")
    print(f"root={root}  network={'offline' if offline else 'online'}")
    print()

    total = len(PHASE_ORDER[phase])
    agg: dict[str, int] = {}
    last_line = ""

    for repo in repos:
        ctx = RunContext(nonce=run_nonce, root=root, offline=offline, timeout=args.timeout)
        try:
            results = _run_phase(repo, phase, ctx)
        finally:
            # Drop this repo's modules before touching the next one. Every repo
            # names its adapter `mlkit_bindings`, so skipping this would serve
            # repo A's cached module to repo B and report A's numbers as B's.
            repo.release()
        store.save(repo, phase, results)

        print(f"--- resilient-{repo.name}  sha={repo.short_sha}  branch={repo.branch}"
              f"{'  DIRTY' if repo.is_dirty else ''}")
        print(phase_table(results, PHASE_ORDER[phase]))

        counts: dict[str, int] = {}
        for r in results:
            counts[r.status.value] = counts.get(r.status.value, 0) + 1
            agg[r.status.value] = agg.get(r.status.value, 0) + 1

        # Phase-specific lines the loop prompts quote verbatim as their
        # done-condition. An unsatisfiable done-condition is an invitation to
        # fabricate a transcript, so these have to be printable for real.
        if phase == "selection":
            by_id = {r.check_id: r for r in results}
            for cid, label in (("S3", "RESOLVED"), ("S4", "LICENCE-VERDICTED")):
                found = by_id.get(cid)
                if found and found.status is Status.PASS:
                    n = found.evidence.get("resolved", found.evidence.get("n_sources", 0))
                    d = found.evidence.get("total", found.evidence.get("n_sources", 0))
                elif found and found.status is Status.FAIL:
                    n = found.evidence.get("resolved", 0)
                    d = found.evidence.get("total", found.evidence.get("n_sources", 0))
                else:
                    n = d = 0
                print(f"{cid}: {n}/{d} {label}")

        n_pass = counts.get("PASS", 0)
        extra = "  ".join(f"{k}={v}" for k, v in sorted(counts.items()) if k != "PASS")
        last_line = f"{phase.upper()}: {n_pass}/{total} PASS" + (f"  {extra}" if extra else "")
        print(f"run nonce: {run_nonce}  repo: {repo.name}  sha: {repo.git_sha}")
        print(last_line)
        print()

    if len(repos) > 1:
        last_line = (
            f"{phase.upper()} ACROSS {len(repos)} REPOS: "
            + "  ".join(f"{k}={v}" for k, v in sorted(agg.items()))
            + f"  (of {total * len(repos)} checks)"
        )
        print(f"run nonce: {run_nonce}")
        print(last_line)

    # Exit codes exist so CI can gate on this. R9 is spec'd to fail the build,
    # so a FAIL must be non-zero; an incomplete run must not be green either.
    # DEFERRED is separated from NA on purpose: waiting on a key the signatory
    # will paste in is not the same failure mode as a loader that does not run,
    # and CI should be able to tell them apart without reading the table.
    if agg.get(Status.FAIL.value):
        return 1
    if agg.get(Status.NA.value) or agg.get(Status.STALE.value):
        return 3
    if agg.get(Status.DEFERRED.value) or agg.get(Status.ESCALATED.value):
        return 4
    return 0


def _cmd_portfolio(repos: list[Repo], run_nonce: str, root: Path) -> int:
    print(f"mlkit {__version__}  portfolio  nonce={run_nonce}")
    print(f"root={root}")
    print()
    states = []
    for repo in repos:
        stored = store.load_all(repo, PHASES)
        states.append(resolve(repo, stored))
    print(render_portfolio(states, run_nonce))
    print()
    for repo in repos:
        print(f"HEAD resilient-{repo.name}: {repo.git_sha or '<not a git worktree>'}")
    return 0


def cmd_fleet(args: argparse.Namespace) -> int:
    """Regenerate the MEASURED columns of the fleet verdict table.

    ``portfolio/MODEL_QUALITY.md`` is the adjudication of record and stays
    hand-written: its last column is a judgement, and a judgement is not a field
    lookup. Every OTHER column in it is a number that exists in exactly one
    other place -- an artifact in a model repo -- and was retyped into the table
    by hand. This command reads those artifacts instead, so a wrong digit stops
    being invisible.

    Every figure is read from the repo's COMMITTED state (``HEAD:<relpath>``),
    not from its working tree. An artifact that is on disk and on no ref reports
    NA naming the file, which is what ``docs/ESCALATIONS.md`` E-M12 cost when it
    did not. ``--allow-dirty`` reads the working tree for local diagnosis and
    then refuses to emit anything, exiting 2.

    Not to be confused with ``mlkit check --portfolio``, which reports each
    repo's terminal readiness state. This one reports model quality.
    """
    from .core import fleet
    from .fleet_adapters import ADAPTERS

    root = Path(args.root).resolve() if args.root else find_root()
    run_nonce = nonce_mod.from_env_or_mint()
    repos = {r.name: r for r in _select_repos(args, root)}
    if not repos:
        print(f"no portfolio repos found under {root}", file=sys.stderr)
        return 2

    allow_dirty = bool(getattr(args, "allow_dirty", False))
    rows: list[fleet.FleetRow] = []
    missing_repos: list[str] = []
    for adapter in ADAPTERS:
        repo = repos.get(adapter.repo)
        if repo is None:
            if args.repo is None and adapter.repo not in missing_repos:
                missing_repos.append(adapter.repo)
            continue
        rows.append(fleet.read_row(repo, adapter, allow_dirty=allow_dirty))

    if allow_dirty:
        return _fleet_diagnosis(rows)

    stats = fleet.counts(rows)
    generated_at = _dt.datetime.now(_dt.UTC).isoformat(timespec="seconds")
    payload = {
        "artifact_schema": "resilient-mlkit/fleet-verdicts/1",
        "generated_by": "mlkit portfolio",
        "mlkit_version": __version__,
        "generated_at_utc": generated_at,
        "run_nonce": run_nonce,
        "root": str(root),
        "mlkit_git_sha": _self_sha(),
        "repos_read": {
            name: {"git_sha": r.git_sha, "branch": r.branch, "dirty": r.is_dirty}
            for name, r in sorted(repos.items())
        },
        "repos_not_found_under_root": missing_repos,
        "counts": stats,
        "rows": [r.to_dict() for r in rows],
    }

    md = _render_fleet_markdown(payload, rows, missing_repos)

    if args.json:
        print(json.dumps(payload, indent=1, sort_keys=False))
    else:
        print(f"mlkit {__version__}  portfolio  nonce={run_nonce}")
        print(f"root={root}")
        print()
        print(md)

    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(md)
        json_path = out.with_suffix(".json")
        json_path.write_text(json.dumps(payload, indent=1) + "\n")
        print(f"\nwrote {out} and {json_path}", file=sys.stderr)

    # NA is not a failure -- an NA with a reason is a result. A row whose MAIN
    # artifact could not be found at all is different: the adapter points at
    # something that is not there, and that IS a defect in this tool.
    broken = [r.key for r in rows if r.main is not None and not r.main.found]
    if broken:
        print(f"\n{len(broken)} row(s) whose declared main artifact did not resolve: "
              f"{', '.join(broken)}", file=sys.stderr)
        return 1
    return 0


def _fleet_diagnosis(rows: list) -> int:
    """What `--allow-dirty` prints instead of a table, and why it exits 2.

    The escape hatch exists so that someone mid-way through producing an
    artifact can see what their pointers resolve to. It must not be a quieter
    way of generating the same document, so this prints cells one per line --
    deliberately NOT the table's shape, so that nothing here can be pasted
    anywhere a table is expected -- and returns non-zero.

    Same posture as `scripts/verify_served_hash_parity.py`, which exits 2 when
    it found nothing to compare: a report that cannot be trusted must not exit
    green, because exit status is what CI reads.
    """
    named = (
        ("model of record", "model_of_record"), ("candidate", "candidate"),
        ("metric", "metric"), ("split", "split"), ("score", "score"),
        ("bar", "baseline_name"), ("bar score", "baseline_score"),
        ("beats bar?", "beats"), ("test arm", "test_arm_spent"),
    )
    print("--allow-dirty: WORKING-TREE DIAGNOSIS. Not a verdict, not a table.\n")
    dirty_rows = 0
    for row in rows:
        marks = [
            f"{alias}={ref.read_from or 'not read'}"
            for alias, ref in row.artifacts.items()
        ]
        flag = "  <-- WORKING TREE" if row.allow_dirty else ""
        dirty_rows += 1 if row.allow_dirty else 0
        print(f"{row.key}  [{', '.join(marks)}]{flag}")
        for label, attr in named:
            cell = getattr(row, attr)
            print(f"    {label:<16} {cell.render()}")
        print()
    print(
        f"{dirty_rows} of {len(rows)} row(s) carry a working-tree read.\n"
        "No table, no --json payload and no --out file was written: a figure that "
        "is in nobody's git history may be looked at and may not be quoted "
        "(docs/ESCALATIONS.md E-M12). Commit the artifact and re-run without "
        "--allow-dirty.",
        file=sys.stderr,
    )
    return 2


def _self_sha() -> str:
    out = subprocess.run(
        ["git", "-C", str(Path(__file__).resolve().parent), "rev-parse", "HEAD"],
        capture_output=True, text=True, check=False,
    )
    return out.stdout.strip() if out.returncode == 0 else ""


def _render_fleet_markdown(
    payload: dict, rows: list, missing_repos: list[str]
) -> str:
    from .core import fleet

    stats = payload["counts"]
    lines = [
        "# Fleet verdicts, machine-read",
        "",
        "**Generated by `mlkit portfolio`. Do not hand-edit — the next run overwrites it.**",
        "",
        "Every figure below was read out of a committed artifact in a model repo by",
        "the adapter declared for that repo in `src/resilient_mlkit/fleet_adapters.py`.",
        "Nothing here was retyped, and nothing here is a default: a column this repo's",
        "artifacts do not carry reports `NA` with the reason, listed in full further down.",
        "",
        "This file does NOT replace `portfolio/MODEL_QUALITY.md`. That document carries",
        "the adjudication and the refutation checks — judgement, which is not a field",
        "lookup. This one carries the arithmetic, so the two can disagree in public.",
        "",
        f"- generated: `{payload['generated_at_utc']}`",
        f"- run nonce: `{payload['run_nonce']}`",
        f"- mlkit: `{payload['mlkit_version']}` at `{payload['mlkit_git_sha'] or 'NA (not a git worktree)'}`",
        (
            f"- rows: **{stats['rows']}**, cells measured: "
            f"**{stats['cells_measured']}**, "
            f"cells NA-with-reason: **{stats['cells_na']}**"
        ),
        "",
    ]
    if missing_repos:
        lines += [
            (
                "- repos declared but not found under the root: "
                f"{', '.join(f'`{m}`' for m in missing_repos)}"
            ),
            "",
        ]
    lines += [
        "## Repos as they were read",
        "",
        "| repo | branch | HEAD | working tree |",
        "|---|---|---|---|",
    ]
    for name, info in payload["repos_read"].items():
        lines.append(
            f"| {name} | `{info['branch'] or 'NA'}` | `{(info['git_sha'] or 'NA')[:12]}` | "
            f"{'DIRTY' if info['dirty'] else 'clean'} |"
        )
    lines += [
        "",
        "## Verdicts",
        "",
        fleet.markdown_table(rows),
        "",
        "`beats bar?` is read from the artifact where the artifact records it, and",
        "otherwise derived from the two scores above it; the row's `beats` source",
        "field in the JSON says which. `test arm` is whatever that repo records about",
        "its holdout reads — a boolean, a count, a timestamp or a sentence — quoted",
        "as it stands rather than normalised into a shape no repo actually uses.",
        "",
        "## Where each figure came from",
        "",
        fleet.provenance_block(rows),
        "",
    ]

    # An artifact that is not in git is not reproducible from the repository,
    # whatever it says. That is a stronger finding than any NA in the table
    # above, so it gets its own section rather than one column in a wide row.
    def _flag(pred):
        return [
            (r.key, alias, ref)
            for r in rows
            for alias, ref in r.artifacts.items()
            if ref.found and pred(ref)
        ]

    uncommitted = _flag(lambda ref: not ref.committed_at_head)
    dirty = _flag(lambda ref: ref.dirty)
    off = _flag(lambda ref: ref.off_checkout)
    lines += ["## Artifacts that are not where a reader would look for them", ""]
    if not (uncommitted or dirty or off):
        lines.append(
            "- none: every artifact above is committed at its tree's HEAD, matches the "
            "committed blob, and is on the branch that tree has checked out."
        )
    for key, alias, ref in uncommitted:
        lines.append(
            f"- **NOT COMMITTED — {key} / {alias}**: `{ref.relpath}` exists on disk "
            f"(sha256 `{ref.sha256[:16]}…`) but git has no such path at `{ref.branch}` "
            f"`{ref.git_sha[:12]}`. Any figure this table takes from it cannot be "
            "reproduced from the repository by anyone else."
        )
    for key, alias, ref in dirty:
        lines.append(
            f"- **DIRTY — {key} / {alias}**: `{ref.relpath}` on disk differs from the "
            f"blob committed at `{ref.git_sha[:12]}`. The figures above are the "
            "working-tree bytes, which no reviewer can see."
        )
    for key, alias, ref in off:
        lines.append(
            f"- **OFF CHECKOUT — {key} / {alias}**: read from the linked worktree "
            f"`{ref.worktree}` on branch `{ref.branch}`, not from the branch the repo "
            "root has checked out. It is evidence about that worktree."
        )
    lines.append("")

    notes = [(r.key, r.note) for r in rows if r.note]
    if notes:
        lines += ["## Row notes", ""]
        lines += [f"- **{key}** — {note}" for key, note in notes]
        lines.append("")
    na = fleet.na_summary(rows)
    lines += ["## Every NA in this table, and why", ""]
    lines += na or ["- none: every declared column resolved."]
    lines.append("")
    return "\n".join(lines)


def cmd_spine(args: argparse.Namespace) -> int:
    """Report whether the canonical spine still matches what is deployed.

    REPORT-ONLY, and deliberately so. This command never writes into a model
    repo. Overwriting eight repos from this one is a decision; making it a side
    effect of running a check is how a hand-written file on a canonical
    filename gets destroyed by something that was only supposed to look.

    ``scripts/sync_spine.py`` remains the only writer, and both read the same
    declaration in ``core.spine`` -- two definitions of "canonical" would be
    the same as none.
    """
    from .core import spine as spine_mod

    root = Path(args.root).resolve() if args.root else find_root()
    spine_root = Path(__file__).resolve().parent.parent.parent / "spine"
    if not spine_root.is_dir():
        print(f"no spine at {spine_root}", file=sys.stderr)
        return 2

    repos = _select_repos(args, root)
    if not repos:
        print(f"no portfolio repos found under {root}", file=sys.stderr)
        return 2

    run_nonce = nonce_mod.from_env_or_mint()
    all_drifts: list[spine_mod.FileDrift] = []
    for repo in repos:
        all_drifts += spine_mod.compare(spine_root, repo.name, repo.path)

    counts = spine_mod.summarise(all_drifts)
    payload = {
        "artifact_schema": "resilient-mlkit/spine-drift/1",
        "generated_by": "mlkit spine",
        "mlkit_version": __version__,
        "generated_at_utc": _dt.datetime.now(_dt.UTC).isoformat(timespec="seconds"),
        "run_nonce": run_nonce,
        "spine_root": str(spine_root),
        "mlkit_git_sha": _self_sha(),
        "canonical_files": [dest for _, dest in spine_mod.CANONICAL_FILES],
        "repos": {
            r.name: {"git_sha": r.git_sha, "branch": r.branch, "dirty": r.is_dirty}
            for r in repos
        },
        "counts": counts,
        "files": [d.to_dict() for d in all_drifts],
    }

    md = _render_spine_markdown(payload, all_drifts, repos)
    if args.json:
        print(json.dumps(payload, indent=1))
    else:
        print(f"mlkit {__version__}  spine  nonce={run_nonce}")
        print(f"spine={spine_root}")
        print()
        print(md)

    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(md)
        out.with_suffix(".json").write_text(json.dumps(payload, indent=1) + "\n")
        print(f"\nwrote {out} and {out.with_suffix('.json')}", file=sys.stderr)

    # Drift is a report, not a build break -- but a canonical file that is
    # ABSENT or UNCLAIMED in a repo means the spine is not in force there at
    # all, which is a different and worse thing than a copy that has moved.
    if counts.get(spine_mod.ABSENT) or counts.get(spine_mod.UNCLAIMED):
        return 1
    if counts.get(spine_mod.DRIFTED) or counts.get(spine_mod.NO_SPINE_SOURCE):
        return 3
    return 0


def _render_spine_markdown(payload: dict, drifts: list, repos: list) -> str:
    from .core import spine as spine_mod

    counts = payload["counts"]
    lines = [
        "# Spine drift, per repo",
        "",
        "**Generated by `mlkit spine`. Report-only: this command never writes into a",
        "model repo.** `scripts/sync_spine.py` is the only writer, and it still refuses",
        "to overwrite a file it did not author.",
        "",
        f"- generated: `{payload['generated_at_utc']}`",
        f"- run nonce: `{payload['run_nonce']}`",
        (
            f"- spine: `{payload['spine_root']}` at mlkit "
            f"`{payload['mlkit_git_sha'] or 'NA (not a git worktree)'}`"
        ),
        f"- canonical files compared per repo: **{len(payload['canonical_files'])}**",
        "- verdicts: " + ", ".join(f"**{k}** {v}" for k, v in sorted(counts.items())),
        "",
        "| verdict | meaning |",
        "|---|---|",
        f"| `{spine_mod.IN_SYNC}` | deployed copy is byte-identical to the spine |",
        (
            f"| `{spine_mod.DRIFTED}` | carries the `{spine_mod.MARKER}` banner but "
            "its bytes have moved; the next sync reverts it |"
        ),
        f"| `{spine_mod.ABSENT}` | no deployed copy at all — the spine is not in force here |",
        (
            f"| `{spine_mod.UNCLAIMED}` | a file without the banner occupies the "
            "canonical filename; the syncer will not touch it |"
        ),
        (
            f"| `{spine_mod.NO_SPINE_SOURCE}` | the spine itself has no such file — a "
            "defect in this repo, not in that one |"
        ),
        "",
        "## Per repo",
        "",
    ]
    by_repo: dict[str, list] = {}
    for d in drifts:
        by_repo.setdefault(d.repo, []).append(d)
    header = ["repo", "branch", *(dest for _, dest in spine_mod.CANONICAL_FILES)]
    lines.append("| " + " | ".join(f"`{h}`" if "/" in h else h for h in header) + " |")
    lines.append("|" + "---|" * len(header))
    branches = {r.name: r.branch for r in repos}
    for name, files in by_repo.items():
        by_path = {f.relpath: f for f in files}
        cells = []
        for _, dest in spine_mod.CANONICAL_FILES:
            f = by_path.get(dest)
            if f is None:
                cells.append("—")
            elif f.clean:
                cells.append("in sync")
            elif f.verdict == spine_mod.DRIFTED:
                cells.append(f"**DRIFTED** ({f.changed_lines} lines)")
            else:
                cells.append(f"**{f.verdict}**")
        lines.append(f"| {name} | `{branches.get(name, '?')}` | " + " | ".join(cells) + " |")

    lines += ["", "## What moved", ""]
    dirty = [d for d in drifts if not d.clean]
    if not dirty:
        lines.append("- nothing: every canonical file in every repo is byte-identical to the spine.")
    for d in dirty:
        lines.append(
            f"- **{d.repo} / `{d.relpath}` — {d.verdict}**. {d.detail}"
        )
        if d.spine_sha256 and d.deployed_sha256:
            lines.append(
                f"  - spine `{d.spine_sha256[:16]}…` vs deployed "
                f"`{d.deployed_sha256[:16]}…`"
            )
        for line in d.sample:
            lines.append(f"  - `{line}`")
    lines.append("")
    return "\n".join(lines)


def cmd_notice(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve() if args.root else find_root()
    repos = _select_repos(args, root)
    if not repos:
        print(f"no portfolio repos found under {root}", file=sys.stderr)
        return 2
    for repo in repos:
        allowlist = policy.load(repo)
        if not allowlist.exists:
            print(f"{repo.name}: no {policy.ALLOWLIST_RELPATH}; nothing to generate")
            continue
        target = repo.path / "NOTICE.md"

        # Refuse to destroy a NOTICE.md this tool did not write. Several repos
        # ship substantial hand-written attribution (choco's is 83 lines), and
        # R9 fails with "NOTICE.md is stale... run `mlkit notice`" — which
        # actively drives an agent into this command. Guarding only the empty-
        # allowlist case would still lose that content the moment one entry
        # existed, so the test is authorship, not entry count.
        if target.is_file() and not args.force:
            head = target.read_text(errors="ignore")[:400]
            if "GENERATED BY `mlkit notice`" not in head:
                print(
                    f"{repo.name}: REFUSED — NOTICE.md exists ({target.stat().st_size} bytes) "
                    "and was not generated by mlkit. Overwriting would destroy hand-written "
                    "attribution. Reconcile it into docs/allowlist.yaml first, or pass "
                    "--force if you have already preserved the content."
                )
                continue

        target.write_text(policy.render_notice(repo, allowlist))
        state = "signed" if allowlist.signed else "UNSIGNED (provisional)"
        print(f"{repo.name}: wrote NOTICE.md from {state} allowlist "
              f"({len(allowlist.attributions())} attribution obligation(s))")
    return 0


def cmd_keys(args: argparse.Namespace) -> int:
    """List every credential the portfolio is waiting on.

    The point of this command is to turn "seven repos are somehow blocked" into
    a short shopping list. Everything here is a path that has already been
    wired and exercised up to the credential boundary, so each entry is one
    paste away from producing real data.
    """
    root = Path(args.root).resolve() if args.root else find_root()
    repos = _select_repos(args, root)
    wanted: dict[str, list[str]] = {}
    for repo in repos:
        for result in store.load_all(repo, PHASES).values():
            if result.status is Status.DEFERRED:
                cred = str(result.evidence.get("credential", "?"))
                wanted.setdefault(cred, []).append(f"{repo.name}:{result.check_id}")

    if not wanted:
        print("No deferred credentials. Nothing in the portfolio is waiting on a key.")
        return 0

    print(f"{len(wanted)} credential(s) would unblock already-wired code paths:\n")
    from .core.table import render

    rows = [
        [cred, str(len(users)), ", ".join(sorted(users)[:6])]
        for cred, users in sorted(wanted.items())
    ]
    print(render(rows, ["CREDENTIAL", "CHECKS", "WAITING ON IT"]))
    print("\nEach of these is wired and exercised; supplying the value is the only")
    print("remaining step for those checks.")
    return 0


def cmd_env(args: argparse.Namespace) -> int:
    """Report whether THIS interpreter can measure each repo at all.

    Exists so that "environment unmeasurable" can be asked for directly rather
    than only discovered after a phase has already tried to write over a
    measured report. A numpy-less python3.14 regenerated ``reports/readiness.md``
    in at least four repos in August 2026; this command answers, in one line
    per repo and before anything is written, whether the shell you are in
    could have measured anything.
    """
    from .core import environment

    root = Path(args.root).resolve() if args.root else find_root()
    repos = _select_repos(args, root)
    if not repos:
        print(f"no portfolio repos found under {root}", file=sys.stderr)
        return 2

    print(f"mlkit {__version__}  environment  interpreter={sys.executable}")
    print(f"python {sys.version.split()[0]}  root={root}")
    print()

    rows, unmeasurable = [], 0
    for repo in repos:
        try:
            probe = environment.probe(repo)
        finally:
            repo.release()
        if probe.verdict == environment.UNMEASURABLE:
            unmeasurable += 1
        ok = sum(1 for v in probe.bindings.values() if v == "ok")
        rows.append([
            repo.name,
            probe.verdict,
            f"{ok}/{len(probe.bindings)}" if probe.bindings else "0/0",
            ", ".join(probe.missing_modules[:4]) or "-",
        ])

    from .core.table import render

    print(render(rows, ["REPO", "VERDICT", "BINDINGS OK", "MISSING FROM THIS INTERPRETER"]))
    print()
    print("MEASURABLE   this interpreter imported every declared binding")
    print("UNMEASURABLE at least one binding needs a module that is not this repo's own")
    print("             source and is absent here; binding-dependent reports are REFUSED")
    print("UNDECLARED   no bindings declared, so nothing was imported and nothing concluded")
    if unmeasurable:
        print()
        print(f"{unmeasurable} repo(s) cannot be measured from this interpreter. That is a")
        print("fact about the shell, not about the repos. Re-run from each repo's own")
        print("environment (its .venv, or `uv run --group gates`).")
    return 1 if unmeasurable else 0


def cmd_allowlist(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve() if args.root else find_root()
    repos = _select_repos(args, root)
    rc = 0
    for repo in repos:
        allowlist = policy.load(repo)
        if not allowlist.exists:
            print(f"{repo.name}: MISSING {policy.ALLOWLIST_RELPATH}")
            rc = 1
            continue
        if allowlist.parse_error:
            print(f"{repo.name}: INVALID — {allowlist.parse_error}")
            rc = 1
            continue
        defects = allowlist.defective_entries()
        status = "signed by " + allowlist.signed_by if allowlist.signed else "UNSIGNED"
        print(f"{repo.name}: {len(allowlist.entries)} entries, {status}")
        for key, problems in defects.items():
            print(f"    {key}: {', '.join(problems)}")
            rc = 1
    return rc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mlkit",
        description="The single measurement and gating tool for the Resilient portfolio.",
    )
    parser.add_argument("--version", action="version", version=f"mlkit {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    def common(p: argparse.ArgumentParser) -> None:
        p.add_argument("--root", help="directory containing the resilient-* checkouts")
        p.add_argument("--repo", help="comma-separated repo names (default: all found)")

    p_check = sub.add_parser("check", help="run a phase, or print the portfolio table")
    common(p_check)
    p_check.add_argument("--phase", choices=list(PHASES), help="phase to run")
    p_check.add_argument("--portfolio", action="store_true", help="print the portfolio table")
    p_check.add_argument("--all-repos", action="store_true", help="explicit form of the default")
    p_check.add_argument("--timeout", type=float, default=20.0, help="per-URL timeout in seconds")
    p_check.add_argument(
        "--offline", action="store_true", default=None,
        help="assert no network; skips reachability probing",
    )
    p_check.set_defaults(func=cmd_check)

    p_fleet = sub.add_parser(
        "portfolio",
        help="regenerate the measured columns of the fleet verdict table from artifacts",
    )
    common(p_fleet)
    p_fleet.add_argument("--out", help="write the table (and its .json twin) here")
    p_fleet.add_argument("--json", action="store_true", help="print the machine artifact instead")
    p_fleet.add_argument(
        "--allow-dirty",
        action="store_true",
        help=(
            "DIAGNOSIS ONLY: read artifacts from the working tree instead of from "
            "HEAD. Prints what the pointers resolve to and then REFUSES to emit a "
            "table, a --json payload or an --out file, and exits 2. Nothing read "
            "this way can become a verdict"
        ),
    )
    p_fleet.set_defaults(func=cmd_fleet)

    p_spine = sub.add_parser(
        "spine", help="report canonical-spine drift in the model repos (never writes)"
    )
    common(p_spine)
    p_spine.add_argument("--out", help="write the report (and its .json twin) here")
    p_spine.add_argument("--json", action="store_true", help="print the machine artifact instead")
    p_spine.set_defaults(func=cmd_spine)

    p_notice = sub.add_parser("notice", help="regenerate NOTICE.md from the allowlist")
    common(p_notice)
    p_notice.add_argument(
        "--force", action="store_true",
        help="overwrite an existing NOTICE.md even when the allowlist is empty",
    )
    p_notice.set_defaults(func=cmd_notice)

    p_keys = sub.add_parser("keys", help="list credentials the portfolio is waiting on")
    common(p_keys)
    p_keys.set_defaults(func=cmd_keys)

    p_env = sub.add_parser(
        "env", help="report whether this interpreter can measure each repo at all"
    )
    common(p_env)
    p_env.set_defaults(func=cmd_env)

    p_allow = sub.add_parser("allowlist", help="verify allowlist structure and signature")
    common(p_allow)
    p_allow.add_argument("action", choices=["verify"], nargs="?", default="verify")
    p_allow.set_defaults(func=cmd_allowlist)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "check" and not args.portfolio and not args.phase:
        parser.error("check requires --phase PHASE or --portfolio")
    return int(args.func(args) or 0)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
