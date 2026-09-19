import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from config import (
    DB_PATH, DEFAULT_EVENING_TIME, DEFAULT_MORNING_TIME,
    DEFAULT_TIMEZONE, PROBABILITY_SOURCE,
)

TASKS_FILE = Path(__file__).resolve().parent / "data" / "probability_list4.json"

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB_PATH, timeout=30)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA foreign_keys=ON")
    return c

def cols(c, table):
    return {r["name"] for r in c.execute(f"PRAGMA table_info({table})")}

def add_col(c, table, name, definition):
    if name not in cols(c, table):
        c.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")

def init_db():
    with conn() as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                action_tokens INTEGER NOT NULL DEFAULT 0,
                flips_total INTEGER NOT NULL DEFAULT 0,
                action_flips INTEGER NOT NULL DEFAULT 0,
                pause_flips INTEGER NOT NULL DEFAULT 0,
                done_count INTEGER NOT NULL DEFAULT 0
            )
        """)

        for name, definition in {
            "chat_id": "INTEGER",
            "timezone": f"TEXT NOT NULL DEFAULT '{DEFAULT_TIMEZONE}'",
            "morning_time": f"TEXT NOT NULL DEFAULT '{DEFAULT_MORNING_TIME}'",
            "evening_time": f"TEXT NOT NULL DEFAULT '{DEFAULT_EVENING_TIME}'",
            "current_task_id": "INTEGER",
            "state": "TEXT NOT NULL DEFAULT 'idle'",
            "created_at": "TEXT",
            "last_seen_at": "TEXT",
            "study_minutes": "INTEGER NOT NULL DEFAULT 0",
        }.items():
            add_col(c, "users", name, definition)

        c.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                source TEXT NOT NULL,
                task_no INTEGER NOT NULL,
                title TEXT NOT NULL,
                topic TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'todo',
                attempts INTEGER NOT NULL DEFAULT 0,
                completed_at TEXT,
                created_at TEXT NOT NULL,
                UNIQUE(user_id, source, task_no)
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                task_id INTEGER NOT NULL,
                started_at TEXT NOT NULL,
                due_at TEXT NOT NULL,
                duration_minutes INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'working',
                reminder_stage INTEGER NOT NULL DEFAULT 0,
                next_ping_at TEXT,
                last_prompt_at TEXT,
                credited INTEGER NOT NULL DEFAULT 0,
                ended_at TEXT
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                task_id INTEGER NOT NULL,
                text TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS daily_plans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                plan_date TEXT NOT NULL,
                main_goal TEXT NOT NULL,
                secondary_goal TEXT NOT NULL,
                study_goal TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(user_id, plan_date)
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS daily_notifications (
                user_id INTEGER NOT NULL,
                local_date TEXT NOT NULL,
                kind TEXT NOT NULL,
                sent_at TEXT NOT NULL,
                PRIMARY KEY(user_id, local_date, kind)
            )
        """)
        c.commit()

def ensure_user(user_id: int, chat_id: Optional[int] = None):
    now = now_iso()
    with conn() as c:
        c.execute("""
            INSERT OR IGNORE INTO users
            (user_id, chat_id, timezone, morning_time, evening_time,
             state, created_at, last_seen_at)
            VALUES (?, ?, ?, ?, ?, 'idle', ?, ?)
        """, (user_id, chat_id, DEFAULT_TIMEZONE, DEFAULT_MORNING_TIME,
              DEFAULT_EVENING_TIME, now, now))
        c.execute("""
            UPDATE users
            SET chat_id=COALESCE(?, chat_id), last_seen_at=?,
                created_at=COALESCE(created_at, ?)
            WHERE user_id=?
        """, (chat_id, now, now, user_id))
        c.commit()
    seed_tasks(user_id)

