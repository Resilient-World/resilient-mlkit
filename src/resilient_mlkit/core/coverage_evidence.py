"""Re-derive a coverage claim's ``empirical`` and ``n`` from its own operands.

D3 asks a repo "do your prediction intervals cover at the level you promise",
and its verdict is a subtraction. E-M21 and E-M23 moved the first operand of
that subtraction -- the promised level -- out of the dict the subject hands
back and into committed state, and clamped the tolerance to mlkit's. The other
two operands were left where tick 13 found them, and E-M23 recorded it as
residual 2:

    with an honest committed 0.90, a binding returning
    {"nominal": 0.90, "empirical": 0.90, "n": 1000000} PASSes, and nothing
    ties either figure to a row set.

There is nothing wrong with those numbers individually. That is the point:
there is nothing right about them either, because no reader -- mlkit included
-- can do anything with them except believe them. A coverage figure is a
COUNT OVER ROWS, and a count nobody can recount is a claim.

So this module takes the operands a count is made of, recounts them, and names
the row set it recounted. It is the round-8 M-06 shape that
:func:`resilient_mlkit.core.served.row_set_digest` already installed for
challenger comparisons, pointed at D3: two figures tie to the same rows or
they do not tie at all.

**What this module does NOT establish**, stated here rather than left to be
discovered: it does not prove the rows are the holdout. The row set is still
the subject's. What changes is that ``empirical`` and ``n`` stop being
assertions and become derivations, and that the rows behind them acquire a
name in the fleet's one spelling of that name -- so a coverage claim and a
served comparison can be held against each other, which they could not be
while one of them named nothing. Tying the declaration itself to committed
state is the next tie and is deliberately not half-built here; see
``reports/D3_COVERAGE_TIE_PREREGISTRATION.md``.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from .served import (
    _SHA256_HEX,
    ServedContractError,
    _row_key_canonical,
    row_set_digest,
)

__all__ = [
    "COVERED_KEY",
    "DIGEST_KEY",
    "EMPIRICAL_AGREEMENT_EPS",
    "GROUPS_KEY",
    "GROUP_ID_KEY",
    "GROUP_N_KEY",
    "ROWS_KEY",
    "ROW_ID_KEY",
    "CoverageRefused",
    "CoverageUntied",
    "DerivedCoverage",
    "derive",
]

#: The digest naming the rows a coverage figure was computed on. Spelled the
#: way ``core.served`` spells the same idea, and computed by that module's
#: function, so a D3 evidence dict and a challenger comparison can be compared.
DIGEST_KEY = "row_set_digest"

#: Per-row operands: one entry per held-out row.
ROWS_KEY = "rows"
ROW_ID_KEY = "row_id"
COVERED_KEY = "covered"

#: Per-group operands: one entry per cell of a partition the subject declares.
#:
#: Why this form exists at all, MEASURED rather than asserted, because the
#: first version of this comment claimed a million rows "cannot be handed to a
#: check row by row" and that is not what the clock says. Driven on this
#: module: 1,000,000 per-row operands derive in **0.96 s**, which is nothing.
#: What they cost is MEMORY -- 242 MB for the payload and a 344 MB peak through
#: :func:`derive` (``tracemalloc``, CPython 3.14) -- and that is charged inside
#: the adopter's own process, beside whatever model held the holdout. The group
#: form is the way out of the memory, not the way out of the arithmetic, and a
#: contract nobody can afford to satisfy is a contract nobody adopts.
GROUPS_KEY = "groups"
GROUP_ID_KEY = "group_id"
GROUP_N_KEY = "n"

#: How far a reported ``empirical`` may sit from the quotient this module
#: derives and still be the same number.
#:
#: This is a FLOAT REPRESENTATION allowance and emphatically not a tolerance,
#: for the same reason ``checks.decision.NOMINAL_AGREEMENT_EPS`` is not one: a
#: subject may average an indicator array and mlkit divides two integers, and
#: the last bits differ. Anything a person could mean by "a different coverage"
#: is many orders of magnitude above this -- the incident that motivated D3's
#: first tie missed by 1.2e-2. ``n`` gets no allowance at all; a count is an
#: integer or it is not a count.
EMPIRICAL_AGREEMENT_EPS = 1e-12


class CoverageUntied(Exception):
    """The operands are ABSENT. Carries the marker D3 reports as NA.

    Distinct from :class:`CoverageRefused` because the two are different
    instructions to different people: an adopter reads "supply this" and a
    reviewer reads "this was supplied and it does not hold". Collapsing them
    would make the first look like a finding and the second look like a gap.
    """

    def __init__(self, marker: str, detail: str) -> None:
        super().__init__(f"{marker}: {detail}")
        self.marker = marker
        self.detail = detail


class CoverageRefused(Exception):
    """The operands are PRESENT and do not hold up. D3 reports FAIL."""

    def __init__(self, marker: str, detail: str) -> None:
        super().__init__(f"{marker}: {detail}")
        self.marker = marker
        self.detail = detail


#: Markers, named here so that tests and adopters quote one spelling.
UNTIED = "COVERAGE_UNTIED"
MALFORMED = "COVERAGE_ROWS_MALFORMED"
DIGEST_MISMATCH = "COVERAGE_ROW_SET_MISMATCH"
SELF_REPORTED = "COVERAGE_SELF_REPORTED"


@dataclass(frozen=True)
class DerivedCoverage:
    """What the operands say, computed here rather than accepted."""

    #: ``"row"`` or ``"group"`` -- which form the subject supplied.
    unit: str
    #: How many held-out points the operands account for.
    n: int
    #: How many of them the intervals covered.
    covered: int
    #: The row-set digest recomputed from the keys the subject handed over.
    digest: str

    @property
    def empirical(self) -> float:
        return self.covered / self.n


def _as_indicator(value: Any, where: str) -> int:
    """1 or 0, or a refusal naming what was there instead.

    ``bool(value)`` is not used and must not be: truthiness is what lets a
    string, a NaN or a 0.3 become "covered" with nobody looking, and a coverage
    count assembled out of truthiness is the fabrication this module exists to
    make impossible. Exactly `True`/`False`, the ints 0 and 1, and the floats
    0.0 and 1.0 are indicators; everything else is refused by name.

    A ``numpy.bool_`` is refused here, deliberately and with a cost: it is not
    a Python ``bool`` and mlkit has no numpy dependency to recognise it with
    (see pyproject's dependency note). The adopter's fix is ``bool(x)`` at the
    yield site, which is one call and leaves the operand a thing every reader
    of the evidence can parse.
    """
    if value is True:
        return 1
    if value is False:
        return 0
    if isinstance(value, int) and value in (0, 1):
        return int(value)
    if isinstance(value, float) and value in (0.0, 1.0):
        return int(value)
    raise CoverageRefused(
        MALFORMED,
        f"{where} carries {COVERED_KEY}={value!r}, which is not a coverage "
        "indicator. A row is covered or it is not: write True/False (or 1/0). "
        "Anything else would be counted by truthiness, and a count assembled "
        "out of truthiness is not a measurement",
    )


def _as_count(value: Any, where: str, field: str) -> int:
    """A non-negative integer, or a refusal naming what was there instead."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise CoverageRefused(
            MALFORMED,
            f"{where} carries {field}={value!r}, which is not a whole number of "
            "rows; a group's counts are integers or they are not counts",
        )
    if value < 0:
        raise CoverageRefused(
            MALFORMED, f"{where} carries {field}={value!r}, and no row set has a "
            "negative number of rows"
        )
    return value


