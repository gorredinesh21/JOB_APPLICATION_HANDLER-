import json
import os
import sqlite3

from langchain_huggingface import ChatHuggingFace, HuggingFaceEndpoint
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field
from datetime import date

# =========================================================
# 🔧 CONFIG
# =========================================================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
today = date.today().strftime("%Y-%m-%d")
INPUT_JSON_PATH = os.path.join(BASE_DIR, "02_job_filtering", f"{today}_mid.json")
OUTPUT_JSON_PATH = os.path.join(BASE_DIR, "02_job_filtering/SCORED", f"{today}_scored.json")
DB_PATH = os.path.join(BASE_DIR, "jobs_new.db")
RESUME_PATH = os.path.join(BASE_DIR, "resume", "resume.txt")

HF_TOKEN = os.getenv("HUGGINGFACEHUB_API_TOKEN")

if not HF_TOKEN:
    raise RuntimeError("HUGGINGFACEHUB_API_TOKEN environment variable is required")


# =========================================================
# 🧠 SCHEMA
# =========================================================
class JobScore(BaseModel):
    score: int = Field(description="Score from 1 to 100")


parser = JsonOutputParser(pydantic_object=JobScore)


# =========================================================
# 🤖 LLM
# =========================================================
llm = HuggingFaceEndpoint(
    repo_id="meta-llama/Llama-3.1-8B-Instruct",
    task="text-generation",
    huggingfacehub_api_token=HF_TOKEN
)

chat_model = ChatHuggingFace(llm=llm)


template = PromptTemplate(
    template=(
        "You are an expert career evaluator.\n\n"
        "You have to give a score from 1-100 , the scorewill basically tell my chances of me getting that job or me being shortlisted to the next round .\n\n"
        "You will be given my resume , the job description , and other details related to a job application \n\n"
        "RESUME:\n{resume}\n\n"
        "JOB DETAILS:\n"
        "- Title: {job_title}\n"
        "- Company: {company_name}\n"
        "- Experience: {experience_required}\n"
        "- Description: {job_description}\n\n"
        "Return ONLY JSON.\n\n"
        "{format_instructions}"
    ),
    input_variables=[
        "resume",
        "job_title",
        "company_name",
        "experience_required",
        "job_description"
    ],
    partial_variables={"format_instructions": parser.get_format_instructions()}
)

chain = template | chat_model | parser


# =========================================================
# 📄 LOAD RESUME
# =========================================================
def load_resume():
    with open(RESUME_PATH, "r", encoding="utf-8") as f:
        return f.read()


# =========================================================
# 🧠 SAFE EXTERNAL JOB ID
# =========================================================
def get_external_job_id(job):
    ext_id = job.get("external_job_id")

    if ext_id and str(ext_id).strip():
        return ext_id

    return (
        job.get("job_title")
        or job.get("title")
        or "unknown_job"
    )


# =========================================================
# 🧠 SCORE ONE JOB
# =========================================================
def score_job(chain, resume_text, job):

    result = chain.invoke({
        "resume": resume_text,
        "job_title": job.get("job_title") or job.get("title") or "N/A",
        "company_name": job.get("company_name") or "N/A",
        "experience_required": job.get("experience_required") or "N/A",
        "job_description": job.get("job_description") or "N/A"
    })

    if isinstance(result, dict):
        score = result.get("score", 50)
    else:
        score = 50

    return max(1, min(100, score))


# =========================================================
# 💾 INSERT INTO DB (FINAL FIXED VERSION)
# =========================================================
def insert_into_db(data):

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    for job in data.get("jobs", []):

        ext_id = get_external_job_id(job)

        cursor.execute("""
            INSERT INTO job_postings (
                job_unique_id,
                job_title,
                company_name,
                experience_required,
                location,
                published_date,
                apply_url,
                source,
                raw_source_text,
                fetched_at,
                experience_level,
                external_job_id,
                job_description,
                score
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            job.get("job_unique_id"),
            job.get("job_title"),
            job.get("company_name"),
            job.get("experience_required"),
            job.get("location"),
            job.get("published_date"),
            job.get("apply_url") or "",   # 🔥 prevents NOT NULL crash
            job.get("source"),
            job.get("raw_source_text"),
            job.get("fetched_at"),
            job.get("experience_level"),
            ext_id,
            job.get("job_description"),
            job.get("score")
        ))

    conn.commit()
    conn.close()

    print("[DB] Insert complete")


# =========================================================
# 🚀 MAIN
# =========================================================
def main():

    if not os.path.exists(INPUT_JSON_PATH):
        raise FileNotFoundError("Input JSON not found")

    print("[INFO] Loading JSON...")
    with open(INPUT_JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    resume_text = load_resume()

    print("[INFO] Creating LLM chain...")
    jobs = data.get("jobs", [])
    print(f"[INFO] Scoring {len(jobs)} jobs...")

    for i, job in enumerate(jobs):

        print(f"[{i}] {job.get('job_title') or job.get('title')}")

        try:
            score = score_job(chain, resume_text, job)
            job["score"] = score
            job["external_job_id"] = get_external_job_id(job)

        except Exception as e:
            print(f"[ERROR] Job {i}: {e}")
            job["score"] = None
            job["external_job_id"] = get_external_job_id(job)

    print("[INFO] Saving updated JSON...")

    with open(OUTPUT_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    print("[INFO] Inserting into DB...")
    insert_into_db(data)

    print("[DONE]")


# =========================================================
if __name__ == "__main__":
    main()
