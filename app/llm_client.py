"""
Модуль взаимодействия с API языковой модели.
Поддерживает режим заглушки (STUB_MODE) для работы без API-ключа.
"""

import asyncio
import json
import time
from app.config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL
from app.config import LLM_MAX_RETRIES, LLM_TIMEOUT, LLM_STUB_MODE

# Заглушка — реалистичный ответ для демонстрации системы
STUB_RESPONSE = json.dumps({
    "score": 5.5,
    "summary": (
        "Код содержит несколько проблем разного уровня критичности. "
        "Обнаружены потенциальная уязвимость безопасности и нарушения "
        "стиля оформления. Рекомендуется исправить критические замечания "
        "перед использованием кода в production."
    ),
    "issues": [
        {
            "line": 5,
            "category": "security",
            "severity": "critical",
            "description": "Пароль хранится в открытом виде прямо в исходном коде.",
            "recommendation": (
                "Используйте переменные окружения: "
                "import os; PASSWORD = os.environ.get('APP_PASSWORD')"
            )
        },
        {
            "line": 11,
            "category": "security",
            "severity": "critical",
            "description": (
                "SQL-запрос формируется через f-строку с пользовательскими данными. "
                "Это открывает возможность SQL-инъекции."
            ),
            "recommendation": (
                "Используйте параметризованные запросы: "
                "cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))"
            )
        },
        {
            "line": 14,
            "category": "logic",
            "severity": "major",
            "description": "Соединение с базой данных не закрывается, что приводит к утечке ресурсов.",
            "recommendation": (
                "Используйте контекстный менеджер: "
                "with sqlite3.connect('users.db') as conn:"
            )
        },
        {
            "line": 16,
            "category": "naming",
            "severity": "minor",
            "description": "Имя функции ProcessData нарушает соглашение PEP 8 для Python.",
            "recommendation": "Переименуйте функцию в snake_case: def process_data(data):"
        },
        {
            "line": 17,
            "category": "style",
            "severity": "minor",
            "description": "Переменная 'l' — однобуквенное имя, трудно читать.",
            "recommendation": "Используйте понятное имя: result = []"
        },
        {
            "line": 19,
            "category": "style",
            "severity": "minor",
            "description": "Сравнение с None через != вместо 'is not'.",
            "recommendation": "Используйте: if data[i] is not None:"
        }
    ]
}, ensure_ascii=False)


class LLMClient:
    """Асинхронный клиент для работы с API языковой модели."""

    def __init__(self):
        self.stub_mode = LLM_STUB_MODE
        self._client = None

        if not self.stub_mode and LLM_API_KEY:
            try:
                from openai import AsyncOpenAI
                self._client = AsyncOpenAI(
                    api_key=LLM_API_KEY,
                    base_url=LLM_BASE_URL,
                    timeout=LLM_TIMEOUT,
                )
            except ImportError:
                print("Предупреждение: библиотека openai не установлена. "
                      "Переключаюсь на режим заглушки.")
                self.stub_mode = True

    async def review(self, system_prompt: str, user_prompt: str) -> str:
        """
        Отправить запрос к языковой модели.

        В режиме заглушки возвращает тестовый ответ.
        При ошибках выполняет повторные попытки с экспоненциальной задержкой.
        """
        if self.stub_mode:
            return await self._stub_response(user_prompt)

        return await self._call_api(system_prompt, user_prompt)

    async def _stub_response(self, user_prompt: str) -> str:
        """Заглушка: имитация задержки API и возврат тестового ответа."""
        # Имитируем реальную задержку сети
        await asyncio.sleep(1.5)
        return STUB_RESPONSE

    async def _call_api(self, system_prompt: str, user_prompt: str) -> str:
        """Реальный вызов API с повторными попытками."""
        last_error = None

        for attempt in range(LLM_MAX_RETRIES):
            try:
                response = await self._client.chat.completions.create(
                    model=LLM_MODEL,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=0.2,      # Низкая температура — стабильные ответы
                    max_tokens=2000,
                    response_format={"type": "json_object"},
                )
                return response.choices[0].message.content

            except Exception as e:
                last_error = e
                error_name = type(e).__name__

                # Превышение лимита запросов — ждём и повторяем
                if "RateLimitError" in error_name:
                    wait = 2 ** attempt
                    print(f"Лимит запросов API. Ожидание {wait} с...")
                    await asyncio.sleep(wait)
                    continue

                # Временная недоступность — повторяем
                if "APIConnectionError" in error_name or "Timeout" in error_name:
                    if attempt < LLM_MAX_RETRIES - 1:
                        wait = 2 ** attempt
                        print(f"Ошибка соединения ({error_name}). Повтор через {wait} с...")
                        await asyncio.sleep(wait)
                        continue

                # Прочие ошибки — сразу выбрасываем
                raise

        raise RuntimeError(
            f"Не удалось получить ответ от API после {LLM_MAX_RETRIES} попыток. "
            f"Последняя ошибка: {last_error}"
        )
