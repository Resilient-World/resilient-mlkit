# Fleet method lessons

**What this is.** Eighteen measurement and process failures that this fleet has
already paid for, written down so the next engineer does not pay for them again.
Every one was found by driving something, not by reasoning about it; several
were found only because a control fired, and two were found only because a
number that nobody was watching moved.

**Why they live in `resilient-mlkit`.** These are METHOD lessons, not repo
facts. They apply to any repo that measures a model behind a gate, and mlkit is
the one package every model repo depends on, so it is the only place a lesson
can be written once. Repo-specific results live in each repo's own
`docs/CAMPAIGN_2026-09.md` and `docs/ESCALATIONS.md`.

**How to read an entry.** Each is: the lesson in one line, what it cost, and the
concrete practice that prevents it. The practice is the part to copy. Where a
figure appears it was measured; nothing here is reconstructed from memory.

**Companion documents.** `docs/CONTENDED_MEASUREMENT.md` is the binding rule for
§7-§9 below. `docs/MERGED_TREE_DRIVE.md` is the binding rule for gate reports.
`docs/BUILD_IDENTITY.md` and `docs/S5_REGISTER_FLEET_CHECK.md` cover the
instrument-identity and cross-repo-invariant material referenced in §14 and §16.

---

## Part 1 — A check that passes is not evidence

### 1. A check that cannot fail measures nothing

**Lesson.** Before believing a green check, establish that the invocation you
ran is capable of going red. An exit code of 0 from a command that found
nothing to examine is indistinguishable from an exit code of 0 from a command
that examined everything and approved it.

**What it cost.** An allowlist verification was run from inside a checkout
without the `--root` argument that tells it where the fleet's checkouts are. It
printed NOTHING and exited 0 — on a working tree whose allowlist was
uncommitted and therefore not validly signed at all. Re-run with `--root`
pointing at the directory that CONTAINS the checkout, the same command printed
`INVALID — allowlist has uncommitted changes; a signature is only meaningful
against a committed file` and exited 1. Had the first reading been taken as a
pass, an unsigned allowlist would have been reported as verified.

The same investigation found the second half of the trap: two control arms that
deliberately corrupted the signature digest could not be driven through the CLI
at all, because the signature check short-circuits on "uncommitted changes"
BEFORE it reaches the digest comparison. With no commit, the CLI cannot tell a
corrupted digest from an uncommitted file. Those arms had to be driven at the
library level, against the same predicates the CLI calls.

**Practice.** For every check you rely on, drive a LIVENESS ARM first: make the
subject deliberately wrong and require the check to fail. Record the failing
output beside the passing one. If you cannot construct a failing arm through the
interface you are using, say so and drive it one layer down — and record which
layer, because a control driven at a different layer from the one in production
is weaker evidence and the reader must be able to see that.

### 2. A green suite is not evidence that the controls in it are alive

**Lesson.** Tests that stop running are worse than tests that fail: a skip is
silent, and a suite full of skipped controls is indistinguishable from a suite
full of passing ones at the level of "did it go green".

**What it cost.** A fixture landed hours earlier read the block it compares
against from `origin/main`. Once the change it was guarding actually landed on
main, the fixture's premise became true, and SIX CONTROLS BEGAN SKIPPING —
quietly, with the suite still green. It was found only because a suite arm read
14 skipped where the baseline arm read 7, and somebody compared the skip counts.
Worse, before that the fixture fell back to the LOCAL main ref, so a stale clone
still PASSED: the same commit read 39 passed / 0 skipped in one clone and five
skips in another.

**Practice.** Three rules, all of which came out of this one defect:
* A fixture must read the fact it needs from THE ARTIFACT'S OWN HISTORY —
  resolve a merge-base at run time, or construct the prior state — and never
  from a moving ref (`origin/main`, a branch head, `HEAD~1`).
* Where history is unreachable, CONSTRUCT the prior state rather than skipping.
  Prove it in a real `git clone --depth 1`, which is the environment where a
  history read fails.
* COMPARE SKIP SETS BETWEEN ARMS, not just failure sets. A control that stops
  measuring is a regression, and the skip count is the only place it shows.

### 3. A fixture id that a real admission makes real will be shadowed

**Lesson.** A test fixture that APPENDS a row under an id it borrowed from a
real document stops testing anything the moment that id is genuinely admitted.

