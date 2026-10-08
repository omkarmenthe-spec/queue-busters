import sqlite3
from contextlib import closing
from pathlib import Path

from flask import (
    Flask,
    abort,
    redirect,
    render_template,
    request,
    url_for,
)

app = Flask(__name__)

# Available college office services.
SERVICES = {
    "bonafide": "Bonafide certificate",
    "fees": "Fee enquiry",
    "exam": "Examination forms",
    "verification": "Document verification",
}

# Store the database inside the project's instance folder.
DATA_FOLDER = Path(app.root_path) / "instance"
DATA_FOLDER.mkdir(exist_ok=True)

DATABASE = DATA_FOLDER / "queue.db"


def init_database():
    """Create the table while preserving existing tokens."""
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


@app.get("/")
def home():
    """Display the student service-selection page."""
    return render_template(
        "index.html",
        services=SERVICES,
    )


@app.post("/tokens")
def create_token():
    """Validate the selected service and generate a token."""
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


@app.get("/tokens/<int:token_id>")
def view_token(token_id):
    """Display a token, the current serving token and queue position."""
    with closing(sqlite3.connect(DATABASE, timeout=15)) as connection:
        connection.row_factory = sqlite3.Row

        # Read the queue information from one consistent snapshot.
        connection.execute("BEGIN")

        token = connection.execute(
            "SELECT * FROM tokens WHERE id = ?",
            (token_id,),
        ).fetchone()

        if token is None:
            abort(404)

        current_token = connection.execute(
            """
            SELECT *
            FROM tokens
            WHERE status = 'serving'
            ORDER BY id ASC
            LIMIT 1
            """
        ).fetchone()

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
        students_ahead = waiting_before

        if current_token is not None:
            students_ahead += 1

    return render_template(
        "token.html",
        token=token,
        token_number=f"Q-{token['id']:03d}",
        service_name=SERVICES[token["service"]],
        current_token=current_token,
        waiting_position=waiting_position,
        students_ahead=students_ahead,
    )


@app.get("/staff")
def staff_dashboard():
    """Display all tokens and the token currently being served."""
    with closing(sqlite3.connect(DATABASE, timeout=15)) as connection:
        connection.row_factory = sqlite3.Row

        tokens = connection.execute(
            "SELECT * FROM tokens ORDER BY id ASC"
        ).fetchall()

    current_token = next(
        (token for token in tokens if token["status"] == "serving"),
        None,
    )

    return render_template(
        "staff.html",
        tokens=tokens,
        services=SERVICES,
        current_token=current_token,
        notice=request.args.get("notice"),
    )


@app.post("/staff/call-next")
def call_next():
    """Call the earliest waiting token only when the counter is free."""
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
                SELECT 1
                FROM tokens
                WHERE status = 'serving'
            )
        """)

        called = cursor.rowcount == 1
        connection.commit()

    notice = "called" if called else "not_called"

    return redirect(
        url_for("staff_dashboard", notice=notice),
        code=303,
    )


@app.post("/staff/complete/<int:token_id>")
def complete_token(token_id):
    """Complete a token only if it is currently being served."""
    with closing(sqlite3.connect(DATABASE, timeout=15)) as connection:
        cursor = connection.execute(
            """
            UPDATE tokens
            SET status = 'completed'
            WHERE id = ? AND status = 'serving'
            """,
            (token_id,),
        )

        changed = cursor.rowcount == 1
        connection.commit()

    notice = "completed" if changed else "not_updated"

    return redirect(
        url_for("staff_dashboard", notice=notice),
        code=303,
    )


@app.post("/staff/skip/<int:token_id>")
def skip_token(token_id):
    """Mark the currently serving token as skipped."""
    with closing(sqlite3.connect(DATABASE, timeout=15)) as connection:
        cursor = connection.execute(
            """
            UPDATE tokens
            SET status = 'skipped'
            WHERE id = ? AND status = 'serving'
            """,
            (token_id,),
        )

        changed = cursor.rowcount == 1
        connection.commit()

    notice = "skipped" if changed else "not_updated"

    return redirect(
        url_for("staff_dashboard", notice=notice),
        code=303,
    )


init_database()

if __name__ == "__main__":
    app.run(debug=True)