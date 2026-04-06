import threading
import time

class JobStatus:
    def __init__(self):
        self.lock = threading.Lock()
        self.jobs = {}

    def start_job(self, job_id, total_steps, description):
        with self.lock:
            self.jobs[job_id] = {
                "status": "running",
                "description": description,
                "current_step": 0,
                "total_steps": total_steps,
                "percentage": 0.0,
                "start_time": time.time(),
                "errors": []
            }

    def update_progress(self, job_id, step_increment=1, message=None):
        with self.lock:
            if job_id in self.jobs:
                job = self.jobs[job_id]
                job["current_step"] += step_increment
                if job["total_steps"] > 0:
                    job["percentage"] = min(100.0, (job["current_step"] / job["total_steps"]) * 100)
                if message:
                    job["description"] = message

    def log_error(self, job_id, error_msg):
        with self.lock:
            if job_id in self.jobs:
                self.jobs[job_id]["errors"].append(error_msg)
                self.jobs[job_id]["status"] = "error"

    def complete_job(self, job_id):
        with self.lock:
            if job_id in self.jobs:
                job = self.jobs[job_id]
                if job["status"] != "error":
                    job["status"] = "completed"
                job["percentage"] = 100.0
                job["end_time"] = time.time()

    def get_status(self, job_id):
        with self.lock:
            return self.jobs.get(job_id, {"status": "not_found"})

# Global singleton instance
tracker = JobStatus()
