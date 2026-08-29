"""R1, R2, R4, R6, R7, R9 controls: the readiness checks that had no pair.

R3, R5, R10, R11 and R12 already have control-pair suites of their own. These
six did not, and two of them are the kind whose silence is the whole risk:

* **R4 owns its tolerance.** `min(case_tol, MAX_METRIC_TOL)` is the line that
  stops a repo passing a known-answer test by declaring a loose enough
  tolerance, which is loosening a threshold with extra steps. The pair is a
  binding asking for 1.0 and being held to 1e-6 anyway, against a binding
  asking for something stricter and being honoured.

* **R7 scans before it reports NA.** A repo with no `[remote]` section but a
  config file pointing at us-east-1 has a defect that is measurable right now,
  and returning NA would report a found defect as unmeasurable. The pair is
  strays-with-no-remote firing, against no-strays-and-no-remote being NA.

R2 gets a pair of a different kind: it delegates to T2 and re-labels the result,
so what has to be proven is that the verdict travels and the check id does not.
"""

from __future__ import annotations

import subprocess
import textwrap
from pathlib import Path
from typing import Any

import yaml

from resilient_mlkit.checks import RunContext
from resilient_mlkit.checks.readiness import (
    MAX_METRIC_TOL,
    REQUIRED_REGION,
    r1_checkpoint_provenance,
    r2_overfit,
    r4_metric_known_answer,
    r6_determinism,
    r7_remote_parity,
    r9_licence_gate,
)
from resilient_mlkit.core import policy
from resilient_mlkit.core.repo import Repo
from resilient_mlkit.core.result import Status

#: Unique per fixture; see the note in tests/test_r3_blocked_splits.py.
_SERIAL = iter(range(10_000))


def _repo(
    tmp_path,
    binding: str,
    fn_name: str,
    body: str,
    *,
    declare: bool = True,
    extra_toml: str = "",
) -> Repo:
    module = f"r_bindings_{next(_SERIAL)}"
    (tmp_path / f"{module}.py").write_text(textwrap.dedent(body))
    (tmp_path / ".mlkit").mkdir(parents=True, exist_ok=True)
    toml = '[repo]\nname = "fixturerepo"\n' + extra_toml
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


# -- R1: every checkpoint has URI, hash and licence -----------------------


def _run_r1(tmp_path, body: str, *, declare: bool = True):
    return _run(
        tmp_path, r1_checkpoint_provenance, "checkpoint_provenance",
        "checkpoint_provenance", body, declare=declare,
    )


_R1_COMPLETE = """
        def checkpoint_provenance():
            return {
                "backbone": {
                    "uri": "s3://weights/backbone.safetensors",
                    "sha256": "0" * 64,
                    "licence_url": "https://example.invalid/LICENSE",
                }
            }
    """


def test_negative_control_a_fully_provenanced_checkpoint_is_silent(tmp_path):
    """SILENT: URI, digest and licence all present."""
    result = _run_r1(tmp_path, _R1_COMPLETE)
    assert result.status is Status.PASS
    assert result.evidence["checkpoints"] == 1


def test_positive_control_a_checkpoint_with_no_digest_is_refused(tmp_path):
    """FIRES: a URI without a hash names a file, not a specific file. Weights at
    a moving pointer are the shape rule 15 exists for."""
    result = _run_r1(tmp_path, _R1_COMPLETE.replace('"sha256": "0" * 64,', ""))
    assert result.status is Status.FAIL
    assert "backbone missing sha256" in result.reason


def test_positive_control_a_checkpoint_with_no_licence_URL_is_refused(tmp_path):
    """FIRES: and by the same branch, so the check is reading each field rather
    than testing that the record is non-empty."""
    result = _run_r1(tmp_path, _R1_COMPLETE.replace('"https://example.invalid/LICENSE"', '""'))
    assert result.status is Status.FAIL
    assert "licence_url" in result.reason


def test_positive_control_no_checkpoints_declared_is_refused_not_passed(tmp_path):
    """FIRES: "every checkpoint has provenance" is vacuously true of none."""
    result = _run_r1(
        tmp_path,
        """
        def checkpoint_provenance():
            return {}
        """,
    )
    assert result.status is Status.FAIL
    assert "no checkpoints declared" in result.reason


def test_an_undeclared_provenance_binding_is_NA(tmp_path):
    result = _run_r1(tmp_path, _R1_COMPLETE, declare=False)
    assert result.status is Status.NA
    assert "no 'checkpoint_provenance' binding declared" in result.reason


# -- R2: the delegation must carry the verdict, not the identity ----------


