"""The metric-name universe R10 checks, derived from the ADOPTER (E-038).

THE DEFECT THIS MODULE EXISTS TO CLOSE
--------------------------------------
R10 keyed the question "is this symbol a measured quantity?" on
:data:`resilient_mlkit.core.fabrication.MEASURED_TOKENS` -- a literal list of
words written inside the check. A metric published under any name outside that
list was never checked, and R10 reported PASS having looked at a fraction of
what the repo actually computes.

Measured against ``resilient-surge`` at ``8b71343`` (2026-08-30), the repo's
own ``src/resilient_surge/evaluation/metrics.py`` declares twelve public metric
callables. R10's vocabulary saw eight and was blind to four --
``peak_timing_error``, ``peak_magnitude_error``, ``false_alarm_ratio`` and
``aal_bias``. That boundary is visible in surge's source: in the SAME FILE,
``f1_score``, ``iou`` and ``hit_rate`` raise ``Unmeasured`` on a 0/0
denominator (R10 could see them), while ``false_alarm_ratio`` returns ``0.0``
-- a perfect no-false-alarm score reported from nothing -- on the identical
degeneracy (R10 could not). The repair stopped exactly where the word list
stopped.

Spelling defeats the list too, not only vocabulary: ``csi`` is IN
``MEASURED_TOKENS``, but ``critical_success_index`` tokenises to
``critical/success/index`` and never reaches it.

This is the same failure the ``_declared_panel_parts`` narrowing and the
tick-12 return-type enumeration were: **the guard enumerated what it expected
rather than asking what exists.** The tick-11 router repair fixed its own
instance by flattening the LIVE served surface instead of reading the router
object it expected. This module is that discipline applied statically.

WHAT IS DERIVED, AND FROM WHAT
------------------------------
The adopter's own figure-producing callables ARE its metric registry. A
callable defined in the trees the repo DECLARES under ``[source]`` is a metric
name when at least one of its returns COMPUTES a number from its own
parameters: an arithmetic ``BinOp``, after unwrapping
``float()``/``int()``/``round()``/``abs()``, both arms of a ternary, and one
hop through a local the function bound to such an expression.

Nothing here is a list of names, so no rename evades it and no implementer can
satisfy a control by editing a vocabulary: the universe is regenerated from the
repo's own definitions at drive time. The "computes it" restriction is what
keeps it precise -- ``half_box_deg``, ``stride``, ``seq_len``, ``lat``/``lon``
and ``p50`` are config knobs and payload keys, not callables that derive a
figure, so they never enter.

TWO RESTRICTIONS TRIED AND MEASURED, BOTH REJECTED
--------------------------------------------------
* **Numeric return annotation, required.** The first draft also demanded
  ``-> float``. It is a proxy for "returns a number" and it is defeated by
  DELETING A TYPE HINT: measured against surge's own ``false_alarm_ratio``,
  dropping ``-> float`` took the name out of the registry and R10 went silent
  again. A restriction an implementer can satisfy by deleting one token is the
  same defeat-by-shape this whole line of work exists to close, so it is gone.
  Everything it admitted, the arithmetic rule admits too; the fleet cost of
  dropping it, measured at the adopters' mains, was three further findings
  (surge 14 -> 16, chokepoint 7 -> 8, fray 6 -> 6) and roughly twice the
  registry.
* **Every numeric-leaf key in the repo's committed JSON.** On surge that
  surface held 471 names and produced 28 R10 findings, of which 23 were knobs
  (``half_box_deg``, ``stride``, ``deductible_pct``, ``lat_min``). Recall
  bought at that price is what gets a check turned off.

WHAT STILL EVADES THIS, MEASURED AND PINNED
-------------------------------------------
A computation performed entirely inside a CALL leaves no ``BinOp`` behind:
``return float(np.divide(fp, fp + tp)) if (fp + tp) > 0 else 0.0`` derives no
name, and R10 is silent on a fabricated ``0.0`` at it. Admitting any call would
make every function in a repo a metric, so this is a stated limit rather than a
gap to patch, and it is pinned by
``tests/test_r10_metric_name_universe.py::test_residual_a_metric_computed_inside_a_call_is_still_invisible``
-- which fails the day it closes, so the disclosure gets updated instead of the
silence being re-pinned.

THE ANCHOR
----------
Blind flattening that silently returns nothing is the failure the tick-11
router repair anchored on ``/health`` to prevent: a walk that returns an empty
set looks exactly like a clean repo. The equivalent here is :data:`_PROBE`, a
fixed source string carrying one metric the vocabulary knows and one it does
not. Every call to :func:`derive` runs it through the SAME parse and the SAME
two restrictions the repo's own files go through, and sets
:attr:`MetricRegistry.refusal` if either name fails to come back. A derivation
that has stopped working then says so by name instead of reporting an empty
universe and letting R10 fall back to the word list -- which is E-038.

Anchoring on the probe rather than on "the repo's registry is non-empty" is
deliberate: a small repo that genuinely computes no figure has an empty
registry HONESTLY, and refusing there would make R10 NA on trees it used to
read correctly. Emptiness is disclosed in the evidence and in
``reports/fabricated_defaults.md``; it is not, on its own, a refusal.

The count of derived names the built-in vocabulary ALREADY classifies is
reported as :attr:`MetricRegistry.known` -- measured at the adopters' mains
on 2026-08-30: surge 7 of 48 (8b71343), chokepoint 1 of 60 (52ac929), fray 1
of 24 (89b7d04). Those ratios are E-038 restated as a number: on chokepoint,
fifty-nine of the sixty names the repo computes figures under were outside the
universe R10 was checking.

WHAT A DERIVED-ONLY NAME EARNS
------------------------------
NA, not FAIL. R10's ``satisfies_a_gate`` reads polarity off the vocabulary, so
for a name the vocabulary does not know it cannot say whether the literal is
the value that PASSES the gate -- and ``calculate_payout`` returning ``0.0``
below its trigger is correct domain behaviour, not a fabrication. Silence is
the one answer that is definitely wrong. So a candidate whose only measured
name comes from this registry is emitted with severity
``UNCLASSIFIED_NAME`` and R10 reports NA quoting the names, structurally
distinct from both PASS and FAIL, in the suite's own pattern.
"""

