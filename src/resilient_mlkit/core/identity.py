"""Which mlkit measured this — an identity that moves when gate semantics move.

THE DEFECT (docs/BUILD_IDENTITY.md, E-M24)
------------------------------------------
``resilient-fray`` pins mlkit by rev ``c65b2e7``; mlkit main is ``6921e9a``.
Forty commits apart, nine source files different, ``+50/-5`` in
``checks/readiness.py`` (the file that emits R1-R12) and ``+373/-13`` in
``core/served.py`` (the promotion verdict) -- and BOTH trees declare
``__version__ == "0.5.0"``. Every adopter readiness table is therefore
"readiness under whichever mlkit happened to be installed", and nothing in the
report says which. A report that cannot name the instrument that wrote it is
not evidence.

The identity that existed did not close this. ``cli._self_sha()`` shells out to
``git rev-parse HEAD`` in mlkit's own source directory. In an adopter's
environment that directory is ``site-packages``, which is not a git worktree,
so the call returns ``""`` and the two headers using it render
``NA (not a git worktree)``. The one field that could have told the builds
apart is empty in exactly the case it is needed.

WHAT IS IDENTITY HERE
---------------------
A length-framed sha256 over every file the RUNNING package was loaded from.
Not a checkout elsewhere, not a number written down by hand: the bytes on disk
under ``Path(__file__).parent.parent``, which is what the interpreter is
executing.

Three properties are wanted and this is the only construction that has all
three:

* **It moves iff the shipped source moves.** Which is the only way gate
  semantics can move. A version literal does not have this property -- that is
  the defect. A git sha has it, but only where there is a git worktree.
* **It is computable from any install form.** Wheel, sdist, editable, or a
  directory somebody edited by hand after install. The git sha is unavailable
  in three of those four.
* **It has a knowable failure.** When the tree cannot be read the digest is
  ``None`` and every comparison over it returns ``INDETERMINATE``. It never
  degrades into a plausible-looking string, because a plausible identity is
  worse than a missing one: it does not get checked.

NOT THE VERSION
---------------
``__version__`` stays one string literal and stays the signatory's: release
naming and tag cutting are not an agent's to invent, and
``tests/test_version_declaration.py`` holds the literal against the newest
CHANGELOG heading. The build identity therefore lives BESIDE the version. The
compared token embeds the version for readability -- ``0.5.0+src.4f2a91c0be3d``
-- but the version is not what is compared; a token differing only in its
digest half is a mismatch and a token differing only in its version half is
too, because both mean a different tree wrote the report.

NOT THE VCS COMMIT EITHER
-------------------------
``direct_url.json`` in the installed ``.dist-info`` records the commit
REQUESTED at install time. It is reported beside the token as context and is
deliberately not part of it:

* it does not move when somebody edits ``site-packages`` after install; the
  digest does;
* two commits can ship a byte-identical package tree, and those two builds
  measure identically, so calling them different identities would make the
  check fire on a difference that is not a difference.

The digest is authoritative. ``direct_url.json`` corroborates, and the read is
tied to the running module: the distribution's own location must contain the
package root that was hashed, or the field reports the disagreement rather
than the metadata.
"""

from __future__ import annotations

import functools
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

#: The name of the installed distribution, as declared in ``pyproject.toml``.
DIST_NAME = "resilient-mlkit"

#: Hex characters of the digest carried in the compared token. Twelve is the
#: same width this repo already uses for a git sha in report tables
#: (``cli._render_fleet_markdown``), and 48 bits is far past any collision this
#: could plausibly meet: the population is "package trees ever built", which is
#: thousands, not billions.
DIGEST_CHARS = 12

#: Directory names never hashed. ``__pycache__`` holds compiled bytecode whose
#: bytes depend on the interpreter and on when it last ran, neither of which is
#: a gate semantic. Hashing it would make the identity move for reasons that
#: are not source changes, which is the mirror image of the defect.
EXCLUDED_DIRS = frozenset({"__pycache__"})

