from flask import Flask, render_template, jsonify, send_file, request
import sqlite3
import os
from datetime import datetime
import json

# Configure static folder
app = Flask(__name__, static_folder='static', static_url_path='/static')

# =========================================================
# 🗄️ DATABASE CONFIG
# =========================================================
DB_PATH = "/home/dinesh/HERMES/08_job_application_pipeline/jobs_new.db"
RESUME_BASE_PATH = "/home/dinesh/HERMES/08_job_application_pipeline/02_resume_engine/LLM_COMPILED_PDFS"

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

def check_resume_exists(job_title, company_name):
    """Check if a resume PDF exists for this job"""
    # Generate filename pattern
    job_clean = "".join(c for c in job_title if c.isalnum() or c in (' ', '-', '_')).rstrip()
    company_clean = "".join(c for c in company_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
    
    # Try different filename patterns
    patterns = [
        f"{job_clean}_{company_clean}.pdf",
        f"{job_clean.replace(' ', '_')}_{company_clean.replace(' ', '_')}.pdf",
        f"{job_clean.lower()}_{company_clean.lower()}.pdf"
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

@app.route('/download/resume/<path:filename>')
def download_resume(filename):
    try:
        # Find the resume file
        today = datetime.now().strftime("%Y-%m-%d")
        today_folder = os.path.join(RESUME_BASE_PATH, today)
        
        # Check today's folder first
        if os.path.exists(today_folder):
            file_path = os.path.join(today_folder, filename)
            if os.path.exists(file_path):
                return send_file(file_path, as_attachment=True)
        
        # Check all date folders
        if os.path.exists(RESUME_BASE_PATH):
            for date_folder in os.listdir(RESUME_BASE_PATH):
                folder_path = os.path.join(RESUME_BASE_PATH, date_folder)
                if os.path.isdir(folder_path):
                    file_path = os.path.join(folder_path, filename)
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
    
    app.run(debug=True, host='0.0.0.0', port=5000)
