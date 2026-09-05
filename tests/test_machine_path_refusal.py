"""M-5 controls: the writer refuses an artifact that names a machine path.

Fixed in ``reports/M5_MACHINE_PATH_REFUSAL_PREREGISTRATION.md`` before the
code. P1 (the two real chokepoint run-of-record artifacts, re-produced through
the writer) is driven by ``scripts/m5_offenders_drive.py`` on this machine's
scratchpad and recorded in ``reports/M5_OFFENDERS_DRIVE.json``; the fixture
below carries the same key SHAPE with the same machine-root prefix so the
refusal is exercised in the suite on any machine.
"""

from __future__ import annotations

import json
import sys
import types
from pathlib import Path

import pytest

from resilient_mlkit.core import artifact, identity, module_bindings

#: The shape of `foundation_finetune.json`'s offending values (measured
#: 2026-09-04: 7 absolute-path strings under these pointers), with the real
#: machine-root prefix.
OFFENDER_SHAPE = {
    "hard_stops": {
        "mlkit_build": {"resolved_from": "/private/tmp/claude-501/x/scratchpad/e056-hardstops/.venv/lib/python3.12/site-packages/resilient_mlkit"},
        "modules_measured": {"resilient_mlkit": "/private/tmp/claude-501/x/scratchpad/e056-hardstops/.venv/lib/python3.12/site-packages/resilient_mlkit/__init__.py"},
        "pre_registration_statement": {"path": "/private/tmp/claude-501/x/scratchpad/e056-hardstops/docs/decision/finetune.prereg.md"},
    },
    "fits": {"chronos2-ft-lr1e-6": {"checkpoint_dir": "/private/tmp/claude-501/x/scratchpad/e056-hardstops/models/foundation_finetune/chronos2-ft-lr1e-6"}},
    "verdict": {"improves_on_zeroshot": []},
}


def _repo(tmp_path: Path) -> Path:
    root = tmp_path / "resilient-chokepoint"
    (root / "src" / "pkg").mkdir(parents=True)
    (root / "src" / "pkg" / "__init__.py").write_text("X = 1\n")
    return root


# ---------------------------------------------------------------------------
# P1 / P2 -- the offender shape is refused; the blessed shape is written
# ---------------------------------------------------------------------------


def test_p1_the_offender_shape_is_refused_listing_every_pointer(tmp_path):
    root = _repo(tmp_path)
    with pytest.raises(artifact.MachinePathRefused) as exc:
        artifact.write_artifact(root, "reports/benchmarks/foundation_finetune.json", OFFENDER_SHAPE)
    pointers = {p for p, _ in exc.value.pointers}
    assert pointers == {
        "/hard_stops/mlkit_build/resolved_from",
        "/hard_stops/modules_measured/resilient_mlkit",
        "/hard_stops/pre_registration_statement/path",
        "/fits/chronos2-ft-lr1e-6/checkpoint_dir",
    }
    assert "repo-relative path + sha256" in str(exc.value)
    assert not (root / "reports" / "benchmarks" / "foundation_finetune.json").exists()
    assert not list((root / "reports").rglob("*")) if (root / "reports").exists() else True


def test_p2_the_blessed_shape_is_written_and_round_trips(tmp_path):
    root = _repo(tmp_path)
    sys.path.insert(0, str(root / "src"))
    try:
        import importlib

        pkg = importlib.import_module("pkg")
        bindings = module_bindings.record([pkg], root=root, repo_local=["pkg"])
    finally:
        sys.path.remove(str(root / "src"))
        sys.modules.pop("pkg", None)
    payload = {
        "module_bindings": bindings,
        "mlkit_build": identity.build_identity().to_dict(),
        "verdict": {"improves_on_zeroshot": []},
        "pre_registration_statement": {"path": "docs/decision/finetune.prereg.md", "sha256": "ab" * 32},
    }
    out = artifact.write_artifact(root, "reports/benchmarks/foundation_finetune.json", payload)
    assert out == root / "reports" / "benchmarks" / "foundation_finetune.json"
    back = json.loads(out.read_text())
    assert back == payload
    assert module_bindings.problems(back["module_bindings"], root=root) == []
    entry = back["module_bindings"]["bindings"]["pkg"]
    assert entry["inside_repo"] is True and entry["repo_relative_path"] == "src/pkg/__init__.py"
    assert len(entry["sha256"]) == 64
    assert artifact.machine_paths(back) == []


