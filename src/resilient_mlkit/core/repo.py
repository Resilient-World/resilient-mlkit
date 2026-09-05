"""Repo discovery and the binding contract.

mlkit does not guess at a model repo's internals. Eight repos grew separately
and none of them agree on where a dataloader lives, so any attempt to
introspect them generically would either be wrong or would quietly degrade
into a check that passes because it found nothing to test.

Instead each repo declares a small adapter in ``.mlkit/repo.toml`` pointing at
callables in its own source tree. mlkit imports those inside the repo's own
environment. A binding that is absent makes the dependent check NA with a
reason -- never a pass.
"""

from __future__ import annotations

import functools
import importlib
import subprocess
import sys
import tomllib
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .result import InputUnavailable, PrematureInputRefusal

#: The eight avoided-loss model repos, in the portfolio's canonical order.
PORTFOLIO = (
    "choco",
    "arabica",
    "fray",
    "torrent",
    "chokepoint",
    "surge",
    "triage",
    "blackout",
)


class BindingError(RuntimeError):
    """A declared binding could not be imported or is malformed."""


@dataclass
class Repo:
    """One model repo on disk."""

    name: str
    path: Path
    #: Modules imported from inside this repo, accumulated across binding
    #: imports and binding calls, evicted together in release().
    _imported: set[str] = field(default_factory=set, repr=False, compare=False)

    # -- git ---------------------------------------------------------------

    def _git(self, *args: str) -> str:
        out = subprocess.run(
            ["git", "-C", str(self.path), *args],
            capture_output=True,
            text=True,
            check=False,
        )
        return out.stdout.strip() if out.returncode == 0 else ""

    @property
    def git_sha(self) -> str:
        """Full HEAD SHA, or "" if this is not a git worktree."""
        return self._git("rev-parse", "HEAD")

    @property
    def short_sha(self) -> str:
        return self.git_sha[:7]

    @property
    def branch(self) -> str:
        return self._git("rev-parse", "--abbrev-ref", "HEAD")

    @property
    def is_dirty(self) -> bool:
        return bool(self._git("status", "--porcelain"))

    # -- bindings ----------------------------------------------------------

    @property
    def config_path(self) -> Path:
        return self.path / ".mlkit" / "repo.toml"

    def config(self) -> dict[str, Any]:
        """Parsed ``.mlkit/repo.toml``, or {} when the repo has not declared one."""
        p = self.config_path
        if not p.is_file():
            return {}
        try:
            with p.open("rb") as fh:
                return tomllib.load(fh)
        except tomllib.TOMLDecodeError as exc:
            raise BindingError(f"{self.name}: malformed .mlkit/repo.toml: {exc}") from exc

    def binding(self, name: str) -> str | None:
        """Return the raw ``module:callable`` string for a binding, if declared."""
        return (self.config().get("bindings") or {}).get(name)

    def resolve(self, name: str) -> Callable[..., Any]:
        """Import and return a declared binding.

        Raises BindingError rather than returning a stub. A check that cannot
        resolve its binding must report NA, and it needs the reason text that
        this exception carries.
        """
        spec = self.binding(name)
        if not spec:
            raise BindingError(
                f"{self.name}: no '{name}' binding declared in .mlkit/repo.toml"
            )
        if ":" not in spec:
            raise BindingError(
                f"{self.name}: binding '{name}' must be 'module.path:callable', got {spec!r}"
            )
        module_name, _, attr = spec.partition(":")

        # The repo's own source must win over anything already importable, so
        # that we test this checkout rather than a wheel installed elsewhere.
        added = []
        for candidate in (self.path, self.path / "src"):
            if candidate.is_dir() and str(candidate) not in sys.path:
                sys.path.insert(0, str(candidate))
                added.append(str(candidate))

        before = set(sys.modules)
        try:
            module = importlib.import_module(module_name)
        except InputUnavailable as exc:
            # Refused BY NAME, and not as a BindingError: a BindingError renders
            # NA ("no binding declared"), and an InputUnavailable raised while
            # the module is still being imported has not resolved anything --
            # it has not read a pin, it has not reached a byte, it has only
            # declined to be checked. The CredentialRequired discipline says
            # raise only at the boundary; this is the same rule for bytes.
            raise PrematureInputRefusal(
                f"PREMATURE_INPUT_REFUSAL: {self.name}: '{module_name}' raised "
                f"InputUnavailable while being IMPORTED for binding '{name}' "
                f"({exc}). UNMEASURABLE is for a binding that resolved its "
                "declaration and stopped at the byte it cannot read; a module "
                "that refuses before it has resolved anything has dodged the "
                "check, and that renders FAIL"
            ) from exc
        except Exception as exc:
            raise BindingError(
                f"{self.name}: importing '{module_name}' for binding '{name}' "
                f"raised {type(exc).__name__}: {exc}"
            ) from exc
        finally:
            for entry in added:
                if entry in sys.path:
                    sys.path.remove(entry)
        self._imported |= set(sys.modules) - before

        fn = getattr(module, attr, None)
        if fn is None:
            raise BindingError(
                f"{self.name}: '{module_name}' has no attribute '{attr}' "
                f"(binding '{name}')"
            )
        if not callable(fn):
            raise BindingError(
                f"{self.name}: binding '{name}' resolved to a non-callable {type(fn).__name__}"
            )

        # Bindings import their repo LAZILY, inside the function body -- that is
        # the pattern .mlkit/repo.toml documents, and it is right, because it
        # keeps a repo's heavy training stack out of the import path of checks
        # that do not need it. But it means sys.path must be live when the
        # binding is CALLED, not merely when its module was imported. Tearing
        # the path down at import time made every lazily-importing binding fail
        # with ModuleNotFoundError against its own package.
        return self._with_import_path(fn)

    def _with_import_path(self, fn: Callable[..., Any]) -> Callable[..., Any]:
        """Wrap a binding so this repo is importable for the duration of the call."""

        @functools.wraps(fn)
        def wrapper(*a: Any, **kw: Any) -> Any:
            added = []
            for candidate in (self.path, self.path / "src"):
                if candidate.is_dir() and str(candidate) not in sys.path:
                    sys.path.insert(0, str(candidate))
                    added.append(str(candidate))
            before = set(sys.modules)
            try:
                return fn(*a, **kw)
            finally:
                self._imported |= set(sys.modules) - before
                for entry in added:
                    if entry in sys.path:
                        sys.path.remove(entry)

        return wrapper

    def release(self) -> None:
        """Evict this repo's modules once we are finished with it.

        Every repo names its adapter ``mlkit_bindings``, so without this the
        second repo probed in one process would be served the FIRST repo's
        cached module and report its numbers as its own -- a confident PASS
        about a repo never opened. Eviction has to happen at the repo boundary
        rather than after each import, because bindings import lazily and their
        modules are not all loaded until the last binding has run.
        """
        self._evict_repo_modules(set(sys.modules) - self._imported)
        self._imported.clear()
        # Eviction drops entries from sys.modules but leaves importlib's finder
        # cache stale. A second binding module in the same directory then raises
        # ModuleNotFoundError until the cache is cleared — see
        # tests/test_economics_controls.py (two _run_e1 calls, one tmp_path).
        importlib.invalidate_caches()

    #: Path fragments marking installed dependencies rather than repo source.
    #: Several repos keep their virtualenv inside the checkout, so "lives under
    #: the repo root" alone would also match torch and numpy -- and evicting a
    #: C-extension module makes re-import fail outright with "cannot load module
    #: more than once per process".
    _VENDOR_MARKERS = ("site-packages", "dist-packages", "/.venv/", "/venv/")

    def _evict_repo_modules(self, before: set[str]) -> None:
        """Drop newly-imported modules that are this repo's own source.

        Origins are resolved for EVERY candidate before anything is deleted.
        A namespace package (a repo subpackage with no ``__init__.py``, which
        several of these repos have) carries a lazy ``_NamespacePath`` whose
        ``__path__`` is recomputed from ``sys.modules[<parent>].__path__`` on
        access. Deleting as we iterate can drop the parent first, and the next
        child's ``__path__`` then raises ``KeyError`` on the parent's name --
        which aborted the whole run inside ``release()``, before any results
        were printed. Two passes make eviction order-independent.
        """
        root = str(self.path.resolve())
        victims: list[str] = []
        for name in set(sys.modules) - before:
            module = sys.modules.get(name)
            origin = getattr(module, "__file__", None) or ""
            if not origin:
                # Namespace packages have no __file__ but can still shadow the
                # next repo's package of the same name.
                try:
                    paths = list(getattr(module, "__path__", []) or [])
                except Exception:  # noqa: BLE001 - an unreadable path is not a victim
                    paths = []
                origin = paths[0] if paths else ""
            if not origin:
                continue
            try:
                resolved = str(Path(origin).resolve())
            except (OSError, ValueError):
                continue
            if not resolved.startswith(root):
                continue
            if any(marker in resolved for marker in self._VENDOR_MARKERS):
                continue
            victims.append(name)

        for name in victims:
            sys.modules.pop(name, None)

    # -- docs --------------------------------------------------------------

    def doc(self, relative: str) -> Path:
        return self.path / relative

    def has_doc(self, relative: str) -> bool:
        return self.doc(relative).is_file()


def discover(root: Path, names: tuple[str, ...] = PORTFOLIO) -> list[Repo]:
    """Find the portfolio repos beneath ``root``.

    Repos are expected at ``<root>/resilient-<name>``. A missing directory is
    simply absent from the returned list; the caller decides whether that is a
    failure, because "the repo is not cloned here" is a different finding from
    "the repo failed a check".
    """
    found: list[Repo] = []
    for name in names:
        candidate = root / f"resilient-{name}"
        if candidate.is_dir():
            found.append(Repo(name=name, path=candidate))
    return found


def find_root(start: Path | None = None) -> Path:
    """Locate the directory that holds the portfolio checkouts.

    Walks upward from ``start`` looking for a directory containing at least two
    ``resilient-*`` subdirectories, which is a strong enough signal without
    hardcoding anyone's home directory.
    """
    here = (start or Path.cwd()).resolve()
    for candidate in (here, *here.parents):
        siblings = [p for p in candidate.glob("resilient-*") if p.is_dir()]
        if len(siblings) >= 2:
            return candidate
    return here
