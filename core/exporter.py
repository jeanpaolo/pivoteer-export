"""
core/exporter.py

Extracts schema (DDL) and data from an Azure SQL Database using live catalog
queries.  All output is written as gzip-compressed SQL scripts to avoid
memory exhaustion on TB-scale databases.

Design principles:
  - DRY: every catalog query is a named helper; no inline SQL strings in callers.
  - Chunked reads: data is streamed in configurable row-batches (default 10 000).
  - STDOUT-only logging: print() for progress; exceptions propagate to callers.
"""

import gzip
import os
import traceback
from .connection import get_connection
from .converter import apply_all_conversions
from .status import tracker

# ---------------------------------------------------------------------------
# Catalog query helpers (DRY: one place for every SQL string)
# ---------------------------------------------------------------------------

_SQL_LIST_TABLES = """
    SELECT s.name AS schema_name, t.name AS table_name
    FROM sys.tables t
    JOIN sys.schemas s ON t.schema_id = s.schema_id
    WHERE t.type = 'U'
    ORDER BY s.name, t.name
"""

_SQL_TABLE_COLUMNS = """
    SELECT
        c.name,
        tp.name AS type_name,
        c.max_length,
        c.precision,
        c.scale,
        c.is_nullable,
        c.is_identity,
        ic.seed_value,
        ic.increment_value,
        c.collation_name
    FROM sys.columns c
    JOIN sys.types tp ON c.user_type_id = tp.user_type_id
    LEFT JOIN sys.identity_columns ic ON ic.object_id = c.object_id AND ic.column_id = c.column_id
    WHERE c.object_id = OBJECT_ID(?)
    ORDER BY c.column_id
"""

_SQL_TABLE_INDEXES = """
    SELECT
        i.name,
        i.type_desc,
        i.is_unique,
        i.is_primary_key,
        STRING_AGG(c.name, ', ') WITHIN GROUP (ORDER BY ic.key_ordinal) AS cols
    FROM sys.indexes i
    JOIN sys.index_columns ic ON ic.object_id = i.object_id AND ic.index_id = i.index_id
    JOIN sys.columns c ON c.object_id = ic.object_id AND c.column_id = ic.column_id
    WHERE i.object_id = OBJECT_ID(?) AND i.type > 0
    GROUP BY i.name, i.type_desc, i.is_unique, i.is_primary_key
"""

_SQL_TABLE_FK = """
    SELECT
        fk.name,
        OBJECT_NAME(fk.parent_object_id) AS parent_table,
        COL_NAME(fkc.parent_object_id, fkc.parent_column_id) AS parent_col,
        OBJECT_NAME(fk.referenced_object_id) AS ref_table,
        COL_NAME(fkc.referenced_object_id, fkc.referenced_column_id) AS ref_col
    FROM sys.foreign_keys fk
    JOIN sys.foreign_key_columns fkc ON fkc.constraint_object_id = fk.object_id
    WHERE fk.parent_object_id = OBJECT_ID(?)
"""

_SQL_VIEWS = """
    SELECT s.name AS schema_name, v.name AS view_name, m.definition
    FROM sys.views v
    JOIN sys.schemas s ON v.schema_id = s.schema_id
    JOIN sys.sql_modules m ON m.object_id = v.object_id
    ORDER BY s.name, v.name
"""

_SQL_PROCS = """
    SELECT s.name AS schema_name, p.name AS proc_name, m.definition
    FROM sys.procedures p
    JOIN sys.schemas s ON p.schema_id = s.schema_id
    JOIN sys.sql_modules m ON m.object_id = p.object_id
    ORDER BY s.name, p.name
"""

_SQL_FUNCTIONS = """
    SELECT s.name AS schema_name, o.name AS func_name, m.definition
    FROM sys.objects o
    JOIN sys.schemas s ON o.schema_id = s.schema_id
    JOIN sys.sql_modules m ON m.object_id = o.object_id
    WHERE o.type IN ('FN','IF','TF','FS','FT')
    ORDER BY s.name, o.name
"""