# ---------------------------------------------------------------------------
# P3 / P4 / P5 -- the discriminator both ways
# ---------------------------------------------------------------------------


def test_p3_a_repo_relative_path_that_is_not_on_the_tree_is_refused(tmp_path):
    root = _repo(tmp_path)
    payload = {"module_bindings": {"schema": module_bindings.MODULE_BINDINGS_SCHEMA, "bindings": {
        "pkg": {"inside_repo": True, "repo_relative_path": "src/pkg/missing.py", "sha256": "00" * 32},
    }}}
    with pytest.raises(artifact.MachinePathRefused) as exc:
        artifact.write_artifact(root, "reports/x.json", payload)
    assert "not a file in this tree" in str(exc.value)
    assert not (root / "reports" / "x.json").exists()


def test_p3_a_binding_whose_digest_moved_is_refused(tmp_path):
    root = _repo(tmp_path)
    payload = {"module_bindings": {"schema": module_bindings.MODULE_BINDINGS_SCHEMA, "bindings": {
        "pkg": {"inside_repo": True, "repo_relative_path": "src/pkg/__init__.py", "sha256": "00" * 32},
    }}}
    with pytest.raises(artifact.MachinePathRefused) as exc:
        artifact.write_artifact(root, "reports/x.json", payload)
    assert "is not the file this artifact was measured with" in str(exc.value)


def test_p4_pointers_urls_and_labels_are_not_paths(tmp_path):
    root = _repo(tmp_path)
    payload = {
        "pointer": "/hard_stops/E1_scaling/status",
        "url": "https://huggingface.co/amazon/chronos-2/raw/29ec3766/README.md",
        "posix_label": "/corridor/suez/h7",
        "relpath": "reports/benchmarks/x.json",
        "windows_label": "C:not-a-path",
        "nested": [{"pointer": "/a/b"}, "/x/y/z"],
    }
    assert artifact.machine_paths(payload) == []
    out = artifact.write_artifact(root, "reports/ok.json", payload)
    assert json.loads(out.read_text()) == payload


def test_p5_an_existing_absolute_path_under_no_listed_root_is_refused(tmp_path):
    root = _repo(tmp_path)
    exists = str(tmp_path)  # /private/var/folders/... on macOS, /tmp/... on Linux
    payload = {"cache_dir": exists}
    # Prove the existence signal on its own: with the roots list emptied the
    # path is still refused because it EXISTS on this machine.
    assert artifact.machine_paths(payload, roots=()) == [("/cache_dir", exists)]
    with pytest.raises(artifact.MachinePathRefused):
        artifact.write_artifact(root, "reports/x.json", payload, roots=())


# ---------------------------------------------------------------------------
# P6 -- mlkit records itself by identity, never by directory
# ---------------------------------------------------------------------------


def test_p6_build_identity_carries_no_absolute_path_and_the_stamp_is_the_digest():
    ident = identity.build_identity()
    d = ident.to_dict()
    assert "root" not in d
    assert d["root_kind"] in ("site-packages", "checkout", "other")
    assert d["root_name"] == "resilient_mlkit"
    assert artifact.machine_paths(d) == []
    assert not any(isinstance(v, str) and v.startswith("/") for v in d.values())
    assert not any(tok.startswith("/") or tok.startswith("`/") for tok in ident.context_line().split())
    assert ident.stamp == f"{d['version']}+src.{(d['source_sha256'] or 'unknown')[:12]}"


