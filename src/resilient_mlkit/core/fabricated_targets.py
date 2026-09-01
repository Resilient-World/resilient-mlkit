"""Static detection of fabricated targets wearing an observed provenance stamp (R11).

The defect class this module exists to catch, stated once:

    A value is drawn from a random number generator, flows into the numbers
    written onto a data record, and that record is then stamped with a
    provenance field claiming the numbers were OBSERVED.

That final stamp is the whole defect. Drawing from an RNG and labelling the
result ``synthetic`` is a fixture, which is a legitimate and necessary thing to
build. Drawing from an RNG and labelling the result ``observed_ccc`` is a
fabrication, and it is a compounding one: R5 counts rows BY the provenance
field, so a mislabelled row is counted as real and the split it lands in
reports zero synthetic rows while being made of noise.

WHY R10 COULD NOT SEE THIS
--------------------------
resilient-choco PR #160 shipped five files under ``scripts/`` of the shape
(reduced to its smallest reproducing form; the full shape is pinned as the
first positive control in ``tests/test_fabricated_targets.py``)::

    feat   = rng.normal(loc=level, scale=0.08, size=len(feature_names))
    tonnes = 4500.0 * (i + 1) * (1.0 + 0.03 * (y - 2019)) \\
             + feat[1] * 1.5 - feat[0] * 20.0
    rows.append({
        "tonnes": tonnes,
        "source_id": "civ_ccc_regional",
        "label_origin": "observed_ccc",
        "feature_origin": "era5_monthly_reduction",
        "licence_class": "trainable",
    })

Fifty-one guard tests stayed green because that repo's generated-paths guard
polices ``src/`` and ``dvc.yaml`` only. R10 could not see it either, for two
independent reasons, and both are the reason this is a separate check rather
than a widened R10:

1. **R10 walks the trees a repo DECLARES** in ``[source] trees``. This walks
   every Python file in the repo, wherever it lives -- ``scripts/``,
   ``benchmarks/``, ``notebooks/``, a one-off at the root. The declared-tree
   list is exactly the surface an author controls, so a check that trusts it
   cannot catch a defect that hides outside it.

2. **R10's synthetic-context excusal would have suppressed it.** R10 stays
   quiet inside a function or file whose NAME declares it a generator --
   ``make_``, ``simulate``, ``fixture`` -- because an RNG draw there is doing
   what it says. R11 deliberately does NOT honour that excusal, and this is
   the single most important design decision in the module: the provenance
   stamp is an assertion about the data, and a file called
   ``make_regional_panel.py`` that stamps its rows ``label_origin=
   "observed_ccc"`` is not excused by its own filename -- it is contradicted
   by it. Where R10 reads the name as a declaration of intent, R11 reads the
   stamp as a declaration of fact, and only the stamp travels with the data.

WHAT SEPARATES A FABRICATION FROM AN HONEST SIMULATION
------------------------------------------------------
Not the *sound* of the provenance string. That was the first answer this module
gave, and naming defeated it twice.

**The first defeat: an opaque product name.** ``ERA5LandBaselineLoader.iter_grid``
in resilient-arabica draws every one of ``t2m, tmax, tmin, precip, rh, vpd,
srad, wind`` from ``self.rng`` and stamps the record ``source="era5_land"``.
``era5_land`` tokenises to ``{era5, land, era5land}``, which met neither claim
vocabulary, so the value classified OPAQUE and OPAQUE never triggered. A fully
synthetic loader therefore read as real and R11 returned zero findings on it --
recorded as an honest negative in that repo's E-051 and left standing, because
the check as written had nothing to say. The same escape was open to any
synthetic loader willing to name itself after a real product, and three of them
were sitting in resilient-surge (``source="ntslf"``, ``"bom"``, ``"jcomm"``,
each a real tide-gauge network, each returning ``np.random.normal(...)``).

**The second defeat: stamp both.** A record carrying a simulation declaration
in ANY provenance field used to be exempt, even when another field claimed
observation, and this module said so in its own docstring: "the cost is a
narrow evasion (stamp both) and it is stated here rather than hidden". Stating
an evasion does not close it. arabica pre-registered
``synthetic_weather_real_isd_fallback`` as a repair label and its own control
rejected it: the string satisfies R11 while still asserting observation to
every human who reads it, and R5 counts by ONE field, so a second field saying
``synthetic`` does not make the first one true.

Both defeats share a shape with R12's (satisfied by an import instead of a
call): the check read a LABEL instead of the thing the label describes, so the
cheapest evasion was to name the fake after something real. The repair is not
another token in a list -- the next loader will be called something else -- but
a second question the AST can already answer.

THE QUESTION THAT REPLACED IT
-----------------------------
Did the VALUES come from an RNG, and is the label beside them contradicted by
the construction that produced them?

A stamp is false in one of three ways, and all three are findings:

* ``OBSERVED_STAMP`` -- the value claims observation outright
  (``label_origin="observed_ccc"``, ``kind="real"``).
* ``CONTRADICTED_STAMP`` -- one value, or one record, both claims observation
  and declares simulation. No longer an exemption.
* ``CONTRADICTED_SOURCE`` -- the stamp NAMES an external source
  (``source="era5_land"``) and every value on the record was manufactured
  inside this process: RNG draws, literals, literal-defaulted knobs, and
  arithmetic or pure numeric calls over those. Nothing on that record came
  from the named source, because nothing on it came from anywhere.

``CONTRADICTED_SOURCE`` still does not adjudicate the string. It never decides
whether ``era5_land`` names a real registry -- that is a judgement about the
world and a gate must not make it. It reads the code instead. The moment ONE
value on the record could have come from outside -- a file read, a request, a
dataframe passed in, a parameter with no default, a call this module does not
recognise -- the rule goes silent, because then the label may well describe
where that value came from. Unrecognised is always the quiet direction: an
unknown call can never be the thing that creates a finding.

A record's identifiers are exempt from that test and its measurements are not.
``fetch_ntslf(station_id)`` passes the caller's station id straight through and
manufactures the water levels; the stamp is a claim about the water levels.

The simulation vocabulary is read from PROVENANCE FIELDS ONLY. A comment, a
docstring or an unrelated ``"note": "synthetic demo"`` does not excuse a
record, because none of those travel into a manifest.

THE PARTS, ALL REQUIRED
-----------------------
1. **An RNG draw.** Detected with ``fabrication._is_random_draw``, the same
   vocabulary R10 uses -- one definition of "this number came from noise".
2. **Flow from that draw into a written field.** A flow-insensitive taint
   fixpoint over each function scope, with one level of inter-procedural
   propagation through module-local helpers whose return value is tainted.
   Flow-INsensitive on purpose: an AST rule that depended on statement order
   would be defeated by moving a line, and the brief for this check is that it
   survive reformatting.
3. **A provenance stamp the record's own construction contradicts**, in one of
   the three ways above.

Miss any one and the module is silent. An RNG draw with no stamp is a fixture.
A stamp with no draw is a data record. A stamp on a record whose only tainted
field is a config knob (``seed``, ``batch_size``) is a run note; the
configuration vocabulary R10 already maintains vetoes those. And a record that
declares itself ``synthetic`` and claims nothing is a fixture, which is the
one thing this check must never report.

THE TWO PASSES, AND WHY THEY LEAN OPPOSITE WAYS
-----------------------------------------------
``taint_of`` over-approximates: a name reassigned from a clean source after
being tainted stays tainted. That is safe because taint alone never produces a
finding -- a stamp is always also required.

``manufactured_of`` under-approximates: anything it cannot PROVE was built
inside the process is left out. That is necessary because it is the conjunct
that turns an opaque source label into a finding, and an over-approximation
there would fire on real loaders. The two passes must lean opposite ways, and
a change that makes ``manufactured_of`` more generous is a change that can
invent findings.

WHAT THIS MODULE DOES NOT CLAIM TO CATCH, so that a green R11 is not read as
more than it is: a target read from a file that was itself generated in an
earlier process (the draw is not in this repo's AST); a target derived from
another column by closed-form arithmetic with no RNG anywhere (that is R5's
formula-derivation probe, which measures the data rather than the code); and
taint carried through a class attribute or a global mutated across functions.
The first two are covered elsewhere in the instrument. The third is a gap,
stated rather than papered over.

``CONTRADICTED_SOURCE`` adds one more, and it is the price of leaning
conservative: a record that mixes ONE externally-sourced value in among
manufactured ones is not adjudicated, even when the external value is a
formality. ``iter_daily`` in the same arabica module reads its farms off
``self._synthetic_farms``, so the class-attribute gap above swallows it too.
Both are under-reports, and an under-report from this rule is a record a
reader still has to open. What it must never do is fire on a loader that reads
real data, and every conjunct above is chosen to keep it off that.

AND ONE MORE, WHICH IS THE SAME DEFEAT ONE LEVEL UP (VERIFY-R11, E-M17)
-----------------------------------------------------------------------
``CONTRADICTED_SOURCE`` no longer adjudicates the provenance VALUE. For a
while it still adjudicated the provenance FIELD NAME: a stamp only became a
source claim when its field was in :data:`SOURCE_NAMING_FIELDS`. So the same
wholly manufactured ERA5 loader, with ``source=`` renamed to
``data_product=``, ``feed=``, ``provider=``, ``network=``, ``archive=``,
``product=`` or twenty other plausible names, went silent again. Measured: 24
of 24 invented field names evaded, against the same construction the module's
own positive control fires on. R5 did not close it either -- R5 counts by
whatever field a repo's own ``provenance()`` adapter reads, so a repo is free
to key its manifest on a name this list does not hold.

Extending the list was refused, and the refusal still stands: the next stamp
will be called something else, which is the identical argument this module
makes against a deny-list of product names. Inverting the direction (treat
every opaque string field on a wholly manufactured record as a source claim)
was measured across all fourteen repos: 4 findings becomes 29, including
``freq="h"``, ``currency="USD"``, ``country_code="GLO"``,
``generator_version="1.0.0"`` and prose ``note=`` fields matched on the word
"observed" inside a sentence declaring the data synthetic. The inversion could
not ship as measured.

WHAT IS CLOSED (T8-4)
~~~~~~~~~~~~~~~~~~~~~
The adjudication moved to the VALUE and off the field name entirely, gated on
two things this module did not invent. On a record ``manufactured_of`` already
proves WHOLLY manufactured -- the precondition is unchanged and is what keeps
the conservative lean -- ANY string-valued field is read as a source claim
when its value

(a) claims observation on the vocabulary that already shipped
    (:data:`OBSERVED_CLAIM_TOKENS`), now applied wherever the string is
    written rather than only under a listed field name; or

(b) reproduces at least :data:`REGISTRY_MATCH_MIN_PARTS` parts of a product
    name in the repo's own signed ``docs/allowlist.yaml``. The allowlist is
    the human signatory's record of which sources are real. READING it is
    permitted; extending it is reserved (CLAUDE.md rule 14) and this module
    never proposes an entry.

Branch (b) is what makes ``era5_land`` a finding under ANY field name:
ERA5-Land is allowlisted where it is used, so a value naming it on a record
proven drawn from ``rng`` is contradicted by the portfolio's own source of
truth rather than by a list this module made up. The control that pins it
renames the stamp through all 24 measured names PLUS a name generated at test
time, so the check cannot be satisfied by adding names to any frozenset.

The VALUE is read however it is spelled, because the brief for this check is
that it survive reformatting. ``era5_land``, ``era5land``, ``ERA5-Land``,
``ERA5``, ``f"era5_land"``, ``"era5" + "_land"``, ``["era5_land"]``, a module
constant and a class attribute all reach the same adjudication; every one of
those was a live evasion of the first cut of this repair and each is now a
control with its honest twin beside it. Folding, never evaluation: an
f-string whose placeholder cannot be resolved makes the value unreadable and
the check silent.

E-M17 RESIDUAL 4 IS CLOSED (M-04, 2026-08-31)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Four more spellings of that same value were measured SILENT at 8517341 while
the plain literal fired: ``"_".join(["era5", "land"])``, ``"era5_%s" %
"land"``, ``"era5_{}".format("land")``, and a module-level ``FEEDS =
{"primary": "era5_land"}`` read back as ``FEEDS["primary"]``. All four now
fold and reach the same adjudication, reported under the FOLDED value so a
reader sees the claim rather than the spelling.

The read-back is the ``SOURCE = "era5_land"`` hoist this module already
closed, written with a subscript instead of a name; the same module dict was
already resolved one level deep for ``**FEEDS`` spreads, so reading it through
a spread and not through a subscript was reading the layout.

The folds stay total functions of already-resolved STRINGS. ``"%d" % 5`` does
not fold, because a numeric conversion is not something this module should be
the place to invent; ``"_".join(parts)`` over an unresolved name does not
fold; a dict that is not a module-level binding is not resolved at all. The
module-dict hop is the ONE fold that follows a name across the tree rather
than down it, so it carries a cycle guard -- ``A = {"x": A["x"]}`` is legal
Python, and a scanner that raises reports nothing at all.

AND THE RESIDUE GETS A THIRD VERDICT: ``UNREADABLE_STAMP``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
What is left once every CONSTANT spelling folds is an expression that is
genuinely dynamic: ``source=f"era5_{region}"``, ``source=FEEDS[which]``.
Staying silent there reports the record as CLEAN. It is not clean. It is
unadjudicated, and the honest verdict for something not measured is NA.

So a record gets an ``UNREADABLE_STAMP`` finding -- severity and rule both,
because there is no fabrication to grade -- and R11 returns **NA rather than
PASS**, when ALL of the following hold. Each conjunct has a silent control
beside it in ``tests/test_fabricated_targets.py``:

* ``_wholly_manufactured`` proves the record (the unchanged
  ``CONTRADICTED_SOURCE`` precondition -- a record arriving as a parameter,
  or carrying one value read off a file, is not adjudicated);
* the field the RNG reached is a TARGET field. An input-only manufactured row
  stays in the ordinary conservative under-report; widening the NA to it would
  turn any unresolvable f-string into a fleet-wide verdict change;
* the unresolved field is in :data:`SOURCE_NAMING_FIELDS`, not merely in
  :data:`PROVENANCE_FIELDS`. This is the one place the module leans on a
  field-NAME list again after moving the source rule off one, and it can only
  do so because the verdict is NA. A computed ``split``, licence class or
  ``kind`` names a partition, a permission or a shape, not an unread origin;
* and the record carries NO readable string at all -- so a resolvable
  ``"provenance": "synthetic"`` beside the dynamic value still ends the
  adjudication in the honesty rule, exactly as before.

The finding QUOTES the expression. "Unreadable" without saying what could not
be read is not something a reader can act on.

Over-fire budget, MEASURED read-only before either stage shipped (2026-08-31,
dual interpreter, each side asserting its own ``resilient_mlkit.__file__``):
ten checkouts at their remote mains, 3394 Python files per side, R11 findings
0 -> 0, NEW 0, GONE 0, with the NA lane enabled. Harness controls -- same rev
on both sides, and a planted-fabricator positive on a copy of a real repo
tree -- in ``reports/M04_FLEET_SWEEP.md``.

The honesty rule is UNCHANGED and still runs first: a simulation token in any
provenance field of the record ends the adjudication before either source rule
is reached. That is what keeps torrent's ``v4_orchestrator`` note ("these
annual maxima were DRAWN, not observed") silent, and the value-side branch
additionally skips any value that declares itself.

WHAT MEASURABLY REMAINS (still E-M17, not closed)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
* **A product in NO allowlist.** ``resilient-chokepoint``'s
  ``climate_model_runners.py`` returns throughput deltas built from four
  literals plus ``rng.normal`` under ``scenario_name="SSP1-2.6 vs SSP5-8.5
  (CMIP6-driven)"``, and no chokepoint allowlist entry mentions CMIP6
  (measured 2026-08-29: ``grep -c cmip6 docs/allowlist.yaml`` -> 0). Branch
  (b) has nothing to match, and branch (a) does not fire because the value
  claims no observation. This record is STILL invisible to R11. It is the
  pre-escalation shape and it is reported in ``docs/ESCALATIONS.md`` E-M17
  rather than repaired here, because repairing it is chokepoint's change.
* **A source claim written with spaces.** The observed-token branch requires a
  LABEL, not a sentence (:func:`is_label_value`), because without that guard
  it fired on three honest NA disclaimers in the fleet -- exactly the prose
  class that sank the inversion. ``data_product="NOAA CO-OPS"`` therefore
  reaches branch (b) only. Stated, not hidden.
* **A one-part product name made only of letters.** ``product="chirps"``
  reproduces one part of ``chirps-daily-precip`` and scores 1, below the
  threshold. Two parts is what separates a compound of a registered name from
  a word two pieces of code happen to share -- ``coffee`` is a part of five of
  arabica's forty entries, ``daily`` of three. A one-part match IS enough when
  the part is a designator (letters and digits, four characters or more:
  ``era5``, ``sentinel2``, ``vjepa2``), because that shape is a product
  identity and almost never an English word. ``chirps``, ``aurora``,
  ``soilgrids`` and ``prithvi`` are the residue.
* **A stamp applied outside the record's own scope.** ``_stamp(row)`` takes
  the record as a parameter with no default, which is how data arrives, so
  ``manufactured_of`` cannot prove the record was built in-process. Pinned as
  a residual control.
* Everything under WHAT THIS MODULE DOES NOT CLAIM TO CATCH above still
  stands, unchanged.

Both residual shapes are pinned as tests that assert the CURRENT, WRONG
silence, so the day one of them closes the suite goes red and the escalation
gets updated instead of the silence being re-pinned.
"""

