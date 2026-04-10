""""
Service for AI-based screening logic.
"""
import json
import sqlite3
import logging
from openai import OpenAI
from config import DB_PATH, AI_MODEL, PROMPT_VERSION

client = OpenAI()

def screen_application_async(application_id, resume_text, job_description):
    """Evaluates a resume asynchronously and updates the DB."""
    prompt = f"Job: {job_description}\nResume: {resume_text}"

    try:
        response = client.chat.completions.create(
            model=AI_MODEL,
            messages=[{"role": "system", "content": "Return JSON with 'decision' and 'reason'."}],
            response_format={"type": "json_object"}
        )
        result = json.loads(response.choices[0].message.content)
        decision = result.get("decision", "rejected")
        feedback = result.get("reason", "No feedback.")
    except Exception as e:
        decision = "rejected"
        feedback = f"AI Error: {str(e)}"

    with sqlite3.connect(DB_PATH, timeout=10) as conn:
        conn.execute(
            "UPDATE applications SET filter_status=?, ai_feedback=?, ai_model=? WHERE id=?",
            (decision, feedback, AI_MODEL, application_id)
        )