**What it cost.** A control suite appended a fixture row at status ALLOWED,
under an id read from a proposal document. The id was absent from the live
document, so the appended row was the only one and the control worked. When the
id was later admitted for real at a different status, appending produced two
rows with the same id — and the resolver takes FIRST-WINS, so the real row
shadowed the fixture's. Three CHECK-NOT-DEAD arms started receiving `None` where
they expected an entry and turned red. The refusal being guarded was intact
throughout; what was lost was the POSITIVE control, without which, in the test
file's own words, a refusal "is equally consistent with a gate that refuses
everything".

**Practice.** A fixture id must be guaranteed absent from the live document —
generate it, or assert its absence in the fixture and fail loudly if the
assertion breaks. Never borrow an id from a document that a decision could make
real. And when a document your fixtures read is about to change, re-drive the
positive arms, not only the refusal arms.

### 4. When a check fires, establish whether the TREE is wrong or the CHECK is

**Lesson.** A firing check is a claim, and it is subject to the same evidence
standard as the thing it is checking.

**What it cost.** A duplicate-id predicate reported a new duplicate introduced
by a merge. Measured: the main side had zero occurrences of that id, the branch
side had two, the merged tree had two — a raise and its resolution, entirely the
branch's own, and the merge introduced nothing. The predicate was comparing the
merged tree's duplicate set against MAIN's duplicate set only, while each side
carried a DIFFERENT pre-existing duplicate set. Waving it through would have
been wrong; so would have been "fixing" the tree.

**Practice.** The corrected predicate is the general one:
`new = merged_dups − (main_dups ∪ branch_dups)`, plus "no id present on a side
is missing from the merge" and "no id's count exceeds the maximum of the two
sides". More generally: a check computed against ONE side of a merge is not a
check on the merge.

---

## Part 2 — What you measured is not what you think you measured

### 5. Measure under the pin the repo DECLARES, not the one your venv happens to have

**Lesson.** A repo's declared dependency revision is part of the tree under
test. Measuring under a different build measures a different repo.

**What it cost.** A repo's main was believed to have five pre-existing test
failures. Re-driven under the mlkit revision the repo itself DECLARES, main was
red in TEN places; the extra five pass only under the older build that happened
to be installed. Under the stale build `core.served` does not exist and the
repo's promotion gate fails to import at all — so the declared pin had become
load-bearing without anyone noticing, and every landing decision taken against
the five-failure baseline had been taken against the wrong instrument.

The same class bit twice more. A repo whose tag pin resolved to an old build
carried three committed reports THE DECLARED DEPENDENCY COULD NOT HAVE WRITTEN:
one check did not exist in that tree, another returned zero findings where the
committed report carried sixteen.

**Practice.** Resolve the declared pin and install THAT, per repo, per arm.
Where a report predates build self-stamping, date it forensically — establish
which revision COULD have produced it by re-running the producer from that
revision's package tree and comparing the output byte-for-byte — and state the
disagreement sharply if the answer contradicts the declaration, rather than
smoothing it.

### 6. An editable install beats `PYTHONPATH`… until it does not, so assert `__file__`

**Lesson.** A clone's tests will silently import a DIFFERENT tree's source, and
the failure mode is import errors that look like repo defects, or a green run
that measured the wrong tree.

**What it cost.** Every repo venv in this environment is an editable install
bound to a long-lived checkout, not to a clone. Running a clone's tests under
such a venv imports the checkout's packages — in one case a checkout 309 commits
behind the branch under test, producing a Frankenstein tree of new tests against
old source. Import errors of the form "cannot import name X from <repo
package>" were reported as repo defects three times before the binding was
checked. It was made worse by passing an EMPTY `PYTHONPATH` to "avoid a stale
one", which guaranteed the editable path won.

And the trap survives its own fix: on a later run, `PYTHONPATH` was set
correctly and the editable install still won, so one pass MEASURED ONE TREE FOUR
TIMES while reporting four distinct arms as successes.

**Practice.** Set `PYTHONPATH=<clone>/src`, and then do not trust it: before any
number is recorded, run
`python -c "import <repo package>; print(<repo package>.__file__)"` and assert
the path resolves INSIDE the tree under test. Assert it for the REPO'S OWN
package, not only for the shared kit. An unasserted binding is worth nothing in
either direction — it produces false greens as readily as false reds.

### 7. A suite that writes into its own workspace poisons the next run

**Lesson.** A test whose refusal path writes into the repository's real
directories is green once and red forever after, and it reads as a flake.

**What it cost.** A refusal path wrote a placeholder file into the repo's real
model-of-record directory. The first run in a fresh clone passed; every
subsequent run in that clone failed a loader test — four failures with one
cause, in a shape that invites "re-run it and see".

