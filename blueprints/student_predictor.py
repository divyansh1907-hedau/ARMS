"""
Student Predictor Module (student_predictor.py)
--------------------------------------------------
NEW FEATURE — Attendance-Linked Risk Prediction
--------------------------------------------------
Originally this module only flagged a student as "at risk" once they had
accumulated 2+ subject failures. That catches trouble only after it has
already happened in the gradebook.

This version combines academic performance WITH attendance into a single
weighted risk score, because low attendance is one of the earliest and
strongest real-world predictors of failure — often visible weeks before
grades actually drop. A student can now be flagged as at-risk purely from
a sustained attendance drop, even while still passing on paper.

risk_score (0-100, higher = more risk):
    risk_score = 0.55 * (100 - avg_percentage) + 0.45 * (100 - avg_attendance)

risk_level:
    >= 60  -> High
    >= 35  -> Medium
    else   -> Low
"""

import config

FAIL_GRADE = "F"

ATTENDANCE_WEIGHT = 0.45
PERFORMANCE_WEIGHT = 0.55

DEFAULT_ATTENDANCE_IF_MISSING = 100  # assume full attendance if never recorded


def _risk_level(score):
    if score >= 60:
        return "High"
    if score >= 35:
        return "Medium"
    return "Low"


def analyse_student_performance(results_by_session):
    """
    results_by_session: {session_name: {exam_name: computed_row}}
    computed_row has "subjects": {name: {"grade": ..., "percentage": ...}},
    "percentage" (overall), and optionally "attendance" (0-100).
    """
    fail_count = 0
    weak_subjects = {}
    all_percentages = []
    all_attendance = []

    for session_name, exams in results_by_session.items():
        for exam_name, row in exams.items():
            all_percentages.append(row.get("percentage", 0))
            if row.get("attendance") is not None:
                all_attendance.append(row["attendance"])
            for subj_name, subj in row.get("subjects", {}).items():
                if subj.get("grade") == FAIL_GRADE:
                    fail_count += 1
                    weak_subjects[subj_name] = weak_subjects.get(subj_name, 0) + 1

    avg_percentage = round(sum(all_percentages) / len(all_percentages), 2) if all_percentages else 0
    avg_attendance = (
        round(sum(all_attendance) / len(all_attendance), 2)
        if all_attendance else DEFAULT_ATTENDANCE_IF_MISSING
    )

    risk_score = round(
        PERFORMANCE_WEIGHT * (100 - avg_percentage) + ATTENDANCE_WEIGHT * (100 - avg_attendance), 1
    )
    risk_level = _risk_level(risk_score)

    # Hard override: most colleges require ~75% minimum attendance for exam
    # eligibility, so a student below that is at real academic risk even
    # with strong grades — bump the level regardless of the weighted score.
    if avg_attendance < 65:
        risk_level = "High"
    elif avg_attendance < 75 and risk_level == "Low":
        risk_level = "Medium"

    # Backward-compatible boolean flag, now driven by the combined score
    # instead of fail-count alone, so an attendance crash triggers it too.
    is_at_risk = risk_level in ("High", "Medium")

    trend = "stable"
    if len(all_percentages) >= 2:
        if all_percentages[-1] < all_percentages[0] - 5:
            trend = "declining"
        elif all_percentages[-1] > all_percentages[0] + 5:
            trend = "improving"

    attendance_trend = "stable"
    if len(all_attendance) >= 2:
        if all_attendance[-1] < all_attendance[0] - 5:
            attendance_trend = "declining"
        elif all_attendance[-1] > all_attendance[0] + 5:
            attendance_trend = "improving"

    risk_drivers = []
    if avg_attendance < 75:
        risk_drivers.append(f"low attendance ({avg_attendance}%)")
    if fail_count > 0:
        risk_drivers.append(f"{fail_count} subject failure(s)")
    if avg_percentage < 40:
        risk_drivers.append(f"low average score ({avg_percentage}%)")
    if attendance_trend == "declining":
        risk_drivers.append("declining attendance trend")

    return {
        "is_at_risk": is_at_risk,
        "risk_score": risk_score,
        "risk_level": risk_level,
        "risk_drivers": risk_drivers,
        "fail_count": fail_count,
        "weak_subjects": sorted(weak_subjects, key=weak_subjects.get, reverse=True),
        "trend": trend,
        "attendance_trend": attendance_trend,
        "average_percentage": avg_percentage,
        "average_attendance": avg_attendance,
    }


def class_at_risk_list(students_coll):
    """Used by the teacher dashboard: which students in this class need help."""
    at_risk = []
    for student in students_coll.find():
        analysis = analyse_student_performance(student.get("results", {}))
        if analysis["is_at_risk"]:
            at_risk.append({
                "college_id": student["college_id"],
                "name": student.get("name"),
                **analysis,
            })
    at_risk.sort(key=lambda s: s["risk_score"], reverse=True)
    return at_risk


def live_at_risk_preview(computed_rows):
    """
    Lightweight risk preview computed directly from an unpublished sheet
    (a single exam's worth of rows), so the teacher gets instant feedback
    in the Sheet Editor without needing to Publish first.
    """
    preview = []
    for row in computed_rows:
        pct = row.get("percentage", 0)
        attendance = row.get("attendance")
        attendance = attendance if attendance is not None else DEFAULT_ATTENDANCE_IF_MISSING
        score = round(PERFORMANCE_WEIGHT * (100 - pct) + ATTENDANCE_WEIGHT * (100 - attendance), 1)
        level = _risk_level(score)
        if attendance < 65:
            level = "High"
        elif attendance < 75 and level == "Low":
            level = "Medium"
        if level in ("High", "Medium"):
            preview.append({
                "student_id": row.get("student_id"),
                "name": row.get("name"),
                "risk_score": score,
                "risk_level": level,
                "percentage": pct,
                "attendance": row.get("attendance"),
            })
    preview.sort(key=lambda s: s["risk_score"], reverse=True)
    return preview
