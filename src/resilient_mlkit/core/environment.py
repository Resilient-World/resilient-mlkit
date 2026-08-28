"""Is this interpreter capable of measuring this repo at all?

WHY THIS EXISTS
---------------
On 2026-08-2x a Python 3.14 interpreter with no numpy installed was used to run
``mlkit`` against at least four repos. Every binding-dependent check raised
``ModuleNotFoundError: No module named 'numpy'``, every one of those was
correctly recorded as a failure of its check -- and then R8 dutifully wrote
``reports/readiness.md`` out of them, overwriting reports whose PASSes had been
measured by a working interpreter. The measurement was not merely lost; it was
replaced by something that looked exactly like a measurement. See
resilient-chokepoint ``docs/ESCALATIONS.md`` E-019.

The fact the instrument was missing is this:

    "This environment cannot measure this repo" is a DIFFERENT FACT from
    "this repo failed". They have different causes, different fixes, and
    different consequences -- and only one of them is a statement about the
    repo. A tool that renders them identically will overwrite the second with
    the first every time somebody runs it from the wrong shell.

THE RULE, AND WHAT MAKES IT MECHANICAL
--------------------------------------
A binding failing to import is not on its own evidence of a broken
environment. ``ImportError: cannot import name 'load_panel' from src.data`` is
a defect IN THE REPO and must stay a FAIL -- suppressing it as "environment
unmeasurable" would be the same overwrite in the opposite direction, and a
strictly worse one because it hides a real defect behind an excuse.

The discriminator is the missing module's own name, and it is decidable
without importing anything:

    ModuleNotFoundError names a top-level module. If that module resolves to
    a path INSIDE the repo (``<repo>/<name>``, ``<repo>/src/<name>``, or the
    matching ``.py``), the repo cannot import its own source: a REPO DEFECT.
    If it does not, the interpreter is missing a third-party dependency the
    repo declares: an UNMEASURABLE ENVIRONMENT.

``numpy`` is not a directory in resilient-chokepoint, so its absence is the
interpreter's problem. ``src.data`` is, so its absence is the repo's. Nothing
here needs a hardcoded list of "real" packages, which is what keeps the rule
from rotting.

WHAT A VERDICT DOES AND DOES NOT AUTHORISE
------------------------------------------
UNMEASURABLE stops a binding-dependent report from being written. It does not
turn a FAIL into a pass, it does not suppress any check result, and it is not
itself a check -- there is no ``R`` number for it, because the portfolio's
terminal state must never depend on which shell someone happened to use. It is
a property of the run, and it belongs in the run's own record.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .repo import BindingError, Repo

#: The environment imported every binding the repo declares.
MEASURABLE = "MEASURABLE"
#: At least one binding could not be imported because a module that is NOT
#: this repo's own source is missing from the interpreter.
UNMEASURABLE = "UNMEASURABLE"
#: The repo declares no bindings, so there is nothing to import and nothing to
#: conclude. Distinct from MEASURABLE: an unwired repo has not demonstrated
#: that this interpreter can measure it, it has only declined to try.
UNDECLARED = "UNDECLARED"


@dataclass(frozen=True)
class EnvironmentProbe:
    """What this interpreter can and cannot import from one repo."""

    verdict: str
    reason: str
    #: binding name -> "ok" | "missing:<module>" | "repo-defect:<detail>" | ...
    bindings: dict[str, str] = field(default_factory=dict)
    #: Third-party modules absent from this interpreter, deduplicated.
    missing_modules: tuple[str, ...] = ()
    #: Bindings whose import failed for a reason that is the REPO's defect.
    repo_defects: tuple[str, ...] = ()
    python: str = ""

    @property
    def measurable(self) -> bool:
        """True when a binding-dependent report may be written from this run.

        UNDECLARED counts as writable. A repo with no bindings produces a
        report made entirely of "binding not declared" NAs, and those are
        measured facts about the repo that a working interpreter and a broken
        one agree on.
        """
        return self.verdict != UNMEASURABLE

    def to_dict(self) -> dict[str, object]:
        return {
            "verdict": self.verdict,
            "reason": self.reason,
            "bindings": dict(self.bindings),
            "missing_modules": list(self.missing_modules),
            "repo_defects": list(self.repo_defects),
            "python": self.python,
        }


def _is_repo_local(repo: Repo, module: str) -> bool:
    """True when ``module``'s top-level name is this repo's own source."""
    top = (module or "").split(".")[0]
    if not top:
        return False
    for base in (repo.path, repo.path / "src"):
        if (base / top).is_dir() or (base / f"{top}.py").is_file():
            return True
    return False


def probe(repo: Repo) -> EnvironmentProbe:
    """Try to import every binding the repo declares, and adjudicate why not.

    Imports only. No binding is CALLED, because calling one can hit a network,
    a credential or a GPU, and the question here is narrower than any of
    those: can this interpreter load this repo's code at all.

    Modules imported by the probe are left in ``sys.modules`` deliberately:
    the caller's per-repo ``Repo.release()`` owns eviction, and evicting here
    would drop modules checks running in the same phase still hold.
    """
    import sys

    python = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    try:
        declared = dict((repo.config().get("bindings") or {}))
    except BindingError as exc:
        return EnvironmentProbe(
            UNDECLARED, f"cannot read binding declarations: {exc}", python=python
        )

    if not declared:
        return EnvironmentProbe(
            UNDECLARED,
            "no bindings declared in .mlkit/repo.toml; this interpreter has not "
            "been asked to import anything from the repo, so its ability to "
            "measure it is unknown rather than confirmed",
            python=python,
        )

    statuses: dict[str, str] = {}
    missing: list[str] = []
    defects: list[str] = []
    for name in sorted(declared):
        try:
            repo.resolve(name)
        except BindingError as exc:
            cause = exc.__cause__
            module = getattr(cause, "name", None) if isinstance(cause, ImportError) else None
            if module and not _is_repo_local(repo, module):
                statuses[name] = f"missing:{module}"
                if module not in missing:
                    missing.append(module)
            else:
                detail = f"{type(cause).__name__}: {cause}" if cause else str(exc)
                statuses[name] = f"repo-defect:{detail[:120]}"
                defects.append(name)
        except Exception as exc:  # noqa: BLE001 - anything else is the repo's
            statuses[name] = f"repo-defect:{type(exc).__name__}: {exc}"[:140]
            defects.append(name)
        else:
            statuses[name] = "ok"

    if missing:
        return EnvironmentProbe(
            UNMEASURABLE,
            f"this interpreter (python {python}) cannot import "
            + ", ".join(missing[:5])
            + f", which {len(missing) == 1 and 'is' or 'are'} not this repo's own source; "
            f"{sum(1 for v in statuses.values() if v.startswith('missing:'))} of "
            f"{len(declared)} binding(s) are unimportable here",
            statuses,
            tuple(missing),
            tuple(defects),
            python,
        )
    return EnvironmentProbe(
        MEASURABLE,
        f"python {python} imported all {len(declared)} declared binding(s)"
        + (f"; {len(defects)} raised a repo-side error" if defects else ""),
        statuses,
        (),
        tuple(defects),
        python,
    )
