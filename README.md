# AI Job Application Pipeline

This project is an end-to-end job application assistant. It takes collected job leads, enriches them with full job descriptions, scores each role against your resume, stores the results in SQLite, generates tailored resume content for strong matches, compiles those resumes into PDFs, and exposes everything through a Flask dashboard.

The goal is to reduce the repetitive parts of job hunting while keeping the final decisions visible: you can see every job, its source, its AI-generated match score, whether a tailored resume exists, and the original apply link.

## What The Project Does

At a high level, the project turns raw job leads into application-ready resume PDFs.

1. It starts from structured daily job JSON files, usually sourced from places like Telegram job posts or Gmail job alerts.
2. It visits each job's `apply_url`, scrapes the posting page, and asks an LLM to extract a cleaner job description and external job ID when available.
3. It compares each enriched job against your resume and assigns a score from 1 to 100.
4. It writes the scored jobs into `jobs_new.db`, which becomes the central database for the dashboard and downstream resume generation.
5. It selects jobs above a configurable score threshold and uses an LLM to tailor your resume JSON to each job description.
6. It renders those tailored JSON files into LaTeX and compiles them into PDF resumes.
7. It provides a web dashboard where you can browse, search, filter, inspect, download resumes, open apply links, and run pipeline stages from an admin page.

## Repository Structure

```text
.
|-- 01_job_sourcing/
|   |-- job_sourcing.py
|   `-- YYYY-MM-DD.json
|-- 02_job_filtering/
|   |-- job_scorer.py
|   |-- MID_LAYER_DATA/
|   `-- SCORED/
|-- 02_resume_engine/
|   |-- base_resume.json
|   |-- data_schema.json
|   |-- generate_json.py
|   |-- generate_resume.py
|   |-- standard_template.tex
|   |-- LLM_GENERATED_JSONS/
|   `-- LLM_COMPILED_PDFS/
|-- 03_web_browser/
|   |-- app.py
|   |-- templates/
|   `-- static/
|-- resume/
|   |-- resume.txt
|   |-- standard_template.tex
|   `-- REAL RESUME/
|-- jobs_new.db
|-- requirements.txt
|-- CI_CD.md
`-- README.md
```

## Main Components

### 1. Job Sourcing And Description Enrichment

File: `01_job_sourcing/job_sourcing.py`

This stage expects an input file named like:

```text
01_job_sourcing/2026-05-07.json
```

The input JSON contains job leads with fields such as:

- `job_unique_id`
- `job_title`
- `company_name`
- `experience_required`
- `location`
- `published_date`
- `apply_url`
- `source`
- `raw_source_text`
- `fetched_at`
- `experience_level`

For each job, the script:

- reads the `apply_url`
- fetches the page HTML with `requests`
- removes scripts/styles using BeautifulSoup
- extracts readable page text
- sends the text to a Hugging Face hosted LLM
- asks the model to return strict JSON containing:
  - `external_job_id`
  - `job_description`
- saves the enriched output to:

```text
02_job_filtering/MID_LAYER_DATA/YYYY-MM-DD_mid.json
```

Run it with:

```bash
python 01_job_sourcing/job_sourcing.py --date 2026-05-07
```

If `--date` is omitted, the script uses today's date.

### 2. Job Filtering And Scoring

File: `02_job_filtering/job_scorer.py`

This stage reads the enriched job data from:

```text
02_job_filtering/MID_LAYER_DATA/YYYY-MM-DD_mid.json
```

It also reads your plain-text resume from:

```text
resume/resume.txt
```

For each job, it sends the resume, job title, company, experience requirement, and job description to an LLM. The model returns a score from 1 to 100 representing how strong the match is for your profile.

The script then:

- adds `score` to each job object
- ensures each job has an `external_job_id` fallback
- writes scored data to:

```text
02_job_filtering/SCORED/YYYY-MM-DD_scored.json
```

- inserts or replaces rows in the SQLite database:

```text
jobs_new.db
```

Run it with:

```bash
python 02_job_filtering/job_scorer.py --date 2026-05-07
```

### 3. Tailored Resume JSON Generation

File: `02_resume_engine/generate_json.py`

This stage queries `jobs_new.db` for jobs fetched on a given date whose score is above a threshold.

By default, it uses:

```text
min_score = 65
```

It reads your base structured resume from:

```text
02_resume_engine/base_resume.json
```

