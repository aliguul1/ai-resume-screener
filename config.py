from pathlib import Path

BASE_DIR = Path(__file__).parent

DB_PATH = BASE_DIR / "screener.db"
UPLOAD_DIR = BASE_DIR / "uploads"

ALLOWED_EXTENSIONS = {"pdf"}

MAX_UPLOAD_SIZE = 10 * 1024 * 1024

AI_MODEL = "gpt-4.1-mini"
PROMPT_VERSION = "v1"