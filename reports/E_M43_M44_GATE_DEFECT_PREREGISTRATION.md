# E-M43 / E-M44 — PREREGISTRATION

Written and committed BEFORE any change to `src/`. Two gate defects of the same
shape: **a check that cannot report what it owns.** E-M43 is a command whose
exit status cannot carry two of the verdicts it prints. E-M44 is a check that
returns on the first of the two obligations it holds and never reaches the
second.

Everything below — the acceptance rules, the control arms, the version rule and
the expected fleet row movements — is fixed here so that the drive can only
confirm or refute it. Nothing in this file is a measurement; the measurements
land in `E_M43_M44_GATE_DEFECT_RESULTS.md`.

---

## 0. THE PREMISE, CHECKED BEFORE IT WAS ACCEPTED

The lane was handed one claim per defect. One of the four E-M43 clauses does
not reproduce on `main` and is recorded here as withdrawn rather than repaired,
because repairing a defect that is not there is how a control arm comes to pass
against nothing.

| clause as handed over | status on `main` at the time of writing |
|---|---|
| `mlkit allowlist verify` prints `INVALID` on a one-character `entries_sha256` flip and returns **0** | **NOT REPRODUCED.** It returns **1**. `cmd_allowlist` sets `rc = 1` on `parse_error`, and `_verify_signature` writes the digest mismatch into `parse_error`. Reproduced instead as a SHELL artifact: the same command in a pipeline (`… \| head`, `… \| tee`) reports `$?` of the LAST stage, which is 0. Same family as the two silent-failure traps the verification pass caught in its own tooling. |
| the same command exits 0 having matched NO repository, printing nothing | **REPRODUCES.** `--root` at a directory with no `resilient-*` checkout: no output, `rc=0`. Five other subcommands (`check`, `fleet`, `spine`, `notice`, `env`) already guard this with exit 2. `allowlist` does not. |
| an UNSIGNED allowlist | **REPRODUCES, and was not in the brief's proof.** `cmd_allowlist` prints `… entries, UNSIGNED` and leaves `rc` at 0. An unsigned allowlist is the state CLAUDE.md rule 14 exists for, and the command that reports it cannot fail on it. |
| `r9_licence_gate` returns before the NOTICE leg it also owns | **REPRODUCES**, `checks/readiness.py`, the four manifest returns (`unlisted`, `blocked`, `eval_only`) and the two earlier ones (`parse_error`, `defective_entries`) all precede the NOTICE block. |

So E-M43 repairs **two** live halves plus one that is already right and will be
PINNED by a control so it cannot regress, and records the third as a shell
trap rather than a tool defect.

---

## 1. E-M43 — ACCEPTANCE RULES

`mlkit allowlist verify` must make its exit status carry every verdict it
prints, and must never let "I matched nothing" read as "everything is fine".

* **A1.** Every repo's allowlist present, parsed, signed, no defective entry →
  exit **0**. Unchanged from today. This is the case whose exit code must be
  preserved.
* **A2.** Any repo's allowlist `INVALID` (including a one-character
  `entries_sha256` flip) → exit **non-zero**, with the reason printed and
  naming what does not match.
* **A3.** Any repo's allowlist **UNSIGNED** → exit **non-zero**. New.
* **A4.** Any repo's allowlist **MISSING** → exit non-zero. Unchanged.
* **A5.** Any repo carrying a **defective entry** → exit non-zero. Unchanged.
* **A6.** The invocation matched **NO repository** → exit **non-zero** AND a
  loud refusal on stderr naming the root that was searched. New.
* **A7.** The exit code must distinguish "the allowlists were read and one of
  them is bad" from "nothing was read". A bad allowlist keeps **1**; matching
  no repository takes **2**, the code `check`, `fleet`, `spine`, `notice` and
  `env` already use for the same condition.

### E-M43 CONTROL ARMS (committed as `reports/E_M43_ALLOWLIST_EXIT_ARMS.json`, driven by a script, read back by a test)

| arm | condition | required |
|---|---|---|
| **C1** | two repos, both valid and signed | rc **0** |
| **C2** | one hex character of `entries_sha256` flipped, verified to have mutated | rc **1**, output names `entries_sha256 does not match` |
| **C3** | `signature.signed: false` | rc **1**, output says `UNSIGNED` |
| **C4** | `docs/allowlist.yaml` absent | rc **1**, output says `MISSING` |
| **C5** | an entry with no `retrieval_date` | rc **1** |
| **C6** | `--root` at a directory with no `resilient-*` | rc **2**, stderr names the root |
| **C7** | `--root` valid, `--repo` naming a repo not checked out there | rc **2** |
| **C8** | **NOT-DEAD**: `cli.py` reverted to `main`, C3 and C6 re-driven | C3 rc **0**, C6 rc **0** — the defect, driven on purpose |

