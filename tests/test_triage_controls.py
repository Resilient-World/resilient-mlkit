"""T1-T5 controls: does each triage check fire when it should, and stay silent when it should not.

Triage diagnoses; it does not repair. That makes its silence cheap to
misread — a repo that has wired nothing at all produces five NAs, and a repo
whose loader, overfit probe, checkpoints, labels and licences are all sound
produces five PASSes, and the only thing standing between those two readings is
that NA is a different status carrying a reason. Every check below is therefore
paired twice over: the defect FIRES, the legitimate shape is SILENT, and the
undeclared binding is NA rather than either.

Three pairings are worth reading in full.

* **T2's ratio bar, at the boundary and either side of it.** The bar is
  `last > 0.1 * first`, so a loss that falls by exactly ten times passes and one
  that falls by slightly less does not. Without both halves, "cannot overfit one
  batch" is indistinguishable from "cannot pass".

* **T3 on `NOT_A_MODEL`.** The fleet's fail-closed adapter convention writes that
  marker when a model named for a foundation model could not load real pinned
  weights. T3 must refuse it, and must equally accept a status that carries a
  digest suffix after the colon — the two together say T3 reads the state and
  not the string.

* **T5's unsigned-but-clean branch.** A manifest that is entirely ALLOWED under
  an unsigned allowlist is ESCALATED, not PASS. A determination nobody has
  signed is a proposal, and the status is what routes the repo to
  AWAITING-SIGNOFF instead of to a training run.
"""

from __future__ import annotations

import subprocess
import textwrap
from pathlib import Path

from resilient_mlkit.checks import RunContext
from resilient_mlkit.checks.triage import (
    t1_batch_load,
    t2_overfit_one_batch,
    t3_weights_status,
    t4_label_counts,
    t5_licence_coverage,
)
from resilient_mlkit.core import policy
from resilient_mlkit.core.repo import Repo
from resilient_mlkit.core.result import Status

#: Unique per fixture; see the note in tests/test_r3_blocked_splits.py.
_SERIAL = iter(range(10_000))


def _repo(tmp_path, binding: str, fn_name: str, body: str, *, declare: bool = True) -> Repo:
    """A repo on disk whose `binding` is `body`, resolved as the real repos are."""
    module = f"t_bindings_{next(_SERIAL)}"
    (tmp_path / f"{module}.py").write_text(textwrap.dedent(body))
    (tmp_path / ".mlkit").mkdir(parents=True, exist_ok=True)
    toml = '[repo]\nname = "fixturerepo"\n'
    if declare:
        toml += f'\n[bindings]\n{binding} = "{module}:{fn_name}"\n'
    (tmp_path / ".mlkit" / "repo.toml").write_text(toml)
    return Repo(name="fixturerepo", path=tmp_path)


def _ctx(tmp_path) -> RunContext:
    return RunContext(nonce="test-nonce", root=tmp_path, offline=True)


def _run(tmp_path, check, binding: str, fn_name: str, body: str, *, declare: bool = True):
    repo = _repo(tmp_path, binding, fn_name, body, declare=declare)
    try:
        return check(repo, _ctx(tmp_path))
    finally:
        repo.release()


# -- T1: one real batch materialises --------------------------------------


def _run_t1(tmp_path, body: str, *, declare: bool = True):
    return _run(tmp_path, t1_batch_load, "batch", "batch", body, declare=declare)


def test_negative_control_a_shaped_batch_is_silent(tmp_path):
    """SILENT: the happy path, described structurally without importing torch."""
    result = _run_t1(
        tmp_path,
        """
        class _Fake:
            def __init__(self, shape):
                self.shape = shape
                self.dtype = "float32"

        def batch():
            return {"x": _Fake((8, 3, 64, 64)), "y": _Fake((8,))}
        """,
    )
    assert result.status is Status.PASS
    assert result.evidence["batch"]["x"] == "shape=(8, 3, 64, 64) dtype=float32"


def test_positive_control_an_unrecognisable_batch_is_refused(tmp_path):
    """FIRES: a loader that returns something with no shape and no length has
    not materialised a batch, whatever it claims to have returned."""
    result = _run_t1(
        tmp_path,
        """
        def batch():
            return {"x": 7, "y": None}
        """,
    )
    assert result.status is Status.FAIL
    assert "empty or unrecognised" in result.reason


