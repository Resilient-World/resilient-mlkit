"""Two holes left open by the E-M24 stamping pass, each driven before it was closed.

E-M24 gave every report mlkit *writes* a line naming the build that wrote it.
Adversarial verification of that change drove two ways an mlkit build still
failed to be named, and both are closed here.

RESIDUAL 1 — THE DIGEST CAN COVER NONE OF THE RUNNING CODE
----------------------------------------------------------
``digest_tree`` excludes ``__pycache__`` and ``*.pyc`` on purpose: bytecode
moves for reasons that are not source changes. In a **sourceless install** --
``.py`` compiled to ``.pyc`` in place and removed, which CPython still imports
-- that exclusion excludes every executing file, and the digest falls through
to whatever non-Python data the package ships. Measured on this tree,
2026-09-01, with two copies of ``src/resilient_mlkit`` differing only in
``checks/readiness.py``:

    D4 (sourceless): files=1  stamp=0.5.0+src.5b9327f66528
    D5 (sourceless): files=1  stamp=0.5.0+src.5b9327f66528   <- readiness.py DIFFERS

A real R10 report written through ``_write_r10_report`` by D4 verified
``MATCH`` against D5. That is the E-M24 defect itself -- two builds with
different gate source reporting one identity -- reappearing inside the fix for
it, and it contradicts ``core/identity.py``'s own stated invariant that the
digest "never degrades into a plausible-looking string".

RESIDUAL 2 — THE ONE READINESS TABLE THAT IS COMPOSED, NOT MEASURED
--------------------------------------------------------------------
``mlkit check --portfolio`` renders a full readiness table out of
``.mlkit/results/*.json`` and exits on it; ``README.md`` says CI gates on that
exit code. The store recorded the repo's git SHA and nothing about mlkit, and
``store.load`` staled only on the SHA. Measured 2026-09-01: 27 PASSes written
by ``0.5.0+src.b1686b22efc6`` were read back at an unchanged repo SHA by
``0.5.0+src.48480b572359`` as live PASSes and rendered

    fray   771b874  PPPPP  PPPPP  PPPPPPPPPPPP  PPPPP  PPPPP  READY-TO-TRAIN

at exit 0, with nothing in the table, the store or the exit code naming either
build. "Readiness under whichever mlkit happened to be installed, and nothing
says which" -- the finding, in the readiness table the stamping pass did not
reach.

Every test here is a PAIR: the forcing that must FIRE, and the honest
neighbour that must stay SILENT. A control that only fires has not been shown
to be measuring the thing it names.
"""

from __future__ import annotations

import dataclasses
import json
import os
import py_compile
import shutil
import subprocess
import sys
from pathlib import Path

import resilient_mlkit
from resilient_mlkit import cli, portfolio
from resilient_mlkit.core import identity, store
from resilient_mlkit.core.repo import Repo
from resilient_mlkit.core.result import CheckResult, Status

PACKAGE = Path(identity.__file__).resolve().parent.parent


def test_the_tests_bind_to_the_package_under_test() -> None:
    """Nothing below means anything if it measured some other mlkit."""
    assert Path(resilient_mlkit.__file__).resolve().parent == PACKAGE
    assert list(resilient_mlkit.__path__) == [str(PACKAGE)]


# ==========================================================================
# RESIDUAL 1 — a digest that covers none of the running code
# ==========================================================================

#: Run in a CHILD interpreter, against a tree this process did not import.
#: The operand and the assertion that reads it must not be built by one import.
_SOURCELESS_DRIVER = """
import json, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import resilient_mlkit
from resilient_mlkit.core import identity
root = Path(sys.argv[1]) / "resilient_mlkit"
assert Path(resilient_mlkit.__file__).parent == root, resilient_mlkit.__file__
assert list(resilient_mlkit.__path__) == [str(root)], resilient_mlkit.__path__
ident = identity.build_identity()
print(json.dumps({
    "loaded_from": resilient_mlkit.__file__,
    "version": resilient_mlkit.__version__,
    "stamp": ident.stamp,
    "known": ident.known,
    "files": ident.files,
    "unavailable": ident.unavailable,
}))
"""


