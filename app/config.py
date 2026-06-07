"""
Конфигурация системы автоматического рецензирования.
Настройки загружаются из переменных окружения или файла .env
"""

import os
from pathlib import Path

# Загрузка .env (если python-dotenv установлен)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Путь к корню проекта
BASE_DIR = Path(__file__).parent.parent

# --- LLM ---
LLM_API_KEY: str = os.getenv("LLM_API_KEY", "")
LLM_BASE_URL: str = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
LLM_MODEL: str = os.getenv("LLM_MODEL", "gpt-4o-mini")
LLM_MAX_RETRIES: int = int(os.getenv("LLM_MAX_RETRIES", "3"))
LLM_TIMEOUT: int = int(os.getenv("LLM_TIMEOUT", "60"))

# Режим заглушки: если True — LLM не вызывается, возвращается тестовый ответ
LLM_STUB_MODE: bool = os.getenv("LLM_STUB_MODE", "true").lower() == "true"

# --- База данных ---
DATABASE_PATH: str = os.getenv("DATABASE_PATH", str(BASE_DIR / "reviews.db"))

# --- API ---
API_SECRET_KEY: str = os.getenv("API_SECRET_KEY", "dev-secret-key")
API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
API_PORT: int = int(os.getenv("API_PORT", "8000"))
