import pytest
from core.status import JobStatus

def test_job_status_lifecycle():
    tracker = JobStatus()
    job_id = "test-job-1"
    
    tracker.start_job(job_id, total_steps=10, description="Starting")
    status = tracker.get_status(job_id)
    assert status["status"] == "running"
    assert status["current_step"] == 0
    assert status["percentage"] == 0.0
    
    tracker.update_progress(job_id, step_increment=5, message="Halfway")
    status = tracker.get_status(job_id)
    assert status["current_step"] == 5
    assert status["percentage"] == 50.0
    assert status["description"] == "Halfway"
    
    tracker.log_error(job_id, "Something went wrong")
    status = tracker.get_status(job_id)
    assert status["status"] == "error"
    assert len(status["errors"]) == 1
    
    tracker.complete_job(job_id)
    status = tracker.get_status(job_id)
    assert status["status"] == "error" # Should not override error status
    assert status["percentage"] == 100.0
    
    # Test successful completion
    job_id2 = "test-job-2"
    tracker.start_job(job_id2, total_steps=2, description="Starting")
    tracker.update_progress(job_id2, step_increment=2)
    tracker.complete_job(job_id2)
    status2 = tracker.get_status(job_id2)
    assert status2["status"] == "completed"
    assert status2["percentage"] == 100.0
