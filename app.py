"""
CampusEvents — College Event Management System
-----------------------------------------------
A production-grade Flask + SQLite event platform with:
  - Public event browsing & intelligent registration
  - Student dashboard with printable 3D tickets
  - Organizer event submission + schedule/sponsor management
  - Admin approval workflows with analytics

Run:  python app.py   ->  http://127.0.0.1:5000
"""

from functools import wraps
from datetime import datetime, timedelta

from flask import (
    Flask, render_template, request, redirect, url_for, session, flash, abort, jsonify
)
from werkzeug.security import generate_password_hash, check_password_hash

import database as db

app = Flask(__name__)
app.secret_key = "college-event-mvp-secret-key-change-in-production"

db.init_db()


# ---------------------------------------------------------------- helpers --
def current_user():
    if "user_id" not in session:
        return None
    conn = db.get_db()
    user = conn.execute("SELECT * FROM users WHERE id=?", (session["user_id"],)).fetchone()
    conn.close()
    return user


@app.context_processor
def inject_user():
    return {"current_user": current_user(), "now": datetime.now()}


def login_required(role=None):
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            user = current_user()
            if user is None:
                flash("Please log in to continue.", "warning")
                return redirect(url_for("login", next=request.path))
            if role and user["role"] != role and user["role"] != "admin":
                if not (role == "organizer" and user["role"] == "admin"):
                    flash("You don't have access to that page.", "danger")
                    return redirect(url_for("index"))
            return f(*args, **kwargs)
        return wrapped
    return decorator


def fmt_dt(value):
    if not value:
        return "—"
    try:
        return datetime.fromisoformat(value).strftime("%a, %d %b %Y · %I:%M %p")
    except Exception:
        return value


app.jinja_env.filters["fmt_dt"] = fmt_dt


def is_past_event(event_time_str):
    """Check if an event has already ended."""
    try:
        event_dt = datetime.fromisoformat(event_time_str)
        return event_dt < datetime.now()
    except Exception:
        return False


# ------------------------------------------------------------- public site --
@app.route("/")
def index():
    conn = db.get_db()
    q = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip()

    sql = """SELECT e.*, u.name AS organizer_name,
          (SELECT COUNT(*) FROM registrations r WHERE r.event_id=e.id AND r.status IN ('confirmed','pending')) AS seats_taken
          FROM events e JOIN users u ON u.id = e.organizer_id WHERE e.status='approved'"""
    params = []
    if q:
        sql += " AND (e.title LIKE ? OR e.description LIKE ?)"
        params += [f"%{q}%", f"%{q}%"]
    if category:
        sql += " AND e.category = ?"
        params.append(category)
    sql += " ORDER BY e.start_time ASC"

    events = conn.execute(sql, params).fetchall()
    categories = [r["category"] for r in conn.execute("SELECT DISTINCT category FROM events WHERE status='approved'")]
    stats = {
        "events": conn.execute("SELECT COUNT(*) c FROM events WHERE status='approved'").fetchone()["c"],
        "students": conn.execute("SELECT COUNT(*) c FROM users WHERE role='student'").fetchone()["c"],
        "tickets": conn.execute("SELECT COUNT(*) c FROM registrations WHERE status IN ('confirmed','attended')").fetchone()["c"],
        "organizers": conn.execute("SELECT COUNT(*) c FROM users WHERE role='organizer'").fetchone()["c"],
    }
    conn.close()
    return render_template("index.html", events=events, categories=categories, q=q, active_cat=category, stats=stats)


@app.route("/event/<int:event_id>")
def event_detail(event_id):
    conn = db.get_db()
    event = conn.execute(
        "SELECT e.*, u.name AS organizer_name FROM events e JOIN users u ON u.id=e.organizer_id WHERE e.id=?",
        (event_id,),
    ).fetchone()
    if not event or (event["status"] != "approved" and (not current_user() or current_user()["role"] == "student")):
        conn.close()
        abort(404)

    schedule = conn.execute(
        "SELECT * FROM schedule_items WHERE event_id=? ORDER BY start_time ASC", (event_id,)
    ).fetchall()
    sponsors = conn.execute(
        "SELECT * FROM sponsors WHERE event_id=? ORDER BY CASE tier "
        "WHEN 'Platinum' THEN 1 WHEN 'Gold' THEN 2 WHEN 'Silver' THEN 3 ELSE 4 END", (event_id,)
    ).fetchall()
    seats_taken = conn.execute(
        "SELECT COUNT(*) c FROM registrations WHERE event_id=? AND status IN ('confirmed','pending')", (event_id,)
    ).fetchone()["c"]

    my_reg = None
    user = current_user()
    if user:
        my_reg = conn.execute(
            "SELECT * FROM registrations WHERE event_id=? AND user_id=?", (event_id, user["id"])
        ).fetchone()
    conn.close()

    event_past = is_past_event(event["end_time"])

    return render_template(
        "event_detail.html", event=event, schedule=schedule, sponsors=sponsors,
        seats_taken=seats_taken, my_reg=my_reg, event_past=event_past,
    )


