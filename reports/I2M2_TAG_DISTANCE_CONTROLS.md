# I2-M2 — controls for the version bump and the tag-distance check

Everything here was DRIVEN. Nothing is reconstructed, and every command is
written out so it can be re-run. Retrieval date for all GitHub reads:
**2026-09-01**. All local measurements are stamped in UTC.

Three trees are involved and they are named the same way throughout:

| name | sha | what it is |
|---|---|---|
| **tag** | `8517341` | the commit the annotated tag object `15a188b` (`v0.5.0`) points at |
| **base** | `6921e9a` | `origin/main` at the moment this branch was cut |
| **head** | this branch | tag-distance check + bump + CHANGELOG + ci.yml header |

Both mlkit environments were made identical before any comparison:
`pip freeze | grep -v '^-e '` is byte-equal between the base venv and the head
venv, so the only difference between the two runs is the package under test.
That equalisation is not cosmetic — a first attempt at CONTROL B produced large
apparent verdict differences that were entirely caused by `numpy` being absent
from one venv and present in the other.

---

## The committed baseline this branch was cut from

Measured in a fresh clone of remote `main` before any edit:

```
git rev-list v0.5.0..HEAD --count            ->  36
git diff --shortstat v0.5.0..HEAD            ->  21 files changed, 5438 insertions(+), 97 deletions(-)
git diff v0.5.0..HEAD -- CHANGELOG.md        ->  (empty)
git show v0.5.0:src/resilient_mlkit/__init__.py | grep __version__
                                             ->  __version__ = "0.5.0"
git for-each-ref refs/tags                   ->  v0.2.0 -> 0a0ddac
                                                 v0.3.0 -> d08d85e
                                                 v0.5.0 -> 8517341   (2026-08-31)
```

There is **no `v0.4.0` tag** and there never was. The `v0.4.0` CHANGELOG
entry's "Not yet tagged" line was therefore TRUE, not false, and it is rewritten
to say what is measurable rather than corrected into a claim about a tag that
does not exist. Only the `v0.5.0` entry's line was false.

Two of the three tags declare a version other than their own name:
`git show v0.3.0:src/resilient_mlkit/__init__.py` reads `0.2.0`. That is E-M08
as committed, still visible from inside the tag, and it is why the new check
examines every release tag rather than only the newest.

---

## CONTROL A — must fire

### A1. Revert the bump alone; the check fails naming the tag and the diff

The only edit is `__version__` back to `"0.5.0"` on the branch head — the
CHANGELOG entry, the ci.yml header and the check itself all stay.

```
sed -i '' 's/^__version__ = "0.6.0"$/__version__ = "0.5.0"/' src/resilient_mlkit/__init__.py
.venv/bin/python -m pytest tests/test_tag_distance.py -q
```

```
1 failed, 11 passed
FAILED test_no_tag_declares_this_version_over_a_different_shipped_source
  this build declares 0.5.0 and so does a tag whose shipped source is not this
  source, so no artifact either of them writes can say which instrument
  produced it (docs/ESCALATIONS.md E-M08, one level up): v0.5.0 (declares
  0.5.0) differs from this build in 9 shipped path(s):
  src/resilient_mlkit/__init__.py, src/resilient_mlkit/checks/decision.py,
  src/resilient_mlkit/checks/readiness.py, src/resilient_mlkit/core/artifact.py,
  src/resilient_mlkit/core/fabricated_targets.py,
  src/resilient_mlkit/core/fabrication.py, src/resilient_mlkit/core/result.py,
  src/resilient_mlkit/core/served.py,
  src/resilient_mlkit/core/served_reimplementation.py.
```

The tag is named and every differing shipped path is listed. A second,
independent check fires on the same revert —
`tests/test_version_declaration.py` goes `1 failed, 16 passed` because the
newest CHANGELOG heading now names a version the code does not declare. The two
checks are not redundant: that one compares the version to the same tree, this
one compares it to the release history.

Restoring the literal returns both to green: `29 passed` across the two files.

### A2. The tag and this branch self-report DIFFERENT versions; the tag and pre-branch main did NOT

Three separate clones, three separate venvs, `resilient_mlkit.__file__`
asserted inside each:

```
v0.5.0 tag  (8517341)  ->  mlkit 0.5.0
origin/main (6921e9a)  ->  mlkit 0.5.0     <- the defect, in one line
branch head            ->  mlkit 0.6.0
```

### A3. In an adopter's install the version is the ONLY identity token

The eight model repos install mlkit from a pinned git ref into a venv, not as an
editable checkout. `cli._self_sha()` shells `git rev-parse HEAD` in the
directory the package was loaded from, so in that deployment there is no git
worktree to read. Installed non-editably from **base**:

```
pip install <mlkit>                     # NOT -e
mlkit portfolio --root <fixture> --json
  "mlkit_version": "0.5.0",
  "mlkit_git_sha": "",
```

So the artifact's only instrument token is the version string, and that string
read `0.5.0` for all three trees above.

**A defect found while checking this operand, NOT repaired here.** `_self_sha()`
asks git about a *directory*, not about mlkit. Put the same non-editable venv
inside an unrelated git repository and the artifact reports that repository's
head as mlkit's:

```
mkdir host && cd host && git init && git commit --allow-empty -m x
  host repo HEAD: 04f3757664f67e61b145becbc9b68f7335491bd5
python -m venv .venv && .venv/bin/pip install <mlkit>
.venv/bin/mlkit portfolio --root <fixture> --json
  "mlkit_git_sha": "04f3757664f67e61b145becbc9b68f7335491bd5"
```

That is a fabricated identity, and it is worse than the empty string because it
looks like an answer. It belongs to the open E-M24 build-identity work (PR #31
`fix/build-identity-e-054`, which owns `src/resilient_mlkit/cli.py` and
`core/identity.py`), so it is **recorded here and not touched**. A version bump
does not fix it and does not depend on it.

---

## CONTROL B — must stay silent

### B1. The suite

Same interpreter (3.14.6), same venv, `resilient_mlkit.__file__` asserted inside
this checkout:

| | result |
|---|---|
| branch point (`origin/main`, unmodified) | **3 failed, 909 passed** |
| branch head | **3 failed, 925 passed** |

`+16 = 12` new in `tests/test_tag_distance.py` and a net `+4` in
`tests/test_ci_workflow.py` (five controls added, one string assertion
replaced). **Zero pre-existing tests moved.**

The 3 failures are the SAME three rows on both sides, all in
`tests/test_torrent_model_of_record.py` (TR-3). They read a sibling
`resilient-torrent` checkout that this branch does not touch and that is not
part of this repo. They are environmental and pre-existing, and they are
reported rather than filtered out.

```
ruff 0.16.5 check src tests scripts   ->  All checks passed
mypy 2.3.1  src/resilient_mlkit       ->  Success: no issues found in 29 source files
```

### B2. Zero check semantics change, on a real fixture

Two byte-identical fixture roots (`diff -r` clean before either run), each
holding shallow clones of `resilient-arabica` (`36a4967`),
`resilient-chokepoint` (`1a905d2`) and `resilient-triage` (`806d4e0`) at their
remote mains. Base drove fixture A, head drove fixture B.

**CLI stdout**, after normalising only the run nonce, the fixture root path and
the version banner:

| phase | result |
|---|---|
| `check --phase readiness --offline` | **IDENTICAL** (59 lines) |
| `check --phase decision --offline` | **IDENTICAL** (38 lines) |
| `check --phase economics --offline` | **IDENTICAL** (38 lines) |

**Every file the two runs wrote**, whole tree, `.git/` and `__pycache__/`
excluded:

```
files compared:                                             2636
byte-identical after normalising run nonce and timestamps:  2633
still different:  resilient-{arabica,chokepoint,triage}/.mlkit/results/readiness.json
```

and the residue in those three is only the absolute fixture root (`i2m2-fixA`
vs `i2m2-fixB`) inside `write.path` / `write.refusal_path`. No verdict, reason,
evidence or count moved anywhere.

**`mlkit portfolio --json` and `mlkit spine --json`**, parsed and compared key
by key with the header fields lifted out:

| | portfolio | spine |
|---|---|---|
| `mlkit_version` | `0.5.0` -> **`0.6.0`** | `0.5.0` -> **`0.6.0`** |
| `mlkit_git_sha` | `6921e9a…` -> `1d16bc0…` | `6921e9a…` -> `1d16bc0…` |
| everything else | **identical** | **identical** |

That version field is the whole point of the change and the only intended
difference in any artifact.

### B3. `tests/test_version_declaration.py` under the new heading

`17 passed`, unmoved. Its two body assertions read the NEWEST entry, which is
now `v0.6.0`: the entry names **D3** — because D3 genuinely changes verdict on
unchanged repo code in this span, which `11a5bcd` states in its own commit
message — and it makes no denial of verdict movement.

### B4. The workflow still parses

```
yaml.safe_load('.github/workflows/ci.yml')
  jobs -> ['lint', 'tests', 'typecheck']
  jobs.tests.steps[0] -> {'uses': 'actions/checkout@v4', 'with': {'fetch-depth': 0}}
```

---

## The fleet-clone measurement quoted in the ci.yml scope note

Driven by me, not carried in from anywhere:

```
2026-09-02T01:06:40Z
for r in fray torrent chokepoint choco arabica surge blackout triage; do
  git clone --depth 1 https://github.com/Resilient-World/resilient-$r.git $r
done
real 24.53s   du -sh . -> 205M
fray 28M  torrent 23M  chokepoint 13M  choco 24M
arabica 16M  surge 75M  blackout 14M  triage 13M
```

This refutes the old scope note's ARGUMENT (that a portfolio/spine job is
impossible because the eight sibling checkouts cannot exist on a runner). It
does not establish that such a job should be written: that stays **NA** until
someone measures a sweep against a declared baseline. No job was added.

---

## What this branch does NOT do

* **It does not cut a tag.** `v0.6.0` does not exist and creating it is the
  signatory's.
* **It does not settle whether major on a `0.x` line is `0.6.0` or `1.0.0`.**
  That is open in E-M08. `0.6.0` is the `v0.4.0` entry's own minimal reading
  applied to `0.5.0`, and simultaneously the minor bump this file's policy
  requires as a floor.
* **It re-measures no adopter.** `portfolio/` is untouched and the per-repo
  consequences in the CHANGELOG entry are quoted from the commits that measured
  them when they landed.
* **It does not repair `_self_sha()`.** See A3.
