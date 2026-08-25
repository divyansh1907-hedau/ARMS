"""
Authentication Module (auth.py)
--------------------------------
Handles teacher/student login, logout, session management and RBAC.

Note on hashing: the thesis specifies bcrypt.checkpw(). This build uses
werkzeug.security's PBKDF2-SHA256 hashing (already a Flask dependency, so
the project runs with zero extra installs). Swap in bcrypt by installing it
and replacing generate_password_hash/check_password_hash below — the call
sites elsewhere in the app are unaffected.
"""

import datetime
import functools
import os
import re

from flask import Blueprint, request, session, redirect, url_for, render_template, flash
from werkzeug.security import generate_password_hash, check_password_hash

import config
from db import get_collection

auth_bp = Blueprint("auth", __name__)


def _log(path, message):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(f"{datetime.datetime.now().isoformat()} {message}\n")


def login_required(view):
    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        if session.get("role") != "teacher":
            return redirect(url_for("auth.login"))
        return view(*args, **kwargs)
    return wrapped


def student_login_required(view):
    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        if session.get("role") != "student":
            return redirect(url_for("auth.login"))
        return view(*args, **kwargs)
    return wrapped


def seed_default_users():
    """Creates a demo teacher + student on first run so login works immediately."""
    teachers = get_collection("teachers")
    students = get_collection("students")

    if not teachers.find_one({"teacher_id": "T001"}):
        teachers.insert_one({
            "teacher_id": "T001",
            "name": "Dr. Surbhi Khare",
            "password_hash": generate_password_hash("teacher123"),
            "subjects": ["Mathematics", "Computer Science"],
        })

    if not students.find_one({"college_id": "S1001"}):
        students.insert_one({
            "college_id": "S1001",
            "name": "Anjali Rao",
            "mother_name": "Sunita Rao",
            "password_hash": generate_password_hash("dummy"),  # not used, kept for parity
        })


@auth_bp.route("/", methods=["GET"])
def index():
    if session.get("role") == "teacher":
        return redirect(url_for("project.dashboard"))
    if session.get("role") == "student":
        return redirect(url_for("result.student_portal"))
    return redirect(url_for("auth.login"))


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")

    role = request.form.get("role")

    if role == "teacher":
        teacher_id = request.form.get("teacher_id", "").strip()
        password = request.form.get("password", "")
        teachers = get_collection("teachers")
        teacher = teachers.find_one({"teacher_id": teacher_id})

        if teacher and check_password_hash(teacher["password_hash"], password):
            session.clear()
            session["role"] = "teacher"
            session["teacher_id"] = teacher_id
            session["name"] = teacher.get("name")
            _log(config.TEACHER_AUTH_LOG, f"SUCCESS login teacher_id={teacher_id}")
            return redirect(url_for("project.dashboard"))

        _log(config.TEACHER_AUTH_LOG, f"FAILED login teacher_id={teacher_id}")
        flash("Invalid teacher ID or password.")
        return redirect(url_for("auth.login"))

    if role == "student":
        college_id = request.form.get("college_id", "").strip()
        mother_name = request.form.get("mother_name", "").strip()
        students = get_collection("students")
        student = students.find_one({"college_id": college_id})

        if student and student.get("mother_name", "").lower() == mother_name.lower():
            session.clear()
            session["role"] = "student"
            session["college_id"] = college_id
            session["name"] = student.get("name")
            _log(config.STUDENT_AUTH_LOG, f"SUCCESS login college_id={college_id}")
            return redirect(url_for("result.student_portal"))

        _log(config.STUDENT_AUTH_LOG, f"FAILED login college_id={college_id}")
        flash("Invalid college ID or mother's name.")
        return redirect(url_for("auth.login"))

    flash("Please select a role.")
    return redirect(url_for("auth.login"))


@auth_bp.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "GET":
        return render_template("signup.html")

    name = request.form.get("name", "").strip()
    teacher_id = request.form.get("teacher_id", "").strip()
    email = request.form.get("email", "").strip()
    password = request.form.get("password", "")
    confirm_password = request.form.get("confirm_password", "")
    subjects_raw = request.form.get("subjects", "").strip()

    errors = []
    if not name:
        errors.append("Full name is required.")
    if not teacher_id or not re.match(r"^[A-Za-z0-9_-]{3,20}$", teacher_id):
        errors.append("Teacher ID must be 3-20 characters (letters, numbers, - or _ only).")
    if not email or "@" not in email:
        errors.append("A valid email address is required.")
    if len(password) < 6:
        errors.append("Password must be at least 6 characters.")
    if password != confirm_password:
        errors.append("Passwords do not match.")

    teachers = get_collection("teachers")
    if not errors and teachers.find_one({"teacher_id": teacher_id}):
        errors.append(f"Teacher ID '{teacher_id}' is already taken.")
    if not errors and teachers.find_one({"email": email}):
        errors.append(f"An account with email '{email}' already exists.")

    if errors:
        for e in errors:
            flash(e)
        return render_template("signup.html", form=request.form)

    subjects = [s.strip() for s in subjects_raw.split(",") if s.strip()]
    teachers.insert_one({
        "teacher_id": teacher_id,
        "name": name,
        "email": email,
        "password_hash": generate_password_hash(password),
        "subjects": subjects,
    })
    _log(config.TEACHER_AUTH_LOG, f"SIGNUP new teacher_id={teacher_id} email={email}")

    flash(f"Account created! You can now log in as {teacher_id}.")
    return redirect(url_for("auth.login"))


@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))
