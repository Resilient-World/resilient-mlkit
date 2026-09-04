"""M-5 drive of record: re-produce committed offenders through the writer; record the refusal.

Usage::

    python scripts/m5_offenders_drive.py --artifact chokepoint=/path/to/foundation_finetune.json ... \
        --out reports/M5_OFFENDERS_DRIVE.json

Each artifact is loaded and offered to ``core.artifact.write_artifact`` against a
throwaway root. The record carries, per artifact: its sha256, whether the
writer refused, and every JSON pointer it named. Nothing is written into any
repo; the artifacts themselves are not modified (regeneration is each repo's
own change, with its inputs -- V3-11).
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import sys
import tempfile
from pathlib import Path

import resilient_mlkit
from resilient_mlkit.core import artifact, identity


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--artifact", action="append", default=[], metavar="LABEL=PATH")
    ap.add_argument("--out")
    args = ap.parse_args(argv)

    here = Path(__file__).resolve().parents[1] / "src"
    at = Path(resilient_mlkit.__file__).resolve()
    if not at.is_relative_to(here):
        raise SystemExit(f"resilient_mlkit imported from {at}, not {here}; refusing to drive")

    rows = []
    with tempfile.TemporaryDirectory(prefix="m5-drive-") as tmp:
        root = Path(tmp) / "resilient-scratch"
        root.mkdir()
        for spec in args.artifact:
            label, _, path = spec.partition("=")
            p = Path(path).resolve()
            raw = p.read_bytes()
            payload = json.loads(raw)
            pointers = artifact.machine_paths(payload)
            refused = False
            message = ""
            try:
                artifact.write_artifact(root, f"reports/{p.name}", payload)
            except artifact.MachinePathRefused as exc:
                refused = True
                # The headline only. The full message quotes the offending
                # values, and a machine path embedded in a SENTENCE is past the
                # writer's whole-value discriminator (a stated boundary), so
                # the record would carry what it exists to refuse.
                message = str(exc).split(":")[0] + f": {len(exc.pointers)} value(s) name a path on THIS machine"
            rows.append({
                "label": label,
                "artifact_name": p.name,
                "artifact_sha256": hashlib.sha256(raw).hexdigest(),
                "artifact_bytes": len(raw),
                "refused": refused,
                "machine_path_count": len(pointers),
                "pointers": [ptr for ptr, _ in pointers],
                # The matched machine root, WITHOUT its leading slash: the first
                # run of this script recorded a 40-character prefix of the
                # value and the writer refused its own record -- correctly.
                "machine_root_of_first": next(
                    (r.lstrip("/") for r in artifact.MACHINE_ROOTS
                     if pointers and (pointers[0][1] == r or pointers[0][1].startswith(r + "/"))),
                    None,
                ),
                "message": message,
                "written": (root / "reports" / p.name).exists(),
            })
            print(f"== {label} {p.name} sha={rows[-1]['artifact_sha256'][:12]} refused={refused} "
                  f"paths={len(pointers)} written={rows[-1]['written']}")
            for ptr in rows[-1]["pointers"]:
                print(f"   {ptr}")
    record = {
        "artifact_schema": "resilient-mlkit/m5-offenders-drive/1",
        "generated_by": "scripts/m5_offenders_drive.py",
        "generated_at_utc": _dt.datetime.now(_dt.UTC).isoformat(timespec="seconds"),
        "mlkit_version": resilient_mlkit.__version__,
        "mlkit_build": identity.build_identity().to_dict(),
        "rows": rows,
    }
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        # Through the writer itself: this record must not name a machine either.
        artifact.write_artifact(out.parent.parent if out.parent.name == "reports" else out.parent,
                                str(out.relative_to(out.parent.parent)) if out.parent.name == "reports" else out.name,
                                record)
        print(f"wrote {out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
