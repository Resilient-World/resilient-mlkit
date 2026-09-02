"""Diff two enumerations and decide the containment claim by counting.

    .venv/bin/python scripts/d6_containment_diff.py <base.json> <head.json> [out.json]

Amendment 1 §4 made a claim in two parts, and the enumeration separates them
because **only one of the two survived**:

* **SILENCED** — refuses at the base, SILENT at the head. This is containment
  proper: a case here means the change is an edit to the rule, not a
  tightening, and rule 6 forbids it. Exit status is non-zero if any exists.
* **REFUSAL_CONSTANT_MOVED** — refuses on both sides, under a DIFFERENT name.
  §4 said "for the same reason", and that half is falsified: making the third
  clause proportional lets it answer cases the fourth clause used to catch,
  and the third clause is EARLIER in the ladder — it is the more specific
  statement about the same assignment. Every such case is checked here to be
  a move to an earlier ladder position, never a later one; a move the other
  way would be a real loss of specificity and is counted separately.
* **TIGHTENED** — silent at the base, refusing at the head. The change itself.
  Zero here would mean nothing was closed.
* **RELATION_MOVED_WITHOUT_VERDICT_MOVING** — a relation is a label on a
  silence, not a verdict, and the amendment moves some of them on purpose.
  Checked here for the one way that could hide a loosening: a silent case whose
  unit is LABELLED as the blocking unit and whose relation became
  ``UNIT_IS_THE_BLOCK`` would be the label clause going quiet.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

#: The refusal ladder, in the order `ResamplingDeclaration.__post_init__` asks.
#: Earlier is more specific about the assignment, so a refusal that moves
#: earlier has not lost anything.
LADDER = (
    "BLOCKS_STRADDLE_ARMS",
    "SINGLE_UNIT",
    "DEPENDENCE_UNIT_TOO_FINE",
    "UNIT_LABEL_CONTRADICTS_CONTENT",
)


def rank(refusal: str) -> int:
    return LADDER.index(refusal) if refusal in LADDER else len(LADDER)


def main() -> int:
    base = json.loads(Path(sys.argv[1]).read_text())["cases"]
    head = json.loads(Path(sys.argv[2]).read_text())["cases"]
    if set(base) != set(head):
        sys.stdout.write("CASE SETS DIFFER -- not the same enumerated space\n")
        return 2

    silenced, moved, moved_later, tightened, unchanged, rel_moved = [], [], [], [], [], []
    label_clause_went_quiet = []
    for cid, b in base.items():
        h = head[cid]
        if b["refusal"] == h["refusal"]:
            unchanged.append(cid)
            if b["relation"] != h["relation"]:
                rel_moved.append(cid)
                if (
                    not h["refusal"]
                    and h["blocking_unit"] == "the_unit"
                    and h["relation"] == "UNIT_IS_THE_BLOCK"
                ):
                    label_clause_went_quiet.append(cid)
        elif b["refusal"] and not h["refusal"]:
            silenced.append(cid)
        elif b["refusal"] and h["refusal"]:
            moved.append(cid)
            if rank(h["refusal"]) > rank(b["refusal"]):
                moved_later.append(cid)
        else:
            tightened.append(cid)

    def tally(ids, fn):
        out: dict[str, int] = {}
        for c in ids:
            k = fn(c)
            out[k] = out.get(k, 0) + 1
        return out

    ok = not silenced and not moved_later and not label_clause_went_quiet
    report = {
        "n_cases": len(base),
        "SILENCED": len(silenced),
        "REFUSAL_CONSTANT_MOVED": len(moved),
        "REFUSAL_CONSTANT_MOVED_LATER_IN_THE_LADDER": len(moved_later),
        "TIGHTENED": len(tightened),
        "UNCHANGED": len(unchanged),
        "RELATION_MOVED_WITHOUT_VERDICT_MOVING": len(rel_moved),
        "SILENT_LABEL_CLAUSE_REGRESSIONS": len(label_clause_went_quiet),
        "verdict": (
            "CONTAINED: no case that refused at the base is silent at the head, "
            "and no refusal moved later in the ladder"
            if ok
            else "CONTAINMENT FALSIFIED"
        ),
        "refusal_transitions": tally(
            moved, lambda c: f"{base[c]['refusal']} -> {head[c]['refusal']}"
        ),
        "tightened_by_new_refusal": tally(tightened, lambda c: head[c]["refusal"]),
        "relation_transitions": tally(
            rel_moved, lambda c: f"{base[c]['relation']} -> {head[c]['relation']}"
        ),
        "example_silenced": [
            {"case": c, "base": base[c], "head": head[c]} for c in silenced[:5]
        ],
        "example_constant_moved": [
            {"case": c, "base": base[c], "head": head[c]} for c in moved[:2]
        ],
        "example_tightened": [
            {"case": c, "base": base[c], "head": head[c]} for c in tightened[:2]
        ],
    }
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if len(sys.argv) > 3:
        Path(sys.argv[3]).write_text(text)
    sys.stdout.write(text)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
