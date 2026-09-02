#!/bin/bash
# The same control pair through `mlkit check` itself, not through the library.
#
# Three throwaway checkouts under a scratch root. `choco` and `fray` carry
# IDENTICAL bindings and identical numbers -- fray's own measured placebo and
# scaling curve -- and differ only in that fray commits a [placebo]/[scaling]
# declaration. `surge` carries fray's declaration over a placebo that BEATS the
# floor and a curve flat across the declared top step: the not-dead arm.
#
# `mlkit check --phase decision|economics` is what an adopter runs and what the
# readiness tables are generated from; a hard stop that fires in pytest and not
# here has not fired where it matters.
set -u
# Derived, never hardcoded: a driver naming one machine's checkout is evidence
# about that machine. VENV may be overridden to pin the interpreter.
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="${VENV:-python3}"
SRC="$HERE/src"
ROOT="${ROOT:-${TMPDIR:-/tmp}/mlkit-d2e1-cli-drive}"

rm -rf "$ROOT"
mkdir -p "$ROOT/resilient-fray/.mlkit" "$ROOT/resilient-choco/.mlkit" \
         "$ROOT/resilient-surge/.mlkit"

BIND='def placebo_test():
    return {"estimate": -62.572, "ci_low": -71.998, "ci_high": -53.146,
            "reference_effect": 22.81138510740044, "run_id": "fray-placebo"}


def scaling_probe():
    return {0.05: -170.0, 0.10: -151.29137, 0.25: -138.13969}
'
BIND_LEAK='def placebo_test():
    """The SAME estimand, a placebo that BEATS the floor. This is leakage."""
    return {"estimate": 17.0, "ci_low": 8.0, "ci_high": 26.0,
            "reference_effect": 22.81138510740044, "run_id": "fray-placebo-leak"}


def scaling_probe():
    """The SAME ladder, the top step buying a quarter of a percent."""
    return {0.05: -170.0, 0.10: -151.29137, 0.25: -151.29137 * 0.9975}
'
BINDINGS='[bindings]
placebo_test = "fray_bindings:placebo_test"
scaling_probe = "fray_bindings:scaling_probe"
'
DECL='
[placebo]
estimand = "skill against the persistence floor, lb/ac"
null_value = 0.0
indicts = "above"

[scaling]
fractions = [0.05, 0.10, 0.25]
'

# choco = the UNDECLARED arm. fray = the DECLARED arm. Same bindings, same
# numbers, same commit; the declaration is the only difference between them.
printf '%s' "$BIND" > "$ROOT/resilient-choco/fray_bindings.py"
printf '[repo]\nname = "choco"\n\n%s' "$BINDINGS" > "$ROOT/resilient-choco/.mlkit/repo.toml"
printf '%s' "$BIND" > "$ROOT/resilient-fray/fray_bindings.py"
printf '[repo]\nname = "fray"\n\n%s%s' "$BINDINGS" "$DECL" > "$ROOT/resilient-fray/.mlkit/repo.toml"
printf '%s' "$BIND_LEAK" > "$ROOT/resilient-surge/fray_bindings.py"
printf '[repo]\nname = "surge"\n\n%s%s' "$BINDINGS" "$DECL" > "$ROOT/resilient-surge/.mlkit/repo.toml"

for r in fray choco surge; do
  git -C "$ROOT/resilient-$r" init -q
  git -C "$ROOT/resilient-$r" config user.email t@example.invalid
  git -C "$ROOT/resilient-$r" config user.name t
  git -C "$ROOT/resilient-$r" add -A
  git -C "$ROOT/resilient-$r" commit -qm fixture
done

PYTHONPATH="$SRC" "$VENV" -c "
import resilient_mlkit, resilient_mlkit.checks.decision as d, resilient_mlkit.checks.economics as e
print('MODULE', resilient_mlkit.__file__)
print('MODULE', d.__file__)
print('MODULE', e.__file__)
assert resilient_mlkit.__file__.startswith('$SRC'), resilient_mlkit.__file__
"

for phase in decision economics; do
  echo
  echo "=== mlkit check --phase $phase --root $ROOT ==="
  PYTHONPATH="$SRC" "$VENV" -m resilient_mlkit.cli check --phase "$phase" --root "$ROOT" --repo choco,fray,surge
  echo "exit=$?"
done