def test_p6_a_file_url_in_vcs_reason_is_rendered_as_a_kind_not_a_directory():
    ident = identity.build_identity()
    assert "file:///" not in ident.vcs_reason
    assert "/private/" not in ident.vcs_reason and "/Users/" not in ident.vcs_reason


# ---------------------------------------------------------------------------
# P7 -- check-not-dead: the discriminator is what refuses
# ---------------------------------------------------------------------------


def test_p7_with_the_roots_emptied_and_existence_disabled_the_offender_is_written(tmp_path):
    root = _repo(tmp_path)
    assert artifact.machine_paths(OFFENDER_SHAPE, check_exists=False, roots=()) == []
    out = artifact.write_artifact(
        root, "reports/dead.json", OFFENDER_SHAPE, check_exists=False, roots=(),
    )
    assert out.exists()


# ---------------------------------------------------------------------------
# module_bindings.record refuses at the yield site
# ---------------------------------------------------------------------------


def test_record_refuses_a_module_without_a_file_and_a_repo_local_module_outside_the_tree(tmp_path):
    root = _repo(tmp_path)
    ghost = types.ModuleType("ghost")
    with pytest.raises(module_bindings.ModuleBindingRefusal):
        module_bindings.record([ghost], root=root)
    outside = types.ModuleType("outside")
    outside.__file__ = str(tmp_path / "elsewhere.py")
    (tmp_path / "elsewhere.py").write_text("y = 2\n")
    with pytest.raises(module_bindings.ModuleBindingRefusal):
        module_bindings.record([outside], root=root, repo_local=["outside"])
    # Out of repo and NOT declared repo-local: recorded by distribution
    # identity, with no path at all.
    doc = module_bindings.record([outside], root=root)
    entry = doc["bindings"]["outside"]
    assert entry["inside_repo"] is False and entry["repo_relative_path"] is None
    assert "why_no_repo_relative_path" in entry and len(entry["sha256"]) == 64
    assert module_bindings.problems(doc, root=root) == []


# ---------------------------------------------------------------------------
# P8 -- THE PRODUCING SCRIPT GOES THROUGH THE WRITER
#
# The adjudicator's finding, 2026-09-05: `reports/R13_FLEET_DRIVE_AT_MOVED_MAINS.json`
# -- this stack's OWN drive of record for M-2, committed AFTER M-5 -- carried
# four machine paths, because `scripts/r13_fleet_drive.py` wrote it with a bare
# `Path.write_text`. A refusal the producing script walks around is theatre.
# These hold the drive to its own writer.
# ---------------------------------------------------------------------------

DRIVE_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "r13_fleet_drive.py"


