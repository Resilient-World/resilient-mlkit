"""One definition of "served" for the portfolio.

WHY THIS MODULE EXISTS
----------------------
The fleet converged on one definition of "ready" — mlkit's checks — while
growing THREE parallel definitions of "served". Measured 2026-08-29:

* ``resilient-chokepoint/src/resilient_chokepoint/mlops/champion_challenger.py``
  (267 lines: ``EvaluationUnmeasured``, ``ChallengerResult``, ``ShadowRouter``)
* ``resilient-torrent/src/torrent/mlops/champion_challenger.py``
  (160 lines: ``ChallengerResult``, ``ShadowRouter``, ``ChampionChallenger``)
* plus per-product serving modules in chokepoint, fray and triage, and eleven
  further files across fray and chokepoint carrying "is this promotable" logic.

Same filenames. Different SHAs. Overlapping but not identical APIs. That is
rule 7's own stated failure mode — *eight local copies of a gate is eight
different definitions of "ready", which is the same as none* — applied one
layer up. Three definitions of "served" is the same as none.

WHAT THE FOUR IMPLEMENTATIONS AGREE ON, AND SO WHAT IS IN HERE
--------------------------------------------------------------
The contract below is the INTERSECTION that is load-bearing, not a superset.
Four clauses, each of which all the serious implementations already have, and
each of which is already spelled slightly differently in each:

1. **A self-hashed artifact, verified at load.** All three serving modules
   compute the sha256 of the artifact's canonical JSON with the hash field
   excluded, and all three refuse to construct on a mismatch:
   ``resilient-triage/src/resilient_triage/serve/weekly_mortality.py:113-158``,
   ``resilient-fray/src/serve/county_yield.py:153-204``,
   ``resilient-chokepoint/src/resilient_chokepoint/serve/daily_flow_forecaster.py:141-199``.
   :func:`canonical_payload_sha256` here is byte-for-byte the same computation
   — ``sort_keys=True``, ``separators=(",", ":")``, ``allow_nan=False`` — so an
   already-committed artifact keeps its already-committed hash when a repo
   swaps its local copy for this one. That is not a nicety: a contract that
   changed the digest would invalidate every committed champion in the fleet.

2. **Provenance refusal against the bytes on disk.** A record's numbers belong
   to the data it names, and a file at the recorded path with a different
   sha256 is a different input wearing the record's filename:
   ``fray/src/registry/models_of_record.py:102-133``,
   ``fray/src/serve/county_yield.py:271-289``,
   ``triage/scripts/serve_weekly_mortality.py:74-80``.

3. **A challenger decision in which NA is not FAIL and not PASS.** An
   unmeasured comparison must never render as a pass, and must never render as
   a failure either — "we could not measure it" and "we measured it and it
   lost" are different facts that lead to different next actions:
   ``triage/.../weekly_mortality.py:444-508``,
   ``fray/src/serve/county_yield.py:638-757``,
   ``chokepoint/.../daily_flow_forecaster.py:497-600``,
   ``chokepoint/.../mlops/champion_challenger.py:64-95``.

4. **A serve-arm guard that refuses a closed arm by construction.**
   ``triage/scripts/serve_weekly_mortality.py:55,66-71`` and
   ``fray/scripts/serve_county_yield.py:104``.

WHAT IS DELIBERATELY *NOT* IN HERE
----------------------------------
* **A metric.** RMSE, MAE, AAL, CSI and BSS all appear as *the* decision metric
  in one repo or another. The contract takes the metric NAMES a caller declares
  and decides on measured skill; it does not compute anyone's loss function.

  It does, since 2026-08-31, require the caller to declare which DIRECTION each
  of those names runs in and what values it can take — see
  :data:`LOWER_IS_BETTER` / :data:`HIGHER_IS_BETTER` and :data:`NONNEGATIVE`.
  That is not a metric; it is the one property of a metric without which
  "beating the bar" has no meaning. Declared, never inferred from the name: a
  name→polarity table is the E-038 defect (``core.metric_registry``), where a
  guard keyed on a word list was blind to every name outside it and ``csi``
  in the list did not catch ``critical_success_index``.
* **A router.** ``ShadowRouter`` exists twice with the same name and opposite
  production semantics (see the divergence note below), and no third repo has
  one at all. Forcing five repos to grow a router two of them need would be the
  superset this module is explicitly not.
* **A test-arm prohibition.** Two repos close ``test`` and refuse it; chokepoint
  *requires* ``test`` and returns NA for val-only evidence
  (``daily_flow_forecaster.py:99,527-570``). Hard-coding "test is forbidden"
  would break a repo whose gate is correct. :class:`ServeArms` therefore makes
  the arm policy DATA the repo declares, and the guard mechanical.

THE DIVERGENCES THIS CONTRACT CLOSES
------------------------------------
* ``torrent/.../champion_challenger.py:30-40`` — ``ChallengerResult`` carries a
  bare ``promote: bool`` and no status at all. An unmeasured comparison there
  is indistinguishable from a measured loss, and
  ``evaluate_from_validation_bss:143-159`` narrows it further to a bare
  ``bool``. Here ``promotable`` is a derived property of a three-valued status
  and cannot be set independently of it.
* ``torrent/.../champion_challenger.py:128`` — ``deviation = ... if
  aal_baseline != 0 else 0.0``, so a zero baseline yields deviation ``0.0``,
  which is below tolerance, which **promotes**. chokepoint hits the identical
  condition at ``mlops/champion_challenger.py:209-218`` and returns NA with a
  reason. Same situation, opposite verdict. Here it is NA:
  :func:`skill` refuses a non-positive or non-finite reference value.
* ``fray/src/registry/models_of_record.py:176-184`` — the verdict dict has
  ``clears: bool`` and no status field; an NA metric and a lost metric both
  land as ``clears=False`` with only prose to tell them apart.
* ``ShadowRouter`` means opposite things in the two files that define it.
  chokepoint's ``predict`` always returns the CHAMPION's result and merely
  counts the challenger's (``champion_challenger.py:148-159``); torrent's
  ``__call__`` RETURNS the challenger's result when the hash bucket routes
  there (``champion_challenger.py:74-88``). One is a shadow; the other is a
  live A/B split serving unpromoted output to real traffic. They share a name.

NUMBERS IN THIS MODULE
----------------------
None. Nothing here contains a measured value, a threshold or a baseline as a
literal. Every figure a caller sees is one it passed in or one recomputed from
bytes on disk.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Iterable, Mapping, Sequence
from copy import deepcopy as _deepcopy
from dataclasses import InitVar, dataclass, field
from pathlib import Path
from typing import Any

from .result import Status

__all__ = [
    "BLOCKS_STRADDLE_ARMS",
    "DEPENDENCE_UNIT_CONTRADICTS_POLICY",
    "DEPENDENCE_UNIT_TOO_FINE",
    "DOMAINS",
    "HASH_KEY",
    "HIGHER_IS_BETTER",
    "IMPOSSIBLE_MEASUREMENT",
    "INTERVAL_COVERS_ZERO",
    "LOWER_IS_BETTER",
    "NONNEGATIVE",
    "POLARITIES",
    "POLARITY_UNDECLARED",
    "REAL",
    "RELATIONS",
    "RESAMPLING_ROWS_UNTIED",
    "ROW_SET_MISMATCH",
    "ROW_SET_UNTIED",
    "SINGLE_UNIT",
    "UNIT_COARSER_THAN_BLOCK",
    "UNIT_CROSSCUTS_ARMS",
    "UNIT_CROSSCUTS_BLOCK",
    "UNIT_FINER_THAN_BLOCK",
    "UNIT_IS_THE_BLOCK",
    "UNIT_LABEL_CONTRADICTS_CONTENT",
    "UNMEASURED",
    "ArtifactIntegrityError",
    "ChallengerDecision",
    "ClosedArm",
    "Comparison",
    "DataSource",
    "Measurement",
    "ProvenanceMismatch",
    "RecordedBar",
    "ResamplingDeclaration",
    "RowUnit",
    "ServeArms",
    "ServedContractError",
    "ServedModel",
    "canonical_payload_sha256",
    "challenger_decision",
    "out_of_domain",
    "row_set_digest",
    "seal",
    "sha256_file",
    "skill",
    "verify_at_load",
]

#: The key an artifact's own hash is stored under. All three serving modules in
#: the fleet already use this exact string; changing it would orphan every
#: committed champion, so it is fixed here rather than made configurable by
#: default.
HASH_KEY = "artifact_sha256"

#: What a comparison with no number says instead of a number. The string the
#: fleet already emits (fray ``county_yield.py:118``, chokepoint
#: ``daily_flow_forecaster.py:102``).
UNMEASURED = "NA"

#: Statuses a challenger decision may take. Deliberately three of the six in
#: :class:`~resilient_mlkit.core.result.Status`: a promotion decision is
#: measured-and-won, measured-and-lost, or not measured. There is no DEFERRED
#: promotion.
DECISION_STATUSES = (Status.PASS, Status.FAIL, Status.NA)


# ---------------------------------------------------------------------------
# What a metric IS, declared rather than assumed
# ---------------------------------------------------------------------------
#: The two directions a decision metric can run in. Which one applies is a
#: property of the metric, not of the gate, and the gate cannot derive it: MAE,
#: RMSE, MAPE, CRPS and pinball loss run one way; R², CSI, BSS, hit rate and
#: coverage run the other, and every one of those appears as *the* decision
#: metric somewhere in this fleet.
LOWER_IS_BETTER = "lower_is_better"
HIGHER_IS_BETTER = "higher_is_better"
POLARITIES = (LOWER_IS_BETTER, HIGHER_IS_BETTER)

#: What values the metric can take at all. ``REAL`` claims nothing. A metric
#: declared ``NONNEGATIVE`` cannot be negative in any arithmetic that produced
#: it, so a negative figure under that declaration is not a bad score — it is
#: evidence that whatever emitted it was not computing the metric it labelled.
REAL = "real"
NONNEGATIVE = "nonnegative"
DOMAINS = (REAL, NONNEGATIVE)


def out_of_domain(value: float | None, domain: str) -> bool:
    """True when ``value`` is a figure the declared ``domain`` cannot contain.

    ``None`` is not out of domain — it is unmeasured, which is a different
    verdict with a different refusal class, and collapsing the two would hide
    an impossible number inside the ordinary NA lane. Non-finite is likewise
    left to :func:`skill`, which already refuses it.
    """
    if value is None:
        return False
    value = float(value)
    if not math.isfinite(value):
        return False
    return domain == NONNEGATIVE and value < 0.0


# ---------------------------------------------------------------------------
# Refusals
# ---------------------------------------------------------------------------
class ServedContractError(RuntimeError):
    """Base for every refusal in the served-model contract."""


class ArtifactIntegrityError(ServedContractError):
    """The artifact is absent, malformed, or is not the bytes it was measured as."""


class ProvenanceMismatch(ServedContractError):
    """A file on disk is not the file the record's numbers were measured on."""


