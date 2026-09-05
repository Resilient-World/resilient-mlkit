"""What a binding READS, declared — and what a merged tree can therefore drive.

WHY THIS EXISTS (the v3 adjudicator's second finding, 2026-09-05)
-----------------------------------------------------------------
``core.merged.checkout`` puts a synthetic merge commit into a temporary
detached worktree. That worktree holds **committed content only**: no
gitignored staged panel travels with it, because no gitignored file is in any
tree object. ``merged.py``'s own docstring says so.

The consequence was disclosed there and nowhere else, and it is the whole of
this module's reason to exist. Every data-bearing check in the fleet —
chokepoint D2/D6/E1, fray D2/D3/D6/E1, torrent D2/E1 — resolves a binding that
reads a panel the repo gitignores. Driven through ``mlkit check
--merged-with``, those bindings reach a byte that is not there, raise an
ordinary exception, and ``cli._run_phase``'s generic handler renders **FAIL**
with "check raised an unhandled exception" — or, for torrent's D2, FAIL with
"ENVIRONMENT REFUSAL, NOT A PLACEBO FINDING" in the text. Either way a table
reader, and every downstream artifact, sees a **verdict** where there was an
**environment**. That is exactly the conflation ``Status.UNMEASURABLE`` (M-1)
was added to end, reappearing inside the tool that was supposed to end it.

It is not hypothetical. fray #115 landed an artifact recording that a
promotion-gate re-run was NOT identical, when the re-run's inputs were absent
and it had measured nothing: an environment failure written down as a finding.

WHAT A REPO DECLARES
--------------------
An optional ``[inputs]`` table in ``.mlkit/repo.toml``, keyed by BINDING NAME,
whose value is the list of repo-relative paths that binding reads and that are
not necessarily in the tree::

    [inputs]
    placebo_test  = ["data/cache/nass_yields.json"]
    scaling_probe = ["data/cache/nass_yields.json"]
    coverage      = []   # reads nothing outside the committed tree

An **empty list is a positive declaration**, not an absence: it says "this
binding needs nothing this tree might be missing", and the check runs. That is
the distinction ``core.declaration`` had to make for ``[placebo]`` and it is
the same one here — "declared nothing" and "declared that it needs nothing"
are opposite answers.

WHY THE UNDECLARED CASE ALSO REFUSES
------------------------------------
On a merged-tree drive, a binding with **no** declaration renders UNMEASURABLE
too. This is the fail-closed direction and it is deliberate:

* the tree being driven provably holds committed content only;
* whether a binding needs more than that is a fact only the repo knows;
* so with no declaration mlkit cannot establish that the input is present —
  and an input that has not been established may be rendered as *unmeasured*,
  never as a verdict. A guess in the other direction is what produced the FAIL
  rows above.

It costs nothing that was working: ``--merged-with`` is new in this stack and
has never landed, so no existing verdict moves, and a repo buys the precise
per-binding answer with three lines of TOML. The guard is armed **only** on a
merged-tree drive (``Repo.require_declared_inputs``); a plain drive resolves
bindings exactly as it did before this module existed.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from .result import InputUnavailable

if TYPE_CHECKING:  # pragma: no cover - typing only
    from .repo import Repo

__all__ = [
    "INPUTS_SECTION",
    "absent",
    "declared",
    "guard",
]

#: The optional table of ``.mlkit/repo.toml``. One constant; two spellings of
#: a section name is how two readers come to disagree about what was declared.
INPUTS_SECTION = "inputs"

#: Appended to every refusal so the reason carries its own remedy.
_RECIPE = (
    "Declare what this binding reads in the [inputs] table of "
    ".mlkit/repo.toml, keyed by binding name, as repo-relative paths "
    "(an empty list declares that it reads nothing outside the committed "
    "tree). Then either commit those inputs or accept UNMEASURABLE here: a "
    "merged worktree is built from tree objects and cannot carry a "
    "gitignored file"
)


def declared(repo: Repo, binding: str) -> list[str] | None:
    """The paths ``binding`` declares, or ``None`` when it declares nothing.

    ``[]`` and ``None`` are different answers and the caller must keep them
    apart: ``[]`` is "declared, needs nothing"; ``None`` is "not declared".

    A malformed table answers ``None`` rather than raising. The caller's
    ``None`` branch REFUSES, so a repo cannot reach a looser outcome by
    breaking this file — the same one-way property ``core.declaration`` has.
    """
    from .repo import BindingError

    try:
        config = repo.config()
    except BindingError:
        return None
    table = config.get(INPUTS_SECTION)
    if not isinstance(table, dict) or binding not in table:
        return None
    value = table[binding]
    if isinstance(value, str) or not isinstance(value, (list, tuple)):
        return None
    if not all(isinstance(p, str) and p for p in value):
        return None
    return [str(p) for p in value]


def absent(repo: Repo, paths: list[str]) -> list[str]:
    """Which declared paths this tree does not carry, in declared order.

    An absolute path, or one that climbs out of the repo, counts as absent and
    is named as such: a declaration mlkit cannot resolve against the tree it is
    driving has not established anything about that tree.
    """
    missing: list[str] = []
    root = Path(repo.path).resolve()
    for rel in paths:
        candidate = Path(rel)
        if candidate.is_absolute():
            missing.append(rel)
            continue
        target = (root / candidate).resolve()
        if not target.is_relative_to(root) or not target.exists():
            missing.append(rel)
    return missing


def guard(repo: Repo, binding: str) -> None:
    """Raise :class:`InputUnavailable` unless this tree can drive ``binding``.

    Called from ``Repo.resolve`` and only when ``repo.require_declared_inputs``
    is set — which ``mlkit check --merged-with`` sets on the temporary worktree
    it drives, and nothing else sets. Raised BEFORE the binding's module is
    imported, and by mlkit rather than by the subject, so it is not a
    ``PrematureInputRefusal``: the declaration mlkit resolved is the repo's own
    ``[inputs]`` table, and what it stopped at is a path this tree does not
    hold.
    """
    paths = declared(repo, binding)
    if paths is None:
        raise InputUnavailable(
            f"{repo.name}: binding '{binding}' declares no inputs, and this drive is "
            f"over a MERGED WORKTREE, which holds committed content only. mlkit "
            f"cannot establish that '{binding}' can read what it reads here, and an "
            f"input it has not established may not be rendered as a verdict. "
            f"{_RECIPE}",
            input=f"[{INPUTS_SECTION}].{binding} (undeclared)",
            evidence={
                "binding": binding,
                "inputs_declared": None,
                "drive": "merged-worktree",
                "committed_content_only": True,
            },
        )
    missing = absent(repo, paths)
    if missing:
        raise InputUnavailable(
            f"{repo.name}: binding '{binding}' declares {len(paths)} input(s) and "
            f"this MERGED WORKTREE does not carry {len(missing)} of them: "
            + ", ".join(missing[:6])
            + (f" (+{len(missing) - 6} more)" if len(missing) > 6 else "")
            + f". {_RECIPE}",
            input=missing[0],
            evidence={
                "binding": binding,
                "inputs_declared": list(paths),
                "inputs_absent": missing,
                "drive": "merged-worktree",
                "committed_content_only": True,
            },
        )
