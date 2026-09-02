"""Enumerate every small assignment and record what the declaration answered.

THE CLAIM THIS EXISTS TO FALSIFY. Amendment 1 §4: *every assignment that
refuses at the base refuses at the head, with the same refusal constant.* That
is the difference between TIGHTENING a rule (allowed) and EDITING one (rule 6,
forbidden), and it is not something to argue about in a PR body. So it is
enumerated.

Run the SAME script under a worktree at the base sha and under the head, and
diff the two JSON files. Every case is identified by its own content, so the
two files line up row for row without either side knowing about the other.

    .venv/bin/python scripts/d6_containment_enumerate.py <out.json> [n_rows]

The space: `n_rows` rows (default 4), each row independently assigned one of
2 arms x 3 block keys x 3 unit keys, under BOTH label configurations (the
resampled unit labelled differently from the policy's blocking unit, and
labelled the same — the second exercises `UNIT_LABEL_CONTRADICTS_CONTENT`).
Constructions the contract refuses outright (no row in the deciding arm) are
recorded as `CONSTRUCTION_REFUSED` with the message, which is itself a fact
that has to match on both sides.

No fit, no data read, no network, no temp repo. Nothing here can reach a
ledgered test read.
"""

from __future__ import annotations

import hashlib
import itertools
import json
import sys
from pathlib import Path
from typing import Any

from resilient_mlkit.core import served as served_module
from resilient_mlkit.core.served import (
    ResamplingDeclaration,
    RowUnit,
    ServedContractError,
)

_HERE = Path(__file__).resolve().parent.parent
_EXPECTED = _HERE / "src" / "resilient_mlkit"
assert _EXPECTED in Path(served_module.__file__).resolve().parents, (
    f"core.served resolved to {served_module.__file__}, not under {_EXPECTED}"
)

ARMS = ("val", "train")
BLOCKS = (0, 1, 2)
UNITS = ("u0", "u1", "u2")
CELLS = tuple(itertools.product(ARMS, BLOCKS, UNITS))


def case_id(cells: tuple[tuple[str, int, str], ...], blocking_unit: str) -> str:
    """The case's identity is its content, so both sides key on the same thing."""
    raw = json.dumps([list(c) for c in cells] + [blocking_unit], sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def answer(cells: tuple[tuple[str, int, str], ...], blocking_unit: str) -> dict[str, Any]:
    rows = [
        RowUnit(row_key=i, arm=a, block_key=b, unit_key=u)
        for i, (a, b, u) in enumerate(cells)
    ]
    try:
        d = ResamplingDeclaration(
            procedure="bootstrap",
            draws=1000,
            policy="p",
            blocking_unit=blocking_unit,
            unit="the_unit",
            arm="val",
            assignment=rows,
        )
    except ServedContractError as exc:
        return {"refusal": "CONSTRUCTION_REFUSED", "relation": None, "note": str(exc)}
    return {
        "refusal": d.refusal or "",
        "relation": d.relation,
        "n_units_in_arm": d.n_units_in_arm,
        "n_blocks_in_arm": d.n_blocks_in_arm,
    }


def main() -> int:
    out_path = Path(sys.argv[1])
    n_rows = int(sys.argv[2]) if len(sys.argv) > 2 else 4

    cases: dict[str, Any] = {}
    for cells in itertools.product(CELLS, repeat=n_rows):
        for blocking_unit in ("the_block", "the_unit"):
            cases[case_id(cells, blocking_unit)] = {
                "cells": [list(c) for c in cells],
                "blocking_unit": blocking_unit,
                **answer(cells, blocking_unit),
            }

    payload = {
        "module_file": str(Path(served_module.__file__).resolve()),
        "n_rows": n_rows,
        "n_cases": len(cases),
        "cases": cases,
    }
    out_path.write_text(json.dumps(payload, indent=1, sort_keys=True) + "\n")
    sys.stdout.write(f"{len(cases)} cases -> {out_path}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
