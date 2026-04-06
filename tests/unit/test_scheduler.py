import pytest
from unittest.mock import patch, MagicMock
from core.scheduler import schedule_sync, remove_sync, list_jobs

def test_schedule_sync_returns_job_id():
    with patch("core.scheduler.run_sync", return_value=100):
        job_id = schedule_sync("src-profile", "dst-profile", "mydb", 30)
    assert isinstance(job_id, str)
    assert len(job_id) == 36  # UUID format

def test_remove_sync():
    with patch("core.scheduler.run_sync", return_value=100):
        job_id = schedule_sync("src-profile", "dst-profile", "mydb", 60)
    result = remove_sync(job_id)
    assert result is True

def test_remove_nonexistent_sync():
    result = remove_sync("nonexistent-job-id-12345")
    assert result is False

def test_list_jobs():
    with patch("core.scheduler.run_sync", return_value=100):
        job_id = schedule_sync("src-profile", "dst-profile", "listdb", 15)
    jobs = list_jobs()
    assert isinstance(jobs, list)
    job_ids = [j["id"] for j in jobs]
    assert job_id in job_ids
    remove_sync(job_id)