def _entries(payload: Mapping[str, Any], key: str) -> Sequence[Mapping[str, Any]]:
    """The operand sequence under ``key``, or a refusal naming its shape."""
    raw = payload[key]
    if isinstance(raw, (str, bytes)) or not isinstance(raw, Sequence):
        raise CoverageRefused(
            MALFORMED,
            f"{key} is a {type(raw).__name__}, not a sequence of per-{key[:-1]} "
            "operands; the figures cannot be re-derived from it",
        )
    for index, entry in enumerate(raw):
        if not isinstance(entry, Mapping):
            raise CoverageRefused(
                MALFORMED,
                f"{key}[{index}] is a {type(entry).__name__}, not a mapping; "
                f"each entry states which {key[:-1]} it is and what happened to it",
            )
    return list(raw)


def _digest_of(keys: Iterable[Any], *, unit: str) -> str:
    """``core.served.row_set_digest``, with its refusals renamed for D3.

    Rule 7 in one line: the digest is NOT recomputed here. Two spellings of
    "the digest of the rows" cannot be compared, which is the whole reason
    ``core.served`` owns exactly one.
    """
    try:
        return row_set_digest(keys)
    except ServedContractError as exc:
        raise CoverageRefused(
            MALFORMED,
            f"the {unit} keys could not be digested -- {exc}",
        ) from exc
    except TypeError as exc:
        raise CoverageRefused(
            MALFORMED,
            f"the {unit} keys are not JSON-serialisable -- {exc}. A key that "
            "cannot be written down cannot be joined to another artifact, which "
            "is the only thing a row-set digest is for",
        ) from exc


