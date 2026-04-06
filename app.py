import sqlite3
import threading
import uuid

from flask import Flask, request, jsonify, g
from werkzeug.utils import secure_filename

import config
from pdf_service import extract_text_from_pdf
from ai_service import screen_application_async


app = Flask(__name__)

app.config["MAX_CONTENT_LENGTH"] = config.MAX_UPLOAD_SIZE
config.UPLOAD_DIR.mkdir(exist_ok=True)


# ---------------------------
# DB helpers
# ---------------------------

def get_db():

    if "db" not in g:

        g.db = sqlite3.connect(config.DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")

    return g.db


@app.teardown_appcontext
def close_db(exc=None):

    db = g.pop("db", None)

    if db:
        db.close()


def row_to_dict(row):
    return dict(row) if row else None


# ---------------------------
# Job endpoints
# ---------------------------

@app.route("/jobs", methods=["GET"])
def list_jobs():

    db = get_db()

    rows = db.execute(
        "SELECT * FROM jobs ORDER BY created_at DESC"
    ).fetchall()

    return jsonify([row_to_dict(r) for r in rows])


@app.route("/jobs/<int:job_id>", methods=["GET"])
def get_job(job_id):

    db = get_db()

    row = db.execute(
        "SELECT * FROM jobs WHERE id=?",
        (job_id,)
    ).fetchone()

    if not row:
        return jsonify({"error": "Job not found"}), 404

    return jsonify(row_to_dict(row))


@app.route("/jobs", methods=["POST"])
def create_job():

    data = request.get_json()

    if not data.get("title") or not data.get("description"):
        return jsonify({"error": "title and description required"}), 400

    db = get_db()

    cur = db.execute(
        """
        INSERT INTO jobs (title, description, requirements)
        VALUES (?, ?, ?)
        """,
        (data["title"], data["description"], data.get("requirements"))
    )

    db.commit()

    return jsonify({"id": cur.lastrowid}), 201


@app.route("/jobs/<int:job_id>", methods=["PUT"])
def update_job(job_id):

    data = request.get_json()

    db = get_db()

    db.execute(
        """
        UPDATE jobs
        SET title = COALESCE(?, title),
            description = COALESCE(?, description),
            requirements = COALESCE(?, requirements)
        WHERE id=?
        """,
        (data.get("title"), data.get("description"), data.get("requirements"), job_id)
    )

    db.commit()

    return jsonify({"message": "Job updated"})


@app.route("/jobs/<int:job_id>", methods=["DELETE"])
def delete_job(job_id):

    db = get_db()

    db.execute("DELETE FROM jobs WHERE id=?", (job_id,))
    db.commit()

    return jsonify({"message": "Job deleted"})


# ---------------------------
# Applications
# ---------------------------

@app.route("/applications", methods=["POST"])
def submit_application():

    job_id = request.form.get("job_id")
    name = request.form.get("applicant_name")
    email = request.form.get("applicant_email")
    resume_file = request.files.get("resume")

    if not all([job_id, name, email, resume_file]):
        return jsonify({"error": "missing fields"}), 400

    if "." not in resume_file.filename:
        return jsonify({"error": "invalid file"}), 400

    if resume_file.filename.split(".")[-1].lower() != "pdf":
        return jsonify({"error": "PDF only"}), 400

    db = get_db()

    job = db.execute(
        "SELECT * FROM jobs WHERE id=?",
        (job_id,)
    ).fetchone()

    if not job:
        return jsonify({"error": "Job not found"}), 404

    filename = secure_filename(f"{uuid.uuid4()}.pdf")
    pdf_path = config.UPLOAD_DIR / filename

    resume_file.save(pdf_path)

    resume_text = extract_text_from_pdf(pdf_path)

    cur = db.execute(
        """
        INSERT INTO applications
        (job_id, applicant_name, applicant_email, resume_text)
        VALUES (?, ?, ?, ?)
        """,
        (job_id, name, email, resume_text)
    )

    db.commit()

    app_id = cur.lastrowid

    job_description = f"""
{job["title"]}

{job["description"]}

Requirements:
{job["requirements"]}
"""

    thread = threading.Thread(
        target=screen_application_async,
        args=(app_id, resume_text, job_description),
        daemon=True
    )

    thread.start()

    return jsonify({
        "id": app_id,
        "filter_status": "pending"
    }), 201


@app.route("/applications/<int:app_id>", methods=["GET"])
def get_application(app_id):

    db = get_db()

    row = db.execute(
        "SELECT * FROM applications WHERE id=?",
        (app_id,)
    ).fetchone()

    if not row:
        return jsonify({"error": "Application not found"}), 404

    data = row_to_dict(row)

    data.pop("resume_text", None)

    return jsonify(data)


@app.route("/jobs/<int:job_id>/applications", methods=["GET"])
def list_accepted(job_id):

    db = get_db()

    rows = db.execute(
        """
        SELECT * FROM applications
        WHERE job_id=? AND filter_status='accepted'
        """,
        (job_id,)
    ).fetchall()

    return jsonify([row_to_dict(r) for r in rows])


# ---------------------------
# Health check
# ---------------------------

@app.route("/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    app.run(debug=True)