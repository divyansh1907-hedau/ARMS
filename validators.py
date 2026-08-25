"""
Real-time Data Integrity Checks
--------------------------------
Validates uploaded/typed marks against project rules before results are
finalized, per Chapter 2.3 objective 5 of the thesis.
"""

import re

STUDENT_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{3,20}$")


def validate_sheet(students, subjects):
    """
    Returns a list of human-readable issues. Empty list = clean sheet.
    """
    issues = []
    max_by_subject = {s["name"]: float(s.get("max_marks", 100)) for s in subjects}
    seen_ids = set()

    for row_idx, student in enumerate(students, start=1):
        sid = str(student.get("student_id", "")).strip()
        name = str(student.get("name", "")).strip()

        if not sid or not STUDENT_ID_PATTERN.match(sid):
            issues.append(f"Row {row_idx}: invalid or missing student ID ('{sid}').")
        elif sid in seen_ids:
            issues.append(f"Row {row_idx}: duplicate student ID '{sid}'.")
        else:
            seen_ids.add(sid)

        if not name:
            issues.append(f"Row {row_idx} ({sid}): missing student name.")

        marks = student.get("marks", {})
        for subj_name, max_marks in max_by_subject.items():
            if subj_name not in marks:
                issues.append(f"Row {row_idx} ({sid}): missing marks for '{subj_name}'.")
                continue
            val = marks[subj_name]
            try:
                val = float(val)
            except (TypeError, ValueError):
                issues.append(f"Row {row_idx} ({sid}): non-numeric mark for '{subj_name}'.")
                continue
            if val < 0:
                issues.append(f"Row {row_idx} ({sid}): negative mark for '{subj_name}'.")
            if val > max_marks:
                issues.append(
                    f"Row {row_idx} ({sid}): '{subj_name}' score {val} exceeds max {max_marks}."
                )

        attendance = student.get("attendance")
        if attendance not in (None, ""):
            try:
                att_val = float(attendance)
                if att_val < 0 or att_val > 100:
                    issues.append(f"Row {row_idx} ({sid}): attendance {att_val} must be between 0-100.")
            except (TypeError, ValueError):
                issues.append(f"Row {row_idx} ({sid}): non-numeric attendance value.")

    return issues