Every mutation is applied in **Python**, and the arm asserts the text actually
changed before running the command. BSD `sed` has no `\?` in a BRE, and the
verification pass has already spent one "corrupted digest" control that
corrupted nothing.

### The inventory E-M43 also owes

Every other `mlkit` subcommand is read for the same two shapes — a printed
failure with a zero exit, and a silent no-op on an empty match. The ones that
gate something are fixed in the same PR; the rest are named in the results
file with the reason they are not defects.

---

## 2. E-M44 — ACCEPTANCE RULES

R9 owns two obligations. It must report both, always.

* **B1.** A repo with a manifest failure AND a NOTICE gap reports **both**, in
  one reason. Status stays **FAIL**.
* **B2.** A repo with a manifest failure only reports one, and its reason is
  **byte-identical to today's**. No row may move for this.
* **B3.** A repo with a NOTICE gap only reports one and **FAILS**. It must not
  become a warning; mlkit has no WARN status and this must not be the reason
  one gets invented.
* **B4.** A clean repo reports none. PASS unchanged, ESCALATED-when-unsigned
  unchanged, NA-on-empty-manifest unchanged **when the NOTICE leg is clean**.
* **B5.** The NOTICE finding names the missing obligations **by source id**, so
  the repair is mechanical. The full list rides in `evidence`; the reason shows
  the first six and says how many more.
* **B6.** **Neither leg is weakened.** Every input that fails R9 today still
  fails it. The change is additive: findings are added, never removed, and no
  threshold, range or holdout is touched.
* **B7.** The NOTICE clause goes **FIRST** in a combined reason. Reasons are
  truncated at `MAX_REASON = 400`; putting the new information last is how it
  would go on being invisible, this time by truncation instead of by `return`.
  The consequence is deliberate and is the one thing in B2 that is relaxed:
  a repo with BOTH defects sees its manifest text move rightwards in the
  string, unchanged in content.
* **B8.** When the manifest leg could not be measured at all (its binding
  raised) and the NOTICE leg failed, R9 is **FAIL**, and the reason says in
  words that the manifest leg was NOT measured and why. A measured unmet
  obligation is a verdict; an unmeasured leg beside it does not erase it, and
  NA would.
* **B9.** When the allowlist is itself structurally invalid (`parse_error`, or
  a defective entry), the manifest leg is still **not** run — the
  determinations it would judge against are not determinations. The NOTICE leg
  IS run, because whether NOTICE.md matches the file on disk is answerable
  without them. `surge` is the repo this clause exists for.

### E-M44 CONTROL ARMS

| arm | fixture | required |
|---|---|---|
| **N1** | BLOCKED source + stale NOTICE | FAIL, reason contains BOTH clauses, and the missing source id |
| **N2** | BLOCKED source + current NOTICE | FAIL, reason **byte-identical to `main`'s** |
| **N3** | clean manifest + stale NOTICE | **FAIL** (not WARN, not NA), names the ids |
| **N4** | clean manifest + current NOTICE | PASS, evidence `allowlist_signed` true |
| **N5** | structurally defective entry + stale NOTICE (the `surge` shape) | FAIL, reason contains BOTH |
| **N6** | manifest binding raises + stale NOTICE (the `torrent`/`triage`/`blackout` shape under an interpreter without `pandas`) | **FAIL**, reason names the NOTICE gap AND says the manifest leg was not measured |
| **N7** | manifest binding raises + current NOTICE | **NA**, reason byte-identical to `main`'s |
| **N8** | NOTICE.md absent, obligations exist | FAIL, `NOTICE.md is absent`, names the obligations |
| **N9** | **NOT-DEAD**: `readiness.py` reverted to `main`, N1/N3/N5/N6 re-driven | N1 reason contains the manifest clause and NOT the NOTICE clause; N5 likewise; N6 is **NA** — the gap hidden again, on purpose |

---

## 3. THE FLEET INVARIANT — WHAT IS EXPECTED TO MOVE

Five phases over all eight adopter clones at their remote mains, one
interpreter, `PYTHONPATH` switched between `origin/main`'s package tree and the
branch's, `resilient_mlkit.__file__` asserted inside the named tree before any
row, arms SEQUENTIAL, every clone `git reset --hard && git clean -fdx` before
every phase. **272 rows** per arm.

