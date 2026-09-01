"""E-M24: a report must be able to name the mlkit that wrote it.

THE MEASURED DEFECT
-------------------
``resilient-fray`` pins mlkit by rev ``c65b2e7``; mlkit main is ``6921e9a``.
Forty commits apart; nine source files different; ``+50/-5`` in
``checks/readiness.py``, the file that emits R1-R12; ``+373/-13`` in
``core/served.py``, the promotion verdict. Both trees declare
``__version__ == "0.5.0"``. Every adopter readiness table written under either
of them is therefore "readiness under whichever mlkit happened to be
installed", and no reader can tell which.

``cli._self_sha()`` did not close it. It shells ``git rev-parse HEAD`` in
mlkit's own directory, which in an adopter's environment is ``site-packages``
and not a git worktree, so it returns ``""`` -- the field is empty in exactly
the case that needed it.

WHAT IS PROVEN HERE, AND HOW
----------------------------
The control pair for the end-to-end claim is deliberately not built in one
block. It copies the package tree twice, mutates ONE BYTE of
``checks/readiness.py`` in the second copy, and runs a SEPARATE INTERPRETER on
each -- each driver asserting ``resilient_mlkit.__file__`` is the tree it was
pointed at before it does anything -- which writes a real R10 report through
the real writer. The parent process then verifies those two reports against
the mlkit IT is running:

* the byte-identical copy, at a different path, in a different process:
  **MATCH**  (negative control -- the identity must not move for a reason that
  is not a source change);
* the one-byte-different copy: **MISMATCH**  (positive control -- the measured
  defect in miniature, since both copies still declare ``0.5.0``).

Neither operand is constructed by the assertion that reads it. The report is
produced by mlkit's own writer in another process; the installed stamp is
computed by this one.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

import resilient_mlkit
from resilient_mlkit import cli
from resilient_mlkit.checks import RunContext
from resilient_mlkit.checks import readiness as readiness_mod
from resilient_mlkit.core import (
    environment,
    fabricated_targets,
    identity,
    metric_registry,
    report,
)
from resilient_mlkit.core.environment import EnvironmentProbe
from resilient_mlkit.core.repo import Repo

ROOT = Path(__file__).resolve().parent.parent
PACKAGE = ROOT / "src" / "resilient_mlkit"

# The suite must be measuring THIS tree and not some other mlkit that happens
# to be importable. Asserted once, at collection, so a wrong-tree run fails by
# name instead of producing a green suite about a package nobody edited.
assert Path(resilient_mlkit.__file__).resolve() == PACKAGE / "__init__.py", (
    f"tests import mlkit from {resilient_mlkit.__file__}, not from {PACKAGE}"
)


@pytest.fixture(autouse=True)
def _fresh_identity_cache():
    """`build_identity` is process-cached; no test here may poison another.

    One test in this file deliberately makes the identity unmeasurable. Without
    this the cached refusal would leak into every test that ran after it, and
    the leak would look like a passing suite about a broken instrument -- which
    is the exact failure shape the file is about.
    """
    identity.build_identity.cache_clear()
    yield
    identity.build_identity.cache_clear()


# -- helpers ---------------------------------------------------------------


def _tree(dest: Path) -> Path:
    """A copy of the package tree at ``dest/resilient_mlkit``, no bytecode.

    ``__pycache__`` is excluded from the COPY as well as from the digest, so
    that a stale ``.pyc`` cannot decide which source the child interpreter
    actually executes.
    """
    out = dest / "resilient_mlkit"
    shutil.copytree(PACKAGE, out, ignore=shutil.ignore_patterns("__pycache__"))
    return out


def _mutate_one_byte(tree: Path, relpath: str) -> None:
    """Append a single comment character to a file. One byte, no semantics."""
    target = tree / relpath
    target.write_bytes(target.read_bytes() + b"#")


#: Runs in a SEPARATE interpreter against a SEPARATE package tree. It asserts
#: which mlkit it imported before it writes anything -- a driver that does not
#: name its own instrument is the defect this file exists to close, and it
#: would be absurd for the control to commit it.
_DRIVER = textwrap.dedent(
    """
    import json, sys
    from pathlib import Path

    tree_parent = sys.argv[1]
    sys.path.insert(0, tree_parent)
    import resilient_mlkit
    expected = str(Path(tree_parent) / "resilient_mlkit" / "__init__.py")
    actual = str(Path(resilient_mlkit.__file__).resolve())
    assert actual == expected, f"driver imported {actual}, wanted {expected}"

    from resilient_mlkit.checks import RunContext
    from resilient_mlkit.checks.readiness import _write_r10_report
    from resilient_mlkit.core import identity
    from resilient_mlkit.core.repo import Repo

    out = Path(sys.argv[2])
    repo_dir = Path(sys.argv[3])
    _write_r10_report(
        out,
        Repo(name="fixturerepo", path=repo_dir),
        RunContext(nonce="driver-nonce", root=repo_dir, offline=True),
        [], 0, ["src"],
    )
    print(json.dumps({
        "mlkit_file": actual,
        "stamp": identity.build_identity().stamp,
        "sha256": identity.build_identity().source_sha256,
        "version": resilient_mlkit.__version__,
    }))
    """
)


def _run_driver(tree_parent: Path, out: Path, repo_dir: Path) -> dict:
    """Write a real R10 report from the mlkit at ``tree_parent``."""
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    proc = subprocess.run(
        [sys.executable, "-c", _DRIVER, str(tree_parent), str(out), str(repo_dir)],
        capture_output=True, text=True, env=env, check=False,
    )
    assert proc.returncode == 0, f"driver failed:\n{proc.stdout}\n{proc.stderr}"
    return json.loads(proc.stdout.strip().splitlines()[-1])


def _ctx(tmp_path: Path) -> RunContext:
    return RunContext(nonce="test-nonce", root=tmp_path, offline=True)


def _repo(tmp_path: Path) -> Repo:
    return Repo(name="fixturerepo", path=tmp_path)


def _installed() -> str:
    return identity.build_identity().stamp


# ==========================================================================
# 1. THE CONSTRUCTING LAYER — what the digest is computed over
# ==========================================================================


def test_positive_control_one_byte_in_a_gate_file_moves_the_digest(tmp_path) -> None:
    """FIRES: the measured defect, reduced to its smallest possible form.

    Two trees whose ``__version__`` literal is byte-identical and whose
    ``checks/readiness.py`` differs by one byte. The version cannot tell them
    apart -- that is E-M24 -- and the digest must.
    """
    a, b = _tree(tmp_path / "a"), _tree(tmp_path / "b")
    _mutate_one_byte(b, "checks/readiness.py")

    sha_a, files_a, why_a = identity.digest_tree(a)
    sha_b, files_b, why_b = identity.digest_tree(b)

    assert (why_a, why_b) == ("", "")
    assert files_a == files_b, "the mutation added a byte, not a file"
    assert (a / "__init__.py").read_bytes() == (b / "__init__.py").read_bytes(), (
        "the two trees must declare the same version, or this proves nothing"
    )
    assert sha_a != sha_b


def test_negative_control_a_byte_identical_tree_at_another_path_has_one_digest(
    tmp_path,
) -> None:
    """SILENT: identity follows the bytes, not the directory they sit in.

    An adopter's ``site-packages/resilient_mlkit`` and this repo's
    ``src/resilient_mlkit`` are different paths. If the path moved the digest,
    the check would fire on every adopter for a reason that is not a source
    change, and would be worthless within a week.
    """
    a, b = _tree(tmp_path / "one"), _tree(tmp_path / "two")
    assert a != b
    assert identity.digest_tree(a)[0] == identity.digest_tree(b)[0]


def test_negative_control_bytecode_and_pycache_do_not_move_the_digest(tmp_path) -> None:
    """SILENT: compiled bytecode is interpreter state, not gate semantics."""
    a, b = _tree(tmp_path / "a"), _tree(tmp_path / "b")
    before = identity.digest_tree(b)[0]
    (b / "__pycache__").mkdir()
    (b / "__pycache__" / "__init__.cpython-999.pyc").write_bytes(b"\x00" * 64)
    (b / "checks" / "__pycache__").mkdir()
    (b / "checks" / "__pycache__" / "readiness.cpython-999.pyc").write_bytes(b"\xff" * 32)
    (b / "stray.pyc").write_bytes(b"\x01\x02")
    assert identity.digest_tree(b)[0] == before
    assert identity.digest_tree(b)[0] == identity.digest_tree(a)[0]


def test_positive_control_length_framing_separates_a_rename_from_a_move(
    tmp_path,
) -> None:
    """FIRES: without per-entry length framing these two trees would collide.

    Concatenating ``relpath || content`` unframed makes ``ab.py`` + ``c`` and
    ``a.py`` + ``bc``... the same byte stream. The framing is what stops a
    rename that shifts bytes between a path and a body from being invisible,
    and this is the pair that shows the framing is doing work.
    """
    one, two = tmp_path / "one", tmp_path / "two"
    one.mkdir()
    two.mkdir()
    (one / "ab").write_bytes(b"c")
    (two / "a").write_bytes(b"bc")
    assert identity.digest_tree(one)[0] != identity.digest_tree(two)[0]


def test_a_missing_tree_yields_no_digest_a_reason_and_an_unknown_stamp(
    tmp_path,
) -> None:
    """A tree that cannot be read produces NO number, and says why."""
    sha, files, why = identity.digest_tree(tmp_path / "nothing-here")
    assert sha is None and files == 0
    assert "is not a directory" in why

    ident = identity.BuildIdentity(
        version="0.5.0", source_sha256=None, files=0,
        root=str(tmp_path / "nothing-here"), unavailable=why,
    )
    assert ident.stamp == "0.5.0+src.unknown"
    assert ident.known is False
    assert why in ident.context_line()


def test_an_empty_tree_is_a_refusal_and_not_the_digest_of_nothing(tmp_path) -> None:
    """sha256 of zero bytes is a perfectly good hex string and a terrible identity."""
    empty = tmp_path / "empty"
    empty.mkdir()
    sha, files, why = identity.digest_tree(empty)
    assert sha is None and files == 0 and "no shipped files" in why


@pytest.mark.skipif(os.geteuid() == 0, reason="root can read a 0o000 file")
def test_no_partial_digest_is_returned_when_one_file_cannot_be_read(tmp_path) -> None:
    """A digest over an unknown subset looks like an identity and is not one."""
    tree = _tree(tmp_path / "a")
    blocked = tree / "checks" / "readiness.py"
    blocked.chmod(0o000)
    try:
        sha, files, why = identity.digest_tree(tree)
    finally:
        blocked.chmod(0o644)
    assert sha is None and files == 0
    assert "checks/readiness.py" in why


def test_the_running_package_is_one_directory_here() -> None:
    """The precondition the digest rests on, asserted rather than assumed."""
    assert identity.one_tree_or_reason(identity.package_root()) == ""
    assert list(resilient_mlkit.__path__) == [str(identity.package_root())]


def test_a_package_split_across_two_directories_refuses_to_name_an_identity(
    tmp_path, monkeypatch
) -> None:
    """FIRES: the digest describes ONE directory, so two is a refusal.

    Split the package -- a namespace package, a shadowing directory earlier on
    sys.path, a half-installed second copy -- and `core/identity.py` can come
    from one tree while `checks/readiness.py` comes from another. A digest of
    the first would be a true statement about half the instrument, reading as
    an identity while not being one. It must decline instead.
    """
    monkeypatch.setattr(
        resilient_mlkit, "__path__",
        [str(identity.package_root()), str(tmp_path)], raising=True,
    )
    identity.build_identity.cache_clear()
    try:
        ident = identity.build_identity()
        assert ident.source_sha256 is None
        assert ident.known is False
        assert ident.stamp.endswith(identity.UNKNOWN_DIGEST)
        assert "not one directory" in ident.unavailable
        # And nothing downstream turns that into an equality.
        verdict = identity.verify_report_text(
            f"{identity.STAMP_PREFIX}`0.5.0+src.{'a' * 12}`\n"
        )
        assert verdict.verdict == identity.INDETERMINATE
    finally:
        # Undone HERE and not at teardown: the assertion below is the one that
        # proves the refusal was caused by the split and not by something this
        # test broke permanently, and it has to run with __path__ restored.
        monkeypatch.undo()
        identity.build_identity.cache_clear()

    assert list(resilient_mlkit.__path__) == [str(identity.package_root())]
    assert identity.build_identity().known is True


def test_the_digest_covers_files_that_are_not_python(tmp_path) -> None:
    """A shipped data file can change behaviour; a .py-only digest would not see it."""
    tree = _tree(tmp_path / "a")
    before = identity.digest_tree(tree)[0]
    (tree / "some_shipped_table.csv").write_text("a,b\n1,2\n")
    assert identity.digest_tree(tree)[0] != before


# ==========================================================================
# 2. THE END-TO-END CONTROL PAIR — real writers, separate interpreters
# ==========================================================================


def test_control_pair_a_report_from_a_different_build_is_a_mismatch(tmp_path) -> None:
    """POSITIVE: a real report, written by a real writer, by another build.

    The child mutates one byte of ``checks/readiness.py``. Its
    ``__version__`` is unchanged and equal to this process's. The report it
    writes is verified here against the mlkit THIS process is running, and the
    verdict must be MISMATCH.
    """
    parent = tmp_path / "mutated"
    parent.mkdir()
    tree = _tree(parent)
    _mutate_one_byte(tree, "checks/readiness.py")

    out = tmp_path / "report_from_mutated.md"
    info = _run_driver(parent, out, tmp_path)

    assert info["version"] == resilient_mlkit.__version__, (
        "the control is only about identity if the two builds agree on the "
        "version; they must, and here they do"
    )
    assert info["stamp"] != _installed()

    verdict = identity.verify_report(out)
    assert verdict.verdict == identity.MISMATCH, verdict.reason
    assert verdict.found == info["stamp"]
    assert verdict.installed == _installed()
    assert verdict.ok is False


def test_control_pair_a_report_from_a_byte_identical_build_matches(tmp_path) -> None:
    """NEGATIVE: same bytes, other path, other process — still one identity."""
    parent = tmp_path / "identical"
    parent.mkdir()
    _tree(parent)

    out = tmp_path / "report_from_identical.md"
    info = _run_driver(parent, out, tmp_path)

    assert info["mlkit_file"] != resilient_mlkit.__file__, (
        "the control is worthless if the child imported the same files as the "
        "parent; it must be a genuinely separate tree"
    )
    assert info["stamp"] == _installed()

    verdict = identity.verify_report(out)
    assert verdict.verdict == identity.MATCH, verdict.reason
    assert verdict.ok is True


# ==========================================================================
# 3. EVERY REPORT WRITER — by calling it, not by grepping for a literal
# ==========================================================================


def _sole_stamp(text: str) -> str:
    found = identity.stamps_in(text)
    assert len(found) == 1, f"expected exactly one stamp, got {found}"
    return found[0]


def test_the_r10_writer_stamps_its_report(tmp_path) -> None:
    out = tmp_path / "r10.md"
    readiness_mod._write_r10_report(
        out, _repo(tmp_path), _ctx(tmp_path), [], 0, ["src"],
        metric_registry.MetricRegistry(),
    )
    assert _sole_stamp(out.read_text()) == _installed()


def test_the_r11_writer_stamps_its_report(tmp_path) -> None:
    out = tmp_path / "r11.md"
    readiness_mod._write_r11_report(
        out, _repo(tmp_path), _ctx(tmp_path), [], 0,
        fabricated_targets.SourceRegistry(),
    )
    assert _sole_stamp(out.read_text()) == _installed()


def test_the_r12_writer_stamps_its_report(tmp_path) -> None:
    out = tmp_path / "r12.md"
    readiness_mod._write_r12_report(out, _repo(tmp_path), _ctx(tmp_path), [], 0)
    assert _sole_stamp(out.read_text()) == _installed()


def test_the_r8_readiness_report_stamps_itself(tmp_path) -> None:
    from resilient_mlkit.core.result import CheckResult

    ctx = _ctx(tmp_path)
    ctx.prior["R10"] = CheckResult.passed("R10", "readiness", {"files": 1})
    result = readiness_mod.r8_report(_repo(tmp_path), ctx)
    assert result.status.value != "NA", result.reason
    written = tmp_path / "reports" / "readiness.md"
    assert written.is_file(), result.reason
    assert _sole_stamp(written.read_text()) == _installed()


def test_the_refusal_file_names_the_build_that_refused(tmp_path) -> None:
    """A refusal is a statement by a build too, and it is read beside a report."""
    target = tmp_path / "readiness.md"
    target.write_text("# prior, measured\n")
    probe = EnvironmentProbe(
        verdict=environment.UNMEASURABLE,
        reason="numpy is absent from this interpreter",
        bindings={"loader": "missing:numpy"},
        missing_modules=("numpy",),
        python="3.14.6",
    )
    assert probe.measurable is False, "the fixture must actually be a refusal"
    written = report.guarded_write(
        target, "# would-be report\n", probe=probe, depends_on_bindings=True,
        nonce="n", git_sha="deadbeef",
    )
    assert written.written is False and written.refusal_path is not None
    assert _sole_stamp(written.refusal_path.read_text()) == _installed()
    assert target.read_text() == "# prior, measured\n", "the prior must be untouched"


def _fleet_root(tmp_path: Path) -> Path:
    """A root `discover()` finds one repo under, so the commands do real work."""
    (tmp_path / "resilient-choco").mkdir()
    return tmp_path


def test_the_fleet_table_stamps_itself_and_its_json_twin(tmp_path) -> None:
    """`mlkit portfolio` writes a COMMITTED file; it must name its own author.

    Driven through `cli.main`, not through the renderer with a payload this
    test made up: the payload construction is part of what has to be right.
    """
    out = tmp_path / "FLEET_VERDICTS.md"
    # The exit code is about whether the fixture repo's artifacts resolved (they
    # do not; it is an empty directory). What is under test is the file the
    # command writes either way, which is the file that gets committed.
    cli.main(["portfolio", "--root", str(_fleet_root(tmp_path)), "--out", str(out)])
    assert out.is_file()
    assert _sole_stamp(out.read_text()) == _installed()
    payload = json.loads(out.with_suffix(".json").read_text())
    assert payload["mlkit_build"] == identity.build_identity().to_dict()
    assert payload["mlkit_version"] == resilient_mlkit.__version__


def test_the_spine_report_stamps_itself_and_its_json_twin(tmp_path) -> None:
    out = tmp_path / "SPINE_DRIFT.md"
    cli.main(["spine", "--root", str(_fleet_root(tmp_path)), "--out", str(out)])
    assert out.is_file()
    assert _sole_stamp(out.read_text()) == _installed()
    payload = json.loads(out.with_suffix(".json").read_text())
    assert payload["mlkit_build"] == identity.build_identity().to_dict()


# -- no writer left behind -------------------------------------------------
#
# The six tests above prove the writers that exist TODAY stamp their output, by
# calling them. They cannot prove anything about the seventh writer somebody
# adds next month, and "every report mlkit writes" is the claim being made. The
# two below are structural, over the source, and they are the half that keeps
# the claim true as the file grows.

#: Files that compose a report header. Both markers are counted in each.
_HEADER_SOURCES = (
    PACKAGE / "checks" / "readiness.py",
    PACKAGE / "core" / "report.py",
    PACKAGE / "cli.py",
)

#: The line every mlkit report header opens with, and the emitter that must
#: appear once per occurrence of it.
_NONCE_LINE = "- run nonce: "
_EMITTERS = ("identity.header_lines()", "identity_mod.header_lines()")


def test_every_report_header_in_the_source_calls_the_one_emitter() -> None:
    """One nonce line, one identity stamp — counted, not merely co-present.

    A file-level "does it mention the emitter anywhere" guard would pass a file
    with five headers and one stamp. This counts, so a new report header with
    no stamp fails by file name.
    """
    for path in _HEADER_SOURCES:
        src = path.read_text(encoding="utf-8")
        headers = src.count(_NONCE_LINE)
        stamps = sum(src.count(marker) for marker in _EMITTERS)
        assert headers > 0, f"{path.name} composes no report header any more"
        assert headers == stamps, (
            f"{path.name} composes {headers} report header(s) and emits "
            f"{stamps} identity stamp(s); a report that does not name the "
            "mlkit that wrote it is the defect E-M24 records"
        )


def test_every_payload_that_stamps_the_version_also_stamps_the_build() -> None:
    """`mlkit_version` cannot identify a build; wherever it is written, the
    identity must be written beside it.

    Parsed with `ast` rather than grepped, so the two keys must be in the SAME
    dict literal -- a `mlkit_build` elsewhere in the file would not satisfy a
    reader looking at one payload.
    """
    import ast

    sources = sorted(PACKAGE.rglob("*.py")) + sorted((ROOT / "scripts").glob("*.py"))
    checked = 0
    for path in sources:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Dict):
                continue
            keys = {k.value for k in node.keys if isinstance(k, ast.Constant)}
            if "mlkit_version" not in keys:
                continue
            checked += 1
            assert "mlkit_build" in keys, (
                f"{path.relative_to(ROOT)}:{node.lineno} writes `mlkit_version` "
                "into a payload without `mlkit_build` beside it; the version is "
                "equal across builds whose gate source differs (E-M24)"
            )
    assert checked >= 4, (
        f"only {checked} version-stamping payload(s) found; this control would "
        "pass over an absence"
    )


def test_the_machine_payload_never_carries_a_bare_unexplained_na() -> None:
    """Every absence in the identity object comes with the reason for it."""
    ident = identity.build_identity().to_dict()
    assert ident["stamp"] == _installed()
    assert ident["source_sha256"] and ident["files"] > 1
    assert ident["unavailable"] == "", ident["unavailable"]
    assert ident["vcs_commit"] or ident["vcs_reason"]


# ==========================================================================
# 4. THE COMPARISON — every operand, and every verdict that is not equality
# ==========================================================================


def test_an_unstamped_report_is_reported_as_unstamped_not_as_a_mismatch() -> None:
    """"Written by an unknown build" and "written by a known other build" differ."""
    verdict = identity.verify_report_text("# Readiness report\n\n- git SHA: `abc`\n")
    assert verdict.verdict == identity.UNSTAMPED
    assert verdict.found is None
    assert verdict.ok is False


def test_two_disagreeing_stamps_in_one_file_are_conflicting() -> None:
    """No single build wrote it, so no single build can be held to it."""
    text = (
        f"{identity.STAMP_PREFIX}`0.5.0+src.aaaaaaaaaaaa`\n"
        "some prose\n"
        f"{identity.STAMP_PREFIX}`0.5.0+src.bbbbbbbbbbbb`\n"
    )
    verdict = identity.verify_report_text(text)
    assert verdict.verdict == identity.CONFLICTING
    assert verdict.all_found == ("0.5.0+src.aaaaaaaaaaaa", "0.5.0+src.bbbbbbbbbbbb")


def test_two_agreeing_stamps_are_not_conflicting() -> None:
    """A report quoted into a longer document twice is still one build's report."""
    line = f"{identity.STAMP_PREFIX}`{_installed()}`"
    verdict = identity.verify_report_text(f"{line}\nprose\n{line}\n")
    assert verdict.verdict == identity.MATCH


