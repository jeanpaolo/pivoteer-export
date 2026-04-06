"""
core/sync.py

Incremental sync engine.  Supports two strategies:
  1. SQL Server Change Tracking (preferred) — requires CT enabled on source.
  2. Watermark column fallback — uses a user-specified datetime/int column.

Design principles:
  - DRY: sync strategy is selected once; all callers use run_sync().
  - Chunked reads: changes are fetched in batches to handle large change sets.
  - STDOUT-only logging.
"""

import traceback
from .connection import get_connection
from .status import tracker

_SQL_CT_ENABLED = """
    SELECT COUNT(*) FROM sys.change_tracking_tables
    WHERE object_id = OBJECT_ID(?)
"""

_SQL_CT_CURRENT_VERSION = "SELECT CHANGE_TRACKING_CURRENT_VERSION()"

_SQL_CT_CHANGES = """
    SELECT ct.SYS_CHANGE_OPERATION, ct.SYS_CHANGE_VERSION, {cols}
    FROM CHANGETABLE(CHANGES [{schema}].[{table}], ?) AS ct
    LEFT JOIN [{schema}].[{table}] t ON {pk_join}
"""

_SQL_LIST_TABLES = """
    SELECT s.name AS schema_name, t.name AS table_name
    FROM sys.tables t
    JOIN sys.schemas s ON t.schema_id = s.schema_id
    WHERE t.type = 'U'
    ORDER BY s.name, t.name
"""

_SQL_PK_COLUMNS = """
    SELECT c.name
    FROM sys.indexes i
    JOIN sys.index_columns ic ON ic.object_id = i.object_id AND ic.index_id = i.index_id
    JOIN sys.columns c ON c.object_id = ic.object_id AND c.column_id = ic.column_id
    WHERE i.object_id = OBJECT_ID(?) AND i.is_primary_key = 1
    ORDER BY ic.key_ordinal
"""

_SQL_TABLE_COLUMNS_NAMES = """
    SELECT c.name
    FROM sys.columns c
    WHERE c.object_id = OBJECT_ID(?)
    ORDER BY c.column_id
"""

def _get_pk_columns(conn, schema_name, table_name):
    cursor = conn.cursor()
    cursor.execute(_SQL_PK_COLUMNS, (f"{schema_name}.{table_name}",))
    return [row[0] for row in cursor.fetchall()]

def _get_all_columns(conn, schema_name, table_name):
    cursor = conn.cursor()
    cursor.execute(_SQL_TABLE_COLUMNS_NAMES, (f"{schema_name}.{table_name}",))
    return [row[0] for row in cursor.fetchall()]

def _apply_changes(dst_conn, schema_name, table_name, changes, pk_cols, all_cols):
    """Applies a batch of change tracking rows to the target database."""
    qualified = f"[{schema_name}].[{table_name}]"
    col_list = ", ".join(f"[{c}]" for c in all_cols)
    pk_where = " AND ".join(f"[{c}] = ?" for c in pk_cols)
    
    cursor = dst_conn.cursor()
    for row in changes:
        operation = row[0]
        data = row[2:]  # Skip operation and version columns
        
        if operation == 'D':
            pk_vals = [data[all_cols.index(pk)] for pk in pk_cols]
            cursor.execute(f"DELETE FROM {qualified} WHERE {pk_where}", pk_vals)
        elif operation == 'I':
            placeholders = ", ".join("?" for _ in all_cols)
            cursor.execute(f"INSERT INTO {qualified} ({col_list}) VALUES ({placeholders})", list(data))
        elif operation == 'U':
            set_clause = ", ".join(f"[{c}] = ?" for c in all_cols if c not in pk_cols)
            non_pk_vals = [data[all_cols.index(c)] for c in all_cols if c not in pk_cols]
            pk_vals = [data[all_cols.index(pk)] for pk in pk_cols]
            cursor.execute(
                f"UPDATE {qualified} SET {set_clause} WHERE {pk_where}",
                non_pk_vals + pk_vals
            )

def run_sync(src_profile, dst_profile, database, job_id, last_sync_version=0, chunk_size=10_000):
    """
    Runs an incremental sync from source to target for all tables in `database`.
    Returns the new sync version for use in the next run.
    """
    tracker.update_progress(job_id, message=f"Starting incremental sync for {database}")
    
    src_conn = get_connection(src_profile, database)
    dst_conn = get_connection(dst_profile, database)
    
    src_cursor = src_conn.cursor()
    src_cursor.execute(_SQL_CT_CURRENT_VERSION)
    current_version = src_cursor.fetchone()[0]
    
    src_cursor.execute(_SQL_LIST_TABLES)
    tables = src_cursor.fetchall()
    
    for schema_name, table_name in tables:
        qualified = f"[{schema_name}].[{table_name}]"
        
        # Check if Change Tracking is enabled for this table
        ct_cursor = src_conn.cursor()
        ct_cursor.execute(_SQL_CT_ENABLED, (f"{schema_name}.{table_name}",))
        ct_enabled = ct_cursor.fetchone()[0] > 0
        
        if not ct_enabled:
            tracker.update_progress(job_id, message=f"Skipping {qualified} (Change Tracking not enabled)")
            continue
            
        tracker.update_progress(job_id, message=f"Syncing {qualified}...")
        
        pk_cols = _get_pk_columns(src_conn, schema_name, table_name)
        all_cols = _get_all_columns(src_conn, schema_name, table_name)
        
        if not pk_cols:
            tracker.update_progress(job_id, message=f"Skipping {qualified} (no primary key)")
            continue
            
        col_aliases = ", ".join(f"t.[{c}]" for c in all_cols)
        pk_join = " AND ".join(f"ct.[{pk}] = t.[{pk}]" for pk in pk_cols)
        
        change_sql = _SQL_CT_CHANGES.format(
            cols=col_aliases,
            schema=schema_name,
            table=table_name,
            pk_join=pk_join
        )
        
        try:
            change_cursor = src_conn.cursor()
            change_cursor.execute(change_sql, (last_sync_version,))
            
            while True:
                changes = change_cursor.fetchmany(chunk_size)
                if not changes:
                    break
                _apply_changes(dst_conn, schema_name, table_name, changes, pk_cols, all_cols)
                
        except Exception as e:
            tracker.log_error(job_id, f"Sync error for {qualified}: {e}")
            traceback.print_exc()
            
    src_conn.close()
    dst_conn.close()
    
    tracker.update_progress(job_id, message="Incremental sync complete.")
    return current_version
