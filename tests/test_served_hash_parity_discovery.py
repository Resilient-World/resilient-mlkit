"""SV-4-PARITY-DISCOVERY — the scanner must see both pin shapes, and stay silent.

``scripts/verify_served_hash_parity.py`` accepted exactly one shape: a JSON
under ``models/`` with a top-level ``artifact_sha256``. Three repos pin their
champion differently, and the scanner rendered each of them ``NA`` with the
reason *"this repo serves nothing hash-pinned yet"* — a claim about the repo it
had never measured, and which was false for all three:

* arabica ``models/yield_model_of_record/model.json`` — nested ``artifact.sha256``
* torrent ``models/hydrology_ridge/model.json``       — nested ``artifact.sha256``
* surge   ``data/model_registry/per_lead_anchor_ols/model.json`` — nested, and
  under a root the scanner never visited

A false NA is worse than a miss. It occupies the row where the finding would
have gone and reads as a settled fact.

Every test below builds its own fixture repo on a temp path. No repo in the
portfolio is read by this file, and nothing is written outside ``tmp_path``.

The pairs:

* **kind** — a self-hashing record and a sidecar-pinning record are discovered,
  and each is labelled with what it actually pins. The two are never merged:
  a sidecar digest covers the file it points at and leaves the record itself
  unpinned, which is a weaker property than a self-hash and must not render
  alike.
* **mismatch** — altering the referenced bytes flips a sidecar row to
  ``DIFFER`` (positive); leaving them alone keeps it ``MATCH`` (negative). Same
  for a self-hash and a tampered field.
* **silence** — a repo carrying neither shape stays ``NA``, with a reason that
  says what was searched for rather than what the repo serves, and the run
  exits nonzero because nothing was compared. A scanner that cannot stay silent
  where NA is correct measures nothing.
* **unresolvable** — a sidecar pinning a file that is not there is ``NA``, not
  ``MATCH`` and not ``DIFFER``. There are no bytes, so the digest is neither
  equal to them nor different from them.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from resilient_mlkit.core.served import canonical_payload_sha256, seal

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "verify_served_hash_parity.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("verify_served_hash_parity", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


parity = _load_script()


# -- fixtures -------------------------------------------------------------


def _repo(root: Path, name: str) -> Path:
    path = root / f"resilient-{name}"
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "-C", str(path), "init", "-q"], check=True)
    return path


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _sidecar_record(repo: Path, relpath: str, coef_rel: str, blob: bytes) -> Path:
    """A champion record in the arabica/torrent/surge shape: nested artifact.sha256."""
    import hashlib

    coef = repo / coef_rel
    coef.parent.mkdir(parents=True, exist_ok=True)
    coef.write_bytes(blob)
    record = repo / relpath
    _write_json(record, {
        "model": "fixture_reference",
        "kind": "reference_model_promoted_to_model_of_record",
        "artifact": {
            "path": coef_rel,
            "role": "model_of_record_coefficients",
            "sha256": hashlib.sha256(blob).hexdigest(),
            "bytes": len(blob),
        },
    })
    return record


def _self_hashed_record(repo: Path, relpath: str) -> Path:
    """A champion record in the fray/chokepoint/triage shape: top-level self-hash."""
    record = repo / relpath
    _write_json(record, seal({"model": "fixture_champion", "val_rmse": 0.5}))
    return record


def _run(tmp_path: Path, out: Path) -> tuple[int, dict[str, Any]]:
    code = parity.main(["--root", str(tmp_path), "--out", str(out)])
    return code, json.loads(out.read_text(encoding="utf-8"))


def _rows(report: dict[str, Any], repo: str) -> list[dict[str, Any]]:
    return [r for r in report["rows"] if r["repo"] == repo]


# -- classify: the two kinds, kept apart ----------------------------------


def test_classify_labels_a_self_hash() -> None:
    assert parity.classify(seal({"a": 1})) == parity.KIND_SELF


def test_classify_labels_a_nested_sidecar_pin() -> None:
    payload = {"artifact": {"path": "models/x/coef.npz", "sha256": "ab" * 32}}
    assert parity.classify(payload) == parity.KIND_SIDECAR


def test_classify_ignores_a_record_carrying_neither() -> None:
    """Negative half of discovery: a licence sidecar is not a champion pin."""
    assert parity.classify({"licence": "CC-BY-4.0", "retrieved": "2026-08-14"}) is None
    # An artifact object missing either half is not a pin: a path with no
    # digest pins nothing, and a digest with no path pins nothing findable.
    assert parity.classify({"artifact": {"path": "models/x.npz"}}) is None
    assert parity.classify({"artifact": {"sha256": "ab" * 32}}) is None


def test_the_two_kinds_are_distinct_constants() -> None:
    """They must never collapse: one covers the record, the other only a file."""
    assert parity.KIND_SELF != parity.KIND_SIDECAR
    assert set(parity.KIND_MEANS) == {parity.KIND_SELF, parity.KIND_SIDECAR}


# -- discovery: the roots that were never visited -------------------------


def test_data_model_registry_is_searched(tmp_path: Path) -> None:
    """The surge shape: a registry under data/model_registry/, never visited before.

    This is the regression proper. On the pre-change scanner this repo produced
    'no committed artifact under models/ ... this repo serves nothing
    hash-pinned yet', which was false.
    """
    repo = _repo(tmp_path, "surge")
    _sidecar_record(
        repo,
        "data/model_registry/per_lead_anchor_ols/model.json",
        "data/model_registry/per_lead_anchor_ols/coefficients.npz",
        b"fixture-coefficients",
    )
    code, report = _run(tmp_path, tmp_path / "out.json")
    rows = _rows(report, "surge")
    assert [r["status"] for r in rows] == ["MATCH"]
    assert rows[0]["kind"] == parity.KIND_SIDECAR
    assert rows[0]["pins"] == "data/model_registry/per_lead_anchor_ols/coefficients.npz"
    assert code == 0
    assert "data/model_registry" in report["searched_roots"]


def test_nested_sidecar_pin_under_models_is_seen(tmp_path: Path) -> None:
    """The arabica/torrent shape: models/<name>/model.json, pin nested at artifact.sha256."""
    repo = _repo(tmp_path, "arabica")
    _sidecar_record(
        repo,
        "models/yield_model_of_record/model.json",
        "models/yield_model_of_record/coefficients.json",
        b'{"alpha": 300.0}',
    )
    _, report = _run(tmp_path, tmp_path / "out.json")
    rows = _rows(report, "arabica")
    assert [r["status"] for r in rows] == ["MATCH"]
    assert rows[0]["kind"] == parity.KIND_SIDECAR


def test_counts_are_reported_per_kind(tmp_path: Path) -> None:
    """A self-hash and a sidecar in one run are counted apart, not summed."""
    repo = _repo(tmp_path, "fray")
    _self_hashed_record(repo, "models/county_yield/champion.json")
    other = _repo(tmp_path, "torrent")
    _sidecar_record(
        other, "models/hydrology_ridge/model.json",
        "models/hydrology_ridge/ridge.npz", b"fixture-npz",
    )
    _, report = _run(tmp_path, tmp_path / "out.json")
    assert report["by_kind"][parity.KIND_SELF]["matched"] == 1
    assert report["by_kind"][parity.KIND_SIDECAR]["matched"] == 1
    assert report["artifacts_compared"] == 2


# -- mismatch: the pair ---------------------------------------------------


def test_sidecar_mismatch_is_flagged(tmp_path: Path) -> None:
    """POSITIVE: alter the referenced bytes after the digest was taken -> DIFFER."""
    repo = _repo(tmp_path, "surge")
    _sidecar_record(
        repo,
        "data/model_registry/per_lead_anchor_ols/model.json",
        "data/model_registry/per_lead_anchor_ols/coefficients.npz",
        b"fixture-coefficients",
    )
    coef = repo / "data/model_registry/per_lead_anchor_ols/coefficients.npz"
    coef.write_bytes(b"fixture-coefficients-TAMPERED")

    code, report = _run(tmp_path, tmp_path / "out.json")
    rows = _rows(report, "surge")
    assert [r["status"] for r in rows] == ["DIFFER"]
    assert rows[0]["recorded_sha256"] != rows[0]["recomputed_sha256"]
    assert code == 2


def test_matching_sidecar_passes(tmp_path: Path) -> None:
    """NEGATIVE: the same fixture with the bytes left alone -> MATCH, exit 0."""
    repo = _repo(tmp_path, "surge")
    _sidecar_record(
        repo,
        "data/model_registry/per_lead_anchor_ols/model.json",
        "data/model_registry/per_lead_anchor_ols/coefficients.npz",
        b"fixture-coefficients",
    )
    code, report = _run(tmp_path, tmp_path / "out.json")
    assert [r["status"] for r in _rows(report, "surge")] == ["MATCH"]
    assert code == 0


def test_self_hash_mismatch_is_flagged(tmp_path: Path) -> None:
    """POSITIVE: edit any field of a self-hashing record -> DIFFER.

    The property a self-hash has and a sidecar digest does not: this edit
    touches no coefficient file, and it is still caught.
    """
    repo = _repo(tmp_path, "fray")
    record = _self_hashed_record(repo, "models/county_yield/champion.json")
    payload = json.loads(record.read_text(encoding="utf-8"))
    payload["val_rmse"] = 0.4
    record.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    code, report = _run(tmp_path, tmp_path / "out.json")
    rows = _rows(report, "fray")
    assert [r["status"] for r in rows] == ["DIFFER"]
    assert rows[0]["kind"] == parity.KIND_SELF
    assert code == 2


def test_matching_self_hash_passes(tmp_path: Path) -> None:
    """NEGATIVE: the same record untouched -> MATCH."""
    repo = _repo(tmp_path, "fray")
    record = _self_hashed_record(repo, "models/county_yield/champion.json")
    code, report = _run(tmp_path, tmp_path / "out.json")
    assert [r["status"] for r in _rows(report, "fray")] == ["MATCH"]
    assert code == 0
    payload = json.loads(record.read_text(encoding="utf-8"))
    assert canonical_payload_sha256(payload) == payload["artifact_sha256"]


# -- silence: NA where NA is correct --------------------------------------


def test_repo_with_neither_shape_stays_na(tmp_path: Path) -> None:
    """NEGATIVE control on the whole scanner: it must not invent a MATCH.

    choco and blackout carry neither shape in the real portfolio. NA is the
    correct answer for them, and a scanner that cannot produce one measures
    nothing.
    """
    repo = _repo(tmp_path, "choco")
    _write_json(repo / "models" / "notes.json", {"note": "no champion promoted yet"})
    _write_json(
        repo / "models" / "weights.licence.json",
        {"licence": "CC-BY-4.0", "retrieval_date": "2026-08-14"},
    )
    code, report = _run(tmp_path, tmp_path / "out.json")
    rows = _rows(report, "choco")
    assert [r["status"] for r in rows] == ["NA"]
    assert "MATCH" not in {r["status"] for r in report["rows"]}
    # Nothing was compared anywhere, so the run must not be green.
    assert code == 2
    assert report["artifacts_compared"] == 0


def test_na_reason_states_what_was_searched_not_what_the_repo_serves(
    tmp_path: Path,
) -> None:
    """The false-NA regression, asserted on the text itself.

    The old reason claimed 'this repo serves nothing hash-pinned yet'. The
    scanner does not measure that. It now reports what it looked for and did
    not find, which is the only thing it is in a position to say.
    """
    repo = _repo(tmp_path, "blackout")
    _write_json(repo / "models" / "readme.json", {"status": "no champion"})
    _, report = _run(tmp_path, tmp_path / "out.json")
    reason = _rows(report, "blackout")[0]["reason"]
    assert "serves nothing hash-pinned yet" not in reason
    for root in parity.ARTIFACT_ROOTS:
        assert root in reason
    assert "artifact_sha256" in reason
    assert "not a finding about what the repo serves" in reason


def test_unresolvable_pin_is_na_not_a_match(tmp_path: Path) -> None:
    """A pin to a file that is not there is unmeasured, not equal and not unequal."""
    repo = _repo(tmp_path, "torrent")
    _sidecar_record(
        repo, "models/hydrology_ridge/model.json",
        "models/hydrology_ridge/ridge.npz", b"fixture-npz",
    )
    (repo / "models/hydrology_ridge/ridge.npz").unlink()

    code, report = _run(tmp_path, tmp_path / "out.json")
    row = _rows(report, "torrent")[0]
    assert row["status"] == "NA"
    assert "unresolvable" in row["reason"]
    assert "recomputed_sha256" not in row
    assert report["unresolvable_pins"] == 1
    assert code == 2


def test_absent_repo_is_na_with_its_own_reason(tmp_path: Path) -> None:
    """A repo that is not checked out is a different NA from one carrying no pin."""
    _repo(tmp_path, "fray")
    _self_hashed_record(tmp_path / "resilient-fray", "models/county_yield/champion.json")
    _, report = _run(tmp_path, tmp_path / "out.json")
    absent = _rows(report, "choco")[0]
    assert absent["status"] == "NA"
    assert "not checked out" in absent["reason"]


# -- worktree fallback: adds evidence, never shadows or duplicates --------


def test_worktree_is_consulted_only_when_the_checkout_has_nothing(
    tmp_path: Path,
) -> None:
    """A linked worktree answers where the checkout is silent, and is flagged.

    The relative-path skip test matters here: a worktree at
    ``<repo>/.worktrees/<name>`` has ".worktrees" in every descendant's
    absolute parts, so testing SKIP_PARTS against the absolute path skipped
    every candidate inside it and rendered the repo NA -- the same vanishing
    this change exists to stop.
    """
    repo = _repo(tmp_path, "triage")
    (repo / "seed.txt").write_text("seed", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    subprocess.run(
        ["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t",
         "commit", "-q", "-m", "seed"],
        check=True,
    )
    wt = repo / ".worktrees" / "e029"
    subprocess.run(
        ["git", "-C", str(repo), "worktree", "add", "-q", "-b", "e029", str(wt)],
        check=True,
    )
    _self_hashed_record(wt, "models/weekly_mortality/champion.json")

    code, report = _run(tmp_path, tmp_path / "out.json")
    rows = _rows(report, "triage")
    assert [r["status"] for r in rows] == ["MATCH"]
    assert rows[0]["worktree"] == str(wt.resolve())
    assert "evidence about that worktree" in rows[0]["scope_note"]
    assert code == 0


def test_checkout_wins_and_the_worktree_does_not_duplicate_it(
    tmp_path: Path,
) -> None:
    """NEGATIVE half: with a candidate in the checkout, no worktree row appears.

    Without this, the fallback would double every artifact that exists in both
    trees and inflate `artifacts_compared` without adding evidence.
    """
    repo = _repo(tmp_path, "triage")
    _self_hashed_record(repo, "models/weekly_mortality/champion.json")
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    subprocess.run(
        ["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t",
         "commit", "-q", "-m", "seed"],
        check=True,
    )
    wt = repo / ".worktrees" / "copy"
    subprocess.run(
        ["git", "-C", str(repo), "worktree", "add", "-q", "-b", "copy", str(wt)],
        check=True,
    )

    _, report = _run(tmp_path, tmp_path / "out.json")
    rows = _rows(report, "triage")
    assert len(rows) == 1
    assert "worktree" not in rows[0]


# -- the report itself ----------------------------------------------------


def test_report_carries_what_each_kind_means(tmp_path: Path) -> None:
    """A reader must not have to open the script to know what a MATCH covered."""
    repo = _repo(tmp_path, "arabica")
    _sidecar_record(
        repo, "models/yield_model_of_record/model.json",
        "models/yield_model_of_record/coefficients.json", b"{}",
    )
    _, report = _run(tmp_path, tmp_path / "out.json")
    means = report["by_kind"][parity.KIND_SIDECAR]["means"]
    assert "WEAKER than a self-hash" in means
    assert "core.served.sha256_file" in means


def test_empty_portfolio_is_not_a_pass(tmp_path: Path) -> None:
    """No repo checked out at all: nothing compared, and that is not green."""
    code, report = _run(tmp_path, tmp_path / "out.json")
    assert report["artifacts_compared"] == 0
    assert code == 2


@pytest.mark.parametrize("kind", [parity.KIND_SELF, parity.KIND_SIDECAR])
def test_every_row_names_the_function_that_verified_it(
    tmp_path: Path, kind: str
) -> None:
    repo = _repo(tmp_path, "fray")
    if kind == parity.KIND_SELF:
        _self_hashed_record(repo, "models/county_yield/champion.json")
        expected = "core.served.canonical_payload_sha256"
    else:
        _sidecar_record(
            repo, "models/county_yield/model.json",
            "models/county_yield/coef.npz", b"x",
        )
        expected = "core.served.sha256_file"
    _, report = _run(tmp_path, tmp_path / "out.json")
    assert _rows(report, "fray")[0]["verified_with"] == expected