def test_a_report_whose_own_digest_was_unknown_is_indeterminate() -> None:
    """No equality is asserted from an unknown operand."""
    text = f"{identity.STAMP_PREFIX}`0.5.0+src.{identity.UNKNOWN_DIGEST}`\n"
    verdict = identity.verify_report_text(text)
    assert verdict.verdict == identity.INDETERMINATE
    assert verdict.ok is False


def test_an_unknown_installed_digest_is_indeterminate_in_both_directions() -> None:
    """The other operand gets the same treatment; neither side may be guessed."""
    real = f"0.5.0+src.{'a' * 12}"
    assert identity.compare_stamps(real, "0.5.0+src.unknown")[0] == identity.INDETERMINATE
    assert identity.compare_stamps("0.5.0+src.unknown", real)[0] == identity.INDETERMINATE
    assert identity.compare_stamps(real, "0.5.0")[0] == identity.INDETERMINATE
    assert identity.compare_stamps("0.5.0", real)[0] == identity.INDETERMINATE


def test_a_difference_in_the_version_half_alone_is_a_mismatch() -> None:
    """Same source digest under two version strings still means two builds."""
    half = "a" * 12
    verdict, _ = identity.compare_stamps(f"0.4.0+src.{half}", f"0.5.0+src.{half}")
    assert verdict == identity.MISMATCH


