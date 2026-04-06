# Pivoteer

**Azure SQL Database → AWS RDS SQL Server migration and sync tool.**

Pivoteer is a self-hosted, Python-based CLI and REST API tool that exports databases from Azure SQL Database to AWS RDS SQL Server. It is designed to run on a dedicated Linux instance (AWS EC2 or Azure VM) to minimise data transfer costs, and handles everything from schema extraction and feature conversion to incremental scheduled sync.

---

## Features

| Capability | Detail |
|---|---|
| Full schema migration | Tables, views, indexes, stored procedures, functions, triggers, logins, users |
| Data migration | Chunked bulk export (TB-safe, 10 000 rows per batch by default) |
| Azure feature conversion | Converts or drops Azure-specific SQL constructs automatically |
| Output formats | Compressed SQL scripts (`.sql.gz`) or BACPAC files |
| Incremental sync | APScheduler-backed, per-database, user-configurable interval |
| REST API | Stdlib-only HTTP server — no Flask, no FastAPI |
| CLI frontend | `argparse`-based with live STDOUT progress |
| Job log | SQLite persistence across process restarts |
| Self-bootstrapping | Auto-installs `pyodbc`, `apscheduler`, `pyyaml` if missing |
| Minimal dependencies | Only 3 external packages total |

---

## Requirements

- Python 3.8+
- Linux (Ubuntu 20.04+ recommended)
- `unixodbc` system library (`sudo apt-get install unixodbc`)
- ODBC Driver 17 for SQL Server ([install guide](https://learn.microsoft.com/en-us/sql/connect/odbc/linux-mac/installing-the-microsoft-odbc-driver-for-sql-server))
- Direct TCP access to Azure SQL (port 1433) and AWS RDS SQL Server (port 1433)

---

## Installation

```bash
git clone https://github.com/your-org/pivoteer.git
cd pivoteer
python3 bootstrap.py          # auto-installs pyodbc, apscheduler, pyyaml
```

---

## Quick Start

### 1. Create server profiles

```bash
python3 pivoteer.py setup
# Follow the interactive wizard to create source (Azure) and target (RDS) profiles
```

Profiles are stored in `~/.pivoteer/config.yaml`:

```yaml
profiles:
  azure-prod:
    host: myserver.database.windows.net
    port: 1433
    user: myuser
    password: mypassword
  rds-dev:
    host: myinstance.rds.amazonaws.com
    port: 1433
    user: admin
    password: mypassword
```

### 2. Run a full migration

```bash
python3 pivoteer.py migrate \
  --src azure-prod \
  --dst rds-dev \
  --db MyDatabase \
  --outdir ./output \
  --format sql_gz
```

To export as BACPAC instead:

```bash
python3 pivoteer.py migrate \
  --src azure-prod \
  --dst rds-dev \
  --db MyDatabase \
  --format bacpac
```

### 3. Schedule incremental sync

```bash
python3 pivoteer.py sync \
  --src azure-prod \
  --dst rds-dev \
  --db MyDatabase \
  --every 30
```

> **Note:** SQL Server Change Tracking must be enabled on the source database for incremental sync to work. If not enabled, tables are skipped with a warning.

### 4. Check job status

```bash
python3 pivoteer.py status --job <JOB_ID>
```

### 5. View job history

```bash
python3 pivoteer.py history
```

### 6. Start the REST API server

```bash
python3 pivoteer.py serve --port 8080
```

---

## REST API Reference

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/jobs/migrate` | Start a migration job |
| `POST` | `/jobs/sync` | Schedule a recurring sync job |
| `GET` | `/jobs/{id}` | Get job status (JSON) |
| `DELETE` | `/jobs/{id}` | Cancel/remove a scheduled job |
| `GET` | `/jobs` | List all scheduled jobs |
| `GET` | `/history` | List past job runs |

**Start a migration via API:**

```bash
curl -X POST http://localhost:8080/jobs/migrate \
  -H "Content-Type: application/json" \
  -d '{"src":"azure-prod","dst":"rds-dev","db":"MyDatabase","format":"sql_gz"}'
```

**Poll status:**

```bash
curl http://localhost:8080/jobs/<JOB_ID>
```

**Schedule sync:**

```bash
curl -X POST http://localhost:8080/jobs/sync \
  -H "Content-Type: application/json" \
  -d '{"src":"azure-prod","dst":"rds-dev","db":"MyDatabase","interval_minutes":30}'
```

---

## Azure Feature Conversion Rules

| Feature | Action |
|---|---|
| Azure AD / Entra authentication | Converted to SQL auth login with placeholder password |
| Row-Level Security (RLS) | Preserved (supported by RDS) |
| Temporal tables (system-versioned) | Preserved (supported by RDS) |
| JSON functions (`FOR JSON`, `OPENJSON`) | Preserved (supported by RDS) |
| Always Encrypted (Azure Key Vault refs) | Key Vault references stripped; column encryption skeleton preserved |
| Ledger tables | `LEDGER = ON` clause removed |
| Elastic Query / external tables | Dropped with comment |
| Stretch Database | Dropped with comment |
| `OPENROWSET` to Azure Blob | Dropped with comment |
| Geo-replication / failover groups | Dropped with comment |
| SQL Agent Jobs | Out of scope — not migrated |

---

## Testing

```bash
# Unit tests (no database required)
PYTHONPATH=. python3 -m pytest tests/unit/ -v

# Integration tests (requires live instances)
export PIVOTEER_TEST_SRC=azure-prod
export PIVOTEER_TEST_DST=rds-dev
export PIVOTEER_TEST_DB=MyDatabase
PYTHONPATH=. python3 -m pytest tests/integration/ --integration -v
```

---

## Project Structure

```
pivoteer/
├── pivoteer.py          # CLI entry point
├── bootstrap.py         # Dependency auto-installer
├── api/
│   └── server.py        # REST API (stdlib http.server)
├── core/
│   ├── config.py        # Profile management + setup wizard
│   ├── connection.py    # pyodbc connection factory
│   ├── converter.py     # Azure → RDS SQL feature conversion rules
│   ├── exporter.py      # Schema + data extraction (chunked)
│   ├── importer.py      # SQL script execution on target
│   ├── joblog.py        # SQLite job log persistence
│   ├── scheduler.py     # APScheduler integration
│   ├── status.py        # In-memory job progress tracker
│   └── sync.py          # Incremental change tracking sync
├── formats/
│   ├── sql_gz.py        # Compressed SQL script utilities
│   └── bacpac.py        # BACPAC export/import via SqlPackage
└── tests/
    ├── conftest.py      # pytest --integration flag
    ├── unit/            # Mocked unit tests (no DB required)
    └── integration/     # Live end-to-end tests
```

---

## Configuration File

Pivoteer stores all server profiles in `~/.pivoteer/config.yaml`. You can edit this file directly or use `pivoteer setup` to add profiles interactively.

---

## Job Log

All job runs are persisted to `~/.pivoteer/joblog.db` (SQLite). This survives process restarts and can be queried directly:

```bash
sqlite3 ~/.pivoteer/joblog.db "SELECT * FROM jobs ORDER BY start_time DESC LIMIT 10;"
```

---

## License

MIT
