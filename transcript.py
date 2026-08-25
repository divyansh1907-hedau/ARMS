"""
Academic Transcript Module (transcript.py)
---------------------------------------------
NEW FEATURE — Full Academic Record (Semester 1 -> Semester 8)
---------------------------------------------
Consolidates a student's scattered per-session, per-exam results (stored as
results[session_name][exam_name] = computed_row) into a single ordered
academic transcript: one row per semester/session, with that semester's
GPA, percentage, and every exam recorded under it — plus a running CGPA.

Sessions are ordered by any digit found in their name (so "Semester 1",
"Sem-1", "Year 1 Sem 1" etc. all sort correctly); sessions without a
number sort alphabetically after the numbered ones.
"""

import re
from calc_engine import compute_cgpa


def _semester_sort_key(session_name):
    match = re.search(r"(\d+)", session_name)
    if match:
        return (0, int(match.group(1)), session_name)
    return (1, 0, session_name)


def build_transcript(results_by_session):
    """
    results_by_session: {session_name: {exam_name: computed_row}}
    Returns: {
        "semesters": [ {session_name, gpa, percentage, exams: [...]} , ... ] (sorted),
        "cgpa": float,
        "total_semesters": int,
    }
    """
    semesters = []

    for session_name, exams in results_by_session.items():
        if not exams:
            continue
        gpas = [row.get("gpa", 0) for row in exams.values()]
        pcts = [row.get("percentage", 0) for row in exams.values()]
        attendances = [row.get("attendance") for row in exams.values() if row.get("attendance") is not None]

        exam_list = []
        for exam_name, row in exams.items():
            exam_list.append({
                "exam_name": exam_name,
                "percentage": row.get("percentage"),
                "grade": row.get("grade"),
                "gpa": row.get("gpa"),
                "total_obtained": row.get("total_obtained"),
                "total_max": row.get("total_max"),
                "attendance": row.get("attendance"),
                "rank": row.get("rank"),
            })

        semesters.append({
            "session_name": session_name,
            "gpa": round(sum(gpas) / len(gpas), 2) if gpas else 0,
            "percentage": round(sum(pcts) / len(pcts), 2) if pcts else 0,
            "average_attendance": round(sum(attendances) / len(attendances), 2) if attendances else None,
            "exams": sorted(exam_list, key=lambda e: e["exam_name"]),
        })

    semesters.sort(key=lambda s: _semester_sort_key(s["session_name"]))

    cgpa = compute_cgpa([s["gpa"] for s in semesters])

    return {
        "semesters": semesters,
        "cgpa": cgpa,
        "total_semesters": len(semesters),
    }
