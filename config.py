"""
ARMS Configuration
--------------------
This project ships with a zero-dependency JSON file "database" so it runs
immediately with no MongoDB server and no external API key. To move to the
production stack described in the thesis (MongoDB + Google Gemini), just:

  1. pip install pymongo google-generativeai
  2. Set USE_MONGO = True and fill MONGO_URI below
  3. Set GEMINI_API_KEY (or export it as an env var) — the chatbot module
     will automatically switch from its offline canned-response mode to
     live Gemini calls as soon as a key is present and the package is
     installed.
"""

import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ---- Security ----
SECRET_KEY = os.environ.get("SRAMS_SECRET_KEY", "dev-secret-change-me")

# ---- Storage backend ----
# False -> uses the built-in JSON file store in db.py (works out of the box)
# True  -> uses MongoDB via pymongo (requires pymongo + a running mongod)
USE_MONGO = False
MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017/")
MONGO_DB_NAME = "sram_system"

# JSON store location (used when USE_MONGO = False)
DATA_DIR = os.path.join(BASE_DIR, "data")
PROJECTS_DIR = os.path.join(DATA_DIR, "projects")
TEACHERS_FILE = os.path.join(DATA_DIR, "teachers.json")
STUDENTS_FILE = os.path.join(DATA_DIR, "students.json")

# ---- Logging ----
LOG_DIR = os.path.join(BASE_DIR, "logs")
TEACHER_AUTH_LOG = os.path.join(LOG_DIR, "teacher_auth.log")
STUDENT_AUTH_LOG = os.path.join(LOG_DIR, "student_auth.log")

# ---- Sheet cache (feeds the teacher chatbot with live context) ----
SHEET_CACHE_FILE = os.path.join(DATA_DIR, "sheet_cache.txt")
PROJECT_OVERVIEW_FILE = os.path.join(DATA_DIR, "project_overview.txt")
SYSTEM_ANALYSIS_FILE = os.path.join(DATA_DIR, "system_analysis.txt")
PROJECTS_ANALYSIS_FILE = os.path.join(DATA_DIR, "projects_analysis.txt")

# ---- Gemini AI ----
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
# Older flash models (1.5, 2.0) were retired by Google; use a current flash
# model so live AI calls actually engage instead of silently degrading to
# offline mode. If the primary model is unavailable/retired, the chatbot
# retries once with GEMINI_FALLBACK_MODEL before going offline.
GEMINI_MODEL = "gemini-3.6-flash"
GEMINI_FALLBACK_MODEL = "gemini-flash-latest"

# ---- Grading defaults (customizable per project) ----
DEFAULT_GRADE_SCALE = [
    (90, "A+", 10),
    (80, "A", 9),
    (70, "B+", 8),
    (60, "B", 7),
    (50, "C+", 6),
    (40, "C", 5),
    (33, "D", 4),
    (0, "F", 0),
]

# At-risk predictor threshold
AT_RISK_FAIL_COUNT = 2
