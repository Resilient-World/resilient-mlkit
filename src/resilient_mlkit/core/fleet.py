"""The fleet verdict table, read out of the repos instead of typed in.

``portfolio/MODEL_QUALITY.md`` answers the only question the portfolio is for:
does each model beat its baseline. Every figure in it was transcribed by hand
from an artifact in another repo. Hand transcription of a number that exists in
exactly one other place has no error detection at all -- a wrong digit is
indistinguishable from a right one, and stays wrong through every re-read.

This module regenerates the *measured* columns by opening the artifacts. What
it cannot regenerate -- the adjudicator's "do I believe it?" column -- it does
not touch, because that is judgement and judgement is not a field lookup.

WHY A DECLARED ADAPTER PER REPO
-------------------------------
The eight repos do not share an artifact schema and should not be made to.
resilient-chokepoint ships a self-describing ``champion.json`` that names its
own source artifacts and their sha256; resilient-arabica records candidates as a
list inside a per-split block; resilient-torrent keeps its reference comparison
in a row-parity file and its test-arm ledger in a JSONL append log. A universal
schema guessed over all eight would either be wrong somewhere or would degrade
into "find any key that looks like an RMSE", which is a generator of confident
nonsense.

So each repo declares, in ``fleet_adapters.py``, exactly which file and exactly
which pointer carries each column. A pointer that does not resolve becomes NA
with the pointer that missed. A field the repo's artifact genuinely does not
carry is declared ``Absent(reason)`` -- written down once, visible in the table,
and never silently omitted.

WHAT IS DECLARED VS WHAT IS MEASURED
------------------------------------
Only three things in an adapter are authored by hand, and none of them is a
measurement:

* the artifact path and pointers -- checkable, and self-invalidating if wrong;
* ``lower_is_better`` -- a property of the metric, not a value of it;
* ``metric`` -- a label. It is corroborated mechanically against the key the
  score pointer lands on, so a label that has drifted away from the quantity it
  names reports NA rather than mislabelling a real number.

Everything that is a number comes off disk.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .artifact import ArtifactRef, Cell, load, resolve_pointer, unresolved
from .repo import Repo

#: Alias every adapter must declare. Others are optional and referenced as
#: ``alias:pointer``.
MAIN = "main"


@dataclass(frozen=True)
class Field:
    """Read this column from ``pointer``.

    ``pointer`` is ``"alias:dotted.path"``; the alias defaults to ``main``.
    Numeric segments index lists. ``transform`` is applied to whatever the
    pointer lands on:

    * ``""``   -- take it as it is
    * ``len``  -- its length (a ledger's value is its line count)
    * ``float``/``bool`` -- coerce, and NA if the coercion fails
    """

    pointer: str
    transform: str = ""


@dataclass(frozen=True)
class Absent:
    """This repo's committed artifacts do not carry this column.

    The reason is mandatory and is printed in the table. An adapter that omits
    a field instead of declaring it Absent is a silently short row, which reads
    as "not applicable" when it means "nobody has written this down".
    """

    reason: str

    def __post_init__(self) -> None:
        if not self.reason.strip():
            raise ValueError("Absent requires a reason")


@dataclass(frozen=True)
class Compare:
    """Derive ``beats`` from the two measured scores under ``lower_is_better``.

    A comparison of two numbers that were both measured is not a fabricated
    number; it is arithmetic over measurements, and the row records that it was
    derived rather than read. If either side is NA the comparison is NA.
    """


@dataclass(frozen=True)
class Declared:
    """A LABEL supplied by the adapter, corroborated against a pointer.

    Only for columns that are names, never for columns that are numbers. Some
    artifacts do not carry a ``"split": "test"`` field because the split is a
    key on the path -- ``splits_scored.test.candidates.0.rmse`` says "test" four
    segments up and nowhere else. Declaring the label is honest there; declaring
    it *unchecked* is not, so the label must be echoed by the pointer it is
    declared against, and reports NA when it is not.

    ``against`` names which of the row's pointers must echo it: ``"score"`` (the
    default) or ``"baseline"``.
    """

    label: str
    against: str = "score"

    def __post_init__(self) -> None:
        if self.against not in ("score", "baseline"):
            raise ValueError(f"Declared.against must be 'score' or 'baseline', got {self.against!r}")


Spec = Field | Absent | Compare | Declared


@dataclass(frozen=True)
class Adapter:
    """How to read one verdict row out of one repo."""

    repo: str
    #: "" for a repo with a single row; the track/head name when a repo
    #: legitimately has more than one model of record (fray has two tracks,
    #: chokepoint two heads). Collapsing those into one row loses the fact.
    entry: str
    artifacts: dict[str, str]
    #: Field when the artifact carries a metric label of its own; Declared when
    #: it does not and the label has to be corroborated against the pointer.
    metric: Spec
    lower_is_better: bool
    model_of_record: Spec
    candidate: Spec
    score: Spec
    split: Spec
    baseline_name: Spec
    baseline_score: Spec
    beats: Spec
    test_arm_spent: Spec
    note: str = ""

    def __post_init__(self) -> None:
        if MAIN not in self.artifacts:
            raise ValueError(f"{self.repo}/{self.entry}: adapter must declare a '{MAIN}' artifact")

    @property
    def key(self) -> str:
        return f"{self.repo}/{self.entry}" if self.entry else self.repo


@dataclass
class FleetRow:
    """One adjudicated row, with every cell traceable to bytes on disk."""

    repo: str
    entry: str
    metric: Cell
    model_of_record: Cell
    candidate: Cell
    score: Cell
    split: Cell
    baseline_name: Cell
    baseline_score: Cell
    beats: Cell
    test_arm_spent: Cell
    artifacts: dict[str, ArtifactRef] = field(default_factory=dict)
    note: str = ""

    @property
    def key(self) -> str:
        return f"{self.repo}/{self.entry}" if self.entry else self.repo

    @property
    def main(self) -> ArtifactRef | None:
        return self.artifacts.get(MAIN)

    @property
    def off_checkout(self) -> bool:
        return any(a.off_checkout for a in self.artifacts.values() if a.found)

    def to_dict(self) -> dict[str, Any]:
        return {
            "repo": self.repo,
            "entry": self.entry or None,
            "metric": self.metric.to_dict(),
            "model_of_record": self.model_of_record.to_dict(),
            "candidate": self.candidate.to_dict(),
            "score": self.score.to_dict(),
            "split": self.split.to_dict(),
            "baseline_name": self.baseline_name.to_dict(),
            "baseline_score": self.baseline_score.to_dict(),
            "beats": self.beats.to_dict(),
            "test_arm_spent": self.test_arm_spent.to_dict(),
            "artifacts": {k: v.to_dict() for k, v in self.artifacts.items()},
            "note": self.note or None,
        }


def _normalise(text: str) -> str:
    return "".join(ch for ch in text.lower() if ch.isalnum())


def corroborates(label: str, pointer: str) -> bool:
    """True when a declared label is echoed somewhere in the pointer it names.

    ``'mae'`` over ``...level_head_on_the_episode_holdouts.test_mae_mtpd``
    corroborates; ``'rmse'`` over the same pointer does not, and the row then
    reports NA rather than putting a real number under a label the artifact
    does not support. ``'test'`` over ``splits_scored.test.candidates.0.rmse``
    corroborates on a segment that is not the leaf, which is why the whole
    pointer is searched and not only its last part.
    """
    body = pointer.rsplit(":", 1)[-1]
    return any(_normalise(label) in _normalise(seg) for seg in body.split("."))


def _read(
    spec: Spec, refs: dict[str, ArtifactRef], *, column: str
) -> Cell:
    if isinstance(spec, Absent):
        return Cell.missing(spec.reason)
    if isinstance(spec, (Compare, Declared)):
        # Both need the row's own pointers, so read_row resolves them.
        return Cell.missing(f"{column} not yet derived")

    alias, _, pointer = spec.pointer.rpartition(":")
    alias = alias or MAIN
    ref = refs.get(alias)
    if ref is None:
        return Cell.missing(f"adapter references undeclared artifact alias '{alias}'")
    if not ref.found:
        return Cell.missing(ref.error or "artifact unavailable", spec.pointer)

    value = resolve_pointer(ref.document, pointer)
    if unresolved(value):
        return Cell.missing(
            f"pointer '{pointer}' does not resolve in {ref.relpath} "
            f"(sha256 {ref.sha256[:12]}…)",
            spec.pointer,
        )
    if spec.transform == "len":
        try:
            value = len(value)
        except TypeError:
            return Cell.missing(
                f"pointer '{pointer}' in {ref.relpath} is a "
                f"{type(value).__name__}, which has no length",
                spec.pointer,
            )
    elif spec.transform == "float":
        try:
            value = float(value)
        except (TypeError, ValueError):
            return Cell.missing(
                f"pointer '{pointer}' in {ref.relpath} is not a number ({value!r})",
                spec.pointer,
            )
    elif spec.transform == "bool" and not isinstance(value, bool):
        return Cell.missing(
            f"pointer '{pointer}' in {ref.relpath} is not a boolean ({value!r})",
            spec.pointer,
        )
    if value is None:
        return Cell.missing(
            f"pointer '{pointer}' in {ref.relpath} resolves to null", spec.pointer
        )
    return Cell.measured(value, f"{ref.relpath}#{pointer}")


def read_row(repo: Repo, adapter: Adapter) -> FleetRow:
    """Open one repo's declared artifacts and fill one verdict row."""
    refs = {alias: load(repo, rel) for alias, rel in adapter.artifacts.items()}

    score = _read(adapter.score, refs, column="score")
    baseline_score = _read(adapter.baseline_score, refs, column="baseline_score")

    if isinstance(adapter.beats, Compare):
        beats = _compare(score, baseline_score, adapter.lower_is_better)
    else:
        beats = _read(adapter.beats, refs, column="beats")

    anchors = {"score": adapter.score, "baseline": adapter.baseline_score}

    def cell(spec: Spec, column: str) -> Cell:
        if isinstance(spec, Declared):
            return _declared(spec, anchors, column=column)
        return _read(spec, refs, column=column)

    return FleetRow(
        repo=adapter.repo,
        entry=adapter.entry,
        metric=cell(adapter.metric, "metric"),
        model_of_record=cell(adapter.model_of_record, "model_of_record"),
        candidate=cell(adapter.candidate, "candidate"),
        score=score,
        split=cell(adapter.split, "split"),
        baseline_name=cell(adapter.baseline_name, "baseline_name"),
        baseline_score=baseline_score,
        beats=beats,
        test_arm_spent=cell(adapter.test_arm_spent, "test_arm_spent"),
        artifacts=refs,
        note=adapter.note,
    )


