"""One definition of "which file did this module resolve to", recorded PORTABLY.

Lifted from ``resilient-fray``'s ``src/validation/module_bindings.py`` (fray
E-069, 2026-09-04) into the instrument, because the defect it repairs is
fleet-wide (plan v3 §7 M-5): 42 committed fray artifacts across 14 deleted
scratch clones, and the two chokepoint run-of-record artifacts of 2026-09-04,
all name ``/private/tmp/claude-501/…`` -- a directory that exists on one
machine for one day. A reader cannot resolve the path, so cannot CHECK it; and
"the string started with my repo root" is the weakest fact available anyway
(an edited or swapped file satisfies the prefix as well as the real one).

WHAT IS RECORDED INSTEAD
------------------------
For a module inside the repository: the path RELATIVE TO THE REPO ROOT, in
POSIX form, plus the sha256 of the file. Both are properties of the tree, not
of the machine, so ``(repo_root / repo_relative_path)`` resolves for every
reader and the digest says whether it is the same bytes.

For a module outside the repository -- ``resilient_mlkit`` itself, installed
into a virtualenv by design -- no path is recorded at all. It is identified by
its distribution name, version, the VCS commit the distribution was installed
from (the installer's own ``direct_url.json``, which is how a ``pyproject``
pin is realised on disk) and the file digest. For mlkit specifically,
``core.identity.build_identity()`` is the stronger record and every artifact
should carry it beside these bindings.

THE RUN-TIME ASSERTION STILL HAPPENS, HERE
------------------------------------------
:func:`record` refuses, at the yield site, a module with no ``__file__`` or a
module the caller declared repo-local that resolved outside the tree. That
check needs the absolute path and has it -- at run time, on the machine that
can answer. The artifact publishes the answer, not the question.

:func:`problems` is the reader's half: it re-resolves every recorded binding
against the reader's own root and returns one string per reason the artifact
does not describe this tree. ``core.artifact.write_artifact`` calls it before
writing, so a repo-relative path that does not exist on the tree is refused
the way an absolute one is: a string that looks right is not a binding.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Sequence
from importlib import metadata
from pathlib import Path, PurePosixPath
from types import ModuleType

#: Bumped when the shape below changes.
MODULE_BINDINGS_SCHEMA = "resilient-mlkit/module-bindings/1"


class ModuleBindingRefusal(RuntimeError):  # noqa: N818 - refusal name, fleet shape
    """A binding could not be recorded or does not describe this tree."""


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def repo_relative(path: object, *, root: Path) -> str | None:
    """``path`` as a POSIX path relative to ``root``, or None when outside it."""
    try:
        resolved = Path(str(path)).resolve()
    except (OSError, ValueError):
        return None
    root = Path(root).resolve()
    if resolved == root or root in resolved.parents:
        return str(PurePosixPath(resolved.relative_to(root)))
    return None


def _distribution_identity(module: ModuleType) -> dict[str, object]:
    """Name an out-of-repo module without naming a directory.

    Every field is read from the installed distribution's own metadata; a
    field that cannot be read is ``None`` with the reason, never guessed.
    """
    top = module.__name__.split(".")[0]
    identity: dict[str, object] = {
        "distribution": None,
        "version": None,
        "vcs_commit_id": None,
        "vcs_requested_revision": None,
        "unreadable": [],
    }
    unreadable: list[str] = identity["unreadable"]  # type: ignore[assignment]
    try:
        dist = metadata.distribution(top)
    except metadata.PackageNotFoundError:
        unreadable.append(f"no installed distribution provides the top-level package {top!r}")
        return identity
    identity["distribution"] = dist.metadata["Name"]
    identity["version"] = dist.version
    try:
        raw = dist.read_text("direct_url.json")
    except (OSError, ValueError) as exc:  # pragma: no cover - defensive
        raw = None
        unreadable.append(f"direct_url.json unreadable: {exc}")
    if raw:
        try:
            info = json.loads(raw).get("vcs_info") or {}
        except json.JSONDecodeError as exc:  # pragma: no cover - defensive
            unreadable.append(f"direct_url.json is not JSON: {exc}")
        else:
            identity["vcs_commit_id"] = info.get("commit_id")
            identity["vcs_requested_revision"] = info.get("requested_revision")
    elif raw is None and not unreadable:
        unreadable.append(
            "the distribution records no direct_url.json, so it was not installed from a VCS pin"
        )
    return identity


def record(
    modules: Sequence[ModuleType],
    *,
    root: Path,
    repo_local: Iterable[str] = (),
    subtree_of: dict[str, str] | None = None,
) -> dict[str, dict[str, object]]:
    """Bind every module to a file and describe it PORTABLY.

    ``root`` is the repository root. ``repo_local`` names the modules that MUST
    resolve inside it; ``subtree_of`` narrows one of them further (e.g.
    ``{"validation": "src"}``: "the trainer came from this tree's src/, not
    from site-packages").

    Refuses at the yield site, before any number is emitted, when a module has
    no ``__file__`` or a declared repo-local module resolved somewhere else.
    """
    root = Path(root).resolve()
    subtree_of = dict(subtree_of or {})
    required = set(repo_local) | set(subtree_of)

    bindings: dict[str, dict[str, object]] = {}
    for module in modules:
        raw = getattr(module, "__file__", None)
        if raw is None:
            raise ModuleBindingRefusal(
                f"REFUSE: module {module.__name__!r} resolved with no __file__; this run "
                "cannot say which code produced its numbers and refuses to produce any"
            )
        resolved = Path(raw).resolve()
        inside = resolved == root or root in resolved.parents
        if module.__name__ in required and not inside:
            raise ModuleBindingRefusal(
                f"REFUSE: module {module.__name__!r} resolved to {resolved}, outside {root}; "
                "this run would be measuring another tree"
            )
        if module.__name__ in subtree_of:
            wanted = (root / subtree_of[module.__name__]).resolve()
            if not (resolved == wanted or wanted in resolved.parents):
                raise ModuleBindingRefusal(
                    f"REFUSE: module {module.__name__!r} resolved to {resolved}, outside "
                    f"{wanted}; this run would be measuring another tree"
                )
        entry: dict[str, object] = {
            "inside_repo": bool(inside),
            "repo_relative_path": (
                str(PurePosixPath(resolved.relative_to(root))) if inside else None
            ),
            "sha256": _sha256_file(resolved),
        }
        if not inside:
            entry.update(_distribution_identity(module))
            entry["why_no_repo_relative_path"] = (
                "installed outside this tree, so no path would be portable; it is "
                "identified by distribution, version, the VCS commit it was installed "
                "from, and the file digest"
            )
        bindings[module.__name__] = entry
    return {"schema": MODULE_BINDINGS_SCHEMA, "bindings": bindings}


def problems(bindings: object, *, root: Path) -> list[str]:
    """Every reason ``bindings`` does not describe the tree at ``root``.

    Accepts either the ``record()`` document or its inner ``bindings`` mapping.
    Empty means every repo-local binding resolves to a file in this tree whose
    sha256 is the recorded one, and every out-of-repo binding carries a digest.
    """
    root = Path(root).resolve()
    if isinstance(bindings, dict) and "bindings" in bindings and "schema" in bindings:
        bindings = bindings["bindings"]
    if not isinstance(bindings, dict):
        return [f"module bindings are a {type(bindings).__name__}, not a mapping"]
    found: list[str] = []
    for name, entry in bindings.items():
        if not isinstance(entry, dict):
            found.append(f"{name}: binding is a {type(entry).__name__}, not a mapping")
            continue
        inside = entry.get("inside_repo")
        rel = entry.get("repo_relative_path")
        if inside is False:
            if rel is not None:
                found.append(f"{name}: inside_repo is False but a repo-relative path {rel!r} is recorded")
            if not entry.get("sha256"):
                found.append(f"{name}: out-of-repo binding records no sha256")
            continue
        if not isinstance(rel, str) or not rel:
            found.append(f"{name}: inside_repo is {inside!r} but repo_relative_path is {rel!r}")
            continue
        if PurePosixPath(rel).is_absolute() or rel.startswith("/"):
            found.append(f"{name}: repo_relative_path {rel!r} is absolute; an absolute path names a machine")
            continue
        if ".." in PurePosixPath(rel).parts:
            found.append(f"{name}: repo_relative_path {rel!r} climbs out of the repo with '..'")
            continue
        try:
            resolved = (root / rel).resolve()
        except (OSError, ValueError) as exc:
            found.append(f"{name}: repo_relative_path {rel!r} cannot be resolved: {exc}")
            continue
        if not (resolved == root or root in resolved.parents):
            found.append(f"{name}: repo_relative_path {rel!r} resolves to {resolved}, outside {root}")
            continue
        if not resolved.is_file():
            found.append(f"{name}: repo_relative_path {rel!r} is not a file in this tree")
            continue
        recorded = entry.get("sha256")
        if not recorded:
            found.append(f"{name}: records no sha256, so the file cannot be tied")
            continue
        actual = _sha256_file(resolved)
        if actual != recorded:
            found.append(
                f"{name}: {rel!r} is not the file this artifact was measured with "
                f"(sha256 {actual}, recorded {recorded})"
            )
    return found
