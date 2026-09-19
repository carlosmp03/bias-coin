import sqlite3
from datetime import datetime, timezone
from typing import Optional

from config import DB_PATH, DEFAULT_TIMEZONE, QUIET_END, QUIET_START


def utc_now():
    return datetime.now(timezone.utc)


def now_iso():
    return utc_now().isoformat()


def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH, timeout=30)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    return db


def _columns(db, table):
    return {r["name"] for r in db.execute(f"PRAGMA table_info({table})")}


def _add_column(db, table, name, definition):
    if name not in _columns(db, table):
        db.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")


def init_db():
    with connect() as db:
        # Compatible with the existing repository/database.
        db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY
            )
        """)
        for name, definition in {
            "chat_id": "INTEGER",
            "timezone": f"TEXT NOT NULL DEFAULT '{DEFAULT_TIMEZONE}'",
            "agent_enabled": "INTEGER NOT NULL DEFAULT 1",
            "quiet_start": f"TEXT NOT NULL DEFAULT '{QUIET_START}'",
            "quiet_end": f"TEXT NOT NULL DEFAULT '{QUIET_END}'",
            "created_at": "TEXT",
            "last_seen_at": "TEXT",
        }.items():
            _add_column(db, "users", name, definition)

        db.execute("""
            CREATE TABLE IF NOT EXISTS commitments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                text TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'proposed',
                created_at TEXT NOT NULL,
                started_at TEXT,
                completed_at TEXT,
                cancelled_at TEXT
            )
        """)

        db.execute("""
            CREATE TABLE IF NOT EXISTS agent_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                commitment_id INTEGER NOT NULL,
                status TEXT NOT NULL,
                focus_minutes INTEGER NOT NULL,
                started_at TEXT NOT NULL,
                due_at TEXT NOT NULL,
                next_ping_at TEXT,
                nag_stage INTEGER NOT NULL DEFAULT 0,
                ended_at TEXT
            )
        """)

        db.execute("""
            CREATE TABLE IF NOT EXISTS agent_reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                commitment_id INTEGER,
                due_at TEXT NOT NULL,
                kind TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL
            )
        """)

        db.execute("""
            CREATE TABLE IF NOT EXISTS agent_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                event_type TEXT NOT NULL,
                text TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)

        db.execute("""
            CREATE TABLE IF NOT EXISTS agent_memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                text TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            )
        """)

        db.execute("""
            CREATE TABLE IF NOT EXISTS daily_pings (
                user_id INTEGER NOT NULL,
                local_date TEXT NOT NULL,
                kind TEXT NOT NULL,
                sent_at TEXT NOT NULL,
                PRIMARY KEY(user_id, local_date, kind)
            )
        """)
        db.commit()


def ensure_user(user_id: int, chat_id: Optional[int] = None):
    now = now_iso()
    with connect() as db:
        db.execute("""
            INSERT OR IGNORE INTO users
            (user_id, chat_id, timezone, agent_enabled, quiet_start, quiet_end,
             created_at, last_seen_at)
            VALUES (?, ?, ?, 1, ?, ?, ?, ?)
        """, (
            user_id, chat_id, DEFAULT_TIMEZONE, QUIET_START, QUIET_END, now, now
        ))
        db.execute("""
            UPDATE users
            SET chat_id=COALESCE(?, chat_id),
                last_seen_at=?,
                created_at=COALESCE(created_at, ?)
            WHERE user_id=?
        """, (chat_id, now, now, user_id))
        db.commit()


def get_user(user_id):
    with connect() as db:
        return db.execute(
            "SELECT * FROM users WHERE user_id=?", (user_id,)
        ).fetchone()


def all_users():
    with connect() as db:
        return db.execute(
            "SELECT * FROM users WHERE chat_id IS NOT NULL AND agent_enabled=1"
        ).fetchall()