@app.route("/event/<int:event_id>/register", methods=["POST"])
@login_required(role="student")
def register_for_event(event_id):
    user = current_user()
    conn = db.get_db()
    event = conn.execute("SELECT * FROM events WHERE id=? AND status='approved'", (event_id,)).fetchone()
    if not event:
        conn.close()
        abort(404)

    if is_past_event(event["end_time"]):
        flash("This event has already ended.", "danger")
        conn.close()
        return redirect(url_for("event_detail", event_id=event_id))

    existing = conn.execute(
        "SELECT * FROM registrations WHERE event_id=? AND user_id=? AND status != 'cancelled'", (event_id, user["id"])
    ).fetchone()
    if existing:
        flash("You're already registered for this event.", "info")
        conn.close()
        return redirect(url_for("event_detail", event_id=event_id))

    seats_taken = conn.execute(
        "SELECT COUNT(*) c FROM registrations WHERE event_id=? AND status IN ('confirmed','pending')", (event_id,)
    ).fetchone()["c"]
    if seats_taken >= event["capacity"]:
        flash("Sorry, this event is fully booked.", "danger")
        conn.close()
        return redirect(url_for("event_detail", event_id=event_id))

    status = "pending" if event["requires_approval"] else "confirmed"
    code = db.gen_ticket_code()
    conn.execute(
        "INSERT INTO registrations (event_id,user_id,ticket_code,status,registered_at) VALUES (?,?,?,?,?)",
        (event_id, user["id"], code, status, datetime.now().isoformat(timespec="seconds")),
    )
    conn.commit()
    conn.close()
    if status == "pending":
        flash("Registered! This event requires admin approval — you'll see it confirmed on your dashboard once approved.", "info")
    else:
        flash("You're registered! Your ticket is ready on your dashboard.", "success")
    return redirect(url_for("student_dashboard"))


@app.route("/event/<int:event_id>/cancel", methods=["POST"])
@login_required()
def cancel_registration(event_id):
    user = current_user()
    conn = db.get_db()
    reg = conn.execute(
        "SELECT * FROM registrations WHERE event_id=? AND user_id=? AND status IN ('confirmed','pending')", 
        (event_id, user["id"])
    ).fetchone()
    if not reg:
        conn.close()
        flash("No active registration found.", "warning")
        return redirect(url_for("student_dashboard"))
    conn.execute(
        "UPDATE registrations SET status='cancelled' WHERE event_id=? AND user_id=?", (event_id, user["id"])
    )
    conn.commit()
    conn.close()
    flash("Registration cancelled.", "info")
    return redirect(url_for("student_dashboard"))


# --------------------------------------------------------------------- auth --
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        name = request.form["name"].strip()
        email = request.form["email"].strip().lower()
        pw = request.form["password"]
        role = request.form.get("role", "student")
        if role not in ("student", "organizer"):
            role = "student"

        if len(pw) < 4:
            flash("Password must be at least 4 characters.", "danger")
            return redirect(url_for("signup"))

        conn = db.get_db()
        if conn.execute("SELECT 1 FROM users WHERE email=?", (email,)).fetchone():
            flash("An account with that email already exists.", "danger")
            conn.close()
            return redirect(url_for("signup"))
        conn.execute(
            "INSERT INTO users (name,email,password_hash,role,created_at) VALUES (?,?,?,?,?)",
            (name, email, generate_password_hash(pw), role, datetime.now().isoformat(timespec="seconds")),
        )
        conn.commit()
        user = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        conn.close()
        session["user_id"] = user["id"]
        flash(f"Welcome, {name}! Your account has been created.", "success")
        return redirect(url_for("index"))
    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        pw = request.form["password"]
        conn = db.get_db()
        user = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        conn.close()
        if user and check_password_hash(user["password_hash"], pw):
            session["user_id"] = user["id"]
            flash(f"Welcome back, {user['name']}!", "success")
            dest = request.args.get("next")
            if dest:
                return redirect(dest)
            if user["role"] == "admin":
                return redirect(url_for("admin_dashboard"))
            if user["role"] == "organizer":
                return redirect(url_for("organizer_dashboard"))
            return redirect(url_for("student_dashboard"))
        flash("Invalid email or password.", "danger")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You've been logged out.", "info")
    return redirect(url_for("index"))


