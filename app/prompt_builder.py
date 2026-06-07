"""
Модуль формирования запросов к языковой модели.
Генерирует системный и пользовательский промпты на основе параметров рецензирования.
"""

SYSTEM_PROMPT = """Ты — опытный рецензент исходного кода с многолетним опытом \
в разработке программного обеспечения.

Твоя задача — провести детальную рецензию предоставленного кода и вернуть \
результат СТРОГО в формате JSON без каких-либо пояснений вне JSON.

Обязательная структура ответа:
{
  "score": <число от 0.0 до 10.0, где 10 — идеальный код>,
  "summary": "<общее резюме рецензии на русском языке, 2-3 предложения>",
  "issues": [
    {
      "line": <номер строки или null если замечание общее>,
      "category": "<одно из: style | logic | security | performance | naming>",
      "severity": "<одно из: critical | major | minor>",
      "description": "<описание проблемы на русском языке>",
      "recommendation": "<конкретная рекомендация по исправлению>"
    }
  ]
}

Правила:
- Отвечай ТОЛЬКО валидным JSON, без markdown и пояснений вне JSON
- Если проблем нет — возвращай пустой массив issues
- Описания и рекомендации пиши на русском языке
- Рекомендации должны быть конкретными, с примером кода если возможно
"""

STRICTNESS_EXTRA = {
    "low": "Обращай внимание только на критические ошибки и проблемы безопасности.",
    "standard": "Проверяй ошибки всех уровней критичности.",
    "high": (
        "Проверяй все категории дефектов включая архитектурные: "
        "соответствие принципам SOLID и DRY, читаемость алгоритмов, "
        "оптимальность выбора структур данных."
    ),
}


class PromptBuilder:
    """Формирование запросов к языковой модели."""

    def build(self, code: str, language: str, metrics: dict,
              config: dict) -> tuple[str, str]:
        """
        Сформировать системный и пользовательский промпты.

        Возвращает кортеж (system_prompt, user_prompt).
        """
        strictness = config.get("strictness", "standard")
        categories = config.get("categories", "style,logic,security,performance,naming")
        extra = config.get("extra_instructions", "")

        # Системный промпт — роль и формат ответа
        system = SYSTEM_PROMPT
        if extra:
            system += f"\n\nДополнительные инструкции: {extra}"

        # Пользовательский промпт — контекст и код
        strictness_hint = STRICTNESS_EXTRA.get(strictness, STRICTNESS_EXTRA["standard"])
        categories_list = categories.replace(",", ", ")

        user = f"""Язык программирования: {language}
Уровень строгости проверки: {strictness}
{strictness_hint}

Категории для проверки: {categories_list}

Метрики кода:
- Всего строк (LOC): {metrics.get('loc', '?')}
- Строк кода без комментариев (SLOC): {metrics.get('sloc', '?')}
- Функций/методов: {metrics.get('functions', '?')}
- Классов: {metrics.get('classes', '?')}
- Максимальная глубина вложенности: {metrics.get('max_depth', '?')}

Исходный код для рецензирования:
```{language.lower()}
{code}
```

Верни JSON-рецензию строго по указанной структуре."""

        return system, user
