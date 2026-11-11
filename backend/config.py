"""Application configuration, loaded from environment variables (.env)."""
import os

from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)
load_dotenv(os.path.join(ROOT_DIR, ".env"))


class Config:
    DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
    DB_PORT = int(os.getenv("DB_PORT", "3306"))
    DB_USER = os.getenv("DB_USER", "root")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "")
    DB_NAME = os.getenv("DB_NAME", "crispy_king_db")

    SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "dev-secret-change-me")
    DEBUG = os.getenv("FLASK_DEBUG", "True").lower() == "true"
    PORT = int(os.getenv("FLASK_PORT", "5000"))

    # Tax rate, currency, business name etc. are NOT here — they live in the
    # `settings` DB table (see utils/settings.py) so they're editable live
    # from the Settings tab instead of requiring an env edit + restart.

    FRONTEND_DIR = os.path.join(ROOT_DIR, "frontend")