def test_positive_control_a_loader_that_raises_is_the_finding(tmp_path):
    """FIRES: the exception IS the triage result, reported rather than swallowed."""
    result = _run_t1(
        tmp_path,
        """
        def batch():
            raise FileNotFoundError("s3://…/tiles/ is empty")
        """,
    )
    assert result.status is Status.FAIL
    assert "FileNotFoundError" in result.reason


def test_an_undeclared_batch_binding_is_NA_not_a_failure(tmp_path):
    """SILENT for the FAIL specifically: "no loader wired yet" is a different
    distance from a training run than "the loader is broken", and triage exists
    to tell them apart."""
    result = _run_t1(
        tmp_path,
        """
        def batch():
            return {}
        """,
        declare=False,
    )
    assert result.status is Status.NA
    assert "no 'batch' binding declared" in result.reason


# -- T2: the loss must collapse on one batch ------------------------------


def _run_t2(tmp_path, body: str, *, declare: bool = True):
    return _run(
        tmp_path, t2_overfit_one_batch, "overfit_one_batch", "overfit", body, declare=declare
    )


def _losses(values: str) -> str:
    return f"""
        def overfit():
            return {values}
    """


def test_negative_control_a_collapsing_loss_is_silent(tmp_path):
    """SILENT: two orders of magnitude on one batch is a model that is wired."""
    result = _run_t2(tmp_path, _losses("[2.40, 0.81, 0.12, 0.019]"))
    assert result.status is Status.PASS
    assert result.evidence["steps"] == 4
    assert result.evidence["ratio"] < 0.1


def test_positive_control_a_loss_that_barely_moves_is_refused(tmp_path):
    """FIRES: the defect T2 exists for. A model that cannot memorise a single
    batch has a wiring fault, and no learning-rate sweep repairs one."""
    result = _run_t2(tmp_path, _losses("[2.40, 2.30, 2.28, 2.27]"))
    assert result.status is Status.FAIL
    assert "cannot overfit one batch" in result.reason


def test_the_ratio_bar_is_inclusive_at_exactly_ten_times(tmp_path):
    """SILENT at the boundary: the test is `last > 0.1 * first`, so a fall of
    exactly ten times passes."""
    result = _run_t2(tmp_path, _losses("[2.0, 0.2]"))
    assert result.status is Status.PASS
    assert result.evidence["ratio"] == 0.1


def test_the_ratio_bar_fires_just_short_of_ten_times(tmp_path):
    """FIRES on the other side of the same boundary, so the bar is a bar."""
    result = _run_t2(tmp_path, _losses("[2.0, 0.21]"))
    assert result.status is Status.FAIL


def test_positive_control_a_single_loss_value_is_not_a_trajectory(tmp_path):
    """FIRES: one number cannot show a collapse, and is refused rather than
    compared against itself."""
    result = _run_t2(tmp_path, _losses("[0.001]"))
    assert result.status is Status.FAIL
    assert "need a trajectory" in result.reason


def test_positive_control_a_non_positive_initial_loss_is_refused(tmp_path):
    """FIRES: a loss starting at zero makes every ratio meaningless, and would
    otherwise divide the pass criterion by nothing."""
    result = _run_t2(tmp_path, _losses("[0.0, 0.0]"))
    assert result.status is Status.FAIL
    assert "loss is misdefined" in result.reason


# -- T3: declared checkpoints resolve to real pretrained weights ----------


def _run_t3(tmp_path, body: str, *, declare: bool = True):
    return _run(
        tmp_path, t3_weights_status, "checkpoint_status", "checkpoint_status", body, declare=declare
    )


def _statuses(mapping: str) -> str:
    return f"""
        def checkpoint_status():
            return {mapping}
    """


def test_negative_control_loaded_pretrained_checkpoints_are_silent(tmp_path):
    """SILENT: the shape T3 is asking for."""
    result = _run_t3(tmp_path, _statuses('{"backbone": "LOADED_PRETRAINED"}'))
    assert result.status is Status.PASS
    assert result.evidence["checkpoints"] == {"backbone": "LOADED_PRETRAINED"}


def test_negative_control_a_status_carrying_a_digest_suffix_is_silent(tmp_path):
    """SILENT: the state is what precedes the colon, so a status that also
    records which revision loaded is not penalised for saying more."""
    result = _run_t3(
        tmp_path, _statuses('{"backbone": "LOADED_PRETRAINED:sha256:deadbeef"}')
    )
    assert result.status is Status.PASS


