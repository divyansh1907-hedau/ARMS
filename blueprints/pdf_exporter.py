"""
PDF Exporter Module (pdf_exporter.py)
----------------------------------------
Generates report cards / mark sheets as downloadable PDFs.

Note: the thesis uses WeasyPrint (HTML/CSS -> PDF) with a bleach CSS
sanitizer. WeasyPrint needs system-level Cairo/Pango libraries that aren't
guaranteed on every machine, so this build uses ReportLab (pure Python,
no system deps) to draw the PDF directly. Output and layout are equivalent;
swap this module for a WeasyPrint version if you want literal parity with
the thesis's implementation.
"""

import io

from flask import Blueprint, request, send_file, session

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
)
from reportlab.lib.styles import getSampleStyleSheet

from blueprints.auth import login_required, student_login_required
from db import get_collection
from transcript import build_transcript

pdf_bp = Blueprint("pdf", __name__)
styles = getSampleStyleSheet()


def _report_elements(student_name, student_id, session_name, exam_name, row):
    elements = []
    elements.append(Paragraph("Academic Record and Management System", styles["Title"]))
    elements.append(Paragraph("Report Card", styles["Heading2"]))
    elements.append(Spacer(1, 8))
    elements.append(Paragraph(f"Name: {student_name} &nbsp;&nbsp; ID: {student_id}", styles["Normal"]))
    elements.append(Paragraph(f"Session: {session_name} &nbsp;&nbsp; Exam: {exam_name}", styles["Normal"]))
    elements.append(Spacer(1, 12))

    table_data = [["Subject", "Marks", "Max", "%", "Grade"]]
    for subj_name, subj in row.get("subjects", {}).items():
        table_data.append([
            subj_name, subj["score"], subj["max_marks"], f"{subj['percentage']}%", subj["grade"]
        ])
    table_data.append(["TOTAL", row["total_obtained"], row["total_max"],
                        f"{row['percentage']}%", row["grade"]])

    table = Table(table_data, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c3e50")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#ecf0f1")),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ALIGN", (1, 0), (-1, -1), "CENTER"),
    ]))
    elements.append(table)
    elements.append(Spacer(1, 16))
    elements.append(Paragraph(f"Rank in class: {row.get('rank', '-')}", styles["Normal"]))
    elements.append(Paragraph(f"GPA: {row.get('gpa', '-')}", styles["Normal"]))
    if row.get("attendance") is not None:
        elements.append(Paragraph(f"Attendance: {row.get('attendance')}%", styles["Normal"]))
    return elements


def _build_report_pdf(student_name, student_id, session_name, exam_name, row):
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=20 * mm)
    elements = _report_elements(student_name, student_id, session_name, exam_name, row)
    doc.build(elements)
    buf.seek(0)
    return buf


@pdf_bp.route("/api/pdf/report/<college_id>/<session_name>/<exam_name>")
@login_required
def export_report(college_id, session_name, exam_name):
    students_coll = get_collection("students")
    student = students_coll.find_one({"college_id": college_id})
    if not student:
        return {"error": "not found"}, 404
    row = student.get("results", {}).get(session_name, {}).get(exam_name)
    if not row:
        return {"error": "result not found"}, 404

    buf = _build_report_pdf(student.get("name", college_id), college_id,
                             session_name, exam_name, row)
    return send_file(buf, mimetype="application/pdf", as_attachment=True,
                      download_name=f"{college_id}_{session_name}_{exam_name}_report.pdf")


@pdf_bp.route("/student/api/pdf/my-report/<session_name>/<exam_name>")
@student_login_required
def export_my_report(session_name, exam_name):
    college_id = session["college_id"]
    students_coll = get_collection("students")
    student = students_coll.find_one({"college_id": college_id})
    row = student.get("results", {}).get(session_name, {}).get(exam_name)
    if not row:
        return {"error": "result not found"}, 404

    buf = _build_report_pdf(student.get("name", college_id), college_id,
                             session_name, exam_name, row)
    return send_file(buf, mimetype="application/pdf", as_attachment=True,
                      download_name=f"{session_name}_{exam_name}_report.pdf")


