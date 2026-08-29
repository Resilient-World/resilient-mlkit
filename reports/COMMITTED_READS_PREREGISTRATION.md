# COMMITTED-READS — pre-registration

**Written before the change it governs.** Commit order is the evidence: this
file lands in its own commit, and no line of `src/` moves until it has.

**Authorization:** A-1 — local CPU only. Nothing is fitted here and no fleet
run is authorised; `portfolio/FLEET_VERDICTS.md` and its `.json` twin are
untouched by this work and stand as measured.

## The defect this closes

`docs/ESCALATIONS.md` E-M12 records that the `choco` row of
`portfolio/FLEET_VERDICTS.md` was read out of
`models/observed_production_head.meta.json`, a file that is committed on **no
ref at all** in that clone (`git log --all -- <path>` empty,
`.gitignore:82:/models/*`) and exists only in the working tree. Candidate,
score, split, baseline score and test-arm-spent for that row all resolve
through it.

The instrument recorded the fact and printed it: `ArtifactRef` already carries
`committed_at_head` and `dirty`, and `fleet.provenance_block` renders them in a
column. That is **disclosure**, and disclosure did not stop the number. A
reader who trusts the score column has to also read the provenance column, notice
a `NO`, and go back and discount a figure they have already read. The number
was quoted first and qualified afterwards.

The rule this change installs is structural rather than advisory:

> **A number the fleet instrument quotes must be a number that is in git.**
> Not "is flagged when it is not in git" — cannot be produced at all.

## The rules, fixed in advance

**R-CR1 — committed reads by default.** `core.artifact.load()` obtains artifact
bytes from the repo's committed state (`git cat-file blob HEAD:<relpath>`), not
from `path.read_bytes()`. The bytes hashed, the bytes parsed and the bytes
whose sha256 lands in the provenance table are all the same bytes, and they are
the ones a reader can fetch by that sha.

**R-CR2 — the two refusals.** Where HEAD has no such blob, `load()` returns a
ref whose error names the defect class and the file: `not committed at HEAD:
<relpath>`. Where HEAD has the blob but the working tree differs from it,
`load()` refuses on the same footing and says so. The refusal is `ArtifactRef.error`,
which `fleet._read` already turns into `Cell.missing(...)` — an NA carrying its
reason, structurally distinct from both PASS and FAIL, and rendered as
`NA (…)` and never as a dash.

The dirty case is refused rather than silently served from HEAD because a file
whose working tree disagrees with its commit is a file whose operator is in the
middle of changing what it says. Serving the HEAD bytes there would be
reproducible and wrong in a subtler way: the table would quote a figure the
person who generated it is not looking at.

**R-CR3 — the escape hatch is marked, and the mark is refused downstream.**
`load(..., allow_dirty=True)` (CLI: `mlkit portfolio --allow-dirty`) reads the
working tree, for local diagnosis of an artifact that is not committed yet.
Every value that descends from such a read carries a structural marker —
`ArtifactRef.allow_dirty_read`, `Cell.allow_dirty`, and
`CheckResult.evidence["allow_dirty_read"]` — and every path that emits a
verdict refuses it:

* `CheckResult.__post_init__` raises on a **PASS** carrying the marker, in the
  same place and the same style as the existing PASS-requires-evidence
  invariant;
* `portfolio.resolve()` raises rather than returning a terminal state computed
  from a marked result;
* `fleet.markdown_table()` and `FleetRow.to_dict()` raise rather than printing
  or serialising a marked cell.

An allow-dirty number is therefore usable in a terminal for diagnosis and
impossible to land in a verdict row. Enforced by test, not by comment.

**R-CR4 — nothing already measured moves.** No committed figure is
recomputed, no threshold moves, no holdout narrows, no gate file is edited to
go green. `portfolio/FLEET_VERDICTS.md`, `portfolio/FLEET_VERDICTS.json`,
`portfolio/MODEL_QUALITY.md` and `CHANGELOG.md`'s retraction entries are held
byte-identical, verified by sha256 recorded below.

## Control pairs, declared before they are run

Each is a pair. A check proven only to fire is consistent with a check that
fires on everything.

| id | FIRES | STAYS SILENT |
|---|---|---|
| CR-1 | a committed artifact whose working-tree copy is then edited: what comes back is not the working-tree number | the same repo before the edit reads the committed number |
| CR-2 | an artifact present only in the working tree, never committed (the E-M12 `choco` shape): NA whose reason contains the relpath and `not committed` | an artifact committed at HEAD carries no such reason |
| CR-3 | — | a committed, clean artifact loads byte-identically to the pre-change behaviour: same sha256, same bytes, same parsed document; the existing `tests/test_fleet.py` controls over `core/artifact.py` still pass |
| CR-4 | a `CheckResult` and a `FleetRow` produced under `allow_dirty` are refused by `CheckResult.__post_init__`, `portfolio.resolve()` and the verdict-emission path | the identical result without the marker resolves and renders normally |
| CR-5 | — | `load(..., allow_dirty=True)` returns the working-tree bytes and its document is readable, outside the verdict path |

## Baseline, recorded before the change (sha256)

    e984c8151cc3687fd5fd298b4036984b37afdca002057b02db671ce1832dd104  portfolio/FLEET_VERDICTS.md
    ba3b0ef5d71e2a5f8ac8a5495dd59fa1767e745f6cd336147f53c0b5b312f4a3  portfolio/FLEET_VERDICTS.json
    03597c159214f06eae2a62143018133589a90a51d5d643874137e14da58c7791  CHANGELOG.md
    90a469ab3e820a61b4bfd96b7ab8c2c9d4f7f078421714876c59fd4b53b55943  portfolio/MODEL_QUALITY.md
    2d28b7e66a4d3044e92750342965667a3fc5ddae983a8fcc52e75da1a2c7a77b  tests/test_version_declaration.py

Focused pre-change run, recorded so a regression is visible rather than
asserted: `.venv/bin/python -m pytest tests/test_fleet.py
tests/test_fabricated_defaults.py tests/test_promotion_state.py -q
--timeout=180` → **132 passed** at `96769ec`.

## What is NOT done here, and why

Cutting `v0.4.0`/`v0.5.0` tags and moving the eight adopters off their
`branch = "main"` pins is the response this change most obviously argues for —
an instrument whose read semantics have changed should not arrive at eight
repos as ambient drift. Tag-cutting is reserved to the session lead per
`docs/ESCALATIONS.md` E-M11. It is recommended in `docs/ESCALATIONS.md` and not
acted on.

Nothing in `resilient-choco` is touched. That repo has an open colleague PR
(#160), and whether its head sidecar should be committed, DVC-tracked, or the
row withdrawn is that repo's decision. What changes here is only that this
instrument can no longer quote the file either way.
