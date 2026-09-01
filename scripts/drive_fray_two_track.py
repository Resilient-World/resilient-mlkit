"""CONTROL A: fray's two-track shape driven through mlkit's real binding path.

Run twice — once with PYTHONPATH pointing at the BASE mlkit tree, once at the
HEAD tree — and diff the JSON. Nothing here trains, predicts, or scores. Every
row it touches is split MEMBERSHIP, which is what the `splits` binding on
fray's main already publishes.

usage:
  PYTHONPATH=<mlkit>/src python drive_fray_two_track.py <fray-root> <out.json>
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

def main() -> int:
    fray_root = Path(sys.argv[1]).resolve()
    out_path = Path(sys.argv[2]).resolve()

    import resilient_mlkit.checks.decision as decision_module
    import resilient_mlkit.checks.readiness as readiness_module
    import resilient_mlkit.core.served as served_module
    from resilient_mlkit.checks import RunContext
    from resilient_mlkit.checks.decision import d6_resampling_unit
    from resilient_mlkit.checks.readiness import r3_blocked_splits
    from resilient_mlkit.core.repo import Repo

    # The binding assertion the loop's rules require of every driver.
    expected = Path(sys.argv[3]).resolve()
    for mod in (decision_module, readiness_module, served_module):
        got = Path(mod.__file__).resolve()
        assert got.is_relative_to(expected), f"{mod.__name__} resolved to {got}, not under {expected}"

    sys.path.insert(0, str(fray_root / "src"))
    from validation.yield_holdout import county_label_splits, county_year_splits

    county = county_label_splits()
    year = county_year_splits()

    def rowkey(rec) -> str:
        return f"{rec.county_key}@{int(rec.year)}"

    county_rows = {
        arm: [(rowkey(r), str(int(r.block_id)), str(r.county_key)) for r in frame.itertuples()]
        for arm, frame in county.items()
    }
    year_rows = {
        arm: [(rowkey(r), str(int(r.year)), str(r.county_key)) for r in frame.itertuples()]
        for arm, frame in year.items()
    }

    def assignment(rows, unit: str) -> list[dict]:
        # unit: "block" -> the group the policy keeps whole (the repair)
        #       "row"   -> what fray's run actually resampled
        #       "county"-> the axis the crop-year policy does not partition
        out = []
        for arm, entries in rows.items():
            for row_key, group, county_key in entries:
                if unit == "block":
                    unit_key = group
                elif unit == "row":
                    unit_key = row_key
                else:
                    unit_key = county_key
                out.append(
                    {"row_key": row_key, "arm": arm, "block_key": group, "unit_key": unit_key}
                )
        return out

    def decl(rows, *, policy, blocking_unit, unit_name, unit, track=None):
        d = {
            "procedure": "bootstrap",
            "draws": 4000,
            "policy": policy,
            "blocking_unit": blocking_unit,
            "unit": unit_name,
            "arm": "val",
            "assignment": assignment(rows, unit),
        }
        if track is not None:
            d["track"] = track
        return d

    county_groups = {a: sorted({g for _, g, _ in rs}) for a, rs in county_rows.items()}
    year_groups = {a: sorted({g for _, g, _ in rs}) for a, rs in year_rows.items()}

    def run(name, splits_value, declaration_value):
        import tempfile
        import textwrap

        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            payload = tmp / "payload.json"
            payload.write_text(
                json.dumps({"splits": splits_value, "declaration": declaration_value})
            )
            (tmp / "b.py").write_text(
                textwrap.dedent(
                    f"""
                    import json
                    _P = json.loads(open({str(payload)!r}).read())
                    def splits():
                        return _P["splits"]
                    def resampling_declaration():
                        return _P["declaration"]
                    """
                )
            )
            (tmp / ".mlkit").mkdir()
            (tmp / ".mlkit" / "repo.toml").write_text(
                '[repo]\nname = "frayfixture"\n\n[bindings]\n'
                'splits = "b:splits"\n'
                'resampling_declaration = "b:resampling_declaration"\n'
            )
            subprocess.run(["git", "-C", str(tmp), "init", "-q"], check=True, capture_output=True)
            repo = Repo(name="frayfixture", path=tmp)
            ctx = RunContext(nonce="ctrlA", root=tmp, offline=True, timeout=60.0)
            try:
                r3 = r3_blocked_splits(repo, ctx)
                d6 = d6_resampling_unit(repo, ctx)
            finally:
                repo.release()
            return {
                "case": name,
                "R3": {"status": r3.status.value, "reason": r3.reason, "evidence": r3.evidence},
                "D6": {"status": d6.status.value, "reason": d6.reason, "evidence": d6.evidence},
            }

    tracked = {
        "tracks": {
            "county_block": county_groups,
            "crop_year": year_groups,
        }
    }

    cases = []

    # A-1: the recorded baseline. One flat splits (the county-block partition,
    # what fray's `splits` binding publishes on main today) and a declaration
    # taken on the CROP-YEAR track. This is the shape sota-w1 recorded.
    cases.append(
        run(
            "A1_flat_county_splits__crop_year_declaration",
            county_groups,
            decl(
                year_rows,
                policy="county_year_splits",
                blocking_unit="crop_year",
                unit_name="crop_year",
                unit="block",
            ),
        )
    )

    # A-2: the same two declarations against a TRACKED splits.
    cases.append(
        run(
            "A2_tracked_splits__both_tracks_declared",
            tracked,
            [
                decl(
                    county_rows,
                    policy="county_label_splits",
                    blocking_unit="spatial_block",
                    unit_name="spatial_block",
                    unit="block",
                    track="county_block",
                ),
                decl(
                    year_rows,
                    policy="county_year_splits",
                    blocking_unit="crop_year",
                    unit_name="crop_year",
                    unit="block",
                    track="crop_year",
                ),
            ],
        )
    )

    # A-3 firing half: the crop-year track resampled by ROW.
    cases.append(
        run(
            "A3_crop_year_track__unit_row",
            tracked,
            [
                decl(
                    year_rows,
                    policy="county_year_splits",
                    blocking_unit="crop_year",
                    unit_name="row",
                    unit="row",
                    track="crop_year",
                )
            ],
        )
    )

    # A-3 second firing half, PREDICTED IN THE PREREG TO STAY SILENT AT THIS
    # HEAD: the crop-year track resampled by COUNTY. A county contributes rows
    # to train, val and test years, so the derived relation is
    # UNIT_CROSSCUTS_ARMS, which silences DEPENDENCE_UNIT_TOO_FINE at 24f23b8.
    # That ladder belongs to item I1-M1 and this branch does not touch it.
    cases.append(
        run(
            "A3_crop_year_track__unit_county",
            tracked,
            [
                decl(
                    year_rows,
                    policy="county_year_splits",
                    blocking_unit="crop_year",
                    unit_name="county",
                    unit="county",
                    track="crop_year",
                )
            ],
        )
    )

    # A-4: the tracked splits with a declaration that names NO track.
    cases.append(
        run(
            "A4_tracked_splits__declaration_names_no_track",
            tracked,
            decl(
                year_rows,
                policy="county_year_splits",
                blocking_unit="crop_year",
                unit_name="crop_year",
                unit="block",
            ),
        )
    )

    # A-5: only one of the two tracks declared -- the recorded gap.
    cases.append(
        run(
            "A5_tracked_splits__one_track_declared",
            tracked,
            [
                decl(
                    year_rows,
                    policy="county_year_splits",
                    blocking_unit="crop_year",
                    unit_name="crop_year",
                    unit="block",
                    track="crop_year",
                )
            ],
        )
    )

    panel = {
        "n_rows_county_track": sum(len(v) for v in county_rows.values()),
        "n_rows_year_track": sum(len(v) for v in year_rows.values()),
        "n_groups_county_track": {a: len(v) for a, v in county_groups.items()},
        "n_groups_year_track": {a: len(v) for a, v in year_groups.items()},
    }
    out_path.write_text(
        json.dumps(
            {
                "mlkit_decision_module": str(Path(decision_module.__file__).resolve()),
                "fray_root": str(fray_root),
                "panel": panel,
                "cases": cases,
            },
            indent=2,
            sort_keys=True,
            default=str,
        )
        + "\n"
    )
    for c in cases:
        print(f"{c['case']}: R3={c['R3']['status']} D6={c['D6']['status']}")
        print(f"    D6 reason: {c['D6']['reason'][:220]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
