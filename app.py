from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from urllib.parse import urlparse
import os
import json
from analyzer import analyze_crash
from apk_info import get_apk_info
from symbolic_validator import validate_path
from ui_state import capture_ui_state

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("AUTOCRASHAI_SECRET_KEY", "change-this-local-dev-key")
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///autocrashai_users.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message = "Please log in to access AutoCrashAI."

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(254), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


with app.app_context():
    db.create_all()


@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("home"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not username or not email or not password:
            flash("Please fill in every field.", "error")
        elif len(username) > 80 or len(email) > 254:
            flash("Username or email is too long.", "error")
        elif len(password) < 8:
            flash("Password must contain at least 8 characters.", "error")
        elif User.query.filter(
            (User.username == username) | (User.email == email)
        ).first():
            flash("That username or email is already registered.", "error")
        else:
            user = User(
                username=username,
                email=email,
                password_hash=generate_password_hash(password)
            )
            db.session.add(user)
            db.session.commit()
            flash("Registration successful. Please log in.", "success")
            return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("home"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            next_url = request.args.get("next", "")
            if next_url and urlparse(next_url).netloc == "":
                return redirect(next_url)
            return redirect(url_for("home"))

        flash("Invalid email or password.", "error")

    return render_template("login.html")


@app.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    flash("You have logged out.", "success")
    return redirect(url_for("login"))


@app.route("/")
@login_required
def home():
    return render_template("index.html")


@app.route("/analyze", methods=["POST"])
@login_required
def analyze():
    apk = request.files.get("apk")
    crash_report = request.files.get("crash_report")

    if not apk or not crash_report or not apk.filename or not crash_report.filename:
        return jsonify({
            "success": False,
            "message": "Please upload both APK and crash report."
        }), 400

    apk_name = secure_filename(apk.filename)
    report_name = secure_filename(crash_report.filename)

    if not apk_name.lower().endswith(".apk"):
        return jsonify({"success": False, "message": "Please upload an APK file."}), 400

    apk_path = os.path.join(app.config["UPLOAD_FOLDER"], apk_name)
    report_path = os.path.join(app.config["UPLOAD_FOLDER"], report_name)

    apk.save(apk_path)
    report.save(report_path)

    apk_info = get_apk_info(apk_path)
    capture_ui_state(apk_path)

    with open("ui_state.json", "r", encoding="utf-8") as f:
        ui_state = json.load(f)
    ui_elements = ui_state["elements"]

    with open(report_path, "r", encoding="utf-8") as f:
        report_text = f.read()

    result = analyze_crash(report_text, apk_name)
    validation = validate_path(result.get("steps", []), ui_elements)

    return jsonify({
        "success": True,
        "result": result,
        "apk_info": apk_info,
        "validation": validation
    })


if __name__ == "__main__":
    app.run(debug=True)
