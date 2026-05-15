import json
import sqlite3
import os
import re
import time
from datetime import datetime

from langchain_huggingface import ChatHuggingFace, HuggingFaceEndpoint
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field
from typing import List, Optional


# =========================================================
# 🔧 CONFIG
# =========================================================
DB_PATH = "/home/dinesh/HERMES/08_job_application_pipeline/jobs_new.db"
BASE_RESUME_JSON = "base_resume.json"
OUTPUT_DIR = "LLM_GENERATED_JSONS"

HF_TOKEN = os.getenv("HUGGINGFACEHUB_API_TOKEN")

if not HF_TOKEN:
    raise RuntimeError("HUGGINGFACEHUB_API_TOKEN environment variable is required")


# =========================================================
# 🧠 SCHEMA
# =========================================================
class Education(BaseModel):
    institute: str
    degree: str
    duration: str
    location: str
    details: List[str]


class Experience(BaseModel):
    role: str
    company: str
    duration: str
    location: str
    points: List[str]


class Project(BaseModel):
    title: str
    tech_stack: str
    repo: Optional[str] = None
    repo_link: Optional[str] = None
    points: List[str]


class Skills(BaseModel):
    languages: List[str]
    technologies: List[str]
    concepts: List[str]


class ResumeSchema(BaseModel):
    name: str
    phone: str
    email: str
    linkedin: str
    linkedin_display: str
    github: str
    github_display: str
    education: List[Education]
    experience: List[Experience]
    projects: List[Project]
    skills: Skills
    achievements: List[str]


parser = JsonOutputParser(pydantic_object=ResumeSchema)


# =========================================================
# 🤖 LLM
# =========================================================
llm = HuggingFaceEndpoint(
    repo_id="meta-llama/Meta-Llama-3-70B-Instruct",
    task="text-generation",
    huggingfacehub_api_token=HF_TOKEN
)

chat_model = ChatHuggingFace(llm=llm)


# =========================================================
# 🧠 LOAD RESUME
# =========================================================
def load_resume():
    with open(BASE_RESUME_JSON, "r", encoding="utf-8") as f:
        return json.load(f)


# =========================================================
# 🧠 FETCH JOBS (UPDATED)
# =========================================================
def fetch_jobs():

    today = datetime.now().strftime("%Y-%m-%d")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT job_title, company_name, job_description, raw_source_text, experience_required
        FROM job_postings
        WHERE score > 65
        AND DATE(fetched_at) = ?
    """, (today,))

    rows = cursor.fetchall()
    conn.close()

    jobs = []
    for row in rows:
        job_description = row[2] if row[2] else row[3]

        jobs.append({
            "job_title": row[0],
            "company_name": row[1],
            "job_description": job_description,
            "experience_required": row[4]
        })

    return jobs


# =========================================================
# 🧠 SAFE INVOKE
# =========================================================
def safe_invoke(chain, inputs, max_retries=3):

    for attempt in range(max_retries):
        try:
            print(f"[LLM] Attempt {attempt+1}")
            return chain.invoke(inputs)

        except Exception as e:
            print(f"[WARN] LLM failed (attempt {attempt+1}): {e}")

    print("[WARN] Switching to fallback parsing...")

    try:
        raw_prompt = template.format(**inputs)
        raw_output = chat_model.invoke(raw_prompt)

        content = raw_output.content if hasattr(raw_output, "content") else str(raw_output)

        stack = []
        start_idx = None

        for i, char in enumerate(content):
            if char == "{":
                if not stack:
                    start_idx = i
                stack.append("{")

            elif char == "}":
                if stack:
                    stack.pop()
                    if not stack:
                        json_str = content[start_idx:i+1]
                        try:
                            return json.loads(json_str)
                        except:
                            continue

        print("[FATAL] Could not extract valid JSON")
        return None

    except Exception as e:
        print("[FATAL] Recovery failed:", e)
        return None


# =========================================================
# 🧠 PROMPT
# =========================================================


template = PromptTemplate(
    template=(
        "You are an expert resume optimizer.\n\n"
        "You will get my resume and the job description of the job i wanna apply for \n\n"
        "you will also get some other details about the job \n\n"
        "Your job is to make changes in my resume according to the job description\n\n"
        "you can include key words , technical words etc... \n\n"
        "Below are some very important rules to follow "
        "IMPORTANT RULES:\n"
        "- Return ONLY ONE valid JSON object\n"
        "- DO NOT include explanations\n"
        "- DO NOT include schema\n"
        "- DO NOT include $defs\n"
        "- DO NOT include multiple JSON blocks\n\n"

        "- DO NOT change factual data:\n"
        "  name, education, companies, project titles\n\n"

        "- You MAY modify:\n"
        "  experience bullet points\n"
        "  project bullet points\n"
        "  skills section\n\n"
        "Relevant course work \n\n"

        "- Add job-relevant keywords\n"
        "- Keep structure EXACTLY same\n\n"

        "{format_instructions}\n\n"

        "BASE RESUME:\n{resume}\n\n"

        "JOB DETAILS:\n"
        "Title: {job_title}\n"
        "Company: {company_name}\n"
        "Description: {job_description}\n"
        "Experience Required: {experience_required}\n"
    ),
    input_variables=[
        "resume",
        "job_title",
        "company_name",
        "job_description",
        "experience_required"
    ],
    partial_variables={
        "format_instructions": parser.get_format_instructions()
    }
)

chain = template | chat_model | parser


# =========================================================
# 🧠 FILE NAME CLEANER
# =========================================================
def clean_filename(text):
    text = text.replace(" ", "_")
    text = re.sub(r'[^a-zA-Z0-9_]', '', text)
    return text


# =========================================================
# 🚀 MAIN (UPDATED)
# =========================================================
def main():

    today = datetime.now().strftime("%Y-%m-%d")

    # 🔥 create dated folder
    output_dir = os.path.join(OUTPUT_DIR, today)
    os.makedirs(output_dir, exist_ok=True)

    resume = load_resume()
    jobs = fetch_jobs()

    print(f"[INFO] Total jobs selected: {len(jobs)}")

    for i, job in enumerate(jobs):

        print(f"[{i}] Processing: {job['job_title']}")

        result = safe_invoke(chain, {
            "resume": json.dumps(resume),
            "job_title": job["job_title"],
            "company_name": job["company_name"],
            "job_description": job["job_description"][:4000],
            "experience_required": job["experience_required"]
        })

        if result is None:
            print(f"[SKIP] Failed job: {job['job_title']}")
            continue

        job_part = clean_filename(job["job_title"])
        company_part = clean_filename(job["company_name"])

        filename = f"{job_part}_{company_part}.json"
        filepath = os.path.join(output_dir, filename)

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)

        print(f"[✓] Saved: {filepath}")

        time.sleep(1)


# =========================================================
if __name__ == "__main__":
    main()
