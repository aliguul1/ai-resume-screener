"""
Application configuration and global constants.
"""
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

DB_PATH = BASE_DIR / "screener.db"
UPLOAD_DIR = BASE_DIR / "uploads"

ALLOWED_EXTENSIONS = {"pdf"}
MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10 MB

# Valid 2026 production model
AI_MODEL = "gpt-4o-mini"
PROMPT_VERSION = "v2"