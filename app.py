"""
Main Flask API for the AI Resume Screener PoC.
This file automatically initializes the database on startup.
"""
import sqlite3
import threading
import uuid
from flask import Flask, request, jsonify, g
from werkzeug.utils import secure_filename

import config
from services.pdf_service import extract_text_from_pdf
from services.ai_service import screen_application_async

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = config.MAX_UPLOAD_SIZE

# Ensure the upload directory exists
config.UPLOAD_DIR.mkdir(exist_ok=True)


def init_db():
    """
    Checks if the database exists. If not, creates it using schema.sql.
    This ensures the 'screener.db' is ready before the first request.
    """
    if not config.DB_PATH.exists():
        print(f"Database not found. Initializing at {config.DB_PATH}...")
        try:
            with sqlite3.connect(config.DB_PATH) as conn:
                with open("schema.sql", "r", encoding="utf-8") as f:
                    conn.executescript(f.read())
            print("Database successfully initialized.")
        except Exception as e:
            print(f"Error initializing database: {e}")


def get_db():
    """Context-aware database connection helper."""
    if "db" not in g:
        g.db = sqlite3.connect(config.DB_PATH, check_same_thread=False)
        g.db.row_factory = sqlite3.Row
        # Ensure Foreign Keys are enforced in SQLite
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(exc=None):
    """Closes the database connection at the end of the request."""
    db = g.pop("db", None)
    if db:
        db.close()


@app.route("/jobs", methods=["POST"])
def create_job():
    """Hiring Manager: Create a new job opening."""
    data = request.json
    if not data or "title" not in data or "description" not in data:
        return jsonify({"error": "Missing title or description"}), 400

    db = get_db()
    cur = db.execute(
        "INSERT INTO jobs (title, description, requirements) VALUES (?, ?, ?)",
        (data["title"], data["description"], data.get("requirements", ""))
    )
    db.commit()
    return jsonify({"id": cur.lastrowid, "message": "Job created"}), 201


@app.route("/applications", methods=["POST"])
def submit_application():
    """Candidate: Submit a resume for a specific job."""
    job_id = request.form.get("job_id")
    name = request.form.get("applicant_name")
    email = request.form.get("applicant_email")
    file = request.files.get("resume")

    if not all([job_id, name, email, file]):
        return jsonify({"error": "Missing required fields"}), 400

    # Save PDF and Extract Text
    filename = f"{uuid.uuid4()}_{secure_filename(file.filename)}"
    save_path = config.UPLOAD_DIR / filename
    file.save(save_path)

    resume_text = extract_text_from_pdf(save_path)
    if not resume_text.strip():
        return jsonify({"error": "Unreadable PDF content"}), 400

    db = get_db()
    job = db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    if not job:
        return jsonify({"error": "Job not found"}), 404

    # Record Application
    cur = db.execute(
        "INSERT INTO applications (job_id, applicant_name, applicant_email, resume_text) VALUES (?, ?, ?, ?)",
        (job_id, name, email, resume_text)
    )
    db.commit()
    app_id = cur.lastrowid

    # Trigger Async AI logic in a background thread
    threading.Thread(
        target=screen_application_async,
        args=(app_id, resume_text, f"{job['title']}\n{job['description']}"),
        daemon=True
    ).start()

    return jsonify({"id": app_id, "status": "pending"}), 201


@app.route("/jobs/<int:job_id>/applications", methods=["GET"])
def list_accepted_applications(job_id):
    """Hiring Manager: View only accepted candidates for a specific job."""
    db = get_db()
    rows = db.execute(
        "SELECT * FROM applications WHERE job_id=? AND filter_status='accepted'",
        (job_id,)
    ).fetchall()

    return jsonify([dict(row) for row in rows])


if __name__ == "__main__":
    # Ensure DB is ready before starting the Flask server
    init_db()
    app.run(debug=True)