"""
Study Roadmap Module (study_roadmap.py)
-----------------------------------------
NEW FEATURE — Edu-AI Improvement Roadmap & Resources
-----------------------------------------------------
Turns a student's published result history into a personalized improvement
plan: focus areas, a phased weekly roadmap, curated free learning resources,
and study habits.

Like insights.py/transcript.py this module is deliberately framework-free
(no Flask imports) so it can be exercised directly from a REPL or script.
It feeds two consumers inside chatbot_handler.py:

  * the LIVE path  -> build_report_context() produces the text digest that is
                      sent to Gemini along with a strict JSON-output prompt;
  * the OFFLINE path -> build_offline_roadmap() deterministically builds the
                      same structure from the data alone, so the feature is
                      fully demoable without an API key.

Both paths converge on ONE plan shape (validated by normalize_ai_roadmap):

    {
      "headline": str,
      "focus_areas": [{subject, current, why, actions[str]}],   # <= 4
      "phases":     [{title, window, goal, steps[str]}],        # <= 4
      "resources":  [{subject, title, type, url}],              # <= 6
      "habits":     [str],
      "encouragement": str,
    }
"""

from blueprints.student_predictor import analyse_student_performance
from transcript import build_transcript

# ---- Curated free-resource library ---------------------------------------
# Matched case-insensitively against subject names; GENERIC fills any slots
# left over so the plan always carries actionable links.
RESOURCE_LIBRARY = [
    ({"math", "mathematics", "algebra", "calculus", "statistics", "discrete"}, {
        "subject": "Mathematics", "title": "Khan Academy Math", "type": "course",
        "url": "https://www.khanacademy.org/math",
    }),
    ({"data structures", "dsa", "algorithms", "programming", "computer science",
      "python", "java", "c++", "coding", "oop"}, {
        "subject": "Computer Science", "title": "CS50x (Harvard, free)", "type": "course",
        "url": "https://cs50.harvard.edu/x/",
    }),
    ({"data structures", "dsa", "algorithms", "programming", "coding"}, {
        "subject": "Programming practice", "title": "freeCodeCamp", "type": "practice",
        "url": "https://www.freecodecamp.org/",
    }),
    ({"networks", "computer networks", "networking", "communication"}, {
        "subject": "Computer Networks", "title": "NPTEL Computer Networks", "type": "video",
        "url": "https://nptel.ac.in/courses/106105183",
    }),
    ({"physics", "mechanics", "optics", "electronics"}, {
        "subject": "Physics", "title": "Khan Academy Physics", "type": "course",
        "url": "https://www.khanacademy.org/science/physics",
    }),
    ({"chemistry", "organic", "inorganic"}, {
        "subject": "Chemistry", "title": "Khan Academy Chemistry", "type": "course",
        "url": "https://www.khanacademy.org/science/chemistry",
    }),
    ({"biology", "botany", "zoology"}, {
        "subject": "Biology", "title": "Khan Academy Biology", "type": "course",
        "url": "https://www.khanacademy.org/science/biology",
    }),
    ({"english", "grammar", "communication", "language"}, {
        "subject": "English", "title": "LearnEnglish (British Council)", "type": "practice",
        "url": "https://learnenglish.britishcouncil.org/",
    }),
]

GENERIC_RESOURCES = [
    {"subject": "All subjects", "title": "NPTEL video lectures", "type": "video",
     "url": "https://nptel.ac.in/"},
    {"subject": "All subjects", "title": "MIT OpenCourseWare", "type": "course",
     "url": "https://ocw.mit.edu/"},
    {"subject": "Revision", "title": "Anki spaced-repetition flashcards", "type": "practice",
     "url": "https://apps.ankiweb.net/"},
]


# ---- Context builder for the live Gemini path ------------------------------

def _band_label(pct):
    if pct < 33:
        return "failing"
    if pct < 40:
        return "borderline pass"
    if pct < 60:
        return "below average"
    if pct < 75:
        return "average"
    return "strong"