from __future__ import annotations

import ast
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from itertools import pairwise
from pathlib import Path

from . import fabrication, policy
from .fabrication import HARD_CONFIG_TOKENS, tokenise, tokenise_parts

# ---------------------------------------------------------------------------
# Vocabulary
# ---------------------------------------------------------------------------

#: Field names that assert WHERE a value came from. A string value under one
#: of these is a provenance stamp, and is the only thing this module will
#: accept as a claim of observation.
#:
#: ``kind`` is in here because R5's own provenance contract is keyed by it --
#: ``{"train": {"real": n, "synthetic": n}}`` -- so ``"kind": "real"`` is a
#: provenance claim in this portfolio's own vocabulary. It is safe to include
#: precisely because the VALUE must also claim observation: ``"kind":
#: "polygon"`` says nothing and is ignored.
ORIGIN_FIELDS: frozenset[str] = frozenset(
    {
        "source_id", "source", "sources", "source_name", "origin", "origins",
        "label_origin", "target_origin", "feature_origin", "data_origin",
        "row_origin", "record_origin", "value_origin", "y_origin",
        "provenance", "lineage", "evidence_mode", "evidence",
        "label_source", "target_source", "data_source", "feature_source",
        "observation_source", "measurement_source",
        "dataset", "dataset_id", "collection", "catalogue", "catalog",
        "kind", "label_kind", "row_kind", "data_kind", "target_kind",
        "label_type", "row_type", "data_type", "record_type",
        "acquisition", "acquisition_mode", "method", "measurement_method",
    }
)

#: The subset of :data:`ORIGIN_FIELDS` whose NAME asserts where the values
#: came from, as opposed to what shape or procedure produced them. Only these
#: can carry a source label that the construction beneath them contradicts.
#:
#: ``kind``, ``*_type``, ``*_kind``, ``method`` and ``measurement_method`` are
#: deliberately NOT here. They are kept in ``ORIGIN_FIELDS`` because a VALUE
#: under them can still claim observation (``"kind": "real"`` is the pinned
#: positive control), but ``"kind": "polygon"`` names a shape rather than a
#: registry, and a rule that read every opaque ``kind`` as a source claim
#: would fire on geometry code.
SOURCE_NAMING_FIELDS: frozenset[str] = frozenset(
    {
        "source_id", "source", "sources", "source_name", "origin", "origins",
        "label_origin", "target_origin", "feature_origin", "data_origin",
        "row_origin", "record_origin", "value_origin", "y_origin",
        "provenance", "lineage", "evidence_mode", "evidence",
        "label_source", "target_source", "data_source", "feature_source",
        "observation_source", "measurement_source",
        "dataset", "dataset_id", "collection", "catalogue", "catalog",
        "acquisition", "acquisition_mode",
    }
)

#: Licence and trainability fields. A record asserting it may be trained on is
#: corroborating context -- it says what the rows will be USED for -- but it is
#: never on its own the claim that makes a fabrication, because "trainable" is
#: a statement about permission, not about origin.
LICENCE_FIELDS: frozenset[str] = frozenset(
    {
        "licence_class", "license_class", "licence", "license",
        "licence_id", "license_id", "usage_class", "usage", "rights",
        "trainable", "train_eligible", "eval_only",
    }
)

#: Split fields. A fabricated row landing in val or test is the aggravated
#: form -- R5's absolute invariant -- so it is captured as evidence.
SPLIT_FIELDS: frozenset[str] = frozenset({"split", "fold", "partition", "subset", "stage"})

#: Every field this module treats as metadata rather than as data.
PROVENANCE_FIELDS: frozenset[str] = ORIGIN_FIELDS | LICENCE_FIELDS | SPLIT_FIELDS

#: Tokens in a provenance VALUE that claim the row was observed in the world.
#: Matched against ``fabrication.tokenise`` of the value, so ``observed_ccc``,
#: ``observedCCC`` and ``observed-ccc`` all reach the same entry and neither
#: reformatting nor a naming-convention change can slip past.
OBSERVED_CLAIM_TOKENS: frozenset[str] = frozenset(
    {
        "observed", "observation", "observations", "observational",
        "real", "actual", "actuals", "measured", "measurement",
        "groundtruth", "insitu", "gauge", "gauged", "station", "stations",
        "survey", "surveyed", "census", "reported", "official", "published",
        "recorded", "empirical", "authoritative", "primary", "field",
        "telemetry", "sensor", "instrument", "logged",
    }
)

#: Tokens in a provenance VALUE that DECLARE the row was made up. Their
#: presence in any provenance field of a record makes the record honest and
#: this module silent about it.
SIMULATED_CLAIM_TOKENS: frozenset[str] = frozenset(
    {
        "synthetic", "synthesised", "synthesized", "simulated", "simulation",
        "simulate", "sim", "fixture", "fixtures", "mock", "mocked", "fake",
        "dummy", "toy", "demo", "example", "placeholder", "stub",
        "generated", "generator", "bootstrap", "bootstrapped", "resampled",
        "augmented", "augmentation", "pseudo", "random", "rng", "noise",
        "drawn", "sampled", "test", "scratch", "imputed", "surrogate",
    }
)

#: Tokens naming the field a model is trained to predict. A tainted value
#: landing here is the aggravated form: the target itself is noise, and the
#: model that fits it is fitting its own inputs.
TARGET_TOKENS: frozenset[str] = frozenset(
    {
        "target", "targets", "label", "labels", "y", "ytrue", "yobs",
        "outcome", "outcomes", "response", "responses", "groundtruth",
        "truth", "observed", "actual", "actuals", "yield", "yields",
        "tonnes", "tons", "tonnage", "production", "output", "volume",
        "throughput", "demand", "load", "price", "prices", "damage",
        "damages", "casualties", "outage", "outages", "failures",
        "downtime", "delay", "delays", "claims", "severity", "frequency",
    }
)

