"""
app.py - Main Flask application for the Shop Website Generator MVP
Handles routing, form processing, and site generation using Jinja2 templates.
"""

from flask import Flask, render_template, request, redirect, url_for, abort
import re

import mysql.connector

def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="your_password",
        database="shopsite"
    )

app = Flask(__name__)

# ---------------------------------------------------------------------------
# In-memory store: { slug: shop_data_dict }
# ---------------------------------------------------------------------------
SHOPS = {}


# ---------------------------------------------------------------------------
# Helper: convert a shop name to a URL-safe slug
# ---------------------------------------------------------------------------
def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text.strip("-")


# ---------------------------------------------------------------------------
# Route: / → Home (input form)
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    return render_template("form.html", active_page="home")


# ---------------------------------------------------------------------------
# Route: /about → About page
# ---------------------------------------------------------------------------
@app.route("/about")
def about():
    return render_template("about.html", active_page="about")


# ---------------------------------------------------------------------------
# Route: /contact → Contact page
# ---------------------------------------------------------------------------
@app.route("/contact")
def contact():
    return render_template("contact.html", active_page="contact")


@app.route("/submit-contact", methods=["POST"])
def submit_contact():
    name = request.form.get("name")
    email = request.form.get("email")
    subject = request.form.get("subject")
    message = request.form.get("message")

    # ✅ Basic validation (added)
    if not name or not email or not message:
        return {"status": "error", "message": "Missing required fields"}

    try:
        conn = get_db_connection()
        cursor = conn.cursor()  # keeping same (no unnecessary change)

        cursor.execute(
            "INSERT INTO contacts (name, email, subject, message) VALUES (%s, %s, %s, %s)",
            (name, email, subject, message)
        )

        conn.commit()

        # ✅ Safe closing (added protection)
        cursor.close()
        conn.close()

        return {"status": "success"}

    except Exception as e:
        print("DB ERROR:", e)
        return {"status": "error"}


# ---------------------------------------------------------------------------
# Route: /generate (POST) → validate inputs, store data, redirect to site
# ---------------------------------------------------------------------------
@app.route("/generate", methods=["POST"])
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
        return render_template(
            "form.html",
            errors=errors,
            form_data=request.form,
            active_page="home"
        )

    products = [p.strip() for p in products_raw.split(",") if p.strip()]
    slug = slugify(shop_name)
    base_slug = slug
    counter = 1
    while slug in SHOPS:
        slug = f"{base_slug}-{counter}"
        counter += 1

    SHOPS[slug] = {
        "shop_name":   shop_name,
        "slug":        slug,
        "category":    category or "General",
        "description": description,
        "products":    products,
        "hours":       hours or "Not specified",
        "contact":     contact,
        "address":     address,
    }

    return redirect(url_for("view_site", shop_slug=slug))


# ---------------------------------------------------------------------------
# Route: /site/<shop_slug> → render the generated website
# ---------------------------------------------------------------------------
@app.route("/site/<shop_slug>")
def view_site(shop_slug):
    shop = SHOPS.get(shop_slug)
    if not shop:
        abort(404)
    return render_template("site.html", shop=shop)


# ---------------------------------------------------------------------------
# Custom 404 page
# ---------------------------------------------------------------------------
@app.errorhandler(404)
def not_found(e):
    return render_template("404.html"), 404


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    app.run(debug=True)