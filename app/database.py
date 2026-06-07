"""
Модуль работы с базой данных SQLite.
Реализует хранение результатов рецензирования и профилей конфигурации.
"""

import sqlite3
import json
from datetime import datetime
from typing import Optional
from app.config import DATABASE_PATH


def get_connection() -> sqlite3.Connection:
    """Создать соединение с базой данных."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Инициализировать схему базы данных."""
    with get_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS configurations (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                name      TEXT NOT NULL UNIQUE,
                strictness TEXT NOT NULL DEFAULT 'standard',
                categories TEXT NOT NULL DEFAULT 'style,logic,security,performance,naming',
                extra_instructions TEXT DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS reviews (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                code_hash    TEXT NOT NULL,
                language     TEXT NOT NULL,
                file_name    TEXT,
                loc          INTEGER NOT NULL,
                sloc         INTEGER NOT NULL,
                score        REAL NOT NULL,
                issues_count INTEGER NOT NULL,
                result_json  TEXT NOT NULL,
                created_at   TEXT NOT NULL,
                config_id    INTEGER REFERENCES configurations(id)
            );

            CREATE INDEX IF NOT EXISTS idx_reviews_hash
                ON reviews(code_hash, config_id);

            INSERT OR IGNORE INTO configurations
                (name, strictness, categories, extra_instructions)
            VALUES
                ('default', 'standard',
                 'style,logic,security,performance,naming', ''),
                ('strict', 'high',
                 'style,logic,security,performance,naming,architecture',
                 'Проверяй также принципы SOLID и DRY.'),
                ('light', 'low',
                 'logic,security', '');
        """)


# ---------- Конфигурации ----------

def get_config(name: str = "default") -> Optional[dict]:
    """Получить профиль конфигурации по имени."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM configurations WHERE name = ?", (name,)
        ).fetchone()
        return dict(row) if row else None


def list_configs() -> list[dict]:
    """Список всех профилей конфигурации."""
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM configurations").fetchall()
        return [dict(r) for r in rows]


def create_config(name: str, strictness: str = "standard",
                  categories: str = "style,logic,security,performance,naming",
                  extra_instructions: str = "") -> dict:
    """Создать новый профиль конфигурации."""
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO configurations
               (name, strictness, categories, extra_instructions)
               VALUES (?, ?, ?, ?)""",
            (name, strictness, categories, extra_instructions)
        )
        row = conn.execute(
            "SELECT * FROM configurations WHERE name = ?", (name,)
        ).fetchone()
        return dict(row)


# ---------- Рецензии ----------

def find_cached(code_hash: str, config_id: int) -> Optional[dict]:
    """Поиск кэшированного результата по хэшу кода и конфигурации."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM reviews WHERE code_hash = ? AND config_id = ? "
            "ORDER BY created_at DESC LIMIT 1",
            (code_hash, config_id)
        ).fetchone()
        if row:
            d = dict(row)
            d["result"] = json.loads(d["result_json"])
            return d
        return None


def save_review(code_hash: str, language: str, file_name: Optional[str],
                loc: int, sloc: int, score: float, issues_count: int,
                result: dict, config_id: int) -> dict:
    """Сохранить результат рецензирования в базу данных."""
    result_json = json.dumps(result, ensure_ascii=False)
    created_at = datetime.now().isoformat()
    with get_connection() as conn:
        cursor = conn.execute(
            """INSERT INTO reviews
               (code_hash, language, file_name, loc, sloc, score,
                issues_count, result_json, created_at, config_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (code_hash, language, file_name, loc, sloc, score,
             issues_count, result_json, created_at, config_id)
        )
        review_id = cursor.lastrowid
        row = conn.execute(
            "SELECT * FROM reviews WHERE id = ?", (review_id,)
        ).fetchone()
        d = dict(row)
        d["result"] = result
        return d


def get_review(review_id: int) -> Optional[dict]:
    """Получить рецензию по идентификатору."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM reviews WHERE id = ?", (review_id,)
        ).fetchone()
        if row:
            d = dict(row)
            d["result"] = json.loads(d["result_json"])
            return d
        return None


def get_stats() -> dict:
    """Получить статистику использования системы."""
    with get_connection() as conn:
        total = conn.execute("SELECT COUNT(*) FROM reviews").fetchone()[0]
        avg_score = conn.execute(
            "SELECT AVG(score) FROM reviews"
        ).fetchone()[0] or 0.0
        by_lang = conn.execute(
            "SELECT language, COUNT(*) as cnt FROM reviews GROUP BY language"
        ).fetchall()
        return {
            "total_reviews": total,
            "avg_score": round(avg_score, 2),
            "by_language": {r["language"]: r["cnt"] for r in by_lang}
        }
