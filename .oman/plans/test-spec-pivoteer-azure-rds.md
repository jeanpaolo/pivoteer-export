# Test Specification: Pivoteer

**Date:** 2026-04-06  
**Author:** Manus AI  
**Status:** Draft for Review

## 1. Overview

This document outlines the testing strategy for Pivoteer, ensuring the tool correctly migrates schema and data from Azure SQL Database to AWS RDS SQL Server while adhering to the defined feature conversion rules. The strategy encompasses both unit testing (isolated logic) and integration testing (end-to-end execution against live databases).

## 2. Test Environments

- **Unit Tests:** Executed locally without requiring database connectivity. Mocks are used for `pyodbc` connections, file system operations, and external command executions (e.g., `SqlPackage`).
- **Integration Tests:** Executed against live Azure SQL Database and AWS RDS SQL Server instances. These tests are gated behind an `--integration` flag and require valid credentials provided via environment variables (`PIVOTEER_TEST_SRC`, `PIVOTEER_TEST_DST`).

## 3. Unit Testing Strategy

Unit tests will focus on validating the core logic of the application, specifically the configuration management, feature conversion rules, and job scheduling mechanisms.

### 3.1. Configuration Management (`tests/unit/test_config.py`)
- **Profile Creation:** Verify that the interactive setup wizard correctly parses user input and generates a valid YAML/JSON configuration file.
- **Profile Loading:** Verify that the application correctly loads and parses existing configuration profiles, handling missing or invalid files gracefully.

### 3.2. Feature Conversion Rules (`tests/unit/test_converter.py`)
This is the most critical unit test suite, ensuring that Azure-specific SQL features are handled correctly.
- **Azure AD Authentication:** Verify that Azure AD login definitions are converted to standard SQL authentication logins.
- **Ledger Tables:** Verify that ledger table definitions are converted to standard tables with audit trigger patterns.
- **Always Encrypted:** Verify that Azure Key Vault references are stripped while the column encryption skeleton is preserved.
- **Unsupported Features:** Verify that Elastic Query, Stretch Database, `OPENROWSET` to Azure Blob, and Geo-replication definitions are completely dropped or stubbed with comments.
- **Supported Features:** Verify that Row-Level Security (RLS), Temporal tables, and JSON functions are preserved without modification.

### 3.3. Job Scheduling and Logging (`tests/unit/test_scheduler.py`, `tests/unit/test_joblog.py`)
- **APScheduler Integration:** Verify that sync jobs are correctly registered with APScheduler using the user-defined intervals.
- **SQLite Persistence:** Verify that job statuses, progress updates, and errors are correctly written to and read from the local SQLite database.

## 4. Integration Testing Strategy

Integration tests will validate the end-to-end migration process, ensuring that the tool can successfully connect to live databases, extract schema and data, and apply them to the target instance.

### 4.1. End-to-End Migration (`tests/integration/test_migration.py`)
- **Schema Export:** Verify that the tool successfully extracts the schema from the source Azure SQL Database and generates valid `.sql.gz` or `.bacpac` files.
- **Data Export:** Verify that the tool successfully extracts data from the source database.
- **Target Import:** Verify that the generated schema and data can be successfully applied to the target AWS RDS SQL Server instance without errors.

### 4.2. Incremental Sync (`tests/integration/test_sync.py`)
- **Change Tracking:** Verify that the tool correctly identifies and synchronizes incremental changes (inserts, updates, deletes) using SQL Server Change Tracking or a watermark column.

### 4.3. REST API and CLI Interaction (`tests/integration/test_api.py`)
- **Job Control:** Verify that the REST API can successfully start, stop, and poll the status of migration jobs.
- **CLI Progress:** Verify that the CLI correctly displays real-time progress updates to STDOUT during a migration run.

## 5. Test Execution

- **Framework:** `pytest` will be used as the primary testing framework.
- **Execution Command (Unit):** `python3 -m pytest tests/unit/`
- **Execution Command (Integration):** `python3 -m pytest tests/integration/ --integration`
