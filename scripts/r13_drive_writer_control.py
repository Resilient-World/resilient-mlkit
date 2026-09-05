"""The control pair for "the fleet drive writes through mlkit's own writer".

The defect this pair exists to hold down: ``scripts/r13_fleet_drive.py`` wrote
its record with a bare ``Path.write_text`` and so wrote four machine paths into
the M-2 drive of record -- inside the same stack whose headline claim is that a
writer refuses exactly that. A refusal the producing script walks around is
theatre, and the way to tell theatre from a check is to make the check FIRE.

Two arms, one command, both driven against the same real trees:

* FIRES  -- the drive is asked to record a machine path
  (``--control-reintroduce-machine-path``). The writer refuses, the drive exits
  2, and NOTHING is written under the record's name. Asserted by checking that
  the target file does not exist afterwards, not by reading the message.
* SILENT -- the same drive, same trees, no injection. The record is written,
  ``artifact.machine_paths`` over it is empty, and so is
  ``artifact.machine_paths_in_text`` over the rendering.

A third arm, CHECK-NOT-DEAD, drives the SILENT arm's own record back through
``machine_paths`` with the roots emptied and existence disabled: the same
payload the discriminator passes must be one the discriminator would have
refused had it named a directory, which is what the FIRES arm shows on the same
bytes.

Usage::

    python scripts/r13_drive_writer_control.py --tree fray=/path/to/clone \\
        --out reports/validation/R13_DRIVE_WRITER_CONTROL.json
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import resilient_mlkit
from resilient_mlkit.core import artifact, identity

HERE = Path(__file__).resolve().parent
DRIVE = HERE / "r13_fleet_drive.py"


def _run(args: list[str], cwd: Path) -> tuple[int, str]:
    out = subprocess.run(
        [sys.executable, str(DRIVE), *args],
        capture_output=True, text=True, check=False, cwd=str(cwd),
    )
    return out.returncode, (out.stderr or "")[-600:]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tree", action="append", default=[], metavar="NAME=PATH", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)

    root = HERE.parent
    at = Path(resilient_mlkit.__file__).resolve()
    if not at.is_relative_to(root / "src"):
        raise SystemExit(f"resilient_mlkit imported from {at}, not this checkout; refusing to drive")

    trees: list[str] = []
    for spec in args.tree:
        trees += ["--tree", spec]

    arms: list[dict] = []
    with tempfile.TemporaryDirectory(prefix="r13-writer-control-") as tmp:
        scratch = Path(tmp)

        # FIRES -- the defect re-introduced into the record the drive writes.
        fires_json = scratch / "fires.json"
        fires_md = scratch / "fires.md"
        # The injected value is a directory that EXISTS on this machine, so it
        # is refused by the existence half of the discriminator as well as by
        # the roots half; a value that only looked like a path would prove less.
        injected = str(scratch)
        rc, err = _run(
            [*trees, "--out", str(fires_json), "--out-md", str(fires_md),
             "--control-reintroduce-machine-path", injected],
            root,
        )
        arms.append({
            "arm": "FIRES",
            "what_was_reintroduced": "a machine path in the record the drive writes",
            "exit_code": rc,
            "refused": rc == 2 and "REFUSED" in err,
            "json_written": fires_json.exists(),
            "md_written": fires_md.exists(),
            "stderr_tail": err.replace(injected, "<the injected directory>"),
        })

        # SILENT -- the repair, same trees, nothing injected.
        ok_json = scratch / "silent.json"
        ok_md = scratch / "silent.md"
        rc, err = _run([*trees, "--out", str(ok_json), "--out-md", str(ok_md)], root)
        record = json.loads(ok_json.read_text()) if ok_json.exists() else None
        rendering = ok_md.read_text() if ok_md.exists() else ""
        arms.append({
            "arm": "SILENT",
            "exit_code": rc,
            "json_written": ok_json.exists(),
            "md_written": ok_md.exists(),
            "machine_paths_in_record": [p for p, _ in artifact.machine_paths(record or {})],
            "machine_paths_in_rendering": [p for p, _ in artifact.machine_paths_in_text(rendering)],
            "rows": [
                {"repo": r["repo"], "git_sha": r["git_sha"], "status": r["status"],
                 "findings": len(r["findings"])}
                for r in (record or {}).get("rows", [])
            ],
        })

        # CHECK-NOT-DEAD -- the discriminator is what refuses, on these bytes.
        arms.append({
            "arm": "CHECK_NOT_DEAD",
            "question": (
                "with the same SILENT record, does the discriminator still refuse a "
                "directory? Offer it one and see."
            ),
            "silent_record_refused_when_one_row_names_a_directory": _would_refuse(record, scratch),
        })

    out = Path(args.out).resolve()
    payload = {
        "artifact_schema": "resilient-mlkit/r13-drive-writer-control/1",
        "generated_by": "scripts/r13_drive_writer_control.py",
        "generated_at_utc": _dt.datetime.now(_dt.UTC).isoformat(timespec="seconds"),
        "mlkit_version": resilient_mlkit.__version__,
        "mlkit_build": identity.build_identity().to_dict(),
        "arms": arms,
    }
    written = artifact.write_artifact(out.parent, out.name, payload)
    print(json.dumps(arms, indent=1))
    print(f"wrote {written.name}", file=sys.stderr)
    return 0


def _would_refuse(record: dict | None, scratch: Path) -> bool:
    """Put a directory into the SILENT record and offer it to the writer."""
    if not record:
        return False
    poisoned = json.loads(json.dumps(record))
    poisoned["rows"][0]["tree_name"] = str(scratch)
    target = scratch / "not-dead"
    target.mkdir(exist_ok=True)
    try:
        artifact.write_artifact(target, "x.json", poisoned)
    except artifact.MachinePathRefused:
        return not (target / "x.json").exists()
    return False


if __name__ == "__main__":
    raise SystemExit(main())
