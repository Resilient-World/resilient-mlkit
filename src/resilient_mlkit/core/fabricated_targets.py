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
One thing, and it is checkable: the *value* of the provenance field.

* ``label_origin="observed_ccc"``  -> the record claims observation. FINDING.
* ``label_origin="synthetic"``     -> the record declares itself. SILENT.
* ``source_id="civ_ccc_regional"`` -> names something, claims nothing this
  module can adjudicate. OPAQUE: reported as corroboration, never as the
  trigger.

A record carrying a simulation declaration in ANY of its provenance fields is
never reported, even when another field claims observation. That asymmetry is
deliberate. A record that says "synthetic" somewhere is not passing itself off,
and flagging it would put this check in the business of adjudicating internally
inconsistent metadata -- a job for review, not for a gate. The cost is a narrow
evasion (stamp both) and it is stated here rather than hidden; the benefit is
that the check never fires on an honest fixture, and a check that fires on
honest work gets disabled.

The simulation vocabulary is read from PROVENANCE FIELDS ONLY. A comment, a
docstring or an unrelated ``"note": "synthetic demo"`` does not excuse a
record, because none of those travel into a manifest.

THE THREE PARTS, ALL REQUIRED
-----------------------------
1. **An RNG draw.** Detected with ``fabrication._is_random_draw``, the same
   vocabulary R10 uses -- one definition of "this number came from noise".
2. **Flow from that draw into a written field.** A flow-insensitive taint
   fixpoint over each function scope, with one level of inter-procedural
   propagation through module-local helpers whose return value is tainted.
   Flow-INsensitive on purpose: an AST rule that depended on statement order
   would be defeated by moving a line, and the brief for this check is that it
   survive reformatting.
3. **A provenance field on the same record claiming observed origin.**

Miss any one and the module is silent. An RNG draw with no stamp is a fixture.
A stamp with no draw is a data record. A stamp on a record whose only tainted
field is a config knob (``seed``, ``batch_size``) is a run note; the
configuration vocabulary R10 already maintains vetoes those.