For each selected job, the LLM is instructed to tailor the resume while preserving factual details. The prompt allows edits to sections like:

- experience bullet points
- project bullet points
- skills
- job-relevant keywords

It should not change factual identity data such as your name, education, companies, or project titles.

Generated resume JSON files are saved under:

```text
02_resume_engine/LLM_GENERATED_JSONS/YYYY-MM-DD/
```

Run it with:

```bash
python 02_resume_engine/generate_json.py --date 2026-05-07 --min-score 65
```

### 4. Resume PDF Compilation

File: `02_resume_engine/generate_resume.py`

This stage converts tailored resume JSON files into PDFs.

It reads JSON files from:

```text
02_resume_engine/LLM_GENERATED_JSONS/YYYY-MM-DD/
```

It renders them through:

```text
02_resume_engine/standard_template.tex
```

Then it compiles the rendered LaTeX using `pdflatex` by default. The compiler can be changed with the `LATEX_COMPILER` environment variable.

Generated PDFs are saved under:

```text
02_resume_engine/LLM_COMPILED_PDFS/YYYY-MM-DD/
```

Run it with:

```bash
python 02_resume_engine/generate_resume.py --date 2026-05-07
```

### 5. Web Dashboard And Admin Runner

File: `03_web_browser/app.py`

The Flask app provides two main browser views:

- `/` - job tracking dashboard
- `/admin` - admin page for running pipeline stages

The dashboard reads from `jobs_new.db` and checks the compiled resume PDF folders to see whether a tailored resume exists for each job.

Core features include:

- job cards sorted by score
- match score statistics
- source distribution
- score distribution
- search by title, company, location, or description
- filters by source, score, and resume availability
- job detail pages
- direct resume PDF downloads
- direct apply links
- admin pipeline execution with run logs

Run the dashboard with:

```bash
python 03_web_browser/app.py
```

Then open:

```text
http://localhost:5000
```

Admin page:

```text
http://localhost:5000/admin
```

## Complete Workflow

For a date such as `2026-05-07`, the full manual workflow is:

```bash
python 01_job_sourcing/job_sourcing.py --date 2026-05-07
python 02_job_filtering/job_scorer.py --date 2026-05-07
python 02_resume_engine/generate_json.py --date 2026-05-07 --min-score 65
python 02_resume_engine/generate_resume.py --date 2026-05-07
python 03_web_browser/app.py
```

The same stages can also be triggered from the `/admin` dashboard. The admin runner supports:

- running a single stage
- running the full pipeline
- selecting a start date and end date
- viewing recent pipeline logs
- seeing success or failure status for each run

## Data Flow

```text
Raw daily job JSON
    |
    v
01_job_sourcing/job_sourcing.py
    |
    v
02_job_filtering/MID_LAYER_DATA/YYYY-MM-DD_mid.json
    |
    v
02_job_filtering/job_scorer.py
    |
    +--> 02_job_filtering/SCORED/YYYY-MM-DD_scored.json
    |
    +--> jobs_new.db
            |
            v
      02_resume_engine/generate_json.py
            |
            v
      02_resume_engine/LLM_GENERATED_JSONS/YYYY-MM-DD/*.json
            |
            v
      02_resume_engine/generate_resume.py
            |
            v
      02_resume_engine/LLM_COMPILED_PDFS/YYYY-MM-DD/*.pdf
            |
            v
      03_web_browser/app.py dashboard
```

## Database

The main database is:

```text
jobs_new.db
```

The project uses a `job_postings` table with these columns:

```text
job_unique_id
job_title
company_name
experience_required
location
published_date
apply_url
source
raw_source_text
fetched_at
experience_level
external_job_id
job_description
score
```

`job_unique_id` is indexed uniquely when it is not null, so repeated pipeline runs can update existing jobs instead of creating duplicate rows.

## Environment Variables

Create a `.env` file at the project root or export these variables before running the scripts.

Required for LLM-powered stages:

```bash
HUGGINGFACEHUB_API_TOKEN=your_huggingface_token
```

Optional:

```bash
JOBS_DB_PATH=/absolute/path/to/jobs_new.db
RESUME_BASE_PATH=/absolute/path/to/02_resume_engine/LLM_COMPILED_PDFS
LATEX_COMPILER=pdflatex
```

Notes:

- `HUGGINGFACEHUB_API_TOKEN` is required by `job_sourcing.py`, `job_scorer.py`, and `generate_json.py`.
- `generate_resume.py` does not call the LLM, but it requires a working LaTeX compiler.
- The Flask app loads `.env` from the repository root when it starts.

## Installation

Create and activate a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
```

Install Python dependencies:

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

Install a LaTeX distribution if you want PDF compilation to work. On Ubuntu/Debian, a typical setup is:

```bash
sudo apt-get update
sudo apt-get install texlive-latex-base texlive-latex-extra texlive-fonts-recommended
```

## Important Inputs And Outputs

### Inputs

- `01_job_sourcing/YYYY-MM-DD.json` - daily raw job leads
- `resume/resume.txt` - plain-text resume used for scoring
- `02_resume_engine/base_resume.json` - structured base resume used for tailoring
- `02_resume_engine/standard_template.tex` - LaTeX template for generated PDFs

### Intermediate Outputs

- `02_job_filtering/MID_LAYER_DATA/YYYY-MM-DD_mid.json` - enriched jobs with descriptions
- `02_job_filtering/SCORED/YYYY-MM-DD_scored.json` - scored jobs
- `jobs_new.db` - SQLite database used by the dashboard and resume generator
- `02_resume_engine/LLM_GENERATED_JSONS/YYYY-MM-DD/*.json` - tailored resume data

### Final Outputs

- `02_resume_engine/LLM_COMPILED_PDFS/YYYY-MM-DD/*.pdf` - final tailored resume PDFs
- Flask dashboard at `http://localhost:5000`

## API Endpoints

The Flask app exposes these useful routes:

```text
GET  /api/jobs
GET  /api/job/<job_id>
GET  /api/stats
GET  /api/admin/jobs
POST /api/admin/pipeline/run
GET  /api/admin/pipeline/runs
GET  /api/admin/pipeline/runs/<run_id>
GET  /download/resume/<filename>
```

## CI/CD

The repository includes a GitHub Actions workflow in:

```text
.github/workflows/ci-cd.yml
```

The CI job:

- installs dependencies from `requirements.txt`
- compiles Python files to catch syntax errors
- checks imports for key dependencies
- imports the Flask app and verifies important routes
- validates resume template input files

Deployment jobs call:

```bash
./scripts/deploy.sh dev
./scripts/deploy.sh prod
```

Those deploy scripts are currently safe hooks/placeholders where real server or cloud deployment commands can be added.

More details are in `CI_CD.md`.

## Troubleshooting

### Missing Hugging Face Token

If a script fails with:

```text
HUGGINGFACEHUB_API_TOKEN environment variable is required
```

add the token to `.env` or export it in your shell:

```bash
export HUGGINGFACEHUB_API_TOKEN=your_huggingface_token
```

### No Input JSON Found

If `job_sourcing.py` says the input JSON is missing, confirm that the date-specific file exists:

```text
01_job_sourcing/YYYY-MM-DD.json
```

The pipeline is date-driven, so `--date` must match the file names and the job `fetched_at` date used downstream.

### No Jobs Selected For Resume Generation

`generate_json.py` only selects jobs where:

```text
score > min_score
DATE(fetched_at) = selected date
```

Try lowering the threshold:

```bash
python 02_resume_engine/generate_json.py --date 2026-05-07 --min-score 50
```

### PDFs Are Not Generated

Make sure:

- the JSON folder exists under `02_resume_engine/LLM_GENERATED_JSONS/YYYY-MM-DD/`
- `pdflatex` or your configured compiler is installed
- `02_resume_engine/standard_template.tex` exists
- the JSON follows the expected resume schema

### Dashboard Shows Jobs But No Resumes

The dashboard looks for PDFs under:

```text
02_resume_engine/LLM_COMPILED_PDFS/
```

It matches filenames using cleaned job title and company names, so if a resume was renamed manually, the dashboard may not detect it.

## Current Design Notes

- The pipeline is intentionally file-and-date based. Each stage can be rerun for a specific date.
- SQLite is used as the central state store after scoring.
- LLM responses are parsed as JSON with Pydantic-backed output parsers.
- Resume generation is split into two steps: generate structured JSON first, then compile PDFs. This makes debugging easier because you can inspect the generated resume content before compiling.
- The dashboard is not just a viewer; the `/admin` route can run pipeline stages and stream recent logs.
