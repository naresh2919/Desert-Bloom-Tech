import os
import secrets
import hmac
import re
from functools import wraps
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import mysql.connector
from mysql.connector import Error
from werkzeug.security import check_password_hash
from dotenv import load_dotenv
load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY") or secrets.token_hex(32)
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("COOKIE_SECURE", "0") == "1",
    MAX_CONTENT_LENGTH=64 * 1024,
)

def csrf_token():
    token = session.get("_csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["_csrf_token"] = token
    return token

def valid_csrf():
    supplied = request.form.get("_csrf_token", "")
    expected = session.get("_csrf_token", "")
    return bool(supplied and expected and hmac.compare_digest(supplied, expected))

def get_db():
    return mysql.connector.connect(
        host=os.environ.get("DB_HOST", "127.0.0.1"),
        port=int(os.environ.get("DB_PORT", "3306")),
        user=os.environ.get("DB_USER", "desert_user"),
        password=os.environ.get("DB_PASSWORD", ""),
        database=os.environ.get("DB_NAME", "desert_bloom"),
        connection_timeout=5,
    )

@app.get("/")
def home():
    return render_template("index.html")

@app.post("/api/contact")
def save_contact():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(success=False, message="Invalid request data."), 400

    fields = ["name", "email", "phone", "clientType", "category", "budget", "deadline", "description"]
    clean = {key: str(data.get(key, "") or "").strip() for key in fields}
    if not clean["name"] or not clean["email"] or not clean["clientType"] or not clean["category"] or not clean["description"]:
        return jsonify(success=False, message="Please fill in all required fields."), 400
    if len(clean["name"]) > 120 or len(clean["email"]) > 254 or len(clean["phone"]) > 30 or len(clean["clientType"]) > 100 or len(clean["category"]) > 150 or len(clean["budget"]) > 80 or len(clean["deadline"]) > 120 or len(clean["description"]) > 5000:
        return jsonify(success=False, message="One or more fields are too long."), 400
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", clean["email"]):
        return jsonify(success=False, message="Please enter a valid email address."), 400

    conn = None
    cursor = None
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO enquiries
            (full_name, email, phone, client_type, category, budget, deadline, description)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (clean["name"], clean["email"], clean["phone"], clean["clientType"],
              clean["category"], clean["budget"], clean["deadline"], clean["description"]))
        conn.commit()
        return jsonify(success=True, message="Your enquiry was saved successfully. WhatsApp is ready too.")
    except Error:
        app.logger.exception("Could not save enquiry")
        return jsonify(success=False, message="Could not save your enquiry. Check the server/database configuration."), 500
    finally:
        if cursor:
            cursor.close()
        if conn and conn.is_connected():
            conn.close()

def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("admin_logged_in"):
            return redirect(url_for("admin_login"))
        return view(*args, **kwargs)
    return wrapped

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    error = ""
    if request.method == "POST":
        if not valid_csrf():
            return "Invalid or expired form token. Refresh and try again.", 400
        password = request.form.get("password", "")
        # Set ADMIN_PASSWORD_HASH to a Werkzeug password hash in your environment.
        password_hash = os.environ.get("ADMIN_PASSWORD_HASH", "")
        if password_hash and check_password_hash(password_hash, password):
            session.clear()
            session["admin_logged_in"] = True
            return redirect(url_for("admin"))
        error = "Login failed. Configure ADMIN_PASSWORD_HASH and try again."
    return render_template("login.html", error=error, csrf_token=csrf_token())

@app.post("/admin/logout")
@admin_required
def admin_logout():
    if not valid_csrf():
        return "Invalid or expired form token. Refresh and try again.", 400
    session.clear()
    return redirect(url_for("admin_login"))

@app.get("/admin")
@admin_required
def admin():
    conn = None
    cursor = None
    try:
        conn = get_db()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT id, full_name, email, phone, client_type, category, budget, deadline, description, status, created_at FROM enquiries ORDER BY created_at DESC LIMIT 500")
        rows = cursor.fetchall()
        return render_template("admin.html", enquiries=rows, csrf_token=csrf_token())
    except Error:
        app.logger.exception("Could not load admin enquiries")
        return "Database error. Check server logs and database configuration.", 500
    finally:
        if cursor:
            cursor.close()
        if conn and conn.is_connected():
            conn.close()

@app.post("/admin/enquiry/<int:enquiry_id>/status")
@admin_required
def update_status(enquiry_id):
    if not valid_csrf():
        return "Invalid or expired form token. Refresh and try again.", 400
    status = request.form.get("status", "")
    allowed = {"New", "In Progress", "Completed", "Closed"}
    if status not in allowed:
        return "Invalid status", 400
    conn = None
    cursor = None
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("UPDATE enquiries SET status=%s WHERE id=%s", (status, enquiry_id))
        conn.commit()
        return redirect(url_for("admin"))
    except Error:
        app.logger.exception("Could not update enquiry status")
        return "Database error", 500
    finally:
        if cursor:
            cursor.close()
        if conn and conn.is_connected():
            conn.close()

if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG", "0") == "1")