#: Tokens naming a field that KEYS or LOCATES a record rather than measuring
#: anything: a station id, a filename, a URL. A source stamp is a claim about
#: where the MEASUREMENTS came from, so an identifier arriving from outside
#: does not make the measurements observed.
#:
#: This exists because ``fetch_ntslf(station_id)`` in resilient-surge returns
#: ``water_level_m=np.random.normal(3.0, 0.3, 24)`` stamped ``source="ntslf"``
#: and passes the caller's ``station_id`` straight through. Requiring EVERY
#: field to be manufactured let the identifier alone excuse the record, which
#: is the naming defeat one level down.
#:
#: Kept deliberately narrow. ``year``, ``lat`` and ``lon`` are NOT here: they
#: can be the axis a real measurement was taken along, and a record built from
#: a caller's years is not one this rule adjudicates.
IDENTIFIER_TOKENS: frozenset[str] = frozenset(
    {
        "id", "ids", "identifier", "identifiers", "uid", "uuid", "guid",
        "key", "keys", "slug", "code", "codes", "name", "names", "title",
        "path", "paths", "file", "filename", "filepath", "url", "uri",
        "href", "index", "idx", "pk",
    }
)



#: Minimum number of an allowlist entry's own name-parts a value must
#: reproduce before it counts as naming that product. TWO, not one, and the
#: threshold is the whole difference between this rule and the inversion that
#: could not ship.
#:
#: Every allowlist in the portfolio is a list of hyphenated compounds --
#: ``gee-era5-land-daily``, ``noaa-coops-water-levels``,
#: ``usda-nass-quickstats`` -- and the parts of those compounds include
#: ordinary descriptive words: ``coffee`` appears in five of arabica's forty
#: entries, ``daily`` in three, ``global`` in one. A one-token rule makes
#: ``crop="coffee"`` and ``freq="daily"`` on any manufactured record into
#: source claims, which is exactly the ``currency="USD"`` class of noise that
#: sank the naive inversion. Requiring two parts means the value has to
#: reproduce a COMPOUND of the registered name, and a compound is not a word
#: two pieces of code happen to share.
#:
#: An adjacent-pair join counts as both of its parts, so ``era5land`` scores
#: the same 2 as ``era5_land``: the joined spelling is not an evasion.
REGISTRY_MATCH_MIN_PARTS = 2

#: A token carries no naming evidence unless it has letters and some length.
#: ``h``, ``sr`` and ``1`` are not product names, and ``1.0.0`` tokenises to
#: digits whose adjacent join ``10`` collides with the ``-1-0`` in
#: ``ecmwf-aifs-single-1-0``. That collision is not hypothetical: it is the
#: pinned ``generator_version="1.0.0"`` negative control, and without this
#: filter the registry branch fires on it.
REGISTRY_TOKEN_MIN_LENGTH = 3


#: Shortest token that can name a product on its own. A DESIGNATOR is a token
#: that mixes letters and digits -- ``era5``, ``cmip6``, ``sentinel2``,
#: ``glo30``, ``vjepa2``. That shape is how the earth-observation world writes
#: a product identity and it is essentially never how English writes an
#: ordinary word, which is why one designator is evidence where one word
#: (``coffee``, ``daily``, ``global``) is not. This is a property of the
#: string, measured, not a list of tokens this module chose.
#:
#: The length floor is what keeps ``co2`` (a part of
#: ``noaa-gml-co2-monthly-global``), ``l30``, ``s30`` and ``v1`` out: three
#: characters is a units string or a version as often as it is a product, and
#: matching ``species="CO2"`` would be the ``currency="USD"`` class of noise
#: all over again.
REGISTRY_DESIGNATOR_MIN_LENGTH = 4


def _is_naming_token(token: str) -> bool:
    """True when a token can carry the identity of a product."""
    return len(token) >= REGISTRY_TOKEN_MIN_LENGTH and any(c.isalpha() for c in token)


def _is_designator_token(token: str) -> bool:
    """True when a token names a product ON ITS OWN.

    Without this, ``data_product="ERA5"`` on a record of pure noise scored one
    part against ``gee-era5-land-daily`` and went silent -- found by attacking
    the T8-4 repair with the shortest spelling of the same claim.
    """
    return (
        len(token) >= REGISTRY_DESIGNATOR_MIN_LENGTH
        and any(c.isalpha() for c in token)
        and any(c.isdigit() for c in token)
    )


def is_label_value(value: str) -> bool:
    """True when a string is a LABEL rather than a sentence about the data.

    R5 counts rows by the provenance value as a CATEGORY -- ``{"train":
    {"real": n, "synthetic": n}}`` -- and a category key has no spaces in it.
    ``observed_ccc``, ``era5_land``, ``real``, ``noaa_coops_synthetic``: all
    labels. ``"No observational asset-level labels exist to score against"``
    is a disclaimer a human wrote for a human, it enters no manifest, and
    nothing counts rows by it.

    This is the guard on the observed-token branch, and it is the difference
    between that branch shipping and not. MEASURED across the fleet without
    it: three findings, all false, all on prose --
    ``empirical_coverage_unmeasured_reason="... empirical coverage is
    unmeasured"`` and ``interpretation="... No observational asset-level
    labels exist ..."`` in resilient-blackout, both of which are the honest
    NA disclaimer this instrument asks people to write. Firing on an honest
    disclaimer teaches authors to delete the disclaimer, which is the exact
    opposite of what R11 is for.

    The cost is stated rather than hidden: a source claim written WITH a space
    (``"NOAA CO-OPS"``) is not read by the observed-token branch. The registry
    branch does not use this guard and is unaffected, because reproducing two
    parts of a registered product name is evidence whatever the spacing.
    """
    return bool(value.strip()) and not any(c.isspace() for c in value)


@dataclass(frozen=True)
class RegistryHit:
    """A value that reproduces the name of a registered real source."""

    #: The allowlist entry id, verbatim, so a reader can look it up.
    entry: str
    #: ALLOWED / BLOCKED / EVAL-ONLY, as the signatory recorded it.
    status: str
    #: The parts of the entry's own name the value reproduced.
    parts: tuple[str, ...]

    def render(self) -> str:
        return f"allowlist:{self.entry} [{self.status}] via {'+'.join(self.parts)}"


@dataclass(frozen=True)
class SourceRegistry:
    """The real sources this repo's human signatory has recorded.

    Read from ``docs/allowlist.yaml`` -- READ, never written: extending it is
    reserved to the signatory (CLAUDE.md rule 14), and this module has no
    business proposing an entry. What it takes from the file is the one thing
    a static check cannot invent: which strings name a real external product
    IN THIS REPO'S OWN JUDGEMENT. That is why a match here is a measurement
    against the portfolio's source of truth rather than against a token list
    this module made up, and it is the whole answer to "the next stamp will be
    called something else".

    ``present=False`` is not the same as an empty registry and is carried
    separately so a caller can REPORT it. A registry that silently is not
    there would turn this branch off with no signal, which is the failure mode
    this module keeps finding in other people's checks.
    """

    path: str = ""
    present: bool = False
    parse_error: str = ""
    #: (entry id, status, base name-parts) for every entry, in file order.
    entries: tuple[tuple[str, str, tuple[str, ...]], ...] = ()

    def match(self, value: str) -> RegistryHit | None:
        """The registered product this value names, if any.

        Scored against the entry's OWN name-parts: a part counts when the
        value's token bag contains it, and an adjacent pair of parts both
        count when the bag contains their join. ``REGISTRY_MATCH_MIN_PARTS``
        parts must land before the value is read as naming the product.
        """
        if not self.entries:
            return None
        bag = set(tokenise(value))
        if not bag:
            return None
        best: RegistryHit | None = None
        for entry_id, status, parts in self.entries:
            hit: set[str] = set()
            score = 0
            for part in parts:
                if _is_naming_token(part) and part in bag:
                    hit.add(part)
            for left, right in pairwise(parts):
                joined = left + right
                if _is_naming_token(joined) and joined in bag:
                    hit.add(left)
                    hit.add(right)
            # A designator carries a product identity by itself; an ordinary
            # word does not. Everything else counts one.
            for part in hit:
                score += 2 if _is_designator_token(part) else 1
            if score < REGISTRY_MATCH_MIN_PARTS:
                continue
            ordered = tuple(p for p in parts if p in hit)
            if best is None or len(ordered) > len(best.parts):
                best = RegistryHit(entry_id, status or "UNSPECIFIED", ordered)
        return best


#: An empty registry. Every entry point defaults to this, so a caller that
#: supplies nothing gets branch (a) only and never a crash.
NO_REGISTRY = SourceRegistry()


def load_source_registry(root: Path) -> SourceRegistry:
    """Read a repo's signed allowlist as a registry of real product names.

    Parsed by :func:`policy.read`, which is the portfolio's one allowlist
    parser. A missing or malformed file yields a registry that says so rather
    than one that quietly holds nothing.
    """
    path = root / policy.ALLOWLIST_RELPATH
    allowlist = policy.read(path)
    entries = tuple(
        (entry.id, entry.status, tuple(tokenise_parts(entry.id)))
        for entry in allowlist.entries.values()
    )
    return SourceRegistry(
        path=str(policy.ALLOWLIST_RELPATH),
        present=allowlist.exists,
        parse_error=allowlist.parse_error,
        entries=entries,
    )


#: Severity of a finding, ranked. Both are defects; only the first puts noise
#: where a model's target is supposed to be.
TARGET_FABRICATED = "TARGET_FABRICATED"
INPUT_FABRICATED = "INPUT_FABRICATED"

#: WHICH of the three rules produced a finding. Severity says where the noise
#: landed (target or input); the rule says what made it a fabrication. They are
#: independent and a reader needs both.
#:
#: ``OBSERVED_STAMP``      a provenance value claims observation.
#: ``CONTRADICTED_STAMP``  one value, or one record, both claims observation
#:                         and declares simulation.
#: ``CONTRADICTED_SOURCE`` a source label naming an external dataset sits on a
#:                         record whose every value was manufactured in this
#:                         process.
#: ``UNREADABLE_STAMP``    (M-04 Stage 2, MEASUREMENT BUILD) the record is
#:                         wholly manufactured with a drawn TARGET, and the
#:                         only provenance value it carries is an expression
#:                         this module cannot resolve. Not a fabrication and
#:                         not a clean record: an unadjudicated one.
OBSERVED_STAMP = "OBSERVED_STAMP"
CONTRADICTED_STAMP = "CONTRADICTED_STAMP"
CONTRADICTED_SOURCE = "CONTRADICTED_SOURCE"
UNREADABLE_STAMP = "UNREADABLE_STAMP"

