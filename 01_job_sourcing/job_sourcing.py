import requests
from bs4 import BeautifulSoup
from typing import Optional
from pydantic import BaseModel, Field
import json
import time
import os

from langchain_huggingface import ChatHuggingFace, HuggingFaceEndpoint
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser

from datetime import date


# =========================================================
# 🔧 CONFIG
# =========================================================
today = date.today().strftime("%Y-%m-%d")
INPUT_JSON_PATH = f"{today}.json"
OUTPUT_JSON_PATH = f"/home/dinesh/HERMES/08_job_application_pipeline/02_job_filtering/MID_LAYER_DATA/{today}_mid.json"
HF_TOKEN = os.getenv("HUGGINGFACEHUB_API_TOKEN")

if not HF_TOKEN:
    raise RuntimeError("HUGGINGFACEHUB_API_TOKEN environment variable is required")


# =========================================================
# 🌐 SCRAPER WITH RETRY
# =========================================================
def fetch_job_page_text(url: str, retries: int = 2) -> str:
    headers = {"User-Agent": "Mozilla/5.0"}

    for attempt in range(retries + 1):
        try:
            print(f"[SCRAPER] Attempt {attempt+1} for {url}")

            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")

            for tag in soup(["script", "style", "noscript"]):
                tag.decompose()

            text = soup.get_text(separator=" ")
            return " ".join(text.split())

        except Exception as e:
            print(f"[SCRAPER ERROR] {e}")

            if attempt == retries:
                print(f"[SCRAPER FAILED] {url}")
                raise

            time.sleep(1)


# =========================================================
# 🧠 SCHEMA
# =========================================================
class JobData(BaseModel):
    external_job_id: Optional[str] = Field(
        description="Job ID of the job posting if present else null"
    )
    job_description: str = Field(
        description="Full job description"
    )


parser = JsonOutputParser(pydantic_object=JobData)


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
        "You are a strict JSON generator.\n\n"
        "You are going to get the web scrapped [page that contains a job posting].\n\n"
        "Your task is to extract the job description from the text you get. \n\n "
        "Also if the job has a job id  then extract that also "
        "Your task is to extract structured data from the given job text.\n\n"

        "RULES:\n"
        "- Output ONLY valid JSON\n"
        "- Do NOT write explanations\n"
        "- Do NOT write code\n"
        "- Do NOT add text before or after JSON\n"
        "- If a field is missing, use null\n\n"

        "{format_instructions}\n\n"

        "TEXT:\n{text}\n\n"

        "OUTPUT:"
    ),
    input_variables=["text"],
    partial_variables={
        "format_instructions": parser.get_format_instructions()
    }
)

chain = template | chat_model | parser


# =========================================================
# 🔁 PROCESS SINGLE JOB (WITH LOGGING)
# =========================================================
def process_single_job(url):
    print(f"[PROCESS] URL: {url}")

    page_text = fetch_job_page_text(url)

    print("[LLM] Sending data to model...")

    result = chain.invoke({
        "text": page_text[:8000]
    })

    print("[LLM] Extraction successful")

    # FIX HERE
    return result.get("external_job_id"), result.get("job_description")


# =========================================================
# 🚀 MAIN PIPELINE
# =========================================================
def main():

    if not os.path.exists(INPUT_JSON_PATH):
        raise FileNotFoundError("Input JSON not found")

    # safer directory handling
    output_dir = os.path.dirname(OUTPUT_JSON_PATH)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    print("[INFO] Loading JSON...")
    with open(INPUT_JSON_PATH, "r", encoding='utf-8') as f:
        data = json.load(f)

    jobs = data.get("jobs", [])

    print(f"[INFO] Total jobs: {len(jobs)}")

    success_count = 0
    fail_count = 0

    for i, job in enumerate(jobs):

        url = job.get("apply_url", "")

        if not url:
            print(f"[{i}] SKIP: No apply_url")
            continue

        print(f"[{i}] Processing job...")

        try:
            external_id, description = process_single_job(url)

            job["external_job_id"] = external_id
            job["job_description"] = description

            success_count += 1

        except Exception as e:
            print(f"[ERROR] Failed processing job {i}")
            print(e)

            job["external_job_id"] = None
            job["job_description"] = None

            fail_count += 1

        time.sleep(1)

    print("[INFO] Saving output JSON...")

    with open(OUTPUT_JSON_PATH, "w", encoding='utf-8') as f:
        json.dump(data, f, indent=2)

    print(f"[DONE] Saved to {OUTPUT_JSON_PATH}")
    print(f"[SUMMARY] Success: {success_count}, Failed: {fail_count}")


# =========================================================
# ENTRY
# =========================================================
if __name__ == "__main__":
    main()
