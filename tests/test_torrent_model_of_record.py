"""Controls for torrent's repaired ``model_of_record`` column.

Pre-registered in ``reports/MEASUREMENT_EXPORT_PREREGISTRATION.md``, committed
before this file existed. Table TR-1..TR-3. (TR-4, the before/after
regeneration of the whole fleet table, is not a unit test: it is a run, and its
artifacts are under ``reports/fleet_verdicts_torrent_record/``.)

The column was ``Absent`` with the recorded reason that resilient-torrent had
committed no artifact declaring a model of record. That stopped being true when
``models/hydrology_ridge/model.json`` landed on torrent's ``main``. The pair
below is what makes the repair a measurement rather than a swap of one written
claim for another:

* FIRES — repoint the ``record`` artifact at a path that does not exist, and
  the column must come back NA naming what it looked for. The fail-closed
  behaviour the ``Absent`` used to provide by hand must now be provided by the
  reader, or the repair has removed a guard instead of a stale reason.
* SILENT — resolved against the real committed artifact, the column is measured
  and carries the value the artifact actually holds.

TR-3 reads a sibling checkout. It SKIPS, loudly and naming the path, when that
checkout is not present. A test that quietly passes when its subject is absent
is the dead-control defect this fleet has shipped more than once.
"""

from __future__ import annotations

import dataclasses
import json
import subprocess
from pathlib import Path

import pytest

from resilient_mlkit.core.fleet import read_row
from resilient_mlkit.core.repo import Repo
from resilient_mlkit.fleet_adapters import ADAPTERS

#: The artifact alias this repair introduced, and the pointer it reads.
RECORD_ALIAS = "record"
RECORD_PATH = "models/hydrology_ridge/model.json"
RECORD_POINTER = "record:served_model"

TORRENT_ADAPTERS = tuple(a for a in ADAPTERS if a.repo == "torrent")
PORTFOLIO_ROOT = Path(__file__).resolve().parent.parent.parent
TORRENT_ROOT = PORTFOLIO_ROOT / "resilient-torrent"


# --------------------------------------------------------- declaration-only controls
#
# These read no repo. A declaration that has drifted must not wait for a
# checkout to surface.


def test_both_torrent_rows_declare_the_record_artifact() -> None:
    assert len(TORRENT_ADAPTERS) == 2, "torrent's two rows are the subject here"
    for adapter in TORRENT_ADAPTERS:
        assert adapter.artifacts.get(RECORD_ALIAS) == RECORD_PATH, adapter.key
        assert adapter.model_of_record.pointer == RECORD_POINTER, adapter.key


def test_no_torrent_row_still_claims_no_artifact_declares_a_model_of_record() -> None:
    """FIRES on `main` at 0b29e63, where both rows carried exactly that reason."""
    stale = "no committed JSON artifact in resilient-torrent declares a model of record"
    normalised = " ".join(stale.split())
    for adapter in TORRENT_ADAPTERS:
        spec = adapter.model_of_record
        text = " ".join(getattr(spec, "reason", "").split())
        assert normalised not in text, (
            f"{adapter.key}: the Absent reason says torrent has committed no such "
            f"artifact, but {RECORD_PATH} is on its main"
        )


# ----------------------------------------------------------------- TR-1 / TR-2 FIRES


@pytest.fixture()
def torrent_like_repo(tmp_path: Path) -> Repo:
    """A git repo carrying only what these two controls resolve through.

    Deliberately a fixture rather than the real checkout: TR-1 and TR-2 have to
    make the reader MISS, and the way to do that honestly is to control the
    tree, not to reach into a sibling repo and take something away.
    """
    root = tmp_path / "resilient-torrent"
    (root / "models" / "hydrology_ridge").mkdir(parents=True)
    (root / "models" / "hydrology_ridge" / "model.json").write_text(
        json.dumps({"served_model": "ridge_with_observed_discharge", "name": "svc"})
    )
    (root / "reports" / "train").mkdir(parents=True)
    (root / "reports" / "train" / "seed_summary_n8_val.json").write_text(
        json.dumps({"metric": "nse", "mean": 0.22, "split": "val",
                    "config": "cfg.yml", "reference": {"name": "p", "median_nse": 0.26}})
    )
    (root / "reports" / "holdout_reads.jsonl").write_text('{"n": 1}\n')
    for args in (
        ["init", "-q", "-b", "main"],
        ["config", "user.email", "t@example.invalid"],
        ["config", "user.name", "t"],
        ["add", "-A"],
        ["commit", "-qm", "artifacts"],
    ):
        subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)
    return Repo(name="torrent", path=root)


