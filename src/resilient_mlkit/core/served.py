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
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .result import Status

__all__ = [
    "DOMAINS",
    "HASH_KEY",
    "HIGHER_IS_BETTER",
    "IMPOSSIBLE_MEASUREMENT",
    "LOWER_IS_BETTER",
    "NONNEGATIVE",
    "POLARITIES",
    "POLARITY_UNDECLARED",
    "REAL",
    "UNMEASURED",
    "ArtifactIntegrityError",
    "ChallengerDecision",
    "ClosedArm",
    "Comparison",
    "DataSource",
    "Measurement",
    "ProvenanceMismatch",
    "RecordedBar",
    "ServeArms",
    "ServedContractError",
    "ServedModel",
    "canonical_payload_sha256",
    "challenger_decision",
    "out_of_domain",
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
    """

    reference: str
    metric: str
    candidate_value: float | None
    reference_value: float | None
    n_rows: int
    arm: str = ""
    row_matched: bool = True
    unmeasured_reason: str = ""
    #: Which direction this metric runs in, and what values it can take. Both
    #: are DATA the caller declares, in the same shape :class:`ServeArms` makes
    #: the arm policy data, and for the same reason: the fleet does not agree
    #: on one answer and both answers are correct in their own repo. A
    #: comparison that declares no polarity is not decided against a guess.
    polarity: str = ""
    domain: str = REAL

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
            "row_matched": self.row_matched,
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

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
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
            "evidence": dict(self.evidence),
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
    5. any declared metric's skill is **unmeasured** — NA.
    6. any declared metric's skill is measured and **not strictly positive** —
       FAIL.

    Otherwise PASS.
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

    unmatched = [m for m in metrics if not by_metric[m].row_matched]
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