def _run_r2(tmp_path, body: str, *, declare: bool = True):
    return _run(tmp_path, r2_overfit, "overfit_one_batch", "overfit", body, declare=declare)


def test_R2_carries_a_T2_failure_through_under_its_own_check_id(tmp_path):
    """FIRES: R2 re-runs T2 and relabels it. Both halves need proving — that the
    verdict travels, and that the id does not. A relabelled result that kept
    "T2" would land in the readiness table under a triage row and quietly go
    missing from the gate that consumes it."""
    result = _run_r2(
        tmp_path,
        """
        def overfit():
            return [2.40, 2.38, 2.37]
        """,
    )
    assert result.status is Status.FAIL
    assert result.check_id == "R2"
    assert result.phase == "readiness"
    assert "cannot overfit one batch" in result.reason


def test_negative_control_R2_carries_a_T2_pass_through_the_same_way(tmp_path):
    """SILENT: the other half. If R2 failed everything, the test above would
    look identical."""
    result = _run_r2(
        tmp_path,
        """
        def overfit():
            return [2.40, 0.05]
        """,
    )
    assert result.status is Status.PASS
    assert result.check_id == "R2"
    assert result.evidence["loss_last"] == 0.05


def test_R2_reports_NA_when_the_overfit_binding_is_undeclared(tmp_path):
    """FIRES as NA, through the delegation: an unwired probe is not a passed one
    at either check id."""
    result = _run_r2(
        tmp_path,
        """
        def overfit():
            return [1.0, 0.01]
        """,
        declare=False,
    )
    assert result.status is Status.NA
    assert result.check_id == "R2"


# -- R4: mlkit owns the tolerance -----------------------------------------


def _run_r4(tmp_path, body: str, *, declare: bool = True):
    return _run(
        tmp_path, r4_metric_known_answer, "metric_known_answer",
        "metric_known_answer", body, declare=declare,
    )


def _cases(cases: str) -> str:
    return f"""
        def metric_known_answer():
            return {cases}
    """


def test_negative_control_a_metric_reproducing_its_analytic_value_is_silent(tmp_path):
    """SILENT: agreement to floating-point noise passes."""
    result = _run_r4(
        tmp_path,
        _cases('[{"name": "rmse_of_constant", "computed": 2.0, "expected": 2.0}]'),
    )
    assert result.status is Status.PASS
    assert result.evidence["cases"] == 1
    assert result.evidence["failed"] == 0


def test_positive_control_a_metric_that_disagrees_is_refused(tmp_path):
    """FIRES: a known-answer test compares against an analytic value, so
    anything past noise means the metric is wrong, not imprecise."""
    result = _run_r4(
        tmp_path, _cases('[{"name": "rmse_of_constant", "computed": 2.1, "expected": 2.0}]')
    )
    assert result.status is Status.FAIL
    assert "rmse_of_constant" in result.reason
    assert "got 2.1, expected 2" in result.reason


def test_positive_control_a_binding_cannot_widen_its_own_tolerance(tmp_path):
    """FIRES: the branch that makes R4 a gate rather than a formality.

    The case declares `tol: 1.0`, under which its own error of 0.1 would pass
    comfortably. `min(case_tol, MAX_METRIC_TOL)` clamps it to 1e-6 and the case
    fires anyway. A subject that sets its own pass mark sets no pass mark, and
    this is the control that says so — the tolerance the reason prints is
    mlkit's, not the binding's.
    """
    result = _run_r4(
        tmp_path,
        _cases(
            '[{"name": "loose", "computed": 2.1, "expected": 2.0, "tol": 1.0}]'
        ),
    )
    assert result.status is Status.FAIL
    assert f"tol {MAX_METRIC_TOL:g}" in result.reason


def test_positive_control_a_binding_asking_for_something_stricter_is_honoured(tmp_path):
    """FIRES on the other side of the clamp, which is what makes it a clamp and
    not a ceiling-and-floor: a binding may be stricter than mlkit, so a case
    declaring 1e-12 fires on an error of 1e-9 that mlkit alone would allow."""
    result = _run_r4(
        tmp_path,
        _cases('[{"name": "strict", "computed": 2.000000001, "expected": 2.0, "tol": 1e-12}]'),
    )
    assert result.status is Status.FAIL
    assert "strict" in result.reason


def test_negative_control_an_error_inside_both_tolerances_is_silent(tmp_path):
    """SILENT: the pair for both clamp tests above. Without it, "R4 fires when
    the tolerance is loose" is indistinguishable from "R4 fires"."""
    result = _run_r4(
        tmp_path,
        _cases('[{"name": "tiny", "computed": 2.0000000000001, "expected": 2.0}]'),
    )
    assert result.status is Status.PASS


