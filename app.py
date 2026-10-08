import json
import secrets
import sqlite3
from contextlib import closing
from datetime import timedelta
from pathlib import Path

from flask import (
    Flask,
    abort,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash


app = Flask(__name__)

SERVICES = {
    "bonafide": "Bonafide certificate",
    "fees": "Fee enquiry",
    "exam": "Examination forms",
    "verification": "Document verification",
}

DATA_FOLDER = Path(app.root_path) / "instance"
DATA_FOLDER.mkdir(exist_ok=True)

DATABASE = DATA_FOLDER / "queue.db"
STAFF_CONFIG = DATA_FOLDER / "staff_config.json"

staff_configuration = {}

if STAFF_CONFIG.exists():
    staff_configuration = json.loads(
        STAFF_CONFIG.read_text(encoding="utf-8")
    )

STAFF_PASSWORD_HASH = staff_configuration.get("password_hash")

app.config.update(
    SECRET_KEY=(
        staff_configuration.get("secret_key")
        or secrets.token_hex(32)
    ),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=False,
    PERMANENT_SESSION_LIFETIME=timedelta(hours=1),
    SESSION_REFRESH_EACH_REQUEST=False,
    MAX_CONTENT_LENGTH=16 * 1024,
)


def init_database():
    """Create the table without deleting existing tokens."""
    with closing(sqlite3.connect(DATABASE, timeout=15)) as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                service TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'waiting',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        connection.commit()


def csrf_token():
    """Security token used by staff forms."""
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_hex(32)

    return session["csrf_token"]


app.jinja_env.globals["csrf_token"] = csrf_token


@app.before_request
def protect_staff_routes():
    is_staff_path = (
        request.path == "/staff"
        or request.path.startswith("/staff/")
    )

    if not is_staff_path:
        return None

    if not STAFF_PASSWORD_HASH:
        abort(
            503,
            description=(
                "Staff access is not configured. "
                "Run setup_staff.py and restart the application."
            ),
        )

    if request.endpoint != "staff_login" and not session.get("staff"):
        # Live updates need a clear response when login expires.
        if request.endpoint == "staff_updates":
            return jsonify(
                error="login_required",
                login_url=url_for("staff_login"),
            ), 401

        return redirect(url_for("staff_login"), code=303)

    if request.method == "POST":
        expected = session.get("csrf_token", "")
        supplied = request.form.get("csrf_token", "")

        if not expected or not secrets.compare_digest(expected, supplied):
            abort(
                400,
                description=(
                    "This form expired or could not be verified. "
                    "Reload the page and try again."
                ),
            )

    return None


@app.after_request
def response_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "same-origin"

    if (
        request.path == "/staff"
        or request.path.startswith("/staff/")
        or request.path.startswith("/tokens/")
    ):
        response.headers["Cache-Control"] = "no-store"

    return response


@app.route("/staff/login", methods=["GET", "POST"])
def staff_login():
    if session.get("staff"):
        return redirect(url_for("staff_dashboard"))

    error = None

    if request.method == "POST":
        password = request.form.get("password", "")

        if check_password_hash(STAFF_PASSWORD_HASH, password):
            session.clear()
            session["staff"] = True
            session.permanent = True
            csrf_token()

            return redirect(url_for("staff_dashboard"), code=303)

        error = "Incorrect password. Please try again."

    return render_template(
        "login.html",
        error=error,
    ), (401 if error else 200)


@app.post("/staff/logout")
def staff_logout():
    session.clear()
    return redirect(url_for("staff_login"), code=303)


@app.get("/")
def home():
    return render_template(
        "index.html",
        services=SERVICES,
    )


@app.post("/tokens")
def create_token():
    service = request.form.get("service", "")

    if service not in SERVICES:
        return render_template(
            "index.html",
            services=SERVICES,
            error="Please select a valid service.",
        ), 400

    with closing(sqlite3.connect(DATABASE, timeout=15)) as connection:
        cursor = connection.execute(
            "INSERT INTO tokens (service) VALUES (?)",
            (service,),
        )
        token_id = cursor.lastrowid
        connection.commit()

    return redirect(
        url_for("view_token", token_id=token_id),
        code=303,
    )


def get_token_details(token_id):
    """Read related queue information from one database snapshot."""
    with closing(sqlite3.connect(DATABASE, timeout=15)) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("BEGIN")

        token = connection.execute(
            "SELECT * FROM tokens WHERE id = ?",
            (token_id,),
        ).fetchone()

        if token is None:
            abort(404)

        current_token = connection.execute("""
            SELECT *
            FROM tokens
            WHERE status = 'serving'
            ORDER BY id ASC
            LIMIT 1
        """).fetchone()

        waiting_before = connection.execute(
            """
            SELECT COUNT(*) AS total
            FROM tokens
            WHERE status = 'waiting' AND id < ?
            """,
            (token_id,),
        ).fetchone()["total"]

    waiting_position = None
    students_ahead = None

    if token["status"] == "waiting":
        waiting_position = waiting_before + 1
        students_ahead = waiting_before + int(current_token is not None)

    return {
        "token": token,
        "token_number": f"Q-{token['id']:03d}",
        "service_name": SERVICES[token["service"]],
        "current_token": current_token,
        "waiting_position": waiting_position,
        "students_ahead": students_ahead,
    }


@app.get("/tokens/<int:token_id>")
def view_token(token_id):
    return render_template(
        "token.html",
        **get_token_details(token_id),
    )


@app.get("/tokens/<int:token_id>/updates")
def token_updates(token_id):
    """Return just the student queue panel for live updates."""
    details = get_token_details(token_id)

    return jsonify(
        html=render_template("_token_panel.html", **details),
    )


def get_staff_details():
    with closing(sqlite3.connect(DATABASE, timeout=15)) as connection:
        connection.row_factory = sqlite3.Row

        tokens = connection.execute(
            "SELECT * FROM tokens ORDER BY id ASC"
        ).fetchall()

    current_token = next(
        (token for token in tokens if token["status"] == "serving"),
        None,
    )

    waiting_tokens = [
        token for token in tokens if token["status"] == "waiting"
    ]

    return {
        "tokens": tokens,
        "services": SERVICES,
        "current_token": current_token,
        "waiting_tokens": waiting_tokens,
    }


@app.get("/staff")
def staff_dashboard():
    return render_template(
        "staff.html",
        notice=request.args.get("notice"),
        **get_staff_details(),
    )


@app.get("/staff/updates")
def staff_updates():
    """This endpoint is protected by the staff login check."""
    return jsonify(
        html=render_template(
            "_staff_panel.html",
            **get_staff_details(),
        ),
    )


@app.post("/staff/call-next")
def call_next():
    with closing(sqlite3.connect(DATABASE, timeout=15)) as connection:
        cursor = connection.execute("""
            UPDATE tokens
            SET status = 'serving'
            WHERE id = (
                SELECT id
                FROM tokens
                WHERE status = 'waiting'
                ORDER BY id ASC
                LIMIT 1
            )
            AND NOT EXISTS (
                SELECT 1 FROM tokens WHERE status = 'serving'
            )
        """)

        called = cursor.rowcount == 1
        connection.commit()

    return redirect(
        url_for(
            "staff_dashboard",
            notice="called" if called else "not_called",
        ),
        code=303,
    )


def finish_current_token(token_id, new_status):
    with closing(sqlite3.connect(DATABASE, timeout=15)) as connection:
        cursor = connection.execute(
            """
            UPDATE tokens
            SET status = ?
            WHERE id = ? AND status = 'serving'
            """,
            (new_status, token_id),
        )

        changed = cursor.rowcount == 1
        connection.commit()

    return redirect(
        url_for(
            "staff_dashboard",
            notice=new_status if changed else "not_updated",
        ),
        code=303,
    )


@app.post("/staff/complete/<int:token_id>")
def complete_token(token_id):
    return finish_current_token(token_id, "completed")


@app.post("/staff/skip/<int:token_id>")
def skip_token(token_id):
    return finish_current_token(token_id, "skipped")


init_database()

if __name__ == "__main__":
    app.run(debug=True)