def test_equal_stamps_are_a_match() -> None:
    stamp = f"0.5.0+src.{'a' * 12}"
    assert identity.compare_stamps(stamp, stamp)[0] == identity.MATCH


def test_prose_quoting_a_stamp_is_not_a_stamp() -> None:
    """The parser is position-anchored, so a document ABOUT identity is safe.

    This file, and docs/BUILD_IDENTITY.md, both quote example stamps. If a
    loose regex counted them, `mlkit identity --verify` would report a
    CONFLICTING verdict over its own documentation.
    """
    text = (
        f"{identity.STAMP_PREFIX}`{_installed()}`\n"
        "\n"
        "The old reports said `0.5.0+src.deadbeefcafe`, which is not this one.\n"
        "  - measured by mlkit: `0.5.0+src.indentednotaheader`\n"
        "- measured by mlkit: 0.5.0+src.notbackticked\n"
    )
    assert identity.stamps_in(text) == [_installed()]
    assert identity.verify_report_text(text).verdict == identity.MATCH


def test_an_unreadable_file_is_indeterminate_and_not_unstamped(tmp_path) -> None:
    """A permissions error must not read as a finding about the report."""
    verdict = identity.verify_report(tmp_path / "does_not_exist.md")
    assert verdict.verdict == identity.INDETERMINATE
    assert "could not read" in verdict.reason


