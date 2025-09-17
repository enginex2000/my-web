from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file
import sqlite3, os
from datetime import datetime, timedelta
import openpyxl
from io import BytesIO

app = Flask(__name__)
app.secret_key = "your_secret_key"

DB_NAME = "database.db"
ADMIN_USER = "admin"
ADMIN_PASS = "esp1234"

# ------------------------- DB -------------------------
def init_db():
    if not os.path.exists(DB_NAME):
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS reservations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                times TEXT NOT NULL,
                courts TEXT NOT NULL,
                name TEXT NOT NULL,
                phone TEXT NOT NULL
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        # ค่า default maintenance = off
        cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('maintenance', 'off')")
        conn.commit()
        conn.close()

def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

# ------------------------- Maintenance -------------------------
def get_maintenance():
    conn = get_db_connection()
    row = conn.execute("SELECT value FROM settings WHERE key='maintenance'").fetchone()
    conn.close()
    return row and row["value"] == "on"

def set_maintenance(status: bool):
    conn = get_db_connection()
    conn.execute("UPDATE settings SET value=? WHERE key='maintenance'", ("on" if status else "off",))
    conn.commit()
    conn.close()

# ------------------------- User Booking -------------------------
def is_time_taken(times, courts):
    today = (datetime.utcnow() + timedelta(hours=7)).strftime("%Y-%m-%d")
    conn = get_db_connection()
    row = conn.execute(
        "SELECT * FROM reservations WHERE times=? AND courts=? AND DATE(created_at)=?",
        (times, courts, today)
    ).fetchone()
    conn.close()
    return row is not None

def insert_reservation(times, courts, name, phone):
    thai_now = datetime.utcnow() + timedelta(hours=7)
    conn = get_db_connection()
    conn.execute(
        "INSERT INTO reservations (created_at, times, courts, name, phone) VALUES (?, ?, ?, ?, ?)",
        (thai_now.strftime("%Y-%m-%d %H:%M:%S"), times, courts, name, phone)
    )
    conn.commit()
    conn.close()

@app.route('/')
def index():
    today = (datetime.utcnow() + timedelta(hours=7)).strftime("%Y-%m-%d")
    conn = get_db_connection()
    rows = conn.execute("SELECT times, courts FROM reservations WHERE DATE(created_at)=?", (today,)).fetchall()
    conn.close()

    booked_dict = {}
    for r in rows:
        court = r["courts"]  # ต้องตรงกับ <option value="C1"> หรือ "C2"
        time = r["times"]    # ต้องตรงกับ <option value="10.00">...
        if court not in booked_dict:
            booked_dict[court] = []
        booked_dict[court].append(time)

    maintenance_status = get_maintenance()
    return render_template("index.html",
                           booked_dict=booked_dict,
                           maintenance=maintenance_status)


@app.route('/process', methods=['POST'])
def process():
    # เช็คโหมดปรับปรุง
    if get_maintenance():
        flash("ระบบอยู่ระหว่างปรับปรุง ไม่สามารถจองได้ในขณะนี้", "error")
        return redirect(url_for('index'))

    courts = request.form.get("courts", "").strip()
    times_label = request.form.get("times", "").strip()
    name = request.form.get("name", "").strip()
    phone = request.form.get("phone", "").strip()

    if not courts or not times_label or not name or not phone:
        flash("กรุณากรอกข้อมูลให้ครบทุกช่อง!", "error")
        return redirect(url_for('index'))

    if not phone.isdigit() or len(phone) != 10:
        flash("เบอร์โทรต้องเป็นตัวเลข 10 หลัก!", "error")
        return redirect(url_for('index'))

    time_value_map = {
        "10.00-12.00": "10.00",
        "12.00-14.00": "12.00",
        "14.00-16.00": "14.00",
        "16.00-18.00": "16.00",
        "18.00-20.00": "18.00",
        "20.00-22.00": "20.00"
    }
    times_value = time_value_map.get(times_label, times_label)

    if is_time_taken(times_value, courts):
        flash(f"ช่วงเวลา {times_label} สนาม {courts} มีคนจองแล้ว", "error")
        return redirect(url_for('index'))

    insert_reservation(times_value, courts, name, phone)
    flash(f"บันทึกเรียบร้อย! {courts} เวลา {times_label} ชื่อ {name} เบอร์ {phone}", "success")
    return redirect(url_for('index'))