def test_positive_control_a_case_with_no_expected_value_is_refused(tmp_path):
    """FIRES: a known-answer case with no known answer is not a case."""
    result = _run_r4(tmp_path, _cases('[{"name": "half_a_case", "computed": 2.0}]'))
    assert result.status is Status.FAIL
    assert "missing 'computed' or 'expected'" in result.reason


def test_positive_control_no_cases_at_all_is_refused(tmp_path):
    """FIRES: zero known-answer cases satisfies "all cases agree" vacuously."""
    result = _run_r4(tmp_path, _cases("[]"))
    assert result.status is Status.FAIL
    assert "no known-answer cases declared" in result.reason


# -- R6: same seed, byte-identical result ---------------------------------


def _run_r6(tmp_path, body: str, *, declare: bool = True):
    return _run(
        tmp_path, r6_determinism, "deterministic_run", "deterministic_run", body, declare=declare
    )


def test_negative_control_a_deterministic_run_is_silent(tmp_path):
    """SILENT: the same seed twice, the same result twice."""
    result = _run_r6(
        tmp_path,
        """
        def deterministic_run(seed):
            import random
            rng = random.Random(seed)
            return [rng.random() for _ in range(4)]
        """,
    )
    assert result.status is Status.PASS
    assert result.evidence["seed"] == 1234


def test_positive_control_a_run_that_drifts_between_calls_is_refused(tmp_path):
    """FIRES: the defect R6 exists for, built as an unseeded global rather than
    as a deliberate difference — a module-level counter is what an unreset
    dataloader or a global RNG actually looks like in a training script."""
    result = _run_r6(
        tmp_path,
        """
        _CALLS = [0]

        def deterministic_run(seed):
            _CALLS[0] += 1
            return {"seed": seed, "call": _CALLS[0]}
        """,
    )
    assert result.status is Status.FAIL
    assert "not reproducible" in result.reason
    assert result.evidence["first"] != result.evidence["second"]


def test_positive_control_a_binding_that_rejects_the_seed_is_a_FAIL(tmp_path):
    """FIRES: R6 calls `fn(seed=1234)`, so a run that cannot be told which seed
    to use cannot be shown to be reproducible at all."""
    result = _run_r6(
        tmp_path,
        """
        def deterministic_run():
            return [1, 2, 3]
        """,
    )
    assert result.status is Status.FAIL
    assert "TypeError" in result.reason


# -- R7: us-west-2, pinned image, one entrypoint --------------------------


_PINNED = (
    f"123456789012.dkr.ecr.{REQUIRED_REGION}.amazonaws.com/trainer"
    "@sha256:" + "0" * 64
)


def _remote_repo(tmp_path, *, remote: dict[str, str] | None, stray_config: str | None) -> Repo:
    (tmp_path / ".mlkit").mkdir(parents=True, exist_ok=True)
    toml = '[repo]\nname = "fixturerepo"\n'
    if remote is not None:
        toml += "\n[remote]\n" + "".join(f'{k} = "{v}"\n' for k, v in remote.items())
    (tmp_path / ".mlkit" / "repo.toml").write_text(toml)
    if stray_config is not None:
        (tmp_path / "config").mkdir(parents=True, exist_ok=True)
        (tmp_path / "config" / "train.yaml").write_text(stray_config)
    return Repo(name="fixturerepo", path=tmp_path)


def test_negative_control_a_pinned_us_west_2_remote_is_silent(tmp_path):
    """SILENT: declared region correct, image pinned by digest, in-region."""
    repo = _remote_repo(
        tmp_path,
        remote={"region": REQUIRED_REGION, "image": _PINNED},
        stray_config=f"region: {REQUIRED_REGION}\n",
    )
    result = r7_remote_parity(repo, _ctx(tmp_path))
    assert result.status is Status.PASS
    assert result.evidence["stray_region_refs"] == 0


def test_positive_control_a_foreign_region_in_config_fires_even_with_no_remote(tmp_path):
    """FIRES: the ordering that matters. The scan runs BEFORE the NA branch, so
    a repo that has declared no [remote] at all still reports the defect it
    actually has. Returning NA here would report a found defect as unmeasurable
    (CLAUDE.md rule 16)."""
    repo = _remote_repo(tmp_path, remote=None, stray_config="region: us-east-1\n")
    result = r7_remote_parity(repo, _ctx(tmp_path))
    assert result.status is Status.FAIL
    assert "us-east-1" in result.reason
    assert result.evidence["stray_region_refs"] == 1


