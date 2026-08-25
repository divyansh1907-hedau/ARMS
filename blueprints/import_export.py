"""
Robust Data Import/Export
---------------------------
Bulk import of student marks from Excel (.xlsx) or CSV, and export of
computed sheets back out to Excel/CSV.

Expected import format (first row = header):
student_id | name | <Subject 1> | <Subject 2> | ...
"""

import io

import pandas as pd
from flask import Blueprint, request, jsonify, send_file

from blueprints.auth import login_required

import_bp = Blueprint("import_export", __name__)


@import_bp.route("/api/import/sheet", methods=["POST"])
@login_required
def import_sheet():
    file = request.files.get("file")
    if not file:
        return jsonify({"error": "no file uploaded"}), 400

    filename = file.filename.lower()
    try:
        if filename.endswith(".csv"):
            df = pd.read_csv(file)
        elif filename.endswith((".xlsx", ".xls")):
            df = pd.read_excel(file)
        else:
            return jsonify({"error": "unsupported file type, use .csv or .xlsx"}), 400
    except Exception as exc:
        return jsonify({"error": f"could not parse file: {exc}"}), 400

    if "student_id" not in df.columns or "name" not in df.columns:
        return jsonify({"error": "file must include 'student_id' and 'name' columns"}), 400

    subject_cols = [c for c in df.columns if c not in ("student_id", "name")]
    students = []
    for _, r in df.iterrows():
        marks = {col: r[col] for col in subject_cols}
        students.append({
            "student_id": str(r["student_id"]),
            "name": str(r["name"]),
            "marks": marks,
        })

    subjects = [{"name": c, "max_marks": 100, "weight": 1.0} for c in subject_cols]
    return jsonify({"students": students, "subjects": subjects})


@import_bp.route("/api/export/sheet", methods=["POST"])
@login_required
def export_sheet():
    """Export a computed sheet (list of rows from calc_engine) back to Excel or CSV."""
    payload = request.get_json(force=True)
    rows = payload.get("rows", [])
    fmt = payload.get("format", "xlsx")

    flat = []
    for row in rows:
        entry = {
            "student_id": row["student_id"],
            "name": row["name"],
            "total": row["total_obtained"],
            "percentage": row["percentage"],
            "grade": row["grade"],
            "gpa": row["gpa"],
            "rank": row.get("rank"),
        }
        for subj_name, subj in row.get("subjects", {}).items():
            entry[subj_name] = subj["score"]
        flat.append(entry)

    df = pd.DataFrame(flat)
    buf = io.BytesIO()

    if fmt == "csv":
        df.to_csv(buf, index=False)
        buf.seek(0)
        return send_file(buf, mimetype="text/csv", as_attachment=True,
                          download_name="results_export.csv")

    df.to_excel(buf, index=False, engine="openpyxl")
    buf.seek(0)
    return send_file(buf, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                      as_attachment=True, download_name="results_export.xlsx")