def _refuse_repeats(keys: Sequence[Any], *, unit: str) -> None:
    """A repeated key makes the count unverifiable, so it is refused.

    Stricter than :func:`core.served.row_set_digest`, which deliberately does
    NOT collapse duplicates -- there, a row scored twice on one side and once
    on the other is a genuine difference between two comparisons. Here the
    digest is the only handle on WHICH rows a count is over, and a set of keys
    with `r7` twice is either one row counted twice or two rows sharing a name.
    Both make ``n`` mean something other than "how many held-out rows there
    are", and neither can be joined to another artifact by that name.

    Sameness is decided by ``core.served``'s own written form of a key and NOT
    by ``repr``, because the two disagree and the disagreement was exploitable
    (docs/ESCALATIONS.md E-M35, found by adversarial verification of this
    branch). ``repr({"a": 1, "b": 2}) != repr({"b": 2, "a": 1})`` while the
    digest treats them as one key, and the same holds for ``(1, 2)`` against
    ``[1, 2]``: a subject with composite row ids could hand over the SAME row
    twice, evade this guard, and inflate ``n`` and ``covered`` past both the
    small-holdout NA and the coverage verdict, with the digest agreeing. A
    guard whose notion of "the same row" differs from the digest's is a guard
    the digest can be steered around, so there is now one notion.
    """
    seen: set[str] = set()
    for key in keys:
        try:
            marker = _row_key_canonical(key)
        except (TypeError, ValueError):
            # Not writable down; `_digest_of` refuses it by name a moment later
            # and says why. Falling back to `repr` here keeps this loop total
            # without letting an unwritable key decide anything.
            marker = repr(key)
        if marker in seen:
            raise CoverageRefused(
                MALFORMED,
                f"{unit} key {key!r} appears more than once. The digest is the "
                f"only handle on which rows this figure covers, so a repeated "
                f"key is either one {unit} counted twice or two sharing a name; "
                "both make n something other than a count of held-out rows",
            )
        seen.add(marker)


def _derive_rows(payload: Mapping[str, Any]) -> DerivedCoverage:
    rows = _entries(payload, ROWS_KEY)
    keys: list[Any] = []
    covered = 0
    for index, row in enumerate(rows):
        where = f"{ROWS_KEY}[{index}]"
        for field in (ROW_ID_KEY, COVERED_KEY):
            if field not in row:
                raise CoverageRefused(
                    MALFORMED,
                    f"{where} does not report {field}; a row that does not say "
                    "which row it is, or whether it was covered, is not an operand",
                )
        keys.append(row[ROW_ID_KEY])
        covered += _as_indicator(row[COVERED_KEY], where)
    _refuse_repeats(keys, unit="row")
    return DerivedCoverage(
        unit="row", n=len(keys), covered=covered, digest=_digest_of(keys, unit="row")
    )


def _derive_groups(payload: Mapping[str, Any]) -> DerivedCoverage:
    groups = _entries(payload, GROUPS_KEY)
    keys: list[Any] = []
    total = 0
    covered = 0
    for index, group in enumerate(groups):
        where = f"{GROUPS_KEY}[{index}]"
        for field in (GROUP_ID_KEY, GROUP_N_KEY, COVERED_KEY):
            if field not in group:
                raise CoverageRefused(
                    MALFORMED,
                    f"{where} does not report {field}; a group states which cell "
                    "of the partition it is, how many rows it holds and how many "
                    "of them were covered",
                )
        size = _as_count(group[GROUP_N_KEY], where, GROUP_N_KEY)
        hits = _as_count(group[COVERED_KEY], where, COVERED_KEY)
        if hits > size:
            raise CoverageRefused(
                MALFORMED,
                f"{where} reports {hits} covered of {size} rows; more rows were "
                "covered than the group holds, so these are not counts over one "
                "row set",
            )
        keys.append(group[GROUP_ID_KEY])
        total += size
        covered += hits
    _refuse_repeats(keys, unit="group")
    if total == 0:
        raise CoverageRefused(
            MALFORMED,
            "the declared groups hold no rows at all; a coverage figure over "
            "zero rows is a division by zero wearing a proportion's clothes",
        )
    return DerivedCoverage(
        unit="group", n=total, covered=covered, digest=_digest_of(keys, unit="group")
    )


