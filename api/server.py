"""
api/server.py

Lightweight REST API for Pivoteer.  Uses only Python stdlib (http.server).
No Flask, no FastAPI, no external web framework.

Endpoints:
  POST   /jobs/migrate          Start a migration job
  POST   /jobs/sync             Schedule a recurring sync job
  GET    /jobs/{id}             Get job status
  DELETE /jobs/{id}             Cancel/remove a scheduled job
  GET    /jobs                  List all scheduled jobs
  GET    /history               List past job runs from SQLite
"""

import json
import sys
import traceback
import threading
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer
from core.status import tracker
from core.joblog import log_job_start, log_job_end, get_job_history
from core.scheduler import schedule_sync, remove_sync, list_jobs
from core.exporter import export_schema, export_data
from core.importer import import_sql_gz

def _json_response(handler, status_code, data):
    body = json.dumps(data).encode('utf-8')
    handler.send_response(status_code)
    handler.send_header('Content-Type', 'application/json')
    handler.send_header('Content-Length', str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)

def _read_json_body(handler):
    length = int(handler.headers.get('Content-Length', 0))
    if length == 0:
        return {}
    return json.loads(handler.rfile.read(length))

def _run_migration_async(job_id, src, dst, db, outdir, fmt):
    """Runs a full migration in a background thread."""
    try:
        tracker.start_job(job_id, total_steps=4, description=f"Migrating {db}: {src} -> {dst}")
        log_job_start(job_id, "migrate", src, dst, db)
        
        if fmt == "bacpac":
            from formats.bacpac import export_bacpac, import_bacpac
            bacpac_path = f"{outdir}/{db}.bacpac"
            export_bacpac(src, db, bacpac_path)
            import_bacpac(dst, db, bacpac_path)
        else:
            schema_file = export_schema(src, db, outdir, job_id)
            tracker.update_progress(job_id, step_increment=1)
            data_file = export_data(src, db, outdir, job_id)
            tracker.update_progress(job_id, step_increment=1)
            import_sql_gz(dst, db, schema_file, job_id)
            tracker.update_progress(job_id, step_increment=1)
            import_sql_gz(dst, db, data_file, job_id)
            tracker.update_progress(job_id, step_increment=1)
            
        tracker.complete_job(job_id)
        log_job_end(job_id, "completed")
    except Exception as e:
        tracker.log_error(job_id, str(e))
        log_job_end(job_id, "error", str(e))
        traceback.print_exc()

class PivoteerHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Redirect access log to STDOUT
        print(f"[API] {self.address_string()} - {format % args}")
        
    def do_GET(self):
        try:
            if self.path == '/jobs':
                _json_response(self, 200, list_jobs())
            elif self.path.startswith('/jobs/'):
                job_id = self.path.split('/')[-1]
                _json_response(self, 200, tracker.get_status(job_id))
            elif self.path == '/history':
                rows = get_job_history()
                history = [
                    {"id": r[0], "type": r[1], "source": r[2], "target": r[3],
                     "database": r[4], "status": r[5], "start_time": r[6],
                     "end_time": r[7], "errors": r[8]}
                    for r in rows
                ]
                _json_response(self, 200, history)
            else:
                _json_response(self, 404, {"error": "Not found"})
        except Exception as e:
            traceback.print_exc()
            _json_response(self, 500, {"error": str(e)})
            
    def do_POST(self):
        try:
            data = _read_json_body(self)
            
            if self.path == '/jobs/migrate':
                required = ['src', 'dst', 'db']
                missing = [k for k in required if k not in data]
                if missing:
                    _json_response(self, 400, {"error": f"Missing fields: {missing}"})
                    return
                    
                job_id = str(uuid.uuid4())
                outdir = data.get('outdir', '/tmp/pivoteer')
                fmt = data.get('format', 'sql_gz')
                
                thread = threading.Thread(
                    target=_run_migration_async,
                    args=(job_id, data['src'], data['dst'], data['db'], outdir, fmt),
                    daemon=True
                )
                thread.start()
                _json_response(self, 202, {"job_id": job_id, "status": "accepted"})
                
            elif self.path == '/jobs/sync':
                required = ['src', 'dst', 'db', 'interval_minutes']
                missing = [k for k in required if k not in data]
                if missing:
                    _json_response(self, 400, {"error": f"Missing fields: {missing}"})
                    return
                    
                job_id = schedule_sync(
                    data['src'], data['dst'], data['db'],
                    int(data['interval_minutes'])
                )
                _json_response(self, 202, {"job_id": job_id, "status": "scheduled"})
                
            else:
                _json_response(self, 404, {"error": "Not found"})
                
        except Exception as e:
            traceback.print_exc()
            _json_response(self, 500, {"error": str(e)})
            
    def do_DELETE(self):
        try:
            if self.path.startswith('/jobs/'):
                job_id = self.path.split('/')[-1]
                removed = remove_sync(job_id)
                if removed:
                    _json_response(self, 200, {"status": "removed", "job_id": job_id})
                else:
                    _json_response(self, 404, {"error": "Job not found or not a scheduled job"})
            else:
                _json_response(self, 404, {"error": "Not found"})
        except Exception as e:
            traceback.print_exc()
            _json_response(self, 500, {"error": str(e)})

def run_server(host='0.0.0.0', port=8080):
    server = HTTPServer((host, port), PivoteerHandler)
    print(f"Pivoteer REST API listening on {host}:{port}")
    server.serve_forever()

if __name__ == '__main__':
    run_server()
