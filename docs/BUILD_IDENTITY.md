# Build identity — the design, written before the code (E-M24)

This document is the first commit on `fix/build-identity-e-054`. It exists
before any source edit so that what the change claims to do can be read
against what it was designed to do, rather than reconstructed from the diff.

**This introduces no statistical instrument.** Nothing here estimates,
thresholds, resamples or compares a figure. It introduces an *identifier* and
an equality test over identifiers. There is therefore no preregistered
hypothesis to file; this design note takes the same slot for the same reason —
the design is fixed before the implementation, in public.

## The measured defect

`resilient-fray` pins `resilient-mlkit` by rev `c65b2e7627be8d3362dcdddc31031
15095ddf3d0`. `resilient-mlkit` main is `6921e9af146faad69ca09ed546c607d7e484
e560`. Between them:

```
$ git -C resilient-mlkit rev-list --count c65b2e7..6921e9a
40
$ git -C resilient-mlkit diff --numstat c65b2e7 6921e9a -- src/ | wc -l
9
$ git -C resilient-mlkit diff --numstat c65b2e7 6921e9a -- \
      src/resilient_mlkit/checks/readiness.py src/resilient_mlkit/core/served.py
50	5	src/resilient_mlkit/checks/readiness.py
373	13	src/resilient_mlkit/core/served.py
```

(Measured 2026-09-01 in a local checkout of
`https://github.com/Resilient-World/resilient-mlkit`. The pin itself is read
from fray's installed dist:
`.venv/lib/python3.12/site-packages/resilient_mlkit-0.5.0.dist-info/direct_url.json`
→ `commit_id c65b2e7627be8d3362dcdddc3103115095ddf3d0`, and the `.dist-info`
directory name carries `0.5.0` — the same string mlkit main declares.)

`checks/readiness.py` is the file that emits R1–R12. `core/served.py` is the
promotion verdict. Both trees declare `resilient_mlkit.__version__ ==
"0.5.0"`.

So: two builds whose gate semantics demonstrably differ report the same
identity, and every adopter readiness table is "readiness under whichever
mlkit happened to be installed" — unverifiably. A report that cannot name
which mlkit measured it is not evidence.

The existing self-identification does not close this. `cli._self_sha()` runs
`git -C <mlkit source dir> rev-parse HEAD`. In an adopter's environment mlkit
is installed into `site-packages`, which is not a git worktree, so the call
returns `""` and the two report headers that use it render
`NA (not a git worktree)`. The one field that could have distinguished the
builds is empty in exactly the case it is needed.

## What is deliberately NOT changed