def _declared(spec: Declared, anchors: dict[str, Spec], *, column: str) -> Cell:
    """Admit a declared label only if the pointer it names echoes it."""
    anchor = anchors.get(spec.against)
    if not isinstance(anchor, Field):
        return Cell.missing(
            f"declared {column} label '{spec.label}' is corroborated against the "
            f"{spec.against} pointer, but this adapter has no {spec.against} pointer "
            "to corroborate it against"
        )
    if not corroborates(spec.label, anchor.pointer):
        return Cell.missing(
            f"declared {column} label '{spec.label}' is not echoed anywhere in the "
            f"{spec.against} pointer '{anchor.pointer}'; the label and the quantity "
            "have drifted apart, so the number is reported without one"
        )
    return Cell.measured(
        spec.label, f"declared, corroborated by {spec.against} pointer {anchor.pointer}"
    )


def _compare(score: Cell, baseline: Cell, lower_is_better: bool) -> Cell:
    if not score.present:
        return Cell.missing(f"score is NA, so no comparison is possible: {score.na_reason}")
    if not baseline.present:
        return Cell.missing(f"baseline is NA, so no comparison is possible: {baseline.na_reason}")
    try:
        a, b = float(score.value), float(baseline.value)
    except (TypeError, ValueError):
        return Cell.missing("score or baseline is not numeric, so they cannot be compared")
    verdict = a < b if lower_is_better else a > b
    direction = "lower is better" if lower_is_better else "higher is better"
    return Cell.measured(
        verdict, f"derived: {a!r} vs {b!r} ({direction}); both read from the artifacts above"
    )


