"""
Automated Calculation Engine
-----------------------------
Given a project's grading scheme and a sheet of raw marks, computes:
  - subject-wise weighted score
  - total / percentage
  - letter grade + grade point (per subject and overall)
  - GPA (average grade point across subjects)
  - CGPA (average GPA across saved sessions/exams for a student)
  - absolute rank and percentile within the class

This is intentionally backend/framework agnostic so it can be unit tested
and reused by result_handler.py and pdf_exporter.py alike.
"""

import config


def grade_for_percentage(pct, scale=None):
    scale = scale or config.DEFAULT_GRADE_SCALE
    for threshold, letter, point in sorted(scale, key=lambda x: -x[0]):
        if pct >= threshold:
            return letter, point
    return "F", 0


def compute_student_row(student, subjects, scale=None):
    """
    student: {"student_id": ..., "name": ..., "marks": {subject_name: score},
              "attendance": 0-100 (optional)}
    subjects: [{"name": ..., "max_marks": 100, "weight": 1.0}, ...]
    Returns an enriched row with totals/percentage/grade/gpa/attendance.
    """
    total_obtained = 0.0
    total_max = 0.0
    weighted_points = 0.0
    total_weight = 0.0
    subject_results = {}

    for subj in subjects:
        name = subj["name"]
        max_marks = float(subj.get("max_marks", 100))
        weight = float(subj.get("weight", 1.0))
        score = float(student.get("marks", {}).get(name, 0) or 0)

        pct = (score / max_marks * 100) if max_marks else 0
        letter, point = grade_for_percentage(pct, scale)

        subject_results[name] = {
            "score": score,
            "max_marks": max_marks,
            "percentage": round(pct, 2),
            "grade": letter,
            "grade_point": point,
        }

        total_obtained += score * weight
        total_max += max_marks * weight
        weighted_points += point * weight
        total_weight += weight

    overall_pct = (total_obtained / total_max * 100) if total_max else 0
    overall_letter, _ = grade_for_percentage(overall_pct, scale)
    gpa = round(weighted_points / total_weight, 2) if total_weight else 0.0

    attendance = student.get("attendance")
    try:
        attendance = round(float(attendance), 1) if attendance not in (None, "") else None
    except (TypeError, ValueError):
        attendance = None

    return {
        "student_id": student.get("student_id"),
        "name": student.get("name"),
        "subjects": subject_results,
        "total_obtained": round(total_obtained, 2),
        "total_max": round(total_max, 2),
        "percentage": round(overall_pct, 2),
        "grade": overall_letter,
        "gpa": gpa,
        "attendance": attendance,
    }


def compute_sheet(students, subjects, scale=None):
    """Compute all rows, then attach rank + percentile based on percentage."""
    rows = [compute_student_row(s, subjects, scale) for s in students]
    ranked = sorted(rows, key=lambda r: r["percentage"], reverse=True)

    n = len(ranked)
    for i, row in enumerate(ranked):
        row["rank"] = i + 1
        row["percentile"] = round((n - row["rank"]) / n * 100, 2) if n > 1 else 100.0

    # restore original student order for display, ranks already attached
    order = {s.get("student_id"): idx for idx, s in enumerate(students)}
    ranked.sort(key=lambda r: order.get(r["student_id"], 0))
    return ranked


def compute_cgpa(session_gpas):
    """session_gpas: list of GPA floats across saved exams/sessions."""
    if not session_gpas:
        return 0.0
    return round(sum(session_gpas) / len(session_gpas), 2)


def class_statistics(rows):
    """Mean, median, std-dev of class percentages — for teacher dashboards."""
    if not rows:
        return {"mean": 0, "median": 0, "std_dev": 0, "highest": 0, "lowest": 0}
    pcts = sorted(r["percentage"] for r in rows)
    n = len(pcts)
    mean = sum(pcts) / n
    median = pcts[n // 2] if n % 2 else (pcts[n // 2 - 1] + pcts[n // 2]) / 2
    variance = sum((p - mean) ** 2 for p in pcts) / n
    std_dev = variance ** 0.5
    return {
        "mean": round(mean, 2),
        "median": round(median, 2),
        "std_dev": round(std_dev, 2),
        "highest": round(pcts[-1], 2),
        "lowest": round(pcts[0], 2),
    }