**Practice.** Refusal and error paths write to `tmp_path` or nothing at all. A
suite must be re-runnable in the same clone with an identical result; make that
an explicit check when a failure smells like a flake, because "it passed the
first time" is diagnostic information, not noise. And after any suite arm, run
`git status --porcelain` and require it to be clean.

### 8. Counts from different clones are not comparable; only the difference in ONE clone is

**Lesson.** Collection totals vary with provisioning. The comparison carries;
the absolute number does not.

**What it cost.** Two engineers measured the same main at 3 failed / 231 passed
and 3 failed / 201 passed — the SAME three failures by name, different
collection totals, because one clone had inputs staged the other did not. Time
was spent reconciling numbers that were never comparable. Elsewhere a branch was
held on a "+17 failures" reading taken against a head the repairing agent had
already moved past; every one of those 17 had been fixed by the time the reading
was reported.

**Practice.** Take both arms in ONE clone with ONE command, and report the
FAILURE-SET DIFFERENCE BY NAME (plus the SKIP-SET difference, per §2), not the
counts. Always say which HEAD SHA a number belongs to — a branch under active
repair is a moving target and a measurement of it expires the moment somebody
pushes.

---

## Part 3 — Verdicts that depend on the machine are not verdicts

### 9. A verdict that moves with machine load is not a verdict

**Lesson.** Wall-clock assertions under contention produce failures that are
indistinguishable from regressions, in both directions.

**What it cost.** The same tree, run twice, produced failure sets FIVE NAMES
apart — every difference a timeout boundary. A control that gives a child
process 10 seconds of wall time read a failure at load 14 (1196 s for a suite
that takes 635 s quiet) and passed on a quiet machine. A repo's 79-minute
"stall" and a "hung" report generation both vanished at low load. A three-stream
parallel plan produced a phantom failure that did not reproduce.

**Practice.** This is now a rule, not advice, and it is written in full in
`docs/CONTENDED_MEASUREMENT.md`:
* Suite arms for a by-name comparison run SEQUENTIALLY. A comparison between
  arms at materially different load is VOID and must be RE-MEASURED, not
  explained. A paragraph about why a failure was probably contention is not a
  measurement.
* Record a contention record per arm: load at BOTH ends of the span, cpu_count,
  this process's CPU time AND its reaped children's, wall, elapsed-vs-budget.
  Children matter because the defect is usually a test that SHELLS OUT, and the
  child's CPU is the whole signal.
* The classifier returns UNMEASURABLE — never PASS, and never a downgraded FAIL.
  UNMEASURABLE is an OBLIGATION: it satisfies no gate and forces a re-measure on
  a quiet machine.
* The declared limit, written before it was measured: a SLEEPING regression on a
  loaded machine is indistinguishable from waiting. That arm reads UNMEASURABLE,
  which is the honest answer and not a pass.

### 10. `@pytest.mark.timeout` in a file BEATS `--timeout` on the command line

**Lesson.** You cannot raise a per-test timeout for a contended arm from the
command line if the test file sets its own.

**What it cost.** Two suite pairs died at 17% because a thread-method timeout
fired; five by-name differences between two runs of the SAME tree turned out to
be per-test timeouts at the 120 s and 180 s boundaries under load, with the
command line's `--timeout=1800` overridden by the decorator in the file.

**Practice.** Where an arm must survive load, change the MECHANISM, not the
threshold: `-o timeout_method=signal` on EVERY arm, applied identically to both
sides. And know the mechanism's limit: a THREAD-method timeout cannot bound a
hang that holds the GIL — the watchdog thread never runs — so a GIL-holding
stall runs to the harness limit no matter what the timeout says. Prefer a
wall-clock budget the harness itself enforces for anything that can stall in C
code.

---

## Part 4 — Changing a record without changing a result

### 11. Distinguish WITNESSES from SUBSTANCE before you decide how to repair

**Lesson.** When a served artifact legitimately changes, the failures that
follow are not one thing, and treating them as one thing is what stalls a
landing.

**What it cost.** A served slot moved and 21 tests went red. Treated as one
problem, the change stalled for a day. Split on one question — does this test
record WHAT WAS READ AND WHEN, or does it make a claim about MODEL QUALITY? —
they separated cleanly: pins, ledger backfill digests and byte-identity
witnesses are STALE and are REGENERATED; guards that refuse because "the operand
behind every comparison has moved since it was read" are working as designed and
their ADJUDICATION must be redone on the new arm.

