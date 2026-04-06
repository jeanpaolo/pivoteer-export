"""
core/importer.py

Applies a gzip-compressed SQL script to a target SQL Server instance.
Splits on GO statements (case-insensitive, standalone line) and executes
each batch individually so that errors are isolated and reported.
"""

import gzip
import re
import sys
import traceback
from .connection import get_connection
from .status import tracker

# Matches a standalone GO on its own line (SQL Server batch separator)
_GO_PATTERN = re.compile(r'^\s*GO\s*$', re.MULTILINE | re.IGNORECASE)

def _split_batches(sql_script):
    """Splits a SQL script into executable batches on GO separators."""
    return [b.strip() for b in _GO_PATTERN.split(sql_script) if b.strip()]

def import_sql_gz(profile_name, database, input_file, job_id):
    """
    Reads a .sql.gz file and executes each batch against the target database.
    Errors are logged to the job tracker and printed to STDOUT; execution
    continues for remaining batches.
    """
    tracker.update_progress(job_id, message=f"Connecting to target: {profile_name}/{database}")
    conn = get_connection(profile_name, database)
    cursor = conn.cursor()
    
    tracker.update_progress(job_id, message=f"Reading {input_file}...")
    with gzip.open(input_file, 'rt', encoding='utf-8') as f:
        sql_script = f.read()
        
    batches = _split_batches(sql_script)
    total = len(batches)
    errors = 0
    
    for i, batch in enumerate(batches, 1):
        preview = batch[:80].replace('\n', ' ')
        tracker.update_progress(job_id, message=f"Executing batch {i}/{total}: {preview}...")
        try:
            cursor.execute(batch)
        except Exception as e:
            errors += 1
            msg = f"Batch {i}/{total} error: {e}\nSQL: {batch[:200]}"
            tracker.log_error(job_id, msg)
            print(msg, file=sys.stdout)
            traceback.print_exc()
            
    conn.close()
    tracker.update_progress(job_id, message=f"Import complete. {total} batches, {errors} errors.")
