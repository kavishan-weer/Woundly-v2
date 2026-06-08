from __future__ import annotations

import base64
import hashlib
import json
import secrets
import sqlite3
import uuid
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from model_lib import WoundAnalyzer

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "woundly.db"
analyzer = None


def get_analyzer():
    global analyzer
    if analyzer is None:
        analyzer = WoundAnalyzer()
    return analyzer


def get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def run_migrations():
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    
    # Check users table
    cursor.execute("PRAGMA table_info(users)")
    columns = [row[1] for row in cursor.fetchall()]
    if "role" not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'patient'")
        conn.commit()

    # Check entries table
    cursor.execute("PRAGMA table_info(entries)")
    columns = [row[1] for row in cursor.fetchall()]
    if "clinician_status" not in columns:
        cursor.execute("ALTER TABLE entries ADD COLUMN clinician_status TEXT DEFAULT 'unreviewed'")
    if "clinician_note" not in columns:
        cursor.execute("ALTER TABLE entries ADD COLUMN clinician_note TEXT DEFAULT ''")
    if "reviewed_by" not in columns:
        cursor.execute("ALTER TABLE entries ADD COLUMN reviewed_by TEXT")
    if "reviewed_at" not in columns:
        cursor.execute("ALTER TABLE entries ADD COLUMN reviewed_at TEXT")
    conn.commit()
    conn.close()

run_migrations()


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


class WoundlyHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    # ── helpers ──────────────────────────────────────────────

    def read_json(self):
        length = int(self.headers.get("Content-Length", "0"))
        return json.loads(self.rfile.read(length))

    def send_json(self, payload, status=HTTPStatus.OK):
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def authenticate(self):
        """Return user row if valid bearer token, else None (sends 401)."""
        auth = self.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            self.send_json({"error": "Missing authorization token."}, HTTPStatus.UNAUTHORIZED)
            return None
        token = auth[7:]
        db = get_db()
        user = db.execute("SELECT id, username, role FROM users WHERE token = ?", (token,)).fetchone()
        db.close()
        if not user:
            self.send_json({"error": "Invalid or expired token."}, HTTPStatus.UNAUTHORIZED)
            return None
        return user

    def authenticate_clinician(self):
        user = self.authenticate()
        if not user:
            return None
        if user["role"] != "clinician":
            self.send_json({"error": "Access denied. Clinician role required."}, HTTPStatus.FORBIDDEN)
            return None
        return user

    # ── GET routes ───────────────────────────────────────────

    def do_GET(self):
        if self.path == "/api/health":
            return self.send_json({"status": "ok"})

        if self.path == "/api/me":
            user = self.authenticate()
            if not user:
                return
            return self.send_json({"id": user["id"], "username": user["username"], "role": user["role"]})

        if self.path == "/api/entries":
            user = self.authenticate()
            if not user:
                return
            db = get_db()
            rows = db.execute(
                "SELECT id, timestamp, photo, analysis_result, clinician_status, clinician_note, reviewed_by, reviewed_at FROM entries WHERE user_id = ? ORDER BY timestamp DESC",
                (user["id"],),
            ).fetchall()
            db.close()
            entries = []
            for row in rows:
                entries.append({
                    "id": row["id"],
                    "date": row["timestamp"],
                    "photo": row["photo"],
                    "modelAnalysis": json.loads(row["analysis_result"]),
                    "clinician_status": row["clinician_status"] or "unreviewed",
                    "clinician_note": row["clinician_note"] or "",
                    "reviewed_by": row["reviewed_by"],
                    "reviewed_at": row["reviewed_at"]
                })
            return self.send_json(entries)

        if self.path == "/api/clinician/queue":
            clinician = self.authenticate_clinician()
            if not clinician:
                return
            db = get_db()
            rows = db.execute(
                "SELECT e.id, e.user_id, e.timestamp, e.photo, e.analysis_result, "
                "e.clinician_status, e.clinician_note, e.reviewed_by, e.reviewed_at, "
                "u.username "
                "FROM entries e JOIN users u ON e.user_id = u.id "
                "ORDER BY e.timestamp DESC"
            ).fetchall()
            db.close()
            entries = []
            for row in rows:
                entries.append({
                    "id": row["id"],
                    "user_id": row["user_id"],
                    "username": row["username"],
                    "date": row["timestamp"],
                    "photo": row["photo"],
                    "modelAnalysis": json.loads(row["analysis_result"]),
                    "clinician_status": row["clinician_status"] or "unreviewed",
                    "clinician_note": row["clinician_note"] or "",
                    "reviewed_by": row["reviewed_by"],
                    "reviewed_at": row["reviewed_at"]
                })
            return self.send_json(entries)

        return super().do_GET()

    # ── POST routes ──────────────────────────────────────────

    def do_POST(self):
        if self.path == "/api/register":
            return self.handle_register()
        if self.path == "/api/login":
            return self.handle_login()
        if self.path == "/api/entries":
            return self.handle_save_entry()
        if self.path == "/api/analyze":
            return self.handle_analyze()
        if self.path == "/api/clinician/review":
            return self.handle_clinician_review()
        return self.send_error(HTTPStatus.NOT_FOUND)

    # ── DELETE routes ────────────────────────────────────────

    def do_DELETE(self):
        if self.path.startswith("/api/entries/"):
            return self.handle_delete_entry()
        return self.send_error(HTTPStatus.NOT_FOUND)

    def handle_delete_entry(self):
        user = self.authenticate()
        if not user:
            return
        entry_id = self.path.split("/api/entries/", 1)[1]
        if not entry_id:
            return self.send_json({"error": "Entry ID is required."}, HTTPStatus.BAD_REQUEST)
        db = get_db()
        cursor = db.execute(
            "DELETE FROM entries WHERE id = ? AND user_id = ?",
            (entry_id, user["id"]),
        )
        db.commit()
        deleted = cursor.rowcount
        db.close()
        if deleted == 0:
            return self.send_json({"error": "Entry not found."}, HTTPStatus.NOT_FOUND)
        return self.send_json({"status": "deleted", "id": entry_id})

    def handle_register(self):
        try:
            data = self.read_json()
            username = data.get("username", "").strip()
            password = data.get("password", "")
            role = data.get("role", "patient").strip()
            
            if not username or not password:
                return self.send_json({"error": "Username and password are required."}, HTTPStatus.BAD_REQUEST)
            if len(password) < 4:
                return self.send_json({"error": "Password must be at least 4 characters."}, HTTPStatus.BAD_REQUEST)
            if role not in ["patient", "clinician"]:
                return self.send_json({"error": "Invalid user role."}, HTTPStatus.BAD_REQUEST)
            
            if role == "clinician":
                reg_code = data.get("registrationCode", "").strip()
                if reg_code != "CLINIC2026":
                    return self.send_json({"error": "Invalid clinician registration code."}, HTTPStatus.BAD_REQUEST)

            user_id = str(uuid.uuid4())
            token = secrets.token_hex(32)
            pw_hash = hash_password(password)

            db = get_db()
            try:
                db.execute(
                    "INSERT INTO users (id, username, password_hash, token, role) VALUES (?, ?, ?, ?, ?)",
                    (user_id, username, pw_hash, token, role),
                )
                db.commit()
            except sqlite3.IntegrityError:
                db.close()
                return self.send_json({"error": "Username already taken."}, HTTPStatus.CONFLICT)
            db.close()
            return self.send_json({"token": token, "user": {"id": user_id, "username": username, "role": role}})
        except Exception as e:
            return self.send_json({"error": str(e)}, HTTPStatus.BAD_REQUEST)

    def handle_login(self):
        try:
            data = self.read_json()
            username = data.get("username", "").strip()
            password = data.get("password", "")
            if not username or not password:
                return self.send_json({"error": "Username and password are required."}, HTTPStatus.BAD_REQUEST)

            pw_hash = hash_password(password)
            db = get_db()
            user = db.execute(
                "SELECT id, username, role FROM users WHERE username = ? AND password_hash = ?",
                (username, pw_hash),
            ).fetchone()
            if not user:
                db.close()
                return self.send_json({"error": "Invalid username or password."}, HTTPStatus.UNAUTHORIZED)

            token = secrets.token_hex(32)
            db.execute("UPDATE users SET token = ? WHERE id = ?", (token, user["id"]))
            db.commit()
            db.close()
            return self.send_json({"token": token, "user": {"id": user["id"], "username": user["username"], "role": user["role"]}})
        except Exception as e:
            return self.send_json({"error": str(e)}, HTTPStatus.BAD_REQUEST)

    def handle_clinician_review(self):
        clinician = self.authenticate_clinician()
        if not clinician:
            return
        try:
            data = self.read_json()
            entry_id = data.get("entry_id")
            status = data.get("status", "unreviewed").strip()
            note = data.get("note", "").strip()
            
            if not entry_id:
                return self.send_json({"error": "Entry ID is required."}, HTTPStatus.BAD_REQUEST)
            if status not in ["unreviewed", "reviewed", "flagged"]:
                return self.send_json({"error": "Invalid review status."}, HTTPStatus.BAD_REQUEST)
                
            db = get_db()
            entry = db.execute("SELECT id FROM entries WHERE id = ?", (entry_id,)).fetchone()
            if not entry:
                db.close()
                return self.send_json({"error": "Entry not found."}, HTTPStatus.NOT_FOUND)
                
            import datetime
            now_str = datetime.datetime.now().isoformat()
            db.execute(
                "UPDATE entries SET clinician_status = ?, clinician_note = ?, reviewed_by = ?, reviewed_at = ? WHERE id = ?",
                (status, note, clinician["username"], now_str, entry_id)
            )
            db.commit()
            db.close()
            return self.send_json({
                "status": "success",
                "entry_id": entry_id,
                "clinician_status": status,
                "clinician_note": note,
                "reviewed_by": clinician["username"],
                "reviewed_at": now_str
            })
        except Exception as e:
            return self.send_json({"error": f"Failed to save review: {e}"}, HTTPStatus.BAD_REQUEST)

    def handle_save_entry(self):
        user = self.authenticate()
        if not user:
            return
        try:
            data = self.read_json()
            entry_id = data.get("id", str(uuid.uuid4()))
            timestamp = data.get("date", "")
            photo = data.get("photo", "")
            model_analysis = data.get("modelAnalysis", {})
            if not timestamp or not photo:
                return self.send_json({"error": "Entry requires date and photo."}, HTTPStatus.BAD_REQUEST)

            db = get_db()
            db.execute(
                "INSERT INTO entries (id, user_id, timestamp, photo, analysis_result) VALUES (?, ?, ?, ?, ?)",
                (str(entry_id), user["id"], timestamp, photo, json.dumps(model_analysis)),
            )
            db.commit()
            db.close()
            return self.send_json({"status": "saved", "id": str(entry_id)})
        except Exception as e:
            return self.send_json({"error": f"Failed to save entry: {e}"}, HTTPStatus.BAD_REQUEST)

    def handle_analyze(self):
        try:
            payload = self.read_json()
            image_data_url = payload["image"]
            encoded = image_data_url.split(",", 1)[1] if "," in image_data_url else image_data_url
            result = get_analyzer().analyze(base64.b64decode(encoded))
            self.send_json(result)
        except FileNotFoundError as error:
            self.send_json({"error": str(error)}, status=HTTPStatus.SERVICE_UNAVAILABLE)
        except Exception as error:
            self.send_json({"error": f"Analysis failed: {error}"}, status=HTTPStatus.BAD_REQUEST)


if __name__ == "__main__":
    print("Woundly running at http://localhost:4173")
    ThreadingHTTPServer(("127.0.0.1", 4173), WoundlyHandler).serve_forever()
