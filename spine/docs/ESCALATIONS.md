# ESCALATIONS.md

Open items reserved to the human signatory. While any item here is open, this
repo's portfolio state is **AWAITING-SIGNOFF**.

An agent appends to this file and moves on to other work. An agent never
performs any item on it.

Reserved by standing policy: S5 decision records, allowlist additions, D1, D4,
D5, E4, E5, and any IAM, billing or cost-incurring resource creation.

---

## E-001 — Training-plane bootstrap (Loop 0) has not been performed

**Status:** OPEN · **Raised:** 2026-08-14 · **Blocks:** R7, D2, D3, E1, E2, E3
**Applies to:** all 8 repos

Loop 0 of the readiness package provisions the `us-west-2` training plane. Every
item in it is IAM, billing, or cost-incurring, and is therefore reserved:

1. S3 bucket for training data and the DVC remote, `us-west-2`, versioning on.
2. ECR repository for the pinned training image.
3. SageMaker AI domain and a serverless managed MLflow app.
4. IAM execution role for SageMaker, least-privilege to the bucket, ECR, MLflow
   and Secrets Manager.
5. GitHub Actions OIDC provider and a CI role. No long-lived access keys.
6. Cost allocation tags `resilient:model`, `resilient:run-id`,
   `resilient:phase`; one AWS Budget per model repo.
7. Secrets Manager placeholders for the Earthdata and Copernicus credentials.
   **The signatory populates the values.** No agent reads them back, and
   CLAUDE.md rule 13 applies throughout.

Until this exists, `mlkit` reports R7 NA (region and image undeclared) and
D2/D3/E1/E2/E3 NA (no Processing or Training Jobs to run on). These are
unmeasured, not passed.

**Also outstanding:** the local AWS session is expired (`aws sts
get-caller-identity` → session expired) and the configured default region is
`us-east-1`, not `us-west-2`.

---

## E-002 — `docs/allowlist.yaml` is unsigned and empty

**Status:** OPEN · **Raised:** 2026-08-14 · **Blocks:** T5, R9
**Applies to:** all 8 repos

The allowlist exists as scaffolding with zero entries and `signed: false`. No
source or checkpoint in any repo has a verified licence determination yet.

Per `docs/DATA_POLICY.md`, an agent may not add an entry. Proposed additions
are recorded below as they are verified, each with the licence URL and the date
that page was actually read. The signatory verifies, moves them into
`docs/allowlist.yaml`, and sets the signature block.

`mlkit` reports T5 and R9 ESCALATED against an unsigned allowlist rather than
PASS, so nothing downstream can mistake a proposal for a determination.

### Proposed additions

_None yet. Entries appear here only after their licence page has been retrieved
and read; nothing is proposed from memory._

| id | kind | proposed status | licence URL | retrieved | notes |
|---|---|---|---|---|---|

---

<!-- Append new escalations above this line, newest last, with a stable E-NNN id. -->
