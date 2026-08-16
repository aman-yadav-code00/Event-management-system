"""
database.py
-----------
All database access for the College Event Management System.
Uses Python's built-in sqlite3 -- no external DB server needed.
"""

import sqlite3
import os
import secrets
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash

DB_PATH = os.path.join(os.path.dirname(__file__), "college_events.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('student','organizer','admin')),
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    category TEXT NOT NULL,
    venue TEXT NOT NULL,
    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL,
    capacity INTEGER NOT NULL,
    requires_approval INTEGER NOT NULL DEFAULT 0,
    banner_emoji TEXT DEFAULT '🎉',
    organizer_id INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','approved','rejected')),
    admin_note TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    FOREIGN KEY(organizer_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS schedule_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL,
    speaker TEXT DEFAULT '',
    location TEXT DEFAULT '',
    FOREIGN KEY(event_id) REFERENCES events(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS sponsors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    tier TEXT NOT NULL CHECK(tier IN ('Platinum','Gold','Silver','Community')),
    website TEXT DEFAULT '',
    description TEXT DEFAULT '',
    FOREIGN KEY(event_id) REFERENCES events(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS registrations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    ticket_code TEXT UNIQUE NOT NULL,
    status TEXT NOT NULL DEFAULT 'confirmed' CHECK(status IN ('pending','confirmed','rejected','cancelled','attended')),
    registered_at TEXT NOT NULL,
    FOREIGN KEY(event_id) REFERENCES events(id) ON DELETE CASCADE,
    FOREIGN KEY(user_id) REFERENCES users(id),
    UNIQUE(event_id, user_id)
);
"""


def init_db():
    fresh = not os.path.exists(DB_PATH)
    conn = get_db()
    conn.executescript(SCHEMA)
    conn.commit()
    if fresh:
        seed(conn)
    conn.close()


def gen_ticket_code():
    return "TCK-" + secrets.token_hex(4).upper()


def seed(conn):
    now = datetime.now().isoformat(timespec="seconds")

    def add_user(name, email, pw, role):
        conn.execute(
            "INSERT INTO users (name, email, password_hash, role, created_at) VALUES (?,?,?,?,?)",
            (name, email, generate_password_hash(pw), role, now),
        )
        return conn.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()["id"]

    admin_id = add_user("Admin User", "admin@college.edu", "admin123", "admin")
    org_id = add_user("Priya Sharma (CS Club)", "organizer@college.edu", "organizer123", "organizer")
    stud_id = add_user("Rahul Verma", "student@college.edu", "student123", "student")

    def add_event(title, desc, cat, venue, start, end, cap, approval, emoji, status, note=""):
        conn.execute(
            """INSERT INTO events
               (title, description, category, venue, start_time, end_time, capacity,
                requires_approval, banner_emoji, organizer_id, status, admin_note, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (title, desc, cat, venue, start, end, cap, approval, emoji, org_id, status, note, now),
        )
        return conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]

    base = datetime.now() + timedelta(days=10)

    e1 = add_event(
        "TechFest 2026 — Innovate & Ignite",
        "A flagship 2-day tech festival with hackathons, robotics demos, and guest talks from industry leaders.",
        "Technical", "Main Auditorium",
        base.replace(hour=9, minute=0).isoformat(timespec="minutes"),
        (base + timedelta(days=1)).replace(hour=18, minute=0).isoformat(timespec="minutes"),
        300, 0, "💻", "approved",
    )
    e2 = add_event(
        "Rhythm Nights — Annual Cultural Fest",
        "Music, dance, and drama competitions followed by a live band performance.",
        "Cultural", "Open Air Theatre",
        (base + timedelta(days=5)).replace(hour=17, minute=0).isoformat(timespec="minutes"),
        (base + timedelta(days=5)).replace(hour=22, minute=0).isoformat(timespec="minutes"),
        500, 1, "🎶", "approved",
    )
    e3 = add_event(
        "Startup Pitch Bootcamp",
        "A hands-on workshop for student entrepreneurs, ending with a pitch competition judged by alumni VCs.",
        "Workshop", "Seminar Hall B",
        (base + timedelta(days=2)).replace(hour=10, minute=0).isoformat(timespec="minutes"),
        (base + timedelta(days=2)).replace(hour=16, minute=0).isoformat(timespec="minutes"),
        80, 1, "🚀", "pending",
    )

    for title, s_off, e_off, speaker, loc in [
        ("Opening Keynote: The Future of AI", 0, 1, "Dr. Anil Kapoor (IIT alum)", "Main Auditorium"),
        ("24-Hour Hackathon Kickoff", 1, 2, "Organizing Committee", "Innovation Lab"),
        ("Robotics Showcase", 3, 4.5, "Robotics Club", "Main Auditorium"),
        ("Closing Ceremony & Prizes", 30, 31, "Chief Guest", "Main Auditorium"),
    ]:
        st = (base + timedelta(hours=s_off)).isoformat(timespec="minutes")
        en = (base + timedelta(hours=e_off)).isoformat(timespec="minutes")
        conn.execute(
            "INSERT INTO schedule_items (event_id,title,start_time,end_time,speaker,location) VALUES (?,?,?,?,?,?)",
            (e1, title, st, en, speaker, loc),
        )

    for ev, name, tier, site, desc in [
        (e1, "ByteWorks Technologies", "Platinum", "https://example.com", "Lead sponsor providing hackathon prizes and mentors."),
        (e1, "CloudNine Systems", "Gold", "https://example.com", "Cloud credits and workshop support."),
        (e2, "Campus Cafe", "Silver", "https://example.com", "Refreshment partner."),
    ]:
        conn.execute(
            "INSERT INTO sponsors (event_id,name,tier,website,description) VALUES (?,?,?,?,?)",
            (ev, name, tier, site, desc),
        )

    conn.execute(
        "INSERT INTO registrations (event_id,user_id,ticket_code,status,registered_at) VALUES (?,?,?,?,?)",
        (e1, stud_id, gen_ticket_code(), "confirmed", now),
    )

    conn.commit()