WHAT THIS MODULE DOES NOT CLAIM TO CATCH, so that a green R11 is not read as
more than it is: a target read from a file that was itself generated in an
earlier process (the draw is not in this repo's AST); a target derived from
another column by closed-form arithmetic with no RNG anywhere (that is R5's
formula-derivation probe, which measures the data rather than the code); and
taint carried through a class attribute or a global mutated across functions.
The first two are covered elsewhere in the instrument. The third is a gap,
stated rather than papered over.
"""

from __future__ import annotations

import ast
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from pathlib import Path

from . import fabrication
from .fabrication import HARD_CONFIG_TOKENS, tokenise

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

#: Severity of a finding, ranked. Both are defects; only the first puts noise
#: where a model's target is supposed to be.
TARGET_FABRICATED = "TARGET_FABRICATED"
INPUT_FABRICATED = "INPUT_FABRICATED"

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


def classify_claim(value: str) -> str:
    """Read a provenance value as a claim about origin.

    Returns ``OBSERVED`` when the value asserts the row came from the world,
    ``SIMULATED`` when it declares the row was made up, and ``OPAQUE`` when it
    names something this module cannot adjudicate -- a source id, a dataset
    code, a product name. OPAQUE is reported as corroboration and never as a
    trigger, because guessing whether ``civ_ccc_regional`` is a real registry
    is exactly the kind of judgement a gate must not make.

    A value declaring simulation wins over one claiming observation, so that
    ``"synthetic observed-style panel"`` is silent rather than flagged.
    """
    tokens = set(tokenise(value))
    if not tokens:
        return OPAQUE
    if tokens & SIMULATED_CLAIM_TOKENS:
        return SIMULATED
    if tokens & OBSERVED_CLAIM_TOKENS:
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

    def render(self) -> str:
        extra = f"; corroborated by {', '.join(self.corroborating)}" if self.corroborating else ""
        split = f"; split={self.split}" if self.split else ""
        return (
            f"{self.path}:{self.line}  {self.field} <- {self.origin_symbol} "
            f"({self.origin_call} at line {self.origin_line}) stamped "
            f'{self.claim_field}="{self.claim_value}" [{self.severity}{split}{extra}]'
            f"\n      {self.snippet}"
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
    #: Names whose taint reaches this record without a nameable field, used by
    #: the frame shape where columns are assigned separately.
    carried: list[str] = field(default_factory=list)


class _ModuleScanner:
    def __init__(self, path: str, source: str, tree: ast.Module) -> None:
        self.path = path
        self.lines = source.splitlines()
        self.tree = tree
        self.parents: dict[int, ast.AST] = {}
        for parent in ast.walk(tree):
            for child in ast.iter_child_nodes(parent):
                self.parents[id(child)] = parent
        self._taint_cache: dict[int, dict[str, Origin]] = {}
        self._findings: list[Finding] = []
        self._seen: set[tuple[int, str, str]] = set()
        self._module_dicts = self._collect_module_dicts()
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
                elif isinstance(sub, (ast.AnnAssign, ast.AugAssign)):
                    pairs = [(self._target_names(sub.target), sub.value)]
                elif isinstance(sub, ast.NamedExpr):
                    pairs = [(self._target_names(sub.target), sub.value)]
                elif isinstance(sub, (ast.For, ast.AsyncFor)):
                    pairs = [(self._target_names(sub.target), sub.iter)]
                elif isinstance(sub, ast.comprehension):
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

    # -- records -----------------------------------------------------------

    def _stamp_from(self, name: str, value: ast.AST) -> Stamp | None:
        if name not in PROVENANCE_FIELDS:
            return None
        if not (isinstance(value, ast.Constant) and isinstance(value.value, str)):
            return None
        text = value.value
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
                else:
                    record.carried.extend(self._target_names(value) or [])
                continue
            if not (isinstance(key, ast.Constant) and isinstance(key.value, str)):
                continue
            name = key.value
            stamp = self._stamp_from(name, value)
            if stamp is not None:
                record.stamps.append(stamp)
                continue
            if name in PROVENANCE_FIELDS:
                continue
            record.data.append((name, value))
        return record

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
                continue
            stamp = self._stamp_from(keyword.arg, keyword.value)
            if stamp is not None:
                record.stamps.append(stamp)
                continue
            if keyword.arg in PROVENANCE_FIELDS:
                continue
            record.data.append((keyword.arg, keyword.value))
        return record

    def _frame_records(self, scope: ast.AST) -> list[_Record]:
        """``df["label_origin"] = "observed_ccc"`` beside a tainted frame.

        The pandas shape: the data goes in when the frame is built and the
        stamp is bolted on afterwards as a column. Nothing about it is one
        expression, so the record has to be assembled from the scope.
        """
        stamps: dict[str, list[Stamp]] = {}
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
            stamp = self._stamp_from(slot.value, sub.value)
            if stamp is None:
                continue
            stamps.setdefault(holder_name, []).append(stamp)
            anchors.setdefault(holder_name, sub)
        out: list[_Record] = []
        for name, found in stamps.items():
            anchor = anchors[name]
            record = _Record(anchor, getattr(anchor, "lineno", 0))
            record.stamps = found
            record.carried = [name]
            out.append(record)
        return out

    # -- adjudication ------------------------------------------------------

    def _adjudicate(self, record: _Record, taint: dict[str, Origin]) -> None:
        claims = [s for s in record.stamps if s.claim is OBSERVED]
        if not claims:
            return
        if any(s.claim is SIMULATED for s in record.stamps):
            # The record declares itself somewhere. Honest, however
            # inconsistently labelled. See the module docstring.
            return

        split = next((s.value for s in record.stamps if s.field in SPLIT_FIELDS), "")
        corroborating = tuple(
            s.render() for s in record.stamps
            if s.claim is not OBSERVED and s.field not in SPLIT_FIELDS
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

        # Report the target field when one is tainted, because that is the
        # aggravated form and the one a reader must see first; otherwise the
        # first tainted input field.
        hits.sort(key=lambda h: (not is_target_field(h[0]), h[0]))
        claim = claims[0]
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
                    severity=TARGET_FABRICATED if is_target_field(name) else INPUT_FABRICATED,
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
                    self._adjudicate(self._record_from_dict(sub), taint)
                elif isinstance(sub, ast.Call):
                    record = self._record_from_call(sub)
                    if record is not None:
                        self._adjudicate(record, taint)
            for record in self._frame_records(scope):
                self._adjudicate(record, taint)
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


def scan_source(source: str, display: str) -> list[Finding]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    return _ModuleScanner(display, source, tree).scan()


def scan_file(path: Path, display: str | None = None) -> list[Finding]:
    """Findings for one Python file. Unreadable or unparseable files yield none."""
    try:
        source = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    return scan_source(source, display or str(path))


def scan_repo(root: Path) -> list[Finding]:
    """Findings across every Python file in a repo."""
    findings: list[Finding] = []
    for path in iter_repo_python_files(root):
        display = str(path.relative_to(root)) if path.is_relative_to(root) else str(path)
        findings.extend(scan_file(path, display))
    findings.sort(key=lambda f: (f.path, f.line, f.field))
    return findings


def count_python_files(roots: Iterable[Path]) -> int:
    return sum(1 for _ in fabrication.iter_python_files(roots, skip=REPO_SKIP_DIRS))
