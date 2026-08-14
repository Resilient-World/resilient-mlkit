# BLOCKERS.md

One line per blocker. While any blocker here is open, this repo's portfolio
state is **BLOCKED**.

A blocker is a measured failure or a fired hard stop — something `mlkit`
reported FAIL on. It is not a task that has not been done yet, and it is not a
check that could not be measured; those are IN-PROGRESS and NA respectively.

**Blockers are fixed at the root cause in `src/`.** Never by editing a gate
file, loosening a threshold, widening a range or narrowing a holdout.

Format: `CHECK-ID — one line — raised YYYY-MM-DD`

---

_No blockers recorded._