#: File suffixes never hashed, for the same reason.
EXCLUDED_SUFFIXES = frozenset({".pyc", ".pyo"})

#: The literal prefix of the report header line. One constant, read by the
#: emitter and by the parser, so the two cannot drift into two conventions.
STAMP_PREFIX = "- measured by mlkit: "

#: What the token's digest half reads when the tree could not be hashed. It is
#: a WORD and not a hex string on purpose: a reader and a parser must both be
#: unable to mistake it for a measurement.
UNKNOWN_DIGEST = "unknown"

# -- verdicts ---------------------------------------------------------------

#: The report names the identity of the mlkit that is installed here.
MATCH = "MATCH"
#: It names a different one. Some other build wrote this report.
MISMATCH = "MISMATCH"
#: There is no identity line at all -- a report written before this existed.
#: Distinct from MISMATCH because "written by an unknown build" and "written by
#: a known, different build" are different facts and need different action.
UNSTAMPED = "UNSTAMPED"
#: Two or more stamps in one file, and they disagree.
CONFLICTING = "CONFLICTING"
#: One side's digest is unknown. No equality is asserted from an unknown
#: operand; that would be a fabricated verdict.
INDETERMINATE = "INDETERMINATE"


@dataclass(frozen=True)
class BuildIdentity:
    """The identity of the mlkit build that is running in this interpreter."""

    #: ``resilient_mlkit.__version__``. Carried for readability, not compared
    #: on its own.
    version: str
    #: Full hex sha256 over the package tree, or None when it could not be read.
    source_sha256: str | None
    #: How many files went into the digest. ``0`` alongside a None digest.
    files: int
    #: Absolute path of the package directory that was hashed.
    root: str
    #: Commit id from the installed dist's ``direct_url.json``, when the dist
    #: was installed from VCS and its location contains ``root``.
    vcs_commit: str | None = None
    #: The VCS url beside it, same conditions.
    vcs_url: str | None = None
    #: Why ``vcs_commit`` is None, in words. Never empty when it is None.
    vcs_reason: str = ""
    #: Why ``source_sha256`` is None, in words. Empty when it is not None.
    unavailable: str = ""

    @property
    def stamp(self) -> str:
        """The one token that gets compared.

        ``0.5.0+src.4f2a91c0be3d``, or ``0.5.0+src.unknown`` when the tree could
        not be hashed. Callers must not compare stamps carrying
        ``UNKNOWN_DIGEST``; :func:`compare_stamps` refuses to, and returns
        INDETERMINATE.
        """
        half = self.source_sha256[:DIGEST_CHARS] if self.source_sha256 else UNKNOWN_DIGEST
        return f"{self.version}+src.{half}"

    @property
    def known(self) -> bool:
        """True when this identity was actually measured off a readable tree."""
        return self.source_sha256 is not None

    def stamp_line(self) -> str:
        """The canonical report header line: the compared token, and nothing else.

        Deliberately carries no path, no file count and no vcs commit. This is
        the line the adopter-side check reads, and the fewer things on it the
        fewer things can be mistaken for the operand. Everything else goes on
        :meth:`context_line`, where a human reads it and no parser does.
        """
        return f"{STAMP_PREFIX}`{self.stamp}`"

    def context_line(self) -> str:
        """The human half: what the token was computed from, and the pin beside it."""
        if self.source_sha256 is None:
            what = f"tree at `{self.root}` was NOT hashed — {self.unavailable}"
        else:
            what = (
                f"sha256 `{self.source_sha256}` over {self.files} shipped file(s) "
                f"in `{self.root}`"
            )
        vcs = (
            f"installed from vcs `{self.vcs_commit}`"
            if self.vcs_commit
            else f"vcs commit NA — {self.vcs_reason}"
        )
        return f"- mlkit build: {what}; {vcs}"

    def header_lines(self) -> list[str]:
        """Both lines, in the order every mlkit report writes them."""
        return [self.stamp_line(), self.context_line()]

    def to_dict(self) -> dict[str, object]:
        return {
            "stamp": self.stamp,
            "version": self.version,
            "source_sha256": self.source_sha256,
            "files": self.files,
            "root": self.root,
            "vcs_commit": self.vcs_commit,
            "vcs_url": self.vcs_url,
            "vcs_reason": self.vcs_reason,
            "unavailable": self.unavailable,
        }


