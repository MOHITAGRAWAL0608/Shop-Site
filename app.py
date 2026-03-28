"""
app.py - Main Flask application for the Shop Website Generator MVP
Handles routing, form processing, and site generation using Jinja2 templates.
Auth system: signup / login / logout via Flask sessions + werkzeug password hashing.
"""

from flask import Flask, render_template, request, redirect, url_for, abort, session, jsonify
import re
import urllib.parse
import mysql.connector
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps


# ---------------------------------------------------------------------------
# DB helper
# ---------------------------------------------------------------------------
def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="mohit_123",
        database="shopsite"
    )


app = Flask(__name__)
app.secret_key = "change-this-to-a-long-random-secret-in-production"

# ---------------------------------------------------------------------------
# YOUR WhatsApp number (with country code, no + or spaces)
# ---------------------------------------------------------------------------
WHATSAPP_NUMBER = "9302692535"   # ← Replace with your real number


# ---------------------------------------------------------------------------
# DB init
# ---------------------------------------------------------------------------
def init_mysql():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id         INT AUTO_INCREMENT PRIMARY KEY,
        username   VARCHAR(80)  NOT NULL UNIQUE,
        email      VARCHAR(120) NOT NULL UNIQUE,
        password   VARCHAR(255) NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS shops (
        slug      VARCHAR(255) PRIMARY KEY,
        shop_name TEXT,
        category  TEXT,
        description TEXT,
        products  TEXT,
        hours     TEXT,
        contact   TEXT,
        address   TEXT,
        user_id   INT NULL,
        CONSTRAINT fk_shops_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS contacts (
        id      INT AUTO_INCREMENT PRIMARY KEY,
        name    VARCHAR(120),
        email   VARCHAR(120),
        subject VARCHAR(255),
        message TEXT,
        sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    conn.commit()
    cursor.close()
    conn.close()


init_mysql()


# ---------------------------------------------------------------------------
# In-memory store
# ---------------------------------------------------------------------------
SHOPS = {}


# ---------------------------------------------------------------------------
# Auth decorator
# ---------------------------------------------------------------------------
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login", next=request.url))
        return f(*args, **kwargs)
    return decorated


# ---------------------------------------------------------------------------
# Slugify
# ---------------------------------------------------------------------------
def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text.strip("-")


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    return render_template("form.html", active_page="home")


@app.route("/about")
def about():
    return render_template("about.html", active_page="about")


@app.route("/contact")
def contact():
    return render_template("contact.html", active_page="contact")


@app.route("/submit-contact", methods=["POST"])
def submit_contact():
    name    = request.form.get("name")
    email   = request.form.get("email")
    subject = request.form.get("subject")
    message = request.form.get("message")

    if not name or not email or not message:
        return {"status": "error", "message": "Missing required fields"}

    try:
        conn   = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO contacts (name, email, subject, message) VALUES (%s, %s, %s, %s)",
            (name, email, subject, message)
        )
        conn.commit()
        cursor.close()
        conn.close()
        return {"status": "success"}
    except Exception as e:
        print("DB ERROR:", e)
        return {"status": "error"}


# ---------------------------------------------------------------------------
# AUTH — Signup
# ---------------------------------------------------------------------------
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if "user_id" in session:
        return redirect(url_for("index"))

    errors = []
    form_data = {}

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email    = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm  = request.form.get("confirm_password", "")

        form_data = {"username": username, "email": email}

        if not username or len(username) < 3:
            errors.append("Username must be at least 3 characters.")
        if not re.match(r"^[\w.-]+$", username or ""):
            errors.append("Username may only contain letters, numbers, dots, underscores, and hyphens.")
        if not email or not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
            errors.append("Enter a valid email address.")
        if not password or len(password) < 6:
            errors.append("Password must be at least 6 characters.")
        if password != confirm:
            errors.append("Passwords do not match.")

        if not errors:
            try:
                conn   = get_db_connection()
                cursor = conn.cursor()
                hashed = generate_password_hash(password)
                cursor.execute(
                    "INSERT INTO users (username, email, password) VALUES (%s, %s, %s)",
                    (username, email, hashed)
                )
                conn.commit()
                user_id = cursor.lastrowid
                cursor.close()
                conn.close()

                session["user_id"]  = user_id
                session["username"] = username
                return redirect(url_for("index"))

            except mysql.connector.errors.IntegrityError as e:
                err_msg = str(e)
                if "username" in err_msg:
                    errors.append("That username is already taken.")
                elif "email" in err_msg:
                    errors.append("An account with that email already exists.")
                else:
                    errors.append("Registration failed. Please try again.")

    return render_template("signup.html", errors=errors, form_data=form_data, active_page="")


# ---------------------------------------------------------------------------
# AUTH — Login
# ---------------------------------------------------------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("index"))

    errors    = []
    form_data = {}

    if request.method == "POST":
        identifier = request.form.get("identifier", "").strip()
        password   = request.form.get("password", "")
        next_url   = request.form.get("next", "")

        form_data = {"identifier": identifier}

        if not identifier or not password:
            errors.append("Please fill in all fields.")
        else:
            try:
                conn   = get_db_connection()
                cursor = conn.cursor(dictionary=True)
                cursor.execute(
                    "SELECT * FROM users WHERE email = %s OR username = %s",
                    (identifier.lower(), identifier)
                )
                user = cursor.fetchone()
                cursor.close()
                conn.close()

                if user and check_password_hash(user["password"], password):
                    session["user_id"]  = user["id"]
                    session["username"] = user["username"]
                    return redirect(next_url or url_for("index"))
                else:
                    errors.append("Invalid credentials.")

            except Exception as e:
                print("LOGIN DB ERROR:", e)
                errors.append("Something went wrong.")

    next_url = request.args.get("next", "")
    return render_template("login.html", errors=errors, form_data=form_data,
                           next_url=next_url, active_page="")


# ---------------------------------------------------------------------------
# AUTH — Logout
# ---------------------------------------------------------------------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


# ---------------------------------------------------------------------------
# Route: /generate
# ---------------------------------------------------------------------------
@app.route("/generate", methods=["POST"])
@login_required
def generate():
    shop_name    = request.form.get("shop_name", "").strip()
    category     = request.form.get("category", "").strip()
    description  = request.form.get("description", "").strip()
    products_raw = request.form.get("products", "").strip()
    hours        = request.form.get("hours", "").strip()
    contact      = request.form.get("contact", "").strip()
    address      = request.form.get("address", "").strip()

    errors = []
    if not shop_name:
        errors.append("Shop name is required.")
    if not contact:
        errors.append("Contact number is required.")
    if not address:
        errors.append("Address is required.")

    if errors:
        return render_template("form.html", errors=errors, form_data=request.form, active_page="home")

    products = [p.strip() for p in products_raw.split(",") if p.strip()]
    slug = slugify(shop_name)

    user_id = session.get("user_id")

    SHOPS[slug] = {
        "shop_name": shop_name,
        "slug": slug,
        "category": category or "General",
        "description": description,
        "products": products,
        "hours": hours or "Not specified",
        "contact": contact,
        "address": address,
        "user_id": user_id,
    }

    return redirect(url_for("view_site", shop_slug=slug))


# ---------------------------------------------------------------------------
# View Site
# ---------------------------------------------------------------------------
@app.route("/site/<shop_slug>")
def view_site(shop_slug):
    shop = SHOPS.get(shop_slug)
    if not shop:
        abort(404)
    return render_template("site.html", shop=shop)


# ---------------------------------------------------------------------------
# ★ NEW: Request Go Live — redirects to WhatsApp with pre-filled message
# ---------------------------------------------------------------------------
@app.route("/request-go-live/<shop_slug>")
def request_go_live(shop_slug):
    shop = SHOPS.get(shop_slug)
    if not shop:
        abort(404)

    site_url = url_for("view_site", shop_slug=shop_slug, _external=True)
    products_str = ", ".join(shop["products"]) if shop["products"] else "N/A"

    message = (
        f"👋 Hello! I'd like to request my ShopSite to go live.\n\n"
        f"🏪 *Shop Name:* {shop['shop_name']}\n"
        f"🗂 *Category:* {shop['category']}\n"
        f"📝 *Description:* {shop['description'] or 'N/A'}\n"
        f"🛒 *Products/Services:* {products_str}\n"
        f"📞 *Contact:* {shop['contact']}\n"
        f"📍 *Address:* {shop['address']}\n"
        f"🕐 *Hours:* {shop['hours']}\n\n"
        f"🔗 *Generated Site:* {site_url}\n\n"
        f"Please review and get back to me. Thank you!"
    )

    encoded_message = urllib.parse.quote(message)
    whatsapp_url = f"https://wa.me/{WHATSAPP_NUMBER}?text={encoded_message}"

    return redirect(whatsapp_url)


# ---------------------------------------------------------------------------
# 404
# ---------------------------------------------------------------------------
@app.errorhandler(404)
def not_found(e):
    return render_template("404.html"), 404


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    app.run(debug=True)