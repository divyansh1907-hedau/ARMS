"""
Chatbot Handler Module (chatbot_handler.py)
---------------------------------------------
Dual-persona AI assistant: one system prompt/context for teachers, one for
students, per the thesis design.

Live mode: if GEMINI_API_KEY is set and google-generativeai is installed,
calls the real Gemini API.
Offline mode (default, works with zero setup): returns rule-based responses
built from the same context files, so the whole app is demoable without a
key or network access.
"""

import os

from flask import Blueprint, request, jsonify, session

import config
from db import get_collection

chatbot_bp = Blueprint("chatbot", __name__)

TEACHER_SYSTEM_PROMPT = """You are Edu-AI, an assistant for teachers using the
Academic Record and Management System (ARMS). Use the provided sheet
data, project overview, system analysis, and historical project analysis to
answer questions about class performance, at-risk students, and how to use
the system. Be concise and data-driven."""

STUDENT_SYSTEM_PROMPT = """You are Edu-AI, a supportive study assistant for a
student using ARMS. Use the student's own result history to explain their
grades, encourage them, and answer questions about their performance. Never
reveal other students' data."""


def _read_file(path):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return ""


def _try_gemini(system_prompt, context, question):
    if not config.GEMINI_API_KEY:
        return None
    try:
        import google.generativeai as genai
        genai.configure(api_key=config.GEMINI_API_KEY)
        model = genai.GenerativeModel(config.GEMINI_MODEL, system_instruction=system_prompt)
        response = model.generate_content(f"CONTEXT:\n{context}\n\nQUESTION:\n{question}")
        return response.text
    except Exception as exc:
        print(f"[chatbot] Gemini call failed, using offline fallback: {exc}")
        return None


def _offline_teacher_reply(context, question):
    q = question.lower()
    if "at risk" in q or "risk" in q or "fail" in q:
        return ("Here's the current at-risk breakdown (combining attendance + grades):\n\n" +
                context[:700])
    if "average" in q or "mean" in q or "class performance" in q:
        return "Here's the latest class statistics I have cached:\n" + context
    if "how" in q and ("use" in q or "upload" in q):
        return ("To upload marks: open a project, use the spreadsheet editor to enter or "
                "paste marks, then hit Save — totals, grades, and ranks compute automatically. "
                "Use 'Publish Results' to push finalized results to the student portal.")
    return ("I'm running in offline demo mode (no GEMINI_API_KEY configured), so I can only "
            "answer from cached project data right now:\n" + context[:500])


def _offline_student_reply(context, question):
    q = question.lower()
    if "why" in q and ("fail" in q or "low" in q or "grade" in q):
        return ("Looking at your results: " + context[:400] +
                "\nFocus revision on the subject(s) with your lowest percentage first.")
    if "cgpa" in q or "gpa" in q:
        return "Your current GPA/CGPA is shown at the top of your dashboard. " + context[:300]
    return ("I'm in offline demo mode right now, but from your saved results:\n" +
            context[:500] + "\nKeep an eye on subjects below 50% and ask your teacher for help there.")


def _build_teacher_context():
    parts = [
        _read_file(config.SHEET_CACHE_FILE),
        _read_file(config.PROJECT_OVERVIEW_FILE),
        _read_file(config.SYSTEM_ANALYSIS_FILE),
        _read_file(config.PROJECTS_ANALYSIS_FILE),
    ]
    return "\n---\n".join(p for p in parts if p)


def _build_student_context(college_id):
    students_coll = get_collection("students")
    student = students_coll.find_one({"college_id": college_id}) or {}
    results = student.get("results", {})
    lines = [f"Student: {student.get('name', college_id)}"]
    for sess, exams in results.items():
        for exam_name, row in exams.items():
            lines.append(
                f"{sess}/{exam_name}: {row.get('percentage')}% grade={row.get('grade')} "
                f"gpa={row.get('gpa')}"
            )
    return "\n".join(lines) if len(lines) > 1 else "No results recorded yet."


@chatbot_bp.route("/api/chatbot/teacher", methods=["POST"])
def chatbot_teacher():
    if session.get("role") != "teacher":
        return jsonify({"error": "unauthorized"}), 401
    question = request.get_json(force=True).get("question", "")
    context = _build_teacher_context()
    reply = _try_gemini(TEACHER_SYSTEM_PROMPT, context, question)
    if reply is None:
        reply = _offline_teacher_reply(context, question)
    return jsonify({"reply": reply})


@chatbot_bp.route("/api/chatbot/student", methods=["POST"])
def chatbot_student():
    if session.get("role") != "student":
        return jsonify({"error": "unauthorized"}), 401
    question = request.get_json(force=True).get("question", "")
    context = _build_student_context(session["college_id"])
    reply = _try_gemini(STUDENT_SYSTEM_PROMPT, context, question)
    if reply is None:
        reply = _offline_student_reply(context, question)
    return jsonify({"reply": reply})


def summarize_results_data(payload):
    """Used by result_handler's /api/result/summarize endpoint."""
    students = payload.get("students", [])
    subjects = payload.get("subjects", [])
    context = f"{len(students)} students, subjects: {', '.join(s['name'] for s in subjects)}"
    reply = _try_gemini(
        TEACHER_SYSTEM_PROMPT, context,
        "Write a short summary of this class's performance and 2-3 recommendations.",
    )
    if reply is None:
        reply = (f"[offline summary] {len(students)} students across "
                  f"{len(subjects)} subjects. Configure GEMINI_API_KEY for a full AI summary.")
    return reply
