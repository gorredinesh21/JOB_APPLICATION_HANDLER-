from flask import Flask, render_template, jsonify, request, send_file
import sqlite3
import os
import subprocess
import sys
import threading
import time
import uuid
from collections import deque
from datetime import datetime, timedelta


def load_env_file(env_path):
    if not os.path.exists(env_path):
        return

    with open(env_path, "r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue

            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")

            if key and key not in os.environ:
                os.environ[key] = value


# =========================================================
# 🗄️ DATABASE CONFIG
# =========================================================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_env_file(os.path.join(BASE_DIR, ".env"))
DB_PATH = os.getenv("JOBS_DB_PATH", os.path.join(BASE_DIR, "jobs_new.db"))
RESUME_BASE_PATH = os.getenv(
    "RESUME_BASE_PATH",
    os.path.join(BASE_DIR, "02_resume_engine", "LLM_COMPILED_PDFS"),
)
MAX_RUN_LOG_LINES = 300
MAX_RUN_HISTORY = 20

# Configure template/static folders from this file so imports are cwd-independent.
app = Flask(
    __name__,
    template_folder=os.path.join(SCRIPT_DIR, "templates"),
    static_folder=os.path.join(SCRIPT_DIR, "static"),
    static_url_path="/static",
)

PIPELINE_STAGES = {
    "job_sourcing": {
        "label": "Fetch Job Descriptions",
        "script": os.path.join(BASE_DIR, "01_job_sourcing", "job_sourcing.py"),
        "cwd": os.path.join(BASE_DIR, "01_job_sourcing"),
    },
    "job_filtering": {
        "label": "Score Jobs",
        "script": os.path.join(BASE_DIR, "02_job_filtering", "job_scorer.py"),
        "cwd": BASE_DIR,
    },
    "resume_json": {
        "label": "Generate Tailored Resume JSON",
        "script": os.path.join(BASE_DIR, "02_resume_engine", "generate_json.py"),
        "cwd": os.path.join(BASE_DIR, "02_resume_engine"),
    },
    "resume_pdf": {
        "label": "Compile Resume PDFs",
        "script": os.path.join(BASE_DIR, "02_resume_engine", "generate_resume.py"),
        "cwd": os.path.join(BASE_DIR, "02_resume_engine"),
    },
}
PIPELINE_SEQUENCE = ["job_sourcing", "job_filtering", "resume_json", "resume_pdf"]
RUNS = {}
RUN_ORDER = deque()
RUN_LOCK = threading.Lock()

# =========================================================
# 📊 DATABASE FUNCTIONS
# =========================================================
def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def get_all_jobs():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT * FROM job_postings 
        ORDER BY score DESC, published_date DESC
    """)
    
    jobs = cursor.fetchall()
    conn.close()
    
    return [dict(job) for job in jobs]

def get_job_by_id(job_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT * FROM job_postings 
        WHERE job_unique_id = ?
    """, (job_id,))
    
    job = cursor.fetchone()
    conn.close()
    
    return dict(job) if job else None

def run_summary(run):
    return {
        "id": run["id"],
        "stage": run["stage"],
        "label": run["label"],
        "status": run["status"],
        "started_at": run["started_at"],
        "ended_at": run["ended_at"],
        "returncode": run["returncode"],
        "duration_seconds": round(run["duration_seconds"], 1) if run["duration_seconds"] else None,
        "log_tail": list(run["logs"])[-30:],
    }

def register_run(stage, label):
    run_id = uuid.uuid4().hex[:12]
    run = {
        "id": run_id,
        "stage": stage,
        "label": label,
        "status": "queued",
        "started_at": None,
        "ended_at": None,
        "returncode": None,
        "duration_seconds": None,
        "logs": deque(maxlen=MAX_RUN_LOG_LINES),
    }

    with RUN_LOCK:
        RUNS[run_id] = run
        RUN_ORDER.appendleft(run_id)
        while len(RUN_ORDER) > MAX_RUN_HISTORY:
            old_id = RUN_ORDER.pop()
            RUNS.pop(old_id, None)

    return run

def append_run_log(run, message):
    timestamp = datetime.now().strftime("%H:%M:%S")
    with RUN_LOCK:
        run["logs"].append(f"[{timestamp}] {message.rstrip()}")

def parse_date(value):
    return datetime.strptime(value, "%Y-%m-%d").date()


