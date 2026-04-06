# Context Snapshot — Pivoteer: Azure SQL → AWS RDS Exporter

**Timestamp:** 2026-04-06  
**Task Slug:** pivoteer-azure-rds  
**Depth Profile:** standard (ambiguity threshold ≤ 0.20, max 12 rounds)

## Task Statement

Build a tool that exports Azure SQL databases to AWS RDS SQL Server instances.

## Desired Outcome (as stated)

- Runs on Linux / bash-like environments
- DRY development principles throughout
- Minimal external dependencies; auto-downloads what it needs
- Converts Azure-specific SQL features to AWS RDS SQL Server equivalents
- Excludes Azure-only features that have no RDS counterpart
- Handles multiple databases and servers, up to terabyte scale
- Errors and stack traces go to STDOUT
- Code is manageable, concise, and testable
- User also invoked: `$ralplan` (REST → Linux CLI front-end migration), `$ralph` (persistent implementation), `$team 3:executor` (parallel frontend/backend/data layer)

## Known Facts

- Source: Azure SQL Database (PaaS, cloud-native)
- Target: AWS RDS for SQL Server (managed SQL Server on EC2-backed RDS)
- The phrase "REST to linux cli front end" implies there may be an existing REST-based interface or the user wants to replace a REST API design with a pure CLI design
- No existing codebase has been provided

## Constraints (inferred)

- Must not require Docker or heavy runtimes as primary dependency
- Must be scriptable / automatable (CI/CD friendly)
- Must handle large schemas and data volumes without memory exhaustion

## Unknowns (to resolve via interview)

1. What does "REST to linux cli front end" mean — is there an existing REST API being replaced, or is this a design choice for the new tool?
2. What is the primary operation mode: schema-only export, data export, or full migration (schema + data + objects)?
3. What SQL objects must be migrated: tables, views, stored procedures, functions, triggers, indexes, users/roles, jobs?
4. What Azure-specific features need active conversion (e.g., Row-Level Security, Elastic Query, Azure AD auth, temporal tables, JSON support)?
5. What is the preferred scripting language: Python, Bash, or a combination?
6. Is this a one-time migration tool or an ongoing sync/replication tool?
7. What connectivity model is expected: direct TCP, SSH tunnel, VPN?
8. What is the expected output format: SQL scripts, BACPAC, BCP files, or direct live transfer?
9. Are there compliance or data-masking requirements?
10. What does "testable" mean to the user: unit tests, integration tests, or both?
