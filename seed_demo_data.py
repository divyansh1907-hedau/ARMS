"""
Seed Demo Academic Data
--------------------------
Populates 10 students with a full Semester 1 -> 8 academic history each,
using realistic, VARIED profiles so you can properly test:
  - the Full Academic Record / transcript feature (student + teacher side)
  - the attendance-linked risk predictor (Low/Medium/High)
  - CGPA trend charts (improving / declining / stable)

Run this once from inside the sram_system folder:

    python seed_demo_data.py

It writes directly into data/students.json (safe to re-run -- it just
upserts these 10 students; it won't touch any other students you've
created). Then log in as a teacher (T001 / teacher123) and use
"View Academic Records" to search any of the IDs below, or log in as
one of the students directly (mother's name is always "Demo Mother").
"""

import random

from db import get_collection
from calc_engine import compute_sheet

random.seed(42)

SUBJECTS = [
    {"name": "Data Structures", "max_marks": 100, "weight": 1.0},
    {"name": "Mathematics", "max_marks": 100, "weight": 1.0},
    {"name": "Computer Networks", "max_marks": 100, "weight": 1.0},
]


def high_performer(sem):
    base = 78 + sem
    marks = {s["name"]: min(98, base + random.randint(-4, 6)) for s in SUBJECTS}
    attendance = min(98, 88 + sem)
    return marks, attendance


def low_performer(sem):
    base = 30 + sem
    marks = {s["name"]: max(10, base + random.randint(-8, 5)) for s in SUBJECTS}
    attendance = max(45, 60 - sem)
    return marks, attendance


def declining(sem):
    base = 85 - sem * 5
    marks = {s["name"]: max(20, base + random.randint(-5, 5)) for s in SUBJECTS}
    attendance = max(50, 92 - sem * 5)
    return marks, attendance


def improving(sem):
    base = 35 + sem * 6
    marks = {s["name"]: min(92, base + random.randint(-4, 6)) for s in SUBJECTS}
    attendance = min(95, 60 + sem * 4)
    return marks, attendance


def good_grades_bad_attendance(sem):
    marks = {s["name"]: 75 + random.randint(-5, 10) for s in SUBJECTS}
    attendance = 50 + random.randint(-5, 5)
    return marks, attendance


def average_steady(sem):
    marks = {s["name"]: 60 + random.randint(-6, 8) for s in SUBJECTS}
    attendance = 80 + random.randint(-5, 5)
    return marks, attendance


def borderline_attendance(sem):
    marks = {s["name"]: 65 + random.randint(-8, 8) for s in SUBJECTS}
    attendance = 73 + random.randint(-3, 3)
    return marks, attendance


def mixed_pass_fail(sem):
    if sem % 3 == 0:
        marks = {s["name"]: 25 + random.randint(0, 10) for s in SUBJECTS}
        attendance = 55
    else:
        marks = {s["name"]: 70 + random.randint(-5, 10) for s in SUBJECTS}
        attendance = 85
    return marks, attendance


def one_bad_semester(sem):
    if sem == 5:
        marks = {s["name"]: 20 + random.randint(0, 10) for s in SUBJECTS}
        attendance = 45
    else:
        marks = {s["name"]: 82 + random.randint(-5, 8) for s in SUBJECTS}
        attendance = 90
    return marks, attendance


def boundary_grades(sem):
    boundary = [40, 50, 60, 70, 33, 60, 80, 40][sem - 1]
    marks = {s["name"]: boundary + random.randint(-1, 1) for s in SUBJECTS}
    attendance = 76
    return marks, attendance


STUDENTS = [
    ("S2001", "Ravi Kulkarni",   high_performer),
    ("S2002", "Meera Joshi",     low_performer),
    ("S2003", "Aarav Deshmukh",  declining),
    ("S2004", "Priya Nair",      improving),
    ("S2005", "Karan Malhotra",  good_grades_bad_attendance),
    ("S2006", "Sneha Patil",     average_steady),
    ("S2007", "Yash Choudhary",  borderline_attendance),
    ("S2008", "Isha Reddy",      mixed_pass_fail),
    ("S2009", "Rohan Kapoor",    one_bad_semester),
    ("S2010", "Divya Menon",     boundary_grades),
]

MOTHER_NAME = "Demo Mother"


def seed():
    students_coll = get_collection("students")

    for college_id, name, profile_fn in STUDENTS:
        results = {}
        for sem in range(1, 9):
            marks, attendance = profile_fn(sem)
            student_payload = [{
                "student_id": college_id,
                "name": name,
                "marks": marks,
                "attendance": attendance,
            }]
            rows = compute_sheet(student_payload, SUBJECTS)
            row = rows[0]
            results[f"Semester {sem}"] = {"Finals": row}

        existing = students_coll.find_one({"college_id": college_id})
        if existing:
            students_coll.update_one(
                {"college_id": college_id},
                {"$set": {"name": name, "mother_name": MOTHER_NAME, "results": results}},
            )
        else:
            students_coll.insert_one({
                "college_id": college_id,
                "name": name,
                "mother_name": MOTHER_NAME,
                "results": results,
            })
        print(f"Seeded {college_id} ({name}) - 8 semesters.")

    print("\nDone! Log in as any student above with Mother's Name = 'Demo Mother',")
    print("or log in as teacher T001/teacher123 and use 'View Academic Records'.")
    print("\nStudent IDs: " + ", ".join(s[0] for s in STUDENTS))


if __name__ == "__main__":
    seed()