@dataclass(frozen=True)
class IdentityMatch:
    """The result of asking whether a report and this dist agree."""

    verdict: str
    #: The stamp read out of the report, or None when it carried none.
    found: str | None
    #: The stamp of the mlkit running here.
    installed: str
    reason: str
    #: Every stamp the file carried, in order of appearance.
    all_found: tuple[str, ...] = ()
    #: The file this came from, when it came from a file.
    path: str | None = None

    @property
    def ok(self) -> bool:
        """True only for MATCH. Everything else is something to look at."""
        return self.verdict == MATCH

    def to_dict(self) -> dict[str, object]:
        return {
            "verdict": self.verdict,
            "found": self.found,
            "installed": self.installed,
            "reason": self.reason,
            "all_found": list(self.all_found),
            "path": self.path,
        }


# -- the digest -------------------------------------------------------------


def package_root() -> Path:
    """The directory the RUNNING package was loaded from.

    Derived from this module's own ``__file__`` rather than by importing
    ``resilient_mlkit`` and reading its ``__file__``: this module IS part of
    the tree being described, so tying the digest to its own location is the
    tightest tie available, and it cannot pick up a different install that
    happens to be first on the path.
    """
    return Path(__file__).resolve().parent.parent


def shipped_files(root: Path) -> list[Path]:
    """Every file under ``root`` that mlkit ships, in sorted relative order.

    Sorted by POSIX relative path so the digest does not depend on the order
    the filesystem happens to hand back. Excludes ``__pycache__`` and compiled
    bytecode; includes everything else, because a package-data file mlkit ships
    can change behaviour and a ``.py``-only digest would leave a gap that reads
    as coverage.
    """
    out: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if EXCLUDED_DIRS.intersection(path.relative_to(root).parts[:-1]):
            continue
        if path.suffix in EXCLUDED_SUFFIXES:
            continue
        out.append(path)
    return sorted(out, key=lambda p: p.relative_to(root).as_posix())


def digest_tree(root: Path) -> tuple[str | None, int, str]:
    """``(hexdigest, file_count, unavailable_reason)`` for the tree at ``root``.

    Each entry is length-framed -- ``len(relpath) || relpath || len(bytes) ||
    bytes``, each length an 8-byte big-endian integer -- so that no rename and
    no shuffle of content between files can produce a colliding byte stream. A
    bare concatenation would let ``a/bc`` + ``d`` and ``a/b`` + ``cd`` hash the
    same, which is a real hazard in a package where module names and module
    bodies are both being hashed.

    A read failure returns ``(None, 0, reason)``. It does NOT return a partial
    digest over the files that happened to be readable: a digest computed from
    an unknown subset is a number that looks like an identity and is not one.
    """
    if not root.is_dir():
        return None, 0, f"package root {root} is not a directory"
    try:
        files = shipped_files(root)
    except OSError as exc:
        return None, 0, f"could not walk {root}: {exc}"
    if not files:
        return None, 0, f"no shipped files found under {root}"

    h = hashlib.sha256()
    for path in files:
        rel = path.relative_to(root).as_posix().encode("utf-8")
        try:
            data = path.read_bytes()
        except OSError as exc:
            return None, 0, f"could not read {path.relative_to(root).as_posix()}: {exc}"
        h.update(len(rel).to_bytes(8, "big"))
        h.update(rel)
        h.update(len(data).to_bytes(8, "big"))
        h.update(data)
    return h.hexdigest(), len(files), ""