def log_event(user_id, role, event_type, text):
    with connect() as db:
        db.execute("""
            INSERT INTO agent_events(user_id, role, event_type, text, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, role, event_type, text, now_iso()))
        db.commit()


def recent_events(user_id, limit=12):
    with connect() as db:
        rows = db.execute("""
            SELECT role, event_type, text, created_at
            FROM agent_events
            WHERE user_id=?
            ORDER BY id DESC
            LIMIT ?
        """, (user_id, limit)).fetchall()
    return list(reversed(rows))


def memories(user_id, limit=20):
    with connect() as db:
        return db.execute("""
            SELECT text, created_at
            FROM agent_memories
            WHERE user_id=? AND active=1
            ORDER BY id DESC
            LIMIT ?
        """, (user_id, limit)).fetchall()


def save_memory(user_id, text):
    text = (text or "").strip()
    if not text:
        return
    with connect() as db:
        exists = db.execute("""
            SELECT 1 FROM agent_memories
            WHERE user_id=? AND active=1 AND text=?
        """, (user_id, text)).fetchone()
        if not exists:
            db.execute("""
                INSERT INTO agent_memories(user_id, text, created_at)
                VALUES (?, ?, ?)
            """, (user_id, text, now_iso()))
            db.commit()


def active_commitment(user_id):
    with connect() as db:
        return db.execute("""
            SELECT * FROM commitments
            WHERE user_id=? AND status IN ('proposed','active')
            ORDER BY id DESC LIMIT 1
        """, (user_id,)).fetchone()


def create_commitment(user_id, text, status="proposed"):
    cancel_open_commitments(user_id)
    with connect() as db:
        cur = db.execute("""
            INSERT INTO commitments(user_id, text, status, created_at)
            VALUES (?, ?, ?, ?)
        """, (user_id, text.strip(), status, now_iso()))
        db.commit()
        return cur.lastrowid


def cancel_open_commitments(user_id):
    now = now_iso()
    with connect() as db:
        db.execute("""
            UPDATE commitments
            SET status='cancelled', cancelled_at=?
            WHERE user_id=? AND status IN ('proposed','active')
        """, (now, user_id))
        db.execute("""
            UPDATE agent_sessions
            SET status='cancelled', ended_at=?
            WHERE user_id=? AND status IN ('working','waiting')
        """, (now, user_id))
        db.execute("""
            UPDATE agent_reminders
            SET status='cancelled'
            WHERE user_id=? AND status='pending'
        """, (user_id,))
        db.commit()


def activate_commitment(commitment_id):
    with connect() as db:
        db.execute("""
            UPDATE commitments
            SET status='active', started_at=COALESCE(started_at, ?)
            WHERE id=?
        """, (now_iso(), commitment_id))
        db.commit()


def complete_commitment(user_id):
    c = active_commitment(user_id)
    if not c:
        return None
    now = now_iso()
    with connect() as db:
        db.execute("""
            UPDATE commitments
            SET status='done', completed_at=?
            WHERE id=?
        """, (now, c["id"]))
        db.execute("""
            UPDATE agent_sessions
            SET status='done', ended_at=?
            WHERE user_id=? AND status IN ('working','waiting')
        """, (now, user_id))
        db.execute("""
            UPDATE agent_reminders SET status='done'
            WHERE user_id=? AND status='pending'
        """, (user_id,))
        db.commit()
    return c


def cancel_current(user_id):
    c = active_commitment(user_id)
    if not c:
        return None
    cancel_open_commitments(user_id)
    return c


def active_session(user_id):
    with connect() as db:
        return db.execute("""
            SELECT s.*, c.text AS commitment_text
            FROM agent_sessions s
            JOIN commitments c ON c.id=s.commitment_id
            WHERE s.user_id=? AND s.status IN ('working','waiting')
            ORDER BY s.id DESC LIMIT 1
        """, (user_id,)).fetchone()


def all_active_sessions():
    with connect() as db:
        return db.execute("""
            SELECT s.*, c.text AS commitment_text,
                   u.chat_id, u.timezone, u.quiet_start, u.quiet_end
            FROM agent_sessions s
            JOIN commitments c ON c.id=s.commitment_id
            JOIN users u ON u.user_id=s.user_id
            WHERE s.status IN ('working','waiting')
              AND u.chat_id IS NOT NULL
        """).fetchall()


def start_session(user_id, commitment_id, focus_minutes, due_at):
    now = now_iso()
    with connect() as db:
        db.execute("""
            UPDATE agent_sessions
            SET status='cancelled', ended_at=?
            WHERE user_id=? AND status IN ('working','waiting')
        """, (now, user_id))
        db.execute("""
            INSERT INTO agent_sessions
            (user_id, commitment_id, status, focus_minutes, started_at, due_at)
            VALUES (?, ?, 'working', ?, ?, ?)
        """, (user_id, commitment_id, focus_minutes, now, due_at))
        db.execute("""
            UPDATE commitments
            SET status='active', started_at=COALESCE(started_at, ?)
            WHERE id=?
        """, (now, commitment_id))
        db.commit()


def set_session_working(session_id, focus_minutes, due_at):
    with connect() as db:
        db.execute("""
            UPDATE agent_sessions
            SET status='working', focus_minutes=?, due_at=?,
                next_ping_at=NULL, nag_stage=0
            WHERE id=?
        """, (focus_minutes, due_at, session_id))
        db.commit()


def set_session_waiting(session_id, next_ping_at, nag_stage=0):
    with connect() as db:
        db.execute("""
            UPDATE agent_sessions
            SET status='waiting', next_ping_at=?, nag_stage=?
            WHERE id=?
        """, (next_ping_at, nag_stage, session_id))
        db.commit()


def advance_nag(session_id, nag_stage, next_ping_at):
    with connect() as db:
        db.execute("""
            UPDATE agent_sessions
            SET nag_stage=?, next_ping_at=?
            WHERE id=?
        """, (nag_stage, next_ping_at, session_id))
        db.commit()


def add_reminder(user_id, commitment_id, due_at, kind="start"):
    with connect() as db:
        db.execute("""
            INSERT INTO agent_reminders
            (user_id, commitment_id, due_at, kind, status, created_at)
            VALUES (?, ?, ?, ?, 'pending', ?)
        """, (user_id, commitment_id, due_at, kind, now_iso()))
        db.commit()


def due_reminders(now_iso_value):
    with connect() as db:
        return db.execute("""
            SELECT r.*, c.text AS commitment_text,
                   u.chat_id, u.timezone, u.quiet_start, u.quiet_end
            FROM agent_reminders r
            LEFT JOIN commitments c ON c.id=r.commitment_id
            JOIN users u ON u.user_id=r.user_id
            WHERE r.status='pending' AND r.due_at<=?
              AND u.chat_id IS NOT NULL
            ORDER BY r.id
        """, (now_iso_value,)).fetchall()


def mark_reminder_sent(reminder_id):
    with connect() as db:
        db.execute(
            "UPDATE agent_reminders SET status='sent' WHERE id=?",
            (reminder_id,)
        )
        db.commit()


def morning_ping_sent(user_id, local_date):
    with connect() as db:
        return db.execute("""
            SELECT 1 FROM daily_pings
            WHERE user_id=? AND local_date=? AND kind='morning'
        """, (user_id, local_date)).fetchone() is not None


def mark_morning_ping(user_id, local_date):
    with connect() as db:
        db.execute("""
            INSERT OR IGNORE INTO daily_pings(user_id, local_date, kind, sent_at)
            VALUES (?, ?, 'morning', ?)
        """, (user_id, local_date, now_iso()))
        db.commit()


def reset_agent(user_id):
    cancel_open_commitments(user_id)
    with connect() as db:
        db.execute("DELETE FROM agent_events WHERE user_id=?", (user_id,))
        db.execute("DELETE FROM agent_memories WHERE user_id=?", (user_id,))
        db.commit()
