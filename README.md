# AI Resume Screener (PoC)

A Proof-of-Concept backend system that automatically screens candidate resumes using AI.

The system allows:
* **Hiring managers** to create job openings
* **Candidates** to submit applications with PDF resumes
* **AI** to evaluate resumes against job descriptions

## Tech Stack

* **Python**
* **Flask**
* **SQLite**
* **OpenAI API**
* **pdfplumber**

## System Architecture

```mermaid
flowchart LR
    Candidate -->|POST /applications| API[Flask API]
    Manager -->|CRUD Jobs| API
    API --> DB[(SQLite)]
    API --> Storage[(Uploads)]
    API --> PDF[pdfplumber]
    API ==>|Async| Worker[Screening Worker]
    Worker --> AI[OpenAI]
    AI --> Worker
    Worker --> DB
```

## Workflow

1.  **Candidate** uploads a PDF resume
2.  **Flask API** stores the file and extracts text via **pdfplumber**
3.  **Application** is saved to **SQLite** with status **pending**
4.  **Background worker** sends extracted text to **AI**
5.  **AI** returns **accepted** or **rejected**
6.  **Database** is updated with the final result

## Installation

**git clone &lt;repo&gt;** **cd ai-resume-screener**

**Create environment:** `python3 -m venv venv`  
`source venv/bin/activate`

**Install dependencies:** `pip install -r requirements.txt`

**Set API key:** `export OPENAI_API_KEY=your_key`

**Run server:** `python3 app.py`  
*(Note: The database and tables are generated automatically on the first run)*

**Server runs on:** `http://127.0.0.1:5000`

## API Examples

### Create Job
**POST /jobs**

```json
{
  "title": "Python Developer",
  "description": "Backend development",
  "requirements": "Flask, SQL"
}
```

### Submit Application
**POST /applications**

**Form-data:**
* `job_id`
* `applicant_name`
* `applicant_email`
* `resume` (PDF file)

## Project Status

PoC implementation of an AI-assisted resume screening backend.