def date_range(start_date, end_date):
    current = start_date
    while current <= end_date:
        yield current.strftime("%Y-%m-%d")
        current += timedelta(days=1)


def run_stage_command(run, stage_key, run_date):
    stage = PIPELINE_STAGES[stage_key]
    if not os.path.exists(stage["script"]):
        append_run_log(run, f"Missing script: {stage['script']}")
        return 127

    if stage_key != "resume_pdf" and not os.getenv("HUGGINGFACEHUB_API_TOKEN"):
        append_run_log(run, "HUGGINGFACEHUB_API_TOKEN is missing.")
        append_run_log(run, f"Add it to {os.path.join(BASE_DIR, '.env')} or export it before starting Flask.")
        return 2

    command = [sys.executable, stage["script"], "--date", run_date]
    append_run_log(run, f"Running: {' '.join(command)}")
    append_run_log(run, f"Working directory: {stage['cwd']}")

    process = subprocess.Popen(
        command,
        cwd=stage["cwd"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        env=os.environ.copy(),
    )

    for line in process.stdout:
        append_run_log(run, line)

    process.wait()
    append_run_log(run, f"Exited with code {process.returncode}")
    return process.returncode

def execute_pipeline_run(run, stage_key, run_dates):
    start = time.time()
    with RUN_LOCK:
        run["status"] = "running"
        run["started_at"] = datetime.now().isoformat(timespec="seconds")

    try:
        if stage_key == "full_pipeline":
            returncode = 0
            for run_date in run_dates:
                append_run_log(run, f"=== Date: {run_date} ===")
                for sequence_stage in PIPELINE_SEQUENCE:
                    append_run_log(run, f"--- {PIPELINE_STAGES[sequence_stage]['label']} ---")
                    returncode = run_stage_command(run, sequence_stage, run_date)
                    if returncode != 0:
                        break
                if returncode != 0:
                    break
        else:
            returncode = 0
            for run_date in run_dates:
                append_run_log(run, f"=== Date: {run_date} ===")
                returncode = run_stage_command(run, stage_key, run_date)
                if returncode != 0:
                    break

        with RUN_LOCK:
            run["returncode"] = returncode
            run["status"] = "completed" if returncode == 0 else "failed"

    except Exception as exc:
        append_run_log(run, f"Error: {exc}")
        with RUN_LOCK:
            run["returncode"] = 1
            run["status"] = "failed"

    finally:
        with RUN_LOCK:
            run["ended_at"] = datetime.now().isoformat(timespec="seconds")
            run["duration_seconds"] = time.time() - start

def query_admin_jobs(args):
    filters = []
    params = []

    search = (args.get("search") or "").strip()
    if search:
        filters.append(
            "(job_title LIKE ? OR company_name LIKE ? OR location LIKE ? OR job_description LIKE ?)"
        )
        like = f"%{search}%"
        params.extend([like, like, like, like])

    source = (args.get("source") or "").strip()
    if source:
        filters.append("source = ?")
        params.append(source)

    min_score = args.get("min_score")
    if min_score:
        filters.append("score >= ?")
        params.append(int(min_score))

    max_score = args.get("max_score")
    if max_score:
        filters.append("score <= ?")
        params.append(int(max_score))

    where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""
    limit = min(max(int(args.get("limit", 50)), 1), 200)
    offset = max(int(args.get("offset", 0)), 0)

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(f"SELECT COUNT(*) as count FROM job_postings {where_clause}", params)
    total = cursor.fetchone()["count"]

    cursor.execute(
        f"""
        SELECT *
        FROM job_postings
        {where_clause}
        ORDER BY score DESC, published_date DESC
        LIMIT ? OFFSET ?
        """,
        params + [limit, offset],
    )
    jobs = [dict(row) for row in cursor.fetchall()]

    cursor.execute("""
        SELECT source
        FROM job_postings
        WHERE source IS NOT NULL AND source != ''
        GROUP BY source
        ORDER BY source
    """)
    sources = [row["source"] for row in cursor.fetchall()]
    conn.close()

    resume_filter = (args.get("resume") or "").strip()
    for job in jobs:
        resume_path = check_resume_exists(job["job_title"], job["company_name"])
        job["resume_exists"] = resume_path is not None
        job["resume_filename"] = os.path.basename(resume_path) if resume_path else None

    if resume_filter:
        wants_resume = resume_filter == "available"
        jobs = [job for job in jobs if job["resume_exists"] == wants_resume]

    return {
        "jobs": jobs,
        "total": total,
        "limit": limit,
        "offset": offset,
        "sources": sources,
    }

def check_resume_exists(job_title, company_name):
    """Check if a resume PDF exists for this job"""
    if not job_title or not company_name:
        return None

    def clean_filename(text):
        text = str(text).replace(" ", "_")
        return "".join(c for c in text if c.isalnum() or c == "_")

    job_clean = clean_filename(job_title)
    company_clean = clean_filename(company_name)
    
    patterns = [
        f"{job_clean}_{company_clean}.pdf",
        f"{job_clean.lower()}_{company_clean.lower()}.pdf",
    ]
    
    # Check today's folder first, then all folders
    today = datetime.now().strftime("%Y-%m-%d")
    today_folder = os.path.join(RESUME_BASE_PATH, today)
    
    if os.path.exists(today_folder):
        for pattern in patterns:
            pdf_path = os.path.join(today_folder, pattern)
            if os.path.exists(pdf_path):
                return os.path.join(today_folder, pattern)
    
    # Check all date folders
    if os.path.exists(RESUME_BASE_PATH):
        for date_folder in os.listdir(RESUME_BASE_PATH):
            folder_path = os.path.join(RESUME_BASE_PATH, date_folder)
            if os.path.isdir(folder_path):
                for pattern in patterns:
                    pdf_path = os.path.join(folder_path, pattern)
                    if os.path.exists(pdf_path):
                        return os.path.join(folder_path, pattern)
    
    return None

# =========================================================
# 🌐 WEB ROUTES
# =========================================================
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/admin')
def admin():
    stages = [
        {"key": key, "label": stage["label"]}
        for key, stage in PIPELINE_STAGES.items()
    ]
    stages.append({"key": "full_pipeline", "label": "Run Full Pipeline"})
    return render_template('admin.html', stages=stages)

@app.route('/api/jobs')
def api_jobs():
    jobs = get_all_jobs()
    
    # Add resume status to each job
    for job in jobs:
        resume_path = check_resume_exists(job['job_title'], job['company_name'])
        job['resume_exists'] = resume_path is not None
        job['resume_path'] = resume_path
        job['resume_filename'] = os.path.basename(resume_path) if resume_path else None
    
    return jsonify(jobs)

@app.route('/api/job/<job_id>')
def api_job_detail(job_id):
    job = get_job_by_id(job_id)
    
    if not job:
        return jsonify({'error': 'Job not found'}), 404
    
    # Add resume status
    resume_path = check_resume_exists(job['job_title'], job['company_name'])
    job['resume_exists'] = resume_path is not None
    job['resume_path'] = resume_path
    job['resume_filename'] = os.path.basename(resume_path) if resume_path else None
    
    return jsonify(job)

@app.route('/api/stats')
def api_stats():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Total jobs
    cursor.execute("SELECT COUNT(*) as count FROM job_postings")
    total_jobs = cursor.fetchone()['count']
    
    # Jobs with scores
    cursor.execute("SELECT COUNT(*) as count FROM job_postings WHERE score IS NOT NULL")
    scored_jobs = cursor.fetchone()['count']
    
    # Average score
    cursor.execute("SELECT AVG(score) as avg_score FROM job_postings WHERE score IS NOT NULL")
    avg_score = cursor.fetchone()['avg_score'] or 0
    
    # Score distribution
    cursor.execute("""
        SELECT 
            CASE 
                WHEN score >= 90 THEN '90-100'
                WHEN score >= 80 THEN '80-89'
                WHEN score >= 70 THEN '70-79'
                WHEN score >= 60 THEN '60-69'
                ELSE '0-59'
            END as score_range,
            COUNT(*) as count
        FROM job_postings 
        WHERE score IS NOT NULL
        GROUP BY score_range
        ORDER BY score_range DESC
    """)
    score_dist = cursor.fetchall()
    
    # Source distribution
    cursor.execute("""
        SELECT source, COUNT(*) as count
        FROM job_postings
        GROUP BY source
        ORDER BY count DESC
    """)
    source_dist = cursor.fetchall()
    
    # Jobs with resumes
    jobs = get_all_jobs()
    resume_count = sum(1 for job in jobs if check_resume_exists(job['job_title'], job['company_name']))
    
    conn.close()
    
    return jsonify({
        'total_jobs': total_jobs,
        'scored_jobs': scored_jobs,
        'avg_score': round(avg_score, 1),
        'resume_count': resume_count,
        'score_distribution': [dict(row) for row in score_dist],
        'source_distribution': [dict(row) for row in source_dist]
    })

@app.route('/api/admin/pipeline/run', methods=['POST'])
def api_admin_pipeline_run():
    payload = request.get_json(silent=True) or {}
    stage_key = payload.get("stage")

    if stage_key not in PIPELINE_STAGES and stage_key != "full_pipeline":
        return jsonify({"error": "Unknown pipeline stage"}), 400

    try:
        start_value = payload.get("start_date") or datetime.now().strftime("%Y-%m-%d")
        end_value = payload.get("end_date") or start_value
        start_date = parse_date(start_value)
        end_date = parse_date(end_value)
    except ValueError:
        return jsonify({"error": "Dates must use YYYY-MM-DD format"}), 400

    if end_date < start_date:
        return jsonify({"error": "End date must be after start date"}), 400

    run_dates = list(date_range(start_date, end_date))
    if len(run_dates) > 31:
        return jsonify({"error": "Date range cannot exceed 31 days"}), 400

    label = "Run Full Pipeline" if stage_key == "full_pipeline" else PIPELINE_STAGES[stage_key]["label"]
    if len(run_dates) == 1:
        label = f"{label} · {run_dates[0]}"
    else:
        label = f"{label} · {run_dates[0]} to {run_dates[-1]}"

    run = register_run(stage_key, label)
    thread = threading.Thread(target=execute_pipeline_run, args=(run, stage_key, run_dates), daemon=True)
    thread.start()

    return jsonify(run_summary(run)), 202

@app.route('/api/admin/pipeline/runs')
def api_admin_pipeline_runs():
    with RUN_LOCK:
        runs = [run_summary(RUNS[run_id]) for run_id in RUN_ORDER if run_id in RUNS]
    return jsonify({"runs": runs})

@app.route('/api/admin/pipeline/runs/<run_id>')
def api_admin_pipeline_run_detail(run_id):
    with RUN_LOCK:
        run = RUNS.get(run_id)
        if not run:
            return jsonify({"error": "Run not found"}), 404
        summary = run_summary(run)
        summary["logs"] = list(run["logs"])
    return jsonify(summary)

@app.route('/api/admin/jobs')
def api_admin_jobs():
    try:
        return jsonify(query_admin_jobs(request.args))
    except ValueError:
        return jsonify({"error": "Invalid numeric filter"}), 400

@app.route('/download/resume/<path:filename>')
def download_resume(filename):
    try:
        safe_filename = os.path.basename(filename)
        if safe_filename != filename or not safe_filename.lower().endswith(".pdf"):
            return jsonify({'error': 'Invalid resume filename'}), 400

        # Find the resume file
        today = datetime.now().strftime("%Y-%m-%d")
        today_folder = os.path.join(RESUME_BASE_PATH, today)
        
        # Check today's folder first
        if os.path.exists(today_folder):
            file_path = os.path.join(today_folder, safe_filename)
            if os.path.exists(file_path):
                return send_file(file_path, as_attachment=True)
        
        # Check all date folders
        if os.path.exists(RESUME_BASE_PATH):
            for date_folder in os.listdir(RESUME_BASE_PATH):
                folder_path = os.path.join(RESUME_BASE_PATH, date_folder)
                if os.path.isdir(folder_path):
                    file_path = os.path.join(folder_path, safe_filename)
                    if os.path.exists(file_path):
                        return send_file(file_path, as_attachment=True)
        
        return jsonify({'error': 'Resume file not found'}), 404
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/job/<job_id>')
def job_detail(job_id):
    return render_template('job_detail.html', job_id=job_id)

# =========================================================
# 🚀 START SERVER
# =========================================================
if __name__ == '__main__':
    print("🚀 Starting Job Application Tracking Dashboard...")
    print(f"📊 Database: {DB_PATH}")
    print(f"📄 Resume Path: {RESUME_BASE_PATH}")
    print("🌐 Dashboard will be available at: http://localhost:5000")
    
    app.run(debug=True, host='0.0.0.0', port=5000, use_reloader=False)