* **`__version__` stays a single string literal, and stays `"0.5.0"`.**
  Release naming and tag cutting are the signatory's. `tests/
  test_version_declaration.py` holds `__version__` against the newest
  CHANGELOG heading and forbids a second literal; nothing here touches either.
  The build identity lives *beside* the version, never inside it.
* **No new readiness row.** Adding an R-row moves every adopter's readiness
  table, which is a release-semantics decision under this repo's own
  CHANGELOG scale. The adopter-side check ships as a public function and a CLI
  subcommand; whether it becomes a gate is a separate, reviewable decision.
* **No existing check changes verdict.** This adds a header line to reports
  and a new CLI subcommand. Nothing in `checks/` gains or loses a PASS.

## The design

### 1. The identity is a digest of the source that is actually running

`resilient_mlkit.core.identity.build_identity()` walks the directory the
running package was loaded from — `Path(core/identity.py).parent.parent`, i.e.
the *installed* `resilient_mlkit/`, not a checkout somewhere else — and hashes
every file it ships, excluding `__pycache__/` and compiled `*.pyc`/`*.pyo`
(interpreter-dependent, not shipped).

The hash is length-framed per entry:

```
h.update(len(relpath_bytes).to_bytes(8, "big")); h.update(relpath_bytes)
h.update(len(content).to_bytes(8, "big"));       h.update(content)
```

so that no rename or content shuffle can produce a colliding byte stream, and
entries are visited in sorted POSIX-relative-path order so the digest is
independent of filesystem walk order.

**Why a source digest and not the git sha.** The git sha is unavailable in the
adopter case (no `.git` under `site-packages`) — that is the defect. The
digest is computable from any install form: wheel, sdist, editable, or a
directory someone edited by hand. And it has the property the finding asks
for: it moves *iff* the shipped source moves, which is the only way gate
semantics can move.

**Why it covers all shipped files and not just `.py`.** A package-data file
mlkit ships can change behaviour; `.py`-only would leave a gap that reads as
coverage.

### 2. The compared token

```
<version>+src.<first 12 hex of the digest>
```

e.g. `0.5.0+src.4f2a91c0be3d`. One token, one operand, one comparison. The
VCS commit recorded in the installed distribution's `direct_url.json` is
reported *beside* it as context and is **not** part of the compared token,
because it can differ between builds whose shipped source is byte-identical,
and because it records the commit *requested at install time* — it does not
move if someone edits `site-packages` afterwards. The digest does. The digest
is authoritative; `direct_url.json` corroborates.

The `direct_url.json` read is tied to the running module: the distribution's
own location must contain the package root we hashed. If it does not — two
installs, a stale `.dist-info`, a namespace shadow — the VCS field reports the
disagreement rather than the metadata.

### 3. Emitted into every report header mlkit writes

One canonical line, one prefix constant, one emitter:

```
- measured by mlkit: `0.5.0+src.4f2a91c0be3d` (…files under …; vcs …)
```

Call sites: `readiness.md` (R8), `reports/fabricated_defaults.md` (R10),
`reports/fabricated_targets.md` (R11), `reports/served_contract.md` (R12), the
`*.UNMEASURABLE.md` refusal file, `portfolio/FLEET_VERDICTS.md`
(`mlkit portfolio`), and the `mlkit spine` report. A test asserts the line is
present in the output of every one of those writers by *calling them*, not by
grepping for a literal.

### 4. The adopter-side check

`resilient_mlkit.verify_report_identity(path_or_text)` parses the stamp out of
a report and compares it against `build_identity().stamp`. Five verdicts, and
the three that are not MATCH/MISMATCH exist because reporting either of those
from an unknown operand would be a fabricated answer:

| verdict | meaning |
|---|---|
| `MATCH` | the report names the identity of the installed dist |
| `MISMATCH` | it names a different one — the report was written by another build |
| `UNSTAMPED` | the report carries no identity line at all (pre-`0.5.0`) |
| `CONFLICTING` | the file carries two stamps that disagree |
| `INDETERMINATE` | one side's digest is unknown; no equality is asserted |

CLI: `mlkit identity` prints the installed identity; `mlkit identity --verify
PATH…` checks report files and exits non-zero unless every one is `MATCH`.

## The control pair, stated before it is written

* **POSITIVE (must FIRE).** Two package trees identical except for one byte
  inside `checks/readiness.py` produce two different digests, and a report
  stamped by the first is `MISMATCH` against the second. This is the measured
  defect in miniature: same `__version__`, different gate source.
* **NEGATIVE (must stay SILENT).** A report stamped by a tree, checked against
  that same tree, is `MATCH`; and a copy of the tree that differs only in
  `__pycache__` content and file mtimes is `MATCH` too — the digest must not
  move for reasons that are not gate semantics.
* **CHECK-NOT-DEAD.** Reverting the emitter (dropping the stamp line from a
  report writer) and reverting the digest (making it constant) must each fail
  named tests. A control that cannot die has not been shown to be alive.

## What this does not close

It does not repin any adopter. `fray`'s `pyproject.toml` still names
`c65b2e7`, and repinning is a change in fray with its own verifier. What this
buys is that after the repin — or without it — every report fray writes says,
in its own header, which mlkit measured it, and `mlkit identity --verify` can
say whether that is the mlkit installed now.
