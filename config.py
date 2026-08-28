import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent

RESUME_DIRECTORY = Path(
    os.getenv("RESUME_DIRECTORY", str(BASE_DIR / "resumes"))
).resolve()

WATCH_INTERVAL = float(os.getenv("WATCH_INTERVAL", "1.0"))
MAX_BATCH_FILES = int(os.getenv("MAX_BATCH_FILES", "50"))

ALLOWED_EXTENSIONS = {
    ".txt",
    ".pdf",
    ".docx",
}