def build_report_context(student_doc):
    """
    Compact text digest of one student's record, sent to the AI as CONTEXT.
    Keeps the prompt short: full subject detail for the latest exam only,
    one-line summaries for earlier ones.
    """
    results = student_doc.get("results", {})
    risk = analyse_student_performance(results)
    transcript = build_transcript(results)

    name = student_doc.get("name") or student_doc.get("college_id") or "Unknown"
    lines = [
        f"Student: {name}",
        f"CGPA: {transcript['cgpa']} across {transcript['total_semesters']} semester(s)",
        (
            f"Risk profile: level={risk['risk_level']} score={risk['risk_score']}/100, "
            f"average score={risk['average_percentage']}%, "
            f"average attendance={risk['average_attendance']}%, "
            f"score trend={risk['trend']}, attendance trend={risk['attendance_trend']}"
        ),
    ]
    if risk["risk_drivers"]:
        lines.append("Risk drivers: " + "; ".join(risk["risk_drivers"]))
    if risk["weak_subjects"]:
        lines.append("Subjects that failed/repeatedly scored low: " + ", ".join(risk["weak_subjects"]))

    if not transcript["semesters"]:
        lines.append("No published results yet.")
        return "\n".join(lines)

    for sem in transcript["semesters"]:
        exam_bits = ", ".join(
            e["exam_name"] + " (" + str(e["percentage"]) + "%)"
            for e in sem["exams"]
        )
        lines.append(
            "- " + sem["session_name"] + ": average " + str(sem["percentage"])
            + "%, GPA " + str(sem["gpa"]) + ", exams: " + exam_bits
        )

    # Subject-level breakdown for the most recent exam only.
    latest = transcript["semesters"][-1]
    latest_exams = results.get(latest["session_name"], {})
    for exam_name, row in latest_exams.items():
        lines.append("Subject breakdown for " + latest["session_name"] + "/" + exam_name + ":")
        subjects = sorted(
            row.get("subjects", {}).items(),
            key=lambda kv: kv[1].get("percentage", 0),
        )
        for subj_name, subj in subjects:
            lines.append(
                "  - " + subj_name + ": " + str(subj.get("score")) + "/"
                + str(subj.get("max_marks")) + " = " + str(subj.get("percentage"))
                + "% (" + str(subj.get("grade")) + ")"
            )
        break  # single latest exam is enough

    return "\n".join(lines)


# ---- Offline (rule-based) roadmap builder -----------------------------------

def _focus_actions(pct):
    """Band-specific action steps, mirroring how teachers actually coach."""
    if pct < 40:
        return [
            "Rebuild the fundamentals chapter by chapter from your class notes",
            "Solve basic worked examples daily for 30-45 minutes before harder problems",
            "List the topics you avoid and ask your teacher about them this week",
        ]
    if pct < 60:
        return [
            "Redo every question you got wrong in the last two exams",
            "Work through one past paper per week under timed conditions",
            "Keep a mistake log and read it before every test",
        ]
    return [
        "Move to advanced problem sets beyond the textbook",
        "Explain the hardest topics to a classmate - teaching exposes gaps",
        "Aim for a 10-point jump with a short weekly self-test",
    ]


def _pick_resources(subject_names, limit=6):
    picked, seen_urls = [], set()
    lowered = [str(s).lower() for s in subject_names]
    for keywords, resource in RESOURCE_LIBRARY:
        if any(k in name for name in lowered for k in keywords):
            if resource["url"] not in seen_urls:
                picked.append(dict(resource))
                seen_urls.add(resource["url"])
    for resource in GENERIC_RESOURCES:
        if len(picked) >= limit:
            break
        if resource["url"] not in seen_urls:
            picked.append(dict(resource))
            seen_urls.add(resource["url"])
    return picked[:limit]


def build_offline_roadmap(results):
    """
    Deterministic improvement plan built purely from the result history -
    the zero-dependency fallback for the AI roadmap feature.
    """
    risk = analyse_student_performance(results)
    transcript = build_transcript(results)

    # Latest exam's subjects drive the focus areas (fall back to the
    # predictor's cumulative weak-subject list when nothing else is known).
    latest_subjects = {}
    latest_label = ""
    if transcript["semesters"]:
        latest_session = transcript["semesters"][-1]["session_name"]
        for exam_name, row in results.get(latest_session, {}).items():
            latest_subjects = row.get("subjects", {})
            latest_label = latest_session + "/" + exam_name
            break

    focus_areas = []
    ranked = sorted(
        latest_subjects.items(),
        key=lambda kv: kv[1].get("percentage", 0),
    )
    weak = [(n, s) for n, s in ranked if s.get("percentage", 0) < 75] or ranked[:1]
    for subj_name, subj in weak[:3]:
        pct = subj.get("percentage", 0)
        why_parts = [
            "scored " + str(subj.get("score")) + "/" + str(subj.get("max_marks"))
            + " (" + str(pct) + "%, " + _band_label(pct) + ") in " + latest_label
        ]
        if subj_name in risk["weak_subjects"]:
            why_parts.append("a recurring weak spot across your history")
        if risk["trend"] == "declining":
            why_parts.append("your overall scores have been trending down")
        focus_areas.append({
            "subject": subj_name,
            "current": pct,
            "why": "You " + " and ".join(why_parts) + ".",
            "actions": _focus_actions(pct),
        })

    phases = [
        {
            "title": "Foundations",
            "window": "Weeks 1-2",
            "goal": "Close the biggest understanding gaps in " + (
                ", ".join(fa["subject"] for fa in focus_areas) or "your weakest subjects"),
            "steps": [
                "Revise notes for each focus area and list concepts you cannot explain",
                "Short daily study block (45-60 min) per focus subject",
            ],
        },
        {
            "title": "Guided practice",
            "window": "Weeks 3-4",
            "goal": "Convert understanding into exam marks",
            "steps": [
                "Past papers / textbook exercises, one timed set per week",
                "Maintain a mistake log; re-solve every logged mistake once",
            ],
        },
        {
            "title": "Test & consolidate",
            "window": "Weeks 5-6",
            "goal": "Walk into the next exam rehearsed, not surprised",
            "steps": [
                "Two full mock tests under exam conditions; review against the mistake log",
                "Final-week light revision of formulas and key definitions only",
            ],
        },
    ]

    habits = [
        "Fixed daily study slot - same time, phone away",
        "End each week with a 20-minute self-quiz on what you studied",
        "7-8 hours of sleep, especially the night before tests",
    ]

    if risk["attendance_trend"] == "declining" or risk["average_attendance"] < 75:
        phases[0]["steps"].insert(
            0,
            "Attendance repair: attend every class for the next month (currently ~"
            + str(risk["average_attendance"]) + "%)",
        )
        habits.insert(0, "Sit in the front row and commit to zero missed lectures this month")

    if risk["trend"] == "improving":
        encouragement = (
            "Your scores are already climbing - keep the streak going and protect that momentum."
        )
    elif risk["trend"] == "declining":
        encouragement = (
            "Recent dips are a signal, not a verdict. Work the plan above and the curve will follow."
        )
    elif risk["risk_level"] == "High":
        encouragement = (
            "Things look tough right now, but steady small wins beat panic - start with Phase 1 today."
        )
    else:
        encouragement = (
            "You are holding steady - sharpening your weakest subjects is what unlocks the next grade."
        )

    headline_bits = []
    if transcript["total_semesters"]:
        headline_bits.append("CGPA " + str(transcript["cgpa"]))
    headline_bits.append(str(risk["average_percentage"]) + "% average")
    headline = (
        "Focus on " + (", ".join(fa["subject"] for fa in focus_areas) or "your core subjects")
        + " (" + " · ".join(headline_bits) + ")"
    )

    return {
        "headline": headline,
        "focus_areas": focus_areas,
        "phases": phases,
        "resources": _pick_resources([fa["subject"] for fa in focus_areas] or list(latest_subjects)),
        "habits": habits,
        "encouragement": encouragement,
    }