_SQL_TRIGGERS = """
    SELECT OBJECT_SCHEMA_NAME(t.object_id) AS schema_name,
           t.name AS trigger_name, m.definition
    FROM sys.triggers t
    JOIN sys.sql_modules m ON m.object_id = t.object_id
    WHERE t.parent_class = 1
    ORDER BY t.name
"""

_SQL_LOGINS = """
    SELECT name, type_desc, default_database_name
    FROM sys.sql_logins
    WHERE name NOT LIKE '##%' AND name != 'sa'
"""

_SQL_DB_USERS = """
    SELECT dp.name AS user_name, dp.type_desc, sl.name AS login_name
    FROM sys.database_principals dp
    LEFT JOIN sys.sql_logins sl ON sl.sid = dp.sid
    WHERE dp.type IN ('S','U','G') AND dp.name NOT IN ('dbo','guest','INFORMATION_SCHEMA','sys')
"""

_SQL_ROW_COUNT = "SELECT COUNT_BIG(*) FROM [{schema}].[{table}]"

# ---------------------------------------------------------------------------
# Column DDL builder (DRY)
# ---------------------------------------------------------------------------

def _column_ddl(row):
    """Returns a single column definition fragment from a sys.columns row."""
    name, type_name, max_len, prec, scale, nullable, is_id, seed, incr, collation = row
    
    # Resolve type string
    if type_name in ('varchar', 'nvarchar', 'char', 'nchar', 'varbinary', 'binary'):
        length = 'MAX' if max_len == -1 else (max_len // 2 if type_name.startswith('n') else max_len)
        type_str = f"{type_name}({length})"
    elif type_name in ('decimal', 'numeric'):
        type_str = f"{type_name}({prec},{scale})"
    elif type_name in ('float', 'real'):
        type_str = f"{type_name}({prec})" if prec else type_name
    elif type_name == 'datetime2':
        type_str = f"datetime2({scale})"
    else:
        type_str = type_name
        
    null_str = "NULL" if nullable else "NOT NULL"
    identity_str = f" IDENTITY({seed},{incr})" if is_id else ""
    collation_str = f" COLLATE {collation}" if collation else ""
    
    return f"    [{name}] {type_str}{identity_str}{collation_str} {null_str}"

# ---------------------------------------------------------------------------
# Schema export
# ---------------------------------------------------------------------------

def export_schema(profile_name, database, output_dir, job_id, chunk_size=10_000):
    """
    Exports the full schema of `database` to a gzip-compressed SQL script.
    Returns the path to the output file.
    """
    tracker.update_progress(job_id, message=f"Connecting to source: {profile_name}/{database}")
    conn = get_connection(profile_name, database)
    cursor = conn.cursor()
    
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, f"{database}_schema.sql.gz")
    
    with gzip.open(output_file, 'wt', encoding='utf-8') as f:
        f.write(f"-- Pivoteer schema export: {database}\n-- Source: {profile_name}\n\n")
        f.write(f"USE [{database}];\nGO\n\n")
        
        # --- Tables ---
        tracker.update_progress(job_id, message="Extracting table definitions...")
        cursor.execute(_SQL_LIST_TABLES)
        tables = cursor.fetchall()
        
        for schema_name, table_name in tables:
            qualified = f"[{schema_name}].[{table_name}]"
            tracker.update_progress(job_id, message=f"Table: {qualified}")
            
            col_cursor = conn.cursor()
            col_cursor.execute(_SQL_TABLE_COLUMNS, (f"{schema_name}.{table_name}",))
            cols = col_cursor.fetchall()
            
            col_defs = [_column_ddl(c) for c in cols]
            
            # Primary key from indexes
            idx_cursor = conn.cursor()
            idx_cursor.execute(_SQL_TABLE_INDEXES, (f"{schema_name}.{table_name}",))
            indexes = idx_cursor.fetchall()
            
            pk_lines = []
            idx_lines = []
            for idx_name, idx_type, is_unique, is_pk, cols_str in indexes:
                if is_pk:
                    pk_lines.append(f"    CONSTRAINT [{idx_name}] PRIMARY KEY {idx_type} ({cols_str})")
                else:
                    unique_kw = "UNIQUE " if is_unique else ""
                    idx_lines.append(
                        f"CREATE {unique_kw}INDEX [{idx_name}] ON {qualified} ({cols_str});\nGO"
                    )
                    
            all_defs = col_defs + pk_lines
            create_stmt = (
                f"IF OBJECT_ID('{schema_name}.{table_name}', 'U') IS NULL\n"
                f"CREATE TABLE {qualified} (\n"
                + ",\n".join(all_defs)
                + "\n);\nGO\n"
            )
            f.write(apply_all_conversions(create_stmt))
            for idx_stmt in idx_lines:
                f.write(apply_all_conversions(idx_stmt) + "\n")
                
            # Foreign keys
            fk_cursor = conn.cursor()
            fk_cursor.execute(_SQL_TABLE_FK, (f"{schema_name}.{table_name}",))
            for fk_name, parent_tbl, parent_col, ref_tbl, ref_col in fk_cursor.fetchall():
                fk_stmt = (
                    f"ALTER TABLE [{schema_name}].[{parent_tbl}] "
                    f"ADD CONSTRAINT [{fk_name}] FOREIGN KEY ([{parent_col}]) "
                    f"REFERENCES [{ref_tbl}] ([{ref_col}]);\nGO\n"
                )
                f.write(fk_stmt)
                
        # --- Views ---
        tracker.update_progress(job_id, message="Extracting views...")
        cursor.execute(_SQL_VIEWS)
        for schema_name, view_name, definition in cursor.fetchall():
            f.write(f"\n-- View: [{schema_name}].[{view_name}]\n")
            f.write(apply_all_conversions(definition) + "\nGO\n")
            
        # --- Stored Procedures ---
        tracker.update_progress(job_id, message="Extracting stored procedures...")
        cursor.execute(_SQL_PROCS)
        for schema_name, proc_name, definition in cursor.fetchall():
            f.write(f"\n-- Procedure: [{schema_name}].[{proc_name}]\n")
            f.write(apply_all_conversions(definition) + "\nGO\n")
            
        # --- Functions ---
        tracker.update_progress(job_id, message="Extracting functions...")
        cursor.execute(_SQL_FUNCTIONS)
        for schema_name, func_name, definition in cursor.fetchall():
            f.write(f"\n-- Function: [{schema_name}].[{func_name}]\n")
            f.write(apply_all_conversions(definition) + "\nGO\n")
            
        # --- Triggers ---
        tracker.update_progress(job_id, message="Extracting triggers...")
        cursor.execute(_SQL_TRIGGERS)
        for schema_name, trigger_name, definition in cursor.fetchall():
            f.write(f"\n-- Trigger: [{trigger_name}]\n")
            f.write(apply_all_conversions(definition) + "\nGO\n")
            
        # --- Logins and Users ---
        tracker.update_progress(job_id, message="Extracting logins and users...")
        try:
            cursor.execute(_SQL_LOGINS)
            for login_name, type_desc, default_db in cursor.fetchall():
                login_stmt = f"IF NOT EXISTS (SELECT 1 FROM sys.sql_logins WHERE name = '{login_name}')\n"
                login_stmt += f"CREATE LOGIN [{login_name}] WITH PASSWORD = 'ChangeMe123!', DEFAULT_DATABASE = [{default_db}];\nGO\n"
                f.write(apply_all_conversions(login_stmt))
        except Exception:
            f.write("-- NOTE: Could not extract logins (requires sysadmin or securityadmin role)\n")
            
        try:
            cursor.execute(_SQL_DB_USERS)
            for user_name, type_desc, login_name in cursor.fetchall():
                login_ref = f"FOR LOGIN [{login_name}]" if login_name else "WITHOUT LOGIN"
                user_stmt = f"IF NOT EXISTS (SELECT 1 FROM sys.database_principals WHERE name = '{user_name}')\n"
                user_stmt += f"CREATE USER [{user_name}] {login_ref};\nGO\n"
                f.write(user_stmt)
        except Exception:
            f.write("-- NOTE: Could not extract database users\n")
            
    conn.close()
    tracker.update_progress(job_id, message="Schema extraction complete.")
    return output_file