# ------------------------------------------------------------------ student --
@app.route("/dashboard")
@login_required(role="student")
def student_dashboard():
    user = current_user()
    conn = db.get_db()
    regs = conn.execute(
        "SELECT r.*, e.title, e.venue, e.start_time, e.end_time, e.banner_emoji, e.status AS event_status "
        "FROM registrations r JOIN events e ON e.id=r.event_id "
        "WHERE r.user_id=? ORDER BY e.start_time ASC", (user["id"],)
    ).fetchall()
    conn.close()
    return render_template("student_dashboard.html", regs=regs)


@app.route("/ticket/<ticket_code>")
@login_required()
def view_ticket(ticket_code):
    user = current_user()
    conn = db.get_db()
    reg = conn.execute(
        "SELECT r.*, e.title, e.venue, e.start_time, e.end_time, e.banner_emoji FROM registrations r "
        "JOIN events e ON e.id=r.event_id WHERE r.ticket_code=?", (ticket_code,)
    ).fetchone()
    conn.close()
    if not reg or (reg["user_id"] != user["id"] and user["role"] != "admin"):
        abort(404)
    return render_template("ticket.html", reg=reg)


# ---------------------------------------------------------------- organizer --
@app.route("/organizer")
@login_required(role="organizer")
def organizer_dashboard():
    user = current_user()
    conn = db.get_db()
    events = conn.execute(
        "SELECT e.*, (SELECT COUNT(*) FROM registrations r WHERE r.event_id=e.id AND r.status IN ('confirmed','pending','attended')) AS regs "
        "FROM events e WHERE e.organizer_id=? ORDER BY e.created_at DESC", (user["id"],)
    ).fetchall()
    conn.close()
    return render_template("organizer_dashboard.html", events=events)


@app.route("/organizer/event/new", methods=["GET", "POST"])
@login_required(role="organizer")
def event_new():
    if request.method == "POST":
        user = current_user()
        conn = db.get_db()
        conn.execute(
            """INSERT INTO events (title,description,category,venue,start_time,end_time,capacity,
               requires_approval,banner_emoji,organizer_id,status,created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?, 'pending', ?)""",
            (
                request.form["title"], request.form["description"], request.form["category"],
                request.form["venue"], request.form["start_time"], request.form["end_time"],
                int(request.form["capacity"]), 1 if request.form.get("requires_approval") else 0,
                request.form.get("banner_emoji") or "🎉", user["id"],
                datetime.now().isoformat(timespec="seconds"),
            ),
        )
        conn.commit()
        conn.close()
        flash("Event submitted! It will appear publicly once an admin approves it.", "success")
        return redirect(url_for("organizer_dashboard"))
    return render_template("event_form.html", event=None)


def _get_owned_event(event_id, user):
    conn = db.get_db()
    event = conn.execute("SELECT * FROM events WHERE id=?", (event_id,)).fetchone()
    conn.close()
    if not event:
        abort(404)
    if event["organizer_id"] != user["id"] and user["role"] != "admin":
        abort(403)
    return event


@app.route("/organizer/event/<int:event_id>/edit", methods=["GET", "POST"])
@login_required(role="organizer")
def event_edit(event_id):
    user = current_user()
    event = _get_owned_event(event_id, user)
    conn = db.get_db()
    if request.method == "POST":
        conn.execute(
            """UPDATE events SET title=?, description=?, category=?, venue=?, start_time=?, end_time=?,
               capacity=?, requires_approval=?, banner_emoji=?, status='pending', admin_note=''
               WHERE id=?""",
            (
                request.form["title"], request.form["description"], request.form["category"],
                request.form["venue"], request.form["start_time"], request.form["end_time"],
                int(request.form["capacity"]), 1 if request.form.get("requires_approval") else 0,
                request.form.get("banner_emoji") or "🎉", event_id,
            ),
        )
        conn.commit()
        conn.close()
        flash("Event updated and re-submitted for admin approval.", "success")
        return redirect(url_for("organizer_dashboard"))
    conn.close()
    return render_template("event_form.html", event=event)