#: Callables that carry no information from outside this process: they compute
#: over what they are given. Used by :meth:`_ModuleScanner.manufactured_of` to
#: decide whether a record's values could have come from anywhere but the
#: program itself. Anything NOT in this set -- ``read_csv``, ``open``,
#: ``open_dataset``, ``get``, ``execute``, an unknown helper -- makes a value
#: potentially external, which is the safe direction: it makes the check
#: SILENT.
PURE_CALLS: frozenset[str] = frozenset(
    {
        "float", "int", "str", "bool", "round", "abs", "min", "max", "sum",
        "len", "range", "enumerate", "zip", "list", "tuple", "set", "sorted",
        "reversed", "format", "divmod", "pow", "complex",
        "sin", "cos", "tan", "arcsin", "arccos", "arctan", "arctan2",
        "exp", "expm1", "log", "log1p", "log10", "log2", "sqrt", "cbrt",
        "clip", "arange", "linspace", "logspace", "geomspace",
        "zeros", "ones", "full", "empty", "eye", "identity",
        "array", "asarray", "asfarray", "astype", "reshape", "ravel",
        "flatten", "squeeze", "expand_dims", "transpose",
        "maximum", "minimum", "fmax", "fmin", "where", "sign", "power",
        "mod", "remainder", "floor", "ceil", "trunc", "rint",
        "tanh", "sinh", "cosh", "sigmoid", "softmax",
        "cumsum", "cumprod", "prod", "repeat", "tile", "concatenate",
        "stack", "hstack", "vstack", "column_stack", "append",
        "mean", "median", "std", "var", "percentile", "quantile",
        "item", "tolist", "copy", "deepcopy", "join", "strip", "lower",
        "upper", "replace", "zfill", "isoformat",
        # Time AXES built from literals. ``pd.date_range("2024-01-01",
        # periods=24, freq="h")`` manufactures its values the same way
        # ``np.arange`` does; without it the timestamp column of every
        # synthetic gauge frame reads as "might have come from outside" and
        # the three fabricated tide-gauge loaders in resilient-surge stayed
        # unreported. The recursion still requires the ARGUMENTS to be
        # manufactured, so ``pd.to_datetime(df["t"])`` is not.
        "date_range", "period_range", "timedelta_range",
        "to_datetime", "to_timedelta", "Timestamp", "Timedelta",
        "datetime", "timedelta", "date",
        # CONTAINERS over their own arguments, on the same terms as ``array``
        # and ``concatenate`` above: the recursion still requires every
        # argument to be manufactured, so ``pd.DataFrame(xr.open_dataset(p))``
        # is not manufactured and neither is ``pd.DataFrame(rows_passed_in)``.
        # Without them the pandas shape -- data in at construction, stamp
        # bolted on afterwards as a column -- could never satisfy the
        # wholly-manufactured conjunct, so ``frame["data_product"] =
        # "era5_land"`` on a frame of pure noise was silent whatever the
        # column was called. MEASURED across all fourteen repos when adding
        # them: fleet findings 4 -> 4, byte identical.
        "DataFrame", "Series", "dict",
    }
)

#: Module aliases whose ATTRIBUTES are numeric constants rather than data
#: handles -- ``np.pi``, ``math.e``. Needed because a seasonal term written
#: ``2.5 * np.sin(2.0 * np.pi * doy / 365.0)`` is manufactured arithmetic and a
#: rule that could not see ``np.pi`` would call it external.
PURE_MODULES: frozenset[str] = frozenset(
    {
        "np", "numpy", "math", "cmath", "statistics", "scipy", "sp", "torch",
        "npr", "pd", "pandas", "dt",
    }
)

#: Directories never walked. R10's set plus the agent scratch directories,
#: which are not source and whose contents are nobody's deliverable. R10's own
#: set is deliberately left untouched so that adding this check cannot change
#: what R10 measures.
REPO_SKIP_DIRS: frozenset[str] = fabrication.SKIP_DIRS | frozenset(
    {".worktrees", ".claude", ".idea", ".vscode", "vendor", "third_party",
     "_vendor", "docs", "site", "htmlcov", "wheels", ".direnv"}
)


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------

OBSERVED = "OBSERVED"
SIMULATED = "SIMULATED"
OPAQUE = "OPAQUE"
CONTRADICTED = "CONTRADICTED"


def classify_claim(value: str) -> str:
    """Read a provenance value as a claim about origin.

    Returns ``OBSERVED`` when the value asserts the row came from the world,
    ``SIMULATED`` when it declares the row was made up, ``CONTRADICTED`` when
    it does BOTH in the same string, and ``OPAQUE`` when it names something
    this module cannot adjudicate from the string alone -- a source id, a
    dataset code, a product name.

    ``CONTRADICTED`` replaces the precedence rule this function used to apply.
    A simulation token used to beat an observation token in the same value, so
    ``synthetic_weather_real_isd_fallback`` classified as ``SIMULATED`` and
    went unreported while still asserting observation to every human who read
    it. That was the module's own stated cost ("the narrow evasion (stamp
    both)"), and arabica's E-051 found it in a pre-registered label before it
    was shipped. A string that both claims and declares is not an honest
    hedge; it is a label that reads one way to the gate and the other way to a
    reader, which is precisely the defect this module exists to catch. It is
    now a finding of its own.

    ``OPAQUE`` is still never a trigger ON ITS OWN. What decides an opaque
    source label is the construction underneath it, not the string -- see
    :meth:`_ModuleScanner.manufactured_of`.
    """
    tokens = set(tokenise(value))
    if not tokens:
        return OPAQUE
    simulated = bool(tokens & SIMULATED_CLAIM_TOKENS)
    observed = bool(tokens & OBSERVED_CLAIM_TOKENS)
    if simulated and observed:
        return CONTRADICTED
    if simulated:
        return SIMULATED
    if observed:
        return OBSERVED
    return OPAQUE


def is_config_field(name: str) -> bool:
    """True when a field names a knob rather than data.

    Reuses R10's configuration vocabulary rather than growing a second one:
    ``seed``, ``batch_size`` and ``n_workers`` drawn from an RNG and written
    beside a data row are a run note, not a fabricated measurement, and two
    definitions of "this is configuration" is the same as none.
    """
    return bool(HARD_CONFIG_TOKENS & set(tokenise(name)))


def is_identifier_field(name: str) -> bool:
    """True when a field keys or locates the record instead of measuring it.

    Consulted only by :meth:`_ModuleScanner._wholly_manufactured`. It never
    vetoes a field out of the taint hits, so an RNG-drawn identifier is still
    reportable when a stamp claims observation.
    """
    return bool(IDENTIFIER_TOKENS & set(tokenise(name)))


def is_target_field(name: str) -> bool:
    """True when a field names the quantity a model is trained to predict."""
    if name.lower() in {"y", "y_true", "y_obs"}:
        return True
    return bool(TARGET_TOKENS & set(tokenise(name)))


# ---------------------------------------------------------------------------
# Findings
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Stamp:
    """One provenance field on a record."""

    field: str
    value: str
    claim: str

    def render(self) -> str:
        return f'{self.field}="{self.value}"'


@dataclass(frozen=True)
class Finding:
    """One record whose numbers came from an RNG and whose stamp says otherwise."""

    path: str
    #: Line of the record being stamped -- the thing a reader must open.
    line: int
    #: The field carrying fabricated data.
    field: str
    #: The variable that took the RNG draw, and the draw itself.
    origin_symbol: str
    origin_call: str
    #: Line of the RNG draw. Often far from ``line``; both are needed to read
    #: the defect, and quoting only one of them makes the report unusable.
    origin_line: int
    #: THE provenance field that makes this a fabrication rather than an
    #: honestly-labelled simulation. This is the whole finding in one field.
    claim_field: str
    claim_value: str
    #: Provenance fields that corroborate without adjudicating: a source id, a
    #: licence class, the split the row lands in.
    corroborating: tuple[str, ...] = ()
    #: The split this record claims, when it declares one. A fabricated row in
    #: val or test is R5's absolute invariant broken at the source.
    split: str = ""
    snippet: str = ""
    severity: str = TARGET_FABRICATED
    #: Which of the three rules fired. Independent of severity: severity says
    #: where the noise landed, this says what made the label false.
    rule: str = OBSERVED_STAMP
    #: WHY this value was read as a source claim, when the field name alone
    #: did not say so. Either ``allowlist:<entry> [<status>] via <parts>`` --
    #: the value reproduces a compound of a product the repo's own signatory
    #: registered -- or ``observed-token:<token>``. Empty when the finding
    #: came from the field name being a declared provenance field, which needs
    #: no such evidence. A finding a reader cannot re-derive is not evidence,
    #: so this is quoted in the reason, the report and ``to_dict``.
    matched_on: str = ""
    #: The other half of a ``CONTRADICTED_SOURCE`` finding, stated rather than
    #: implied: what the record was BUILT from. A source claim is only
    #: contradicted because nothing on the record came from outside, and a
    #: reader who cannot see that sentence has to reconstruct the rule from
    #: memory before they can judge the finding.
    construction: str = ""
    #: How many of the record's data fields carry a draw, and how many it has.
    #: One finding is emitted per record rather than one per field -- eight
    #: findings for one row would bury seven other rows -- so this pair is
    #: what tells a reader whether the record is lightly jittered or is noise
    #: all the way down.
    tainted_fields: int = 1
    data_fields: int = 1

    def render(self) -> str:
        extra = f"; corroborated by {', '.join(self.corroborating)}" if self.corroborating else ""
        split = f"; split={self.split}" if self.split else ""
        matched = f"; matched on {self.matched_on}" if self.matched_on else ""
        built = f"\n      {self.construction}" if self.construction else ""
        return (
            f"{self.path}:{self.line}  {self.field} <- {self.origin_symbol} "
            f"({self.origin_call} at line {self.origin_line}) stamped "
            f'{self.claim_field}="{self.claim_value}" [{self.rule}/{self.severity}{split}; '
            f"{self.tainted_fields}/{self.data_fields} data fields drawn{matched}{extra}]"
            f"\n      {self.snippet}{built}"
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "path": self.path,
            "line": self.line,
            "field": self.field,
            "origin_symbol": self.origin_symbol,
            "origin_call": self.origin_call,
            "origin_line": self.origin_line,
            "claim_field": self.claim_field,
            "claim_value": self.claim_value,
            "corroborating": list(self.corroborating),
            "split": self.split,
            "snippet": self.snippet,
            "severity": self.severity,
            "rule": self.rule,
            "matched_on": self.matched_on,
            "construction": self.construction,
            "tainted_fields": self.tainted_fields,
            "data_fields": self.data_fields,
        }


@dataclass(frozen=True)
class Origin:
    """Where a tainted value came from."""

    symbol: str
    call: str
    line: int


# ---------------------------------------------------------------------------
# The scanner
# ---------------------------------------------------------------------------


@dataclass
class _Record:
    """A dict literal, constructor call or frame carrying stamps and data."""

    node: ast.AST
    line: int
    stamps: list[Stamp] = field(default_factory=list)
    data: list[tuple[str, ast.AST]] = field(default_factory=list)
    #: Every string-literal field on the record, whatever it is called --
    #: including the ones that ARE declared provenance fields. The field-name
    #: rules read ``stamps``; the value-side rule reads this, because the
    #: field name is the thing an author renames and therefore the thing this
    #: half must not depend on.
    literals: list[tuple[str, str]] = field(default_factory=list)
    #: Names whose taint reaches this record without a nameable field, used by
    #: the frame shape where columns are assigned separately.
    carried: list[str] = field(default_factory=list)
    #: Declared provenance fields whose VALUE this module could not resolve to
    #: any string: ``source=f"era5_{region}"``, ``feed=FEEDS[which]``. The
    #: field name says a provenance claim is being made; the value says
    #: nothing this module can read. Carried as the expression source so a
    #: finding can quote it.
    unreadable: list[tuple[str, str]] = field(default_factory=list)


