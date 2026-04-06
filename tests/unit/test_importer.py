import pytest
import gzip
import os
from unittest.mock import MagicMock, patch, call
from core.importer import _split_batches, import_sql_gz

def test_split_batches_basic():
    sql = "SELECT 1;\nGO\nSELECT 2;\nGO\n"
    batches = _split_batches(sql)
    assert len(batches) == 2
    assert batches[0] == "SELECT 1;"
    assert batches[1] == "SELECT 2;"

def test_split_batches_case_insensitive():
    sql = "SELECT 1;\ngo\nSELECT 2;\nGo\n"
    batches = _split_batches(sql)
    assert len(batches) == 2

def test_split_batches_no_go():
    sql = "SELECT 1; SELECT 2;"
    batches = _split_batches(sql)
    assert len(batches) == 1

def test_split_batches_empty():
    sql = "GO\nGO\n"
    batches = _split_batches(sql)
    assert len(batches) == 0

def test_import_sql_gz_executes_batches(tmp_path):
    sql_content = "CREATE TABLE t1 (id INT);\nGO\nINSERT INTO t1 VALUES (1);\nGO\n"
    gz_file = tmp_path / "test.sql.gz"
    with gzip.open(gz_file, 'wt') as f:
        f.write(sql_content)
    
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    
    with patch("core.importer.get_connection", return_value=mock_conn):
        import_sql_gz("test-profile", "testdb", str(gz_file), "test-job")
    
    assert mock_cursor.execute.call_count == 2
    calls = mock_cursor.execute.call_args_list
    assert "CREATE TABLE t1" in calls[0][0][0]
    assert "INSERT INTO t1" in calls[1][0][0]

def test_import_sql_gz_continues_on_error(tmp_path):
    """Errors in one batch should not stop subsequent batches."""
    sql_content = "INVALID SQL;\nGO\nSELECT 1;\nGO\n"
    gz_file = tmp_path / "test.sql.gz"
    with gzip.open(gz_file, 'wt') as f:
        f.write(sql_content)
    
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.execute.side_effect = [Exception("Syntax error"), None]
    mock_conn.cursor.return_value = mock_cursor
    
    with patch("core.importer.get_connection", return_value=mock_conn):
        import_sql_gz("test-profile", "testdb", str(gz_file), "test-job-2")
    
    # Both batches should have been attempted
    assert mock_cursor.execute.call_count == 2