**Practice.**
* A WITNESS records what was read and when. It is regenerated under a
  preregistration, with a control proving the regeneration moves NO MEASURED
  FIGURE — leaf-by-leaf over the artifact, zero numeric leaves changed.
  Regenerating a witness is not adjusting a threshold.
* SUBSTANCE — a claim about quality — is RE-ADJUDICATED, under a
  preregistration written and committed BEFORE the run, with the acceptance rule
  fixed in advance and the outcome published whichever way it falls.
* Never fold the two into one change. The same discriminator settled a
  re-pinning question elsewhere: re-pinning a preregistered baseline is
  admissible ONLY where the artifact moved under a decided, unrelated change AND
  zero numeric leaves moved; otherwise it is outcome-driven amendment.

### 12. A control pinned to a branch head measures "has main moved"

**Lesson.** Any control anchored to a FIXED COMMIT drifts into measuring
something else the moment that commit stops being the branch point.

**What it cost.** A control pinned to the head of a pull request that has since
merged. With that head now an ancestor of main and four decided changes having
regenerated the files it watches, it reports a difference for every branch — it
measures "has main moved" rather than "has this branch touched the files it
guards". Three separate instances of this exact defect class were found in three
different repos in one campaign.

**Practice.** Pin a control to the SET OF FILES IT GUARDS and derive the base at
RUN TIME as the branch's own merge-base; compare BY CONTENT at base, HEAD and
worktree; and REFUSE when a base cannot be established rather than passing.
And the governance half: a control that blocks your own change must be repaired
by someone with no stake in its verdict — needing a control to pass is exactly
when you must not touch it.

---

## Part 5 — The environment will lie to you

### 13. Never kill by name pattern across a shared workspace

**Lesson.** Pattern-based process control kills things you did not mean to kill,
and killing a shell does not kill its children.

**What it cost.** A wait loop of the form `until ! pgrep -f "<pattern>"`
DEADLOCKED because the waiting shell's OWN command line contains the pattern.
Clearing the resulting stray watchers by name-matching killed a process whose
driver was named `run-arm.sh`, matching `-arm.sh`: another lane's baseline suite
arm, two and a half minutes in. Worse, the killed shell's pytest CHILD SURVIVED,
reparented to PID 1, and kept running against the tree the clone had since been
moved to — so BOTH arms were contaminated and both had to be re-driven from
scratch. Cost: roughly two hours on one repo.

**Practice.**
* Never wait on a `pgrep -f` pattern that the waiting shell's own command line
  contains. Wait on a pidfile, a sentinel file, or the log's summary line.
* Never kill by name pattern in a shared workspace. Kill only a PID you RECORDED
  at launch, and kill its PROCESS GROUP (`setsid` at launch, `kill -- -<pgid>`),
  so children cannot orphan.
* One clone per suite arm. Never `git checkout --detach` in a clone another
  process is measuring.

### 14. Never edit a shell script while it is running

**Lesson.** `bash` reads a script by BYTE OFFSET as it executes, so editing the
file under a running interpreter makes the tail execute as garbage.

**What it cost.** One baseline arm. The pytest child kept looking healthy while
the driver script's remaining lines were being read from the wrong offsets.

**Practice.** Copy the script to a new path, edit the copy, and launch the copy.
If a running driver needs changing, stop it by its recorded PID and process
group first (§13), then restart it — and treat everything it produced after the
edit as unmeasured.

### 15. `rsync` exclusions and recursion are both easy to get silently wrong

**Lesson.** Two independent `rsync` defects, both of which fail SILENTLY and
both of which corrupt a measurement rather than stopping it.

**What it cost.**
* `--exclude-from` paths are interpreted relative to the rsync SOURCE, not to
  the working directory. A file list generated as repo-relative paths excluded
  nothing at all, and the exclusion was a no-op nobody could see.
* `--files-from` does NOT recurse without an explicit `-r`. Eleven data stores
  staged EMPTY, and a repo's main read 16 failures instead of 15. That one was
  survivable only because both arms had been staged identically, so the
  comparison was not invalidated — but it was luck, not design.

**Practice.** Generate exclusion lists relative to the SOURCE
(`git -C <src> ls-files <dir> | sed "s|^<dir>/||"`). Pass `-a -r` explicitly
when using `--files-from`. And VERIFY STAGING PER PATH after it completes: assert
each expected store is non-empty, and distinguish "staging failed" from "empty
upstream" by checking the source too.

### 16. A gitignored DIRECTORY can contain TRACKED files

**Lesson.** `.gitignore` on a directory does not mean git tracks nothing inside
it, and staging inputs into such a directory can overwrite committed files.

