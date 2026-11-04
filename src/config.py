import os
from pathlib import Path
from dotenv import load_dotenv

# Carrega variáveis de ambiente do .env
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

DADOS_DIR = BASE_DIR / "dados"
DB_PATH = BASE_DIR / "condominio.db"
DB_URL = f"sqlite+aiosqlite:///{DB_PATH.as_posix()}"

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
APP_NAME = "residencial_aurora_app"
DEFAULT_USER_ID = "morador"