# ---------------------------------------------------------------------------
# Data export (chunked, TB-safe)
# ---------------------------------------------------------------------------

def export_data(profile_name, database, output_dir, job_id, chunk_size=10_000):
    """
    Exports all table data as INSERT statements in a gzip-compressed SQL script.
    Streams data in chunks to avoid memory exhaustion on large tables.
    Returns the path to the output file.
    """
    tracker.update_progress(job_id, message=f"Connecting to source for data export: {profile_name}/{database}")
    conn = get_connection(profile_name, database)
    cursor = conn.cursor()
    
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, f"{database}_data.sql.gz")
    
    cursor.execute(_SQL_LIST_TABLES)
    tables = cursor.fetchall()
    
    with gzip.open(output_file, 'wt', encoding='utf-8') as f:
        f.write(f"-- Pivoteer data export: {database}\n-- Source: {profile_name}\n\n")
        f.write(f"USE [{database}];\nGO\n\n")
        
        for schema_name, table_name in tables:
            qualified = f"[{schema_name}].[{table_name}]"
            
            # Get row count for progress reporting
            try:
                count_cursor = conn.cursor()
                count_cursor.execute(_SQL_ROW_COUNT.format(schema=schema_name, table=table_name))
                row_count = count_cursor.fetchone()[0]
            except Exception:
                row_count = 0
                
            tracker.update_progress(job_id, message=f"Exporting data: {qualified} ({row_count:,} rows)")
            
            # Get column names
            col_cursor = conn.cursor()
            col_cursor.execute(_SQL_TABLE_COLUMNS, (f"{schema_name}.{table_name}",))
            col_names = [row[0] for row in col_cursor.fetchall()]
            col_list = ", ".join(f"[{c}]" for c in col_names)
            
            f.write(f"\n-- Data: {qualified}\n")
            f.write(f"SET IDENTITY_INSERT {qualified} ON;\nGO\n")
            
            # Chunked read
            offset = 0
            data_cursor = conn.cursor()
            while True:
                try:
                    data_cursor.execute(
                        f"SELECT {col_list} FROM {qualified} ORDER BY (SELECT NULL) "
                        f"OFFSET {offset} ROWS FETCH NEXT {chunk_size} ROWS ONLY"
                    )
                    rows = data_cursor.fetchall()
                    if not rows:
                        break
                        
                    for row in rows:
                        values = []
                        for val in row:
                            if val is None:
                                values.append("NULL")
                            elif isinstance(val, (int, float)):
                                values.append(str(val))
                            else:
                                escaped = str(val).replace("'", "''")
                                values.append(f"N'{escaped}'")
                        val_str = ", ".join(values)
                        f.write(f"INSERT INTO {qualified} ({col_list}) VALUES ({val_str});\n")
                        
                    offset += chunk_size
                    
                except Exception as e:
                    tracker.log_error(job_id, f"Error exporting data from {qualified}: {e}")
                    f.write(f"-- ERROR exporting data from {qualified}: {e}\n")
                    traceback.print_exc()
                    break
                    
            f.write(f"SET IDENTITY_INSERT {qualified} OFF;\nGO\n")
            
    conn.close()
    tracker.update_progress(job_id, message="Data extraction complete.")
    return output_file
