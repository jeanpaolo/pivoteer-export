# Implementation Plan: Pivoteer

**Date:** 2026-04-06  
**Author:** Manus AI  
**Status:** Draft for Review

## 1. Overview

This document outlines the phased implementation strategy for Pivoteer, a self-hosted Python tool designed to migrate and synchronize databases from Azure SQL Database to AWS RDS SQL Server. The implementation is divided into distinct phases, each focusing on a specific architectural component.

## 2. Phase 1: Foundation and Configuration

The initial phase establishes the core project structure, dependency management, and configuration handling.

### 2.1. Project Structure and Bootstrapping
- Create the directory structure (`api/`, `core/`, `formats/`, `tests/`).
- Implement `bootstrap.py` to automatically install `pyodbc` and `apscheduler` using `pip` or `pip3`.
- Set up the `pytest` testing framework and configure the `--integration` flag.

### 2.2. Configuration Management (`core/config.py`)
- Implement the interactive CLI setup wizard to prompt users for source and target database credentials.
- Implement logic to save and load server profiles from a local YAML or JSON configuration file (`~/.pivoteer/config.yaml`).
- Write unit tests to validate profile creation and loading.

## 3. Phase 2: Database Connectivity and Job Logging

This phase focuses on establishing reliable connections to the databases and persisting job states.

### 3.1. Connection Pooling (`core/connection.py`)
- Implement a robust connection pool using `pyodbc` to manage connections to both Azure SQL Database and AWS RDS SQL Server.
- Implement retry logic and error handling for transient network issues.

### 3.2. Job Logging (`core/joblog.py`, `core/status.py`)
- Initialize a local SQLite database to store job history, step progress, and errors.
- Implement functions to create, update, and query job records.
- Implement a shared state mechanism (`core/status.py`) to track real-time progress for the CLI and REST API.
- Write unit tests to validate SQLite persistence and state updates.

## 4. Phase 3: Schema Extraction and Feature Conversion

This is the most complex phase, involving the extraction of the source schema and the application of conversion rules.

### 4.1. Schema Extraction (`core/exporter.py`)
- Implement logic to query system catalog views (e.g., `sys.tables`, `sys.columns`, `sys.indexes`) to extract the database schema.
- Implement logic to generate `CREATE` statements for tables, views, stored procedures, functions, and triggers.

### 4.2. Feature Conversion (`core/converter.py`)
- Implement the conversion rules defined in the PRD:
  - Convert Azure AD authentication to SQL auth logins.
  - Convert Ledger tables to audit trigger patterns.
  - Strip Azure Key Vault references while preserving the column encryption skeleton.
  - Drop Elastic Query, Stretch Database, `OPENROWSET` to Azure Blob, and Geo-replication definitions.
  - Preserve Row-Level Security (RLS), Temporal tables, and JSON functions.
- Write comprehensive unit tests to validate each conversion rule against mocked schema definitions.

## 5. Phase 4: Data Export and Output Formatting

This phase focuses on extracting the actual data and formatting it for the target instance.

### 5.1. Data Extraction (`core/exporter.py`)
- Implement logic to perform bulk data extraction using `pyodbc` or `bcp` (if available).
- Implement logic to handle large datasets efficiently, avoiding memory exhaustion.

### 5.2. Output Formatting (`formats/sql_gz.py`, `formats/bacpac.py`)
- Implement logic to write the extracted schema and data to compressed SQL scripts (`.sql.gz`).
- Implement logic to invoke the `SqlPackage` CLI to generate BACPAC files.

## 6. Phase 5: Target Import and Incremental Sync

This phase focuses on applying the extracted data to the target instance and establishing ongoing synchronization.

### 6.1. Target Import (`core/importer.py`)
- Implement logic to execute the generated `.sql.gz` scripts or import the `.bacpac` file into the target AWS RDS SQL Server instance.
- Implement error handling and rollback mechanisms for failed imports.

### 6.2. Incremental Sync (`core/sync.py`, `core/scheduler.py`)
- Implement logic to identify and extract incremental changes using SQL Server Change Tracking or a watermark column.
- Implement logic to apply these changes to the target instance.
- Integrate `apscheduler` to manage recurring sync jobs based on user-defined intervals.
- Write unit tests to validate the scheduling mechanism.

## 7. Phase 6: Interfaces and Integration

The final phase ties everything together with the CLI and REST API interfaces.

### 7.1. REST API (`api/server.py`)
- Implement a lightweight HTTP server using Python's standard `http.server` or `socketserver`.
- Implement endpoints to start (`POST /jobs`), stop (`DELETE /jobs/{id}`), and poll the status (`GET /jobs/{id}`) of migration jobs.

### 7.2. CLI Frontend (`pivoteer.py`)
- Implement the main entry point using `argparse`.
- Implement subcommands for `setup`, `migrate`, `sync`, `status`, and `history`.
- Implement logic to display real-time progress updates to STDOUT during interactive execution.

### 7.3. End-to-End Testing
- Execute the full suite of integration tests against live Azure SQL Database and AWS RDS SQL Server instances.
- Verify that all acceptance criteria defined in the PRD are met.
