"""The declared version must be able to tell this build apart from a tag.

WHAT THIS PINS, MEASURED ON THIS REPO
-------------------------------------
`tests/test_version_declaration.py` holds the version against the CHANGELOG and
against every other literal in the package. Both of those compare the version to
something written down in the same tree. Neither compares it to the thing a
consumer actually pins, which is a TAG. So this was measurable on `main` at
`6921e9a` (2026-09-01) and nothing in the suite could see it::

    git rev-list v0.5.0..6921e9a --count            -> 36
    git diff --shortstat v0.5.0..6921e9a            -> 21 files, +5438 -97
    git show v0.5.0:src/resilient_mlkit/__init__.py -> __version__ = "0.5.0"
    resilient_mlkit.__version__ at 6921e9a          -> "0.5.0"

`resilient-chokepoint` pins mlkit at `8517341`, which IS the `v0.5.0` tag, and
`resilient-fray` pins `c65b2e7`. Both of those trees declare `0.5.0`, and so
does a tree 36 commits and 5,438 insertions later in which D3 changes verdict on
unchanged repo code (`11a5bcd`), R11 grows an NA lane (`f5cd91c`) and
`core.served.challenger_decision` grows two more (`66c456b`, `7884be5`). Every
artifact any of those trees writes stamps the same `mlkit_version`. The number
that is supposed to name the instrument names three different instruments.

This is E-M08's defect class returning one level up. E-M08 was three copies of
the version inside one tree, and the repair was to hold the copies against each
other. The copies now agree; what nothing held is the version against the
RELEASE HISTORY, so the string could sit still while the instrument moved.

WHAT IS ASSERTED
----------------
One invariant, stated so that it constrains the tree rather than a snapshot:

    No tag may declare the same version this build declares while shipping
    different source.

Equivalently: if the version has not moved since a tag, neither may the shipped
package. Note which way round that is. The check never demands a bump for its
own sake -- a HEAD sitting exactly ON a tag is silent, and a HEAD that has
already bumped past the newest tag is silent no matter how much source moves
afterwards. It fires on exactly one state: a version string that cannot
distinguish two different instruments.

Cutting the tag stays the signatory's; this only refuses to let the string go
stale while they are not looking.

SCOPE, and why it is `src/` and `pyproject.toml`
------------------------------------------------
`SHIPPED_SURFACE` is the surface an adopter installs. `src/` is the importable
package -- every check's semantics live there. `pyproject.toml` carries the
dependencies, the entry point and the Python floor, which are equally part of
what `pip install` produces. Docs, reports, `spine/` templates and this test
suite are deliberately OUT: they are not what the eight repos execute, and a
check that demanded a version bump for a typo in a report would be turned off.
Widening the surface is one edit to the tuple, which is the point of naming it.

GIT AVAILABILITY
----------------
The invariant is about release history, so it can only be measured where the
release history is. Three states are SKIPPED, each naming itself and the path
or condition that produced it, because a silent pass over a missing tag store
is precisely the shape of "a green tick for having measured nothing":

* `git` is not on PATH;
* this checkout has no `.git` (an installed sdist or a vendored copy);
* no `v*` tag is visible -- notably `actions/checkout` at its default
  `fetch-depth: 1` fetches no tags, which is why `.github/workflows/ci.yml`
  sets `fetch-depth: 0` on the pytest job.

Any OTHER git failure is raised, not skipped. A skip lane wide enough to
swallow `git show` returning garbage would be a checker that cannot fail.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from collections.abc import Iterable
from pathlib import Path

import pytest

import resilient_mlkit

ROOT = Path(__file__).resolve().parent.parent

#: What an adopter installs. See the module docstring for what is deliberately
#: excluded and why. Paths are repo-relative and passed to `git` as pathspecs.
SHIPPED_SURFACE = ("src", "pyproject.toml")

#: The one file the version literal lives in, at HEAD and inside every tag.
VERSION_FILE = "src/resilient_mlkit/__init__.py"

#: A release tag. `nightly`, `v1.0`, `release-2` and `v1.0.0-rc1` are not
#: release tags of this package and are not ranked as ones.
_TAG = re.compile(r"^v(\d+)\.(\d+)\.(\d+)$")

#: The module-level assignment. Deliberately the same shape
#: `tests/test_version_declaration.py` uses: an indented assignment inside a
#: function is a local, not the package's declaration.
_VERSION_LITERAL = re.compile(r"^__version__\s*=\s*['\"]([^'\"]+)['\"]", re.MULTILINE)


# -- pure helpers, so the controls below drive the same code the repo test does


def release_tags(tags: Iterable[str]) -> list[str]:
    """The `vX.Y.Z` tags among `tags`, oldest release first.

    Ordered by the parsed triple, NOT by string: `v0.10.0` is newer than
    `v0.9.0` and sorts before it lexicographically. That is an operand this
    check reports on, so it is not left to `sorted()` on text.
    """
    ranked = [
        (tuple(int(g) for g in match.groups()), tag)
        for tag in (t.strip() for t in tags)
        if (match := _TAG.match(tag))
    ]
    return [tag for _, tag in sorted(ranked)]


def version_in(source: str) -> str | None:
    """The `__version__` a module source declares, or None if it declares none.

    None is the honest answer and callers must not read it as "matches". A tag
    whose `__init__.py` carries no literal cannot be compared, and the caller
    says so by name rather than treating the tag as agreeing.
    """
    match = _VERSION_LITERAL.search(source)
    return match.group(1) if match else None


def indistinguishable(
    head_version: str,
    tag_version: str | None,
    changed_paths: Iterable[str],
) -> bool:
    """True when this build and that tag share a version but not a source.

    Both operands matter and neither alone is the defect: equal versions with an
    equal tree is a HEAD sitting on the tag, and a different tree under a
    different version is an ordinary unreleased bump.
    """
    return head_version == tag_version and bool(list(changed_paths))


# -- the git lane ----------------------------------------------------------


def _git(*args: str) -> str:
    """Run git in this checkout. Raises on failure; never skips.

    The skip conditions are established once, by the `release_history` fixture,
    from questions with yes/no answers. Everything reaching here has already
    been established to be answerable, so a non-zero exit is a defect in this
    test or in the checkout and must be seen as one.
    """
    proc = subprocess.run(
        ["git", "-C", str(ROOT), *args],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(args)} exited {proc.returncode} in {ROOT}: "
            f"{proc.stderr.strip()}"
        )
    return proc.stdout


@pytest.fixture(scope="module")
def release_history() -> list[str]:
    """This checkout's release tags, oldest first. Skips by name when absent."""
    if shutil.which("git") is None:
        pytest.skip(
            "SKIPPED-NAMED tag-distance: git is not on PATH, so this checkout's "
            "release history cannot be read. The invariant is unmeasured here, "
            "not satisfied."
        )
    if not (ROOT / ".git").exists():
        pytest.skip(
            f"SKIPPED-NAMED tag-distance: {ROOT} has no .git (an installed sdist "
            "or a vendored copy), so there is no release history to compare the "
            "declared version against. Unmeasured, not satisfied."
        )
    tags = release_tags(_git("tag", "--list", "v*").splitlines())
    if not tags:
        pytest.skip(
            f"SKIPPED-NAMED tag-distance: no vX.Y.Z tag is visible in {ROOT}. "
            "actions/checkout fetches no tags at its default fetch-depth: 1 -- "
            "ci.yml sets fetch-depth: 0 for this reason. Unmeasured, not "
            "satisfied."
        )
    return tags