def test_negative_control_no_remote_and_no_strays_is_NA_not_a_pass(tmp_path):
    """SILENT for the FAIL, and the pair for the test above: with nothing
    declared and nothing found, parity is unmeasured — and the reason says both
    halves, so the row cannot be read as "parity confirmed"."""
    repo = _remote_repo(tmp_path, remote=None, stray_config=f"region: {REQUIRED_REGION}\n")
    result = r7_remote_parity(repo, _ctx(tmp_path))
    assert result.status is Status.NA
    assert "no [remote] section" in result.reason
    assert "parity itself is unmeasured" in result.reason


def test_positive_control_an_unpinned_image_is_refused(tmp_path):
    """FIRES: a tag moves. `:latest` in a training plane is a run nobody can
    reproduce, and the digest is what makes the image an identity."""
    repo = _remote_repo(
        tmp_path,
        remote={
            "region": REQUIRED_REGION,
            "image": f"123456789012.dkr.ecr.{REQUIRED_REGION}.amazonaws.com/trainer:latest",
        },
        stray_config=None,
    )
    result = r7_remote_parity(repo, _ctx(tmp_path))
    assert result.status is Status.FAIL
    assert "not pinned by digest" in result.reason


def test_positive_control_a_digest_pinned_image_in_the_wrong_registry_is_refused(tmp_path):
    """FIRES: pinned is not the same as in-region. A cross-region pull is a
    defect under rule 16 however immutable the digest is."""
    repo = _remote_repo(
        tmp_path,
        remote={
            "region": REQUIRED_REGION,
            "image": "123456789012.dkr.ecr.us-east-1.amazonaws.com/trainer@sha256:" + "0" * 64,
        },
        stray_config=None,
    )
    result = r7_remote_parity(repo, _ctx(tmp_path))
    assert result.status is Status.FAIL
    assert "registry" in result.reason


def test_positive_control_a_declared_foreign_region_is_refused(tmp_path):
    """FIRES: and the remedy is never to change the policy to match the config."""
    repo = _remote_repo(
        tmp_path, remote={"region": "eu-west-1", "image": _PINNED}, stray_config=None
    )
    result = r7_remote_parity(repo, _ctx(tmp_path))
    assert result.status is Status.FAIL
    assert "is not us-west-2" in result.reason


# -- R9: the licence gate, and NOTICE.md drift ----------------------------


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True)


def _entry(source_id: str, status: str, **extra: Any) -> dict:
    return {
        "id": source_id,
        "kind": "data",
        "status": status,
        "licence_url": "https://example.invalid/licence",
        "retrieval_date": "2026-08-29",
        **extra,
    }


def _gate_repo(
    tmp_path,
    *,
    entries: list[dict],
    sources: list[str],
    notice: str | None = "generated",
    sign: bool = True,
) -> Repo:
    """A committed repo with an allowlist, a manifest and a NOTICE.md.

    `notice="generated"` renders the correct file, `None` writes none, and any
    other string is written verbatim as a stale one.
    """
    root = tmp_path / "resilient-fixturerepo"
    (root / ".mlkit").mkdir(parents=True)
    (root / "docs").mkdir(parents=True)
    (root / "manifest.yaml").write_text(yaml.safe_dump({"sources": sources}))
    (root / ".mlkit" / "repo.toml").write_text(
        '[repo]\nname = "fixturerepo"\n\n[manifest]\npath = "manifest.yaml"\n'
    )
    repo = Repo(name="fixturerepo", path=root)

    parsed_entries = {
        e["id"]: policy.Entry(
            id=e["id"], kind=e["kind"], status=e["status"], licence_url=e["licence_url"],
            retrieval_date=e["retrieval_date"], attribution=e.get("attribution", ""),
        )
        for e in entries
    }
    doc: dict = {"entries": entries}
    if sign:
        doc["signature"] = {
            "signed": True,
            "signed_by": "signatory@example.invalid",
            "signed_at": "2026-08-29",
            "entries_sha256": policy.entries_digest(parsed_entries),
        }
    (root / policy.ALLOWLIST_RELPATH).write_text(yaml.safe_dump(doc))

    if notice is not None:
        allowlist = policy.load(repo)
        text = policy.render_notice(repo, allowlist) if notice == "generated" else notice
        (root / "NOTICE.md").write_text(text)

    _git(tmp_path, "init", "-q", str(root))
    _git(root, "config", "user.email", "t@example.invalid")
    _git(root, "config", "user.name", "t")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "fixture")
    return repo


