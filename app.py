from __future__ import annotations

import csv
import io
import json
import os
import sqlite3
from datetime import date, datetime
from functools import wraps
from pathlib import Path

from flask import Flask, Response, flash, g, jsonify, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "tmart_mystery.db"

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-secret-key-in-production")

CRITERIA = [
    ("c1", "Packaging Quality & Integrity", 20),
    ("c2", "Delivery Time Compliance", 15),
    ("c3", "Packing Quality & Organization", 15),
    ("c4", "Taste / Flavor Quality", 15),
    ("c5", "Ingredient Verification", 10),
    ("c6", "Expiry Date Compliance", 15),
    ("c7", "Sensory Quality", 10),
]
CATEGORIES = ["Fruits & Vegetables", "Bakery", "Frozen Meat", "Frozen Chicken", "Frozen Fish", "Ice Cream", "Dry Food", "Cheese & Cold Cuts", "Fresh Meat", "Fresh Chicken"]
ITEM_TYPES = ["New Supplier Item (40%)", "Private Label – PL (35%)", "Other Category (25%)"]

STORES_RAW = '''DS01|talabat mart, New Maadi - Taqseem Laselky
DS02|talabat mart, Dokki - Mosaddak
DS03|talabat mart, El Rehab City
DS04|talabat mart, Zahraa El Maadi - El Me'arag El Ouloy
DS05|talabat mart, Mohandesin - Lebanon square
DS06|talabat mart, Mokattam - El Mafarik
DS07|talabat mart, Agouza
DS08|talabat mart, Nasr City - El Tayaran
DS09|talabat mart, Maadi Old
DS10|talabat mart, Heliopolis - Hegaz Square
DS11|talabat mart, Haram - Tersa
DS12|talabat mart, 6th of October - 4th District
DS13|talabat mart, Al-Manial
DS14|talabat mart, Helwan
DS15|talabat mart, Downtown - El Sayeda Zeinab
DS16|talabat mart, El Daher
DS17|talabat mart, Ard El Golf
DS18|talabat mart, Hadayek El Ahram
DS19|talabat mart, Tagammoa 5 - Banks Center
DS20|talabat mart, Tagamoa 5 - AUC
DS21|talabat mart, El Zaitoun - Al Gharbeya
DS22|talabat mart, El Sheikh Zayed - El Hay 9
DS23|talabat mart, Madinaty - Sporting Club
DS24|talabat mart, El Helw Street
DS25|talabat mart, El Magzar
DS26|talabat mart, Miami - Arab Academy
DS27|talabat mart, Ibrahimia
DS28|talabat mart, Shobra - El Sahel
DS29|talabat mart, El Shorouk - 1st Area
DS30|talabat mart, El Obour - El Hay 9
DS31|talabat mart, Matareya
DS32|talabat mart, Al Sharq District
DS33|talabat mart, Hay Thany Zagazig
DS34|talabat mart, Downtown - Champollion
DS35|talabat mart, El Weleideya
DS36|Tmart, 6th Of October - Palm Hills
DS37|talabat mart, Tagammoa 1
DS38|Tmart, Masaken El Nagda
DS39|Tmart, Madinaty - Work Shops
DS40|Talabat Mart, Nasr City - Hay 8
DS41|Tmart, Fleming - Koliyat Tarbya 2
DS42|Tmart, Haram - Talbiya 2
DS43|Tmart, Tagammoa 5 - Hay 1
DS44|Tmart, 6th of October - El Montzah
DS45|Tmart, Tagammoa 5 - Emaar Mivida
DS46|talabat mart, Mokattam - Easy Sport Club
DS47|Tmart, 6th of October - 6th District
DS48|Tmart, El Mokhtalat
DS49|talabat mart, Zahraa El Maadi - El Shatr El Sades
DS50|Tmart, Creek town Compound
DS51|EG Shrouk Mgawra (2)
DS52|EG Heliopolis Sheraton
DS53|EG Sheikh Zayed (2)
DS54|EG Faisal Maryoteya (2)
DS55|EG Tagamoa El Banafseg
DS56|EG Rock Vera Mall
DS57|EG El Obour Industrial Area
DS58|EG October Festival City
DS59|EG Nasr City (3)
DS60|EG Alexandria Smouha
DS61|EG New Damietta
DS62|EG Alex Moharam BK
DS63|talabat mart, Nasr City - Masaken El Shorouk
DS64|talabat mart, Tagammoa 5 - South Investors
DS65|EG Suez
DS66|EG Palm Hills (2)
DS67|talabat mart, Agamy - Hanuvile
DS68|EG Alex Elmontazah
DS69|EG Tagamoa 1 Toya Mall
DS70|EG Tagamoa 5 El Loutus
DS71|talabat mart, Mokattam - El Nafora Square
DS72|EG Nasr 5
DS73|EG Shrouk (3)
DS74|EG 10th Of Ramadan
DS75|EG Sheben Elkom'''

