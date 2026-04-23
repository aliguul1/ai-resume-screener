import threading
import sqlite3
from flask import Flask, request, jsonify, g
from werkzeug.utils import secure_filename
import config
from services.pdf_service import extract_text_from_pdf
from services.ai_service import screen_application_async

app = Flask(__name__)


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(config.DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(e_None):
    db = g.pop("db",None)
    if db is not None:
        db.close()


def init_db():
    """Initializes the database using the fixed schema logic."""
    with sqlite3.connect(config.DB_PATH) as conn:
        # Tables
        conn.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                requirements TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )""")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS applications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id INTEGER NOT NULL,
                applicant_name TEXT NOT NULL,
                applicant_email TEXT NOT NULL,
                resume_text TEXT,
                filter_status TEXT DEFAULT 'pending'
                    CHECK(filter_status IN ('pending','accepted','rejected')),
                ai_feedback TEXT,
                prompt_version TEXT,
                ai_model TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(job_id) REFERENCES jobs(id) ON DELETE CASCADE
            )""")

        # Indexes
        conn.execute("CREATE INDEX IF NOT EXISTS idx_applications_job ON applications(job_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_applications_status ON applications(filter_status)")

        # Triggers
        conn.execute("""
            CREATE TRIGGER IF NOT EXISTS jobs_updated_at AFTER UPDATE ON jobs
            BEGIN
                UPDATE jobs SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
            END;""")
        conn.execute("""
            CREATE TRIGGER IF NOT EXISTS apps_updated_at AFTER UPDATE ON applications
            BEGIN
                UPDATE applications SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
            END;""")


@app.route("/", methods=["GET"])
def home():
    return jsonify({"status": "online", "message": "Submit Job PDFs and CV PDFs here."})


@app.route("/jobs", methods=["POST"])
def create_job():
    """Hiring Manager: Upload a PDF of the Job Opening."""
    title = request.form.get("title")
    file = request.files.get("job_pdf")

    if not title or not file:
        return jsonify({"error": "Title and job_pdf are required"}), 400

    filename = secure_filename(f"job_{title}.pdf")
    path = config.UPLOAD_DIR / filename
    file.save(path)

    # Extract text from the Job PDF
    job_content = extract_text_from_pdf(path)

    db = get_db()
    # Mapping extracted text to the 'description' column per schema.sql
    cur = db.execute(
        "INSERT INTO jobs (title, description) VALUES (?, ?)",
        (title, job_content)
    )
    db.commit()
    return jsonify({"id": cur.lastrowid, "message": "Job opening PDF processed"}), 201


@app.route("/applications", methods=["POST"])
def submit_application():
    """Candidate: Submit a CV PDF."""
    job_id = request.form.get("job_id")
    name = request.form.get("applicant_name")
    email = request.form.get("applicant_email")
    file = request.files.get("resume")

    if not all([job_id, name, email, file]):
        return jsonify({"error": "Missing fields"}), 400

    # Save CV and Extract Text
    filename = secure_filename(f"cv_{email}_{job_id}.pdf")
    path = config.UPLOAD_DIR / filename
    file.save(path)
    resume_text = extract_text_from_pdf(path)

    db = get_db()
    # Updated to select 'description' instead of 'job_text'
    job = db.execute("SELECT description FROM jobs WHERE id = ?", (job_id,)).fetchone()
    if not job:
        return jsonify({"error": "Job not found"}), 404

    cur = db.execute(
        "INSERT INTO applications (job_id, applicant_name, applicant_email, resume_text) VALUES (?, ?, ?, ?)",
        (job_id, name, email, resume_text)
    )
    db.commit()
    app_id = cur.lastrowid

    # Run AI screening
    threading.Thread(
        target=screen_application_async,
        args=(app_id, resume_text, job['description']),
        daemon=True
    ).start()

    return jsonify({"id": app_id, "status": "pending"}), 201


@app.route("/jobs/<int:job_id>/applications", methods=["GET"])
def get_accepted(job_id):
    db = get_db()
    apps = db.execute(
        "SELECT * FROM applications WHERE job_id = ? AND filter_status = 'accepted'",
        (job_id,)
    ).fetchall()
    return jsonify([dict(row) for row in apps])


if __name__ == "__main__":
    init_db()
    app.run(debug=True, port=5000)