def _copy_package(dest_parent: Path) -> Path:
    """A real copy of the package under test, with bytecode stripped."""
    dest_parent.mkdir(parents=True, exist_ok=True)
    tree = dest_parent / "resilient_mlkit"
    shutil.copytree(PACKAGE, tree)
    for cache in tree.rglob("__pycache__"):
        shutil.rmtree(cache, ignore_errors=True)
    return tree


def _make_sourceless(tree: Path) -> None:
    """Compile every ``.py`` to a ``.pyc`` beside it and delete the source."""
    for py in sorted(tree.rglob("*.py")):
        py_compile.compile(str(py), cfile=str(py.with_suffix(".pyc")), doraise=True)
        py.unlink()


def _drive(parent: Path) -> dict:
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    proc = subprocess.run(
        [sys.executable, "-c", _SOURCELESS_DRIVER, str(parent)],
        capture_output=True, text=True, env=env, check=False,
    )
    assert proc.returncode == 0, f"driver failed:\n{proc.stdout}\n{proc.stderr}"
    return json.loads(proc.stdout.strip().splitlines()[-1])


def test_fires_a_sourceless_install_names_no_identity_at_all(tmp_path) -> None:
    """FIRES: two builds that differed reported one stamp. Now neither reports one.

    Both halves are driven in child interpreters against trees this process
    never imported, because the whole point is that the reader and the thing
    read are not the same import.
    """
    a, b = tmp_path / "a", tmp_path / "b"
    tree_a, tree_b = _copy_package(a), _copy_package(b)
    # The measured defect in miniature: same __version__, different gate source.
    readiness_b = tree_b / "checks" / "readiness.py"
    readiness_b.write_bytes(readiness_b.read_bytes() + b"\n")
    assert (tree_a / "__init__.py").read_bytes() == (tree_b / "__init__.py").read_bytes()

    _make_sourceless(tree_a)
    _make_sourceless(tree_b)
    assert not list(tree_a.rglob("*.py")), "the fixture must really be sourceless"

    got_a, got_b = _drive(a), _drive(b)

    assert got_a["loaded_from"].endswith(".pyc"), got_a["loaded_from"]
    assert got_a["version"] == got_b["version"] == resilient_mlkit.__version__
    for got in (got_a, got_b):
        assert got["known"] is False
        assert got["files"] == 0
        assert got["stamp"].endswith(identity.UNKNOWN_DIGEST)
        assert "not among" in got["unavailable"]
        assert "sourceless" in got["unavailable"]


def test_fires_no_equality_survives_a_sourceless_operand(tmp_path) -> None:
    """The verdict, not just the digest: an unknown build asserts nothing.

    Before the repair, a report written by one sourceless build verified MATCH
    against a different sourceless build. The stamp such a build now writes is
    ``+src.unknown``, and every comparison over it is INDETERMINATE -- which is
    the honest answer to "which build is this?" when the digest covers none of
    the running code.
    """
    unknown = f"{resilient_mlkit.__version__}+src.{identity.UNKNOWN_DIGEST}"
    verdict, reason = identity.compare_stamps(unknown, identity.build_identity().stamp)
    assert verdict == identity.INDETERMINATE
    assert "could not hash its own package tree" in reason

    verdict2, _ = identity.compare_stamps(unknown, unknown)
    assert verdict2 == identity.INDETERMINATE, (
        "two unknowns are not a match; that is the equality the sourceless "
        "install was getting for free"
    )


def test_stays_silent_an_ordinary_install_still_names_its_identity(tmp_path) -> None:
    """SILENT: a copy that ships source is measured exactly as before.

    The guard must cost nothing to every real install form. A source-shipping
    copy at another path digests, and digests to the SAME value as the package
    under test, because identity follows bytes and not location.
    """
    parent = tmp_path / "ordinary"
    _copy_package(parent)
    got = _drive(parent)

    assert got["loaded_from"].endswith(".py")
    assert got["known"] is True
    assert got["unavailable"] == ""
    assert got["files"] > 0
    assert got["stamp"] == identity.build_identity().stamp