def _is_under(child: Path, parent: Path) -> bool:
    """True when ``child`` is ``parent`` or lives inside it."""
    try:
        child.relative_to(parent)
    except ValueError:
        return False
    return True


def _direct_url_payload(dist: object) -> tuple[dict | None, str]:
    """``(payload, reason)`` for a dist's ``direct_url.json``."""
    try:
        raw = dist.read_text("direct_url.json")  # type: ignore[attr-defined]
    except Exception as exc:  # noqa: BLE001 - metadata is third-party-populated
        return None, f"direct_url.json unreadable: {exc}"
    if not raw:
        return None, "the dist carries no direct_url.json (not a direct install)"
    try:
        return json.loads(raw), ""
    except json.JSONDecodeError as exc:
        return None, f"direct_url.json is not valid JSON: {exc}"


def _ties_to_root(dist: object, payload: dict | None, root: Path) -> bool:
    """Whether ``dist``'s own records describe the tree at ``root``.

    Two ways a distribution can be shown to describe this tree, and both are
    checked because each covers a case the other cannot:

    * **By install location.** ``locate_file("resilient_mlkit")`` resolving to
      ``root``. True for a wheel or a VCS install into ``site-packages``.
    * **By editable source directory.** An editable install's ``direct_url``
      names the source tree with ``dir_info.editable``, and ``locate_file``
      then points at a ``site-packages`` path that does not exist. Ties when
      ``root`` lives under the named directory.

    Neither holding is NOT "no metadata". It is "the metadata on this machine
    describes some other build", which is a different and more interesting
    fact, and the caller reports it as such.
    """
    try:
        located = Path(str(dist.locate_file("resilient_mlkit"))).resolve()  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001
        located = None
    if located is not None and located == root:
        return True
    if payload and (payload.get("dir_info") or {}).get("editable"):
        url = payload.get("url") or ""
        if isinstance(url, str) and url.startswith("file://"):
            from urllib.parse import unquote, urlparse

            src = Path(unquote(urlparse(url).path)).resolve()
            if _is_under(root, src):
                return True
    return False


def _dist_name(dist: object) -> str:
    """A distribution's declared name, or ``""`` when its metadata is unusable.

    Broad by design. The caller walks EVERY installed distribution in the
    environment, most of which are nothing to do with mlkit, and one of them
    with a malformed ``METADATA`` must not take the identity lookup down with
    it. An empty name simply does not match ``DIST_NAME``, so the entry is
    skipped exactly as any other package on the path is.
    """
    try:
        return (dist.metadata["Name"] or "") if dist.metadata else ""  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001 - a malformed sibling dist is not ours
        return ""


def _vcs_of_installed_dist(root: Path) -> tuple[str | None, str | None, str]:
    """``(commit, url, reason)`` from the installed dist's ``direct_url.json``.

    The read is TIED: the distribution that gets asked must be one whose own
    records describe the package root we hashed. Without that tie this would
    happily report the pin of a second mlkit installed elsewhere on the path,
    which is the defect wearing a disguise -- an identity field describing a
    build other than the one that ran.

    Every path out of here that yields no commit yields a REASON. There is no
    branch that returns a bare ``None``, because "vcs: NA" with no explanation
    is the shape of field this whole change exists to stop.
    """
    try:
        from importlib import metadata
    except ImportError as exc:  # pragma: no cover - stdlib
        return None, None, f"importlib.metadata unavailable: {exc}"

    try:
        dists = list(metadata.distributions())
    except Exception as exc:  # noqa: BLE001 - metadata is third-party-populated
        return None, None, f"could not enumerate installed distributions: {exc}"

    seen = 0
    for dist in dists:
        name = _dist_name(dist)
        if name.replace("_", "-").lower() != DIST_NAME:
            continue
        seen += 1
        payload, payload_reason = _direct_url_payload(dist)
        if not _ties_to_root(dist, payload, root):
            continue
        if payload is None:
            return None, None, payload_reason
        info = payload.get("vcs_info") or {}
        commit = info.get("commit_id")
        if not isinstance(commit, str) or not commit:
            editable = (payload.get("dir_info") or {}).get("editable")
            return None, None, (
                f"installed from `{payload.get('url')}`"
                + (" as an editable directory" if editable else " directly")
                + ", which records no vcs commit_id"
            )
        url = payload.get("url")
        return commit, url if isinstance(url, str) else None, ""

    if seen:
        return None, None, (
            f"{seen} installed {DIST_NAME} distribution(s) were found and none "
            f"of them describes {root}; the metadata on this machine belongs to "
            "some other mlkit, so it is not reported as this one's"
        )
    return None, None, (
        f"no installed {DIST_NAME} distribution was found; {root} is on the "
        "import path without being an installed dist"
    )