def test_positive_control_a_randomly_initialised_checkpoint_is_refused(tmp_path):
    """FIRES: a model named for a foundation model, holding random weights, is
    the failure this check is for."""
    result = _run_t3(tmp_path, _statuses('{"backbone": "RANDOM_INIT"}'))
    assert result.status is Status.FAIL
    assert "backbone=RANDOM_INIT" in result.reason


def test_positive_control_the_NOT_A_MODEL_marker_is_refused(tmp_path):
    """FIRES: the fleet's fail-closed adapter convention writes NOT_A_MODEL when
    real pinned weights could not be loaded. T3 is the check that must not read
    that marker as a checkpoint."""
    result = _run_t3(
        tmp_path,
        _statuses('{"prithvi": "NOT_A_MODEL:no licence file at the pinned revision"}'),
    )
    assert result.status is Status.FAIL
    assert "prithvi=NOT_A_MODEL" in result.reason


def test_positive_control_no_checkpoints_at_all_is_refused_not_passed(tmp_path):
    """FIRES: an empty mapping satisfies "none of them is unpretrained"
    vacuously. Passing a weights gate by declaring no weights is exactly the
    shape R9 refuses for an empty manifest, and T3 refuses it too."""
    result = _run_t3(tmp_path, _statuses("{}"))
    assert result.status is Status.FAIL
    assert "no checkpoints" in result.reason


def test_an_undeclared_checkpoint_binding_is_NA(tmp_path):
    result = _run_t3(tmp_path, _statuses('{"backbone": "LOADED_PRETRAINED"}'), declare=False)
    assert result.status is Status.NA


# -- T4: labels counted from real data ------------------------------------


def _run_t4(tmp_path, body: str, *, declare: bool = True):
    return _run(tmp_path, t4_label_counts, "label_counts", "label_counts", body, declare=declare)


def test_negative_control_observed_label_counts_are_silent(tmp_path):
    result = _run_t4(
        tmp_path,
        """
        def label_counts():
            return {"flood": 412, "no_flood": 8_140}
        """,
    )
    assert result.status is Status.PASS
    assert result.evidence["total"] == 8552


def test_positive_control_an_empty_label_panel_is_refused(tmp_path):
    """FIRES: no observed labels is not a clean label panel."""
    result = _run_t4(
        tmp_path,
        """
        def label_counts():
            return {}
        """,
    )
    assert result.status is Status.FAIL
    assert "no observed labels" in result.reason


def test_positive_control_all_zero_counts_are_refused(tmp_path):
    """FIRES, and it is a distinct branch from the empty one: a panel that
    declares its classes and has found none of them is a pipeline that ran and
    matched nothing, which reads as coverage if it is allowed to pass."""
    result = _run_t4(
        tmp_path,
        """
        def label_counts():
            return {"flood": 0, "no_flood": 0}
        """,
    )
    assert result.status is Status.FAIL
    assert "every observed-label count is zero" in result.reason


# -- T5: every pipeline source is on the signed allowlist -----------------


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True)


def _entry(source_id: str, status: str) -> dict:
    return {
        "id": source_id,
        "kind": "data",
        "status": status,
        "licence_url": "https://example.invalid/licence",
        "retrieval_date": "2026-08-29",
    }


def _licence_repo(tmp_path, *, entries: list[dict] | None, sources: list[str], sign: bool) -> Repo:
    """A git repo with a manifest and, optionally, an allowlist covering it.

    `entries=None` writes no allowlist at all, which is the ESCALATED branch:
    only a human signatory may create one, so its absence is never an agent's
    failure to fix.
    """
    import yaml

    root = tmp_path / "resilient-fixturerepo"
    (root / ".mlkit").mkdir(parents=True)
    (root / "docs").mkdir(parents=True)
    (root / "manifest.yaml").write_text(yaml.safe_dump({"sources": sources}))
    (root / ".mlkit" / "repo.toml").write_text(
        '[repo]\nname = "fixturerepo"\n\n[manifest]\npath = "manifest.yaml"\n'
    )
    repo = Repo(name="fixturerepo", path=root)

    if entries is not None:
        doc: dict = {"entries": entries}
        if sign:
            parsed = policy.Allowlist(path=root / policy.ALLOWLIST_RELPATH)
            parsed.entries = {
                e["id"]: policy.Entry(
                    id=e["id"], kind=e["kind"], status=e["status"],
                    licence_url=e["licence_url"], retrieval_date=e["retrieval_date"],
                    attribution=e.get("attribution", ""),
                )
                for e in entries
            }
            doc["signature"] = {
                "signed": True,
                "signed_by": "signatory@example.invalid",
                "signed_at": "2026-08-29",
                "entries_sha256": policy.entries_digest(parsed.entries),
            }
        (root / policy.ALLOWLIST_RELPATH).write_text(yaml.safe_dump(doc))

    _git(tmp_path, "init", "-q", str(root))
    _git(root, "config", "user.email", "t@example.invalid")
    _git(root, "config", "user.name", "t")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "fixture")
    return repo


