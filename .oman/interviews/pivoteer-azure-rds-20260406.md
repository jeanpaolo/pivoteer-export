# Interview Transcript — Pivoteer

**Date:** 2026-04-06 | **Rounds:** 3 | **Final ambiguity:** 0.14

## Round 1

**Q1 (Scope):** REST-to-CLI meaning?  
**A:** B — tool exposes both REST API (backend control plane) and Linux CLI (frontend). API keeps backend running uninterrupted.

**Q2 (Outcome):** Primary operation?  
**A:** C+D — full migration (schema + data + logins) plus incremental sync via external tools where possible.

**Q3 (Constraint):** Preferred language?  
**A:** Open — agent to recommend.

**Q4 (Intent):** One-time or ongoing?  
**A:** Include scheduled sync if possible.

## Round 2

**Q5 (Constraint):** Python + pyodbc + apscheduler stack OK?  
**A:** Yes. Also add real-time migration status for multi-step processes.

**Q6 (Constraint):** Connectivity model?  
**A:** Direct TCP, configurable via config file or interactive questionnaire.

**Q7 (Outcome):** Output format?  
**A:** Tool on its own instance. Compressed SQL files (.sql.gz) + BACPAC. Both supported, flag-controlled.

**Q8 (Success):** What does "testable" mean?  
**A:** C — unit + integration tests. Integration gated behind flag, runnable when instances available.

**Q9 (Scope):** Azure feature conversion priorities?  
**A:** Drop Elastic Query, Stretch DB, OPENROWSET. Strip Key Vault refs, keep column encryption skeleton. Drop geo-replication. Keep RLS, temporal tables, JSON functions.

## Round 3

**Q10 (Success):** Status reporting location?  
**A:** C+D — REST API polling + CLI STDOUT + SQLite job-log persistence.

**Q11 (Scope):** SQL Agent Jobs?  
**A:** B — skip entirely.

**Q12 (Scope):** Sync granularity?  
**A:** D — fully user-configurable per database profile, set dynamically.
