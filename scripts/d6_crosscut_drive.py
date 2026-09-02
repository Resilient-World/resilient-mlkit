"""Drive D6 over the fray fixtures the wave-1 verifier used, and record it.

WHY THIS FILE EXISTS. The wave-1 adversarial verifier of PR #32 drove
`resilient-fray`'s panel through D6 with COUNTY unit keys and recorded
`D6 PASS` — because every county key that happens to appear in more than one
arm made the whole declaration `UNIT_CROSSCUTS_ARMS`, and the crosscut branch
silenced `DEPENDENCE_UNIT_TOO_FINE` unconditionally. The verifier then flipped
ONE val row's `unit_key` to collide with a train row's and the refusal vanished
for the other 1,364. That escape is what `M-D6X-*` closes, and this script is
how it is measured rather than asserted: it runs the SAME shapes at the branch
base and at the branch head and writes a JSON recording each time.

Run it with the repo's own interpreter and no arguments:

    .venv/bin/python scripts/d6_crosscut_drive.py <output.json>

Nothing here fits, trains, reads a holdout, or touches a model repo. Every
fixture is built in a temp directory that is deleted on the way out. No figure
in the output is typed by hand; every one of them is what D6 returned.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from resilient_mlkit import checks as checks_module
from resilient_mlkit.checks import RunContext
from resilient_mlkit.checks import decision as decision_module
from resilient_mlkit.checks.decision import d6_resampling_unit
from resilient_mlkit.core import served as served_module
from resilient_mlkit.core.repo import Repo

# The binding assertion the loop's rules require of every driver. `resilient_mlkit`
# is installed into eight virtualenvs on this machine and an editable install
# elsewhere resolves first if PYTHONPATH is not what it should be, so a recording
# made without this assertion says nothing about the tree under review.
_HERE = Path(__file__).resolve().parent.parent
_EXPECTED = _HERE / "src" / "resilient_mlkit"
for _mod in (served_module, decision_module, checks_module):
    _got = Path(_mod.__file__).resolve()
    assert _EXPECTED in _got.parents, f"{_mod.__name__} resolved to {_got}, not {_EXPECTED}"

# Shapes, in fray's own counts, from the round-8 per-year table
# (253 + 267 + 278 + 285 + 282 = 1365 val rows over five crop years).
VAL_YEARS = {2016: 253, 2017: 267, 2018: 278, 2019: 285, 2020: 282}
TRAIN_YEARS = {2013: 40, 2014: 41, 2015: 42}
TEST_YEARS = {2021: 44, 2022: 45, 2023: 46, 2024: 47, 2025: 48}
ARMS = (("train", TRAIN_YEARS), ("val", VAL_YEARS), ("test", TEST_YEARS))

_BINDING_SRC = '''
import json

ROWS = json.loads({rows!r})
SPLITS = json.loads({splits!r})
DECLARED = json.loads({declared!r})


def resampling_declaration():
    out = dict(DECLARED)
    out["assignment"] = ROWS
    return out


def splits():
    return SPLITS
'''


def fray_rows(unit: str) -> list[dict[str, Any]]:
    """fray's county-year panel, blocked by crop year, resampled by ``unit``.

    ``unit`` is the ONE expression that varies:

    * ``"row"``      — what the run did. Every unit key is unique.
    * ``"crop_year"`` — the repair. The unit is the policy's block.
    * ``"county"``   — what the wave-1 verifier drove. County indices recur
      across arms, so some county keys crosscut and some (the ones only a big
      val year reaches) do not. This is the escape's shape.
    """
    rows: list[dict[str, Any]] = []
    for arm, years in ARMS:
        for year, n in years.items():
            for county in range(n):
                if unit == "row":
                    unit_key: Any = [year, county]
                elif unit == "crop_year":
                    unit_key = year
                elif unit == "county":
                    unit_key = county
                else:  # pragma: no cover - the caller is this file
                    raise ValueError(unit)
                rows.append(
                    {
                        "row_key": [year, county],
                        "arm": arm,
                        "block_key": year,
                        "unit_key": unit_key,
                    }
                )
    return rows


def collide_one_val_row(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The verifier's one-row mutation: ONE val unit key made to collide.

    Exactly one row changes. Under the superseded rule this silenced the
    refusal for the other 1,364 rows, which is the whole finding.
    """
    out = [dict(r) for r in rows]
    train_key = next(r["unit_key"] for r in out if r["arm"] == "train")
    victim = next(r for r in out if r["arm"] == "val")
    victim["unit_key"] = train_key
    return out


def chokepoint_rows(days: int = 120, corridors: int = 28) -> list[dict[str, Any]]:
    """A time-blocked split whose unit crosscuts EVERY arm. The carve-out case."""
    rows = []
    for day in range(days):
        arm = "train" if day < 80 else ("val" if day < 100 else "test")
        for c in range(corridors):
            rows.append(
                {
                    "row_key": [day, c],
                    "arm": arm,
                    "block_key": day,
                    "unit_key": f"corridor-{c}",
                }
            )
    return rows


