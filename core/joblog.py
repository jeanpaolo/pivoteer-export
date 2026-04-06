import sqlite3
import os
import time

DB_PATH = os.path.expanduser("~/.pivoteer/joblog.db")

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY,
            type TEXT,
            source TEXT,
            target TEXT,
            database TEXT,
            status TEXT,
            start_time REAL,
            end_time REAL,
            errors TEXT
        )
    ''')
    conn.commit()
    conn.close()

def log_job_start(job_id, job_type, source, target, database):
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO jobs (id, type, source, target, database, status, start_time)
        VALUES (?, ?, ?, ?, ?, 'running', ?)
    ''', (job_id, job_type, source, target, database, time.time()))
    conn.commit()
    conn.close()

def log_job_end(job_id, status, errors=None):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE jobs SET status = ?, end_time = ?, errors = ?
        WHERE id = ?
    ''', (status, time.time(), errors, job_id))
    conn.commit()
    conn.close()

def get_job_history():
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM jobs ORDER BY start_time DESC')
    rows = cursor.fetchall()
    conn.close()
    return rows
