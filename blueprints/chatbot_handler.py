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

Also hosts the Improvement Roadmap endpoints (/api/chatbot/{student,teacher}/
roadmap): the student's published history is analyzed into a study plan +
resource list — live Gemini when available, deterministic fallback via
study_roadmap.build_offline_roadmap otherwise.
"""

import hashlib
import json
import os

from flask import Blueprint, request, jsonify, session

import config
from db import get_collection
from study_roadmap import build_offline_roadmap, build_report_context, normalize_ai_roadmap

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

ROADMAP_SYSTEM_PROMPT = """You are Edu-AI, a supportive academic coach for a
student using ARMS. Analyze the provided result history (grades, trends,
attendance, risk profile) and produce a realistic improvement plan.

Reply with ONLY raw JSON — no markdown fences, no commentary — exactly in
this shape:
{
  "headline": "one-sentence summary of what to focus on",
  "focus_areas": [{"subject": "...", "current": 45.0, "why": "...", "actions": ["...", "..."]}],
  "phases": [{"title": "...", "window": "Weeks 1-2", "goal": "...", "steps": ["...", "..."]}],
  "resources": [{"subject": "...", "title": "...", "type": "course|video|practice|book", "url": "https://..."}],
  "habits": ["...", "..."],
  "encouragement": "one warm closing sentence"
}

Rules: 2-4 focus areas (weakest subjects first, with concrete study actions);
exactly 3 phases forming a realistic weekly roadmap; 3-6 resources pointing to
REAL, well-known free learning sites only (Khan Academy, NPTEL, MIT
OpenCourseWare, freeCodeCamp, CS50, British Council LearnEnglish); never
invent URLs; never mention other students; be encouraging but honest."""


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
    except Exception as exc:
        print(f"[chatbot] Gemini unavailable, using offline fallback: {exc}")
        return None
    for model_name in (config.GEMINI_MODEL, config.GEMINI_FALLBACK_MODEL):
        try:
            model = genai.GenerativeModel(model_name, system_instruction=system_prompt)
            response = model.generate_content(f"CONTEXT:\n{context}\n\nQUESTION:\n{question}")
            return response.text
        except Exception as exc:
            print(f"[chatbot] Gemini call failed on {model_name}, trying fallback: {exc}")
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


# ---- Improvement Roadmap (student report -> plan + resources) ---------------

# Re-clicks shouldn't re-bill Gemini while a student's results are unchanged,
# so the last generated plan is cached per (college_id, context digest).
_ROADMAP_CACHE = {}
_ROADMAP_CACHE_MAX = 128


def _extract_json(text):
    """Best-effort recovery of a JSON object from a model reply."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        first_line_break = cleaned.find("\n")
        if first_line_break != -1:
            cleaned = cleaned[first_line_break + 1:]
        cleaned = cleaned.rstrip("`").strip()
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start == -1 or end <= start:
        return None
    return cleaned[start:end + 1]


def _try_gemini_roadmap(context):
    if not config.GEMINI_API_KEY:
        return None
    try:
        import google.generativeai as genai
        genai.configure(api_key=config.GEMINI_API_KEY)
    except Exception as exc:
        print(f"[chatbot] Gemini unavailable, using offline fallback: {exc}")
        return None
    for model_name in (config.GEMINI_MODEL, config.GEMINI_FALLBACK_MODEL):
        try:
            model = genai.GenerativeModel(
                model_name, system_instruction=ROADMAP_SYSTEM_PROMPT,
            )
            response = model.generate_content(
                f"CONTEXT:\n{context}\n\nTASK:\nProduce the improvement plan JSON now."
            )
            parsed = json.loads(_extract_json(response.text))
            return normalize_ai_roadmap(parsed)
        except Exception as exc:
            print(f"[chatbot] Gemini roadmap failed on {model_name}, trying fallback: {exc}")
    return None


def build_roadmap_response(college_id):
    """
    Shared by both roadmap routes: gather the student's history, try live
    Gemini, degrade to the deterministic offline plan, cache, and shape the
    API response.
    """
    students_coll = get_collection("students")
    student = students_coll.find_one({"college_id": college_id})
    if not student:
        return jsonify({"error": "not found"}), 404

    results = student.get("results", {})
    student_brief = {"college_id": college_id, "name": student.get("name")}

    if not results:
        return jsonify({
            "ok": False,
            "message": "No published results yet — a plan will be available once your teacher publishes results.",
            "student": student_brief,
        })

    context = build_report_context(student)
    cache_key = (college_id, hashlib.md5(context.encode("utf-8")).hexdigest())
    cached = _ROADMAP_CACHE.get(cache_key)
    if cached is not None:
        return jsonify({**cached, "cached": True})

    plan = _try_gemini_roadmap(context)
    mode = "gemini"
    if plan is None:
        plan = build_offline_roadmap(results)
        mode = "offline"

    payload = {"ok": True, "plan": plan, "mode": mode, "student": student_brief}
    if len(_ROADMAP_CACHE) >= _ROADMAP_CACHE_MAX:
        _ROADMAP_CACHE.clear()
    _ROADMAP_CACHE[cache_key] = payload
    return jsonify(payload)


@chatbot_bp.route("/api/chatbot/student/roadmap", methods=["POST"])
def chatbot_student_roadmap():
    if session.get("role") != "student":
        return jsonify({"error": "unauthorized"}), 401
    return build_roadmap_response(session["college_id"])


@chatbot_bp.route("/api/chatbot/teacher/roadmap", methods=["POST"])
def chatbot_teacher_roadmap():
    if session.get("role") != "teacher":
        return jsonify({"error": "unauthorized"}), 401
    college_id = (request.get_json(force=True) or {}).get("college_id", "").strip()
    if not college_id:
        return jsonify({"error": "college_id required"}), 400
    return build_roadmap_response(college_id)


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
