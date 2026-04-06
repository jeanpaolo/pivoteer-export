import pytest
import os
import sqlite3
from core.joblog import init_db, log_job_start, log_job_end, get_job_history

def test_joblog_lifecycle(tmp_path, monkeypatch):
    db_file = tmp_path / "joblog.db"
    monkeypatch.setattr("core.joblog.DB_PATH", str(db_file))
    
    init_db()
    assert os.path.exists(db_file)
    
    job_id = "test-job-123"
    log_job_start(job_id, "migrate", "azure-prod", "rds-dev", "mydb")
    
    history = get_job_history()
    assert len(history) == 1
    assert history[0][0] == job_id
    assert history[0][5] == "running"
    
    log_job_end(job_id, "completed")
    
    history = get_job_history()
    assert history[0][5] == "completed"
    assert history[0][8] is None # errors
    
    log_job_end(job_id, "error", "Connection failed")
    history = get_job_history()
    assert history[0][5] == "error"
    assert history[0][8] == "Connection failed"