# ==========================================================================
# 5. THE CLI SURFACE
# ==========================================================================


def test_cli_identity_prints_the_running_build(capsys) -> None:
    assert cli.main(["identity"]) == 0
    out = capsys.readouterr().out
    assert _installed() in out
    assert identity.stamps_in(out) == [_installed()]


def test_cli_identity_json_is_the_same_object_the_reports_carry(capsys) -> None:
    assert cli.main(["identity", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload == identity.build_identity().to_dict()


def test_cli_verify_exits_zero_only_for_a_match(tmp_path, capsys) -> None:
    good = tmp_path / "good.md"
    good.write_text(f"{identity.STAMP_PREFIX}`{_installed()}`\n")
    assert cli.main(["identity", "--verify", str(good)]) == 0
    capsys.readouterr()


def test_cli_verify_exits_three_on_a_report_from_another_build(tmp_path, capsys) -> None:
    """A distinct exit code, because "another build wrote this" has its own fix."""
    other = tmp_path / "other.md"
    other.write_text(f"{identity.STAMP_PREFIX}`0.5.0+src.{'f' * 12}`\n")
    assert cli.main(["identity", "--verify", str(other)]) == cli.IDENTITY_MISMATCH_EXIT
    capsys.readouterr()


def test_cli_verify_exits_one_on_an_unstamped_report(tmp_path, capsys) -> None:
    plain = tmp_path / "plain.md"
    plain.write_text("# Readiness report\n\n- git SHA: `abc`\n")
    assert cli.main(["identity", "--verify", str(plain)]) == 1
    assert "UNSTAMPED" in capsys.readouterr().out


def test_cli_verify_a_mismatch_anywhere_outranks_a_match_beside_it(
    tmp_path, capsys
) -> None:
    """One good report does not launder the bad one next to it."""
    good = tmp_path / "good.md"
    good.write_text(f"{identity.STAMP_PREFIX}`{_installed()}`\n")
    other = tmp_path / "other.md"
    other.write_text(f"{identity.STAMP_PREFIX}`0.5.0+src.{'f' * 12}`\n")
    rc = cli.main(["identity", "--verify", str(good), str(other)])
    assert rc == cli.IDENTITY_MISMATCH_EXIT
    capsys.readouterr()


# ==========================================================================
# 6. THE BOUNDARY THIS CHANGE MUST NOT CROSS
# ==========================================================================


def test_the_identity_does_not_touch_the_version_literal() -> None:
    """Release naming and tag cutting stay the signatory's (CLAUDE.md rule 12).

    A future edit that "simplifies" this by folding the digest into
    ``__version__`` would put an agent-computed string into the number the
    signatory cuts releases against, and would break
    ``tests/test_version_declaration.py``'s agreement with the CHANGELOG. This
    fails first, and says why.
    """
    assert "+" not in resilient_mlkit.__version__
    assert "src." not in resilient_mlkit.__version__
    source = (PACKAGE / "__init__.py").read_text(encoding="utf-8")
    assert f'__version__ = "{resilient_mlkit.__version__}"' in source, (
        "__version__ must remain ONE plain string literal; the build identity "
        "lives beside it, never inside it"
    )


def test_the_build_identity_is_reachable_as_a_dunder_beside_the_version() -> None:
    """``__build__`` is the adopter-facing name, and it is not a second literal."""
    assert resilient_mlkit.__build__ == identity.build_identity().stamp
    assert resilient_mlkit.__build__.startswith(resilient_mlkit.__version__ + "+")
    source = (PACKAGE / "__init__.py").read_text(encoding="utf-8")
    assert "__build__ = " not in source, (
        "__build__ must be MEASURED off the tree, not written down; a literal "
        "here is E-M08 returning in a new field"
    )


def test_an_unknown_attribute_still_raises_attributeerror() -> None:
    """The PEP 562 hook must not turn every typo into a silent object."""
    with pytest.raises(AttributeError):
        resilient_mlkit.__nonexistent_attribute__  # noqa: B018