def seed_tasks(user_id):
    items = json.loads(TASKS_FILE.read_text(encoding="utf-8"))
    with conn() as c:
        for t in items:
            c.execute("""
                INSERT OR IGNORE INTO tasks
                (user_id, source, task_no, title, topic, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (user_id, PROBABILITY_SOURCE, t["task_no"],
                  t["title"], t["topic"], now_iso()))
        c.commit()

def get_user(user_id):
    with conn() as c:
        return c.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()

def users():
    with conn() as c:
        return c.execute("SELECT * FROM users WHERE chat_id IS NOT NULL").fetchall()

def set_state(user_id, state):
    with conn() as c:
        c.execute("UPDATE users SET state=? WHERE user_id=?", (state, user_id))
        c.commit()

def set_timezone(user_id, tz):
    with conn() as c:
        c.execute("UPDATE users SET timezone=? WHERE user_id=?", (tz, user_id))
        c.commit()

def set_schedule(user_id, morning, evening):
    with conn() as c:
        c.execute("UPDATE users SET morning_time=?, evening_time=? WHERE user_id=?",
                  (morning, evening, user_id))
        c.commit()

def current_task(user_id):
    with conn() as c:
        row = c.execute("""
            SELECT t.* FROM users u
            LEFT JOIN tasks t ON t.id=u.current_task_id
            WHERE u.user_id=?
        """, (user_id,)).fetchone()
        if row and row["id"] is not None and row["status"] != "done":
            return row
    return None

def next_task(user_id):
    cur = current_task(user_id)
    if cur:
        return cur
    with conn() as c:
        t = c.execute("""
            SELECT * FROM tasks
            WHERE user_id=? AND source=? AND status='todo'
            ORDER BY task_no LIMIT 1
        """, (user_id, PROBABILITY_SOURCE)).fetchone()
        if t:
            c.execute("UPDATE users SET current_task_id=? WHERE user_id=?",
                      (t["id"], user_id))
            c.commit()
        return t

def all_tasks(user_id):
    with conn() as c:
        return c.execute("""
            SELECT * FROM tasks WHERE user_id=? AND source=? ORDER BY task_no
        """, (user_id, PROBABILITY_SOURCE)).fetchall()

def active_session(user_id):
    with conn() as c:
        return c.execute("""
            SELECT s.*, t.task_no, t.title, t.topic
            FROM sessions s JOIN tasks t ON t.id=s.task_id
            WHERE s.user_id=? AND s.status IN ('working','waiting','snoozed')
            ORDER BY s.id DESC LIMIT 1
        """, (user_id,)).fetchone()

def active_sessions():
    with conn() as c:
        return c.execute("""
            SELECT s.*, u.chat_id, u.timezone, u.user_id,
                   t.task_no, t.title, t.topic
            FROM sessions s
            JOIN users u ON u.user_id=s.user_id
            JOIN tasks t ON t.id=s.task_id
            WHERE s.status IN ('working','waiting','snoozed')
              AND u.chat_id IS NOT NULL
        """).fetchall()

def create_session(user_id, task_id, minutes, due_at):
    now = now_iso()
    with conn() as c:
        c.execute("""
            UPDATE sessions SET status='cancelled', ended_at=?
            WHERE user_id=? AND status IN ('working','waiting','snoozed')
        """, (now, user_id))
        c.execute("""
            INSERT INTO sessions
            (user_id, task_id, started_at, due_at, duration_minutes, status)
            VALUES (?, ?, ?, ?, ?, 'working')
        """, (user_id, task_id, now, due_at, minutes))
        c.execute("UPDATE users SET state='working' WHERE user_id=?", (user_id,))
        c.commit()

def session_waiting(session_id, next_ping_at, stage=0):
    with conn() as c:
        c.execute("""
            UPDATE sessions SET status='waiting', reminder_stage=?,
            next_ping_at=?, last_prompt_at=? WHERE id=?
        """, (stage, next_ping_at, now_iso(), session_id))
        c.commit()

def session_working(session_id, due_at, minutes):
    with conn() as c:
        c.execute("""
            UPDATE sessions SET status='working', due_at=?, duration_minutes=?,
            reminder_stage=0, next_ping_at=NULL, credited=0 WHERE id=?
        """, (due_at, minutes, session_id))
        c.commit()

def session_snoozed(session_id, wake_at):
    with conn() as c:
        c.execute("""
            UPDATE sessions SET status='snoozed', next_ping_at=?, reminder_stage=0
            WHERE id=?
        """, (wake_at, session_id))
        c.commit()

def advance_reminder(session_id, stage, next_ping_at):
    with conn() as c:
        c.execute("""
            UPDATE sessions SET reminder_stage=?, next_ping_at=?,
            last_prompt_at=? WHERE id=?
        """, (stage, next_ping_at, now_iso(), session_id))
        c.commit()

def credit_session(user_id):
    s = active_session(user_id)
    if not s or s["credited"]:
        return 0
    minutes = int(s["duration_minutes"])
    with conn() as c:
        c.execute("UPDATE sessions SET credited=1 WHERE id=?", (s["id"],))
        c.execute("UPDATE users SET study_minutes=study_minutes+? WHERE user_id=?",
                  (minutes, user_id))
        c.commit()
    return minutes

def complete_task(user_id):
    t = current_task(user_id)
    if not t:
        return None
    now = now_iso()
    with conn() as c:
        c.execute("UPDATE tasks SET status='done', completed_at=? WHERE id=?",
                  (now, t["id"]))
        c.execute("""
            UPDATE users SET current_task_id=NULL, done_count=done_count+1,
            action_tokens=action_tokens+1, state='idle' WHERE user_id=?
        """, (user_id,))
        c.execute("""
            UPDATE sessions SET status='done', ended_at=?
            WHERE user_id=? AND status IN ('working','waiting','snoozed')
        """, (now, user_id))
        c.commit()
    return t

def skip_task(user_id):
    t = current_task(user_id)
    if not t:
        return None
    with conn() as c:
        c.execute("UPDATE tasks SET status='skipped' WHERE id=?", (t["id"],))
        c.execute("UPDATE users SET current_task_id=NULL,state='idle' WHERE user_id=?",
                  (user_id,))
        c.execute("""
            UPDATE sessions SET status='cancelled',ended_at=?
            WHERE user_id=? AND status IN ('working','waiting','snoozed')
        """, (now_iso(), user_id))
        c.commit()
    return t

def reopen_skipped(user_id):
    with conn() as c:
        cur = c.execute("""
            UPDATE tasks SET status='todo'
            WHERE user_id=? AND source=? AND status='skipped'
        """, (user_id, PROBABILITY_SOURCE))
        c.commit()
        return cur.rowcount

def save_attempt(user_id, text):
    t = current_task(user_id)
    if not t:
        return False
    with conn() as c:
        c.execute("""
            INSERT INTO attempts(user_id,task_id,text,created_at)
            VALUES (?,?,?,?)
        """, (user_id, t["id"], text, now_iso()))
        c.execute("UPDATE tasks SET attempts=attempts+1 WHERE id=?", (t["id"],))
        c.execute("UPDATE users SET state='idle' WHERE user_id=?", (user_id,))
        c.commit()
    return True

def upsert_plan(user_id, date, main, secondary, study):
    with conn() as c:
        c.execute("""
            INSERT INTO daily_plans
            (user_id,plan_date,main_goal,secondary_goal,study_goal,created_at)
            VALUES (?,?,?,?,?,?)
            ON CONFLICT(user_id,plan_date) DO UPDATE SET
            main_goal=excluded.main_goal,
            secondary_goal=excluded.secondary_goal,
            study_goal=excluded.study_goal,
            created_at=excluded.created_at
        """, (user_id, date, main, secondary, study, now_iso()))
        c.commit()

def plan(user_id, date):
    with conn() as c:
        return c.execute("""
            SELECT * FROM daily_plans WHERE user_id=? AND plan_date=?
        """, (user_id, date)).fetchone()

def notification_sent(user_id, date, kind):
    with conn() as c:
        return c.execute("""
            SELECT 1 FROM daily_notifications
            WHERE user_id=? AND local_date=? AND kind=?
        """, (user_id, date, kind)).fetchone() is not None

def mark_notification(user_id, date, kind):
    with conn() as c:
        c.execute("""
            INSERT OR IGNORE INTO daily_notifications
            (user_id,local_date,kind,sent_at) VALUES (?,?,?,?)
        """, (user_id, date, kind, now_iso()))
        c.commit()

def coin(user_id, action):
    with conn() as c:
        if action:
            c.execute("""
                UPDATE users SET flips_total=flips_total+1,
                action_flips=action_flips+1 WHERE user_id=?
            """, (user_id,))
        else:
            c.execute("""
                UPDATE users SET flips_total=flips_total+1,
                pause_flips=pause_flips+1 WHERE user_id=?
            """, (user_id,))
        c.commit()

def stats(user_id):
    with conn() as c:
        u = c.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
        x = c.execute("""
            SELECT
            SUM(status='done') done,
            SUM(status='todo') todo,
            SUM(status='skipped') skipped,
            COUNT(*) total
            FROM tasks WHERE user_id=? AND source=?
        """, (user_id, PROBABILITY_SOURCE)).fetchone()
    return dict(
        action_tokens=int(u["action_tokens"] or 0),
        flips_total=int(u["flips_total"] or 0),
        action_flips=int(u["action_flips"] or 0),
        pause_flips=int(u["pause_flips"] or 0),
        study_minutes=int(u["study_minutes"] or 0),
        done=int(x["done"] or 0),
        todo=int(x["todo"] or 0),
        skipped=int(x["skipped"] or 0),
        total=int(x["total"] or 0),
    )
