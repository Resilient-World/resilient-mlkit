"""Writing a report, and refusing to.

A report file is the most durable thing mlkit produces. Check results live in
``.mlkit/results/`` and are gitignored; ``reports/readiness.md`` is committed,
quoted in PR bodies, and read by people who were not there when it was
generated. It is therefore the one artifact where being overwritten by a
non-measurement does lasting damage, and the only defence that works is for
the writer itself to refuse.

THE RULE
--------
A report whose content is produced by IMPORTING the repo may not be written
from an interpreter that cannot import the repo. The prior report is left
byte-for-byte untouched, and the refusal is recorded beside it, in its own
file, so that the fact is visible to someone reading the directory rather than
only to whoever was watching the terminal.

The refusal file is named ``<report>.UNMEASURABLE.md`` and never
``<report>.md``. That naming is not cosmetic: the failure mode being closed is
"a non-measurement occupying the filename a measurement is read from", and a
refusal written into the report's own name would be that failure mode wearing
an apology.

THE SECOND RULE (E-M42)
-----------------------
A report may not name a directory on the machine that generated it. mlkit has
owned that discriminator since M-5 -- ``core.artifact.machine_paths_in_text``,
and ``write_text_artifact``, which refuses on it -- and the reports mlkit
stamps into eight repos went through neither: this module wrote them with a
bare ``path.write_text``. arabica's four stamped reports each carry a
``/private/tmp/…`` directory in their ``mlkit build:`` line as a result, put
there by mlkit's own header renderer. The guard now sits where the write
happens, so no future site anywhere in mlkit can put one in a committed report
without the writer refusing. Refusal, not scrubbing: rewriting the text of a
measurement so a check passes is the thing the fleet's rule 6 forbids, and it
would be no better for being done by the tool.

WHAT IS NOT GUARDED, AND WHY
----------------------------
``depends_on_bindings=False`` writes unconditionally. R10 and R11 parse source
with ``ast`` and import nothing from the repo; their findings are exactly as
valid from a numpy-less interpreter as from a working one. Guarding them would
suppress a real measurement in the name of protecting measurements, which is
the same defect with the sign flipped. Each caller states which it is, at the
call site, in one argument.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from . import artifact, identity
from .environment import EnvironmentProbe

#: Suffix for the file that records a refusal. Deliberately not ``.md`` alone.
REFUSAL_SUFFIX = ".UNMEASURABLE.md"

#: Suffix for the file that records the OTHER refusal (E-M42): the rendering
#: named a directory on the machine that generated it. A separate suffix from
#: :data:`REFUSAL_SUFFIX` because "this environment could not measure" and "this
#: text is not portable" are different facts with different repairs, and one
#: filename carrying both would make a reader guess which happened.
MACHINE_PATH_SUFFIX = ".NAMES_A_MACHINE.md"


@dataclass(frozen=True)
class ReportWrite:
    """What happened when a report was offered to the writer."""

    path: Path
    written: bool
    preserved: bool
    reason: str
    #: sha256 of the report file before the call, or None if it did not exist.
    prior_sha256: str | None = None
    #: sha256 of the report file after the call. Equal to ``prior_sha256``
    #: whenever ``preserved`` is true -- that equality is the evidence the
    #: guard works, and the controls in ``tests/test_report_guard.py`` assert
    #: on exactly it.
    sha256: str | None = None
    #: Where the refusal was recorded, when there was one.
    refusal_path: Path | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "path": str(self.path),
            "written": self.written,
            "preserved": self.preserved,
            "reason": self.reason,
            "prior_sha256": self.prior_sha256,
            "sha256": self.sha256,
            "refusal_path": str(self.refusal_path) if self.refusal_path else None,
        }


def _sha256(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def guarded_write(
    path: Path,
    content: str,
    *,
    probe: EnvironmentProbe | None,
    depends_on_bindings: bool,
    nonce: str = "",
    git_sha: str = "",
) -> ReportWrite:
    """Write ``content`` to ``path``, unless doing so would destroy a measurement.

    Args:
        probe: the environment verdict for the repo, or None when the caller
            did not take one. None is treated as "no evidence of an
            unmeasurable environment" and writes -- a guard that refused on
            absent evidence would make every unwired repo unreportable.
        depends_on_bindings: True when the content was produced by importing
            the repo. False for a pure static analysis, which is measured
            correctly whatever the interpreter is missing.
    """
    prior = _sha256(path)

    named = artifact.machine_paths_in_text(content)
    if named:
        return _refuse_machine_path(path, named, prior, nonce, git_sha)

    if not depends_on_bindings or probe is None or probe.measurable:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        return ReportWrite(
            path, True, False,
            "environment can import this repo's bindings"
            if probe is not None and depends_on_bindings
            else "report does not depend on importing the repo",
            prior, _sha256(path),
        )

    refusal = path.with_name(path.name.removesuffix(".md") + REFUSAL_SUFFIX)
    refusal.parent.mkdir(parents=True, exist_ok=True)
    refusal.write_text(_render_refusal(path, probe, prior, nonce, git_sha))
    after = _sha256(path)
    reason = (
        f"refused to write {path.name} from an unmeasurable environment: {probe.reason}. "
        + (
            f"the prior report is preserved unchanged (sha256 {prior[:12]}…)"
            if prior
            else f"no prior {path.name} existed, so none was destroyed; "
            "nothing was written in its place"
        )
        + f"; the refusal is recorded in {refusal.name}"
    )
    return ReportWrite(path, False, True, reason, prior, after, refusal)


def _refuse_machine_path(
    path: Path,
    named: list[tuple[str, str]],
    prior: str | None,
    nonce: str,
    git_sha: str,
) -> ReportWrite:
    """Refuse to write a report whose text names a directory on this machine.

    E-M42. mlkit has owned the discriminator since M-5
    (:func:`core.artifact.machine_paths_in_text`) and has owned a writer that
    refuses on it (:func:`core.artifact.write_text_artifact`), and the four
    reports mlkit stamps into eight repos went through NEITHER: this function's
    caller wrote them with a bare ``path.write_text``. So the one class of
    defect mlkit tells its adopters to refuse was the one class its own most
    durable artifact could carry, and did — arabica's four stamped reports each
    carry a ``/private/tmp/…`` directory in their ``mlkit build:`` line, put
    there by mlkit's own header renderer.

    Refusing is the right verb and scrubbing is not. A report is a
    measurement's text; a writer that silently rewrote it would be editing a
    measurement to make its own check pass, which is the shape rule 6 forbids.
    The measurement is preserved untouched and the run says, loudly, that the
    text it was about to write named a machine.

    **The refusal record names POSITIONS, never the tokens.** Writing the
    offending path into the file that objects to it would be the same defect
    with an apology attached, and this file is written into the repo exactly
    where the report would have gone. The full tokens go to the terminal
    through :class:`core.artifact.MachinePathRefused`, which is raised by the
    sibling writer and is where an operator reads them.
    """
    refusal = path.with_name(path.name.removesuffix(".md") + MACHINE_PATH_SUFFIX)
    refusal.parent.mkdir(parents=True, exist_ok=True)
    refusal.write_text(_render_machine_path_refusal(path, named, prior, nonce, git_sha))
    after = _sha256(path)
    reason = (
        f"refused to write {path.name}: {len(named)} token(s) in the rendered "
        "report name an absolute directory on the machine that generated it, "
        "which no reader of this repository can resolve or check "
        f"(at line:col {', '.join(pos for pos, _ in named[:8])}"
        + (f", +{len(named) - 8} more" if len(named) > 8 else "")
        + "). "
        + (
            f"the prior report is preserved unchanged (sha256 {prior[:12]}…)"
            if prior
            else f"no prior {path.name} existed, so none was destroyed; "
            "nothing was written in its place"
        )
        + f"; the refusal is recorded in {refusal.name}"
    )
    return ReportWrite(path, False, True, reason, prior, after, refusal)


def _render_machine_path_refusal(
    path: Path,
    named: list[tuple[str, str]],
    prior: str | None,
    nonce: str,
    git_sha: str,
) -> str:
    lines = [
        f"# {path.name} was NOT written — the rendering named a machine",
        "",
        "This file is not a report. It records a refusal.",
        "",
        f"- run nonce: `{nonce or 'NA (not supplied)'}`",
        f"- git SHA: `{git_sha or 'NA (not a git worktree)'}`",
        *identity.header_lines(),
        f"- offending token(s): {len(named)}",
        "",
        "## Why",
        "",
        "The text mlkit was about to write carried absolute filesystem paths on",
        "the machine that generated it. A committed report is read by people who",
        "were not there when it ran and on machines where that directory does not",
        "exist, so such a token is unresolvable and uncheckable — it reads as",
        "evidence and is not. mlkit records itself by IDENTITY (`stamp`,",
        "`source_sha256`, `vcs_commit`) and records a repo file by repo-relative",
        "path plus sha256; neither needs a directory.",
        "",
        "The prior report was NOT overwritten, and nothing was scrubbed: a writer",
        "that edited the text of a measurement to make its own check pass would be",
        "the defect this refusal exists to stop, wearing the fix's clothes.",
        "",
        "## Where",
        "",
        "Positions only. The tokens themselves are deliberately NOT reproduced",
        "here: this file is written into the repository at the report's own",
        "location, and repeating the directory would put on disk exactly what the",
        "refusal objects to. The full tokens are on the terminal, in the",
        "`MachinePathRefused` message from `core.artifact`.",
        "",
        "| line:col | token length |",
        "|---|---|",
    ]
    lines += [f"| `{pos}` | {len(tok)} |" for pos, tok in named[:64]]
    if len(named) > 64:
        lines.append(f"| … | +{len(named) - 64} more |")
    lines += [
        "",
        "## What to do",
        "",
        "Fix the producer, not the text. Find what put a directory into the",
        "rendering — a check reporting a resolved path rather than a declared,",
        "repo-relative one is the usual cause — and have it name the repo-relative",
        "path, or the kind of tree, or the identity. Then re-run the phase.",
        "",
    ]
    if prior:
        lines += [
            f"`{path.name}` is unchanged at sha256 `{prior}`.",
            "",
        ]
    lines += ["Delete this file once a clean report has been written.", ""]
    return "\n".join(lines)


def _render_refusal(
    path: Path,
    probe: EnvironmentProbe,
    prior: str | None,
    nonce: str,
    git_sha: str,
) -> str:
    lines = [
        f"# {path.name} was NOT regenerated — environment unmeasurable",
        "",
        "This file is not a report. It records a refusal.",
        "",
        f"- run nonce: `{nonce or 'NA (not supplied)'}`",
        f"- git SHA: `{git_sha or 'NA (not a git worktree)'}`",
        # The refusal is stamped for the same reason the report is (E-M24):
        # "which mlkit declined to overwrite this" is as much a fact about a
        # build as "which mlkit measured it", and a reader comparing this file
        # against the report beside it needs both to name their author.
        *identity.header_lines(),
        f"- interpreter: python {probe.python or 'NA'}",
        f"- verdict: **{probe.verdict}**",
        "",
        "## Why",
        "",
        probe.reason,
        "",
        "`Environment unmeasurable` is a different fact from `FAIL`. A check that",
        "could not run says nothing about the repo, so its output must not replace",
        "output that said something. mlkit therefore left the existing report",
        "exactly as it found it.",
        "",
    ]
    if prior:
        lines += [
            f"`{path.name}` is unchanged at sha256 `{prior}`. Whatever it says was",
            "measured by whichever interpreter last wrote it; this run did not touch it.",
            "",
        ]
    else:
        lines += [
            f"There was no existing `{path.name}`, so nothing was destroyed — and",
            "nothing was written in its place either. An absent report is an honest",
            "statement that this repo has not been measured here.",
            "",
        ]
    lines += ["## Bindings, as this interpreter found them", "", "| binding | result |", "|---|---|"]
    for name, status in sorted(probe.bindings.items()):
        lines.append(f"| `{name}` | `{status}` |")
    if not probe.bindings:
        lines.append("| — | none declared |")
    lines += [
        "",
        "## What to do",
        "",
        "Run mlkit from the environment the repo declares — its own `.venv`, or",
        "`uv run --group gates` — and re-run the phase. Nothing here needs fixing",
        "in the repo; the missing modules above are absent from the interpreter,",
        "not from the source tree.",
        "",
        "Delete this file once a measured report has been regenerated.",
        "",
    ]
    return "\n".join(lines)
