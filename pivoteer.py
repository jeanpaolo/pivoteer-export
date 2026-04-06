#!/usr/bin/env python3
"""
pivoteer.py — Azure SQL Database to AWS RDS SQL Server migration tool.

Usage:
  pivoteer setup                         Interactive profile setup wizard
  pivoteer migrate --src P --dst P --db D [--outdir DIR] [--format sql_gz|bacpac]
  pivoteer sync    --src P --dst P --db D --every N
  pivoteer status  --job JOB_ID
  pivoteer history
  pivoteer serve   [--port 8080]         Start the REST API server
"""

import argparse
import sys
import os
import uuid
import traceback
import threading
import time

# Ensure the project root is on the path when run directly
sys.path.insert(0, os.path.dirname(__file__))

# Bootstrap dependencies before importing project modules
import bootstrap
bootstrap.install_dependencies()

from core.config import interactive_setup, get_profile
from core.exporter import export_schema, export_data
from core.importer import import_sql_gz
from core.scheduler import schedule_sync, list_jobs
from core.status import tracker
from core.joblog import log_job_start, log_job_end, get_job_history

def _print_progress(job_id, stop_event):
    """Background thread that prints live progress to STDOUT."""
    while not stop_event.is_set():
        status = tracker.get_status(job_id)
        if status.get("status") in ("completed", "error", "not_found"):
            break
        pct = status.get("percentage", 0.0)
        desc = status.get("description", "")
        print(f"\r  [{pct:5.1f}%] {desc[:70]:<70}", end="", flush=True)
        time.sleep(0.5)
    print()  # newline after progress

def cmd_setup(args):
    interactive_setup()

def cmd_migrate(args):
    job_id = str(uuid.uuid4())
    outdir = args.outdir or "./pivoteer_output"
    fmt = args.format or "sql_gz"
    
    print(f"Starting migration job: {job_id}")
    print(f"  Source  : {args.src}/{args.db}")
    print(f"  Target  : {args.dst}/{args.db}")
    print(f"  Format  : {fmt}")
    print(f"  Output  : {outdir}")
    
    tracker.start_job(job_id, total_steps=6, description="Initialising migration...")
    log_job_start(job_id, "migrate", args.src, args.dst, args.db)
    
    stop_event = threading.Event()
    progress_thread = threading.Thread(target=_print_progress, args=(job_id, stop_event), daemon=True)
    progress_thread.start()
    
    try:
        if fmt == "bacpac":
            from formats.bacpac import export_bacpac, import_bacpac
            os.makedirs(outdir, exist_ok=True)
            bacpac_path = os.path.join(outdir, f"{args.db}.bacpac")
            export_bacpac(args.src, args.db, bacpac_path)
            import_bacpac(args.dst, args.db, bacpac_path)
        else:
            schema_file = export_schema(args.src, args.db, outdir, job_id)
            tracker.update_progress(job_id, step_increment=2)
            data_file = export_data(args.src, args.db, outdir, job_id)
            tracker.update_progress(job_id, step_increment=2)
            import_sql_gz(args.dst, args.db, schema_file, job_id)
            tracker.update_progress(job_id, step_increment=1)
            import_sql_gz(args.dst, args.db, data_file, job_id)
            tracker.update_progress(job_id, step_increment=1)
            
        tracker.complete_job(job_id)
        log_job_end(job_id, "completed")
        stop_event.set()
        progress_thread.join()
        print(f"\nMigration job {job_id} completed successfully.")
        
    except Exception as e:
        tracker.log_error(job_id, str(e))
        log_job_end(job_id, "error", str(e))
        stop_event.set()
        progress_thread.join()
        print(f"\nMigration job {job_id} FAILED: {e}")
        traceback.print_exc()
        sys.exit(1)

def cmd_sync(args):
    job_id = schedule_sync(args.src, args.dst, args.db, args.every)
    print(f"Scheduled sync job: {job_id}")
    print(f"  Database : {args.db}")
    print(f"  Interval : every {args.every} minute(s)")
    print(f"  Source   : {args.src}")
    print(f"  Target   : {args.dst}")
    print("  Use 'pivoteer serve' to keep the scheduler running.")

def cmd_status(args):
    status = tracker.get_status(args.job)
    print(f"Job ID   : {args.job}")
    print(f"Status   : {status.get('status', 'unknown')}")
    print(f"Progress : {status.get('percentage', 0.0):.1f}%")
    print(f"Step     : {status.get('description', '')}")
    errors = status.get('errors', [])
    if errors:
        print("Errors:")
        for err in errors:
            print(f"  - {err}")

def cmd_history(args):
    rows = get_job_history()
    if not rows:
        print("No job history found.")
        return
    print(f"{'ID':<38} {'Type':<10} {'DB':<20} {'Status':<12} {'Source':<20} {'Target':<20}")
    print("-" * 120)
    for r in rows:
        print(f"{r[0]:<38} {r[1]:<10} {r[4]:<20} {r[5]:<12} {r[2]:<20} {r[3]:<20}")

def cmd_serve(args):
    from api.server import run_server
    port = args.port or 8080
    run_server(port=port)

def build_parser():
    parser = argparse.ArgumentParser(
        prog="pivoteer",
        description="Azure SQL Database → AWS RDS SQL Server migration tool"
    )
    sub = parser.add_subparsers(dest="command", metavar="COMMAND")
    
    # setup
    sub.add_parser("setup", help="Interactive profile setup wizard")
    
    # migrate
    m = sub.add_parser("migrate", help="Full schema + data migration")
    m.add_argument("--src", required=True, metavar="PROFILE", help="Source profile name")
    m.add_argument("--dst", required=True, metavar="PROFILE", help="Target profile name")
    m.add_argument("--db", required=True, metavar="DATABASE", help="Database name")
    m.add_argument("--outdir", default="./pivoteer_output", metavar="DIR", help="Output directory")
    m.add_argument("--format", choices=["sql_gz", "bacpac"], default="sql_gz",
                   help="Output format: sql_gz (default) or bacpac")
    
    # sync
    s = sub.add_parser("sync", help="Schedule incremental sync")
    s.add_argument("--src", required=True, metavar="PROFILE")
    s.add_argument("--dst", required=True, metavar="PROFILE")
    s.add_argument("--db", required=True, metavar="DATABASE")
    s.add_argument("--every", required=True, type=int, metavar="MINUTES",
                   help="Sync interval in minutes")
    
    # status
    st = sub.add_parser("status", help="Poll job status")
    st.add_argument("--job", required=True, metavar="JOB_ID")
    
    # history
    sub.add_parser("history", help="List past job runs")
    
    # serve
    sv = sub.add_parser("serve", help="Start the REST API server")
    sv.add_argument("--port", type=int, default=8080, metavar="PORT")
    
    return parser

def main():
    parser = build_parser()
    args = parser.parse_args()
    
    dispatch = {
        "setup": cmd_setup,
        "migrate": cmd_migrate,
        "sync": cmd_sync,
        "status": cmd_status,
        "history": cmd_history,
        "serve": cmd_serve,
    }
    
    if args.command in dispatch:
        dispatch[args.command](args)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