def test_negative_control_a_clean_signed_manifest_with_a_current_NOTICE_is_silent(tmp_path):
    """SILENT: the one shape that passes R9.

    The generated half of the NOTICE pair shares `render_notice` with the check,
    so this asserts drift-freedom and not renderer correctness — which is the
    honest limit of what a same-process fixture can claim. The FIRES half below
    is where the check earns its keep.
    """
    repo = _gate_repo(
        tmp_path, entries=[_entry("sentinel2_l2a", "ALLOWED")], sources=["sentinel2_l2a"]
    )
    result = r9_licence_gate(repo, _ctx(tmp_path))
    assert result.status is Status.PASS
    assert result.evidence["allowlist_signed"] is True


def test_positive_control_an_EVAL_ONLY_source_in_a_training_manifest_is_refused(tmp_path):
    """FIRES: the branch a presence-only gate would miss entirely. The source IS
    on the allowlist; what it is not is licensed for training."""
    repo = _gate_repo(
        tmp_path, entries=[_entry("commercial_panel", "EVAL-ONLY")], sources=["commercial_panel"]
    )
    result = r9_licence_gate(repo, _ctx(tmp_path))
    assert result.status is Status.FAIL
    assert "EVAL-ONLY source(s) present in a training manifest" in result.reason


def test_positive_control_a_BLOCKED_source_outranks_the_EVAL_ONLY_branch(tmp_path):
    """FIRES: and reports BLOCKED specifically, so two different licence
    determinations do not collapse into one message."""
    repo = _gate_repo(
        tmp_path, entries=[_entry("scraped_panel", "BLOCKED")], sources=["scraped_panel"]
    )
    result = r9_licence_gate(repo, _ctx(tmp_path))
    assert result.status is Status.FAIL
    assert "BLOCKED source(s)" in result.reason


def test_positive_control_a_stale_NOTICE_is_refused_and_names_the_remedy(tmp_path):
    """FIRES: the drift branch. NOTICE.md is generated so it cannot wander away
    from the allowlist it reflects, and a hand-edited one is exactly that
    wandering. The reason names `mlkit notice`, which is the remedy."""
    repo = _gate_repo(
        tmp_path,
        entries=[_entry("sentinel2_l2a", "ALLOWED", attribution="Contains Copernicus data")],
        sources=["sentinel2_l2a"],
        notice="# NOTICE\n\nhand-edited, and no longer what the allowlist says\n",
    )
    result = r9_licence_gate(repo, _ctx(tmp_path))
    assert result.status is Status.FAIL
    assert "stale" in result.reason
    assert "mlkit notice" in result.reason


def test_positive_control_an_absent_NOTICE_is_refused_separately_from_a_stale_one(tmp_path):
    """FIRES, by its own branch: "never generated" and "generated and drifted"
    are different states of the same obligation."""
    repo = _gate_repo(
        tmp_path,
        entries=[_entry("sentinel2_l2a", "ALLOWED")],
        sources=["sentinel2_l2a"],
        notice=None,
    )
    result = r9_licence_gate(repo, _ctx(tmp_path))
    assert result.status is Status.FAIL
    assert "NOTICE.md is absent" in result.reason


def test_a_structurally_defective_allowlist_entry_is_refused_before_anything_else(tmp_path):
    """FIRES: an entry with no retrieval date is not an entry. "It was open when
    I looked" is only defensible if you recorded when you looked."""
    repo = _gate_repo(
        tmp_path,
        entries=[_entry("sentinel2_l2a", "ALLOWED", retrieval_date="")],
        sources=["sentinel2_l2a"],
        sign=False,
    )
    result = r9_licence_gate(repo, _ctx(tmp_path))
    assert result.status is Status.FAIL
    assert "structurally invalid" in result.reason
    assert "retrieval_date is missing" in result.reason


def test_a_clean_manifest_under_an_unsigned_allowlist_is_ESCALATED(tmp_path):
    """FIRES as ESCALATED, not PASS: the signature is the determination, and its
    absence routes the repo to AWAITING-SIGNOFF rather than to a run."""
    repo = _gate_repo(
        tmp_path,
        entries=[_entry("sentinel2_l2a", "ALLOWED")],
        sources=["sentinel2_l2a"],
        sign=False,
    )
    result = r9_licence_gate(repo, _ctx(tmp_path))
    assert result.status is Status.ESCALATED
    assert "unsigned" in result.reason


def test_an_empty_manifest_is_NA_because_a_gate_over_nothing_measures_nothing(tmp_path):
    """FIRES as NA: declaring no data is the one way to make a licence gate
    meaningless, and it is explicitly not a pass."""
    repo = _gate_repo(tmp_path, entries=[_entry("sentinel2_l2a", "ALLOWED")], sources=[])
    result = r9_licence_gate(repo, _ctx(tmp_path))
    assert result.status is Status.NA
    assert "measures nothing" in result.reason