@app.route("/organizer/event/<int:event_id>/schedule", methods=["GET", "POST"])
@login_required(role="organizer")
def manage_schedule(event_id):
    user = current_user()
    event = _get_owned_event(event_id, user)
    conn = db.get_db()
    if request.method == "POST":
        conn.execute(
            "INSERT INTO schedule_items (event_id,title,start_time,end_time,speaker,location) VALUES (?,?,?,?,?,?)",
            (event_id, request.form["title"], request.form["start_time"], request.form["end_time"],
             request.form.get("speaker", ""), request.form.get("location", "")),
        )
        conn.commit()
        flash("Schedule item added.", "success")
    items = conn.execute("SELECT * FROM schedule_items WHERE event_id=? ORDER BY start_time ASC", (event_id,)).fetchall()
    conn.close()
    return render_template("schedule_manage.html", event=event, items=items)


@app.route("/organizer/schedule/<int:item_id>/delete", methods=["POST"])
@login_required(role="organizer")
def delete_schedule_item(item_id):
    conn = db.get_db()
    item = conn.execute("SELECT * FROM schedule_items WHERE id=?", (item_id,)).fetchone()
    if not item:
        conn.close()
        abort(404)
    event = _get_owned_event(item["event_id"], current_user())
    conn.execute("DELETE FROM schedule_items WHERE id=?", (item_id,))
    conn.commit()
    conn.close()
    flash("Schedule item removed.", "info")
    return redirect(url_for("manage_schedule", event_id=event["id"]))


@app.route("/organizer/event/<int:event_id>/sponsors", methods=["GET", "POST"])
@login_required(role="organizer")
def manage_sponsors(event_id):
    user = current_user()
    event = _get_owned_event(event_id, user)
    conn = db.get_db()
    if request.method == "POST":
        conn.execute(
            "INSERT INTO sponsors (event_id,name,tier,website,description) VALUES (?,?,?,?,?)",
            (event_id, request.form["name"], request.form["tier"], request.form.get("website", ""),
             request.form.get("description", "")),
        )
        conn.commit()
        flash("Sponsor added.", "success")
    sponsors = conn.execute("SELECT * FROM sponsors WHERE event_id=?", (event_id,)).fetchall()
    conn.close()
    return render_template("sponsors_manage.html", event=event, sponsors=sponsors)


@app.route("/organizer/sponsor/<int:sponsor_id>/delete", methods=["POST"])
@login_required(role="organizer")
def delete_sponsor(sponsor_id):
    conn = db.get_db()
    sponsor = conn.execute("SELECT * FROM sponsors WHERE id=?", (sponsor_id,)).fetchone()
    if not sponsor:
        conn.close()
        abort(404)
    event = _get_owned_event(sponsor["event_id"], current_user())
    conn.execute("DELETE FROM sponsors WHERE id=?", (sponsor_id,))
    conn.commit()
    conn.close()
    flash("Sponsor removed.", "info")
    return redirect(url_for("manage_sponsors", event_id=event["id"]))


@app.route("/organizer/event/<int:event_id>/registrations")
@login_required(role="organizer")
def organizer_view_registrations(event_id):
    user = current_user()
    event = _get_owned_event(event_id, user)
    conn = db.get_db()
    regs = conn.execute(
        "SELECT r.*, u.name AS student_name, u.email AS student_email FROM registrations r "
        "JOIN users u ON u.id=r.user_id WHERE r.event_id=? ORDER BY r.registered_at ASC", (event_id,)
    ).fetchall()
    conn.close()
    return render_template("admin/registrations.html", event=event, regs=regs, back_url=url_for("organizer_dashboard"))


# -------------------------------------------------------------------- admin --
@app.route("/admin")
@login_required(role="admin")
def admin_dashboard():
    conn = db.get_db()
    stats = {
        "pending_events": conn.execute("SELECT COUNT(*) c FROM events WHERE status='pending'").fetchone()["c"],
        "approved_events": conn.execute("SELECT COUNT(*) c FROM events WHERE status='approved'").fetchone()["c"],
        "pending_regs": conn.execute("SELECT COUNT(*) c FROM registrations WHERE status='pending'").fetchone()["c"],
        "total_students": conn.execute("SELECT COUNT(*) c FROM users WHERE role='student'").fetchone()["c"],
        "total_tickets": conn.execute("SELECT COUNT(*) c FROM registrations WHERE status IN ('confirmed','attended')").fetchone()["c"],
        "total_organizers": conn.execute("SELECT COUNT(*) c FROM users WHERE role='organizer'").fetchone()["c"],
    }
    recent_events = conn.execute(
        "SELECT e.*, u.name AS organizer_name FROM events e JOIN users u ON u.id=e.organizer_id ORDER BY e.created_at DESC LIMIT 6"
    ).fetchall()
    conn.close()
    return render_template("admin/dashboard.html", stats=stats, recent_events=recent_events)