def derive(payload: Mapping[str, Any]) -> DerivedCoverage:
    """Recount a coverage claim from the operands it arrived with.

    Raises :class:`CoverageUntied` when the operands are absent -- D3 reports
    that as NA, naming what to supply -- and :class:`CoverageRefused` when they
    are present and do not hold, which is a FAIL.
    """
    has_rows = ROWS_KEY in payload
    has_groups = GROUPS_KEY in payload
    if has_rows and has_groups:
        raise CoverageRefused(
            MALFORMED,
            f"the evidence carries both {ROWS_KEY} and {GROUPS_KEY}. Two "
            "descriptions of the same row set can disagree, and a check that "
            "picked one would be choosing which of the subject's answers to "
            "believe; supply the rows or the groups they partition, not both",
        )
    if not has_rows and not has_groups:
        raise CoverageUntied(
            UNTIED,
            f"the coverage evidence carries no {ROWS_KEY} and no {GROUPS_KEY}, so "
            "`empirical` and `n` are figures nobody -- mlkit included -- can "
            "re-derive. Supply one entry per held-out row "
            f'({{"{ROW_ID_KEY}": ..., "{COVERED_KEY}": True}}) or per declared '
            f'group ({{"{GROUP_ID_KEY}": ..., "{GROUP_N_KEY}": ..., '
            f'"{COVERED_KEY}": ...}}), beside a `{DIGEST_KEY}` from '
            "core.served.row_set_digest. docs/ESCALATIONS.md E-M23 residual 2",
        )
    if DIGEST_KEY not in payload:
        raise CoverageUntied(
            UNTIED,
            f"the coverage evidence carries operands but no {DIGEST_KEY}, so the "
            "rows it counts have no name and this figure cannot be held against "
            "any other figure over the same rows. Compute it with "
            "core.served.row_set_digest over the same keys",
        )
    claimed = payload[DIGEST_KEY]
    if not isinstance(claimed, str) or not _SHA256_HEX.fullmatch(claimed):
        raise CoverageRefused(
            DIGEST_MISMATCH,
            f"{DIGEST_KEY} is {claimed!r}, which is not a sha256. Two "
            "placeholders are equal to each other, so a tie to one is a tie "
            "that always holds. Use core.served.row_set_digest",
        )
    derived = _derive_rows(payload) if has_rows else _derive_groups(payload)
    if derived.digest != claimed:
        raise CoverageRefused(
            DIGEST_MISMATCH,
            f"the evidence names row set {claimed} and the {derived.unit} keys it "
            f"handed over digest to {derived.digest}. The figures were computed "
            "over one row set and attributed to another, or the keys are not the "
            "ones that were scored; either way the name and the operands are not "
            "about the same rows",
        )
    return derived


def disagreement(
    derived: DerivedCoverage, *, reported_empirical: float, reported_n: int
) -> str | None:
    """The refusal detail when the reported figures are not the derived ones.

    ``None`` when they agree, which is the only way past this module.
    """
    if reported_n != derived.n:
        return (
            f"the coverage binding reported n={reported_n} against the "
            f"{derived.n} its own {derived.unit} operands account for. A "
            "denominator that is not the number of rows measured is not the "
            "denominator of this proportion"
        )
    empirical = derived.empirical
    if not math.isfinite(reported_empirical):
        # Unreachable through D3, which refuses non-finite figures before the
        # tie so that the E-M09/E-M10 guards keep their own reasons. Held here
        # so the module is correct on its own terms for any other caller.
        return (
            f"the coverage binding reported a non-finite empirical against the "
            f"{empirical!r} its own {derived.unit} operands re-derive to"
        )
    gap = abs(reported_empirical - empirical)
    if gap > EMPIRICAL_AGREEMENT_EPS:
        return (
            f"the coverage binding reported empirical {reported_empirical!r} "
            f"against the {empirical!r} its own {derived.unit} operands re-derive "
            f"to -- {derived.covered} covered of {derived.n} -- differing by "
            f"{gap:.6g}. The figure a verdict is taken on is the one the rows "
            "support, and these rows do not support this one"
        )
    return None
