import json
import sqlite3
from openai import OpenAI

from config import DB_PATH, AI_MODEL, PROMPT_VERSION

client = OpenAI()


def validate_ai_response(data):

    if not isinstance(data, dict):
        return "rejected", "Invalid AI response"

    decision = data.get("decision")
    reason = data.get("reason", "")

    if decision not in ["accepted", "rejected"]:
        return "rejected", "Invalid AI decision"

    return decision, reason


def screen_application_async(application_id, resume_text, job_description):

    prompt = f"""
Evaluate the resume against the job description.

JOB DESCRIPTION:
{job_description}

RESUME:
{resume_text}

Return JSON:

{{
 "decision": "accepted or rejected",
 "reason": "short explanation"
}}
"""

    try:

        response = client.chat.completions.create(
            model=AI_MODEL,
            messages=[
                {"role": "system", "content": "You are an expert recruiter."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            max_tokens=200
        )

        raw = response.choices[0].message.content
        result = json.loads(raw)

        decision, feedback = validate_ai_response(result)

    except Exception as e:

        decision = "rejected"
        feedback = f"AI error: {str(e)}"

    with sqlite3.connect(DB_PATH) as conn:

        conn.execute(
            """
            UPDATE applications
            SET filter_status=?, ai_feedback=?, prompt_version=?, ai_model=?
            WHERE id=?
            """,
            (decision, feedback, PROMPT_VERSION, AI_MODEL, application_id)
        )