def test_an_absent_allowlist_is_ESCALATED_not_a_failure(tmp_path):
    """FIRES as ESCALATED: the allowlist is signed by a human and the agent may
    not create one (CLAUDE.md rule 14). Reporting that as FAIL would invite an
    agent to fix it, which is the one repair that is forbidden."""
    repo = _licence_repo(tmp_path, entries=None, sources=["sentinel2_l2a"], sign=False)
    result = t5_licence_coverage(repo, _ctx(tmp_path))
    assert result.status is Status.ESCALATED
    assert "docs/allowlist.yaml does not exist" in result.reason


def test_positive_control_a_source_absent_from_the_allowlist_is_refused(tmp_path):
    """FIRES: the check's stated job. Training on something that cannot be sold
    must surface on day one, not after the GPU spend."""
    repo = _licence_repo(
        tmp_path,
        entries=[_entry("sentinel2_l2a", "ALLOWED")],
        sources=["sentinel2_l2a", "some_scraped_panel"],
        sign=True,
    )
    result = t5_licence_coverage(repo, _ctx(tmp_path))
    assert result.status is Status.FAIL
    assert "some_scraped_panel" in result.reason
    assert result.evidence["unlisted"] == ["some_scraped_panel"]


def test_positive_control_a_BLOCKED_source_in_the_manifest_is_refused(tmp_path):
    """FIRES, and by a different branch than the one above: listed is not the
    same as permitted, and a check that only looked for presence would pass a
    source whose licence forbids exactly this use."""
    repo = _licence_repo(
        tmp_path,
        entries=[_entry("proprietary_panel", "BLOCKED")],
        sources=["proprietary_panel"],
        sign=True,
    )
    result = t5_licence_coverage(repo, _ctx(tmp_path))
    assert result.status is Status.FAIL
    assert "not ALLOWED" in result.reason
    assert result.evidence["not_allowed"] == {"proprietary_panel": "BLOCKED"}


def test_a_clean_manifest_under_an_UNSIGNED_allowlist_is_ESCALATED(tmp_path):
    """FIRES as ESCALATED, and this is the pairing that matters most in T5.

    Every source is listed ALLOWED. The only thing missing is the signature, and
    the check refuses to let that render like a pass: a determination nobody has
    signed is a proposal. The status is what routes the repo to
    AWAITING-SIGNOFF rather than to a training run.
    """
    repo = _licence_repo(
        tmp_path,
        entries=[_entry("sentinel2_l2a", "ALLOWED")],
        sources=["sentinel2_l2a"],
        sign=False,
    )
    result = t5_licence_coverage(repo, _ctx(tmp_path))
    assert result.status is Status.ESCALATED
    assert "unsigned" in result.reason
    assert result.evidence["allowlist_signed"] is False


def test_negative_control_a_clean_manifest_under_a_SIGNED_allowlist_is_silent(tmp_path):
    """SILENT: the one shape that passes, and the half without which every
    assertion above is consistent with a check that refuses everything."""
    repo = _licence_repo(
        tmp_path,
        entries=[_entry("sentinel2_l2a", "ALLOWED")],
        sources=["sentinel2_l2a"],
        sign=True,
    )
    result = t5_licence_coverage(repo, _ctx(tmp_path))
    assert result.status is Status.PASS
    assert result.evidence["allowlist_signed"] is True
    assert result.evidence["sources"] == 1


def test_an_empty_manifest_is_NA_rather_than_a_vacuous_pass(tmp_path):
    """FIRES as NA: "no sources to check" satisfies "no unlisted source"
    vacuously, and passing a licence gate by declaring no data is the one way to
    make it meaningless."""
    repo = _licence_repo(
        tmp_path, entries=[_entry("sentinel2_l2a", "ALLOWED")], sources=[], sign=True
    )
    result = t5_licence_coverage(repo, _ctx(tmp_path))
    assert result.status is Status.NA
    assert "nothing to licence-check" in result.reason
