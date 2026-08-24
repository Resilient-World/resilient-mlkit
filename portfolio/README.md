# portfolio/ — the readings, next to the instrument

`src/resilient_mlkit/` is the instrument: the single tool permitted to emit a
number for any of the eight avoided-loss model repos (rule 1, in every repo's
`CLAUDE.md`). This directory holds the portfolio-level **readings** taken with
it, and the cross-repo conclusions drawn from them.

| file | what it is |
|---|---|
| `MODEL_QUALITY.md` | Adjudication of every repo against its operational baseline. Each figure was read out of a committed artifact on disk or recomputed from that artifact's raw per-unit table. |
| `CROSS_POLLINATION.md` | What one repo found that another could use, and what happened when it was tried. |

## Why here, and not in a repo of their own

These documents compare all eight model repos, so no single model repo is their
home; a copy in each would be eight documents that drift, which is the same
failure rule 7 names for the gate code itself ("eight local copies of a gate is
eight different definitions of ready, which is the same as none").

mlkit is already the portfolio-scoped artifact — it resolves all eight repos, it
authors the shared spine in `spine/`, and its own description calls it the tool
"for the Resilient avoided-loss model portfolio". The instrument defines what
"beats its baseline" means; these files record who did. Keeping them together
means a change to a gate and the re-adjudication it forces land in one history.

A separate portfolio repo was considered and rejected: it would hold two
markdown files, no code, no tests and no CI, while adding a second thing to
permission, back up and remember. If portfolio reporting later grows tooling of
its own, `git filter-repo` promotes this directory into a repo with its history
intact.

## This directory does not ship

`pyproject.toml` sets `[tool.setuptools.packages.find] where = ["src"]`, with no
`MANIFEST.in` and no `include-package-data`. Verified by building the wheel on
2026-08-24: `resilient_mlkit-0.1.0-py3-none-any.whl`, 24 entries, all under
`resilient_mlkit/` or `.dist-info/` — neither `portfolio/` nor `spine/` appears.
So these documents cost the eight consuming environments nothing.

## Editing

`MODEL_QUALITY.md` is a living document, rewritten each adjudication round;
`CROSS_POLLINATION.md` accumulates. Neither is synced outward by
`scripts/sync_spine.py` — they are read here, not propagated, precisely so there
is one copy to disagree with.
