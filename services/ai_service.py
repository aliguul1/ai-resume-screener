import json
import sqlite3
from openai import OpenAI
import config


def screen_application_async(application_id, resume_text, job_text):
    """
    AI Integration: Compares extracted Resume text vs extracted Job text.
    Uses OpenAI GPT-4o with structured JSON output.
    """
    client = OpenAI()

    prompt = f"""
    ### SYSTEM INSTRUCTIONS
    You are a professional recruiter. Compare the candidate's RESUME against the JOB OPENING.
    Evaluate if the candidate's skills and experience match the requirements.

    ### JOB OPENING (Extracted from PDF)
    {job_text}

    ### CANDIDATE RESUME (Extracted from PDF)
    {resume_text}

    ### RESPONSE FORMAT
    Return ONLY a valid JSON object:
    {{
      "decision": "accepted" | "rejected",
      "reason": "A one-sentence explanation of the decision."
    }}
    """

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )

        result = json.loads(response.choices[0].message.content)
        decision = result.get("decision", "rejected").lower()
        reason = result.get("reason", "No feedback provided.")
    except Exception as e:
        decision = "rejected"
        reason = f"AI processing failed: {str(e)}"

    with sqlite3.connect(config.DB_PATH) as conn:
        conn.execute(
            "UPDATE applications SET filter_status = ?, ai_feedback = ? WHERE id = ?",
            (decision, reason, application_id)
        )