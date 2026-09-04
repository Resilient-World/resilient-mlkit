"""Rendering.

Plain ASCII on purpose. These tables get pasted into transcripts, PRs and
commit messages, and anything that relies on terminal colour or box-drawing
characters degrades badly in exactly those places.
"""

from __future__ import annotations

from .result import CheckResult, Status

#: Fixed-width glyphs so columns line up whatever the status mix.
GLYPH = {
    Status.PASS: "P",
    Status.FAIL: "F",
    Status.NA: "-",
    Status.DEFERRED: "K",
    Status.STALE: "S",
    Status.ESCALATED: "E",
    Status.UNMEASURABLE: "U",
}

#: `S` no longer means only "the tree moved". `core/store.py` also stales a
#: PASS whose stored mlkit build is not the one reading it (E-M24 residual), so
#: a legend saying "SHA moved" would send a reader looking at the wrong thing;
#: the per-result reason names which of the two it was.
#:
#: `U` (M-1) is the glyph a reader scanning a strip must be able to tell from
#: `F` and from `-`: the check is armed and its declaration resolved, and this
#: machine cannot supply the input it is declared over. Not indicted, not
#: unarmed.
LEGEND = ("P=pass  F=fail  -=NA(reason given)  K=deferred(wired, awaiting a key)  "
          "S=stale(repo SHA or mlkit build moved)  E=escalated(human sign-off)  "
          "U=unmeasurable(armed; declared input absent here)")


def render(rows: list[list[str]], headers: list[str]) -> str:
    """Render a simple left-aligned ASCII table."""
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(str(cell)))
    out = ["  ".join(h.ljust(widths[i]) for i, h in enumerate(headers)).rstrip()]
    out.append("  ".join("-" * widths[i] for i in range(len(headers))))
    for row in rows:
        out.append(
            "  ".join(str(c).ljust(widths[i]) for i, c in enumerate(row)).rstrip()
        )
    return "\n".join(out)


def phase_table(results: list[CheckResult], check_order: list[str]) -> str:
    """One row per check, in the order the phase doc prescribes."""
    by_id = {r.check_id: r for r in results}
    rows = []
    for check_id in check_order:
        result = by_id.get(check_id)
        if result is None:
            rows.append([check_id, "-", "not run"])
            continue
        detail = result.reason
        if result.status is Status.PASS and not detail:
            # Summarise measured evidence rather than leaving the cell empty,
            # so a pass still shows what it was a pass *of*.
            detail = ", ".join(f"{k}={v}" for k, v in list(result.evidence.items())[:3])
        rows.append([check_id, result.status.value, detail])
    return render(rows, ["CHECK", "STATUS", "DETAIL"])


def compact(results: dict[str, CheckResult], check_ids: list[str]) -> str:
    """A per-phase glyph strip like ``PPF-E`` for the portfolio table."""
    out = []
    for check_id in check_ids:
        result = results.get(check_id)
        out.append(GLYPH[result.status] if result else ".")
    return "".join(out)