class ClosedArm(ServedContractError):
    """A serve request named an arm this product does not serve."""


# ---------------------------------------------------------------------------
# Hashing
# ---------------------------------------------------------------------------
def canonical_payload_sha256(payload: Mapping[str, Any], *, hash_key: str = HASH_KEY) -> str:
    """sha256 of an artifact's canonical JSON, excluding the hash field itself.

    Byte-for-byte the computation the three serving modules already perform, so
    that adopting this function leaves every committed ``artifact_sha256``
    unchanged. ``allow_nan=False`` is part of the contract, not an option: a
    ``NaN`` serialises to the non-JSON token ``NaN``, which no other reader can
    parse back, and a hash over unparseable bytes verifies nothing.
    """
    body = {k: v for k, v in payload.items() if k != hash_key}
    encoded = json.dumps(body, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


#: The shape every tie in this module is written in. A digest field that is
#: neither empty nor a sha256 is a caller who meant to tie two things together
#: and tied them to a placeholder instead.
_SHA256_HEX = re.compile(r"[0-9a-f]{64}")


def row_set_digest(row_keys: Iterable[Any]) -> str:
    """sha256 over the identifiers of the rows a figure was computed on.

    ONE definition, here, for the same reason :func:`canonical_payload_sha256`
    is one definition: two repos computing "the digest of the rows" two ways
    can never compare their answers, and a comparison whose two sides tie to
    incomparable digests is untied while looking tied.

    Order-invariant, because a row SET has no order and two scorers that
    iterated the same rows differently scored the same rows. Duplicates are
    NOT collapsed: a row scored twice on one side and once on the other is a
    genuine difference in what was compared.

    An empty key set is refused. A digest over no rows is a constant, and two
    comparisons carrying it would tie to each other and read as matched.
    """
    canonical = sorted(
        json.dumps(k, sort_keys=True, separators=(",", ":"), allow_nan=False)
        for k in row_keys
    )
    if not canonical:
        raise ServedContractError(
            "a row-set digest over no rows identifies nothing, and two of them "
            "would be equal to each other; pass the rows the figure was computed on"
        )
    return hashlib.sha256("\n".join(canonical).encode("utf-8")).hexdigest()


def sha256_file(path: Path | str) -> str:
    """sha256 of a file's bytes, streamed."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def seal(payload: Mapping[str, Any], *, hash_key: str = HASH_KEY) -> dict[str, Any]:
    """Return ``payload`` with its own canonical hash written in.

    The only supported way to produce an artifact this module will load. A repo
    that computes the digest itself is a repo that can compute it differently.
    """
    body = {k: v for k, v in payload.items() if k != hash_key}
    return {**body, hash_key: canonical_payload_sha256(body, hash_key=hash_key)}


# ---------------------------------------------------------------------------
# The dependence unit
# ---------------------------------------------------------------------------
# WHY THIS EXISTS, and what it is not.
#
# Round-8 adjudication measured this in `resilient-fray`. Its holdout policy,
# in its own words, puts WHOLE CROP YEARS in one partition, so the exchangeable
# unit is the crop year and VAL has five of them. The run's bootstrap resampled
# 1,365 ROWS as if independent:
#
#     resampling unit          point       95% CI                 clears zero
#     ROW (what was reported)  +22.811     [+16.016, +29.646]     yes
#     CROP-YEAR block (5)      +22.811     [-1.289, +41.704]      NO
#
# No gate was edited by anyone. fray's preregistration fixed the row bootstrap
# in advance and the run honoured it exactly. `resilient-chokepoint` resamples
# its dependence unit (corridor block, 28 clusters, predictions held fixed).
# Two repos, two conventions, one fleet -- and NOTHING IN MLKIT REQUIRED EITHER
# ONE, or required the choice to be stated at all. An interval could rest on a
# resampling unit nobody declared, and no instrument compared that unit to the
# holdout policy the same artifact declares.
#
# THE RULE, in one sentence:
#
#     A resampling procedure draws units and treats them as exchangeable. A
#     holdout policy that keeps a block whole has asserted that the block's
#     rows are NOT exchangeable -- that is the entire reason it refuses to
#     split them. So if the unit the procedure drew STAYS INSIDE THE DECIDING
#     ARM and SPLITS at least one of the policy's blocks, the procedure has
#     manufactured independent replicates out of exactly the rows the policy
#     refused to separate.
#
# WHAT THIS DOES NOT ESTABLISH, said here rather than left to be assumed.
# `UNIT_CROSSCUTS_ARMS` -- a unit whose keys appear in more than one arm, which
# is chokepoint's corridor -- is RECORDED, not blessed. A corridor bootstrap
# does not account for the temporal axis a time-blocked split partitions, and
# nothing here claims it does. What this type does is force both numbers into
# the record side by side: the units resampled, and the blocks in the arm that
# were not. Refusing the crosscutting case as well would make the fleet's
# CORRECT convention unadoptable, on a standard no measurement in this round
# supports, which is the R12 failure mode ("adopting the check would not clear
# it") one layer up.


#: The unit is exactly the unit the holdout policy keeps whole. fray's repair.
UNIT_IS_THE_BLOCK = "UNIT_IS_THE_BLOCK"
#: Whole blocks nest inside the resampled units. Conservative: the procedure
#: draws fewer, larger clusters than the policy's partitions.
UNIT_COARSER_THAN_BLOCK = "UNIT_COARSER_THAN_BLOCK"
#: The unit splits a block and stays inside the arm. The fray shape.
UNIT_FINER_THAN_BLOCK = "UNIT_FINER_THAN_BLOCK"
#: The unit splits a block AND a block splits a unit, both inside the arm.
#: Neither refines the other; still manufactures replicates out of blocks.
UNIT_CROSSCUTS_BLOCK = "UNIT_CROSSCUTS_BLOCK"
#: At least one resampled unit's rows appear in more than one arm, so the unit
#: is an axis the split does not partition. chokepoint's corridor.
UNIT_CROSSCUTS_ARMS = "UNIT_CROSSCUTS_ARMS"

RELATIONS = (
    UNIT_IS_THE_BLOCK,
    UNIT_COARSER_THAN_BLOCK,
    UNIT_FINER_THAN_BLOCK,
    UNIT_CROSSCUTS_BLOCK,
    UNIT_CROSSCUTS_ARMS,
)

#: The declared policy says whole blocks go to one partition; the assignment
#: says a block's rows are in two arms. The declaration describes a policy the
#: content does not have, and every later statement rests on it.
BLOCKS_STRADDLE_ARMS = "BLOCKS_STRADDLE_ARMS"
#: One unit cannot be resampled. Not a threshold -- arithmetic.
SINGLE_UNIT = "SINGLE_UNIT"
#: The refusal this whole section exists for.
DEPENDENCE_UNIT_TOO_FINE = "DEPENDENCE_UNIT_TOO_FINE"
#: The unit is LABELLED as the blocking unit and the assignment says it is
#: something else. A name is not a tie; the content is.
UNIT_LABEL_CONTRADICTS_CONTENT = "UNIT_LABEL_CONTRADICTS_CONTENT"


@dataclass(frozen=True)
class RowUnit:
    """One row of the panel, and the three groupings it belongs to.

    Four fields and no more, because the declaration below derives everything
    else from them and a fifth would be a place to put an assertion.

    * ``row_key`` — what identifies this row. The same identifier
      :func:`row_set_digest` takes, so a comparison's row digest and a
      declaration's row digest are computable to the same value.
    * ``arm`` — which partition the holdout policy put it in.
    * ``block_key`` — the key of the group the policy keeps WHOLE. fray: the
      crop year. chokepoint's daily-flow split: the date block.
    * ``unit_key`` — the key of the unit the resampling procedure DREW. fray as
      run: the row itself. chokepoint: the corridor.
    """

    row_key: Any
    arm: str
    block_key: Any
    unit_key: Any

    def __post_init__(self) -> None:
        if not str(self.arm).strip():
            raise ServedContractError(
                f"row {self.row_key!r} names no arm; a row that is in no partition "
                "cannot say anything about a holdout policy"
            )


def _canonical(key: Any) -> str:
    """The one spelling of a grouping key, so two of them compare by content."""
    try:
        return json.dumps(key, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ServedContractError(
            f"grouping key {key!r} is not JSON-serialisable ({exc}); a key that "
            "cannot be written down cannot be digested, and two keys that fall "
            "back to repr() compare by memory address"
        ) from exc


@dataclass(frozen=True)
class ResamplingDeclaration:
    """What a resampling procedure drew, and whether that contradicts the split.

    SIX THINGS ARE DECLARED and everything else is DERIVED. The declared six
    are labels and provenance — the procedure, its draws, the policy's name,
    the name of the unit the policy keeps whole, the name of the unit the
    procedure drew, and the arm. The counts, the three digests, the relation
    between the unit and the blocks, and the refusal are all computed here from
    ``assignment`` and are ``init=False``.

    That split is the point, and it is ``Comparison.row_matched``'s (M-06)
    applied one level up: **there is no spelling of the derived facts.**
    ``ResamplingDeclaration(..., n_units=5)`` is a ``TypeError`` naming the
    argument, and so are ``unit_digest=``, ``relation=`` and ``refusal=``. A
    caller who wants the answer to be "the unit is the block" has to hand over
    an assignment in which it is.

    ``assignment`` is the WHOLE panel, not the arm. Two of the derived facts
    are statements about arms other than the deciding one — whether the policy
    really keeps its blocks whole, and whether the resampled unit crosscuts the
    split — and neither is computable from the arm alone. That is also what
    separates chokepoint's corridor (present in train, val and test) from
    fray's row (present in exactly one), which is the distinction the whole
    refusal turns on.
    """

    procedure: str
    draws: int
    policy: str
    blocking_unit: str
    unit: str
    arm: str
    assignment: InitVar[Iterable[RowUnit]]

    # -- derived; see the class docstring. None of these is settable. --------
    n_rows: int = field(init=False, default=0)
    n_blocks_in_arm: int = field(init=False, default=0)
    n_units_in_arm: int = field(init=False, default=0)
    n_rows_panel: int = field(init=False, default=0)
    row_digest: str = field(init=False, default="")
    block_digest: str = field(init=False, default="")
    unit_digest: str = field(init=False, default="")
    #: The policy's block keys present in the deciding arm, as strings, sorted.
    #: Kept because this is the set a SECOND declaration of the same partition
    #: — the ``splits`` binding R3 already reads — can be compared against, and
    #: a declaration that is only ever compared to itself is not compared.
    block_keys_in_arm: tuple[str, ...] = field(init=False, default=())
    relation: str = field(init=False, default="")
    refusal: str = field(init=False, default="")
    detail: str = field(init=False, default="")

    def __post_init__(self, assignment: Iterable[RowUnit]) -> None:
        for name in ("procedure", "policy", "blocking_unit", "unit", "arm"):
            if not str(getattr(self, name)).strip():
                raise ServedContractError(
                    f"a resampling declaration must name its {name}; an unnamed "
                    "resampling procedure is the state this contract exists to end"
                )
        draws = self.draws
        if isinstance(draws, bool) or not isinstance(draws, int) or draws < 1:
            raise ServedContractError(
                f"resampling declares {draws!r} draws; a procedure that drew nothing "
                "produced no interval, and `True` is not a count"
            )

        rows = list(assignment)
        bad = [r for r in rows if not isinstance(r, RowUnit)]
        if bad:
            raise ServedContractError(
                f"assignment carries {type(bad[0]).__name__} entries; pass "
                "core.served.RowUnit, whose four fields are named. A bare tuple can "
                "be handed over with the block and the unit the wrong way round, and "
                "every verdict below would be exactly reversed with nothing to see."
            )
        if not rows:
            raise ServedContractError(
                "a resampling declaration over an empty assignment describes no rows; "
                "two of them would be equal to each other and read as matched"
            )

        seen: set[str] = set()
        duplicates: list[str] = []
        for r in rows:
            key = _canonical(r.row_key)
            if key in seen:
                duplicates.append(key)
            seen.add(key)
        if duplicates:
            raise ServedContractError(
                f"assignment repeats row key(s) {sorted(set(duplicates))[:3]}; a row "
                "listed twice is either two rows wearing one identifier or one row "
                "counted twice, and the two are not distinguishable from here"
            )

        in_arm = [r for r in rows if r.arm == self.arm]
        if not in_arm:
            raise ServedContractError(
                f"the assignment holds no row in arm {self.arm!r} (arms present: "
                f"{sorted({r.arm for r in rows})}); the interval was computed on rows "
                "that are not in this assignment"
            )

        arms_of_block: dict[str, set[str]] = {}
        arms_of_unit: dict[str, set[str]] = {}
        for r in rows:
            arms_of_block.setdefault(_canonical(r.block_key), set()).add(r.arm)
            arms_of_unit.setdefault(_canonical(r.unit_key), set()).add(r.arm)

        units_of_block: dict[str, set[str]] = {}
        blocks_of_unit: dict[str, set[str]] = {}
        raw_block: dict[str, Any] = {}
        raw_unit: dict[str, Any] = {}
        for r in in_arm:
            b, u = _canonical(r.block_key), _canonical(r.unit_key)
            raw_block.setdefault(b, r.block_key)
            raw_unit.setdefault(u, r.unit_key)
            units_of_block.setdefault(b, set()).add(u)
            blocks_of_unit.setdefault(u, set()).add(b)

        object.__setattr__(self, "n_rows_panel", len(rows))
        object.__setattr__(self, "n_rows", len(in_arm))
        object.__setattr__(self, "n_blocks_in_arm", len(units_of_block))
        object.__setattr__(self, "n_units_in_arm", len(blocks_of_unit))
        # Digested over the RAW keys, through the fleet's one row-set digest, so
        # that a repo which computes "the digest of the blocks" elsewhere lands
        # on the same hex string. Digesting the canonical strings instead would
        # encode them twice and tie only to this function's own private
        # spelling.
        object.__setattr__(self, "row_digest", row_set_digest(r.row_key for r in in_arm))
        object.__setattr__(self, "block_digest", row_set_digest(raw_block.values()))
        object.__setattr__(self, "unit_digest", row_set_digest(raw_unit.values()))
        object.__setattr__(
            self, "block_keys_in_arm", tuple(sorted(str(k) for k in raw_block.values()))
        )

        straddling = sorted(b for b, arms in arms_of_block.items() if len(arms) > 1)
        crosscutting = sorted(
            u for u in blocks_of_unit if len(arms_of_unit.get(u, set())) > 1
        )
        split_blocks = sorted(b for b, units in units_of_block.items() if len(units) > 1)
        split_units = sorted(u for u, blocks in blocks_of_unit.items() if len(blocks) > 1)

        if crosscutting:
            relation = UNIT_CROSSCUTS_ARMS
        elif split_blocks and split_units:
            relation = UNIT_CROSSCUTS_BLOCK
        elif split_blocks:
            relation = UNIT_FINER_THAN_BLOCK
        elif split_units:
            relation = UNIT_COARSER_THAN_BLOCK
        else:
            relation = UNIT_IS_THE_BLOCK
        object.__setattr__(self, "relation", relation)

        # The ladder. Order is the order the questions have to be answered:
        # a policy whose blocks straddle arms is not the policy that was
        # declared, so nothing computed against its blocks means anything yet.
        refusal, detail = "", ""
        if straddling:
            refusal = BLOCKS_STRADDLE_ARMS
            detail = (
                f"policy {self.policy!r} is declared to keep whole "
                f"{self.blocking_unit!r} blocks in one partition, but "
                f"{len(straddling)} of them appear in more than one arm "
                f"(e.g. {straddling[0]} in "
                f"{sorted(arms_of_block[straddling[0]])}). The declaration "
                "describes a policy this assignment does not have."
            )
        elif self.n_units_in_arm < 2:
            refusal = SINGLE_UNIT
            detail = (
                f"the {self.procedure} drew {self.unit!r} and arm {self.arm!r} "
                f"contains one of them ({self.n_rows} rows). A procedure that "
                "resamples a single unit resamples the same thing every draw; the "
                "interval it produces has no width that came from the data."
            )
        elif not crosscutting and split_blocks:
            refusal = DEPENDENCE_UNIT_TOO_FINE
            detail = (
                f"the {self.procedure} resampled {self.n_units_in_arm} "
                f"{self.unit!r} unit(s) inside arm {self.arm!r}, but holdout policy "
                f"{self.policy!r} keeps whole {self.blocking_unit!r} blocks in one "
                f"partition and that arm holds {self.n_blocks_in_arm} of them. "
                f"{len(split_blocks)} block(s) are split across units (e.g. "
                f"{split_blocks[0]} spans "
                f"{len(units_of_block[split_blocks[0]])} units). The policy declares "
                f"rows inside a {self.blocking_unit!r} to be dependent -- that is why "
                "it refuses to separate them -- and this procedure drew them as "
                "independent replicates, so it manufactured more evidence out of the "
                f"arm than the arm contains. Resample {self.blocking_unit!r}, or "
                "declare a unit the split does not partition."
            )
        elif self.unit == self.blocking_unit and relation != UNIT_IS_THE_BLOCK:
            refusal = UNIT_LABEL_CONTRADICTS_CONTENT
            detail = (
                f"the unit resampled is LABELLED {self.unit!r}, the same name as the "
                f"policy's blocking unit, and the assignment says the relation is "
                f"{relation}. Two things called by one name are not tied to each "
                "other by being called that; the assignment is the tie and it "
                "disagrees."
            )
        object.__setattr__(self, "refusal", refusal)
        object.__setattr__(self, "detail", detail)

    @property
    def contradicts_policy(self) -> bool:
        """True when this declaration refuses itself against its own policy."""
        return bool(self.refusal)

    def to_dict(self) -> dict[str, Any]:
        return {
            "procedure": self.procedure,
            "draws": self.draws,
            "policy": self.policy,
            "blocking_unit": self.blocking_unit,
            "unit": self.unit,
            "arm": self.arm,
            "n_rows": self.n_rows,
            "n_rows_panel": self.n_rows_panel,
            # Reported TOGETHER, always. The number of units resampled means
            # nothing without the number of blocks the arm holds that were not,
            # and a table carrying only the first is how a five-year holdout
            # reads as 1,365 independent draws.
            "n_units_in_arm": self.n_units_in_arm,
            "n_blocks_in_arm": self.n_blocks_in_arm,
            "row_digest": self.row_digest,
            "block_digest": self.block_digest,
            "unit_digest": self.unit_digest,
            "relation": self.relation,
            "refusal": self.refusal or UNMEASURED,
            "detail": self.detail,
        }


# ---------------------------------------------------------------------------
# The record
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class DataSource:
    """One input file the record's numbers belong to, pinned by its bytes."""

    path: str
    sha256: str
    role: str = "training"

    def __post_init__(self) -> None:
        if not self.path:
            raise ArtifactIntegrityError("a data source with no path pins nothing")
        if not self.sha256:
            raise ArtifactIntegrityError(
                f"data source {self.path!r} carries no sha256; the bytes it was "
                "measured on are unidentifiable and this contract will not guess"
            )

    def verify(self, root: Path | str) -> str:
        """Hash the file under ``root`` and refuse it if it is not the pinned one."""
        resolved = Path(root) / self.path
        if not resolved.is_file():
            raise ProvenanceMismatch(
                f"{self.role} source {self.path} is absent at {resolved}; the bytes "
                f"the record was measured on are not here (pinned {self.sha256})"
            )
        actual = sha256_file(resolved)
        if actual != self.sha256:
            raise ProvenanceMismatch(
                f"{self.role} source {self.path} hashes to {actual} but the record "
                f"pins {self.sha256}; the file on disk is different data wearing the "
                "recorded filename"
            )
        return actual

    def to_dict(self) -> dict[str, Any]:
        return {"path": self.path, "sha256": self.sha256, "role": self.role}

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> DataSource:
        return cls(
            path=str(d.get("path", "")),
            sha256=str(d.get("sha256", "")),
            role=str(d.get("role", "training")),
        )


@dataclass(frozen=True)
class Measurement:
    """One committed figure, with the artifact it was read out of.

    A value with no artifact behind it is a remembered number, which rule 3
    says is not a number at all. A measurement with no value must say why —
    the same invariant :class:`~resilient_mlkit.core.result.CheckResult`
    enforces for a check, applied to a served model's own record.
    """

    arm: str
    metric: str
    value: float | None
    artifact: str = ""
    artifact_sha256: str = ""
    unmeasured_reason: str = ""

    def __post_init__(self) -> None:
        if not self.arm or not self.metric:
            raise ArtifactIntegrityError(
                "a measurement must name the arm it was taken on and the metric it is in"
            )
        if self.value is None:
            if not self.unmeasured_reason.strip():
                raise ArtifactIntegrityError(
                    f"measurement {self.metric!r} on arm {self.arm!r} has no value and "
                    "no reason; an unexplained absence looks like coverage and carries "
                    "no information"
                )
            return
        if not math.isfinite(float(self.value)):
            raise ArtifactIntegrityError(
                f"measurement {self.metric!r} on arm {self.arm!r} is {self.value!r}; a "
                "non-finite figure is not a measurement"
            )
        if not self.artifact or not self.artifact_sha256:
            raise ArtifactIntegrityError(
                f"measurement {self.metric!r} on arm {self.arm!r} carries a value but "
                "no artifact path and sha256; a figure that cannot be traced back to "
                "the bytes it was read from is not citable"
            )

    @property
    def measured(self) -> bool:
        return self.value is not None

    def to_dict(self) -> dict[str, Any]:
        return {
            "arm": self.arm,
            "metric": self.metric,
            "value": self.value,
            "artifact": self.artifact,
            "artifact_sha256": self.artifact_sha256,
            "unmeasured_reason": self.unmeasured_reason,
        }

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> Measurement:
        raw = d.get("value")
        return cls(
            arm=str(d.get("arm", "")),
            metric=str(d.get("metric", "")),
            value=None if raw is None else float(raw),
            artifact=str(d.get("artifact", "")),
            artifact_sha256=str(d.get("artifact_sha256", "")),
            unmeasured_reason=str(d.get("unmeasured_reason", "")),
        )


@dataclass(frozen=True)
class RecordedBar:
    """The reference a served model was promoted against and stays compared to.

    A champion that silently stops being compared to the reference it beat is
    how a win rots (``triage/.../weekly_mortality.py:444-462``). The bar is part
    of the record, so it travels with the artifact rather than living in
    whichever script last scored it.
    """

    name: str
    metrics: tuple[str, ...]
    description: str = ""

    def __post_init__(self) -> None:
        if not self.name:
            raise ArtifactIntegrityError("a recorded bar must be named")
        if not self.metrics:
            raise ArtifactIntegrityError(
                f"recorded bar {self.name!r} names no decision metric; a bar with no "
                "metric cannot be cleared or missed"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "metrics": list(self.metrics),
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> RecordedBar:
        return cls(
            name=str(d.get("name", "")),
            metrics=tuple(str(m) for m in (d.get("metrics") or ())),
            description=str(d.get("description", "")),
        )


@dataclass(frozen=True)
class ServedModel:
    """What the portfolio means by a served model.

    Constructed only through :func:`verify_at_load`, :meth:`from_payload` or
    :meth:`load`, all of which verify the self-hash FIRST. A model whose bytes
    changed since it was written is not the model that was measured, and this
    class refuses to become one.
    """

    model_id: str
    fit: Mapping[str, Any]
    training_data: tuple[DataSource, ...]
    recorded_bar: RecordedBar
    measurements: tuple[Measurement, ...]
    artifact_sha256: str
    payload: Mapping[str, Any] = field(default_factory=dict, repr=False)

    # -- construction -------------------------------------------------------
    @classmethod
    def from_payload(
        cls,
        payload: Mapping[str, Any],
        *,
        hash_key: str = HASH_KEY,
        root: Path | str | None = None,
    ) -> ServedModel:
        """Verify and build. See :func:`verify_at_load`, which this delegates to."""
        return verify_at_load(payload, hash_key=hash_key, root=root)

    @classmethod
    def load(
        cls,
        path: Path | str,
        *,
        hash_key: str = HASH_KEY,
        root: Path | str | None = None,
    ) -> ServedModel:
        """Read an artifact from disk and verify it.

        ``root`` is the directory the record's ``path`` fields are relative to.
        Passing it makes the load verify data provenance as well as the
        self-hash; omitting it verifies the self-hash only, and the caller is
        then holding a record it has not checked against the data on disk.
        """
        path = Path(path)
        if not path.is_file():
            raise ArtifactIntegrityError(
                f"no served-model artifact at {path}. The absence of a champion is "
                "not a licence to serve a default."
            )
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ArtifactIntegrityError(f"{path} is not readable JSON: {exc}") from exc
        if not isinstance(payload, dict):
            raise ArtifactIntegrityError(
                f"{path} does not hold a JSON object; it is a {type(payload).__name__}"
            )
        return verify_at_load(payload, hash_key=hash_key, root=root)

    # -- provenance ---------------------------------------------------------
    def verify_provenance(self, root: Path | str) -> dict[str, str]:
        """Hash every pinned input under ``root``; raise on the first mismatch.

        Returns ``{path: sha256}`` for what was actually hashed, so a caller can
        record what it verified rather than asserting that it did.
        """
        return {source.path: source.verify(root) for source in self.training_data}

    # -- reading the record --------------------------------------------------
    def measurement(self, arm: str, metric: str) -> Measurement | None:
        for m in self.measurements:
            if m.arm == arm and m.metric == metric:
                return m
        return None

    def measured_arms(self) -> tuple[str, ...]:
        seen: list[str] = []
        for m in self.measurements:
            if m.arm not in seen:
                seen.append(m.arm)
        return tuple(seen)

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "fit": dict(self.fit),
            "training_data": [s.to_dict() for s in self.training_data],
            "recorded_bar": self.recorded_bar.to_dict(),
            "measurements": [m.to_dict() for m in self.measurements],
            HASH_KEY: self.artifact_sha256,
        }


def verify_at_load(
    payload: Mapping[str, Any],
    *,
    hash_key: str = HASH_KEY,
    root: Path | str | None = None,
) -> ServedModel:
    """Recompute the self-hash, refuse on mismatch, and refuse on stale data.

    Two refusals, in this order, because they answer two different questions
    and the first one has to be settled before the second means anything:

    1. **Is this the artifact that was measured?** The hash is recomputed over
       the canonical payload with the hash field excluded. An artifact carrying
       no hash is refused outright — an unhashed record has no provenance, and
       accepting it would let a hand-written file serve as a measurement.
    2. **Is this the data it was measured on?** Only when ``root`` is given.
       Every pinned source is hashed on disk. A file that is absent, or present
       with different bytes, is a refusal rather than a warning: the record's
       numbers do not describe it.
    """
    recorded = payload.get(hash_key)
    if not recorded:
        raise ArtifactIntegrityError(
            f"artifact carries no {hash_key}; an unhashed record has no provenance "
            "and will not be served"
        )
    recomputed = canonical_payload_sha256(payload, hash_key=hash_key)
    if recomputed != recorded:
        raise ArtifactIntegrityError(
            f"served-model artifact hash mismatch: recorded {recorded}, recomputed "
            f"{recomputed}. The bytes changed since the artifact was measured; "
            "refusing to serve it."
        )

    model_id = str(payload.get("model_id") or "")
    if not model_id:
        raise ArtifactIntegrityError("artifact carries no model_id")

    sources = tuple(
        DataSource.from_dict(s) for s in (payload.get("training_data") or ())
    )
    if not sources:
        raise ArtifactIntegrityError(
            f"{model_id} pins no training data; a model whose inputs are "
            "unidentifiable cannot have its numbers attributed to anything"
        )

    bar = RecordedBar.from_dict(payload.get("recorded_bar") or {})
    measurements = tuple(
        Measurement.from_dict(m) for m in (payload.get("measurements") or ())
    )
    if not measurements:
        raise ArtifactIntegrityError(
            f"{model_id} carries no measurements; a served model with no committed "
            "figure has nothing for a challenger to be compared against"
        )

    model = ServedModel(
        model_id=model_id,
        fit=dict(payload.get("fit") or {}),
        training_data=sources,
        recorded_bar=bar,
        measurements=measurements,
        artifact_sha256=str(recorded),
        payload=dict(payload),
    )
    if root is not None:
        model.verify_provenance(root)
    return model


# ---------------------------------------------------------------------------
# The challenger decision
# ---------------------------------------------------------------------------
def skill(
    candidate: float | None,
    reference: float | None,
    *,
    polarity: str | None = None,
    domain: str = REAL,
) -> float | None:
    """Positive when the candidate beat the reference, in the DECLARED direction.

    ``1 - candidate/reference`` for a lower-is-better metric;
    ``candidate/reference - 1`` for a higher-is-better one. Both are positive
    exactly when the candidate won, and neither can be derived from the other
    without knowing which way the metric runs — which is why ``polarity`` is a
    parameter and not a default.

    ``None`` — not zero, not a raised exception — whenever the quotient is not
    a number about accuracy:

    * either side missing, or either side non-finite;
    * a reference of zero or below. That case is
      ``torrent/.../champion_challenger.py:128`` inverted: there, a zero
      baseline silently produced a deviation of ``0.0``, which cleared the
      tolerance and PROMOTED. Here it is unmeasured, which is what chokepoint's
      counterpart already concluded from the identical condition. It stays a
      refusal under ``HIGHER_IS_BETTER`` too: a bar at or below zero makes the
      ratio say more about the divisor than about either model, and a gate that
      guessed which side that favoured would be guessing;
    * **a polarity that was not declared.** Until this parameter existed, this
      function applied the lower-is-better formula to every metric name a
      caller passed, so an r² of 0.10 against a bar of 0.90 returned ``0.8889``
      and PROMOTED (measured at 8517341). Defaulting the other way would be the
      same defect with the opposite sign, so the undeclared case is unmeasured;
    * **a value the declared domain cannot contain** — see :func:`out_of_domain`.
      A negative MAPE against a bar of 0.20 returned ``1.25`` and promoted
      hardest of all, because the impossibility pushed the quotient furthest.
      Impossible is not "unmeasured" in any interesting sense, but it is
      certainly not a skill number, and the caller that needs to tell the two
      apart gets a named refusal class from :func:`challenger_decision` rather
      than from here.
    """
    if candidate is None or reference is None:
        return None
    candidate = float(candidate)
    reference = float(reference)
    if not math.isfinite(candidate) or not math.isfinite(reference):
        return None
    if polarity not in POLARITIES:
        return None
    if domain not in DOMAINS:
        return None
    if out_of_domain(candidate, domain) or out_of_domain(reference, domain):
        return None
    if reference <= 0.0:
        return None
    if polarity == HIGHER_IS_BETTER:
        return candidate / reference - 1.0
    return 1.0 - candidate / reference


@dataclass(frozen=True)
class Comparison:
    """A candidate and a reference, in one metric, on ONE row set.

    ``n_rows`` and ``row_matched`` are both here because they answer different
    questions. ``n_rows`` is how much was compared; ``row_matched`` is whether
    the reference predicted the same rows the candidate did. A reference scored
    on a subset produced a number about a different row set, and two numbers
    about different row sets sitting side by side look comparable without being
    so (``fray/src/serve/county_yield.py:700-711``).

    ``row_matched`` USED TO BE A CALLER-SUPPLIED ``bool`` DEFAULTING TO ``True``
    (M-06, 2026-08-31). That default is the defect: the gate's whole
    row-set clause rested on an assertion the caller made for free, and every
    comparison that never thought about row sets asserted the strongest
    possible claim about them. Measured at 8517341, an ordinary
    ``Comparison(bar, "mae", 80.0, 100.0, 500, arm="val")`` — no row evidence of
    any kind — reached PASS.

    It is now DERIVED from two digests, and there is no way to spell the
    assertion. Both digests present and equal → ``True``; present and unequal →
    ``False``; either absent → ``None``, which is *untied*: not matched, not
    mismatched, not known. ``None`` is NA at the gate, not a pass. This is
    fray's split-identity/E-043 pattern moved into the contract — every
    comparison operand needs a tie, and the tie is content, not a promise.
    """

    reference: str
    metric: str
    candidate_value: float | None
    reference_value: float | None
    n_rows: int
    arm: str = ""
    unmeasured_reason: str = ""
    #: Which direction this metric runs in, and what values it can take. Both
    #: are DATA the caller declares, in the same shape :class:`ServeArms` makes
    #: the arm policy data, and for the same reason: the fleet does not agree
    #: on one answer and both answers are correct in their own repo. A
    #: comparison that declares no polarity is not decided against a guess.
    polarity: str = ""
    domain: str = REAL
    #: sha256 of the row identifiers each side's figure was computed over, from
    #: :func:`row_set_digest`. Content, not a promise: the only two things that
    #: can make these equal are the same rows on both sides.
    candidate_row_digest: str = ""
    reference_row_digest: str = ""
    #: Bounds on THIS comparison's ``skill`` — the same quantity :attr:`skill`
    #: computes, not a bound on the candidate's raw metric and not a bound on a
    #: difference of metrics. An interval on a different quantity than the one
    #: the gate decides is untied while looking tied, so ``__post_init__``
    #: refuses an interval that does not contain its own point estimate.
    skill_interval_low: float | None = None
    skill_interval_high: float | None = None
    #: What produced that interval, and what it drew. An interval is the output
    #: of a resampling procedure, so there is no way to declare one here
    #: without declaring the unit: an interval with no declaration raises, and a
    #: declaration with no interval raises. That is the whole of "an adopter
    #: cannot silently use the weaker convention" at this layer — the weaker
    #: convention is still spellable, but it is no longer silent, because the
    #: unit it drew is in the record and is compared to the policy beside it.
    resampling: ResamplingDeclaration | None = None
    #: DERIVED in ``__post_init__``, never passed in. ``init=False`` is the
    #: point: ``Comparison(..., row_matched=True)`` is a TypeError naming the
    #: argument, so the assertion the gate used to rest on cannot be spelled at
    #: all — not by a caller who forgot to think about rows, and not by one who
    #: wants the answer to be True.
    row_matched: bool | None = field(init=False, default=None)

    def __post_init__(self) -> None:
        if not self.reference or not self.metric:
            raise ServedContractError("a comparison must name its reference and metric")
        if self.n_rows < 0:
            raise ServedContractError(
                f"comparison against {self.reference!r} reports {self.n_rows} rows; a "
                "negative row count is not a row count"
            )
        if self.polarity and self.polarity not in POLARITIES:
            raise ServedContractError(
                f"comparison on {self.metric!r} declares polarity {self.polarity!r}; "
                f"the declared polarities are {list(POLARITIES)}. A spelling this "
                "contract does not recognise is not a declaration, and treating it as "
                "one would restore the assumption this field exists to remove."
            )
        if self.domain not in DOMAINS:
            raise ServedContractError(
                f"comparison on {self.metric!r} declares domain {self.domain!r}; the "
                f"declared domains are {list(DOMAINS)}"
            )
        for side, digest in (
            ("candidate", self.candidate_row_digest),
            ("reference", self.reference_row_digest),
        ):
            if not digest:
                continue
            if not _SHA256_HEX.fullmatch(digest):
                raise ServedContractError(
                    f"comparison on {self.metric!r} carries {side}_row_digest "
                    f"{digest!r}, which is not a sha256. Two placeholders are equal "
                    "to each other, so a tie written in anything but content is a "
                    "tie that always holds. Use core.served.row_set_digest."
                )
        if self.candidate_row_digest and self.reference_row_digest:
            derived: bool | None = (
                self.candidate_row_digest == self.reference_row_digest
            )
        else:
            derived = None
        object.__setattr__(self, "row_matched", derived)
        self._check_interval()

    def _check_interval(self) -> None:
        """Refuse an interval and a declaration that are not each other's.

        Five refusals, all at construction, because each is a malformed
        declaration rather than a verdict about evidence — there is nothing for
        a reader to weigh in "one endpoint without the other".
        """
        lo, hi = self.skill_interval_low, self.skill_interval_high
        has_interval = lo is not None or hi is not None
        if has_interval and (lo is None or hi is None):
            raise ServedContractError(
                f"comparison on {self.metric!r} declares one interval endpoint and not "
                "the other; half an interval bounds nothing"
            )
        if has_interval and self.resampling is None:
            raise ServedContractError(
                f"comparison on {self.metric!r} carries the interval "
                f"[{lo!r}, {hi!r}] and no resampling declaration. An interval is the "
                "output of a resampling procedure, and the unit that procedure drew is "
                "the difference between [+16.016, +29.646] and [-1.289, +41.704] on "
                "one identical set of 1,365 rows (round-8 adjudication 2.1). Declare "
                "it with core.served.ResamplingDeclaration."
            )
        if self.resampling is not None and not has_interval:
            raise ServedContractError(
                f"comparison on {self.metric!r} carries a resampling declaration and "
                "no interval. A declaration about nothing declares nothing, and it "
                "would render in the record beside comparisons that do carry one."
            )
        if not has_interval:
            return

        low, high = float(lo), float(hi)  # type: ignore[arg-type]
        nonfinite = [
            name for name, v in (("low", low), ("high", high)) if not math.isfinite(v)
        ]
        if nonfinite:
            raise ServedContractError(
                f"comparison on {self.metric!r} declares a non-finite interval "
                f"endpoint ({', '.join(nonfinite)}); an infinity is not a bound and a "
                "NaN compares False to zero in both directions, which is the one "
                "question an interval is asked"
            )
        if low > high:
            raise ServedContractError(
                f"comparison on {self.metric!r} declares the interval [{low!r}, "
                f"{high!r}], whose lower bound is above its upper one"
            )
        declaration = self.resampling
        assert declaration is not None  # narrowed by has_interval above
        if not self.arm:
            raise ServedContractError(
                f"comparison on {self.metric!r} carries a resampling declaration for "
                f"arm {declaration.arm!r} and names no arm of its own; there is "
                "nothing to tie the declaration to"
            )
        if declaration.arm != self.arm:
            raise ServedContractError(
                f"comparison on {self.metric!r} was measured on arm {self.arm!r} and "
                f"its interval was resampled on arm {declaration.arm!r}; a bound taken "
                "on other rows is not a bound on this figure"
            )
        point = self.skill
        if point is not None and not (low <= point <= high):
            raise ServedContractError(
                f"comparison on {self.metric!r} declares the interval [{low!r}, "
                f"{high!r}], which does not contain its own point estimate {point!r}. "
                "These fields bound THIS comparison's skill — 1 - candidate/reference "
                "for a lower-is-better metric — and an interval on some other "
                "quantity (a difference in the metric's own units, say) ties to "
                "nothing here while reading as though it does."
            )

    @property
    def declared(self) -> bool:
        """True when this comparison says which direction its metric runs in."""
        return self.polarity in POLARITIES

    @property
    def impossible(self) -> tuple[str, ...]:
        """Which operands hold a figure the declared domain cannot contain."""
        offending: list[str] = []
        if out_of_domain(self.candidate_value, self.domain):
            offending.append("candidate")
        if out_of_domain(self.reference_value, self.domain):
            offending.append("reference")
        return tuple(offending)

    @property
    def skill(self) -> float | None:
        return skill(
            self.candidate_value,
            self.reference_value,
            polarity=self.polarity or None,
            domain=self.domain,
        )

    @property
    def has_interval(self) -> bool:
        """True when this comparison carries a bound AND what produced it.

        One property rather than two reads, because ``__post_init__`` has
        already refused every state in which the endpoints and the declaration
        disagree about whether an interval exists.
        """
        return self.skill_interval_low is not None

    @property
    def interval_clears_zero(self) -> bool | None:
        """True when the whole interval is above zero. ``None`` when untied.

        Above zero, not away from zero: :func:`skill` is already signed so that
        positive means the candidate won, whichever direction the metric runs
        in, so "clears" is one comparison and not two.
        """
        low = self.skill_interval_low
        if low is None:
            return None
        return float(low) > 0.0

    def to_dict(self) -> dict[str, Any]:
        measured = self.skill
        return {
            "reference": self.reference,
            "metric": self.metric,
            "arm": self.arm,
            "candidate_value": self.candidate_value,
            "reference_value": self.reference_value,
            "polarity": self.polarity or UNMEASURED,
            "domain": self.domain,
            "skill": UNMEASURED if measured is None else measured,
            "n_rows": self.n_rows,
            "candidate_row_digest": self.candidate_row_digest or UNMEASURED,
            "reference_row_digest": self.reference_row_digest or UNMEASURED,
            # UNMEASURED rather than null, and never False: "nobody tied the row
            # sets" and "the row sets differ" are different facts, and a reader
            # who cannot tell them apart will read the first as the second and
            # go looking for a split that is not there.
            "row_matched": UNMEASURED if self.row_matched is None else self.row_matched,
            # UNMEASURED rather than null, for the reason `row_matched` is:
            # "this figure carries no interval" and "this interval is null" are
            # different facts, and only one of them is a state a resampling
            # procedure can be in.
            "skill_interval": (
                UNMEASURED
                if not self.has_interval
                else [self.skill_interval_low, self.skill_interval_high]
            ),
            "interval_clears_zero": (
                UNMEASURED
                if self.interval_clears_zero is None
                else self.interval_clears_zero
            ),
            "resampling": (
                UNMEASURED if self.resampling is None else self.resampling.to_dict()
            ),
            "unmeasured_reason": self.unmeasured_reason,
        }


#: Why a decision refused, in a token a caller can branch on without matching
#: prose. chokepoint already needed one of these
#: (``daily_flow_forecaster.py:106``) and had to invent it locally.
NOT_COMPARED = "NOT_COMPARED"
NO_ROWS = "NO_ROWS"
ROW_SET_MISMATCH = "ROW_SET_MISMATCH"
ARM_MISMATCH = "ARM_MISMATCH"
UNMEASURED_SKILL = "UNMEASURED_SKILL"
NO_SKILL = "NO_SKILL"
CLEARS_BAR = "CLEARS_BAR"
#: The figure cannot be the metric it is labelled as. Distinct from
#: ``UNMEASURED_SKILL`` on purpose: "we could not measure it" sends someone to
#: look at the harness, "this number is impossible" sends someone to look at
#: the scorer, and a table that renders them identically answers neither.
IMPOSSIBLE_MEASUREMENT = "IMPOSSIBLE_MEASUREMENT"
#: Nobody said which direction the metric runs in, so nobody can say who won.
POLARITY_UNDECLARED = "POLARITY_UNDECLARED"
#: Nobody tied the two figures to the rows they were computed on. Kept apart
#: from ``ROW_SET_MISMATCH`` on purpose: "the row sets differ" sends a reader
#: to find the split, "nobody said" sends them to add the digests, and until
#: 2026-08-31 the second condition silently reported the strongest form of the
#: opposite (``row_matched: bool = True``).
ROW_SET_UNTIED = "ROW_SET_UNTIED"
#: The interval was resampled over rows that are not the rows the point
#: estimate was computed over. Kept apart from ``ROW_SET_MISMATCH``, which is
#: about the candidate and the reference: this one is about the point and its
#: own interval, and the two send a reader to different places.
RESAMPLING_ROWS_UNTIED = "RESAMPLING_ROWS_UNTIED"
#: The unit the interval's procedure drew contradicts the holdout policy the
#: same comparison declares. See :class:`ResamplingDeclaration`.
DEPENDENCE_UNIT_CONTRADICTS_POLICY = "DEPENDENCE_UNIT_CONTRADICTS_POLICY"
#: The point estimate cleared the bar and the interval around it does not.
#: This is a FAIL and not an NA: the comparison WAS measured, and what it
#: measured is a margin that its own resampling cannot distinguish from zero.
INTERVAL_COVERS_ZERO = "INTERVAL_COVERS_ZERO"


@dataclass(frozen=True)
class ChallengerDecision:
    """PASS, FAIL or NA — and ``promotable`` is derived from that, never set.

    The structural point of this class, and the reason it is a class rather
    than a dict: **NA is not FAIL and not PASS.** Three of the fleet's five
    promotion paths already agree on that in prose, and two of them lose it in
    their data shape — ``torrent/.../champion_challenger.py:39`` has only
    ``promote: bool``, ``fray/src/registry/models_of_record.py:177`` has only
    ``clears: bool``. In both, an unmeasured comparison and a measured loss are
    the same value, and only the surrounding prose distinguishes them. Prose is
    not a field anyone can branch on.

    Here:

    * ``promotable`` is a property equal to ``status is PASS``. It cannot be
      set to ``True`` on an NA, because it cannot be set at all.
    * an NA carries **no skill number** — every entry is ``None``. A decision
      that could not measure the comparison has nothing to report as the
      comparison's value, and reporting one anyway is how an unmeasured figure
      gets quoted downstream as if it were measured.
    * a PASS requires a measured, strictly positive skill for **every** declared
      decision metric. A pass on a metric nobody scored is the defect the whole
      instrument exists to catch.
    * FAIL and NA both require a reason.
    """

    status: Status
    reason: str
    recorded_bar: str
    metrics: tuple[str, ...]
    skill: Mapping[str, float | None]
    n_rows: int = 0
    refusal_class: str = ""
    evidence: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if isinstance(self.status, str):
            object.__setattr__(self, "status", Status(self.status))
        # FIRST, before any of the clauses below, because all of them are
        # comprehensions over `self.metrics` and an empty tuple satisfies every
        # one of them vacuously. Measured at 8517341:
        # `ChallengerDecision(status=PASS, reason=..., metrics=(), skill={})`
        # constructed, and `promotable` -- derived correctly, doing its job --
        # returned True. `challenger_decision()` already refused this, but that
        # refusal lives in the function and this type is public, so the
        # function could simply be stepped around. A guard that only one path
        # into an object performs is a guard on that path, not on the object.
        if not self.metrics:
            raise ServedContractError(
                "a challenger decision declares no metric. Every clause that makes "
                "a PASS mean something is a statement about the declared metrics, "
                "so a decision over none of them passes every clause without "
                "having been compared to anything."
            )
        if self.status not in DECISION_STATUSES:
            raise ServedContractError(
                f"a challenger decision is {[s.value for s in DECISION_STATUSES]}; "
                f"{self.status.value} is not one of them. There is no DEFERRED "
                "promotion: a promotion that is waiting on something has not happened."
            )
        if self.status in (Status.FAIL, Status.NA) and not self.reason.strip():
            raise ServedContractError(
                f"a {self.status.value} decision must say why; an unexplained refusal "
                "is indistinguishable from a bug in the gate"
            )
        missing = [m for m in self.metrics if m not in self.skill]
        if missing:
            raise ServedContractError(
                f"decision declares metrics {list(self.metrics)} but reports no skill "
                f"entry for {missing}; a metric with no entry is a metric nobody scored"
            )
        # Found by driving this class adversarially after the M-02 repair
        # landed: a skill dict WIDER than the declared metrics constructed
        # cleanly, and `skill_vs_recorded_bar` then carried a figure for a
        # metric the decision never decided on. Downstream that number is
        # quotable exactly like the ones that were decided, with nothing in the
        # record marking it as an extra.
        extra = sorted(set(self.skill) - set(self.metrics))
        if extra:
            raise ServedContractError(
                f"decision declares metrics {list(self.metrics)} but reports skill "
                f"for {extra} as well. A figure in the skill map that no clause of "
                "this decision examined is a number nobody decided on, sitting where "
                "readers take numbers to have been decided on."
            )
        # Same drive: `float('nan') <= 0.0` is False, so a PASS carrying a NaN
        # skill satisfied the non-positive clause below and came out
        # promotable. A non-finite skill is not a margin over the bar in either
        # direction, on any status.
        nonfinite = sorted(
            m for m, v in self.skill.items()
            if v is not None and not math.isfinite(float(v))
        )
        if nonfinite:
            raise ServedContractError(
                f"decision reports non-finite skill on {nonfinite}. A NaN is not a "
                "margin over the bar and an infinity is not a bigger one; neither "
                "compares to zero, which is the only question this verdict asks."
            )
        if self.status is Status.NA:
            reported = {k: v for k, v in self.skill.items() if v is not None}
            if reported:
                raise ServedContractError(
                    f"an NA decision reports skill values {reported}; NA means the "
                    "comparison was not measured, and a number attached to it would be "
                    "quoted downstream as though it had been"
                )
        if self.status is Status.PASS:
            unmeasured = [m for m in self.metrics if self.skill.get(m) is None]
            if unmeasured:
                raise ServedContractError(
                    f"a PASS decision has no measured skill on {unmeasured}; a pass on "
                    "an unscored metric is a fabricated promotion"
                )
            lost = [m for m in self.metrics if float(self.skill[m] or 0.0) <= 0.0]
            if lost:
                raise ServedContractError(
                    f"a PASS decision reports non-positive skill on {lost}; clearing a "
                    "bar means beating it"
                )

    @property
    def promotable(self) -> bool:
        """True only for PASS. Derived, so no caller can disagree with the status."""
        return self.status is Status.PASS

    @property
    def measured(self) -> bool:
        """False for NA. "Not measured" is the question this answers, not "lost"."""
        return self.status is not Status.NA

    def declared_resampling(self) -> list[dict[str, Any]]:
        """Every resampling declaration this decision actually looked at.

        Read out of the evidence the decision already carries rather than
        stored as a field of its own, so there is no second place to write one
        and no way for the summary to disagree with the comparisons it
        summarises.
        """
        found: list[dict[str, Any]] = []
        for key in ("comparisons", "resampling"):
            for entry in self.evidence.get(key) or ():
                if not isinstance(entry, Mapping):
                    continue
                declaration = entry.get("resampling")
                if isinstance(declaration, Mapping):
                    found.append(dict(declaration))
        return found

    def to_dict(self) -> dict[str, Any]:
        declarations = self.declared_resampling()
        return {
            "status": self.status.value,
            # A PRINTED absence, not a missing key. A promotion that rests on
            # an interval and reports `"resampling": "NA"` has said, in the
            # record a person reads, that nobody declared what was resampled --
            # which is the state round-8 adjudication had to reconstruct by
            # hand from a trainer's source.
            "resampling": declarations or UNMEASURED,
            "promotable": self.promotable,
            "measured": self.measured,
            "recorded_bar": self.recorded_bar,
            "decision_metrics": list(self.metrics),
            "skill_vs_recorded_bar": {
                k: (UNMEASURED if v is None else v) for k, v in self.skill.items()
            },
            "n_rows_compared": self.n_rows,
            "refusal_class": self.refusal_class,
            "reason": self.reason,
            # A DEEP copy. `dict(self.evidence)` is shallow, and the evidence
            # this class carries is a list of comparison dicts one level down:
            # driven adversarially, editing `to_dict()["evidence"]
            # ["comparisons"][0]["skill"]` edited the decision's own record.
            # A verdict hands out what it decided on; it does not hand out the
            # thing it decided on.
            "evidence": _deepcopy(dict(self.evidence)),
        }


def challenger_decision(
    comparisons: Sequence[Comparison],
    *,
    recorded_bar: str,
    metrics: Iterable[str],
    deciding_arm: str | None = None,
    arm_refusal_note: str = "",
) -> ChallengerDecision:
    """Decide a challenger against the recorded bar. Returns; never raises.

    Losing is a measurement, not an error, so this reports rather than raising —
    the shape all four implementations converged on independently.

    Six refusals, in the order the questions have to be answered, and none of
    them is a pass by default:

    1. the bar is **absent** from the comparisons — FAIL. Not being compared is
       not the same as being compared and winning, and it is a fact about the
       candidate's evidence rather than about the measurement apparatus, which
       is why all three serving modules make this FAIL rather than NA.
    2. **no rows** were compared — NA. A comparison over nothing is not a win
       and is not a loss.
    3. the reference did not predict the **same rows** — NA.
    4. the comparison is on an arm other than ``deciding_arm``, when one is
       declared — NA. chokepoint's val-only refusal
       (``daily_flow_forecaster.py:527-570``): a challenger with a val margin
       has not been measured on the terms the champion was promoted on.
    5. the interval was resampled over **different rows** than the figure it
       bounds — NA. Only reachable for a comparison that carries an interval.
    6. the interval's **resampling unit contradicts the holdout policy** the
       same comparison declares — NA. See :class:`ResamplingDeclaration`; this
       is the round-8 finding, and it is NA rather than FAIL because the
       candidate may be perfectly good and the evidence about it is what cannot
       be adjudicated.
    7. any declared metric's skill is **unmeasured** — NA.
    8. any declared metric's skill is measured and **not strictly positive** —
       FAIL.
    9. the skill is strictly positive and **its own interval does not exclude
       zero** — FAIL. Asked last, and only of comparisons carrying an interval,
       so that nothing without one changes verdict and a point-estimate loss
       still reports ``NO_SKILL``.

    Otherwise PASS.

    Lanes 5, 6 and 9 are unreachable for a :class:`Comparison` with no
    interval, which is every comparison this function decided before
    2026-09-01. Adding them moved no existing verdict.
    """
    metrics = tuple(metrics)
    if not metrics:
        raise ServedContractError(
            "a challenger decision needs at least one decision metric; a gate that "
            "decides on nothing passes everything"
        )
    none_skill: dict[str, float | None] = dict.fromkeys(metrics)

    against_bar = [c for c in comparisons if c.reference == recorded_bar]
    if not against_bar:
        return ChallengerDecision(
            status=Status.FAIL,
            reason=(
                f"the candidate was not compared to the recorded bar {recorded_bar!r} "
                f"(references compared: {sorted({c.reference for c in comparisons})}). "
                "An uncompared candidate is not a winning one."
            ),
            recorded_bar=recorded_bar,
            metrics=metrics,
            skill=none_skill,
            refusal_class=NOT_COMPARED,
        )

    by_metric = {c.metric: c for c in against_bar}
    missing = [m for m in metrics if m not in by_metric]
    if missing:
        return ChallengerDecision(
            status=Status.FAIL,
            reason=(
                f"the candidate was not compared to {recorded_bar!r} on {missing}; the "
                "decision metrics were declared and not all of them were scored"
            ),
            recorded_bar=recorded_bar,
            metrics=metrics,
            skill=none_skill,
            refusal_class=NOT_COMPARED,
        )

    # Before asking how much was compared, ask whether the figures can be the
    # metric they are labelled as, and whether anyone said which way that
    # metric runs. Both questions are about the numbers themselves, and until
    # they are settled every later lane is reasoning about arithmetic that may
    # not mean anything. Measured at 8517341, with neither question asked: a
    # MAPE of -0.05 against a bar of 0.20 PROMOTED on skill 1.25, and an r2 of
    # 0.10 against a bar of 0.90 PROMOTED on skill 0.8889.
    impossible = {
        m: by_metric[m].impossible for m in metrics if by_metric[m].impossible
    }
    if impossible:
        detail = "; ".join(
            f"{m} {by_metric[m].domain} but "
            + ", ".join(
                f"{side} {getattr(by_metric[m], side + '_value')!r}"
                for side in sides
            )
            for m, sides in impossible.items()
        )
        return ChallengerDecision(
            status=Status.NA,
            reason=(
                f"the comparison against {recorded_bar!r} carries a figure its own "
                f"declared domain cannot contain: {detail}. A number outside the "
                "metric's domain is not a bad score; it is evidence that whatever "
                "produced it was not computing the metric it labelled, and dividing "
                "two of them yields a skill figure about nothing."
            ),
            recorded_bar=recorded_bar,
            metrics=metrics,
            skill=none_skill,
            n_rows=min(by_metric[m].n_rows for m in metrics),
            refusal_class=IMPOSSIBLE_MEASUREMENT,
        )

    undeclared = [m for m in metrics if not by_metric[m].declared]
    if undeclared:
        return ChallengerDecision(
            status=Status.NA,
            reason=(
                f"the comparison against {recorded_bar!r} declares no polarity on "
                f"{undeclared}, so which of the two values is the better one is "
                f"unstated. Declare {LOWER_IS_BETTER!r} or {HIGHER_IS_BETTER!r} on the "
                "comparison. This gate assumed lower-is-better until 2026-08-31 and "
                "promoted a model that was worse on r2 by eight tenths."
            ),
            recorded_bar=recorded_bar,
            metrics=metrics,
            skill=none_skill,
            n_rows=min(by_metric[m].n_rows for m in metrics),
            refusal_class=POLARITY_UNDECLARED,
        )

    n_rows = min(by_metric[m].n_rows for m in metrics)
    if n_rows <= 0:
        return ChallengerDecision(
            status=Status.NA,
            reason=(
                f"the comparison against {recorded_bar!r} scored no rows; there is "
                "nothing here to pass"
            ),
            recorded_bar=recorded_bar,
            metrics=metrics,
            skill=none_skill,
            n_rows=0,
            refusal_class=NO_ROWS,
        )

    untied = [m for m in metrics if by_metric[m].row_matched is None]
    if untied:
        return ChallengerDecision(
            status=Status.NA,
            reason=(
                f"the comparison against {recorded_bar!r} carries no row-set tie on "
                f"{untied}: one or both sides did not say which rows its figure was "
                "computed over, so whether the two numbers describe the same rows is "
                "unknown. Until 2026-08-31 this contract took the caller's word for "
                "it and defaulted the answer to True, which meant every comparison "
                "that had never thought about row sets asserted the strongest "
                "possible claim about them. Tie both sides with "
                "core.served.row_set_digest."
            ),
            recorded_bar=recorded_bar,
            metrics=metrics,
            skill=none_skill,
            n_rows=n_rows,
            refusal_class=ROW_SET_UNTIED,
        )

    unmatched = [m for m in metrics if by_metric[m].row_matched is False]
    if unmatched:
        return ChallengerDecision(
            status=Status.NA,
            reason=(
                f"the recorded bar {recorded_bar!r} did not predict every row the "
                f"candidate predicted on {unmatched}, so the two figures describe "
                "different row sets. A skill number across two row sets is not a "
                "comparison, and this gate will not turn one into a pass."
            ),
            recorded_bar=recorded_bar,
            metrics=metrics,
            skill=none_skill,
            n_rows=n_rows,
            refusal_class=ROW_SET_MISMATCH,
        )

    if deciding_arm is not None:
        wrong_arm = {by_metric[m].arm for m in metrics if by_metric[m].arm != deciding_arm}
        if wrong_arm:
            return ChallengerDecision(
                status=Status.NA,
                reason=(
                    f"the comparison against {recorded_bar!r} was measured on "
                    f"{sorted(wrong_arm)}, not on the deciding arm {deciding_arm!r}. A "
                    "margin measured elsewhere has not been measured on the terms the "
                    "champion was promoted on."
                    + (f" {arm_refusal_note}" if arm_refusal_note else "")
                ),
                recorded_bar=recorded_bar,
                metrics=metrics,
                skill=none_skill,
                n_rows=n_rows,
                refusal_class=ARM_MISMATCH,
            )

    # -- the dependence unit ------------------------------------------------
    #
    # Both lanes are skipped entirely by a comparison carrying no interval, so
    # every verdict this function gave before 2026-09-01 is unchanged. What
    # they close is the case the round-8 adjudication measured: a promotion
    # conditioned on an interval, where the unit the interval's procedure drew
    # was nobody's declared decision and no instrument compared it to the
    # holdout policy sitting beside it in the same artifact.
    with_interval = [m for m in metrics if by_metric[m].has_interval]

    rows_untied = [
        m
        for m in with_interval
        if by_metric[m].candidate_row_digest
        and by_metric[m].resampling is not None
        and by_metric[m].resampling.row_digest != by_metric[m].candidate_row_digest  # type: ignore[union-attr]
    ]
    if rows_untied:
        detail = "; ".join(
            f"{m}: point over {by_metric[m].candidate_row_digest[:12]}…, interval over "
            f"{by_metric[m].resampling.row_digest[:12]}…"  # type: ignore[union-attr]
            for m in rows_untied
        )
        return ChallengerDecision(
            status=Status.NA,
            reason=(
                f"the interval against {recorded_bar!r} was resampled over a different "
                f"row set than the figure it bounds on {rows_untied} ({detail}). A "
                "bound taken on other rows is not a bound on this number."
            ),
            recorded_bar=recorded_bar,
            metrics=metrics,
            skill=none_skill,
            n_rows=n_rows,
            refusal_class=RESAMPLING_ROWS_UNTIED,
            evidence={"resampling": [by_metric[m].to_dict() for m in rows_untied]},
        )

    contradicting = [
        m
        for m in with_interval
        if by_metric[m].resampling is not None
        and by_metric[m].resampling.contradicts_policy  # type: ignore[union-attr]
    ]
    if contradicting:
        detail = " | ".join(
            f"{m}: {by_metric[m].resampling.refusal} — "  # type: ignore[union-attr]
            f"{by_metric[m].resampling.detail}"  # type: ignore[union-attr]
            for m in contradicting
        )
        return ChallengerDecision(
            status=Status.NA,
            reason=(
                f"the interval against {recorded_bar!r} rests on a resampling unit "
                f"that contradicts the holdout policy this comparison declares, on "
                f"{contradicting}. {detail}"
            ),
            recorded_bar=recorded_bar,
            metrics=metrics,
            skill=none_skill,
            n_rows=n_rows,
            refusal_class=DEPENDENCE_UNIT_CONTRADICTS_POLICY,
            evidence={"resampling": [by_metric[m].to_dict() for m in contradicting]},
        )

    measured: dict[str, float | None] = {m: by_metric[m].skill for m in metrics}
    unmeasured = [m for m in metrics if measured[m] is None]
    if unmeasured:
        reasons = "; ".join(
            by_metric[m].unmeasured_reason or "no reason recorded" for m in unmeasured
        )
        return ChallengerDecision(
            status=Status.NA,
            reason=(
                f"skill against {recorded_bar!r} is unmeasured on {unmeasured}: "
                f"{reasons}. An unmeasured comparison is not a pass, and it is not a "
                "failure either."
            ),
            recorded_bar=recorded_bar,
            metrics=metrics,
            skill=none_skill,
            n_rows=n_rows,
            refusal_class=UNMEASURED_SKILL,
        )

    evidence = {
        "comparisons": [by_metric[m].to_dict() for m in metrics],
        "arm": by_metric[metrics[0]].arm,
    }
    lost = [m for m in metrics if float(measured[m] or 0.0) <= 0.0]
    if lost:
        detail = ", ".join(f"{m} {float(measured[m] or 0.0):+.6f}" for m in lost)
        return ChallengerDecision(
            status=Status.FAIL,
            reason=(
                f"measured skill against {recorded_bar!r} is not strictly positive on "
                f"{detail} over {n_rows} rows; not promotable"
            ),
            recorded_bar=recorded_bar,
            metrics=metrics,
            skill=measured,
            n_rows=n_rows,
            refusal_class=NO_SKILL,
            evidence=evidence,
        )

    # Asked LAST, and only of comparisons that carry one, so that a comparison
    # with no interval reaches PASS by exactly the path it always did and a
    # point-estimate loss still reports NO_SKILL rather than being re-labelled.
    # This is the fray case: point +22.811 clears the floor, and the interval
    # its own holdout policy implies is [-1.289, +41.704].
    covering = [m for m in with_interval if by_metric[m].interval_clears_zero is False]
    if covering:
        detail = ", ".join(
            f"{m} {float(measured[m] or 0.0):+.6f} in "
            f"[{by_metric[m].skill_interval_low!r}, {by_metric[m].skill_interval_high!r}] "
            f"({by_metric[m].resampling.procedure} over "  # type: ignore[union-attr]
            f"{by_metric[m].resampling.n_units_in_arm} "  # type: ignore[union-attr]
            f"{by_metric[m].resampling.unit!r} unit(s))"  # type: ignore[union-attr]
            for m in covering
        )
        return ChallengerDecision(
            status=Status.FAIL,
            reason=(
                f"skill against {recorded_bar!r} is positive and its own interval does "
                f"not exclude zero on {detail} over {n_rows} rows. The point estimate "
                "is the number; the interval is whether the number is distinguishable "
                "from no effect, and promotion rests on the second."
            ),
            recorded_bar=recorded_bar,
            metrics=metrics,
            skill=measured,
            n_rows=n_rows,
            refusal_class=INTERVAL_COVERS_ZERO,
            evidence=evidence,
        )

    detail = ", ".join(f"{m} {float(measured[m] or 0.0):+.6f}" for m in metrics)
    return ChallengerDecision(
        status=Status.PASS,
        reason=(
            f"measured strictly-positive skill against {recorded_bar!r} on {detail} "
            f"over {n_rows} rows"
        ),
        recorded_bar=recorded_bar,
        metrics=metrics,
        skill=measured,
        n_rows=n_rows,
        refusal_class=CLEARS_BAR,
        evidence=evidence,
    )


# ---------------------------------------------------------------------------
# The serve-arm guard
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ServeArms:
    """Which arms a product serves, and why the others are shut.

    The policy is DATA, not a rule baked into this module, because the fleet
    does not agree on which arm is closed and both positions are correct in
    their own repo. triage and fray close ``test`` and refuse it
    (``triage/scripts/serve_weekly_mortality.py:55,66-71``); chokepoint's gate
    *requires* ``test`` and returns NA for val-only evidence
    (``daily_flow_forecaster.py:99``). A contract that hard-coded "test is
    forbidden" would make a correct gate unadoptable.

    What IS baked in is the mechanism: :meth:`require` refuses anything not
    explicitly open. An arm nobody declared is refused for the same reason a
    closed one is — a serve path that accepts an unrecognised arm is a serve
    path whose row set is whatever the caller typed.
    """

    open: frozenset[str]
    closed: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "open", frozenset(self.open))
        object.__setattr__(self, "closed", dict(self.closed))
        if not self.open:
            raise ServedContractError(
                "a serve-arm policy with no open arm serves nothing; declare the arms "
                "this product serves rather than leaving the set empty"
            )
        both = sorted(self.open & set(self.closed))
        if both:
            raise ServedContractError(
                f"arm(s) {both} are declared both open and closed; a serve path cannot "
                "hold two policies about the same rows"
            )
        unexplained = sorted(a for a, why in self.closed.items() if not str(why).strip())
        if unexplained:
            raise ServedContractError(
                f"closed arm(s) {unexplained} carry no reason. A closure nobody can "
                "read is a closure the next person will lift."
            )

    def is_open(self, arm: str) -> bool:
        return arm in self.open

    def require(self, arm: str) -> str:
        """Return ``arm`` if it is open; raise :class:`ClosedArm` otherwise."""
        if arm in self.open:
            return arm
        if arm in self.closed:
            raise ClosedArm(
                f"refusing to serve the {arm!r} arm: {self.closed[arm]} "
                f"(open arms: {sorted(self.open)})"
            )
        raise ClosedArm(
            f"refusing to serve the {arm!r} arm: it is not declared by this product "
            f"(open arms: {sorted(self.open)}; closed arms: {sorted(self.closed)}). An "
            "undeclared arm is not a licence to guess which rows were meant."
        )

    def to_dict(self) -> dict[str, Any]:
        return {"open": sorted(self.open), "closed": dict(self.closed)}
