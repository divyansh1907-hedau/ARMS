# ARMS — Academic Record and Management System

Rebuilt from the thesis "Academic Record and Management System"
(Priyadarshini College of Engineering, Nagpur). Full working Flask app —
runs out of the box with zero external services.

## What's included (matches the thesis modules)

| Thesis module              | File                                  |
|-----------------------------|----------------------------------------|
| Authentication Module       | `blueprints/auth.py`                  |
| Project Handler Module      | `blueprints/project_handler.py`       |
| Result Handler Module       | `blueprints/result_handler.py`        |
| PDF Exporter Module         | `blueprints/pdf_exporter.py`          |
| Chatbot Handler Module      | `blueprints/chatbot_handler.py`       |
| Student Predictor Module    | `blueprints/student_predictor.py`     |
| Data Import/Export          | `blueprints/import_export.py`         |
| Calculation Engine          | `calc_engine.py`                      |
| Data Integrity Validation   | `validators.py`                       |

## Quick start

```bash
pip install -r requirements.txt
python app.py
```

Open **http://127.0.0.1:5000**

**Demo logins** (auto-seeded on first run):
- Teacher: ID `T001`, password `teacher123`
- Student: College ID `S1001`, Mother's name `Sunita Rao`

## How to use it

1. Log in as the teacher.
2. Create a new Project (e.g. `sem8-2026` / "Semester 8 Finals").
3. Add subjects and student rows (or import an .xlsx/.csv with
   `student_id, name, <subject columns>`).
4. Click **Save** — totals, %, grade, GPA, rank, and class stats compute
   automatically, and any data issues (missing marks, over-max scores,
   duplicate IDs) are flagged.
5. Click **Publish Results** to push the finalized sheet into each
   student's result history.
6. Ask the Edu-AI assistant about the class (e.g. "who is at risk?").
7. Log out, log in as the student, and view the published result, CGPA,
   download a PDF report card, and chat with Edu-AI about it.

## Differences from the literal thesis spec (and why)

This sandbox has no internet access and no MongoDB/Gemini services running,
so the build swaps in offline-equivalent, zero-dependency implementations
that preserve the same architecture and are drop-in upgradeable:

- **MongoDB → JSON file store** (`db.py`). Every blueprint calls
  `get_collection("teachers"/"students")` exactly as it would against
  pymongo. Set `config.USE_MONGO = True` + install `pymongo` + run a local
  `mongod` to switch to real MongoDB with no other code changes.
- **bcrypt → werkzeug.security (PBKDF2-SHA256)** for password hashing —
  already a Flask dependency, same security properties, no extra install.
- **WeasyPrint → ReportLab** for PDF generation — WeasyPrint needs system
  Cairo/Pango libraries; ReportLab is pure Python and needs nothing extra.
- **Gemini API — live-if-configured, offline fallback otherwise**
  (`blueprints/chatbot_handler.py`). Set the `GEMINI_API_KEY` environment
  variable and `pip install google-generativeai` to get real AI responses;
  without a key the chatbot answers from the same cached context files
  using simple rules, so the whole app is demoable offline.

## Project structure

```
sram_system/
├── app.py                  # entry point
├── config.py               # all settings in one place
├── db.py                   # storage abstraction (JSON store / Mongo)
├── calc_engine.py          # grading calculations
├── validators.py           # data integrity checks
├── blueprints/
│   ├── auth.py
│   ├── project_handler.py
│   ├── result_handler.py
│   ├── pdf_exporter.py
│   ├── chatbot_handler.py
│   ├── student_predictor.py
│   └── import_export.py
├── templates/               # Jinja2 HTML
├── static/                  # CSS + JS (spreadsheet editor, chatbot widget)
├── data/                    # JSON "database" + AI context files
└── logs/                    # auth logs
```

## Adding your guide's "new feature"

The architecture is deliberately modular so a new capability drops in as
its own blueprint + a hook into `calc_engine.py` / `student_predictor.py`.
Ready when you are — just tell me which feature to build next
(e.g. attendance-linked risk scoring, AI study-plan generator, parent
email digests, marks-anomaly detection, or an analytics dashboard v2).
