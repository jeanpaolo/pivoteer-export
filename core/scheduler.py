"""
core/scheduler.py

APScheduler-backed job scheduler.  Supports dynamic add/remove/list of
recurring sync jobs without restarting the process.

Design principles:
  - DRY: all job state is stored in the SQLite job log; APScheduler is the
    execution engine only.
  - Thread-safe: BackgroundScheduler runs in its own thread.
"""

import uuid
import traceback
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from .joblog import log_job_start, log_job_end
from .status import tracker
from .sync import run_sync

# Global singleton scheduler
_scheduler = BackgroundScheduler(timezone="UTC")
_scheduler.start()

# In-memory map of job_id -> last_sync_version for incremental sync state
_sync_versions = {}

def schedule_sync(src_profile, dst_profile, database, interval_minutes):
    """
    Registers a recurring sync job.  Returns the APScheduler job ID.
    """
    job_id = str(uuid.uuid4())
    _sync_versions[job_id] = 0
    
    def _run():
        run_job_id = str(uuid.uuid4())
        tracker.start_job(run_job_id, total_steps=10,
                          description=f"Sync {database}: {src_profile} -> {dst_profile}")
        log_job_start(run_job_id, "sync", src_profile, dst_profile, database)
        
        try:
            new_version = run_sync(
                src_profile, dst_profile, database, run_job_id,
                last_sync_version=_sync_versions.get(job_id, 0)
            )
            _sync_versions[job_id] = new_version
            tracker.complete_job(run_job_id)
            log_job_end(run_job_id, "completed")
        except Exception as e:
            tracker.log_error(run_job_id, str(e))
            log_job_end(run_job_id, "error", str(e))
            traceback.print_exc()
            
    trigger = IntervalTrigger(minutes=interval_minutes)
    _scheduler.add_job(_run, trigger, id=job_id,
                       name=f"sync:{database}:{interval_minutes}m",
                       replace_existing=True)
    return job_id

def remove_sync(job_id):
    """Removes a scheduled sync job by ID."""
    if _scheduler.get_job(job_id):
        _scheduler.remove_job(job_id)
        _sync_versions.pop(job_id, None)
        return True
    return False

def list_jobs():
    """Returns a list of currently scheduled jobs."""
    return [
        {"id": job.id, "name": job.name, "next_run": str(job.next_run_time)}
        for job in _scheduler.get_jobs()
    ]
