# Execution-Ready Specification — Pivoteer

**Slug:** pivoteer-azure-rds  
**Date:** 2026-04-06  
**Interview rounds:** 3  
**Final ambiguity score:** 0.14 (threshold ≤ 0.20 — MET)

---

## Clarity Breakdown

| Dimension | Score | Status |
|---|---|---|
| Intent Clarity | 0.10 | Clear |
| Outcome Clarity | 0.12 | Clear |
| Scope Clarity | 0.15 | Clear |
| Constraint Clarity | 0.14 | Clear |
| Success Criteria | 0.18 | Clear |

---

## Intent

Build **Pivoteer** — a self-hosted migration and sync tool that runs on a dedicated Linux instance (AWS or Azure) and exports Azure SQL databases to AWS RDS SQL Server. It exposes a REST API for programmatic control and a Linux CLI for interactive use. The backend runs uninterrupted; the CLI and API are thin control planes over it.

---

## Outcome

A fully functional, production-grade Python 3 tool that:

1. Performs full schema + data migration from Azure SQL Database to AWS RDS SQL Server.
2. Converts or strips Azure-specific SQL features to RDS-compatible equivalents.
3. Supports ongoing incremental/scheduled sync (user-configurable schedule per database).
4. Outputs compressed SQL scripts (`.sql.gz`) and/or BACPAC files.
5. Reports migration status in real time via REST API polling and CLI STDOUT.
6. Persists job history in a local SQLite database (survives restarts).
7. Manages multiple source/target server profiles via config file or interactive setup wizard.

---

## Scope

### In Scope

| Area | Detail |
|---|---|
| Schema migration | Tables, views, indexes, stored procedures, functions, triggers, constraints |
| Data migration | Full bulk copy + incremental sync (change tracking or timestamp-based) |
| Login/role migration | SQL auth logins and roles that have RDS equivalents |
| Azure feature conversion | See conversion table below |
| Output formats | `.sql.gz` (compressed SQL scripts), `.bacpac` (BACPAC via SqlPackage) |
| REST API | Start/stop/status/schedule jobs; JSON responses |
| CLI frontend | `pivoteer` command with subcommands; argparse-based |
| Setup wizard | Interactive questionnaire to create server profiles |
| Config file | YAML/JSON per-server profiles |
| Scheduled sync | APScheduler-backed, per-database, user-configurable interval |
| Job log | SQLite persistence of all job runs, steps, errors |
| Progress reporting | REST `/status/{job_id}` + CLI live STDOUT |
| Self-bootstrapping | Auto-installs `pyodbc`, `apscheduler` if missing |
| Testing | Unit tests (mocked DB) + integration tests (gated behind `--integration` flag) |

### Azure Feature Conversion Table

| Feature | Action |
|---|---|
| Azure AD / Entra authentication | Convert to SQL auth login definitions |
| Row-Level Security (RLS) | Keep as-is (RDS supports it) |
| Temporal tables (system-versioned) | Keep as-is (RDS supports it) |
| JSON functions (`FOR JSON`, `OPENJSON`) | Keep as-is (RDS supports it) |
| Always Encrypted (Azure Key Vault refs) | Strip Key Vault references; keep column encryption skeleton |
| Elastic Query / external tables | Drop entirely |
| Stretch Database | Drop entirely |
| `OPENROWSET` to Azure Blob | Drop entirely |
| Ledger tables | Convert to audit trigger pattern |
| Geo-replication / failover groups | Drop entirely |
| SQL Agent Jobs | Skip (out of scope) |

### Out of Scope

- Docker / container orchestration
- SQL Server Analysis Services, Integration Services, Reporting Services
- Azure Synapse / Dedicated SQL Pool
- Cross-cloud CDC using Debezium or Kafka (may integrate as optional external tool)
- Data masking / PII scrubbing (future feature)
- Windows-only tooling

---

## Constraints

| Constraint | Detail |
|---|---|
| Language | Python 3.8+ (stdlib-first) |
| External packages | `pyodbc` (DB connectivity), `apscheduler` (scheduling) — auto-installed |
| Optional system tool | `SqlPackage` CLI (for BACPAC) — auto-downloaded if not present |
| Connectivity | Direct TCP; configurable per profile (host, port, credentials) |
| Platform | Linux (Ubuntu 20.04+); bash-compatible |
| Deployment target | Standalone instance in AWS or Azure |
| Output | STDOUT for all logs, errors, and stack traces |
| DRY | Single source of truth for all SQL conversion rules, config schemas, and job logic |

---

## Architecture (high level)

```
pivoteer/
├── pivoteer.py          # CLI entry point (argparse)
├── api/
│   └── server.py        # REST API (stdlib http.server)
├── core/
│   ├── config.py        # Config file + setup wizard
│   ├── connection.py    # DB connection pool (pyodbc)
│   ├── exporter.py      # Schema + data export orchestrator
│   ├── converter.py     # Azure → RDS SQL feature conversion rules
│   ├── importer.py      # RDS import / apply logic
│   ├── sync.py          # Incremental sync engine
│   ├── scheduler.py     # APScheduler wrapper
│   ├── joblog.py        # SQLite job log
│   └── status.py        # Progress tracker (shared state)
├── formats/
│   ├── sql_gz.py        # Compressed SQL script writer
│   └── bacpac.py        # BACPAC export via SqlPackage
├── bootstrap.py         # Dependency auto-installer
├── tests/
│   ├── unit/            # Mocked unit tests
│   └── integration/     # Gated integration tests (--integration flag)
└── README.md
```

---

## Acceptance Criteria

1. `pivoteer setup` launches an interactive wizard and writes a valid server profile to `~/.pivoteer/config.yaml`.
2. `pivoteer migrate --src PROFILE --dst PROFILE --db DBNAME` completes a full schema + data migration and writes output to the configured format.
3. `pivoteer sync --src PROFILE --dst PROFILE --db DBNAME --every 30m` starts a background sync job and registers it in APScheduler.
4. `pivoteer status --job JOB_ID` prints current step, percentage, elapsed time, and any errors to STDOUT.
5. REST API: `POST /jobs` starts a job; `GET /jobs/{id}` returns JSON status; `DELETE /jobs/{id}` cancels.
6. All Azure-specific features in the conversion table are handled correctly (unit-tested).
7. SQLite job log persists across process restarts; `pivoteer history` lists past runs.
8. `python3 -m pytest tests/unit/` passes with zero failures on a machine with no SQL Server access.
9. `python3 -m pytest tests/integration/ --integration` passes when `PIVOTEER_TEST_SRC` and `PIVOTEER_TEST_DST` env vars point to live instances.
10. `bootstrap.py` installs missing dependencies without root if a virtualenv is active, or with `--user` flag otherwise.

---

## Assumptions

- Source Azure SQL Database uses SQL authentication (or Azure AD auth that will be converted).
- Target AWS RDS SQL Server instance is pre-provisioned; Pivoteer does not provision infrastructure.
- `SqlPackage` CLI is available or can be downloaded from Microsoft's public CDL URL.
- The tool instance has outbound TCP access to both Azure SQL (port 1433) and AWS RDS (port 1433).
- Incremental sync uses SQL Server Change Tracking (must be enabled on source) or falls back to a `modified_at` watermark column.