**What it cost.** A data cache directory was gitignored, and TEN provenance
records inside it were tracked. Copying the directory from another checkout
overwrote a tracked provenance record with an older, DIFFERENT one — not merely
an older timestamp, but one recording a match on a different basis, with its
generation date going backwards four days. A provenance record silently replaced
by a stale one that matched on a different basis is precisely the class of defect
this fleet exists to catch. It was caught by a dirty-tree check before any push;
blast radius verified zero by `git log` over the directory. The same trap fired
twice more: once on a different repo's manifest, and once at TEARDOWN, where an
`rm -rf` of the staging directory deleted the ten tracked files.

**Practice.** Before staging into any gitignored directory, run
`git ls-files <dir>` and exclude those paths (§15), or restore them afterwards
file by file. After staging AND after teardown, require
`git status --porcelain | grep -v '^??'` to be EMPTY before trusting any
regenerated artifact. Never repair a contaminated staging with a blanket
`git checkout -- .` — that discards uncommitted work as well; restore the named
files.

---

## Part 6 — Facts about other trees

### 17. Assert facts from `origin/main`, never from a long-lived local checkout

**Lesson.** A checkout that has been sitting on a workstation is stale by weeks,
and a premise taken from it is wrong in a way that survives careful reasoning.

**What it cost.** This premise error was made TWICE in one night.
* A repo was reported as declaring no dependency on the shared kit at all,
  because the reading was taken from a local checkout two weeks behind
  `origin/main` and predating the commit that added the declaration. The
  conclusion — "this repo needs a new dependency" — was wrong; it needed the
  same pin change as its siblings, and the fleet split was five/three, not
  six/three.
* A repo was reported as pinning by tag. On `origin/main` it had been re-pinned
  to a revision two days earlier, and its committed reports named the newer
  build. The change that resulted therefore added no pin move at all — it added
  the CHECK that keeps the pin.

**Practice.** `git fetch` and read `origin/main` (or `git show
origin/main:<path>`) for every fact about another tree. Never read a fact out of
a checkout you did not just fetch, and never read one out of an installed
package. State the premise you are acting on and the ref you read it from, so a
correction is cheap.

### 18. A tag pin is a branch pin wearing a version number

**Lesson.** A tag is movable, so pinning a dependency by tag gives you the
mutability of a branch with the appearance of a release.

**What it cost.** Two repos pinned the shared kit by tag. One tag resolved to a
build in which a module the repo's own committed reports name DOES NOT EXIST,
and under which the repo's promotion gate raises `ModuleNotFoundError` on
import — the repo did not import under its own declared dependency. The
practical proof was cheap and decisive: one `uv lock` moved two repos to a
version released that night, with nobody deciding to take it. An instrument that
arrives without a decision is the opposite of a pin.

**Practice.** Declare dependencies by IMMUTABLE FULL SHA. Add a both-ways test
that FAILS if the declaration reverts to a branch OR a tag, with a FAIL-CLOSED
key allowlist (a denylist of `branch`/`tag` holds only while the packaging tool's
vocabulary does). Prove it with the re-lock: run the lock under each pin kind and
show that `branch` and `tag` move while `rev` stays put. Moving a pin is an
INSTRUMENT CHANGE and needs its own decided change with an A/B on every gate row,
per repo — not a side effect of a lockfile refresh.

---

## Part 7 — A check that cannot report what it owns

### 19. A gate that prints a failure and exits 0

**Lesson.** The printed text and the exit status are two separate claims, and a
command that prints a failure while returning success has already been believed
by something. §1 says drive a failing arm before you trust a passing one; this
is the half §1 does not cover — the arm fires, you can watch it fire, and the
caller still reads a pass.

**What it cost.** `mlkit allowlist verify` returned 0 on an UNSIGNED allowlist
while printing the failure. Rule 14 makes the signature the determination — the
agent proposes, the human signs — so the one command whose whole job is to say
whether those determinations hold was returning success on their absence. The
same command returned 0 with ZERO lines on stdout and zero on stderr when
`--root` named a directory holding no `resilient-*` checkout, or `--repo` named
a repo that was not cloned there: silence and success, indistinguishable from a
pass. `mlkit notice` printed ``REFUSED — NOTICE.md exists … and was not
generated by mlkit`` and returned 0 — and R9's own remedy text sends an agent
into that command, which makes its exit status a gate whether or not anyone
declared it one, so `mlkit notice && git commit -am "regenerate"` committed
nothing and reported success. `mlkit keys` said "Nothing in the portfolio is
waiting on a key" from a root under which it had read nothing.

