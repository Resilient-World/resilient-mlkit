"""The ``mlkit`` command line.

This is the only thing in the portfolio permitted to emit a number. Every
metric, loss, score, coverage figure and cost in a report, a commit message or
a transcript must have come out of a run of this CLI. Anything else is a claim,
and claims are what this whole apparatus exists to stop.
"""

from __future__ import annotations

import argparse
import socket
import sys
import traceback
from pathlib import Path

from . import checks as checks_pkg
from .checks import PHASE_ORDER, PHASES, RunContext, for_phase
from .core import nonce as nonce_mod
from .core import policy, store
from .core.repo import PORTFOLIO, Repo, discover, find_root
from .core.result import CheckResult, CredentialRequired, Status
from .core.table import phase_table
from .portfolio import render_portfolio, resolve

__version__ = "0.2.0"


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
                r = by_id.get(cid)
                if r and r.status is Status.PASS:
                    n = r.evidence.get("resolved", r.evidence.get("n_sources", 0))
                    d = r.evidence.get("total", r.evidence.get("n_sources", 0))
                elif r and r.status is Status.FAIL:
                    n = r.evidence.get("resolved", 0)
                    d = r.evidence.get("total", r.evidence.get("n_sources", 0))
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
