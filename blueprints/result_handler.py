"""
Result Handler Module (result_handler.py)
-------------------------------------------
Handles publishing finalized results into the student-facing store, and
retrieving a student's full academic history for their portal. Also exposes
an AI-summarization endpoint for teachers.
"""

from flask import Blueprint, request, jsonify, render_template, session

from blueprints.auth import login_required, student_login_required
from db import get_collection
from calc_engine import compute_sheet, compute_cgpa
from blueprints.chatbot_handler import summarize_results_data
from blueprints.student_predictor import analyse_student_performance
from insights import generate_insights
from transcript import build_transcript

result_bp = Blueprint("result", __name__)


@result_bp.route("/api/result/publish", methods=["POST"])
@login_required
def publish_results():
    """
    Upserts a computed sheet into each student's nested result history:
    students.results[session][exam_name] = row
    """
    payload = request.get_json(force=True)
    session_name = payload["session"]
    exam_name = payload["exam_name"]
    subjects = payload["subjects"]
    students_in = payload["students"]

    rows = compute_sheet(students_in, subjects)
    students_coll = get_collection("students")

    for row in rows:
        sid = row["student_id"]
        existing = students_coll.find_one({"college_id": sid})
        if not existing:
            # Auto-provision a student record if one doesn't exist yet
            students_coll.insert_one({
                "college_id": sid,
                "name": row["name"],
                "mother_name": "",
                "results": {session_name: {exam_name: row}},
            })
            continue

        results = existing.get("results", {})
        results.setdefault(session_name, {})[exam_name] = row
        students_coll.update_one(
            {"college_id": sid},
            {"$set": {"results": results}},
        )

    return jsonify({"ok": True, "published": len(rows)})


@result_bp.route("/api/result/<session_name>/<exam_name>", methods=["DELETE"])
@login_required
def delete_result(session_name, exam_name):
    students_coll = get_collection("students")
    for student in students_coll.find():
        results = student.get("results", {})
        if session_name in results and exam_name in results[session_name]:
            del results[session_name][exam_name]
            students_coll.update_one(
                {"college_id": student["college_id"]},
                {"$set": {"results": results}},
            )
    return jsonify({"ok": True})


@result_bp.route("/api/result/summarize", methods=["POST"])
@login_required
def summarize():
    payload = request.get_json(force=True)
    summary = summarize_results_data(payload)
    return jsonify({"summary": summary})


@result_bp.route("/api/result/insights", methods=["POST"])
@login_required
def insights():
    row = request.get_json(force=True)
    return jsonify(generate_insights(row))


@result_bp.route("/student/portal")
@student_login_required
def student_portal():
    college_id = session["college_id"]
    students_coll = get_collection("students")
    student = students_coll.find_one({"college_id": college_id}) or {}
    results = student.get("results", {})

    gpas = [
        exam["gpa"]
        for sess in results.values()
        for exam in sess.values()
        if "gpa" in exam
    ]
    cgpa = compute_cgpa(gpas)
    risk = analyse_student_performance(results)
    transcript = build_transcript(results)

    return render_template(
        "student_dashboard.html",
        student=student,
        results=results,
        cgpa=cgpa,
        risk=risk,
        transcript=transcript,
    )


@result_bp.route("/api/student/<college_id>/results")
@login_required
def api_student_results(college_id):
    students_coll = get_collection("students")
    student = students_coll.find_one({"college_id": college_id})
    if not student:
        return jsonify({"error": "not found"}), 404
    return jsonify(student.get("results", {}))


@result_bp.route("/api/student/<college_id>/transcript")
@login_required
def api_student_transcript(college_id):
    """NEW FEATURE: teacher-facing full academic record, Semester 1 -> 8."""
    students_coll = get_collection("students")
    student = students_coll.find_one({"college_id": college_id})
    if not student:
        return jsonify({"error": "not found"}), 404
    transcript = build_transcript(student.get("results", {}))
    return jsonify({
        "student": {"college_id": student.get("college_id"), "name": student.get("name")},
        **transcript,
    })
