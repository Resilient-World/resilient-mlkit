# M-5 — refuse to write an artifact that names a machine path; record mlkit by identity: PREREGISTRATION

**Written 2026-09-04, BEFORE any code on this branch. First commit of
`feat/v3-m5-machine-path-refusal`, based on M-2's head `611043a` (PR #48).**
Plan item: `sota-plan-v3.md` §7 M-5.

## The defect, measured (not recalled)

* fray: 42 committed artifacts across 14 deleted scratch clones name
  `/private/tmp/claude-501/…/scratchpad/<clone>/src/validation/__init__.py`
  (fray E-069; the test `test_every_module_binding_resolves_inside_this_tree`
  could only ever pass on the author's machine). fray built
  `src/validation/module_bindings.py` (repo-relative path + sha256; an
  out-of-repo module identified by distribution/version/VCS commit/digest) —
  in one repo.
* The two most important artifacts in the fleet tonight, measured in this
  session's scratchpad with a path walk:
  `e056-hardstops/reports/benchmarks/foundation_finetune.json` carries **7**
  absolute-path strings (`/hard_stops/mlkit_build/resolved_from`,
  `/hard_stops/modules_measured/resilient_mlkit`,
  `/hard_stops/pre_registration_statement/path`,
  `/provenance/modules_measured/resilient_mlkit`,
  `/modules_measured/resilient_mlkit`, `/fits/…/checkpoint_dir`, …);
  `ccrun/reports/benchmarks/foundation_cross_corridor_ladder.json` carries
  **3**. A reader cannot resolve any of them.
* **mlkit's own share of it:** `core.identity.BuildIdentity.to_dict()` emits
  `"root": <absolute package directory>` and `context_line()` renders it into
  the header of every report mlkit writes ("in `/private/tmp/…`"). The
  identity's whole point is the length-framed sha256 stamp; the directory is a
  fact about one machine.

## What changes (fixed now)

1. `core/module_bindings.py` — fray's module becomes mlkit's (rule 7): `record(modules,
   root=, repo_local=, subtree_of=)` binds every module to `{inside_repo,
   repo_relative_path, sha256}` (or, out of repo, to distribution / version /
   VCS commit / digest with `why_no_repo_relative_path`), refusing at the
   yield site a module with no `__file__` or a declared-repo-local module that
   resolved elsewhere; `problems(bindings, root=)` is the reader's half.
   Schema `resilient-mlkit/module-bindings/1`.
2. `core/artifact.py` — `write_artifact(root, relpath, payload)`: refuses, **by
   name, listing every JSON pointer**, a payload carrying a **machine path**:
   a string that is an absolute filesystem path and either **exists on this
   machine** or starts with a machine root (`/private/tmp`, `/tmp`, `/Users`,
   `/home`, `/var/folders`, `/opt`, `/root`, `/mnt`, `/srv`, a drive letter).
   JSON pointers such as `/hard_stops/x` are not filesystem paths and stay
   silent. The refusal message offers the blessed shape. It also refuses a
   `repo_relative_path` that does not exist on the tree at `root` (a string
   that looks right is not a binding) — through `module_bindings.problems`.
   Writes atomically (temp file + rename); never writes on refusal.
3. `core.identity.BuildIdentity`: `to_dict()` replaces `root` with
   `root_kind` ∈ {`site-packages`, `checkout`, `other`} and `root_name` (the
   basename); `context_line()` renders the kind and name, never the directory.
   `stamp`, `source_sha256`, `vcs_commit` are unchanged — the identity is the
   identity.

Nothing else moves; no check changes verdict.

## Acceptance — controls fixed before the code

| id | direction | fixture | required |
|---|---|---|---|
| P1 | FIRES (the committed offenders) | the two scratchpad artifacts above, re-produced through `write_artifact` | **refused**, the message listing at least `/hard_stops/modules_measured/resilient_mlkit` for both and `/fits/chronos2-ft-lr1e-6/checkpoint_dir` for the fine-tune; recorded by `scripts/m5_offenders_drive.py` → `reports/M5_OFFENDERS_DRIVE.json` |
| P2 | SILENT (the blessed shape) | the same payload with `modules_measured` replaced by `module_bindings.record(...)` output and mlkit by `build_identity().to_dict()` | **written**; bytes round-trip; `problems()` on the written bindings is empty |
| P3 | FIRES | a `repo_relative_path` that is not a file on the tree | refused naming it |
| P4 | SILENT | JSON pointers (`/hard_stops/x`), URLs, POSIX-looking strings that neither exist nor start with a machine root | written |
| P5 | FIRES | an absolute path that EXISTS on this machine but under no listed machine root (`tmp_path` itself) | refused (existence is the stronger signal) |
| P6 | IDENTITY | `build_identity().to_dict()` | no value is an absolute path; `stamp` unchanged from the pre-branch value on the same tree; `context_line()` contains no `/` path |
| P7 | CHECK-NOT-DEAD | `machine_paths()` with the machine-root list emptied and existence disabled | P1's payload is written — the discriminator is what refuses |

**Falsifier:** if P6 changes `stamp` on an unchanged tree, the identity was
reading the directory and the change is not cosmetic — stop.

## What is NA, said now

The 42 fray artifacts and the two chokepoint artifacts are **not regenerated
here** (their producers' inputs — gridMET cache, the pinned parquet, the
fine-tune checkpoints — are not on this machine, and regeneration is each
repo's own change). They are listed as offenders by measurement; the plan's
`KNOWN_UNREPAIRED` list is the adopters' (V3-11).