class _ModuleScanner:
    def __init__(self, path: str, source: str, tree: ast.Module,
                 registry: SourceRegistry | None = None) -> None:
        self.path = path
        self.lines = source.splitlines()
        self.tree = tree
        #: The real-source registry the value-side rule adjudicates against.
        #: Absent means branch (b) cannot fire, which is why every caller
        #: REPORTS whether it had one -- see R11's ``source_registry``
        #: evidence.
        self.registry = registry or NO_REGISTRY
        self.parents: dict[int, ast.AST] = {}
        for parent in ast.walk(tree):
            for child in ast.iter_child_nodes(parent):
                self.parents[id(child)] = parent
        self._taint_cache: dict[int, dict[str, Origin]] = {}
        self._manufactured_cache: dict[int, set[str]] = {}
        self._module_constant_cache: set[str] | None = None
        self._findings: list[Finding] = []
        self._seen: set[tuple[int, str, str]] = set()
        self._module_dicts = self._collect_module_dicts()
        self._module_strings = self._collect_module_strings()
        #: Cycle guard for the ONE fold that jumps across the tree instead of
        #: down it. ``A = {"x": A["x"]}`` is legal Python and would otherwise
        #: recurse until the interpreter gave out -- on a scanner that reads
        #: whatever source a repo happens to contain, that is a crash, and a
        #: crashed check reports nothing.
        self._dict_resolving: set[tuple[str, str]] = set()
        self._class_string_cache: dict[int, dict[str, str]] = {}
        self._tainted_functions: dict[str, Origin] = {}

    # -- source helpers ----------------------------------------------------

    def snippet(self, node: ast.AST) -> str:
        line = getattr(node, "lineno", 0)
        if 1 <= line <= len(self.lines):
            return self.lines[line - 1].strip()[:170]
        return ""

    def ancestors(self, node: ast.AST) -> Iterator[ast.AST]:
        current = self.parents.get(id(node))
        while current is not None:
            yield current
            current = self.parents.get(id(current))

    def enclosing_scope(self, node: ast.AST) -> ast.AST:
        for parent in self.ancestors(node):
            if isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef)):
                return parent
        return self.tree

    def _collect_module_dicts(self) -> dict[str, ast.Dict]:
        """Module-level ``NAME = {...}`` constants, for ``**NAME`` spreads.

        Lifting the stamp block into a module constant and spreading it into
        each row is the natural way to write this code, and a rule that only
        read inline keys would miss every record written that way.
        """
        out: dict[str, ast.Dict] = {}
        for stmt in self.tree.body:
            if isinstance(stmt, ast.Assign) and isinstance(stmt.value, ast.Dict):
                for target in stmt.targets:
                    if isinstance(target, ast.Name):
                        out[target.id] = stmt.value
        return out

    def _collect_module_strings(self) -> dict[str, str]:
        """Module-level ``NAME = "literal"``, for stamps written indirectly.

        ``SOURCE = "era5_land"`` at the top of the file and ``source=SOURCE``
        on the record is a rename with no semantic content, and it defeated
        every rule in this module: nothing here read anything but an
        ``ast.Constant``, so the stamp simply was not a stamp. Found by
        attacking the T8-4 repair, not by reading the code.

        Only DIRECT module-level bindings, and only string literals. A name
        this cannot resolve is left unresolved, which is the quiet direction.
        """
        out: dict[str, str] = {}
        for stmt in self.tree.body:
            if not isinstance(stmt, ast.Assign):
                continue
            if not (isinstance(stmt.value, ast.Constant)
                    and isinstance(stmt.value.value, str)):
                continue
            for target in stmt.targets:
                if isinstance(target, ast.Name):
                    out[target.id] = stmt.value.value
        return out

    def _class_strings(self, klass: ast.ClassDef) -> dict[str, str]:
        """Direct ``NAME = "literal"`` bindings in one class body."""
        cached = self._class_string_cache.get(id(klass))
        if cached is None:
            cached = {}
            for stmt in klass.body:
                if not isinstance(stmt, ast.Assign):
                    continue
                if not (isinstance(stmt.value, ast.Constant)
                        and isinstance(stmt.value.value, str)):
                    continue
                for target in stmt.targets:
                    if isinstance(target, ast.Name):
                        cached[target.id] = stmt.value.value
            self._class_string_cache[id(klass)] = cached
        return cached

    def _string_of(self, node: ast.AST | None) -> str | None:
        """The string this expression IS: constants, one hop, and folding.

        FOLDING, never evaluation. ``f"era5_land"`` and ``"era5" + "_land"``
        are the same three tokens the parser already has, written two other
        ways; a rule that could read one spelling and not the others was
        reading the layout again. Every one of these was a live evasion of the
        T8-4 repair when it was attacked:

            "source": f"era5_land"          # JoinedStr, no placeholder
            "source": "era5" + "_land"      # BinOp
            SOURCE = "era5_land"; "source": SOURCE

        E-M17 residual 4 (M-04 Stage 1) added the four spellings that were
        still readable to the parser and not to this method. Each is the same
        constant-folding argument one syntax over:

            "source": "_".join(["era5", "land"])
            "source": "era5_%s" % "land"
            "source": "era5_{}".format("land")
            FEEDS = {"primary": "era5_land"}; "source": FEEDS["primary"]

        All four were driven SILENT at 8517341 against a record whose only
        data field is an ``rng.normal`` draw, while the plain literal fired.
        The last one is the ``SOURCE = "era5_land"`` hoist already closed
        above, written with a subscript instead of a name: the value is a
        string constant in the module body either way, and reading one and
        not the other is reading the layout.

        FOLDING, NEVER EVALUATION, and the folds are total functions of
        already-resolved STRINGS. ``%`` and ``.format`` are applied only when
        the template and every operand have themselves been folded to strings,
        and only inside a guard that returns ``None`` on any failure -- a
        template this cannot apply is unreadable, not an error to report.

        A placeholder whose value this cannot resolve makes the whole
        expression unreadable and the rule silent, which is the quiet
        direction.
        """
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        if isinstance(node, ast.Name):
            return self._module_strings.get(node.id)
        if isinstance(node, ast.Attribute):
            # ``self.FEED`` where the class body says ``FEED = "era5_land"``.
            # VERIFY-R11-A4 made exactly this argument about NUMERIC
            # constants: a constant is as manufactured wherever it is written
            # down, and a rule that saw it in one place and not the other was
            # reading the layout. The same hoist worked on the STAMP until
            # this line -- moving one string into the class body turned the
            # finding off. Resolved against the ENCLOSING class only, so two
            # classes with the same attribute name cannot borrow each other's
            # value and invent a finding.
            klass = self._enclosing_class(node)
            if klass is None:
                return None
            return self._class_strings(klass).get(node.attr)
        if isinstance(node, ast.JoinedStr):
            parts = [self._string_of(v) for v in node.values]
            if any(p is None for p in parts):
                return None
            return "".join(p for p in parts if p is not None)
        if isinstance(node, ast.FormattedValue):
            return self._string_of(node.value)
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            left = self._string_of(node.left)
            right = self._string_of(node.right)
            if left is None or right is None:
                return None
            return left + right
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mod):
            return self._fold_percent(node)
        if isinstance(node, ast.Subscript):
            return self._module_dict_entry(node)
        if isinstance(node, ast.Call):
            return self._fold_string_method(node)
        return None

    #: Nothing this module reads is a real source label past this length, and
    #: a fold is not a place to build a megabyte. ``"x" * n`` is not folded at
    #: all; this bounds the ``%``/``.format`` width specifiers, which can.
    _FOLD_LIMIT = 4096

    def _bounded(self, text: str | None) -> str | None:
        if text is None or len(text) > self._FOLD_LIMIT:
            return None
        return text

    @staticmethod
    def _template_is_safe_to_apply(template: str) -> bool:
        """Refuse a template whose padding would build the string first.

        ``_bounded`` throws the result away, but ``"{:>999999999}".format("a")``
        has already allocated a gigabyte by the time it can. A scanner reads
        whatever source a repo happens to contain, so "the result is discarded"
        is not a defence against a template written to exhaust it -- the same
        argument as the cycle guard below: a scanner that dies reports nothing
        at all, which is strictly worse than the silence it replaced.

        A width or precision of five digits or more is not a source label.
        Refusing it makes the expression unreadable, which is the quiet
        direction.
        """
        if len(template) > _ModuleScanner._FOLD_LIMIT:
            return False
        run = 0
        for character in template:
            if character.isdigit():
                run += 1
                if run >= 5:
                    return False
            else:
                run = 0
        return True

    def _fold_percent(self, node: ast.BinOp) -> str | None:
        """``"era5_%s" % "land"`` and ``"%s_%s" % ("era5", "land")``.

        Only when the template AND every operand fold to strings. An int on
        the right (``"%d" % 5``) leaves ``_string_of`` returning ``None`` for
        that operand and the whole expression unreadable -- deliberately, so
        this fold cannot be the place a numeric conversion gets invented.
        """
        template = self._string_of(node.left)
        if template is None or not self._template_is_safe_to_apply(template):
            return None
        if isinstance(node.right, (ast.Tuple, ast.List)):
            operands = [self._string_of(e) for e in node.right.elts]
            if any(o is None for o in operands):
                return None
            args: object = tuple(operands)
        else:
            single = self._string_of(node.right)
            if single is None:
                return None
            args = (single,)
        try:
            return self._bounded(template % args)
        except (TypeError, ValueError, KeyError, IndexError):
            # A template these operands do not satisfy is unreadable, not a
            # defect to report. Quiet direction.
            return None

    def _fold_string_method(self, node: ast.Call) -> str | None:
        """``"_".join([...])`` and ``"era5_{}".format(...)``, constants only."""
        func = node.func
        if not isinstance(func, ast.Attribute):
            return None
        receiver = self._string_of(func.value)
        if receiver is None:
            return None
        if func.attr == "join":
            if len(node.args) != 1 or node.keywords:
                return None
            argument = node.args[0]
            if not isinstance(argument, (ast.List, ast.Tuple, ast.Set)):
                # ``sep.join(parts)`` over a name this cannot resolve is the
                # unreadable case, not a fold.
                return None
            parts = [self._string_of(e) for e in argument.elts]
            if any(p is None for p in parts):
                return None
            return self._bounded(receiver.join([p for p in parts if p is not None]))
        if func.attr == "format":
            if not self._template_is_safe_to_apply(receiver):
                return None
            positional = [self._string_of(a) for a in node.args]
            if any(p is None for p in positional):
                return None
            if any(k.arg is None for k in node.keywords):
                return None
            keyword: dict[str, str] = {}
            for k in node.keywords:
                value = self._string_of(k.value)
                if value is None or k.arg is None:
                    return None
                keyword[k.arg] = value
            try:
                return self._bounded(
                    receiver.format(
                        *[p for p in positional if p is not None], **keyword
                    )
                )
            except (TypeError, ValueError, KeyError, IndexError, AttributeError):
                return None
        return None

    def _module_dict_entry(self, node: ast.Subscript) -> str | None:
        """``FEEDS["primary"]`` where the module body holds the dict literal.

        The same hoist ``_collect_module_strings`` already closes for
        ``SOURCE = "era5_land"``, and the same dict ``_record_from_dict``
        already resolves one level deep for ``**FEEDS`` spreads. Reading it
        through a spread and not through a subscript was reading the layout.

        Module-level bindings only, and a CONSTANT STRING key only. A dynamic
        key (``FEEDS[which]``) resolves to nothing and stays quiet.
        """
        holder = node.value
        if not isinstance(holder, ast.Name):
            return None
        table = self._module_dicts.get(holder.id)
        if table is None:
            return None
        slot = node.slice
        if not (isinstance(slot, ast.Constant) and isinstance(slot.value, str)):
            return None
        marker = (holder.id, slot.value)
        if marker in self._dict_resolving:
            return None
        self._dict_resolving.add(marker)
        try:
            for key, value in zip(table.keys, table.values):
                if isinstance(key, ast.Constant) and key.value == slot.value:
                    return self._string_of(value)
        finally:
            self._dict_resolving.discard(marker)
        return None

    def _strings_of(self, node: ast.AST | None) -> list[str]:
        """Every string this expression carries, unwrapping one container.

        ``sources=["era5_land"]`` and ``feeds=("era5_land",)`` are how a
        record names more than one origin, and reading only scalars made the
        list spelling a free evasion.
        """
        if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
            out: list[str] = []
            for element in node.elts:
                out.extend(self._strings_of(element))
            return out
        text = self._string_of(node)
        return [text] if text is not None else []

    # -- taint -------------------------------------------------------------

    @staticmethod
    def _target_names(target: ast.AST) -> list[str]:
        if isinstance(target, ast.Name):
            return [target.id]
        if isinstance(target, ast.Attribute):
            return [target.attr]
        if isinstance(target, (ast.Tuple, ast.List)):
            out: list[str] = []
            for element in target.elts:
                out.extend(_ModuleScanner._target_names(element))
            return out
        if isinstance(target, ast.Subscript):
            return _ModuleScanner._target_names(target.value)
        return []

    def _origin_of(self, expr: ast.AST | None, taint: dict[str, Origin]) -> Origin | None:
        """The RNG origin this expression carries, if any."""
        if expr is None:
            return None
        draw = fabrication._is_random_draw(expr)
        if draw is not None:
            return Origin("<draw>", draw, getattr(expr, "lineno", 0))
        for sub in ast.walk(expr):
            if isinstance(sub, ast.Name) and sub.id in taint:
                return taint[sub.id]
            if isinstance(sub, ast.Attribute) and sub.attr in taint:
                return taint[sub.attr]
            if isinstance(sub, ast.Call):
                func = sub.func
                name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
                if name in self._tainted_functions:
                    inner = self._tainted_functions[name]
                    return Origin(
                        f"{name}()", f"{inner.call} via {name}()", getattr(sub, "lineno", 0)
                    )
        return None

    def _statements(self, scope: ast.AST) -> Iterator[ast.AST]:
        """Every node in ``scope``, not descending into a nested scope.

        ``ast.walk`` cannot be used here. It queues the children of every node
        it visits, so filtering its output would still carry every nested
        function's body into the enclosing scope -- which would let a draw in
        one function taint a record in another and report a defect that does
        not exist. Scope boundaries have to be enforced on the descent.
        """

        def descend(node: ast.AST) -> Iterator[ast.AST]:
            for child in ast.iter_child_nodes(node):
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    continue
                yield child
                yield from descend(child)

        yield from descend(scope)

    def taint_of(self, scope: ast.AST) -> dict[str, Origin]:
        """Names in ``scope`` whose value can carry an RNG draw.

        Flow-INSENSITIVE and computed to a fixpoint: every assignment in the
        scope is considered regardless of position, and the pass repeats until
        nothing new is tainted. Statement order is not evidence -- a rule that
        depended on it would be defeated by moving a line, and this check was
        commissioned specifically to survive reformatting. The cost is
        over-approximation (a name reassigned from a clean source after being
        tainted stays tainted), which is the safe direction for a check whose
        other two conditions are strict.
        """
        key = id(scope)
        if key in self._taint_cache:
            return self._taint_cache[key]
        taint: dict[str, Origin] = {}
        changed = True
        while changed:
            changed = False
            for sub in self._statements(scope):
                pairs: list[tuple[list[str], ast.AST | None]] = []
                if isinstance(sub, ast.Assign):
                    pairs = [(self._target_names(t), sub.value) for t in sub.targets]
                elif isinstance(sub, (ast.AnnAssign, ast.AugAssign, ast.NamedExpr)):
                    pairs = [(self._target_names(sub.target), sub.value)]
                elif isinstance(sub, (ast.For, ast.AsyncFor, ast.comprehension)):
                    pairs = [(self._target_names(sub.target), sub.iter)]
                elif isinstance(sub, ast.withitem) and sub.optional_vars is not None:
                    pairs = [(self._target_names(sub.optional_vars), sub.context_expr)]
                else:
                    continue
                for names, value in pairs:
                    origin = self._origin_of(value, taint)
                    if origin is None:
                        continue
                    for name in names:
                        if name in taint:
                            continue
                        taint[name] = Origin(
                            name if origin.symbol == "<draw>" else origin.symbol,
                            origin.call,
                            origin.line,
                        )
                        changed = True
        self._taint_cache[key] = taint
        return taint

    # -- manufactured values -----------------------------------------------
    #
    # The question this answers is the one a source label makes a claim about:
    # could ANY value on this record have come from outside the running
    # process? Not "does the string sound observed" -- that is the question
    # that was defeated by naming a fully synthetic loader ``era5_land``.
    #
    # A value is MANUFACTURED when it is built only from literals, RNG draws,
    # loop indices over manufactured ranges, scalar parameters with literal
    # defaults, and arithmetic or pure numeric calls over those. Anything else
    # -- a file handle, a request, a dataframe passed in, a parameter with no
    # default, an attribute of an object this scope did not build, a call to
    # an unrecognised helper -- is NOT manufactured, and the check goes silent.
    # The unknown direction is deliberately the quiet one: an unrecognised
    # call must never be the thing that CREATES a finding.

    @staticmethod
    def _is_literal_default(node: ast.AST | None) -> bool:
        """True when a parameter default is a literal.

        ``lat_min=-20.0`` does NOT parse to ``ast.Constant``; it parses to
        ``UnaryOp(USub, Constant(20.0))``. Reading only ``ast.Constant`` here
        silently dropped every negative bound in the ERA5 grid loader -- the
        exact shape this rule exists for -- and the check stayed green for a
        reason that had nothing to do with the data. Literal containers are
        included for the same reason: ``bands=("t2m", "tp")`` is a knob.
        """
        if node is None:
            return False
        if isinstance(node, ast.Constant):
            return True
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
            return _ModuleScanner._is_literal_default(node.operand)
        if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
            return all(_ModuleScanner._is_literal_default(e) for e in node.elts)
        if isinstance(node, ast.Dict):
            return all(
                (k is None or _ModuleScanner._is_literal_default(k))
                and _ModuleScanner._is_literal_default(v)
                for k, v in zip(node.keys, node.values)
            )
        return False

    def _scope_parameters(self, scope: ast.AST) -> set[str]:
        """Parameters that are knobs rather than inbound data.

        A parameter with a LITERAL default is a dial the caller may turn --
        ``days=365``, ``resolution=0.5``, ``lat_min=-20.0``. A parameter with
        no default is how data arrives, and a record built from one is not
        wholly manufactured however the rest of it was made. That distinction
        is what keeps this rule off ``def build(years)`` and ``def
        jitter(rows)``.
        """
        if not isinstance(scope, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return set()
        args = scope.args
        positional = list(args.posonlyargs) + list(args.args)
        out: set[str] = set()
        # Defaults right-align onto the positional parameters.
        for arg, default in zip(positional[len(positional) - len(args.defaults):],
                                args.defaults):
            if self._is_literal_default(default):
                out.add(arg.arg)
        for kwarg, kw_default in zip(args.kwonlyargs, args.kw_defaults):
            if kw_default is not None and self._is_literal_default(kw_default):
                out.add(kwarg.arg)
        return out

    @staticmethod
    def _is_draw_call(node: ast.AST) -> bool:
        """True when ``node`` IS an RNG draw, not merely one containing a draw.

        ``fabrication._is_random_draw`` answers "is there a draw anywhere under
        here", which is the right question for taint and the wrong one here.
        ``float(row.t2m) + rng.normal(0, 0.01)`` contains a draw and is NOT
        manufactured -- half of it was read off a dataset -- and treating it as
        manufactured made the rule fire on a real loader that jitters real
        data. The callee is re-asked on its own, with the arguments removed, so
        the draw vocabulary still has exactly one definition.
        """
        if not isinstance(node, ast.Call):
            return False
        bare = ast.copy_location(ast.Call(func=node.func, args=[], keywords=[]), node)
        return fabrication._is_random_draw(bare) is not None

    def _manufactured_expr(self, node: ast.AST | None, names: set[str]) -> bool:
        """True when nothing in ``node`` can carry a value from outside."""
        if node is None:
            return False
        if self._is_draw_call(node):
            # A draw manufactures its output -- provided its own parameters
            # were manufactured too. ``rng.normal(loc=df.mean(), scale=0.1)``
            # is noise centred on real data and is not adjudicated here.
            assert isinstance(node, ast.Call)
            return (
                all(self._manufactured_expr(a, names) for a in node.args)
                and all(self._manufactured_expr(k.value, names) for k in node.keywords)
            )
        if isinstance(node, ast.Constant):
            return True
        if isinstance(node, ast.Name):
            return node.id in names
        if isinstance(node, ast.Attribute):
            base = node.value
            if isinstance(base, ast.Name) and base.id in PURE_MODULES:
                return True  # np.pi, math.e -- a constant, not a handle.
            return node.attr in names
        if isinstance(node, ast.Call):
            func = node.func
            fname = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
            if fname not in PURE_CALLS:
                return False
            if isinstance(func, ast.Attribute):
                base = func.value
                pure_module = isinstance(base, ast.Name) and base.id in PURE_MODULES
                if not pure_module and not self._manufactured_expr(base, names):
                    return False
            return (
                all(self._manufactured_expr(a, names) for a in node.args)
                and all(self._manufactured_expr(k.value, names) for k in node.keywords)
            )
        if isinstance(node, ast.Slice):
            return all(
                part is None or self._manufactured_expr(part, names)
                for part in (node.lower, node.upper, node.step)
            )
        if isinstance(node, (ast.BinOp, ast.UnaryOp, ast.BoolOp, ast.Compare,
                             ast.IfExp, ast.JoinedStr, ast.FormattedValue,
                             ast.Tuple, ast.List, ast.Set, ast.Dict,
                             ast.Subscript, ast.Starred, ast.Index)):
            children = list(ast.iter_child_nodes(node))
            values = [c for c in children if isinstance(c, ast.expr)]
            if not values:
                return True
            return all(self._manufactured_expr(c, names) for c in values)
        return False

    def _literal_bindings(self, body: list[ast.stmt]) -> set[str]:
        """Names bound to manufactured expressions by the statements in ``body``.

        Only the DIRECT statements of a module or class body -- never a nested
        function -- run to a fixpoint against the same expression rule the
        scope pass uses. A binding this cannot prove manufactured is left out,
        which is the quiet direction.
        """
        names: set[str] = set()
        changed = True
        while changed:
            changed = False
            for sub in body:
                if isinstance(sub, ast.Assign):
                    pairs = [(self._bound_names(t), sub.value) for t in sub.targets]
                elif isinstance(sub, ast.AnnAssign):
                    if sub.value is None:
                        continue
                    pairs = [(self._bound_names(sub.target), sub.value)]
                else:
                    continue
                for targets, value in pairs:
                    if not self._manufactured_expr(value, names):
                        continue
                    for name in targets:
                        if name not in names:
                            names.add(name)
                            changed = True
        return names

    def _module_constants(self) -> set[str]:
        cached = self._module_constant_cache
        if cached is None:
            cached = self._literal_bindings(self.tree.body)
            self._module_constant_cache = cached
        return cached

    def _enclosing_class(self, scope: ast.AST) -> ast.ClassDef | None:
        node: ast.AST | None = scope
        while node is not None:
            parent = self.parents.get(id(node))
            if isinstance(parent, ast.ClassDef):
                return parent
            node = parent
        return None

    def _outer_constants(self, scope: ast.AST) -> set[str]:
        """Literal constants bound OUTSIDE ``scope`` but visible inside it.

        VERIFY-R11-A4. Without this, the cheapest evasion of
        ``CONTRADICTED_SOURCE`` was a refactor with no semantic content: hoist
        one literal out of the function.

            BASE_T = 22.0                          # module constant, or
            class L:
                BASE_T = 22.0                      # class attribute
                ...
                t2m = float(self.BASE_T + self.rng.normal(0, 1.2))

        made ``t2m`` unprovable, so the record stopped being wholly
        manufactured and the rule went silent on a loader that was still 100%
        noise. Measured on the shipped ERA5 shape: moving ``22.0`` to either
        place turned the finding off. A constant is exactly as manufactured
        wherever it is written down, and a rule that could see it in one place
        and not the other was reading the layout rather than the code.

        A name the scope ASSIGNS is dropped from this seed: the outer binding
        is shadowed, and re-adding it would be the over-approximation this
        pass must never make. The local fixpoint re-adds it if the local value
        is itself manufactured.
        """
        outer = set(self._module_constants())
        klass = self._enclosing_class(scope)
        if klass is not None:
            outer |= self._literal_bindings(klass.body)
        if not outer:
            return outer
        assigned: set[str] = set()
        for sub in self._statements(scope):
            if isinstance(sub, ast.Assign):
                for t in sub.targets:
                    assigned.update(self._target_names(t))
            elif isinstance(sub, (ast.AnnAssign, ast.AugAssign, ast.NamedExpr,
                                  ast.For, ast.AsyncFor, ast.comprehension)):
                assigned.update(self._target_names(sub.target))
        return outer - assigned

    @staticmethod
    def _bound_names(target: ast.AST) -> list[str]:
        """Names this target proves something about. NOT ``obj[k] = v``.

        ``_target_names`` deliberately reports the BASE of a subscript, so
        ``df["water_level_m"] = rng.normal(...)`` taints ``df`` -- correct for
        the taint pass, whose whole job is to over-approximate.

        It is wrong here, and measurably so. ``payload["verdict"] =
        "MEASURED"`` writes one literal into one key and says NOTHING about
        the other forty values in ``payload``; treating it as a proof that
        ``payload`` was manufactured is precisely the over-approximation this
        pass documents that it must never make. MEASURED on the fleet: it put
        ``scripts/measure_coops_vintage_delta.py``'s payload -- a record built
        from ``_git()`` output and a live NOAA CO-OPS fetch -- into
        ``manufactured_of``, and two of resilient-blackout's honestly-labelled
        metrics dicts with it. Three false CONTRADICTED_SOURCE findings, all
        three on code that reads real data, all three from this one line.

        Attribute targets stay: ``self.BASE_T = 22.0`` binds a whole value,
        and ``_manufactured_expr`` reads ``self.BASE_T`` back by that same
        attribute name, so the two halves agree.
        """
        if isinstance(target, ast.Subscript):
            return []
        if isinstance(target, (ast.Tuple, ast.List)):
            out: list[str] = []
            for element in target.elts:
                out.extend(_ModuleScanner._bound_names(element))
            return out
        return _ModuleScanner._target_names(target)

    def manufactured_of(self, scope: ast.AST) -> set[str]:
        """Names in ``scope`` that provably came from inside this process.

        Seeded with the scope's literal-defaulted parameters, then run to a
        fixpoint over the same assignment forms the taint pass reads.
        Flow-insensitive for the same reason: statement order is not evidence.

        Over-approximating here would be UNSAFE -- it is the conjunct that
        makes an opaque source label a finding -- so unlike ``taint_of`` this
        pass is deliberately conservative. Anything it cannot prove
        manufactured stays out, and the check stays quiet. Element writes
        (``obj[k] = v``) prove nothing about ``obj`` and are dropped here; see
        :meth:`_bound_names`.
        """
        key = id(scope)
        cached = self._manufactured_cache.get(key)
        if cached is not None:
            return cached
        # NOT seeded from ``taint_of``. Taint is a "contains a draw anywhere"
        # relation, so a name assigned ``float(row.t2m) + rng.normal(0, 0.01)``
        # is tainted while being half real data; seeding from it would carry
        # that same false positive one hop further and out of sight of the
        # expression rule below.
        names: set[str] = self._scope_parameters(scope) | self._outer_constants(scope)
        changed = True
        while changed:
            changed = False
            for sub in self._statements(scope):
                pairs: list[tuple[list[str], ast.AST | None]] = []
                if isinstance(sub, ast.Assign):
                    pairs = [(self._bound_names(t), sub.value) for t in sub.targets]
                elif isinstance(sub, (ast.AnnAssign, ast.AugAssign, ast.NamedExpr)):
                    pairs = [(self._bound_names(sub.target), sub.value)]
                elif isinstance(sub, (ast.For, ast.AsyncFor, ast.comprehension)):
                    pairs = [(self._bound_names(sub.target), sub.iter)]
                else:
                    continue
                for targets, value in pairs:
                    if not self._manufactured_expr(value, names):
                        continue
                    for name in targets:
                        if name not in names:
                            names.add(name)
                            changed = True
        self._manufactured_cache[key] = names
        return names

    def _resolve_tainted_functions(self) -> None:
        """Module-local helpers whose return value carries a draw.

        One level of inter-procedural propagation, iterated to a fixpoint so a
        chain of helpers resolves. Without it the commonest refactor of the
        defect -- lift the draw into ``_draw_features()`` and call it -- walks
        straight past the check.
        """
        functions = [
            node for node in ast.walk(self.tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        changed = True
        while changed:
            changed = False
            for fn in functions:
                if fn.name in self._tainted_functions:
                    continue
                self._taint_cache.pop(id(fn), None)
                taint = self.taint_of(fn)
                for sub in self._statements(fn):
                    if not isinstance(sub, ast.Return) or sub.value is None:
                        continue
                    origin = self._origin_of(sub.value, taint)
                    if origin is not None:
                        self._tainted_functions[fn.name] = origin
                        changed = True
                        break
        # Taint computed before the helper set was known is stale; recompute.
        self._taint_cache.clear()
        self._manufactured_cache.clear()

    # -- records -----------------------------------------------------------

    def _stamps_from(self, name: str, value: ast.AST) -> list[Stamp]:
        """Every provenance stamp this field carries. Empty when it is not one."""
        if name not in PROVENANCE_FIELDS:
            return []
        return [self._stamp_of(name, text) for text in self._strings_of(value)]

    def _stamp_of(self, name: str, text: str) -> Stamp:
        if name in SPLIT_FIELDS:
            return Stamp(name, text, OPAQUE)
        if name in LICENCE_FIELDS:
            claim = classify_claim(text)
            # A licence class states permission, not origin. It corroborates
            # ("these rows are to be trained on") but never triggers.
            return Stamp(name, text, SIMULATED if claim is SIMULATED else OPAQUE)
        return Stamp(name, text, classify_claim(text))

    def _record_from_dict(self, node: ast.Dict) -> _Record:
        record = _Record(node, getattr(node, "lineno", 0))
        for key, value in zip(node.keys, node.values):
            if key is None:
                # ``**SPREAD`` -- resolve one level against module constants.
                if isinstance(value, ast.Name) and value.id in self._module_dicts:
                    spread = self._record_from_dict(self._module_dicts[value.id])
                    record.stamps.extend(spread.stamps)
                    record.literals.extend(spread.literals)
                    record.unreadable.extend(spread.unreadable)
                else:
                    record.carried.extend(self._target_names(value) or [])
                continue
            if not (isinstance(key, ast.Constant) and isinstance(key.value, str)):
                continue
            name = key.value
            record.literals.extend((name, t) for t in self._strings_of(value))
            stamps = self._stamps_from(name, value)
            if stamps:
                record.stamps.extend(stamps)
                continue
            if name in PROVENANCE_FIELDS:
                record.unreadable.extend(self._unreadable_of(name, value))
                continue
            record.data.append((name, value))
        return record

    def _unreadable_of(self, name: str, value: ast.AST) -> list[tuple[str, str]]:
        """A declared SOURCE-NAMING field whose value resolved to no string.

        Scoped to :data:`SOURCE_NAMING_FIELDS`, not to all of
        :data:`PROVENANCE_FIELDS`, and for the same reason that set exists:
        ``kind``, ``*_type``, ``method`` and the licence and split fields name
        a shape, a permission or a partition rather than an origin, and a
        computed value under one of them is not an unread source claim. A
        record whose only unresolved provenance field is ``split=chosen``
        would otherwise take its repo's R11 row to NA over a partition name.

        This is the one place the module leans on a field-NAME list again
        after moving the source rule off one, and it can only do so because
        the verdict it produces is NA: under-reporting here costs a record
        nobody was told to open, which is the same conservative direction
        every other conjunct in this module leans.
        """
        if name not in SOURCE_NAMING_FIELDS:
            return []
        if isinstance(value, (ast.Tuple, ast.List, ast.Set)) and not value.elts:
            return []
        try:
            expression = ast.unparse(value)
        except (TypeError, ValueError, AttributeError):
            return []
        return [(name, expression[:200])]

    def _record_from_call(self, node: ast.Call) -> _Record | None:
        if not node.keywords:
            return None
        record = _Record(node, getattr(node, "lineno", 0))
        for keyword in node.keywords:
            if keyword.arg is None:
                if isinstance(keyword.value, ast.Name) \
                        and keyword.value.id in self._module_dicts:
                    spread = self._record_from_dict(self._module_dicts[keyword.value.id])
                    record.stamps.extend(spread.stamps)
                    record.literals.extend(spread.literals)
                    record.unreadable.extend(spread.unreadable)
                continue
            record.literals.extend(
                (keyword.arg, t) for t in self._strings_of(keyword.value)
            )
            stamps = self._stamps_from(keyword.arg, keyword.value)
            if stamps:
                record.stamps.extend(stamps)
                continue
            if keyword.arg in PROVENANCE_FIELDS:
                record.unreadable.extend(
                    self._unreadable_of(keyword.arg, keyword.value)
                )
                continue
            record.data.append((keyword.arg, keyword.value))
        return record

    def _frame_records(self, scope: ast.AST) -> list[_Record]:
        """``df["label_origin"] = "observed_ccc"`` beside a tainted frame.

        The pandas shape: the data goes in when the frame is built and the
        stamp is bolted on afterwards as a column. Nothing about it is one
        expression, so the record has to be assembled from the scope.

        Every string-literal column is collected, not only the ones whose NAME
        is a declared provenance field. Collecting only the latter would leave
        the whole value-side rule blind to ``df["data_product"] =
        "era5_land"`` -- the same rename this rule exists to survive, one
        syntax over.
        """
        stamps: dict[str, list[Stamp]] = {}
        literals: dict[str, list[tuple[str, str]]] = {}
        anchors: dict[str, ast.AST] = {}
        for sub in self._statements(scope):
            if not isinstance(sub, ast.Assign) or len(sub.targets) != 1:
                continue
            target = sub.targets[0]
            if not isinstance(target, ast.Subscript):
                continue
            holder = target.value
            holder_name = holder.id if isinstance(holder, ast.Name) else \
                getattr(holder, "attr", "")
            slot = target.slice
            if not (holder_name and isinstance(slot, ast.Constant)
                    and isinstance(slot.value, str)):
                continue
            texts = self._strings_of(sub.value)
            if texts:
                literals.setdefault(holder_name, []).extend(
                    (slot.value, t) for t in texts
                )
                anchors.setdefault(holder_name, sub)
            found = self._stamps_from(slot.value, sub.value)
            if not found:
                continue
            stamps.setdefault(holder_name, []).extend(found)
            anchors.setdefault(holder_name, sub)
        out: list[_Record] = []
        for name, anchor in anchors.items():
            record = _Record(anchor, getattr(anchor, "lineno", 0))
            record.stamps = stamps.get(name, [])
            record.literals = literals.get(name, [])
            record.carried = [name]
            out.append(record)
        return out

    # -- adjudication ------------------------------------------------------

    def _value_side_claim(self, record: _Record) -> tuple[Stamp, str] | None:
        """A source claim read off a VALUE, whatever the field is called.

        This is the half that survives a rename. The field-name rules above
        adjudicate ``source=``, ``label_origin=`` and twenty-odd siblings, and
        E-M17 measured what that costs: the same wholly manufactured ERA5
        loader with ``source=`` renamed to ``data_product=``, ``feed=``,
        ``provider=``, ``archive=`` or any of 24 measured names went silent,
        24 of 24. Extending the list closes 24 names and no more, which is the
        identical argument this module already makes against a deny-list of
        product names.

        So the field name is not consulted at all here. What is consulted is
        the VALUE, against two vocabularies neither of which this rule
        invented:

        (a) :data:`OBSERVED_CLAIM_TOKENS` -- already shipped, already the
            thing that makes ``label_origin="observed_ccc"`` a finding, now
            applied wherever the string is written.

        (b) the repo's own signed ``docs/allowlist.yaml`` -- the human
            signatory's record of which products are real. A value naming an
            allowlisted product, on a record already PROVEN drawn from an RNG
            and literals, is contradicted by the portfolio's own source of
            truth. ``era5_land`` is a finding under any field name because
            ERA5-Land is registered where it is used, not because this module
            holds an opinion about ERA5.

        Two guards, both load-bearing, both measured:

        * The value must not declare itself. ``SIMULATED`` and
          ``CONTRADICTED`` values are skipped, so
          ``data_product="era5_land_shaped_synthetic_grid"`` stays a fixture
          and the ``note="... DRAWN, not observed ..."`` disclaimer in
          torrent's ``v4_orchestrator`` stays silent on its own value, on top
          of the record-level honesty rule that already covers it.
        * The caller must have proved the record WHOLLY manufactured. That
          precondition is the reason this can read every field instead of a
          list of them, and relaxing it is what turned 4 findings into 29.
        """
        observed_hit: tuple[Stamp, str] | None = None
        registry_hit: tuple[Stamp, str] | None = None
        for name, text in record.literals:
            claim = classify_claim(text)
            if claim is SIMULATED or claim is CONTRADICTED:
                continue
            if claim is OBSERVED and observed_hit is None and is_label_value(text):
                token = min(set(tokenise(text)) & OBSERVED_CLAIM_TOKENS)
                observed_hit = (Stamp(name, text, OBSERVED), f"observed-token:{token}")
                continue
            if registry_hit is None:
                hit = self.registry.match(text)
                if hit is not None:
                    registry_hit = (Stamp(name, text, OPAQUE), hit.render())
        return observed_hit or registry_hit

    def _decide(self, record: _Record) -> tuple[str, Stamp, str] | None:
        """Which rule this record trips, the stamp that trips it, and why.

        Four gates, in the order a reader should hear them. The record's
        construction is not consulted here -- that is the caller's job, and it
        is what settles the last two.
        """
        observed = [s for s in record.stamps if s.claim is OBSERVED]
        declared = [s for s in record.stamps if s.claim is SIMULATED]
        both_in_one = [s for s in record.stamps if s.claim is CONTRADICTED]

        if both_in_one:
            # One string that claims and declares at once:
            # ``synthetic_weather_real_isd_fallback``.
            return CONTRADICTED_STAMP, both_in_one[0], ""
        if observed and declared:
            # Two stamps on one record saying opposite things. This used to be
            # an exemption -- "a record that says synthetic somewhere is not
            # passing itself off" -- and it was the cheapest way past this
            # check: keep the observed claim that R5 counts by, add a second
            # field nothing counts by. Report the OBSERVED stamp, because that
            # is the one that travels into a manifest, and carry the
            # declaration in the corroboration so a reader sees the conflict.
            return CONTRADICTED_STAMP, observed[0], ""
        if observed:
            return OBSERVED_STAMP, observed[0], ""
        if declared:
            # Declares itself and claims nothing. A fixture. Silent. This is
            # the honesty rule, and it is UNCHANGED: a simulation token in any
            # provenance field of the record ends the adjudication here,
            # before either source rule below is reached.
            return None

        named = [
            s for s in record.stamps
            if s.field in SOURCE_NAMING_FIELDS and s.claim is OPAQUE and tokenise(s.value)
        ]
        if named:
            return CONTRADICTED_SOURCE, named[0], ""

        # The field name said nothing. Ask the value.
        value_side = self._value_side_claim(record)
        if value_side is not None:
            stamp, matched_on = value_side
            return CONTRADICTED_SOURCE, stamp, matched_on

        # Nothing on this record resolved to a string at all, and yet it
        # DECLARES a provenance field. The record is not clean and it is not
        # a fabrication: it is unadjudicated, and saying so is the honest
        # third verdict. Reported only when the record carries no readable
        # stamp of any kind -- one resolvable declaration beside the dynamic
        # value ends the adjudication in the honesty rule above, and one
        # resolvable source value would have fired the rule above this.
        if record.unreadable and not record.stamps and not record.literals:
            name, expression = record.unreadable[0]
            return UNREADABLE_STAMP, Stamp(name, expression, OPAQUE), ""
        return None

    def _wholly_manufactured(self, record: _Record, scope: ast.AST) -> bool:
        """True when no value on this record could have come from outside.

        The substance behind an opaque source label. ``source="era5_land"`` on
        a record whose every field is an RNG draw, a literal, or arithmetic
        over a loop index is a label contradicted by the construction it
        labels: there is no ERA5 anywhere in it. The same label on a record
        that also carries a value read from a file, passed in as an argument,
        or pulled off an object this scope did not build is NOT adjudicated,
        because then the label may well describe where that value came from.

        Note what this does NOT do: it does not decide whether ``era5_land``
        names a real registry. That judgement stays out of the gate. It reads
        the code instead, which is checkable.
        """
        names = self.manufactured_of(scope)
        values = [
            v for name, v in record.data
            if not is_config_field(name) and not is_identifier_field(name)
        ]
        if not values and not record.carried:
            return False
        if not all(self._manufactured_expr(v, names) for v in values):
            return False
        return all(name in names for name in record.carried)

    def _adjudicate(self, record: _Record, taint: dict[str, Origin],
                    scope: ast.AST) -> None:
        decision = self._decide(record)
        if decision is None:
            return
        rule, claim, matched_on = decision
        if rule in (CONTRADICTED_SOURCE, UNREADABLE_STAMP) \
                and not self._wholly_manufactured(record, scope):
            return

        split = next((s.value for s in record.stamps if s.field in SPLIT_FIELDS), "")
        corroborating = tuple(
            s.render() for s in record.stamps
            if s is not claim and s.field not in SPLIT_FIELDS
        )

        hits: list[tuple[str, Origin]] = []
        for name, value in record.data:
            if is_config_field(name):
                continue
            origin = self._origin_of(value, taint)
            if origin is not None:
                if origin.symbol == "<draw>":
                    # Drawn straight into the record, never named. The field it
                    # was written to is the only name it ever had.
                    origin = Origin(name, origin.call, origin.line)
                hits.append((name, origin))
        for name in record.carried:
            origin = taint.get(name)
            if origin is not None and not is_config_field(name):
                hits.append((name, origin))
        if not hits:
            return

        # One finding per RECORD, not per field. A row whose every column is
        # drawn would otherwise emit a dozen findings and bury eleven other
        # rows; the counts carried on the finding say how deep it goes.
        # Report the target field when one is tainted, because that is the
        # aggravated form and the one a reader must see first; otherwise the
        # first tainted input field.
        hits.sort(key=lambda h: (not is_target_field(h[0]), h[0]))
        if rule is UNREADABLE_STAMP and not is_target_field(hits[0][0]):
            # The NA lane is scoped to a drawn TARGET, and only to that. A
            # record whose INPUT columns are drawn under a dynamic source
            # stamp is the ordinary conservative under-report this module has
            # always taken; widening the NA to it would turn an unresolvable
            # f-string on any manufactured row into a fleet-wide verdict
            # change, which is what the over-fire budget exists to stop.
            return
        data_fields = sum(1 for name, _ in record.data if not is_config_field(name)) \
            + len(record.carried)
        construction = ""
        if rule is UNREADABLE_STAMP:
            construction = (
                f"unadjudicated: the record is wholly manufactured in this "
                f"process and its target field carries an RNG draw, and the "
                f"only provenance value it declares is "
                f"{claim.field}={claim.value} -- an expression this module "
                f"cannot resolve to a string. Neither a fabrication nor a "
                f"clean record: NOT MEASURED. Resolve the value or declare "
                f"the record's provenance beside it."
            )
        if rule is CONTRADICTED_SOURCE:
            drawn = ", ".join(sorted({n for n, _ in hits}))
            construction = (
                f"construction: wholly manufactured in this process -- "
                f"{len(hits)} of {max(data_fields, len(hits))} data field(s) "
                f"({drawn}) carry an RNG draw, and every remaining value is a "
                f"literal, a literal-defaulted parameter, or arithmetic over "
                f"those. Nothing on the record came from "
                f'{claim.field}="{claim.value}" because nothing on it came '
                f"from anywhere."
            )
        for name, origin in hits[:1]:
            key = (record.line, name, claim.field)
            if key in self._seen:
                continue
            self._seen.add(key)
            self._findings.append(
                Finding(
                    path=self.path,
                    line=record.line,
                    field=name,
                    origin_symbol=origin.symbol,
                    origin_call=origin.call,
                    origin_line=origin.line,
                    claim_field=claim.field,
                    claim_value=claim.value,
                    corroborating=corroborating,
                    split=split,
                    snippet=self.snippet(record.node),
                    severity=(
                        UNREADABLE_STAMP if rule is UNREADABLE_STAMP
                        else TARGET_FABRICATED if is_target_field(name)
                        else INPUT_FABRICATED
                    ),
                    rule=rule,
                    matched_on=matched_on,
                    construction=construction,
                    tainted_fields=len(hits),
                    data_fields=max(data_fields, len(hits)),
                )
            )

    # -- the walk ----------------------------------------------------------

    def scan(self) -> list[Finding]:
        self._resolve_tainted_functions()
        scopes: list[ast.AST] = [self.tree]
        scopes.extend(
            node for node in ast.walk(self.tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        )
        for scope in scopes:
            # Every scope is walked, including those whose taint map is empty.
            # A draw written straight into the record --
            # ``{"tonnes": float(rng.normal(4500.0, 90.0)), ...}`` -- never
            # passes through a named variable, so it taints nothing and an
            # empty-taint shortcut would skip the most direct form of the
            # defect there is.
            taint = self.taint_of(scope)
            for sub in self._statements(scope):
                if isinstance(sub, ast.Dict):
                    self._adjudicate(self._record_from_dict(sub), taint, scope)
                elif isinstance(sub, ast.Call):
                    record = self._record_from_call(sub)
                    if record is not None:
                        self._adjudicate(record, taint, scope)
            for record in self._frame_records(scope):
                self._adjudicate(record, taint, scope)
        self._findings.sort(key=lambda f: (f.path, f.line, f.field))
        return self._findings


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def iter_repo_python_files(root: Path) -> Iterator[Path]:
    """Every Python file in a repo, wherever it lives.

    This is the point of R11: no declared-tree list, no opt-in. ``scripts/``,
    ``benchmarks/``, ``notebooks/`` and a one-off at the repo root are all
    walked, because the declared-tree list is the surface the author controls
    and the incident this check exists for lived entirely outside it.

    ``tests/`` stays excluded, and that exclusion is load-bearing rather than
    incidental: a test asserting that this check fires has to CONTAIN the
    defect it asserts on, and scanning tests would make every control fixture
    a finding. Test data does not enter a manifest, so nothing measured is
    lost.
    """
    return fabrication.iter_python_files([root], skip=REPO_SKIP_DIRS)


def scan_source(source: str, display: str,
                registry: SourceRegistry | None = None) -> list[Finding]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    return _ModuleScanner(display, source, tree, registry).scan()


def scan_file(path: Path, display: str | None = None,
              registry: SourceRegistry | None = None) -> list[Finding]:
    """Findings for one Python file. Unreadable or unparseable files yield none."""
    try:
        source = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    return scan_source(source, display or str(path), registry)


def scan_repo(root: Path, registry: SourceRegistry | None = None) -> list[Finding]:
    """Findings across every Python file in a repo.

    The registry defaults to the repo's OWN signed allowlist, read fresh.
    Passing one explicitly is for callers that already loaded it (and for
    controls); passing :data:`NO_REGISTRY` deliberately disables branch (b),
    which is a thing a control does and never a thing production does.
    """
    if registry is None:
        registry = load_source_registry(root)
    findings: list[Finding] = []
    for path in iter_repo_python_files(root):
        display = str(path.relative_to(root)) if path.is_relative_to(root) else str(path)
        findings.extend(scan_file(path, display, registry))
    findings.sort(key=lambda f: (f.path, f.line, f.field))
    return findings


def count_python_files(roots: Iterable[Path]) -> int:
    return sum(1 for _ in fabrication.iter_python_files(roots, skip=REPO_SKIP_DIRS))
