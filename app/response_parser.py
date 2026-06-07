"""
Модуль разбора ответов языковой модели.
Реализует трёхуровневый алгоритм извлечения JSON из текстового ответа.
"""

import json
import re
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict, ValidationError, field_validator

DEFAULT_RESPONSE = {
    "score": 0.0,
    "summary": "Не удалось разобрать ответ системы. Попробуйте повторить запрос.",
    "issues": [
        {
            "line": None,
            "category": "logic",
            "severity": "major",
            "description": "Системная ошибка: не удалось получить рецензию.",
            "recommendation": "Повторите запрос. Если ошибка повторяется — проверьте настройки API."
        }
    ]
}


class CodeIssue(BaseModel):
    model_config = ConfigDict(extra="ignore")
    line: Optional[int] = None
    category: str = "style"
    severity: str = "minor"
    description: str = ""
    recommendation: str = ""

    @field_validator("category", mode="before")
    @classmethod
    def fix_category(cls, v):
        valid = {"style", "logic", "security", "performance", "naming"}
        return v if isinstance(v, str) and v in valid else "style"

    @field_validator("severity", mode="before")
    @classmethod
    def fix_severity(cls, v):
        valid = {"critical", "major", "minor"}
        return v if isinstance(v, str) and v in valid else "minor"


class ReviewResult(BaseModel):
    model_config = ConfigDict(extra="ignore")
    score: float = Field(default=5.0, ge=0.0, le=10.0)
    summary: str = "Рецензия сформирована."
    issues: list[CodeIssue] = []


class ResponseParser:
    """Разбор и валидация ответа языковой модели."""

    def parse(self, raw_response: str) -> dict:
        """
        Извлечь структурированные данные из ответа модели.

        Алгоритм (трёхуровневый):
        1. Прямой JSON-парсинг
        2. Извлечение из markdown-блока ```json ... ```
        3. Поиск JSON по фигурным скобкам
        """
        if not raw_response or not raw_response.strip():
            return DEFAULT_RESPONSE.copy()

        # Уровень 1: прямой JSON-парсинг
        result = self._try_parse_json(raw_response.strip())
        if result:
            return self._validate_and_fix(result)

        # Уровень 2: извлечение из markdown-блока
        extracted = self._extract_from_markdown(raw_response)
        if extracted:
            result = self._try_parse_json(extracted)
            if result:
                return self._validate_and_fix(result)

        # Уровень 3: поиск по фигурным скобкам
        extracted = self._extract_by_braces(raw_response)
        if extracted:
            result = self._try_parse_json(extracted)
            if result:
                return self._validate_and_fix(result)

        return DEFAULT_RESPONSE.copy()

    def _try_parse_json(self, text: str) -> Optional[dict]:
        """Попытка разобрать строку как JSON."""
        try:
            return json.loads(text)
        except (json.JSONDecodeError, ValueError):
            return None

    def _extract_from_markdown(self, text: str) -> Optional[str]:
        """Извлечь JSON из блока markdown (```json ... ```)."""
        patterns = [
            r"```json\s*([\s\S]+?)\s*```",
            r"```\s*([\s\S]+?)\s*```",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.DOTALL)
            if match:
                return match.group(1).strip()
        return None

    def _extract_by_braces(self, text: str) -> Optional[str]:
        """Найти JSON по первой открывающей и последней закрывающей скобке."""
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            return text[start:end + 1]
        return None

    def _validate_and_fix(self, data: dict) -> dict:
        if not isinstance(data, dict):
            data = {}
        if "score" in data:
            try:
                s = float(data["score"])
                data["score"] = max(0.0, min(10.0, s))
            except (ValueError, TypeError):
                data["score"] = 5.0
        try:
            return ReviewResult.model_validate(data).model_dump()
        except ValidationError:
            return DEFAULT_RESPONSE.copy()