@app.route("/admin/events")
@login_required(role="admin")
def admin_events():
    status = request.args.get("status", "pending")
    conn = db.get_db()
    if status == "all":
        events = conn.execute(
            "SELECT e.*, u.name AS organizer_name FROM events e JOIN users u ON u.id=e.organizer_id ORDER BY e.created_at DESC"
        ).fetchall()
    else:
        events = conn.execute(
            "SELECT e.*, u.name AS organizer_name FROM events e JOIN users u ON u.id=e.organizer_id WHERE e.status=? ORDER BY e.created_at DESC",
            (status,),
        ).fetchall()
    conn.close()
    return render_template("admin/events.html", events=events, active_status=status)


@app.route("/admin/event/<int:event_id>/decide", methods=["POST"])
@login_required(role="admin")
def admin_decide_event(event_id):
    decision = request.form["decision"]
    note = request.form.get("admin_note", "")
    status = "approved" if decision == "approve" else "rejected"
    conn = db.get_db()
    conn.execute("UPDATE events SET status=?, admin_note=? WHERE id=?", (status, note, event_id))
    conn.commit()
    conn.close()
    flash(f"Event {status}.", "success" if status == "approved" else "info")
    return redirect(url_for("admin_events", status="pending"))


@app.route("/admin/event/<int:event_id>/schedule", methods=["GET", "POST"])
@login_required(role="admin")
def admin_manage_schedule(event_id):
    return manage_schedule(event_id)


@app.route("/admin/event/<int:event_id>/sponsors", methods=["GET", "POST"])
@login_required(role="admin")
def admin_manage_sponsors(event_id):
    return manage_sponsors(event_id)


@app.route("/admin/registrations")
@login_required(role="admin")
def admin_registrations():
    status = request.args.get("status", "pending")
    conn = db.get_db()
    if status == "all":
        regs = conn.execute(
            "SELECT r.*, u.name AS student_name, u.email AS student_email, e.title FROM registrations r "
            "JOIN users u ON u.id=r.user_id JOIN events e ON e.id=r.event_id ORDER BY r.registered_at DESC"
        ).fetchall()
    else:
        regs = conn.execute(
            "SELECT r.*, u.name AS student_name, u.email AS student_email, e.title FROM registrations r "
            "JOIN users u ON u.id=r.user_id JOIN events e ON e.id=r.event_id WHERE r.status=? ORDER BY r.registered_at DESC",
            (status,),
        ).fetchall()
    conn.close()
    return render_template("admin/all_registrations.html", regs=regs, active_status=status)


@app.route("/admin/registration/<int:reg_id>/decide", methods=["POST"])
@login_required(role="admin")
def admin_decide_registration(reg_id):
    decision = request.form["decision"]
    status = {"approve": "confirmed", "reject": "rejected", "attended": "attended"}.get(decision, "confirmed")
    conn = db.get_db()
    conn.execute("UPDATE registrations SET status=? WHERE id=?", (status, reg_id))
    conn.commit()
    conn.close()
    flash(f"Registration marked {status}.", "success")
    return redirect(request.referrer or url_for("admin_registrations"))


@app.route("/api/event/<int:event_id>/seats")
def api_event_seats(event_id):
    """AJAX endpoint for real-time seat availability."""
    conn = db.get_db()
    event = conn.execute("SELECT capacity FROM events WHERE id=? AND status='approved'", (event_id,)).fetchone()
    if not event:
        conn.close()
        return jsonify({"error": "Event not found"}), 404
    taken = conn.execute(
        "SELECT COUNT(*) c FROM registrations WHERE event_id=? AND status IN ('confirmed','pending')", (event_id,)
    ).fetchone()["c"]
    conn.close()
    return jsonify({"capacity": event["capacity"], "taken": taken, "available": max(0, event["capacity"] - taken)})


if __name__ == "__main__":
    app.run(debug=True, port=5000)