@pdf_bp.route("/api/pdf/preview", methods=["POST"])
@login_required
def preview_pdf():
    """Generate a PDF directly from an already-computed row (no publish needed)."""
    payload = request.get_json(force=True)
    row = payload["row"]
    project_title = payload.get("project_title", "Project")
    buf = _build_report_pdf(row.get("name", ""), row.get("student_id", ""),
                             project_title, "Preview", row)
    return send_file(buf, mimetype="application/pdf", as_attachment=True,
                      download_name=f"{row.get('student_id','student')}_report.pdf")


@pdf_bp.route("/api/pdf/preview-bulk", methods=["POST"])
@login_required
def preview_pdf_bulk():
    """Generate one combined multi-page PDF, one report card per student."""
    payload = request.get_json(force=True)
    rows = payload["rows"]
    project_title = payload.get("project_title", "Project")

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=20 * mm)
    all_elements = []
    for i, row in enumerate(rows):
        all_elements.extend(_report_elements(row.get("name", ""), row.get("student_id", ""),
                                              project_title, "Preview", row))
        if i < len(rows) - 1:
            from reportlab.platypus import PageBreak
            all_elements.append(PageBreak())

    doc.build(all_elements)
    buf.seek(0)
    return send_file(buf, mimetype="application/pdf", as_attachment=True,
                      download_name=f"{project_title}_all_reports.pdf")


def _transcript_elements(student_name, student_id, transcript):
    elements = []
    elements.append(Paragraph("Academic Record and Management System", styles["Title"]))
    elements.append(Paragraph("Full Academic Transcript", styles["Heading2"]))
    elements.append(Spacer(1, 8))
    elements.append(Paragraph(f"Name: {student_name} &nbsp;&nbsp; ID: {student_id}", styles["Normal"]))
    elements.append(Spacer(1, 12))

    table_data = [["Semester", "Exam", "%", "Grade", "GPA", "Attendance"]]
    for sem in transcript["semesters"]:
        for exam in sem["exams"]:
            table_data.append([
                sem["session_name"], exam["exam_name"], f"{exam['percentage']}%",
                exam["grade"], exam["gpa"],
                f"{exam['attendance']}%" if exam.get("attendance") is not None else "-",
            ])

    table = Table(table_data, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c3e50")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ALIGN", (2, 0), (-1, -1), "CENTER"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
    ]))
    elements.append(table)
    elements.append(Spacer(1, 16))
    elements.append(Paragraph(f"Overall CGPA (across {transcript['total_semesters']} semesters): "
                               f"<b>{transcript['cgpa']}</b>", styles["Normal"]))
    return elements


@pdf_bp.route("/api/pdf/transcript/<college_id>")
@login_required
def transcript_pdf_teacher(college_id):
    """NEW FEATURE: full Semester 1-8 transcript PDF, teacher access."""
    students_coll = get_collection("students")
    student = students_coll.find_one({"college_id": college_id})
    if not student:
        return {"error": "not found"}, 404
    transcript = build_transcript(student.get("results", {}))
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=20 * mm)
    doc.build(_transcript_elements(student.get("name", college_id), college_id, transcript))
    buf.seek(0)
    return send_file(buf, mimetype="application/pdf", as_attachment=True,
                      download_name=f"{college_id}_full_transcript.pdf")


@pdf_bp.route("/student/api/pdf/my-transcript")
@student_login_required
def transcript_pdf_student():
    college_id = session["college_id"]
    students_coll = get_collection("students")
    student = students_coll.find_one({"college_id": college_id})
    transcript = build_transcript(student.get("results", {}))
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=20 * mm)
    doc.build(_transcript_elements(student.get("name", college_id), college_id, transcript))
    buf.seek(0)
    return send_file(buf, mimetype="application/pdf", as_attachment=True,
                      download_name="my_full_transcript.pdf")
