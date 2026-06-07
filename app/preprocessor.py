"""
Модуль предобработки исходного кода.
Определяет язык программирования и вычисляет метрики кода.
"""

import re
import hashlib
from typing import Optional

try:
    from pygments.lexers import get_lexer_for_filename, guess_lexer
    from pygments.util import ClassNotFound
    PYGMENTS_AVAILABLE = True
except ImportError:
    PYGMENTS_AVAILABLE = False


# Словарь расширений файлов на случай, если pygments недоступен
EXTENSION_MAP = {
    ".py": "Python", ".js": "JavaScript", ".ts": "TypeScript",
    ".java": "Java", ".cs": "C#", ".cpp": "C++", ".c": "C",
    ".go": "Go", ".rb": "Ruby", ".php": "PHP", ".swift": "Swift",
    ".kt": "Kotlin", ".rs": "Rust", ".sql": "SQL", ".html": "HTML",
    ".css": "CSS", ".sh": "Bash",
}


class CodePreprocessor:
    """Предобработка исходного кода перед отправкой на рецензирование."""

    def detect_language(self, code: str,
                        filename: Optional[str] = None) -> str:
        """
        Определить язык программирования.

        Сначала пробует определить по расширению файла,
        затем — по содержимому кода через эвристику pygments.
        """
        # 1. По расширению файла
        if filename:
            ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
            if ext in EXTENSION_MAP:
                return EXTENSION_MAP[ext]
            if PYGMENTS_AVAILABLE:
                try:
                    lexer = get_lexer_for_filename(filename)
                    return lexer.name
                except ClassNotFound:
                    pass

        # 2. По содержимому кода
        if PYGMENTS_AVAILABLE:
            try:
                lexer = guess_lexer(code)
                # Фильтруем слишком общие ответы pygments
                if lexer.name not in ("Text only", ""):
                    return lexer.name
            except ClassNotFound:
                pass

        # 3. Простые эвристики
        return self._heuristic_detect(code)

    def _heuristic_detect(self, code: str) -> str:
        """Простое определение языка по характерным конструкциям."""
        code_lower = code.lower()
        if re.search(r"\bdef\b.*:|^\s*import\s+\w+|^\s*from\s+\w+\s+import",
                     code, re.MULTILINE):
            return "Python"
        if re.search(r"\bfunction\b|\bconst\b|\blet\b|\bvar\b|\bconsole\.log\b",
                     code):
            return "JavaScript"
        if re.search(r"\bpublic\s+class\b|\bpublic\s+static\s+void\s+main\b",
                     code):
            return "Java"
        if re.search(r"#include\s*<|int\s+main\s*\(", code):
            return "C/C++"
        if re.search(r"\bpackage\s+main\b|\bfunc\s+\w+\(", code):
            return "Go"
        return "Unknown"

    def compute_metrics(self, code: str) -> dict:
        """
        Вычислить метрики исходного кода.

        Возвращает словарь с:
        - loc: общее количество строк
        - sloc: строки без пустых строк и комментариев
        - functions: количество функций/методов
        - classes: количество классов
        - max_depth: максимальная глубина вложенности
        """
        lines = code.splitlines()
        loc = len(lines)

        sloc = sum(
            1 for line in lines
            if line.strip() and not self._is_comment(line.strip())
        )

        # Подсчёт функций и классов (Python-ориентированный, но работает для многих языков)
        functions = len(re.findall(
            r"^\s*(def\s+\w+|function\s+\w+|\w+\s*=\s*function|\w+\s*=\s*\(.*\)\s*=>)",
            code, re.MULTILINE
        ))
        classes = len(re.findall(r"^\s*class\s+\w+", code, re.MULTILINE))
        max_depth = self._get_max_indent(lines)

        return {
            "loc": loc,
            "sloc": sloc,
            "functions": functions,
            "classes": classes,
            "max_depth": max_depth,
        }

    def _is_comment(self, line: str) -> bool:
        """Проверить, является ли строка комментарием."""
        return (
            line.startswith("#")
            or line.startswith("//")
            or line.startswith("*")
            or line.startswith("/*")
            or line.startswith('"""')
            or line.startswith("'''")
        )

    def _get_max_indent(self, lines: list) -> int:
        """Определить максимальную глубину вложенности по отступам."""
        max_indent = 0
        for line in lines:
            if line.strip():
                # Считаем отступ в условных единицах (4 пробела = 1 уровень)
                indent = len(line) - len(line.lstrip())
                max_indent = max(max_indent, indent // 4)
        return max_indent

    def normalize(self, code: str) -> str:
        """Нормализовать код: убрать лишние пустые строки, привести к UTF-8."""
        # Убираем более двух пустых строк подряд
        code = re.sub(r"\n{3,}", "\n\n", code)
        # Убираем пробелы в конце строк
        lines = [line.rstrip() for line in code.splitlines()]
        return "\n".join(lines).strip()

    def compute_hash(self, code: str) -> str:
        """Вычислить SHA-256 хэш исходного кода для кэширования."""
        return hashlib.sha256(code.encode("utf-8")).hexdigest()
