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

TWO PROBES, BECAUSE ONE OF THEM HAS A HOLE
------------------------------------------
``probe()`` imports the declared bindings and is available BEFORE any check
runs. It has a blind spot, and the blind spot is not hypothetical: bindings in
this portfolio import their repo LAZILY, inside the function body, because
that is the pattern ``.mlkit/repo.toml`` documents and it is right -- it keeps
a repo's heavy training stack out of the import path of checks that do not
need it. A lazily-importing binding module imports perfectly from an
interpreter with no numpy, and only fails when it is CALLED.

Measured, 2026-08-28, running ``mlkit env`` from a python 3.14.6 with no
numpy: seven of the eight repos reported UNMEASURABLE on the import probe and
resilient-surge reported MEASURABLE, 11 of 11 bindings imported -- from the
very interpreter that cannot run any of them. The import probe alone would
have left surge's report unguarded.

``from_results()`` closes it, using evidence that costs nothing extra: the
check results already produced in this run. A check whose reason carries
``No module named 'X'`` for an X that is not this repo's own source is a
binding that was called and could not run. That is stronger evidence than the
import probe, because it is what actually happened rather than what might.
``assess()`` runs both and takes the worse verdict; no binding is ever called
just to find out.

WHAT A VERDICT DOES AND DOES NOT AUTHORISE
------------------------------------------
UNMEASURABLE stops a binding-dependent report from being written. It does not
turn a FAIL into a pass, it does not suppress any check result, and it is not
itself a check -- there is no ``R`` number for it, because the portfolio's
terminal state must never depend on which shell someone happened to use. It is
a property of the run, and it belongs in the run's own record.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field

from .repo import BindingError, Repo

#: Python's own wording for a module it could not find, and the only thing
#: ``from_results`` keys on. It is stable across every version this tool runs
#: on and it survives being wrapped in mlkit's own "binding raised ..." text.
_MISSING_MODULE = re.compile(r"No module named ['\"]([A-Za-z_][\w.]*)['\"]")

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
        declared = dict(repo.config().get("bindings") or {})
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


def from_results(repo: Repo, results: Mapping[str, object]) -> EnvironmentProbe:
    """Read the environment's verdict off the checks that already ran.

    The import probe cannot see a lazily-importing binding fail, because such a
    binding imports fine and only breaks when called. This one does not need to
    call anything: a check that already ran and reported ``No module named
    'numpy'`` has performed the experiment.

    The same discriminator applies -- a missing module that resolves inside the
    repo is the REPO's defect and leaves the environment MEASURABLE. Without
    that, an ordinary ``from src.models import x`` typo would suppress the
    report it should have turned red.
    """
    import sys

    python = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    missing: list[str] = []
    culprits: dict[str, str] = {}
    local: list[str] = []
    for check_id, result in results.items():
        reason = getattr(result, "reason", "") or ""
        for module in _MISSING_MODULE.findall(reason):
            if _is_repo_local(repo, module):
                if check_id not in local:
                    local.append(str(check_id))
                continue
            if module not in missing:
                missing.append(module)
            culprits.setdefault(f"{check_id} (called)", f"missing:{module}")

    if missing:
        return EnvironmentProbe(
            UNMEASURABLE,
            f"this interpreter (python {python}) ran {len(culprits)} check(s) that "
            f"failed for want of " + ", ".join(missing[:5])
            + ", which is not this repo's own source; the checks were called and "
            "could not run, so what they reported is a fact about the interpreter",
            culprits,
            tuple(missing),
            tuple(local),
            python,
        )
    return EnvironmentProbe(
        UNDECLARED,
        f"no check in this run failed for a missing third-party module "
        f"({len(results)} result(s) read)",
        {},
        (),
        tuple(local),
        python,
    )


def assess(repo: Repo, results: Mapping[str, object] | None = None) -> EnvironmentProbe:
    """The environment verdict for a run: both probes, worse verdict wins.

    UNMEASURABLE from either is UNMEASURABLE. The import probe answers before
    anything has run; the results probe sees what a lazily-importing binding
    did when it was actually called. Neither calls a binding to find out.
    """
    imported = probe(repo)
    if imported.verdict == UNMEASURABLE or not results:
        return imported
    observed = from_results(repo, results)
    if observed.verdict != UNMEASURABLE:
        return imported
    merged = dict(imported.bindings)
    merged.update(observed.bindings)
    return EnvironmentProbe(
        UNMEASURABLE,
        observed.reason
        + f" (every declared binding IMPORTED cleanly here, which is why the "
        f"import probe alone said {imported.verdict}: these bindings import "
        "their repo lazily and fail only when called)",
        merged,
        observed.missing_modules,
        tuple(dict.fromkeys(imported.repo_defects + observed.repo_defects)),
        observed.python,
    )