def one_tree_or_reason(root: Path) -> str:
    """``""`` when the running package is exactly the one directory at ``root``.

    The digest describes ``Path(core/identity.py).parent.parent``. That is the
    right answer only while ``resilient_mlkit`` IS one directory. Split the
    package across two path entries -- a namespace package, a shadowing
    directory earlier on ``sys.path``, a half-installed second copy -- and
    ``core/identity.py`` can be loaded from one of them while
    ``checks/readiness.py`` is loaded from the other. A digest of the first
    would then be a true statement about half the running instrument, which is
    worse than no statement: it would READ as an identity without being one.

    So this is a REFUSAL, not a warning. Its caller drops the digest, the stamp
    becomes ``+src.unknown``, and every comparison over it reports
    INDETERMINATE. mlkit has a measured history with package-path order (see
    the ``fix/evict-namespace-package-order`` work), and the identity must not
    be the one field that quietly survives it.
    """
    import importlib

    try:
        pkg = importlib.import_module(__package__.rpartition(".")[0])
    except Exception as exc:  # noqa: BLE001
        return f"could not import the parent package to check its __path__: {exc}"
    entries = [str(Path(p).resolve()) for p in getattr(pkg, "__path__", [])]
    if entries == [str(root)]:
        return ""
    return (
        f"resilient_mlkit.__path__ is {entries!r}, not exactly [{str(root)!r}]; "
        "the package is not one directory on this interpreter, so a digest of "
        "one directory would describe only part of the instrument that ran"
    )


@functools.lru_cache(maxsize=1)
def build_identity() -> BuildIdentity:
    """The identity of the mlkit running in this interpreter.

    Cached: the tree does not change under a running process, and every report
    header asks for this. ``build_identity.cache_clear()`` exists for tests.
    """
    from .. import __version__

    root = package_root()
    split = one_tree_or_reason(root)
    if split:
        sha, files, unavailable = None, 0, split
    else:
        sha, files, unavailable = digest_tree(root)
    commit, url, vcs_reason = _vcs_of_installed_dist(root)
    return BuildIdentity(
        version=__version__,
        source_sha256=sha,
        files=files,
        root=str(root),
        vcs_commit=commit,
        vcs_url=url,
        vcs_reason=vcs_reason,
        unavailable=unavailable,
    )


def header_lines() -> list[str]:
    """The two report header lines for the mlkit running here.

    Every report writer in mlkit calls THIS, not its own f-string. One emitter
    and one parser reading one prefix constant is the whole point: a second
    place that composes the line is a second convention, and two conventions is
    how a field ends up meaning different things in two reports.
    """
    return build_identity().header_lines()


# -- the adopter-side check -------------------------------------------------


def stamps_in(text: str) -> list[str]:
    """Every identity stamp the text carries, in order of appearance.

    Deliberately line-anchored and prefix-anchored, and deliberately NOT a
    loose regex over the whole document: prose quoting a stamp ("the old
    reports said ``0.5.0+src.dead...``") must not be mistaken for the header
    the writer emitted. A stamp counts only where it appears in the position
    the emitter writes it -- start of line, exact prefix, first backticked
    token after it.
    """
    found: list[str] = []
    for line in text.splitlines():
        if not line.startswith(STAMP_PREFIX):
            continue
        rest = line[len(STAMP_PREFIX) :]
        if not rest.startswith("`"):
            continue
        close = rest.find("`", 1)
        if close <= 1:
            continue
        found.append(rest[1:close])
    return found


