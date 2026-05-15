import sqlite3
import uuid
from datetime import datetime
from flask import Flask, request, redirect, render_template_string, g

app = Flask(__name__)
DATABASE = "database.db"

# ─── DB Helper ───────────────────────────────────────────

def get_db():
    db = getattr(g, "_database", None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, "_database", None)
    if db is not None:
        db.close()

def init_db():
    with sqlite3.connect(DATABASE) as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT UNIQUE NOT NULL,
                original_url TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                link_code TEXT NOT NULL,
                ip TEXT,
                user_agent TEXT,
                referer TEXT,
                lang TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

# ─── HTML Templates (inline biar simple) ─────────────────

HOME_HTML = """
<!doctype html>
<html>
<head><title>Link Tracker</title>
<style>
  body{font-family:Arial;max-width:600px;margin:50px auto;padding:20px;background:#111;color:#0f0}
  input,button{width:100%;padding:12px;margin:8px 0;border:none;border-radius:6px}
  button{background:#0f0;color:#000;font-weight:bold;cursor:pointer}
  .result{background:#222;padding:15px;border-radius:8px;margin-top:15px}
  .result a{color:#0f0;word-break:break-all}
  h2{color:#0f0}
</style>
</head>
<body>
  <h2>🔗 Buat Link Tracking</h2>
  <form method="POST" action="/create">
    <input type="url" name="url" placeholder="Paste link asli di sini (TikTok, dll)" required>
    <button type="submit">Generate Link</button>
  </form>
  {% if track_url %}
  <div class="result">
    <p><b>Link Tracking:</b></p>
    <a href="{{ track_url }}" target="_blank">{{ track_url }}</a>
    <p style="font-size:12px;color:#888;margin-top:10px">
      Copy link di atas & kirim ke target. Kalau dia klik, data-nya bakal ke-log.
    </p>
    <p><a href="/admin" style="color:#fff">📊 Lihat Hasil Tracking</a></p>
  </div>
  {% endif %}
</body>
</html>
"""

ADMIN_HTML = """
<!doctype html>
<html>
<head><title>Hasil Tracking</title>
<style>
  body{font-family:Arial;max-width:900px;margin:30px auto;padding:20px;background:#111;color:#0f0}
  table{width:100%;border-collapse:collapse;font-size:13px}
  th,td{border:1px solid #333;padding:10px;text-align:left}
  th{background:#222}
  tr:nth-child(even){background:#1a1a1a}
  a{color:#0f0}
  .back{color:#fff}
</style>
</head>
<body>
  <h2>📊 Hasil Tracking</h2>
  <a href="/" class="back">← Kembali</a>
  <table style="margin-top:20px">
    <tr>
      <th>Waktu</th>
      <th>Link Code</th>
      <th>IP Address</th>
      <th>User Agent</th>
      <th>Referer</th>
      <th>Bahasa</th>
    </tr>
    {% for row in rows %}
    <tr>
      <td>{{ row.created_at }}</td>
      <td>{{ row.link_code }}</td>
      <td>{{ row.ip }}</td>
      <td>{{ row.user_agent }}</td>
      <td>{{ row.referer or '-' }}</td>
      <td>{{ row.lang or '-' }}</td>
    </tr>
    {% else %}
    <tr><td colspan="6" style="text-align:center;color:#888">Belum ada yang klik.</td></tr>
    {% endfor %}
  </table>
</body>
</html>
"""

# ─── Routes ──────────────────────────────────────────────

@app.route("/")
def index():
    return render_template_string(HOME_HTML)

@app.route("/create", methods=["POST"])
def create():
    original = request.form.get("url", "").strip()
    if not original:
        return "URL wajib diisi", 400

    code = uuid.uuid4().hex[:8]
    db = get_db()
    try:
        db.execute("INSERT INTO links (code, original_url) VALUES (?, ?)", (code, original))
        db.commit()
    except sqlite3.IntegrityError:
        return "Coba lagi", 500

    track_url = request.host_url.rstrip("/") + "/track/" + code
    return render_template_string(HOME_HTML, track_url=track_url)

@app.route("/track/<code>")
def track(code):
    db = get_db()
    link = db.execute("SELECT * FROM links WHERE code = ?", (code,)).fetchone()
    if not link:
        return "Link tidak ditemukan", 404

    ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    ua = request.headers.get("User-Agent", "")
    ref = request.headers.get("Referer", "")
    lang = request.headers.get("Accept-Language", "")

    db.execute(
        "INSERT INTO logs (link_code, ip, user_agent, referer, lang) VALUES (?, ?, ?, ?, ?)",
        (code, ip, ua, ref, lang),
    )
    db.commit()

    return redirect(link["original_url"])

@app.route("/admin")
def admin():
    db = get_db()
    rows = db.execute("SELECT * FROM logs ORDER BY created_at DESC").fetchall()
    return render_template_string(ADMIN_HTML, rows=rows)

# ─── Main ────────────────────────────────────────────────

if __name__ == "__main__":
    init_db()
    print("[+] Database initialized.")
    print("[+] Buka http://127.0.0.1:5000 di browser lo.")
    app.run(host="0.0.0.0", port=5000, debug=True)

# Untuk production (Render, dsb)
# Gunicorn akan import app langsung, jadi init_db harus dipanggil saat startup
init_db()