from __future__ import annotations

import ast
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path

from . import fabrication

__all__ = [
    "MetricRegistry",
    "PolarityDeclaration",
    "derive",
    "normalise",
    "polarities_from",
]

#: Arithmetic that turns inputs into a figure. Bit operations and comparisons
#: are deliberately absent: they produce masks and verdicts, not measurements.
_ARITHMETIC = (ast.Div, ast.Sub, ast.Add, ast.Mult, ast.Pow, ast.FloorDiv, ast.Mod)

#: Wrappers that do not change what a return expression IS.
_TRANSPARENT_CALLS: frozenset[str] = frozenset({"float", "int", "round", "abs"})

_NON_ALNUM = re.compile(r"[^0-9a-z]+")

#: The anchor. One name the vocabulary knows (``kge``) and two it does not,
#: written in the three shapes the fleet actually uses -- a plain arithmetic
#: return, a ternary with a degenerate fallback, and a computation assigned to
#: a local and returned on the next line. All three must come back from every
#: derivation or the derivation is not running.
_PROBE = '''
def kge(observed, predicted) -> float:
    return float(predicted / observed)


def qq_anchor_ratio(numerator, denominator):
    return float(numerator / denominator) if denominator else 0.0


def qq_anchor_via_local(numerator, denominator):
    value = numerator / denominator if denominator else 0.0
    return value
'''

#: What :data:`_PROBE` must yield, normalised.
_PROBE_EXPECTED = frozenset({"kge", "qqanchorratio", "qqanchorvialocal"})


def normalise(name: str) -> str:
    """Fold an identifier to its comparison form.

    ``hit_rate``, ``hitRate``, ``HIT_RATE`` and ``_hit_rate`` all fold to
    ``hitrate``. Folding is EXACT-identifier, not token: the registry must not
    inherit the token vocabulary's reach, or ``value`` on a surface would
    capture every ``*_value`` in a codebase.
    """
    return _NON_ALNUM.sub("", name.lower())