### E-M43: expected movement is ZERO rows

It changes an exit code and adds a refusal. It touches no check. **Any** row
that moves refutes it and the lane stops.

### E-M44: expected movement, named per repo BEFORE the drive

Measured with mlkit's own `policy.render_notice` against each repo's committed
`NOTICE.md` at the mains listed in §5, and with R9's own `before` reading:

| repo | R9 before | NOTICE on disk | obligations | missing sections | R9 after, EXPECTED | why |
|---|---|---|---|---|---|---|
| choco | FAIL | current | 61 | 0 | **FAIL, reason unchanged** | no NOTICE gap |
| arabica | FAIL | **STALE** (text only) | 34 | 0 | **FAIL, reason GROWS** | NOTICE text differs; no section is missing |
| fray | PASS | current | 17 | 0 | **PASS, unchanged** | clean on both legs |
| torrent | NA (`pandas` absent here) | **STALE** | 48 | **10** | **NA → FAIL** | 10 unmet attribution obligations, measured without any binding |
| chokepoint | FAIL | current | 24 | 0 | **FAIL, reason unchanged** | no NOTICE gap |
| surge | FAIL (defective entries) | **STALE** | 36 | **12** | **FAIL, reason GROWS** | B9: the NOTICE leg runs past a structurally invalid allowlist |
| triage | NA (`pandas` absent here) | **STALE** | 21 | **10** | **NA → FAIL** | as torrent |
| blackout | NA (`pandas` absent here) | **STALE** | 11 | **5** | **NA → FAIL** | as torrent |

Nothing else may move. In particular **R8** — the row that writes
`reports/readiness.md` — must not change status on any repo; R9's reason lands
in that report's table, so the report TEXT changes on the five repos above and
the report's own verdict must not.

**A caveat this file records before it can be mistaken for a finding.** The NA
on torrent, triage and blackout is this interpreter's missing `pandas`, not the
repositories'. Under each repo's own environment their R9 already reads FAIL on
the manifest leg, and there the movement is reason-only. The status move
NA → FAIL is real, is what B8 prescribes, and is environment-shaped; it is
named as such rather than reported as eight repos changing verdict.

---

## 4. THE VERSION RULE, FIXED BEFORE THE DRIVE

`CHANGELOG.md`'s own scale: **major** = an existing check changes verdict on
unchanged code; **minor** = a new check exists, or a report or CLI surface
changes; **patch** = a defect in the instrument is fixed with no verdict change.

* **E-M43 is a MINOR.** A CLI surface changes: two conditions that exited 0 now
  exit non-zero, and one new refusal is printed. No check is touched, and the
  fleet drive is preregistered to move zero rows. → **v2.2.0**.
* **E-M44 is a MAJOR.** R9 changes verdict on unchanged repository code — three
  repos move NA → FAIL in this environment, and five see a finding they were
  not shown before. The scale does not have a softer word for that, and the
  brief's "at least a minor" is met by exceeding it. → **v3.0.0**.

If the E-M44 drive moves **no** status on any repo, the release is a minor and
this paragraph is what says so; the clause is written before the drive so it
cannot be chosen after it.

## 5. THE MAINS THE DRIVE IS AGAINST

```
choco      dbbe120e9c5d1a17df3e0041c5421f04a5c2aecd
arabica    795feacc03910a362339c2efaafb98cdfab08536
fray       512aedecff610af643ed23966867ddae3ca14dd6
torrent    538f14a064b0ce6938117b583e0276f3b54dd6c5
chokepoint bd11bc16d102f023697a08b95417fa930ee3ef53
surge      ad9855abde3af4bb24f138666d208712d4f0f1ee
triage     286cd72445adfa8389a055876abc1361b9cdd23d
blackout   bf4fdeeac23dd6b7c6e1a70be515ab5d556d4c8a
mlkit      912853dfabad57bf3e00c98386e6aa0091eff08f  (v2.1.0)
```

All eight rev-pin mlkit, so **no consumer verdict moves until someone moves a
pin.** Nothing is pushed to any consumer repo by this lane. The per-repo
adoption — which attribution sections are missing and the one command that
regenerates each `NOTICE.md` — is written out separately and is NOT performed
here.

## 6. WHAT THIS LANE MAY NOT DO

No gate file, threshold, range or holdout edited to make a check pass. No
allowlist entry added, edited or signed. No D1/D4/D5, E4/E5, S5 record, IAM or
billing. No tag cut. No credential read, printed, logged or written. `#45` is
untouched. Nothing pushed to a consumer repo.