# ---------------------------------------------------------------- rendering

#: Columns of the generated verdict table, in the order they are printed.
COLUMNS = (
    "repo",
    "model of record",
    "candidate scored",
    "metric",
    "split",
    "score",
    "bar",
    "bar score",
    "beats bar?",
    "test arm",
)


def _short(text: str, limit: int) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _num(cell: Cell) -> str:
    """Render a score at full precision, so a table cell is not a rounding."""
    if not cell.present:
        return f"NA — {_short(cell.na_reason, 90)}"
    if isinstance(cell.value, float):
        return repr(cell.value)
    return _short(cell.value, 60)


def markdown_table(rows: list[FleetRow]) -> str:
    """The verdict table itself, every cell either a read value or an NA."""
    out = ["| " + " | ".join(COLUMNS) + " |", "|" + "---|" * len(COLUMNS)]
    for row in rows:
        out.append(
            "| "
            + " | ".join(
                (
                    row.key,
                    _short(row.model_of_record.render(), 60),
                    _short(row.candidate.render(), 60),
                    _short(row.metric.render(), 40),
                    _short(row.split.render(), 40),
                    _num(row.score),
                    _short(row.baseline_name.render(), 40),
                    _num(row.baseline_score),
                    _short(row.beats.render(), 40),
                    _short(row.test_arm_spent.render(), 60),
                )
            )
            + " |"
        )
    return "\n".join(out)


