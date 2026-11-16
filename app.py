import os
import sqlite3
import uuid
from flask import Flask, render_template, request, redirect, url_for, session
from werkzeug.utils import secure_filename
from functools import wraps

app = Flask(__name__)
app.secret_key = "euphoric-secret-2025-change-me"
ADMIN_PASSWORD = "euphoric2025"
UPLOAD_FOLDER = "static/uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
BOT_USERNAME = "euphoricshop_bot"

def db():
    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = db()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category TEXT NOT NULL,
        title TEXT NOT NULL,
        description TEXT,
        price INTEGER NOT NULL,
        color TEXT,
        image TEXT,
        images TEXT,
        sales INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS workshops (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        description TEXT,
        link TEXT,
        image TEXT,
        video TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS reviews (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        rating INTEGER NOT NULL,
        text TEXT,
        image TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    );
    """)
    defaults = {
        "banner_image": "", "bg_color": "#0a0a0a", 
        "accent_color": "#c9a96e", "site_title": "Искусство в каждой детали"
    }
    for k, v in defaults.items():
        conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v))
    conn.commit()
    conn.close()

init_db()

def get_settings():
    conn = db()
    rows = conn.execute("SELECT * FROM settings").fetchall()
    conn.close()
    return {r['key']: r['value'] for r in rows}

def login_required(f):
    @wraps(f)
    def wrapper(*a, **kw):
        if not session.get("admin"):
            return redirect(url_for("admin_login"))
        return f(*a, **kw)
    return wrapper

@app.context_processor
def inject_settings():
    return dict(site_settings=get_settings())

@app.route("/")
def index():
    conn = db()
    products = conn.execute("SELECT * FROM products ORDER BY id DESC").fetchall()
    conn.close()
    return render_template("index.html", products=products, bot=BOT_USERNAME)

@app.route("/product/<int:pid>")
def product(pid):
    conn = db()
    p = conn.execute("SELECT * FROM products WHERE id=?", (pid,)).fetchone()
    conn.close()
    if not p: return "Товар не найден", 404
    images_list = p['images'].split(',') if p['images'] else [p['image']]
    return render_template("product.html", p=p, images=images_list, bot=BOT_USERNAME)

@app.route("/workshops")
def workshops():
    conn = db()
    ws = conn.execute("SELECT * FROM workshops ORDER BY id DESC").fetchall()
    conn.close()
    return render_template("workshops.html", workshops=ws)

@app.route("/reviews", methods=["GET", "POST"])
def reviews():
    conn = db()
    if request.method == "POST":
        name = request.form["name"]
        rating = int(request.form["rating"])
        text = request.form["text"]
        img = ""
        f = request.files.get("image")
        if f and f.filename:
            img = f"{uuid.uuid4().hex}_{secure_filename(f.filename)}"
            f.save(os.path.join(UPLOAD_FOLDER, img))
        conn.execute("INSERT INTO reviews (name, rating, text, image) VALUES (?,?,?,?)", (name, rating, text, img))
        conn.commit()
        return redirect(url_for("reviews"))
    all_reviews = conn.execute("SELECT * FROM reviews ORDER BY id DESC").fetchall()
    conn.close()
    return render_template("reviews.html", reviews=all_reviews)

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        if request.form["password"] == ADMIN_PASSWORD:
            session["admin"] = True
            return redirect(url_for("admin"))
        return render_template("admin_login.html", error="Неверный пароль")
    return render_template("admin_login.html")

@app.route("/admin/logout")
def admin_logout():
    session.clear()
    return redirect(url_for("admin_login"))

@app.route("/admin")
@login_required
def admin():
    conn = db()
    products = conn.execute("SELECT * FROM products ORDER BY id DESC").fetchall()
    ws = conn.execute("SELECT * FROM workshops ORDER BY id DESC").fetchall()
    revs = conn.execute("SELECT * FROM reviews ORDER BY id DESC").fetchall()
    conn.close()
    return render_template("admin.html", products=products, workshops=ws, reviews=revs)

@app.route("/admin/settings", methods=["POST"])
@login_required
def save_settings():
    conn = db()
    for key in ["bg_color", "accent_color", "site_title"]:
        if key in request.form:
            conn.execute("UPDATE settings SET value=? WHERE key=?", (request.form[key], key))
    f = request.files.get("banner_image")
    if f and f.filename:
        img = f"{uuid.uuid4().hex}_{secure_filename(f.filename)}"
        f.save(os.path.join(UPLOAD_FOLDER, img))
        conn.execute("UPDATE settings SET value=? WHERE key='banner_image'", (img,))
    conn.commit(); conn.close()
    return redirect(url_for("admin"))

@app.route("/admin/product/add", methods=["POST"])
@login_required
def add_product():
    images = []
    files = request.files.getlist("images")
    for f in files:
        if f and f.filename:
            img = f"{uuid.uuid4().hex}_{secure_filename(f.filename)}"
            f.save(os.path.join(UPLOAD_FOLDER, img))
            images.append(img)
    img_str = ",".join(images) if images else ""
    main_img = images[0] if images else ""
    conn = db()
    conn.execute("INSERT INTO products (category,title,description,price,color,image,images) VALUES (?,?,?,?,?,?,?)",
                 (request.form["category"], request.form["title"],
                  request.form["description"], int(request.form["price"]), request.form["color"], main_img, img_str))
    conn.commit(); conn.close()
    return redirect(url_for("admin"))

@app.route("/admin/product/<int:pid>/delete", methods=["POST"])
@login_required
def delete_product(pid):
    conn = db(); conn.execute("DELETE FROM products WHERE id=?", (pid,))
    conn.commit(); conn.close()
    return redirect(url_for("admin"))

@app.route("/admin/product/<int:pid>/edit", methods=["POST"])
@login_required
def edit_product(pid):
    conn = db()
    conn.execute("UPDATE products SET category=?, title=?, description=?, price=?, color=? WHERE id=?",
                 (request.form["category"], request.form["title"],
                  request.form["description"], int(request.form["price"]), request.form["color"], pid))
    conn.commit(); conn.close()
    return redirect(url_for("admin"))

# (Остальные функции для мастер-классов и отзывов оставляем без изменений, они ниже в твоем файле)
@app.route("/admin/workshop/add", methods=["POST"])
@login_required
def add_workshop():
    img = ""
    f = request.files.get("image")
    if f and f.filename:
        img = f"{uuid.uuid4().hex}_{secure_filename(f.filename)}"
        f.save(os.path.join(UPLOAD_FOLDER, img))
    conn = db()
    conn.execute("INSERT INTO workshops (title,description,link,image,video) VALUES (?,?,?,?,?)",
                 (request.form["title"], request.form["description"], request.form["link"], img, request.form["video"]))
    conn.commit(); conn.close()
    return redirect(url_for("admin"))

@app.route("/admin/workshop/<int:wid>/delete", methods=["POST"])
@login_required
def delete_workshop(wid):
    conn = db(); conn.execute("DELETE FROM workshops WHERE id=?", (wid,))
    conn.commit(); conn.close()
    return redirect(url_for("admin"))

@app.route("/admin/review/<int:rid>/delete", methods=["POST"])
@login_required
def delete_review(rid):
    conn = db(); conn.execute("DELETE FROM reviews WHERE id=?", (rid,))
    conn.commit(); conn.close()
    return redirect(url_for("admin"))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