**And the correction is the part worth carrying.** The clause this lane was
handed said that flipping one character of `entries_sha256` prints INVALID and
RETURNS 0. It does not, and did not before the repair: driven against the
process it returns 1. **The 0 came from a pipeline.** `mlkit allowlist verify …
| head` and `… | tee` both report `$?` = 0, because the shell reports the LAST
stage's status, not the command's. The verification that produced the original
reading was measuring the pipe. That is now arm **C2P** in
`reports/E_M43_ALLOWLIST_EXIT_ARMS.json`, so the distinction is a measurement
rather than an argument, and the withdrawal is written into `CHANGELOG.md`
(v2.2.0), `docs/ESCALATIONS.md` (E-M43) and the test's own docstring — replaced,
not quietly dropped.

**Practice.**
* **Never read an exit status through a pipe.** `cmd | head` reports `head`'s
  status. If an arm must page, tee or filter, capture the status first
  (`cmd > out; rc=$?`) or set `pipefail` and read `PIPESTATUS`, and say in the
  record which you did. A verification harness that pipes a gate into anything
  is measuring the pipe.
* Assert the EXIT STATUS in the same control arm that asserts the TEXT, for
  every branch the command can print. The ten arms in
  `reports/E_M43_ALLOWLIST_EXIT_ARMS.json` do this, including two CHECK-NOT-DEAD
  arms that re-drive the fixed conditions against the pre-repair source and
  require the old, wrong answer.
* Give "nothing was read" its OWN code, distinct from "something was read and it
  is bad" — they are different problems with different fixes. mlkit now exits 1
  for the second and 2 for the first, and the refusal says what was not done
  rather than only what was not found.
* When a guard exists in five separate copies, the command that is missing it is
  the one you have not read yet. Five subcommands carried their own
  empty-selection guard and `allowlist` carried none; there is now one
  definition (`_refuse_empty_selection`, `NOTHING_MATCHED_EXIT` in
  `src/resilient_mlkit/cli.py`) used by all seven and asserted for all seven by
  one parametrised test.
* **An exit-code change is not a verdict change, and that is a claim to
  preregister rather than to explain afterwards.** Zero row movement was written
  into `reports/E_M43_M44_GATE_DEFECT_PREREGISTRATION.md` §3 before the drive;
  measured over eight adopter remote mains, five phases each, **272 adjudicated
  rows, 0 added, 0 removed, 0 statuses moved, 0 reasons moved**, with two
  independent `origin/main` drives an hour apart agreeing on all 272.

### 20. A gate that `return`s before a leg it owns

**Lesson.** A check that owns two obligations and reports the first finding it
reaches is not a check that sometimes under-reports. Its second obligation is
unmeasured on exactly the repositories most likely to be in breach of it,
because a repo that fails the first leg is the one that never reaches the
second.

**What it cost.** `r9_licence_gate` checks that no source in the manifest is
unlisted, BLOCKED or EVAL-ONLY **and** that every attribution obligation in the
signed allowlist is rendered into `NOTICE.md`. **Six `return`s** stood between
the top of the function and the NOTICE block, so the second leg was unreachable
on any repo with a finding in the first. Measured against the eight adopter
remote mains with mlkit's own `policy.render_notice`, at each repo's own pin
(table in `CHANGELOG.md`, v3.0.0):

```
torrent    38 sections on disk / 48 obligations   10 missing
surge      24 / 36                                12 missing
triage     11 / 21                                10 missing
blackout    6 / 11                                 5 missing
arabica    34 / 34                                 0 missing, text drift
```

**Thirty-seven undischarged attribution obligations across four repositories,
none of them visible in the check that owns them** — unmet licence conditions,
not formatting. Only triage's R9 reached the leg at all, and only because its
manifest leg happened to be clean in its own environment.

**Practice.**
* Compute EVERY leg a check owns first and unconditionally, then fold them into
  one verdict. Reachability, not precedence: anything computed after a `return`
  is one refactor away from being unreachable, and this one already was.
* A leg that needs nothing must run when the other leg could not be measured at
  all. `policy.notice_gap` needs no binding, no import of the repo's code and no
  data, so "this interpreter cannot import pandas" does not make an undischarged
  obligation unknowable. A measured breach beside an unmeasured leg is **FAIL**
  whose reason names the leg that was not measured; NA would erase the half that
  WAS measured, which is the collapse `core.result.Status` refuses by name.