# ---- Normalizer for the live Gemini path ------------------------------------

def _clean_str(value, cap=300):
    if not isinstance(value, str):
        return ""
    value = value.strip()
    return value[:cap]


def _as_float(value):
    try:
        return round(float(value), 1)
    except (TypeError, ValueError):
        return None


def _safe_url(value):
    url = _clean_str(value, 500)
    return url if url.startswith(("http://", "https://")) else ""


def _norm_focus(item):
    if not isinstance(item, dict):
        return None
    subject = _clean_str(item.get("subject"), 120)
    actions = [_clean_str(a) for a in item.get("actions", []) if isinstance(a, str)]
    actions = [a for a in actions if a][:6]
    if not subject or not actions:
        return None
    return {
        "subject": subject,
        "current": _as_float(item.get("current")),
        "why": _clean_str(item.get("why")),
        "actions": actions,
    }


def _norm_phase(item):
    if not isinstance(item, dict):
        return None
    title = _clean_str(item.get("title"), 120) or _clean_str(item.get("phase"), 120)
    steps = [_clean_str(s) for s in item.get("steps", []) if isinstance(s, str)]
    steps = [s for s in steps if s][:6]
    if not title or not steps:
        return None
    return {
        "title": title,
        "window": _clean_str(item.get("window", ""), 60),
        "goal": _clean_str(item.get("goal")),
        "steps": steps,
    }


def _norm_resource(item):
    if not isinstance(item, dict):
        return None
    title = _clean_str(item.get("title"), 150)
    url = _safe_url(item.get("url"))
    if not title or not url:
        return None
    return {
        "subject": _clean_str(item.get("subject"), 120),
        "title": title,
        "type": _clean_str(item.get("type"), 40),
        "url": url,
    }


def normalize_ai_roadmap(data):
    """
    Coerce whatever the model returned into the plan contract.
    Returns a clean plan dict, or None if it is unusable (callers then fall
    back to the offline builder, mirroring the app-wide degrade-to-offline rule).
    """
    if not isinstance(data, dict):
        return None

    headline = _clean_str(data.get("headline"), 250)
    phases_raw = data.get("phases") if isinstance(data.get("phases"), list) else data.get("roadmap")
    if not headline or not isinstance(phases_raw, list) or not phases_raw:
        return None

    phases = [p for p in (_norm_phase(x) for x in phases_raw[:4]) if p]
    if not phases:
        return None

    focus_areas = [f for f in (_norm_focus(x) for x in (data.get("focus_areas") or [])[:4]) if f]
    resources = [r for r in (_norm_resource(x) for x in (data.get("resources") or [])[:8]) if r]
    habits = [_clean_str(h) for h in (data.get("habits") or [])[:8] if isinstance(h, str)]
    habits = [h for h in habits if h][:6]

    return {
        "headline": headline,
        "focus_areas": focus_areas,
        "phases": phases,
        "resources": resources[:6],
        "habits": habits,
        "encouragement": _clean_str(data.get("encouragement")),
    }
