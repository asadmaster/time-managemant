from flask import Flask, request, jsonify, render_template
import sqlite3
import os
from datetime import datetime

app = Flask(__name__)
DB = os.path.join(os.path.dirname(__file__), "sempla.db")

# ── DB INIT ──────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS work_entries (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            work_name TEXT    NOT NULL,
            date      TEXT    NOT NULL,
            start_time TEXT   NOT NULL,
            end_time   TEXT   NOT NULL,
            duration_min INTEGER GENERATED ALWAYS AS (
                (CAST(substr(end_time,1,2) AS INTEGER)*60 + CAST(substr(end_time,4,2) AS INTEGER))
                - (CAST(substr(start_time,1,2) AS INTEGER)*60 + CAST(substr(start_time,4,2) AS INTEGER))
            ) VIRTUAL,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.commit()
    conn.close()

init_db()

# ── HELPERS ──────────────────────────────────────────────
def calc_duration(start, end):
    fmt = "%H:%M"
    try:
        s = datetime.strptime(start, fmt)
        e = datetime.strptime(end, fmt)
        diff = (e - s).seconds // 60
        return diff if diff >= 0 else 0
    except:
        return 0

# ── ROUTES ───────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html")

# CREATE
@app.route("/api/entries", methods=["POST"])
def create_entry():
    data = request.get_json()
    work_name  = data.get("work_name", "").strip()
    date       = data.get("date", "").strip()
    start_time = data.get("start_time", "").strip()
    end_time   = data.get("end_time", "").strip()

    if not all([work_name, date, start_time, end_time]):
        return jsonify({"error": "All fields are required."}), 400

    dur = calc_duration(start_time, end_time)
    if dur <= 0:
        return jsonify({"error": "End time must be after start time."}), 400

    conn = get_db()
    conn.execute(
        "INSERT INTO work_entries (work_name, date, start_time, end_time) VALUES (?,?,?,?)",
        (work_name, date, start_time, end_time)
    )
    conn.commit()
    conn.close()
    return jsonify({"message": "Entry created.", "duration": dur}), 201

# READ ALL (optional date filter)
@app.route("/api/entries", methods=["GET"])
def get_entries():
    date_filter = request.args.get("date", "")
    conn = get_db()
    if date_filter:
        rows = conn.execute(
            "SELECT * FROM work_entries WHERE date=? ORDER BY date, start_time",
            (date_filter,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM work_entries ORDER BY date DESC, start_time"
        ).fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        d["duration"] = calc_duration(r["start_time"], r["end_time"])
        result.append(d)
    return jsonify(result)

# UPDATE
@app.route("/api/entries/<int:entry_id>", methods=["PUT"])
def update_entry(entry_id):
    data = request.get_json()
    work_name  = data.get("work_name", "").strip()
    date       = data.get("date", "").strip()
    start_time = data.get("start_time", "").strip()
    end_time   = data.get("end_time", "").strip()

    if not all([work_name, date, start_time, end_time]):
        return jsonify({"error": "All fields are required."}), 400

    dur = calc_duration(start_time, end_time)
    if dur <= 0:
        return jsonify({"error": "End time must be after start time."}), 400

    conn = get_db()
    conn.execute(
        "UPDATE work_entries SET work_name=?, date=?, start_time=?, end_time=? WHERE id=?",
        (work_name, date, start_time, end_time, entry_id)
    )
    conn.commit()
    conn.close()
    return jsonify({"message": "Entry updated."})

# DELETE
@app.route("/api/entries/<int:entry_id>", methods=["DELETE"])
def delete_entry(entry_id):
    conn = get_db()
    conn.execute("DELETE FROM work_entries WHERE id=?", (entry_id,))
    conn.commit()
    conn.close()
    return jsonify({"message": "Entry deleted."})

# CHART DATA — minutes per day
@app.route("/api/chart", methods=["GET"])
def chart_data():
    conn = get_db()
    rows = conn.execute(
        """
        SELECT date, work_name,
               SUM(
                   (CAST(substr(end_time,1,2) AS INTEGER)*60 + CAST(substr(end_time,4,2) AS INTEGER))
                 - (CAST(substr(start_time,1,2) AS INTEGER)*60 + CAST(substr(start_time,4,2) AS INTEGER))
               ) AS total_min
        FROM work_entries
        GROUP BY date, work_name
        ORDER BY date
        """
    ).fetchall()
    conn.close()

    # pivot: {date: [{work_name, total_min}]}
    from collections import defaultdict
    data = defaultdict(list)
    for r in rows:
        data[r["date"]].append({"work_name": r["work_name"], "total_min": r["total_min"]})

    dates = sorted(data.keys())
    # unique work names
    all_works = []
    seen = set()
    for r in rows:
        if r["work_name"] not in seen:
            all_works.append(r["work_name"])
            seen.add(r["work_name"])

    return jsonify({"dates": dates, "works": all_works, "data": data})

if __name__ == "__main__":
    print("\n✅  Sempla is running → http://127.0.0.1:5000\n")
    app.run(debug=True, port=5000)
