import threading
import sqlite3
from flask import Flask, request, jsonify, g
from werkzeug.utils import secure_filename
import config
from services.pdf_service import extract_text_from_pdf
from services.ai_service import screen_application_async

app = Flask(__name__)


# --- Database Management ---

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(config.DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(e=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    """Initializes the database with full Schema, Indexes, and Triggers."""
    with sqlite3.connect(config.DB_PATH) as conn:
        # 1. Tables
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

        # 2. Indexes
        conn.execute("CREATE INDEX IF NOT EXISTS idx_applications_job ON applications(job_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_applications_status ON applications(filter_status)")

        # 3. Triggers
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


# --- ROUTES ---

@app.route("/", methods=["GET"])
def home():
    """RESTORED: Root endpoint for health checks."""
    return jsonify({"status": "online", "message": "Submit Job PDFs and CV PDFs here."})


@app.route("/jobs", methods=["POST"])
def create_job():
    """CREATE: Process Job PDF."""
    title = request.form.get("title")
    file = request.files.get("job_pdf")
    if not title or not file:
        return jsonify({"error": "Title and job_pdf are required"}), 400

    filename = secure_filename(f"job_{title}.pdf")
    path = config.UPLOAD_DIR / filename
    file.save(path)
    job_content = extract_text_from_pdf(path)

    db = get_db()
    cur = db.execute("INSERT INTO jobs (title, description) VALUES (?, ?)", (title, job_content))
    db.commit()
    return jsonify({"id": cur.lastrowid, "message": "Job opening created"}), 201


@app.route("/jobs", methods=["GET"])
def list_all_jobs():
    """READ: List all jobs."""
    db = get_db()
    jobs = db.execute("SELECT * FROM jobs ORDER BY created_at DESC").fetchall()
    return jsonify([dict(row) for row in jobs])


@app.route("/jobs/<int:job_id>", methods=["PUT"])
def update_job(job_id):
    """UPDATE: Update job title and description."""
    data = request.json
    title = data.get("title")
    description = data.get("description")

    db = get_db()
    db.execute(
        "UPDATE jobs SET title = COALESCE(?, title), description = COALESCE(?, description) WHERE id = ?",
        (title, description, job_id)
    )
    db.commit()
    return jsonify({"message": "Job updated"}), 200


@app.route("/jobs/<int:job_id>", methods=["DELETE"])
def delete_job(job_id):
    """DELETE: Remove job and its applications."""
    db = get_db()
    db.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
    db.commit()
    return jsonify({"message": "Job deleted"}), 200


@app.route("/applications", methods=["POST"])
def submit_application():
    """CREATE: Submit CV and trigger AI."""
    job_id = request.form.get("job_id")
    name = request.form.get("applicant_name")
    email = request.form.get("applicant_email")
    file = request.files.get("resume")

    if not all([job_id, name, email, file]):
        return jsonify({"error": "Missing fields"}), 400

    filename = secure_filename(f"cv_{email}_{job_id}.pdf")
    path = config.UPLOAD_DIR / filename
    file.save(path)
    resume_text = extract_text_from_pdf(path)

    db = get_db()
    job = db.execute("SELECT description FROM jobs WHERE id = ?", (job_id,)).fetchone()
    if not job:
        return jsonify({"error": "Job not found"}), 404

    cur = db.execute(
        "INSERT INTO applications (job_id, applicant_name, applicant_email, resume_text) VALUES (?, ?, ?, ?)",
        (job_id, name, email, resume_text)
    )
    db.commit()
    app_id = cur.lastrowid

    threading.Thread(
        target=screen_application_async,
        args=(app_id, resume_text, job['description']),
        daemon=True
    ).start()

    return jsonify({"id": app_id, "status": "pending"}), 201


@app.route("/jobs/<int:job_id>/applications", methods=["GET"])
def get_job_applications(job_id):
    """READ: Get all applications for a job."""
    status = request.args.get("status")
    db = get_db()
    query = "SELECT * FROM applications WHERE job_id = ?"
    params = [job_id]
    if status:
        query += " AND filter_status = ?"
        params.append(status)
    apps = db.execute(query, params).fetchall()
    return jsonify([dict(row) for row in apps])


@app.route("/applications/<int:app_id>", methods=["PUT"])
def update_application(app_id):
    """UPDATE: Update applicant_name, applicant_email, job_id, and resume_text."""
    data = request.json
    job_id = data.get("job_id")
    name = data.get("applicant_name")
    email = data.get("applicant_email")
    resume_text = data.get("resume_text")

    db = get_db()
    db.execute("""
        UPDATE applications SET 
            job_id = COALESCE(?, job_id), 
            applicant_name = COALESCE(?, applicant_name), 
            applicant_email = COALESCE(?, applicant_email), 
            resume_text = COALESCE(?, resume_text) 
        WHERE id = ?""",
               (job_id, name, email, resume_text, app_id)
               )
    db.commit()
    return jsonify({"message": "Application updated"}), 200


@app.route("/applications/<int:app_id>", methods=["DELETE"])
def delete_application(app_id):
    """DELETE: Remove a specific application."""
    db = get_db()
    db.execute("DELETE FROM applications WHERE id = ?", (app_id,))
    db.commit()
    return jsonify({"message": "Application deleted"}), 200


if __name__ == "__main__":
    init_db()
    app.run(debug=True, port=5000)
# import threading
# import sqlite3
# from flask import Flask, request, jsonify, g
# from werkzeug.utils import secure_filename
# import config
# from services.pdf_service import extract_text_from_pdf
# from services.ai_service import screen_application_async
#
# app = Flask(__name__)
#
# # --- Database Management ---
#
# def get_db():
#     if "db" not in g:
#         g.db = sqlite3.connect(config.DB_PATH)
#         g.db.row_factory = sqlite3.Row
#     return g.db
#
# @app.teardown_appcontext
# def close_db(e=None):
#     db = g.pop("db", None)
#     if db is not None:
#         db.close()
#
# def init_db():
#     """Initializes the database with full Schema, Indexes, and Triggers."""
#     with sqlite3.connect(config.DB_PATH) as conn:
#         # 1. Tables
#         conn.execute("""
#             CREATE TABLE IF NOT EXISTS jobs (
#                 id INTEGER PRIMARY KEY AUTOINCREMENT,
#                 title TEXT NOT NULL,
#                 description TEXT NOT NULL,
#                 requirements TEXT,
#                 created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
#                 updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
#             )""")
#         conn.execute("""
#             CREATE TABLE IF NOT EXISTS applications (
#                 id INTEGER PRIMARY KEY AUTOINCREMENT,
#                 job_id INTEGER NOT NULL,
#                 applicant_name TEXT NOT NULL,
#                 applicant_email TEXT NOT NULL,
#                 resume_text TEXT,
#                 filter_status TEXT DEFAULT 'pending'
#                     CHECK(filter_status IN ('pending','accepted','rejected')),
#                 ai_feedback TEXT,
#                 prompt_version TEXT,
#                 ai_model TEXT,
#                 created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
#                 updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
#                 FOREIGN KEY(job_id) REFERENCES jobs(id) ON DELETE CASCADE
#             )""")
#
#         # 2. Indexes
#         conn.execute("CREATE INDEX IF NOT EXISTS idx_applications_job ON applications(job_id)")
#         conn.execute("CREATE INDEX IF NOT EXISTS idx_applications_status ON applications(filter_status)")
#
#         # 3. Triggers
#         conn.execute("""
#             CREATE TRIGGER IF NOT EXISTS jobs_updated_at AFTER UPDATE ON jobs
#             BEGIN
#                 UPDATE jobs SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
#             END;""")
#         conn.execute("""
#             CREATE TRIGGER IF NOT EXISTS apps_updated_at AFTER UPDATE ON applications
#             BEGIN
#                 UPDATE applications SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
#             END;""")
#
# # --- ROUTES ---
#
# @app.route("/", methods=["GET"])
# def home():
#     """RESTORED: Root endpoint for health checks."""
#     return jsonify({"status": "online", "message": "Submit Job PDFs and CV PDFs here."})
#
# @app.route("/jobs", methods=["POST"])
# def create_job():
#     """CREATE: Process Job PDF."""
#     title = request.form.get("title")
#     file = request.files.get("job_pdf")
#     if not title or not file:
#         return jsonify({"error": "Title and job_pdf are required"}), 400
#
#     filename = secure_filename(f"job_{title}.pdf")
#     path = config.UPLOAD_DIR / filename
#     file.save(path)
#     job_content = extract_text_from_pdf(path)
#
#     db = get_db()
#     cur = db.execute("INSERT INTO jobs (title, description) VALUES (?, ?)", (title, job_content))
#     db.commit()
#     return jsonify({"id": cur.lastrowid, "message": "Job opening created"}), 201
#
# @app.route("/jobs", methods=["GET"])
# def list_all_jobs():
#     """READ: List all jobs."""
#     db = get_db()
#     jobs = db.execute("SELECT * FROM jobs ORDER BY created_at DESC").fetchall()
#     return jsonify([dict(row) for row in jobs])
#
# @app.route("/jobs/<int:job_id>", methods=["DELETE"])
# def delete_job(job_id):
#     """DELETE: Remove job and its applications."""
#     db = get_db()
#     db.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
#     db.commit()
#     return jsonify({"message": "Job deleted"}), 200
#
# @app.route("/applications", methods=["POST"])
# def submit_application():
#     """CREATE: Submit CV and trigger AI."""
#     job_id = request.form.get("job_id")
#     name = request.form.get("applicant_name")
#     email = request.form.get("applicant_email")
#     file = request.files.get("resume")
#
#     if not all([job_id, name, email, file]):
#         return jsonify({"error": "Missing fields"}), 400
#
#     filename = secure_filename(f"cv_{email}_{job_id}.pdf")
#     path = config.UPLOAD_DIR / filename
#     file.save(path)
#     resume_text = extract_text_from_pdf(path)
#
#     db = get_db()
#     job = db.execute("SELECT description FROM jobs WHERE id = ?", (job_id,)).fetchone()
#     if not job:
#         return jsonify({"error": "Job not found"}), 404
#
#     cur = db.execute(
#         "INSERT INTO applications (job_id, applicant_name, applicant_email, resume_text) VALUES (?, ?, ?, ?)",
#         (job_id, name, email, resume_text)
#     )
#     db.commit()
#     app_id = cur.lastrowid
#
#     threading.Thread(
#         target=screen_application_async,
#         args=(app_id, resume_text, job['description']),
#         daemon=True
#     ).start()
#
#     return jsonify({"id": app_id, "status": "pending"}), 201
#
# @app.route("/jobs/<int:job_id>/applications", methods=["GET"])
# def get_job_applications(job_id):
#     """READ: Get all applications for a job."""
#     status = request.args.get("status")
#     db = get_db()
#     query = "SELECT * FROM applications WHERE job_id = ?"
#     params = [job_id]
#     if status:
#         query += " AND filter_status = ?"
#         params.append(status)
#     apps = db.execute(query, params).fetchall()
#     return jsonify([dict(row) for row in apps])
#
# @app.route("/applications/<int:app_id>", methods=["PATCH"])
# def manual_update_status(app_id):
#     """UPDATE: Change applicant status."""
#     new_status = request.json.get("filter_status")
#     if new_status not in ['pending', 'accepted', 'rejected']:
#         return jsonify({"error": "Invalid status"}), 400
#     db = get_db()
#     db.execute("UPDATE applications SET filter_status = ? WHERE id = ?", (new_status, app_id))
#     db.commit()
#     return jsonify({"message": "Status updated"})
#
#
# @app.route("/applications/<int:app_id>", methods=["DELETE"])
# def delete_application(app_id):
#     """DELETE: Remove a specific application by its ID."""
#     db = get_db()
#
#     # Check if it exists first (optional but good practice)
#     app_record = db.execute("SELECT id FROM applications WHERE id = ?", (app_id,)).fetchone()
#     if not app_record:
#         return jsonify({"error": "Application not found"}), 404
#
#     db.execute("DELETE FROM applications WHERE id = ?", (app_id,))
#     db.commit()
#
#     return jsonify({"message": f"Application {app_id} deleted successfully"}), 200
#
# if __name__ == "__main__":
#     init_db()
#     app.run(debug=True, port=5000)