def test_stays_silent_stray_bytecode_beside_real_source_is_still_ignored(
    tmp_path,
) -> None:
    """SILENT: the exclusion the repair narrows must still do its original job.

    A repair that closed the sourceless hole by hashing bytecode would make the
    identity move whenever the interpreter recompiled, which is the mirror
    image of the defect. It does not: source present, bytecode ignored.
    """
    parent = tmp_path / "withpyc"
    tree = _copy_package(parent)
    before = _drive(parent)["stamp"]
    (tree / "__pycache__").mkdir(exist_ok=True)
    (tree / "__pycache__" / "__init__.cpython-999.pyc").write_bytes(b"\x00" * 64)
    (tree / "stray.pyc").write_bytes(b"\x01\x02\x03")
    assert _drive(parent)["stamp"] == before


# ==========================================================================
# RESIDUAL 2 — the composed readiness table and the store behind it
# ==========================================================================


def _git_repo(path: Path) -> Repo:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    subprocess.run(
        ["git", "-C", str(path), "-c", "user.email=t@t", "-c", "user.name=t",
         "commit", "-q", "--allow-empty", "-m", "base"],
        check=True,
    )
    return Repo(name="fray", path=path)


def _passes(repo: Repo, phase: str, ids: list[str]) -> list[CheckResult]:
    out = []
    for cid in ids:
        r = CheckResult.passed(cid, phase, {"note": "measured by the other build"})
        out.append(dataclasses.replace(r, git_sha=repo.git_sha, repo=repo.name, nonce="N1"))
    return out


def _store_written_by(repo: Repo, phase: str, ids: list[str], build: str) -> None:
    """Write a results file exactly as ``save()`` does, but naming ``build``.

    The stamp is substituted in the PAYLOAD rather than by monkeypatching
    ``build_identity``, so the reader under test resolves its own identity for
    real and only the stored operand is controlled.
    """
    store.save(repo, phase, _passes(repo, phase, ids))
    path = repo.path / ".mlkit" / "results" / f"{phase}.json"
    payload = json.loads(path.read_text())
    assert payload[store.BUILD_KEY] == identity.build_identity().stamp
    payload[store.BUILD_KEY] = build
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def test_fires_a_pass_measured_by_another_build_is_stale(tmp_path) -> None:
    """FIRES: the driven defect. Another build's PASS no longer reads as one.

    ``0.5.0+src.b1686b22efc6`` measured it; the build installed here is asking.
    Those two differ in ``checks/readiness.py`` and agree on ``__version__``,
    which is E-M24 exactly.
    """
    repo = _git_repo(tmp_path / "resilient-fray")
    other = "0.5.0+src.b1686b22efc6"
    assert other != identity.build_identity().stamp
    _store_written_by(repo, "readiness", ["R1", "R2"], other)

    loaded = {r.check_id: r for r in store.load(repo, "readiness")}
    assert set(loaded) == {"R1", "R2"}
    for r in loaded.values():
        assert r.status is Status.STALE, r.status
        assert other in r.reason and identity.build_identity().stamp in r.reason


def test_fires_a_results_file_that_names_no_build_is_stale(tmp_path) -> None:
    """FIRES: the shape every pre-E-M24 store on disk already has.

    Tied to nothing is the same as tied to something else, and this is the
    reason ``_stale_if_moved`` already stales a result with no git SHA.
    """
    repo = _git_repo(tmp_path / "resilient-fray")
    store.save(repo, "readiness", _passes(repo, "readiness", ["R1"]))
    path = repo.path / ".mlkit" / "results" / "readiness.json"
    payload = json.loads(path.read_text())
    del payload[store.BUILD_KEY]
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")

    (loaded,) = store.load(repo, "readiness")
    assert loaded.status is Status.STALE
    assert "record no mlkit build" in loaded.reason


