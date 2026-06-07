"""
Интерфейс командной строки системы рецензирования кода.
Использование: python cli.py review --file example.py --config default --format html
"""

import sys
import asyncio
import argparse

# Инициализируем БД при запуске
from app import database as db
db.init_db()

from app.preprocessor import CodePreprocessor
from app.prompt_builder import PromptBuilder
from app.llm_client import LLMClient
from app.response_parser import ResponseParser
from app.report_generator import ReportGenerator

preprocessor = CodePreprocessor()
prompt_builder = PromptBuilder()
llm_client = LLMClient()
response_parser = ResponseParser()
report_generator = ReportGenerator()


async def run_review(code: str, file_name: str,
                     config_name: str, fmt: str, output: str):
    """Выполнить рецензирование и вывести/сохранить результат."""

    # Получить конфигурацию
    cfg = db.get_config(config_name)
    if not cfg:
        print(f"Ошибка: конфигурация '{config_name}' не найдена.")
        print("Доступные профили:", [c["name"] for c in db.list_configs()])
        sys.exit(1)

    print(f"Язык: ", end="", flush=True)
    language = preprocessor.detect_language(code, file_name)
    print(language)

    code = preprocessor.normalize(code)
    metrics = preprocessor.compute_metrics(code)
    code_hash = preprocessor.compute_hash(code)

    print(f"Метрики: LOC={metrics['loc']}, функций={metrics['functions']}, "
          f"классов={metrics['classes']}")

    # Проверяем кэш
    cached = db.find_cached(code_hash, cfg["id"])
    if cached:
        print("Результат из кэша.")
        review = cached
    else:
        print("Отправляю запрос к системе...", end=" ", flush=True)
        system_prompt, user_prompt = prompt_builder.build(code, language, metrics, cfg)
        raw = await llm_client.review(system_prompt, user_prompt)
        result = response_parser.parse(raw)
        review = db.save_review(
            code_hash=code_hash, language=language, file_name=file_name,
            loc=metrics["loc"], sloc=metrics["sloc"],
            score=result["score"], issues_count=len(result["issues"]),
            result=result, config_id=cfg["id"]
        )
        print("готово.")

    result = review["result"]
    print(f"\n{'='*50}")
    print(f"Оценка качества кода: {result['score']:.1f}/10")
    print(f"Замечаний найдено: {len(result['issues'])}")
    print(f"Резюме: {result['summary']}")
    print(f"{'='*50}\n")

    # Краткий список замечаний в консоли
    for i, issue in enumerate(result["issues"], 1):
        line = f"стр.{issue['line']}" if issue.get("line") else "общее"
        print(f"{i}. [{issue['severity'].upper()}] {issue['category']} "
              f"({line}): {issue['description']}")

    # Генерируем отчёт
    report_content = report_generator.generate(review, fmt)

    if output:
        with open(output, "w", encoding="utf-8") as f:
            f.write(report_content)
        print(f"\nОтчёт сохранён: {output}")
    elif fmt == "json":
        import json
        print("\n" + json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"\nОтчёт сформирован. Укажите --output для сохранения в файл.")

    return review


def main():
    parser = argparse.ArgumentParser(
        description="Система автоматического рецензирования исходного кода"
    )
    subparsers = parser.add_subparsers(dest="command")

    # Команда review
    review_parser = subparsers.add_parser("review", help="Рецензировать файл с кодом")
    review_parser.add_argument("--file", "-f", required=True,
                               help="Путь к файлу с исходным кодом")
    review_parser.add_argument("--config", "-c", default="default",
                               help="Имя профиля конфигурации (default/strict/light)")
    review_parser.add_argument("--format", default="json",
                               choices=["json", "html", "md"],
                               help="Формат отчёта")
    review_parser.add_argument("--output", "-o", default="",
                               help="Путь для сохранения отчёта")

    # Команда configs
    subparsers.add_parser("configs", help="Список профилей конфигурации")

    # Команда stats
    subparsers.add_parser("stats", help="Статистика использования")

    args = parser.parse_args()

    if args.command == "review":
        try:
            with open(args.file, encoding="utf-8") as f:
                code = f.read()
        except FileNotFoundError:
            print(f"Ошибка: файл '{args.file}' не найден.")
            sys.exit(1)
        except Exception as e:
            print(f"Ошибка чтения файла: {e}")
            sys.exit(1)

        asyncio.run(run_review(
            code=code,
            file_name=args.file,
            config_name=args.config,
            fmt=args.format,
            output=args.output,
        ))

    elif args.command == "configs":
        configs = db.list_configs()
        print("\nДоступные профили конфигурации:")
        for c in configs:
            print(f"  {c['name']:12} | строгость: {c['strictness']:10} "
                  f"| категории: {c['categories']}")

    elif args.command == "stats":
        stats = db.get_stats()
        print(f"\nСтатистика системы:")
        print(f"  Всего рецензий:  {stats['total_reviews']}")
        print(f"  Средняя оценка:  {stats['avg_score']:.2f}/10")
        print(f"  По языкам:       {stats['by_language']}")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
