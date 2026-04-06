"""
Integration tests for end-to-end migration.

Prerequisites:
  - PIVOTEER_TEST_SRC env var: source profile name in ~/.pivoteer/config.yaml
  - PIVOTEER_TEST_DST env var: target profile name in ~/.pivoteer/config.yaml
  - PIVOTEER_TEST_DB  env var: database name to migrate

Run with: python3 -m pytest tests/integration/ --integration
"""
import pytest
import os
import gzip
from core.exporter import export_schema, export_data
from core.importer import import_sql_gz
from core.status import tracker
import uuid

SRC = os.environ.get("PIVOTEER_TEST_SRC")
DST = os.environ.get("PIVOTEER_TEST_DST")
DB = os.environ.get("PIVOTEER_TEST_DB")

@pytest.mark.skipif(not SRC or not DST or not DB, reason="PIVOTEER_TEST_SRC/DST/DB env vars not set")
def test_schema_export(tmp_path):
    job_id = str(uuid.uuid4())
    tracker.start_job(job_id, total_steps=5, description="Schema export test")
    
    output_file = export_schema(SRC, DB, str(tmp_path), job_id)
    
    assert os.path.exists(output_file)
    with gzip.open(output_file, 'rt') as f:
        content = f.read()
    assert len(content) > 0

@pytest.mark.skipif(not SRC or not DST or not DB, reason="PIVOTEER_TEST_SRC/DST/DB env vars not set")
def test_data_export(tmp_path):
    job_id = str(uuid.uuid4())
    tracker.start_job(job_id, total_steps=5, description="Data export test")
    
    output_file = export_data(SRC, DB, str(tmp_path), job_id)
    
    assert os.path.exists(output_file)

@pytest.mark.skipif(not SRC or not DST or not DB, reason="PIVOTEER_TEST_SRC/DST/DB env vars not set")
def test_full_migration(tmp_path):
    job_id = str(uuid.uuid4())
    tracker.start_job(job_id, total_steps=4, description="Full migration test")
    
    schema_file = export_schema(SRC, DB, str(tmp_path), job_id)
    data_file = export_data(SRC, DB, str(tmp_path), job_id)
    
    import_sql_gz(DST, DB, schema_file, job_id)
    import_sql_gz(DST, DB, data_file, job_id)
    
    tracker.complete_job(job_id)
    status = tracker.get_status(job_id)
    assert status["status"] == "completed"