def test_stays_silent_a_pass_from_this_build_survives_the_round_trip(tmp_path) -> None:
    """SILENT: the honest case. Same repo SHA, same mlkit, still a PASS.

    Without this the "fix" would be a rule that stales everything, which would
    be indistinguishable from deleting the store.
    """
    repo = _git_repo(tmp_path / "resilient-fray")
    store.save(repo, "readiness", _passes(repo, "readiness", ["R1", "R2"]))

    loaded = {r.check_id: r for r in store.load(repo, "readiness")}
    assert [r.status for r in loaded.values()] == [Status.PASS, Status.PASS]
    assert loaded["R1"].evidence == {"note": "measured by the other build"}


def test_stays_silent_a_fail_from_another_build_is_not_hidden(tmp_path) -> None:
    """SILENT, and load-bearing: staling a FAIL would hide a failure.

    ``_stale_if_moved`` stales only PASS and ESCALATED for exactly this reason,
    and the instrument rule must not be broader than the tree rule it mirrors.
    """
    repo = _git_repo(tmp_path / "resilient-fray")
    fail = CheckResult.failed("R1", "readiness", "the loader refuses the panel")
    fail = dataclasses.replace(fail, git_sha=repo.git_sha, repo=repo.name)
    store.save(repo, "readiness", [fail])
    path = repo.path / ".mlkit" / "results" / "readiness.json"
    payload = json.loads(path.read_text())
    payload[store.BUILD_KEY] = "0.5.0+src.b1686b22efc6"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")

    (loaded,) = store.load(repo, "readiness")
    assert loaded.status is Status.FAIL
    assert loaded.reason == "the loader refuses the panel"


def test_fires_the_portfolio_table_no_longer_reads_ready_on_another_builds_verdicts(
    tmp_path, capsys,
) -> None:
    """FIRES, end to end, through the command whose exit code CI gates on.

    Driven through ``cli.main`` and not through ``render_portfolio`` with a
    state list this test built: composing the states is part of what has to be
    right.
    """
    from resilient_mlkit.checks import PHASE_ORDER, PHASES

    root = tmp_path / "root"
    repo = _git_repo(root / "resilient-fray")
    _git_repo(root / "resilient-surge")  # a second, so find_root/discover behave
    for phase in PHASES:
        _store_written_by(repo, phase, list(PHASE_ORDER[phase]), "0.5.0+src.b1686b22efc6")

    code = cli.main(["check", "--portfolio", "--root", str(root)])
    out = capsys.readouterr().out

    assert code != 0, "another build's PASSes must not resolve READY at exit 0"
    assert portfolio.READY not in out.split("Why each repo is where it is:")[0]
    assert "S" in out, "the staled cells must be visible in the table"


def test_stays_silent_the_portfolio_table_still_resolves_on_this_builds_verdicts(
    tmp_path, capsys,
) -> None:
    """SILENT: the same command, the same repo, this build's own results.

    The pair matters more here than anywhere else: a rule that staled every
    stored PASS would make the portfolio permanently un-READY, which reads as
    rigour and is just breakage.
    """
    from resilient_mlkit.checks import PHASE_ORDER, PHASES

    root = tmp_path / "root"
    repo = _git_repo(root / "resilient-fray")
    _git_repo(root / "resilient-surge")
    for phase in PHASES:
        store.save(repo, phase, _passes(repo, phase, list(PHASE_ORDER[phase])))

    cli.main(["check", "--portfolio", "--root", str(root)])
    out = capsys.readouterr().out

    assert portfolio.READY in out
    assert "record no mlkit build" not in out
    assert "the mlkit installed here is" not in out


def test_the_portfolio_table_names_the_build_that_rendered_it(tmp_path) -> None:
    """The table is a readiness table and must name its instrument like the rest.

    Asserted on the rendered text through the one parser, not by grepping for a
    literal: whatever ``stamps_in`` would read out of a report is what has to be
    there, or the adopter-side check reads a different convention than the
    emitter writes.
    """
    root = tmp_path / "root"
    repo = _git_repo(root / "resilient-fray")
    rendered = portfolio.render_portfolio(
        [portfolio.resolve(repo, {})], "nonce-for-this-table"
    )
    assert identity.stamps_in(rendered) == [identity.build_identity().stamp]