def provenance_block(rows: list[FleetRow]) -> str:
    """Which bytes each row came out of. This is the part that makes it checkable."""
    lines = [
        "| row | artifact | sha256 | bytes | committed at HEAD | dirty | tree |",
        "|---|---|---|---|---|---|---|",
    ]
    for row in rows:
        for alias, ref in row.artifacts.items():
            if not ref.found:
                lines.append(
                    f"| {row.key} | `{ref.relpath}` ({alias}) | — | — | no | — | "
                    f"NOT FOUND: {_short(ref.error, 120)} |"
                )
                continue
            tree = "checkout" if not ref.worktree else f"worktree `{ref.worktree}`"
            lines.append(
                f"| {row.key} | `{ref.relpath}` ({alias}) | `{ref.sha256}` | {ref.bytes_} | "
                f"{'yes' if ref.committed_at_head else 'NO'} | "
                f"{'YES' if ref.dirty else 'no'} | {tree} @ `{ref.branch}` `{ref.git_sha[:12]}` |"
            )
    return "\n".join(lines)


def na_summary(rows: list[FleetRow]) -> list[str]:
    """Every NA in the table, with its reason, gathered in one place."""
    named = (
        ("model of record", lambda r: r.model_of_record),
        ("candidate", lambda r: r.candidate),
        ("metric", lambda r: r.metric),
        ("split", lambda r: r.split),
        ("score", lambda r: r.score),
        ("bar", lambda r: r.baseline_name),
        ("bar score", lambda r: r.baseline_score),
        ("beats bar?", lambda r: r.beats),
        ("test arm", lambda r: r.test_arm_spent),
    )
    out: list[str] = []
    for row in rows:
        for label, getter in named:
            cell = getter(row)
            if not cell.present:
                out.append(f"- **{row.key} / {label}** — {cell.na_reason}")
    return out


def counts(rows: list[FleetRow]) -> dict[str, int]:
    """How much of the table is measured, and how much is NA-with-reason."""
    measured = na = 0
    for row in rows:
        for cell in (
            row.model_of_record, row.candidate, row.metric, row.split, row.score,
            row.baseline_name, row.baseline_score, row.beats, row.test_arm_spent,
        ):
            if cell.present:
                measured += 1
            else:
                na += 1
    return {"rows": len(rows), "cells_measured": measured, "cells_na": na}