# -- the real repo ---------------------------------------------------------


def test_the_package_under_test_is_this_checkout() -> None:
    """Every operand below must come from one tree, or the comparison is empty.

    `resilient_mlkit.__version__` is read from the IMPORTED package and the diff
    is taken in THIS directory. If those are two different trees the check reads
    one build's version against another build's source and can report anything.
    """
    imported = Path(resilient_mlkit.__file__).resolve()
    assert imported.is_relative_to(ROOT / "src"), (
        f"the imported resilient_mlkit is {imported}, which is not inside "
        f"{ROOT / 'src'}; the version and the diff would come from two "
        "different trees"
    )


def test_no_tag_declares_this_version_over_a_different_shipped_source(
    release_history: list[str],
) -> None:
    """The invariant. FIRES on `main` at `6921e9a`, where v0.5.0 is 36 commits back.

    Every release tag is examined, not only the newest: `v0.3.0` declares
    `0.2.0` in its own tree (that is E-M08 as committed), so "the newest tag"
    and "the tag declaring this version" are not the same question.
    """
    head_version = resilient_mlkit.__version__
    offenders: list[str] = []
    for tag in release_history:
        tag_version = version_in(_git("show", f"{tag}:{VERSION_FILE}"))
        changed = sorted(
            set(_git("diff", "--name-only", tag, "--", *SHIPPED_SURFACE).split())
            | set(
                _git(
                    "ls-files", "--others", "--exclude-standard", "--", *SHIPPED_SURFACE
                ).split()
            )
        )
        if indistinguishable(head_version, tag_version, changed):
            offenders.append(
                f"{tag} (declares {tag_version}) differs from this build in "
                f"{len(changed)} shipped path(s): {', '.join(changed)}"
            )
    assert not offenders, (
        f"this build declares {head_version} and so does a tag whose shipped "
        "source is not this source, so no artifact either of them writes can "
        "say which instrument produced it (docs/ESCALATIONS.md E-M08, one level "
        f"up): {'; '.join(offenders)}. Bump resilient_mlkit.__version__ and add "
        "the matching CHANGELOG heading; cutting the tag is the signatory's."
    )