@dataclass(frozen=True)
class MetricRegistry:
    """The metric names one adopter declares, by computing them."""

    #: Normalised names, the comparison set.
    names: frozenset[str] = frozenset()
    #: Normalised name -> ``"spelling <- path:line"``, for the evidence.
    origins: Mapping[str, str] = field(default_factory=dict)
    #: Derived names the built-in vocabulary already classifies. The anchor.
    known: frozenset[str] = frozenset()
    #: Derived names the built-in vocabulary has no opinion on. These are the
    #: coverage E-038 was losing.
    unclassified: frozenset[str] = frozenset()
    #: Python files the derivation parsed.
    files: int = 0
    #: Set when the derivation cannot be trusted. NA, never silence.
    refusal: str | None = None

    def contains(self, name: str) -> bool:
        return normalise(name) in self.names

    def origin(self, name: str) -> str | None:
        return self.origins.get(normalise(name))

    def to_dict(self) -> dict[str, object]:
        return {
            "derived_names": len(self.names),
            "vocabulary_known": sorted(self.known),
            "unclassified": sorted(self.unclassified),
            "files_parsed": self.files,
            "refusal": self.refusal,
        }


def _value_expressions(expr: ast.AST) -> Iterable[ast.AST]:
    """The sub-expressions a return actually yields.

    ``float(a / b)`` yields ``a / b``; ``x if p else 0.0`` yields both arms.
    Without the ternary leg, ``return float(fp / (fp + tp)) if (fp + tp) > 0
    else 0.0`` -- surge's false_alarm_ratio, verbatim -- is not recognised as
    computing anything, and the very site E-038 is about stays invisible.
    """
    if (
        isinstance(expr, ast.Call)
        and isinstance(expr.func, ast.Name)
        and expr.func.id in _TRANSPARENT_CALLS
        and expr.args
    ):
        yield from _value_expressions(expr.args[0])
        return
    if isinstance(expr, ast.IfExp):
        yield from _value_expressions(expr.body)
        yield from _value_expressions(expr.orelse)
        return
    yield expr


def _is_path_join(expr: ast.BinOp) -> bool:
    """True when this ``/`` cannot be numeric division (E-M41, defect D2).

    ``pathlib`` spells path joining with the same operator arithmetic uses, so
    ``self.cache_dir / f"{key}.json"`` parses as a ``BinOp(Div)`` and admitted
    ``resilient-chokepoint``'s ``data/ingest/base.py:69 fetch()`` to the metric
    registry -- a cache-file accessor reported as a figure-producing callable.

    The predicate is a TYPE FACT rather than a heuristic about names: dividing
    a number by a string raises ``TypeError``, so a ``/`` with a string literal
    or an f-string on either side is not division. If the line runs at all, it
    is ``Path.__truediv__``.

    Deliberately narrow. ``REPO_ROOT / path``, both sides plain names, is NOT
    caught here and stays a stated limit -- widening it to "an operand whose
    name looks path-ish" would be the spelling rule this whole line of work
    exists to avoid.
    """
    if not isinstance(expr.op, ast.Div):
        return False
    for side in (expr.left, expr.right):
        if isinstance(side, ast.JoinedStr):
            return True
        if isinstance(side, ast.Constant) and isinstance(side.value, str):
            return True
        # ``root / "reports" / name`` parses as ``(root / "reports") / name``:
        # the OUTER node has a Name on both visible sides and only the inner
        # one carries the string. A ``/`` chain rooted in a path join is a path
        # join for its whole length.
        if isinstance(side, ast.BinOp) and _is_path_join(side):
            return True
    return False


def _is_arithmetic(expr: ast.AST) -> bool:
    return any(
        isinstance(e, ast.BinOp)
        and isinstance(e.op, _ARITHMETIC)
        and not _is_path_join(e)
        for e in _value_expressions(expr)
    )