def chokepoint_with_one_val_only_corridor() -> list[dict[str, Any]]:
    """The carve-out shape plus ONE corridor that lives only in `val`.

    Not a mutation of the fleet's convention: an ADDITION to it. The 28 real
    corridors still crosscut all three arms; a 29th appears on val dates only,
    so part of every val date block is drawn as a replicate that the split
    never partitioned. Recorded to show what the narrowed carve-out does at its
    own boundary.
    """
    rows = chokepoint_rows()
    for day in range(80, 100):
        rows.append(
            {
                "row_key": [day, 999],
                "arm": "val",
                "block_key": day,
                "unit_key": "corridor-val-only",
            }
        )
    return rows


def splits_from(rows: list[dict[str, Any]]) -> dict[str, list[Any]]:
    """`splits` derived from the SAME rows, so the second operand agrees."""
    out: dict[str, set[str]] = {}
    for r in rows:
        out.setdefault(r["arm"], set()).add(str(r["block_key"]))
    return {k: sorted(v) for k, v in out.items()}


def drive(name: str, rows: list[dict[str, Any]], declared: dict[str, Any]) -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        module = "d6_drive_bindings"
        (root / f"{module}.py").write_text(
            _BINDING_SRC.format(
                rows=json.dumps(rows),
                splits=json.dumps(splits_from(rows)),
                declared=json.dumps(declared),
            )
        )
        (root / ".mlkit").mkdir(parents=True, exist_ok=True)
        (root / ".mlkit" / "repo.toml").write_text(
            '[repo]\nname = "d6drive"\n\n[bindings]\n'
            f'resampling_declaration = "{module}:resampling_declaration"\n'
            f'splits = "{module}:splits"\n'
        )
        subprocess.run(
            ["git", "-C", str(root), "init", "-q"], check=True, capture_output=True
        )
        repo = Repo(name="d6drive", path=root)
        try:
            result = d6_resampling_unit(
                repo, RunContext(nonce="drive", root=root, offline=True, timeout=5.0)
            )
        finally:
            repo.release()
    ev = result.evidence or {}
    return {
        "shape": name,
        "status": result.status.name,
        "relation": ev.get("relation"),
        "refusal": ev.get("refusal"),
        "n_rows": ev.get("n_rows"),
        "n_units_in_arm": ev.get("n_units_in_arm"),
        "n_blocks_in_arm": ev.get("n_blocks_in_arm"),
        # Present only at head; `None` at the base is itself part of the record.
        "n_units_crosscutting_arms": ev.get("n_units_crosscutting_arms"),
        "n_units_local_to_arm": ev.get("n_units_local_to_arm"),
        "n_blocks_split_by_local_units": ev.get("n_blocks_split_by_local_units"),
        "n_blocks_split_by_crosscutting_units": ev.get(
            "n_blocks_split_by_crosscutting_units"
        ),
        "reason": result.reason,
    }


FRAY = {
    "procedure": "bootstrap",
    "draws": 4000,
    "policy": "county_year_splits",
    "blocking_unit": "crop_year",
    "unit": "row",
    "arm": "val",
}
CHOKE = {
    "procedure": "corridor-block bootstrap",
    "draws": 2000,
    "policy": "time_blocked_split",
    "blocking_unit": "date",
    "unit": "corridor",
    "arm": "val",
}


def main() -> int:
    out_path = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    rows: list[dict[str, Any]] = []

    # -- must fire ---------------------------------------------------------
    rows.append(drive("fray_as_run_row_units", fray_rows("row"), FRAY))
    rows.append(
        drive(
            "fray_county_units_THE_VERIFIER_DRIVE",
            fray_rows("county"),
            {**FRAY, "unit": "county"},
        )
    )
    rows.append(
        drive(
            "fray_row_units_ONE_COLLIDING_KEY",
            collide_one_val_row(fray_rows("row")),
            FRAY,
        )
    )
    # -- must stay silent --------------------------------------------------
    rows.append(
        drive(
            "fray_repaired_crop_year_units",
            fray_rows("crop_year"),
            {**FRAY, "unit": "crop_year"},
        )
    )
    rows.append(drive("chokepoint_corridor_CARVE_OUT", chokepoint_rows(), CHOKE))
    rows.append(
        drive(
            "chokepoint_label_contradicts_content",
            chokepoint_rows(),
            {**CHOKE, "blocking_unit": "corridor"},
        )
    )
    # -- the carve-out's own boundary, recorded not asserted ---------------
    rows.append(
        drive(
            "chokepoint_plus_one_val_only_corridor",
            chokepoint_with_one_val_only_corridor(),
            CHOKE,
        )
    )

    payload = {
        "driver": str(Path(__file__).resolve().relative_to(_HERE)),
        "module_file": str(Path(served_module.__file__).resolve()),
        "sha": subprocess.run(
            ["git", "-C", str(_HERE), "rev-parse", "HEAD"],
            capture_output=True, text=True, check=True,
        ).stdout.strip(),
        "results": rows,
    }
    text = json.dumps(payload, indent=2, sort_keys=False) + "\n"
    if out_path is not None:
        out_path.write_text(text)
    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