def _digest_half(stamp: str) -> str | None:
    """The digest half of a stamp, or None when it does not carry one."""
    marker = "+src."
    at = stamp.rfind(marker)
    if at < 0:
        return None
    half = stamp[at + len(marker) :]
    return half or None


def compare_stamps(found: str, installed: str) -> tuple[str, str]:
    """``(verdict, reason)`` for one report stamp against the installed one.

    Both operands are stamps -- the same construction, from the same
    ``BuildIdentity.stamp`` property -- so the comparison has no second
    definition to drift from. Equality is over the WHOLE token, version half
    included, because a token differing only in its version half also means a
    different tree wrote the report.
    """
    found_half, installed_half = _digest_half(found), _digest_half(installed)
    if found_half is None:
        return INDETERMINATE, (
            f"the stamp in the report (`{found}`) carries no `+src.<digest>` "
            "half, so there is nothing to compare against"
        )
    if found_half == UNKNOWN_DIGEST:
        return INDETERMINATE, (
            "the report was written by an mlkit that could not hash its own "
            "package tree, so it names no identity to check"
        )
    if installed_half is None or installed_half == UNKNOWN_DIGEST:
        return INDETERMINATE, (
            "the mlkit installed here cannot hash its own package tree, so it "
            "has no identity to compare the report against; "
            f"the report names `{found}`"
        )
    if found == installed:
        return MATCH, f"the report was written by this build (`{installed}`)"
    return MISMATCH, (
        f"the report names mlkit `{found}`; the mlkit installed here is "
        f"`{installed}`. These are different builds, and every verdict in that "
        "report was reached by the one it names, not by this one"
    )


def verify_report_text(text: str, *, path: str | None = None) -> IdentityMatch:
    """Check one report's identity stamp against the mlkit installed here."""
    installed = build_identity().stamp
    found = stamps_in(text)
    if not found:
        return IdentityMatch(
            UNSTAMPED,
            None,
            installed,
            (
                "this report carries no `"
                + STAMP_PREFIX.strip()
                + "` line, so it does not say which mlkit measured it. That is "
                "NOT a mismatch: it is the absence E-M24 records, and it is "
                "what every report written by an mlkit predating this stamp "
                "looks like. It cannot be repaired by editing the file -- the "
                "fact is not recoverable from it. Re-run the phase under an "
                f"mlkit that stamps ({installed}) and the regenerated report "
                "will say so"
            ),
            (),
            path,
        )
    distinct = sorted(set(found))
    if len(distinct) > 1:
        return IdentityMatch(
            CONFLICTING,
            found[0],
            installed,
            (
                f"this file carries {len(found)} identity stamps naming "
                f"{len(distinct)} different builds ({', '.join(distinct)}); no "
                "single build wrote it, so no single build can be held to it"
            ),
            tuple(found),
            path,
        )
    verdict, reason = compare_stamps(found[0], installed)
    return IdentityMatch(verdict, found[0], installed, reason, tuple(found), path)


def verify_report(path: Path | str) -> IdentityMatch:
    """Check the report file at ``path``.

    An unreadable file is INDETERMINATE with the OS reason, never UNSTAMPED:
    "there is no stamp in this file" and "this file could not be opened" are
    different facts, and collapsing them would let a permissions error read as
    a finding about the report.
    """
    p = Path(path)
    try:
        text = p.read_text(encoding="utf-8")
    except OSError as exc:
        return IdentityMatch(
            INDETERMINATE,
            None,
            build_identity().stamp,
            f"could not read {p}: {exc}",
            (),
            str(p),
        )
    return verify_report_text(text, path=str(p))