def _melstm_adapter():
    return next(a for a in TORRENT_ADAPTERS if a.entry == "melstm-10ep-n8-val")


def test_tr1_a_record_artifact_that_is_not_there_yields_na_naming_it(
    torrent_like_repo: Repo,
) -> None:
    """FIRES: rot in the pointer is reported, never defaulted around."""
    adapter = _melstm_adapter()
    broken = dataclasses.replace(
        adapter,
        artifacts={**adapter.artifacts, RECORD_ALIAS: "models/no_such_record/model.json"},
    )
    row = read_row(torrent_like_repo, broken)
    assert not row.model_of_record.present, "a missing artifact produced a value"
    assert "models/no_such_record/model.json" in row.model_of_record.na_reason


def test_tr2_a_pointer_the_record_does_not_carry_yields_na_naming_it(
    torrent_like_repo: Repo,
) -> None:
    """FIRES: a key that is not in the artifact is not a value the table may print."""
    from resilient_mlkit.core.fleet import Field

    adapter = _melstm_adapter()
    broken = dataclasses.replace(adapter, model_of_record=Field("record:champion_id"))
    row = read_row(torrent_like_repo, broken)
    assert not row.model_of_record.present
    assert "champion_id" in row.model_of_record.na_reason


def test_tr1_negative_control_the_same_repo_resolves_the_declared_pointer(
    torrent_like_repo: Repo,
) -> None:
    """SILENT: on one input, the rule fires when repointed and not when it is not.

    Same fixture, same adapter, one field changed. Without this half, TR-1 is
    consistent with a reader that reports NA for everything.
    """
    row = read_row(torrent_like_repo, _melstm_adapter())
    assert row.model_of_record.present, row.model_of_record.na_reason
    assert row.model_of_record.value == "ridge_with_observed_discharge"


# ------------------------------------------------------ TR-3 SILENT, against the real repo


def _committed(path: str) -> bool:
    return subprocess.run(
        ["git", "-C", str(TORRENT_ROOT), "cat-file", "-e", f"HEAD:{path}"],
        capture_output=True,
        check=False,
    ).returncode == 0


@pytest.mark.skipif(
    not (TORRENT_ROOT / ".git").exists(),
    reason=f"resilient-torrent is not checked out at {TORRENT_ROOT}",
)
def test_tr3_the_declared_record_is_committed_in_the_real_repo() -> None:
    """SILENT: the artifact the adapter names is in torrent's committed state."""
    assert _committed(RECORD_PATH), (
        f"{RECORD_PATH} does not resolve at HEAD in {TORRENT_ROOT}; the adapter "
        "names an artifact the repo does not carry"
    )


@pytest.mark.skipif(
    not (TORRENT_ROOT / ".git").exists(),
    reason=f"resilient-torrent is not checked out at {TORRENT_ROOT}",
)
def test_tr3_both_real_rows_report_a_measured_model_of_record() -> None:
    """SILENT: the two cells that were NA are read from the artifact."""
    repo = Repo(name="torrent", path=TORRENT_ROOT)
    for adapter in TORRENT_ADAPTERS:
        row = read_row(repo, adapter)
        assert row.model_of_record.present, f"{adapter.key}: {row.model_of_record.na_reason}"
        assert row.model_of_record.value == "ridge_with_observed_discharge", adapter.key
        assert RECORD_PATH in row.model_of_record.source, adapter.key


@pytest.mark.skipif(
    not (TORRENT_ROOT / ".git").exists(),
    reason=f"resilient-torrent is not checked out at {TORRENT_ROOT}",
)
def test_tr3_the_value_is_the_bar_the_sibling_row_measures_against() -> None:
    """SILENT: the ridge is both the record and the `left` side of the row parity.

    This is what makes `served_model` the right pointer rather than `name`: the
    string it yields is the one torrent's own comparison artifact already uses
    for the same object. If they ever diverge, this fails rather than the table
    quietly carrying two names for one model.
    """
    repo = Repo(name="torrent", path=TORRENT_ROOT)
    parity = next(a for a in TORRENT_ADAPTERS if a.entry == "ridge-vs-melstm-val")
    row = read_row(repo, parity)
    assert row.baseline_name.present, row.baseline_name.na_reason
    assert row.model_of_record.value == row.baseline_name.value
