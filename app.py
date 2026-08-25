"""
ARMS - Academic Record and Management System
------------------------------------------------------
Entry point. Run with:  python app.py
Then open http://127.0.0.1:5000

Demo login:
  Teacher -> ID: T001   password: teacher123
  Student -> College ID: S1001   Mother's name: Sunita Rao
"""

import os

from flask import Flask

import config
from blueprints.auth import auth_bp, seed_default_users
from blueprints.project_handler import project_bp
from blueprints.result_handler import result_bp
from blueprints.chatbot_handler import chatbot_bp
from blueprints.pdf_exporter import pdf_bp
from blueprints.import_export import import_bp


def create_app():
    app = Flask(__name__)
    app.secret_key = config.SECRET_KEY

    os.makedirs(config.DATA_DIR, exist_ok=True)
    os.makedirs(config.PROJECTS_DIR, exist_ok=True)
    os.makedirs(config.LOG_DIR, exist_ok=True)

    app.register_blueprint(auth_bp)
    app.register_blueprint(project_bp)
    app.register_blueprint(result_bp)
    app.register_blueprint(chatbot_bp)
    app.register_blueprint(pdf_bp)
    app.register_blueprint(import_bp)

    with app.app_context():
        seed_default_users()

    return app


app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "1") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug)
