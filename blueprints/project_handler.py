"""
Project Handler Module (project_handler.py)
--------------------------------------------
Save / load / list "Projects" (isolated result cycles: a semester, an
academic year, an exam). Includes path-traversal protection when resolving
project files by ID, and maintains a live sheet cache the teacher chatbot
reads for context.
"""

import json
import os

from flask import Blueprint, request, jsonify, render_template, session

import config
from blueprints.auth import login_required
from calc_engine import compute_sheet, class_statistics
from validators import validate_sheet
from blueprints.student_predictor import live_at_risk_preview

project_bp = Blueprint("project", __name__)


def _safe_project_path(project_id):
    """Sanitize project_id to prevent path traversal, keep file inside PROJECTS_DIR."""
    safe_name = os.path.basename(str(project_id))
    path = os.path.abspath(os.path.join(config.PROJECTS_DIR, f"{safe_name}.json"))
    if not path.startswith(os.path.abspath(config.PROJECTS_DIR)):
        raise ValueError("Invalid project id.")
    return path


def load_project(project_id):
    path = _safe_project_path(project_id)
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_project(project_id, data):
    os.makedirs(config.PROJECTS_DIR, exist_ok=True)
    path = _safe_project_path(project_id)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    _update_sheet_cache(project_id, data)


def list_projects():
    os.makedirs(config.PROJECTS_DIR, exist_ok=True)
    out = []
    for fname in sorted(os.listdir(config.PROJECTS_DIR)):
        if fname.endswith(".json"):
            pid = fname[:-5]
            data = load_project(pid)
            if data:
                out.append({
                    "project_id": pid,
                    "title": data.get("title", pid),
                    "session": data.get("session", ""),
                    "student_count": len(data.get("students", [])),
                })
    return out


def _update_sheet_cache(project_id, data):
    """Writes a compact human-readable summary the chatbot can read as context."""
    subjects = data.get("subjects", [])
    students = data.get("students", [])
    rows = compute_sheet(students, subjects) if subjects and students else []
    stats = class_statistics(rows)
    at_risk = live_at_risk_preview(rows)

    lines = [
        f"Project: {data.get('title', project_id)} ({data.get('session', '')})",
        f"Subjects: {', '.join(s['name'] for s in subjects)}",
        f"Students: {len(students)}",
        f"Class stats -> mean:{stats['mean']} median:{stats['median']} "
        f"std_dev:{stats['std_dev']} highest:{stats['highest']} lowest:{stats['lowest']}",
    ]
    if at_risk:
        lines.append("At-risk students (attendance + performance combined):")
        for s in at_risk:
            lines.append(
                f"  - {s['name']} ({s['student_id']}): risk={s['risk_level']} "
                f"score={s['risk_score']} attendance={s.get('attendance')}% "
                f"grade%={s['percentage']}"
            )
    else:
        lines.append("No students currently flagged as at-risk.")

    os.makedirs(os.path.dirname(config.SHEET_CACHE_FILE), exist_ok=True)
    with open(config.SHEET_CACHE_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


@project_bp.route("/dashboard")
@login_required
def dashboard():
    return render_template("teacher_dashboard.html", projects=list_projects())


@project_bp.route("/api/project/list")
@login_required
def api_list():
    return jsonify(list_projects())


@project_bp.route("/api/project/<project_id>", methods=["GET"])
@login_required
def api_get(project_id):
    data = load_project(project_id)
    if not data:
        return jsonify({"error": "not found"}), 404
    return jsonify(data)


@project_bp.route("/api/project/<project_id>", methods=["POST"])
@login_required
def api_save(project_id):
    data = request.get_json(force=True)
    subjects = data.get("subjects", [])
    students = data.get("students", [])

    issues = validate_sheet(students, subjects)
    save_project(project_id, data)

    rows = compute_sheet(students, subjects) if subjects and students else []
    return jsonify({
        "ok": True,
        "issues": issues,
        "computed": rows,
        "stats": class_statistics(rows),
        "at_risk": live_at_risk_preview(rows),
    })


@project_bp.route("/api/project/<project_id>", methods=["DELETE"])
@login_required
def api_delete(project_id):
    path = _safe_project_path(project_id)
    if os.path.exists(path):
        os.remove(path)
        return jsonify({"ok": True})
    return jsonify({"error": "not found"}), 404