def test_the_newest_release_tag_is_identified_and_parses_a_version(
    release_history: list[str],
) -> None:
    """Guards the check above against passing over an absence.

    `indistinguishable` returns False when the tag's version is None, so a tag
    whose `__init__.py` this parser cannot read would be silently exonerated.
    Assert here that the newest tag really does yield a version.
    """
    newest = release_history[-1]
    declared = version_in(_git("show", f"{newest}:{VERSION_FILE}"))
    assert declared is not None, (
        f"{newest} carries no readable `__version__` literal in {VERSION_FILE}, "
        "so the tag-distance check above cannot compare against it and would "
        "pass over the absence"
    )


def test_the_shipped_surface_pathspecs_all_exist(release_history: list[str]) -> None:
    """A typo'd pathspec makes every diff empty and every verdict green.

    `git diff -- src/resiliant_mlkit` is not an error; it is an empty diff. This
    is the same failure mode as a scanner pointed at the wrong directory.
    """
    for path in SHIPPED_SURFACE:
        assert (ROOT / path).exists(), (
            f"SHIPPED_SURFACE names {path!r}, which does not exist in {ROOT}; a "
            "pathspec matching nothing makes this file's diffs empty and its "
            "verdicts vacuous"
        )


# -- controls --------------------------------------------------------------


def test_positive_control_the_state_measured_on_main_is_caught() -> None:
    """FIRES: `main` at `6921e9a` -- 0.5.0 on both sides, nine shipped paths moved."""
    assert indistinguishable(
        "0.5.0",
        "0.5.0",
        ["src/resilient_mlkit/checks/decision.py", "src/resilient_mlkit/core/served.py"],
    )


def test_negative_control_a_bumped_version_is_accepted() -> None:
    """SILENT: the repair. Source moved AND the string moved with it."""
    assert not indistinguishable("0.6.0", "0.5.0", ["src/resilient_mlkit/core/served.py"])


def test_negative_control_a_head_sitting_on_the_tag_is_accepted() -> None:
    """SILENT: equal versions over an equal tree is what a tag IS."""
    assert not indistinguishable("0.5.0", "0.5.0", [])


def test_negative_control_an_unparseable_tag_version_is_not_an_offence() -> None:
    """SILENT here, and LOUD in the test above: None is not equality.

    A tag this parser cannot read must not be reported as an offender -- the
    honest verdict is "unread", and it is
    `test_the_newest_release_tag_is_identified_and_parses_a_version` that
    refuses to let an unread tag stand.
    """
    assert not indistinguishable("0.5.0", None, ["src/resilient_mlkit/core/served.py"])


def test_release_tags_are_ranked_by_number_not_by_string() -> None:
    """FIRES on the lexicographic bug: `v0.10.0` sorts before `v0.9.0` as text."""
    assert release_tags(["v0.9.0", "v0.10.0", "v0.2.0"]) == ["v0.2.0", "v0.9.0", "v0.10.0"]


def test_release_tags_ignores_everything_that_is_not_a_release_tag() -> None:
    """SILENT on `nightly`; a moving pointer is not a release to compare against."""
    assert release_tags(["nightly", "v1.0", "v1.0.0-rc1", "release-2", "v1.0.0"]) == [
        "v1.0.0"
    ]


def test_release_tags_of_nothing_is_empty_not_an_exception() -> None:
    """The empty case the fixture converts into a NAMED skip, not into a pass."""
    assert release_tags([]) == []


def test_version_in_reads_the_declaration_and_only_the_declaration() -> None:
    """The three shapes this repo has actually carried, as committed."""
    assert version_in('__version__ = "0.2.0"\n') == "0.2.0"
    assert version_in("from . import __version__\nprint(__version__)\n") is None
    assert version_in("def probe():\n    __version__ = '0.0.1'\n") is None
