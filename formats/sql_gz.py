"""
formats/sql_gz.py

Utility for reading/writing gzip-compressed SQL scripts.
"""

import gzip
import os

def write_sql_gz(output_path, content):
    """Writes a SQL string to a gzip-compressed file."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with gzip.open(output_path, 'wt', encoding='utf-8') as f:
        f.write(content)

def read_sql_gz(input_path):
    """Reads and returns the content of a gzip-compressed SQL file."""
    with gzip.open(input_path, 'rt', encoding='utf-8') as f:
        return f.read()