# ------------------------- Admin -------------------------
@app.route("/admin/login", methods=["GET","POST"])
def admin_login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        if username == ADMIN_USER and password == ADMIN_PASS:
            session["admin"] = True
            return redirect(url_for("admin_panel"))
        else:
            flash("รหัสไม่ถูกต้อง", "error")
    return render_template("admin_login.html")

@app.route("/admin/logout")
def admin_logout():
    session.pop("admin", None)
    flash("ออกจากระบบเรียบร้อย", "success")
    return redirect(url_for("admin_login"))

@app.route("/admin", methods=["GET", "POST"])
def admin_panel():
    if "admin" not in session:
        return redirect(url_for("admin_login"))

    selected_date = (datetime.utcnow() + timedelta(hours=7)).strftime("%Y-%m-%d")
    show_all = False

    if request.method == "POST":
        selected_date = request.form.get("date", selected_date)
        show_all = request.form.get("show_all") is not None

    conn = get_db_connection()
    if show_all:
        reservations = conn.execute("SELECT * FROM reservations ORDER BY created_at DESC").fetchall()
    else:
        reservations = conn.execute(
            "SELECT * FROM reservations WHERE DATE(created_at)=? ORDER BY created_at DESC",
            (selected_date,)
        ).fetchall()
    conn.close()

    return render_template("admin_panel.html",
                           reservations=reservations,
                           selected_date=selected_date,
                           show_all=show_all,
                           maintenance=get_maintenance())

@app.route("/admin/reset", methods=["POST"])
def reset_data():
    if "admin" not in session:
        return redirect(url_for("admin_login"))

    date = request.form.get("date")
    password = request.form.get("password")

    if password != ADMIN_PASS:
        flash("รหัสผ่านไม่ถูกต้อง!", "error")
        conn = get_db_connection()
        reservations = conn.execute(
            "SELECT * FROM reservations WHERE DATE(created_at)=? ORDER BY created_at DESC",
            (date,)
        ).fetchall()
        conn.close()
        return render_template("admin_panel.html",
                               reservations=reservations,
                               selected_date=date,
                               show_all=False,
                               maintenance=get_maintenance())

    conn = get_db_connection()
    conn.execute("DELETE FROM reservations WHERE DATE(created_at)=?", (date,))
    conn.commit()
    conn.close()
    flash(f"รีเซ็ตข้อมูลวันที่ {date} สำเร็จ!", "success")
    return redirect(url_for("admin_panel"))

@app.route("/admin/export")
def export_excel():
    if "admin" not in session:
        return redirect(url_for("admin_login"))

    conn = get_db_connection()
    reservations = conn.execute("SELECT * FROM reservations ORDER BY created_at DESC").fetchall()
    conn.close()

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Reservations"
    ws.append(["ID","Created At","Time","Court","Name","Phone"])
    for r in reservations:
        ws.append([r["id"], r["created_at"], r["times"], r["courts"], r["name"], r["phone"]])

    output = BytesIO()
    wb.save(output)
    output.seek(0)
    filename = f"reservations_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    return send_file(output, as_attachment=True, download_name=filename,
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

@app.route("/admin/toggle_maintenance", methods=["POST"])
def toggle_maintenance():
    if "admin" not in session:
        return redirect(url_for("admin_login"))
    current = get_maintenance()
    set_maintenance(not current)
    flash("เปิดโหมดปรับปรุงแล้ว" if not current else "ปิดโหมดปรับปรุงเรียบร้อย", "success")
    return redirect(url_for("admin_panel"))

# ------------------------- Main -------------------------
if __name__ == "__main__":
    init_db()
    app.run(debug=True)
