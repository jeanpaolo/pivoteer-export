# Product Requirements Document: Pivoteer

**Date:** 2026-04-06  
**Author:** Manus AI  
**Status:** Draft for Review

## 1. Overview

Pivoteer is a self-hosted, Python-based CLI and REST API tool designed to migrate and continuously sync databases from Azure SQL Database to AWS RDS SQL Server. It is built to run on a dedicated Linux instance (AWS EC2 or Azure VM) to minimize data transfer costs. The tool handles schema conversion, data export, and incremental synchronization while automatically stripping or converting Azure-specific features that are incompatible with AWS RDS.

## 2. Target Audience

Database Administrators (DBAs) and DevOps engineers who need a reliable, scriptable, and maintainable tool to migrate workloads out of Azure SQL Database into AWS RDS SQL Server without relying on heavy third-party GUI tools or expensive SaaS migration services.

## 3. Core Features

### 3.1. Dual Interface (CLI + REST API)
- **CLI Frontend:** An interactive command-line interface for manual execution, configuration wizardry, and real-time progress monitoring via STDOUT.
- **REST API Backend:** A lightweight, dependency-free HTTP server that allows programmatic control (start, stop, status polling) and keeps the migration engine running uninterrupted in the background.

### 3.2. Schema and Data Migration
- **Full Export:** Supports exporting schema (tables, views, indexes, stored procedures, functions, triggers) and data.
- **Output Formats:** Configurable output to either compressed SQL scripts (`.sql.gz`) or BACPAC files (via `SqlPackage`).
- **Incremental Sync:** Supports scheduled, incremental data synchronization using APScheduler, configurable per database profile.

### 3.3. Azure Feature Conversion
The tool automatically detects and handles Azure-specific SQL features:
- **Convert:** Azure AD authentication to SQL auth logins; Ledger tables to audit trigger patterns.
- **Keep:** Row-Level Security (RLS), Temporal tables, JSON functions (all supported by RDS).
- **Strip/Drop:** Elastic Query, Stretch Database, `OPENROWSET` to Azure Blob, Geo-replication, and Azure Key Vault references (keeping the column encryption skeleton).
- **Skip:** SQL Agent Jobs are explicitly out of scope.

### 3.4. State and Configuration Management
- **Interactive Setup:** A CLI wizard to generate and store server profiles (host, port, credentials) in a local YAML/JSON configuration file.
- **Job Logging:** A local SQLite database persists job history, step progress, and errors across process restarts.

## 4. Technical Constraints

- **Language:** Python 3.8+ using standard library components wherever possible.
- **Dependencies:** Minimal external dependencies (`pyodbc` for database connectivity, `apscheduler` for task scheduling). The tool must self-bootstrap and auto-install these if missing.
- **Environment:** Linux (bash-compatible).
- **Connectivity:** Direct TCP connection to source and target databases.

## 5. Acceptance Criteria

1. The `pivoteer setup` command successfully creates a valid configuration profile.
2. The `pivoteer migrate` command successfully exports a database to the specified format (`.sql.gz` or `.bacpac`).
3. The `pivoteer sync` command successfully registers and executes a scheduled background sync job.
4. The REST API correctly reports job status and progress.
5. Azure-specific features are correctly converted, stripped, or preserved according to the conversion rules.
6. The SQLite job log accurately records all job activities and survives process restarts.
7. Unit tests pass without requiring a live database connection.
8. Integration tests pass when provided with valid source and target database credentials.
