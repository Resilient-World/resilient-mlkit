"""CONTROL B: single-track adopters, base vs head, compared as bytes.

Every check in mlkit that reads the `splits` binding is R3 and D6 (grepped:
`checks/readiness.py`, `checks/decision.py`; no other consumer exists). Both are
driven here, through the real binding path, against the REAL split membership
`resilient-torrent` and `resilient-chokepoint` publish from their own
`mlkit_bindings:splits`, captured once into splits_real.json.

usage:
  PYTHONPATH=<mlkit>/src python drive_single_track_controls.py \
      splits_real.json <out.json> <expected-mlkit-src>
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path


def main() -> int:
    real = json.loads(Path(sys.argv[1]).read_text())
    out_path = Path(sys.argv[2]).resolve()
    expected = Path(sys.argv[3]).resolve()

    import resilient_mlkit.checks.decision as decision_module
    import resilient_mlkit.checks.readiness as readiness_module
    import resilient_mlkit.core.served as served_module
    from resilient_mlkit.checks import RunContext
    from resilient_mlkit.checks.decision import d6_resampling_unit
    from resilient_mlkit.checks.readiness import r3_blocked_splits
    from resilient_mlkit.core.repo import Repo

    for mod in (decision_module, readiness_module, served_module):
        got = Path(mod.__file__).resolve()
        assert got.is_relative_to(expected), f"{mod.__name__} resolved to {got}, not under {expected}"

    def run(name, splits_value, declaration_value, *, declare_binding=True):
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
            toml = '[repo]\nname = "fixturerepo"\n\n[bindings]\nsplits = "b:splits"\n'
            if declare_binding:
                toml += 'resampling_declaration = "b:resampling_declaration"\n'
            (tmp / ".mlkit" / "repo.toml").write_text(toml)
            subprocess.run(["git", "-C", str(tmp), "init", "-q"], check=True, capture_output=True)
            repo = Repo(name="fixturerepo", path=tmp)
            ctx = RunContext(nonce="ctrlB", root=tmp, offline=True, timeout=60.0)
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

    def blocked_declaration(splits_value, *, policy, unit_name, rows_per_group=3):
        """The adopter's own convention: the resampled unit IS the block."""
        assignment = []
        for arm, groups in splits_value.items():
            for g in sorted(map(str, groups)):
                for i in range(rows_per_group):
                    assignment.append(
                        {"row_key": f"{g}#{i}", "arm": arm, "block_key": g, "unit_key": g}
                    )
        return {
            "procedure": "block bootstrap",
            "draws": 4000,
            "policy": policy,
            "blocking_unit": unit_name,
            "unit": unit_name,
            "arm": "val",
            "assignment": assignment,
        }

    cases = []
    for repo_name, policy, unit_name in (
        ("torrent", "basin_blocked_split", "basin"),
        ("chokepoint", "corridor_blocked_split", "corridor"),
    ):
        splits_value = {k: sorted(map(str, v)) for k, v in real[repo_name].items()}
        decl = blocked_declaration(splits_value, policy=policy, unit_name=unit_name)
        cases.append(run(f"B_{repo_name}_real_splits__block_unit", splits_value, decl))
        # the row bootstrap the contract exists to refuse, on the same splits
        row_decl = json.loads(json.dumps(decl))
        for r in row_decl["assignment"]:
            r["unit_key"] = r["row_key"]
        row_decl["unit"] = "row"
        cases.append(run(f"B_{repo_name}_real_splits__row_unit", splits_value, row_decl))
        # and the same repo with no resampling binding at all
        cases.append(
            run(f"B_{repo_name}_real_splits__no_binding", splits_value, decl,
                declare_binding=False)
        )

    out_path.write_text(json.dumps({"cases": cases}, indent=2, sort_keys=True, default=str) + "\n")
    for c in cases:
        print(f"{c['case']}: R3={c['R3']['status']} D6={c['D6']['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