* Order the reason by what was NEWLY made visible. Reasons are truncated
  (`core/result.py`, `MAX_REASON` = 400), so putting the newly visible half last
  is the same defect a second time. Driven: a 40-source manifest finding renders
  a 397-character reason ending `…[truncated]` with the NOTICE clause and its
  count intact at the head.
* **A check that grows a new way to fail must be shown NOT failing everything
  else it touches, and BYTE-IDENTICAL is the only version of that claim worth
  making.** Arms N2 and N7 in `reports/E_M44_R9_BOTH_LEGS_ARMS.json` require the
  new check's reason on an unaffected fixture to be byte-identical to the old
  check's. The fleet A/B: 272 rows, 0 added, 0 removed, 3 statuses moved and 2
  reasons — every one of the eight per-repo outcomes written into the
  preregistration before the drive, and all eight matched.
* **Check that your negative controls are actually negative before you read the
  positive ones.** The first E-M44 drive committed the allowlist and the NOTICE
  together, so signature verification saw an uncommitted allowlist, the renderer
  emitted its UNSIGNED provisional trailer, and N2, N4 and N7 all came out
  stale — the repair appearing to fire on the three arms that exist to pin it
  NOT firing. A fixture defect will imitate a successful repair.

### 21. An obligation nobody measures is not an obligation

**Lesson.** The distance between "the licence says attribute" and "something
goes red when we do not" is where an unmet condition lives — indefinitely, in a
committed file, with every suite green.

**What it cost.** At the moment §20's early return was found, **37 attribution
obligations were outstanding across four repositories.** Every one was recorded
in that repo's OWN signed `docs/allowlist.yaml`; not one had been rendered into
its `NOTICE.md`; and nothing anywhere failed. They were discharged to **0** by
running the generator at the revision each repo already pins — merged as
`resilient-arabica` #175, `resilient-blackout` #145, `resilient-triage` #108,
`resilient-torrent` #210 and `resilient-surge` #86. Re-driven from fresh clones
of the five merged mains: obligations 34/11/21/48/36, sections 34/11/21/48/36,
**missing 0 on all five**, each committed `NOTICE.md` byte-equal to the
rendering.

Doing it turned up three things the count alone would not have:

* **A generated file that had been hand-edited.** blackout's commit `f7dd18c`
  replaced the generator's single `- Licence:` line under
  `## ornl-eagle-i-outages` with two lines of its own, in a file whose own header
  says edits are overwritten. Regenerating restored what the signed allowlist
  actually records — and the substance was not lost, because that entry's licence
  URL is carried in its attribution text as well.
* **Values stale since a named commit.** torrent's `NOTICE.md` still carried
  three retrieval dates and one licence URL from before commit `8f74454` (its
  E-060 allowlist sweep, "ten sources re-read from their own licences") changed
  the determinations under it. The allowlist moved; the notice was never
  regenerated; nothing noticed. Every replacement was read back out of the signed
  entry's own `licence_url` / `retrieval_date` rather than typed.
* **Entries whose kind the vocabulary has no true value for.** surge's
  `neuralgcm-source` and `nvidia-physicsnemo-corrdiff-source` are signed
  `kind: code` — deliberate CODE-ONLY determinations, each separating Apache-2.0
  source from weights under a different licence — and mlkit's `Entry` admits only
  `data` and `weights`, so a CORRECT determination renders as a structural defect.
  Escalated as E-051 in `resilient-surge/docs/ESCALATIONS.md` and not edited: the
  field is signed and rule 14 reserves it. Same class of gap as R10's vocabulary.

And what did NOT happen: triage's R9 went FAIL → PASS **by root cause** (the
whole finding was this), while arabica's, blackout's, torrent's and surge's
pre-existing manifest or structural findings stayed byte-identical and still
FAIL. No check was made green that should not be green.

**Practice.**
* For every obligation you accept — licence, retention, disclosure — name the
  ARTIFACT that discharges it and the CHECK that reads that artifact. If no check
  reads it, the obligation is a sentence in a document.
* **Regenerate the discharging artifact BEFORE landing the check that would name
  the gap.** The obligation is then met before anyone is told it was unmet, and
  the two changes stay separable: none of the five repos moved its mlkit pin.
* Prove the generator is stable across the versions in play before running it in
  anger, and prove it TWICE. The function's source segment hashing identically at
  0.1.0, 0.5.0, 0.6.0 and v3.0.0 (sha256 `40791153…`) was not enough on its own,
  because the rendering also depends on everything it reads; the deciding
  measurement was each repo's OWN rendering hashed at its pin and again at
  v3.0.0.
* When a correct determination cannot be expressed in the tool's vocabulary,
  escalate the VOCABULARY. Do not edit the determination to fit it.