def _own_body(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> Iterable[ast.AST]:
    """Every node belonging to ``fn`` ITSELF, not to a function it defines.

    E-M41, defect D1. ``_computes_a_figure`` used ``ast.walk(fn)``, which
    descends into nested ``def``s and lambdas, so an outer function was
    credited with arithmetic that belongs to an inner one.
    ``resilient-arabica``'s ``scripts/val_predictions_group_interval.py:52
    main(path) -> int`` does no arithmetic in its own body; the ``skill()`` it
    defines does (``1.0 - rm / rq``). That is how the NAME ``main`` entered the
    registry, and how a process exit status at
    ``src/validation/run_validate.py:577`` became an R10 finding.

    Nested functions are still visited as candidates in their OWN right --
    :func:`_names_in` walks every ``FunctionDef`` in the module, nested or not
    -- so scoping here removes the false attribution and not the coverage.

    Scoping ALONE would have cost real recall, and that was measured before it
    was accepted: ``standardized_mean_differences`` (arabica
    ``src/analysis/psm_matching.py:260``) and ``e_value``
    (``src/analysis/sensitivity.py:174``) both put their arithmetic in a nested
    ``_smd`` / ``_e_from_effect`` and RETURN a value built from it. They are
    exactly the domain names E-038 exists to admit. :func:`_delegated_helpers`
    keeps them by looking at the RETURN, which is also what separates them from
    ``main``: ``main`` calls its helper and then returns ``0`` or ``1``.
    """
    stack: list[ast.AST] = list(fn.body)
    while stack:
        node = stack.pop()
        yield node
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            # Its own body is its own; do not descend.
            continue
        stack.extend(ast.iter_child_nodes(node))


def _delegated_helpers(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    """Names of nested functions ``fn`` defines that compute a figure themselves.

    The one-hop delegation rule, symmetric with the existing one-hop through a
    local. ``def e_value(...): def _e_from_effect(effect): return rr + ...;
    return EValueResult(point_e_value=_e_from_effect(estimate), ...)`` is the
    same function as one with the arithmetic inline, and the fleet writes it
    both ways.

    Being CALLED is not enough; the caller has to RETURN what the helper
    produced. That is the whole difference between ``e_value`` and an argparse
    ``main`` that calls a scoring helper and then returns an exit status.
    """
    helpers: set[str] = set()
    for node in fn.body:
        for sub in ast.walk(node):
            if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if _computes_a_figure(sub):
                    helpers.add(sub.name)
    return helpers


def _mentions(expr: ast.AST, helpers: set[str]) -> bool:
    """True when ``expr`` calls one of ``helpers`` anywhere inside itself."""
    if not helpers:
        return False
    for node in ast.walk(expr):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in helpers:
                return True
    return False


def _computes_a_figure(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """True when some return arithmetically derives a number from the inputs.

    One hop through a local is followed, because ``ratio = a / b if b else 0.0;
    return ratio`` is the same function as ``return a / b if b else 0.0`` and
    the fleet writes it both ways. Without the hop, moving the expression onto
    its own line silences the check -- another one-token evasion.
    """
    params = {
        a.arg
        for a in list(fn.args.posonlyargs) + list(fn.args.args) + list(fn.args.kwonlyargs)
    }
    params -= {"self", "cls"}
    if not params:
        # A no-argument callable returns a constant or reads state; either way
        # it is not computing a figure FROM anything this walk can see.
        return False
    helpers = _delegated_helpers(fn)
    derived_locals: set[str] = set()
    for node in _own_body(fn):
        value = getattr(node, "value", None)
        if not isinstance(node, (ast.Assign, ast.AnnAssign)) or value is None:
            continue
        if not (_is_arithmetic(value) or _mentions(value, helpers)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        for target in targets:
            if isinstance(target, ast.Name):
                derived_locals.add(target.id)
    for node in _own_body(fn):
        if not isinstance(node, ast.Return) or node.value is None:
            continue
        if _mentions(node.value, helpers):
            return True
        for expr in _value_expressions(node.value):
            if (
                isinstance(expr, ast.BinOp)
                and isinstance(expr.op, _ARITHMETIC)
                and not _is_path_join(expr)
            ):
                return True
            if isinstance(expr, ast.Name) and expr.id in derived_locals:
                return True
    return False


def _names_in(source: str, display: str) -> dict[str, str]:
    """The metric names one module declares. The single derivation path.

    The probe and the repo's own files go through THIS function, so an anchor
    that passes cannot be evidence about a different code path.
    """
    out: dict[str, str] = {}
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return out
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.name.startswith("test") or node.name.startswith("__"):
            continue
        if not _computes_a_figure(node):
            continue
        key = normalise(node.name)
        if key and key not in out:
            out[key] = f"{node.name} <- {display}:{node.lineno}"
    return out


def _anchor_failure() -> str | None:
    """Run :data:`_PROBE` through the real derivation. None when it is alive."""
    recovered = set(_names_in(_PROBE, "<anchor>"))
    missing = _PROBE_EXPECTED - recovered
    if not missing:
        return None
    return (
        "the metric-registry derivation is not running: its own anchor probe "
        f"lost {', '.join(sorted(missing))}. Every name R10 would have checked "
        "beyond its built-in word list is therefore unmeasured, and a PASS here "
        "would be the word list reporting on itself -- which is E-038"
    )


def derive(roots: Iterable[Path], base: Path | None = None) -> MetricRegistry:
    """Derive one adopter's metric-name universe from its own source.

    ``roots`` are the trees the repo declares under ``[source]`` -- the same
    ones R10 walks, deliberately, so that the registry and the scan cannot
    disagree about what this repo's source is.
    """
    roots = list(roots)
    origins: dict[str, str] = {}
    files = 0
    for path in fabrication.iter_python_files(roots):
        files += 1
        display = str(path)
        if base is not None and path.is_relative_to(base):
            display = str(path.relative_to(base))
        for key, origin in _names_in(
            path.read_text(encoding="utf-8", errors="replace"), display
        ).items():
            origins.setdefault(key, origin)

    names = frozenset(origins)
    known = frozenset(n for n in names if fabrication.is_measured_name(n))
    refusal = _anchor_failure()
    return MetricRegistry(
        names=names,
        origins=origins,
        known=known,
        unclassified=names - known,
        files=files,
        refusal=refusal,
    )


# ---------------------------------------------------------------------------
# The adopter's declared polarities (E-M41)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PolarityDeclaration:
    """What one adopter declares under ``[metrics]`` in ``.mlkit/repo.toml``.

    THE PROBLEM IT SOLVES. ``satisfies_a_gate`` reads polarity off mlkit's
    built-in word list, so for a domain name the repo defines by computing it,
    R10 cannot say whether a literal is the value that PASSES the gate or one
    that would fail it. It asserts neither, the row is ``UNCLASSIFIED_NAME``,
    and R10 renders NA. Measured on ``resilient-arabica`` ``2a65d9a5``, five of
    the 163 names it computes figures under are in mlkit's vocabulary; the
    other 158 are not, and every residual R10 finding there sits at one of
    them. NA is the honest answer and it is not a good resting place.

    WHY A DECLARATION AND NOT A GUESS. The alternative was a fourth severity
    for "a degenerate-input guard whose value is the mathematically defined
    answer" — and separating that from an absent-value default means deciding
    whether ``if not matched:`` tests absence or degeneracy, which is the same
    syntax wearing two meanings. A severity mlkit guesses wrong is worse than
    an NA it declines honestly. Asking the repo reaches the subset that matters
    from the other side, and the answer is a line a reviewer reads in a diff.

    WHY IT CANNOT BE USED TO GO GREEN. There are exactly three values and none
    of them is "not a metric". A declaration can only turn an
    ``UNCLASSIFIED_NAME`` row (NA) into ``SATISFIES_GATE`` or
    ``PUBLISHES_UNMEASURED`` (FAIL). It cannot remove a row, it cannot silence
    a name, and it cannot reach a name mlkit's own vocabulary already judges —
    so no repo can re-aim ``rmse``. Declaring is monotone toward strictness,
    which is why it does not need the committed-bytes treatment a
    verdict-loosening declaration would.

    An unrecognised value is IGNORED rather than accepted, and named in
    :attr:`refused`, so a typo leaves the row NA instead of quietly adjudicating
    it in whichever direction the typo happened to fall near.
    """

    #: Normalised name -> one of ``fabrication.DECLARED_POLARITIES``.
    directions: Mapping[str, str] = field(default_factory=dict)
    #: ``"name = value"`` for every entry that was not one of the three.
    refused: tuple[str, ...] = ()

    def polarity(self, name: str) -> str | None:
        return self.directions.get(normalise(name))

    def to_dict(self) -> dict[str, object]:
        return {
            "declared": len(self.directions),
            "names": sorted(self.directions),
            "refused": list(self.refused),
        }


def polarities_from(config: Mapping[str, object]) -> PolarityDeclaration:
    """Read ``[metrics]`` out of one repo's parsed ``.mlkit/repo.toml``.

    An absent table gives an empty declaration, which changes nothing: every
    row that was ``UNCLASSIFIED_NAME`` stays ``UNCLASSIFIED_NAME``.
    """
    table = config.get("metrics")
    if not isinstance(table, Mapping):
        return PolarityDeclaration()
    directions: dict[str, str] = {}
    refused: list[str] = []
    for name, value in table.items():
        key = normalise(str(name))
        text = str(value).strip().lower()
        if not key:
            continue
        if text in fabrication.DECLARED_POLARITIES:
            directions[key] = text
        else:
            refused.append(f"{name} = {value!r}")
    return PolarityDeclaration(directions=directions, refused=tuple(sorted(refused)))