DEFAULT_USERS = [
    ("admin", "Mohamed Salah Ibrahim", "admin", "Admin@2024", "Quality Manager"),
    ("mark", "Mark", "auditor", "Mark@2024", "New Suppliers & Items"),
    ("yara", "Yara", "auditor", "Yara@2024", "New Suppliers & Items"),
    ("alia", "Alia", "auditor", "Alia@2024", "PL Items"),
    ("bassant", "Bassant", "auditor", "Bassant@2024", "PL Items"),
    ("abdelnasser", "Abdel Nasser", "auditor", "ANasser@2024", "PL Items"),
    ("mojahed", "Mojahed", "auditor", "Mojahed@2024", "Other Categories"),
    ("abdelmaged", "Abdel Maged", "auditor", "AMaged@2024", "Other Categories"),
]

def get_db() -> sqlite3.Connection:
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(_=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()

def init_db():
    db = sqlite3.connect(DB_PATH)
    cur = db.cursor()
    cur.executescript('''
    CREATE TABLE IF NOT EXISTS users (
      id TEXT PRIMARY KEY,
      name TEXT NOT NULL,
      role TEXT NOT NULL CHECK(role IN ('admin','auditor')),
      password_hash TEXT NOT NULL,
      focus TEXT DEFAULT '',
      is_active INTEGER NOT NULL DEFAULT 1,
      created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS stores (
      code TEXT PRIMARY KEY,
      name TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS audits (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      auditor_id TEXT NOT NULL,
      store_code TEXT NOT NULL,
      category TEXT NOT NULL,
      item_type TEXT DEFAULT '',
      audit_date TEXT NOT NULL,
      audit_time TEXT NOT NULL,
      product_name TEXT NOT NULL,
      brand TEXT DEFAULT '',
      supplier TEXT DEFAULT '',
      criteria_json TEXT NOT NULL,
      availability_pct REAL DEFAULT 0,
      stock_status TEXT DEFAULT '',
      critical_available TEXT DEFAULT '',
      availability_notes TEXT DEFAULT '',
      quality_score INTEGER NOT NULL,
      availability_score INTEGER NOT NULL,
      total_score INTEGER NOT NULL,
      rating TEXT NOT NULL,
      notes TEXT DEFAULT '',
      status TEXT DEFAULT 'submitted',
      created_at TEXT NOT NULL,
      FOREIGN KEY(auditor_id) REFERENCES users(id),
      FOREIGN KEY(store_code) REFERENCES stores(code)
    );
    CREATE TABLE IF NOT EXISTS issues (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      description TEXT NOT NULL,
      store_code TEXT NOT NULL,
      category TEXT DEFAULT '',
      issue_date TEXT NOT NULL,
      status TEXT NOT NULL DEFAULT 'open',
      severity TEXT NOT NULL DEFAULT 'medium',
      assigned_to TEXT DEFAULT '',
      action_taken TEXT DEFAULT '',
      created_at TEXT NOT NULL,
      FOREIGN KEY(store_code) REFERENCES stores(code)
    );
    ''')
    if cur.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
        now = datetime.now().isoformat(timespec="seconds")
        for uid, name, role, pw, focus in DEFAULT_USERS:
            cur.execute("INSERT INTO users VALUES (?,?,?,?,?,?,?)", (uid, name, role, generate_password_hash(pw), focus, 1, now))
    if cur.execute("SELECT COUNT(*) FROM stores").fetchone()[0] == 0:
        for line in STORES_RAW.splitlines():
            code, name = line.split('|', 1)
            cur.execute("INSERT INTO stores VALUES (?,?)", (code.strip(), name.strip()))
    if cur.execute("SELECT COUNT(*) FROM issues").fetchone()[0] == 0:
        samples = [
            ("Packaging integrity failure – chicken breast delivery", "DS08", "Fresh Chicken", "open", "high", "Mark"),
            ("Expiry date less than 24 hours on dairy products", "DS03", "Cheese & Cold Cuts", "in-progress", "high", "Alia"),
            ("Frozen items partially thawed upon delivery", "DS32", "Frozen Meat", "open", "critical", "Mojahed"),
        ]
        now = datetime.now().isoformat(timespec="seconds")
        for desc, store, cat, status, sev, assignee in samples:
            cur.execute("INSERT INTO issues(description,store_code,category,issue_date,status,severity,assigned_to,created_at) VALUES (?,?,?,?,?,?,?,?)", (desc, store, cat, str(date.today()), status, sev, assignee, now))
    db.commit(); db.close()

def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapper

def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if session.get("role") != "admin":
            flash("Admin access only.", "error")
            return redirect(url_for("index"))
        return fn(*args, **kwargs)
    return wrapper

def row_to_dict(r): return dict(r) if r else None

def current_user():
    if not session.get("user_id"): return None
    return row_to_dict(get_db().execute("SELECT id,name,role,focus FROM users WHERE id=?", (session["user_id"],)).fetchone())

def calc_score(criteria: dict, avail_pct: float, critical_available: str, stock_status: str):
    earned = possible = 0
    for cid, _name, weight in CRITERIA:
        val = criteria.get(cid, "na")
        if val != "na":
            possible += weight
            if val == "pass": earned += weight
    q_score = round((earned / possible) * 100) if possible else 0
    avail_score = round((float(avail_pct or 0) / 100) * 10)
    if critical_available == "yes": avail_score += 3
    if stock_status == "in-stock": avail_score += 2
    avail_score = min(15, avail_score)
    total = round(q_score * 0.85 + (avail_score / 15 * 100) * 0.15)
    return q_score, avail_score, total, rating(total)

def rating(score: int):
    if score >= 90: return "EXCELLENT"
    if score >= 80: return "VERY GOOD"
    if score >= 70: return "GOOD"
    if score >= 60: return "FAIR"
    return "POOR"

def get_dashboard_stats():
    db = get_db()
    audits = db.execute("SELECT * FROM audits").fetchall()
    issues = db.execute("SELECT * FROM issues").fetchall()
    total = len(audits)
    avg = round(sum(a["total_score"] for a in audits) / total) if total else 0
    return {"total": total, "avg": avg, "passed": len([a for a in audits if a["total_score"] >= 70]), "critical": len([a for a in audits if a["total_score"] < 60]), "open_issues": len([i for i in issues if i["status"] == "open"]), "avg_availability": round(sum(float(a["availability_pct"] or 0) for a in audits) / total) if total else 0}

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        uid = request.form.get("username", "").strip().lower()
        pw = request.form.get("password", "")
        user = get_db().execute("SELECT * FROM users WHERE id=? AND is_active=1", (uid,)).fetchone()
        if user and check_password_hash(user["password_hash"], pw):
            session.clear(); session["user_id"] = user["id"]; session["role"] = user["role"]
            return redirect(url_for("index"))
        flash("Incorrect username or password.", "error")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear(); return redirect(url_for("login"))

@app.route("/")
@login_required
def index():
    u = current_user()
    db = get_db()
    stores = [dict(x) for x in db.execute("SELECT * FROM stores ORDER BY code").fetchall()]
    users = [dict(x) for x in db.execute("SELECT id,name,role,focus,is_active FROM users ORDER BY role,name").fetchall()]
    return render_template("app.html", user=u, stats=get_dashboard_stats(), stores=stores, users=users, categories=CATEGORIES, item_types=ITEM_TYPES, criteria=CRITERIA)

@app.route("/audits")
@login_required
def audits():
    db = get_db()
    q = '''SELECT a.*, u.name auditor_name, s.name store_name FROM audits a JOIN users u ON u.id=a.auditor_id JOIN stores s ON s.code=a.store_code'''
    args = []
    if session["role"] != "admin":
        q += " WHERE a.auditor_id=?"; args.append(session["user_id"])
    q += " ORDER BY a.id DESC"
    rows = [dict(x) for x in db.execute(q, args).fetchall()]
    return render_template("audits.html", audits=rows, user=current_user())

@app.route("/audit/new", methods=["GET", "POST"])
@login_required
def audit_new():
    db = get_db()
    if request.method == "POST":
        f = request.form
        criteria = {cid: f.get(cid, "na") for cid,_,_ in CRITERIA}
        q, avs, total, rt = calc_score(criteria, float(f.get("availability_pct") or 0), f.get("critical_available", "no"), f.get("stock_status", ""))
        auditor_id = f.get("auditor_id") if session["role"] == "admin" else session["user_id"]
        db.execute('''INSERT INTO audits(auditor_id,store_code,category,item_type,audit_date,audit_time,product_name,brand,supplier,criteria_json,availability_pct,stock_status,critical_available,availability_notes,quality_score,availability_score,total_score,rating,notes,status,created_at)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', (auditor_id, f["store_code"], f["category"], f.get("item_type",""), f.get("audit_date") or str(date.today()), f.get("audit_time") or datetime.now().strftime("%H:%M"), f["product_name"], f.get("brand",""), f.get("supplier",""), json.dumps(criteria), float(f.get("availability_pct") or 0), f.get("stock_status",""), f.get("critical_available",""), f.get("availability_notes",""), q, avs, total, rt, f.get("notes",""), "submitted", datetime.now().isoformat(timespec="seconds")))
        db.commit(); flash("Audit submitted successfully.", "success"); return redirect(url_for("audits"))
    stores = db.execute("SELECT * FROM stores ORDER BY code").fetchall(); users = db.execute("SELECT id,name FROM users WHERE role='auditor' AND is_active=1 ORDER BY name").fetchall()
    return render_template("audit_form.html", stores=stores, users=users, categories=CATEGORIES, item_types=ITEM_TYPES, criteria=CRITERIA, audit=None, today=str(date.today()), now=datetime.now().strftime("%H:%M"))

@app.route("/audit/<int:audit_id>/delete", methods=["POST"])
@login_required
@admin_required
def audit_delete(audit_id):
    get_db().execute("DELETE FROM audits WHERE id=?", (audit_id,)); get_db().commit(); flash("Audit deleted.", "success"); return redirect(url_for("audits"))

@app.route("/issues")
@login_required
def issues():
    rows = get_db().execute('''SELECT i.*, s.name store_name FROM issues i JOIN stores s ON s.code=i.store_code ORDER BY i.id DESC''').fetchall()
    return render_template("issues.html", issues=rows)

@app.route("/issue/new", methods=["GET", "POST"])
@login_required
@admin_required
def issue_new():
    db = get_db()
    if request.method == "POST":
        f = request.form
        db.execute('''INSERT INTO issues(description,store_code,category,issue_date,status,severity,assigned_to,action_taken,created_at) VALUES(?,?,?,?,?,?,?,?,?)''', (f["description"], f["store_code"], f.get("category",""), f.get("issue_date") or str(date.today()), f.get("status","open"), f.get("severity","medium"), f.get("assigned_to",""), f.get("action_taken",""), datetime.now().isoformat(timespec="seconds")))
        db.commit(); flash("Issue added.", "success"); return redirect(url_for("issues"))
    return render_template("issue_form.html", stores=db.execute("SELECT * FROM stores ORDER BY code").fetchall(), users=db.execute("SELECT id,name FROM users ORDER BY name").fetchall(), categories=CATEGORIES, today=str(date.today()))

@app.route("/issue/<int:issue_id>/delete", methods=["POST"])
@login_required
@admin_required
def issue_delete(issue_id):
    get_db().execute("DELETE FROM issues WHERE id=?", (issue_id,)); get_db().commit(); flash("Issue deleted.", "success"); return redirect(url_for("issues"))

@app.route("/users")
@login_required
@admin_required
def users():
    rows = get_db().execute("SELECT id,name,role,focus,is_active,created_at FROM users ORDER BY role,name").fetchall()
    return render_template("users.html", users=rows)

@app.route("/user/new", methods=["GET", "POST"])
@login_required
@admin_required
def user_new():
    if request.method == "POST":
        f = request.form
        get_db().execute("INSERT INTO users(id,name,role,password_hash,focus,is_active,created_at) VALUES(?,?,?,?,?,?,?)", (f["id"].strip().lower(), f["name"], f["role"], generate_password_hash(f["password"]), f.get("focus",""), 1, datetime.now().isoformat(timespec="seconds")))
        get_db().commit(); flash("User created.", "success"); return redirect(url_for("users"))
    return render_template("user_form.html")

@app.route("/user/<uid>/delete", methods=["POST"])
@login_required
@admin_required
def user_delete(uid):
    if uid == session["user_id"]:
        flash("You cannot delete your current account.", "error")
    else:
        get_db().execute("DELETE FROM users WHERE id=?", (uid,)); get_db().commit(); flash("User deleted.", "success")
    return redirect(url_for("users"))

@app.route("/stores")
@login_required
def stores():
    rows = get_db().execute("SELECT * FROM stores ORDER BY code").fetchall()
    return render_template("stores.html", stores=rows)

@app.route("/reports")
@login_required
@admin_required
def reports():
    return render_template("reports.html")

@app.route("/export/<kind>")
@login_required
@admin_required
def export_csv(kind):
    db = get_db()
    tables = {"audits":"audits", "issues":"issues", "users":"users"}
    if kind not in tables: return "Not found", 404
    rows = db.execute(f"SELECT * FROM {tables[kind]}").fetchall()
    out = io.StringIO(); writer = csv.writer(out)
    if rows:
        writer.writerow(rows[0].keys())
        for r in rows: writer.writerow([r[k] for k in r.keys()])
    return Response(out.getvalue(), mimetype="text/csv", headers={"Content-Disposition": f"attachment; filename={kind}.csv"})

@app.route("/api/dashboard")
@login_required
def api_dashboard():
    db = get_db()
    rating_rows = db.execute("SELECT rating, COUNT(*) c FROM audits GROUP BY rating").fetchall()
    category_rows = db.execute("SELECT category, ROUND(AVG(total_score)) avg_score FROM audits GROUP BY category").fetchall()
    return jsonify({"stats": get_dashboard_stats(), "ratings": [dict(x) for x in rating_rows], "categories": [dict(x) for x in category_rows]})

if __name__ == "__main__":
    init_db()
    app.run(debug=True)