* A repair that discharges one obligation must leave every other finding at full
  strength, and you should be able to say so by name.

## Part 8 — The harness is an instrument too

### 22. A harness that reports success having measured nothing

**Lesson.** Two portability traps, hit in one verification pass, both the same
shape: the harness completed, printed its marker, and had measured nothing. A
driver's exit is not evidence that its work happened.

**What it cost.**
* **BSD `sed` does not support `\?` in a basic regular expression.** A control
  arm whose job was to CORRUPT a signature digest corrupted nothing. The gate
  under test then read exactly what it reads on a clean tree, and the gate looked
  LIVE when it had never been tested — the §1 liveness arm, defeated by the tool
  that was supposed to drive it. Redone in Python.
* **`zsh` does not word-split an unquoted parameter.** A driver loop of the form
  `for spec in "surge 8517341d"; set -- $spec` passed `repo="surge 8517341d"` —
  the whole string — as the repository name. Every drive in the loop failed on a
  name no repo has, and the loop still printed its `ALLDONE` marker at the end.
  Moved into `#!/bin/bash` scripts.

Both were caught inside the fleet's own tooling rather than in a repo, which is
the only reason they are recoverable at all: a corrupted-digest arm that
corrupts nothing produces a PASS, and a pass is what everybody wanted to see.

**Practice.**
* **A mutation control asserts that the bytes CHANGED, and refuses to proceed if
  they did not.** "I ran a `sed`" is not evidence that anything moved. Every
  fixture mutation in the two gate-defect lanes that followed is applied in
  Python and refuses a no-op, for this reason.
* **A driver's success marker must be the CONJUNCTION of its items' successes,
  not the end of its loop body.** Count what you drove, require the count, and
  make the loop exit non-zero when any item did. The same lanes replaced shell
  loops with a Python `for` over a dict.
* Do not write measurement drivers in an interactive shell's dialect. Put them in
  `#!/bin/bash` or Python and pin the interpreter in the shebang: the difference
  between shells here is a silent semantic, not a syntax error, and the machine
  you develop on is not necessarily the machine that runs the arm.
* Prefer the language that lets you ASSERT over the language that gives you the
  one-liner, anywhere a control's own correctness is load-bearing.

### 23. A contention classifier is only worth having if a clean run can show it staying silent

**Lesson.** §9 gives UNMEASURABLE the power to void a reading. A rule that has
only ever been observed FIRING is indistinguishable from a rule that fires on
everything; what completes it is a full, clean pass in which it stays silent and
every reading survives, recorded with the same care as the readings that voided.

**What it cost.** Nothing — and that is the entry. The 2026-09-07 independent
verification pass drove nine repositories from full fresh clones, every arm
SEQUENTIALLY, recording `load1` at BOTH ENDS of every span against `hw.ncpu` =
**10**. Every reading fell between **1.62 and 4.12**, i.e. **0.16–0.41 ×
cpu_count**, against a predicate that voids a reading at
`load1 >= 1.0 × cpu_count`. **No reading in that pass was void and none needed
re-measuring.** The two gate-defect lanes that followed read 2.1–3.1 (0.21–0.31 ×
cpu_count) at both ends of every span, and the five-repo licence lane 0.18–0.33 ×
cpu_count. In that last one, two readings were RE-MEASURED rather than explained:
a staging artefact of the lane's own making, and a live-network test that flips on
both trees — driven eight times, four per tree, and settled by running a fourth
main arm so the landing pair was exactly equal rather than argued equal.

**Practice.**
* Record the contention record on the PASSING arms too, not only on the ones you
  suspect. A load figure that is never taken when the answer is "quiet" cannot
  establish that the classifier discriminates.
* State the PREDICATE and the measured MARGIN in the same sentence, so a reader
  can see how far from void a reading was rather than being told it was fine.
* Keep §9's rule intact when it costs you something: re-measure, never
  re-explain. Running one more arm is cheaper than a paragraph arguing that a
  reading was probably clean, and it is the only one of the two that is evidence.

---

## The short form

If you read nothing else:

1. Drive a failing arm before you trust a passing one.
2. Compare failure sets AND skip sets, by name, in one clone.
3. Assert the tree under test is the tree being imported, and the pin under test
   is the pin declared.
4. Run comparison arms sequentially; a verdict that moves with load is not a
   verdict.
5. Regenerate witnesses; re-adjudicate substance; never fold the two together.
6. Kill recorded PIDs and their process groups, never patterns.
7. Read facts from `origin/main`, and pin by immutable sha.
