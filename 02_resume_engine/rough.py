import json
import sqlite3
import os
import re
import time

from langchain_huggingface import ChatHuggingFace, HuggingFaceEndpoint
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field
from typing import List, Optional


# =========================================================
# 🔧 CONFIG
# =========================================================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.getenv("JOBS_DB_PATH", os.path.join(BASE_DIR, "jobs_new.db"))
BASE_RESUME_JSON = os.path.join(SCRIPT_DIR, "base_resume.json")
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "LLM_GENERATED_JSONS")

HF_TOKEN = os.getenv("HUGGINGFACEHUB_API_TOKEN")

if not HF_TOKEN:
    raise RuntimeError("HUGGINGFACEHUB_API_TOKEN environment variable is required")


# =========================================================
# 🧠 SCHEMA
# =========================================================
class Education(BaseModel):
    institute: str = Field(description="Name of the institute")
    degree: str = Field(description="Degree obtained")
    duration: str = Field(description="Duration of study")
    location: str = Field(description="Location of institute")
    details: List[str] = Field(description="Coursework or details")


class Experience(BaseModel):
    role: str = Field(description="Job role/title")
    company: str = Field(description="Company name")
    duration: str = Field(description="Duration of employment")
    location: str = Field(description="Job location")
    points: List[str] = Field(description="Bullet points describing work")


class Project(BaseModel):
    title: str = Field(description="Project title")
    tech_stack: str = Field(description="Technologies used")
    repo: Optional[str] = None
    repo_link: Optional[str] = None
    points: List[str] = Field(description="Project description bullet points")


class Skills(BaseModel):
    languages: List[str] = Field(description="Programming languages")
    technologies: List[str] = Field(description="Technologies and tools")
    concepts: List[str] = Field(description="Conceptual knowledge areas")


class ResumeSchema(BaseModel):
    name: str = Field(description="Full name")
    phone: str = Field(description="Phone number")
    email: str = Field(description="Email address")

    linkedin: str = Field(description="LinkedIn URL")
    linkedin_display: str = Field(description="Short LinkedIn display text")

    github: str = Field(description="GitHub URL")
    github_display: str = Field(description="Short GitHub display text")

    education: List[Education] = Field(description="Education details")
    experience: List[Experience] = Field(description="Work experience")
    projects: List[Project] = Field(description="Projects list")
    skills: Skills = Field(description="Skills section")
    achievements: List[str] = Field(description="Achievements list")


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
# 🧠 FETCH JOBS
# =========================================================
def fetch_jobs():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT job_title, company_name, job_description, raw_source_text, experience_required
        FROM job_postings
        WHERE score > 65
    """)

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
# 🧠 SAFE INVOKE (ROBUST)
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

        # 🔥 robust JSON extraction
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
        "You will get my resume and the job description.\n\n"
        "Your job is to tailor my resume.\n\n"

        "IMPORTANT RULES:\n"
        "- Return ONLY ONE valid JSON object\n"
        "- DO NOT include explanations\n"
        "- DO NOT include schema\n\n"

        "- DO NOT change factual data:\n"
        "  name, education, companies, project titles\n\n"

        "- You MAY modify:\n"
        "  experience bullet points\n"
        "  project bullet points\n"
        "  skills section\n\n"

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
# 🚀 MAIN
# =========================================================
def main():

    os.makedirs(OUTPUT_DIR, exist_ok=True)

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
        filepath = os.path.join(OUTPUT_DIR, filename)

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)

        print(f"[✓] Saved: {filepath}")

        # avoid API throttling
        time.sleep(1)


# =========================================================
if __name__ == "__main__":
    main()


