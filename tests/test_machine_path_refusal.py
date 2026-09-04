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
