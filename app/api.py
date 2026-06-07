"""
REST API системы автоматического рецензирования исходного кода.
Реализован на основе фреймворка FastAPI.
"""

from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.responses import HTMLResponse, PlainTextResponse
from pydantic import BaseModel, Field
from typing import Optional
import asyncio

from app import config
from app import database as db
from app.preprocessor import CodePreprocessor
from app.prompt_builder import PromptBuilder
from app.llm_client import LLMClient
from app.response_parser import ResponseParser
from app.report_generator import ReportGenerator

# Инициализация базы данных при старте
db.init_db()

app = FastAPI(
    title="Система автоматического рецензирования кода",
    description="API для анализа качества исходного кода с помощью LLM",
    version="1.0.0",
)

# Компоненты системы (синглтоны)
preprocessor = CodePreprocessor()
prompt_builder = PromptBuilder()
llm_client = LLMClient()
response_parser = ResponseParser()
report_generator = ReportGenerator()


# ───────────────────── Схемы данных ─────────────────────

class ReviewRequest(BaseModel):
    code: str = Field(..., min_length=1, description="Исходный код для рецензирования")
    config_name: str = Field("default", description="Имя профиля конфигурации")
    file_name: Optional[str] = Field(None, description="Имя файла (для определения языка)")
    format: str = Field("json", description="Формат отчёта: json | html | md")


class ConfigRequest(BaseModel):
    name: str = Field(..., min_length=1, description="Название профиля")
    strictness: str = Field("standard", description="Уровень строгости: low | standard | high")
    categories: str = Field(
        "style,logic,security,performance,naming",
        description="Категории проверки через запятую"
    )
    extra_instructions: str = Field("", description="Дополнительные инструкции для LLM")


# ───────────────────── Аутентификация ─────────────────────

def verify_token(authorization: Optional[str] = Header(None)):
    """Проверка API-ключа из заголовка Authorization."""
    if not authorization:
        return  # В режиме разработки — пропускаем
    token = authorization.replace("Bearer ", "").strip()
    if token and token != config.API_SECRET_KEY:
        raise HTTPException(status_code=401, detail="Неверный API-ключ")


# ───────────────────── Эндпоинты ─────────────────────

@app.get("/", tags=["info"])
def root():
    """Информация о системе."""
    return {
        "name": "Система автоматического рецензирования кода",
        "version": "1.0.0",
        "stub_mode": config.LLM_STUB_MODE,
        "docs": "/docs",
    }


@app.post("/api/v1/review", status_code=201, tags=["review"])
async def create_review(
    request: ReviewRequest,
    _=Depends(verify_token)
):
    """
    Создать рецензию для предоставленного исходного кода.
    Возвращает структурированный JSON с оценкой и списком замечаний.
    """
    # 1. Получить конфигурацию
    cfg = db.get_config(request.config_name)
    if not cfg:
        raise HTTPException(
            status_code=404,
            detail=f"Конфигурация '{request.config_name}' не найдена"
        )

    # 2. Предобработка кода
    code = preprocessor.normalize(request.code)
    language = preprocessor.detect_language(code, request.file_name)
    metrics = preprocessor.compute_metrics(code)
    code_hash = preprocessor.compute_hash(code)

    # 3. Проверка кэша
    cached = db.find_cached(code_hash, cfg["id"])
    if cached:
        cached["from_cache"] = True
        return cached

    # 4. Формирование запроса
    system_prompt, user_prompt = prompt_builder.build(code, language, metrics, cfg)

    # 5. Запрос к LLM
    try:
        raw_response = await llm_client.review(system_prompt, user_prompt)
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"Ошибка при обращении к API языковой модели: {str(e)}"
        )

    # 6. Разбор ответа
    result = response_parser.parse(raw_response)

    # 7. Сохранение и возврат
    review = db.save_review(
        code_hash=code_hash,
        language=language,
        file_name=request.file_name,
        loc=metrics["loc"],
        sloc=metrics["sloc"],
        score=result["score"],
        issues_count=len(result["issues"]),
        result=result,
        config_id=cfg["id"],
    )
    review["from_cache"] = False
    return review


@app.get("/api/v1/review/{review_id}", tags=["review"])
def get_review(review_id: int, _=Depends(verify_token)):
    """Получить рецензию по идентификатору."""
    review = db.get_review(review_id)
    if not review:
        raise HTTPException(status_code=404, detail="Рецензия не найдена")
    return review


@app.get("/api/v1/review/{review_id}/html",
         response_class=HTMLResponse, tags=["review"])
def get_review_html(review_id: int, _=Depends(verify_token)):
    """Получить рецензию в формате HTML с подсветкой замечаний."""
    review = db.get_review(review_id)
    if not review:
        raise HTTPException(status_code=404, detail="Рецензия не найдена")
    return HTMLResponse(content=report_generator.generate(review, "html"))


@app.get("/api/v1/review/{review_id}/md",
         response_class=PlainTextResponse, tags=["review"])
def get_review_md(review_id: int, _=Depends(verify_token)):
    """Получить рецензию в формате Markdown."""
    review = db.get_review(review_id)
    if not review:
        raise HTTPException(status_code=404, detail="Рецензия не найдена")
    return PlainTextResponse(content=report_generator.generate(review, "md"))


@app.post("/api/v1/configs", status_code=201, tags=["configs"])
def create_config(request: ConfigRequest, _=Depends(verify_token)):
    """Создать новый профиль конфигурации."""
    if db.get_config(request.name):
        raise HTTPException(
            status_code=409,
            detail=f"Конфигурация '{request.name}' уже существует"
        )
    return db.create_config(
        name=request.name,
        strictness=request.strictness,
        categories=request.categories,
        extra_instructions=request.extra_instructions,
    )


@app.get("/api/v1/configs", tags=["configs"])
def list_configs(_=Depends(verify_token)):
    """Получить список всех профилей конфигурации."""
    return db.list_configs()


@app.get("/api/v1/stats", tags=["stats"])
def get_stats(_=Depends(verify_token)):
    """Статистика использования системы."""
    return db.get_stats()