def _load_drive():
    import importlib.util

    spec = importlib.util.spec_from_file_location("_r13_fleet_drive_under_test", DRIVE_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _tree(tmp_path: Path, name: str) -> Path:
    """A minimal git worktree R13 can be driven over."""
    import subprocess

    root = tmp_path / name
    (root / "src").mkdir(parents=True)
    (root / "src" / "m.py").write_text("X = 1\n")
    (root / "CLAUDE.md").write_text("# rules\n\nNothing quoted here.\n")
    for args in (
        ["init", "-q", "-b", "main"],
        ["-c", "user.name=t", "-c", "user.email=t@t", "add", "-A"],
        ["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "seed"],
    ):
        subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)
    return root


def test_p8_the_drive_holds_no_bare_write_text_of_its_record():
    """The defect, held down at the source: no `Path.write_text` of an output."""
    body = DRIVE_SCRIPT.read_text()
    assert "out.write_text(" not in body
    assert "out_md.write_text(" not in body
    assert "artifact.write_artifact(" in body
    assert "artifact.write_text_artifact(" in body


def test_p8_silent_arm_the_repaired_drive_writes_a_record_with_no_machine_path(tmp_path):
    drive = _load_drive()
    tree = _tree(tmp_path, "resilient-fray")
    out = tmp_path / "out" / "record.json"
    out_md = tmp_path / "out" / "record.md"
    rc = drive.main(["--tree", f"fray={tree}", "--out", str(out), "--out-md", str(out_md)])
    assert rc == 0
    record = json.loads(out.read_text())
    assert artifact.machine_paths(record) == []
    assert artifact.machine_paths_in_text(out_md.read_text()) == []
    # The row names the tree by a resolvable sha and a basename, never a path.
    row = record["rows"][0]
    assert "path" not in row
    assert row["tree_name"] == "resilient-fray"
    assert len(row["git_sha"]) == 40


def test_p8_fires_arm_a_machine_path_in_the_record_is_refused_and_nothing_is_written(tmp_path):
    drive = _load_drive()
    tree = _tree(tmp_path, "resilient-fray")
    out = tmp_path / "out" / "record.json"
    out_md = tmp_path / "out" / "record.md"
    rc = drive.main([
        "--tree", f"fray={tree}",
        "--out", str(out), "--out-md", str(out_md),
        "--control-reintroduce-machine-path", str(tmp_path),
    ])
    assert rc == 2
    assert not out.exists()
    assert not out_md.exists()


# ---------------------------------------------------------------------------
# P9 -- the RENDERING is refused on the same terms as the record
# ---------------------------------------------------------------------------


def test_p9_a_directory_inside_a_markdown_table_cell_is_refused(tmp_path):
    root = _repo(tmp_path)
    text = "| tree | path |\n|---|---|\n| fray | `/private/tmp/claude-501/x/scratchpad/fray` |\n"
    found = artifact.machine_paths_in_text(text)
    assert [v for _, v in found] == ["/private/tmp/claude-501/x/scratchpad/fray"]
    with pytest.raises(artifact.MachinePathRefused):
        artifact.write_text_artifact(root, "reports/x.md", text)
    assert not (root / "reports" / "x.md").exists()


def test_p9_json_pointers_and_urls_in_prose_stay_silent(tmp_path):
    root = _repo(tmp_path)
    text = (
        "- pointer `/hard_stops/e1/gain` is fine\n"
        "- see https://example.com/a/b and `docs/allowlist.yaml`\n"
    )
    assert artifact.machine_paths_in_text(text) == []
    assert artifact.write_text_artifact(root, "reports/ok.md", text).read_text() == text


# ---------------------------------------------------------------------------
# P10 -- mlkit's OWN identity carries no directory in any field
#
# `to_dict()` dropped `root` for M-5, but `vcs_reason` and `unavailable` are
# also fields of it and two of their branches interpolated the absolute package
# root. Both travel inside `mlkit_build` into every artifact an adopter stamps,
# which is how mlkit's own writer came to refuse mlkit's own identity.
# ---------------------------------------------------------------------------


def test_p10_root_as_kind_names_a_kind_and_a_basename_never_a_directory(tmp_path):
    src = tmp_path / "src" / "resilient_mlkit"
    src.mkdir(parents=True)
    (tmp_path / "pyproject.toml").write_text("[project]\n")
    named = identity.root_as_kind(src)
    assert named == "`resilient_mlkit` (checkout)"
    assert str(tmp_path) not in named
    assert artifact.machine_paths_in_text(named) == []


def test_p10_no_identity_field_names_a_directory_on_any_branch(tmp_path):
    """Every reason branch, forced, not merely the one this machine takes."""
    absent = tmp_path / "no-such-tree" / "resilient_mlkit"
    for reason in (
        identity.digest_tree(absent)[2],
        identity._vcs_of_installed_dist(absent)[2],
        identity.one_tree_or_reason(absent),
    ):
        assert artifact.machine_paths_in_text(reason) == [], reason
        assert str(tmp_path) not in reason

    d = identity.build_identity().to_dict()
    for key, value in d.items():
        if isinstance(value, str):
            assert artifact.machine_paths_in_text(value) == [], f"{key}: {value}"
