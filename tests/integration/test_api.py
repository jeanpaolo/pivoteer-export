"""
Integration tests for the REST API.

Run with: python3 -m pytest tests/integration/ --integration
"""
import pytest
import json
import threading
import time
from http.client import HTTPConnection
from api.server import run_server
from core.status import tracker

@pytest.fixture(scope="module")
def api_server():
    """Start the REST API server in a background thread."""
    thread = threading.Thread(target=run_server, kwargs={"port": 18080}, daemon=True)
    thread.start()
    time.sleep(0.5)  # Allow server to start
    yield
    # Server is a daemon thread, it will stop when the test process exits

def test_get_job_status_not_found(api_server):
    conn = HTTPConnection("localhost", 18080)
    conn.request("GET", "/jobs/nonexistent-job-id")
    response = conn.getresponse()
    assert response.status == 200
    data = json.loads(response.read())
    assert data["status"] == "not_found"

def test_post_job_and_get_status(api_server):
    conn = HTTPConnection("localhost", 18080)
    payload = json.dumps({"src": "test-src", "dst": "test-dst", "db": "testdb"}).encode()
    conn.request("POST", "/jobs", body=payload, headers={"Content-Length": str(len(payload))})
    response = conn.getresponse()
    assert response.status == 202
    data = json.loads(response.read())
    assert "job_id" in data
    
    job_id = data["job_id"]
    conn.request("GET", f"/jobs/{job_id}")
    response = conn.getresponse()
    assert response.status == 200
    status_data = json.loads(response.read())
    assert "status" in status_data
