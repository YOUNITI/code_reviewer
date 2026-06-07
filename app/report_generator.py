"""
Модуль генерации отчётов.
Поддерживает форматы HTML, JSON и Markdown.
"""

from datetime import datetime

SEVERITY_LABELS = {
    "critical": "Критический",
    "major": "Значительный",
    "minor": "Незначительный",
}
CATEGORY_LABELS = {
    "style": "Стиль",
    "logic": "Логика",
    "security": "Безопасность",
    "performance": "Производительность",
    "naming": "Именование",
}
SEVERITY_COLORS = {
    "critical": "#dc3545",
    "major": "#fd7e14",
    "minor": "#6c757d",
}


class ReportGenerator:
    """Генерация отчётов рецензирования в различных форматах."""

    def generate(self, review: dict, fmt: str = "html") -> str:
        """
        Сформировать отчёт.

        fmt: 'html' | 'json' | 'md'
        """
        fmt = fmt.lower().strip()
        if fmt == "html":
            return self._to_html(review)
        elif fmt == "md":
            return self._to_markdown(review)
        else:
            import json
            return json.dumps(review.get("result", {}),
                              ensure_ascii=False, indent=2)

    # ------------------------------------------------------------------ HTML

    def _to_html(self, review: dict) -> str:
        result = review.get("result", {})
        score = result.get("score", 0)
        summary = result.get("summary", "")
        issues = result.get("issues", [])
        language = review.get("language", "")
        file_name = review.get("file_name") or "фрагмент кода"
        created = review.get("created_at", "")[:10]

        score_color = (
            "#28a745" if score >= 7 else
            "#fd7e14" if score >= 4 else
            "#dc3545"
        )

        issues_html = ""
        for i, issue in enumerate(issues, 1):
            sev = issue.get("severity", "minor")
            cat = issue.get("category", "style")
            line = issue.get("line")
            line_str = f"строка {line}" if line else "общее"
            color = SEVERITY_COLORS.get(sev, "#6c757d")
            issues_html += f"""
            <div class="issue">
              <div class="issue-header">
                <span class="badge" style="background:{color}">
                  {SEVERITY_LABELS.get(sev, sev)}
                </span>
                <span class="badge badge-cat">
                  {CATEGORY_LABELS.get(cat, cat)}
                </span>
                <span class="issue-line">{line_str}</span>
              </div>
              <p class="issue-desc">{issue.get('description', '')}</p>
              <p class="issue-rec"><strong>Рекомендация:</strong>
                {issue.get('recommendation', '')}</p>
            </div>"""

        if not issues_html:
            issues_html = '<p class="no-issues">Замечаний не обнаружено.</p>'

        counts = {s: sum(1 for x in issues if x.get("severity") == s)
                  for s in ("critical", "major", "minor")}

        return f"""<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8">
  <title>Рецензия кода — {file_name}</title>
  <style>
    body {{font-family: 'Segoe UI', sans-serif; margin: 0; background: #f5f5f5; color: #333;}}
    .container {{max-width: 860px; margin: 32px auto; background: #fff;
                 border-radius: 8px; padding: 32px; box-shadow: 0 2px 8px #0001;}}
    h1 {{font-size: 1.5rem; margin-bottom: 4px;}}
    .meta {{color: #888; font-size: .9rem; margin-bottom: 24px;}}
    .score-block {{display:flex; align-items:center; gap:16px; margin-bottom:24px;}}
    .score-circle {{width:72px;height:72px;border-radius:50%;display:flex;
                    align-items:center;justify-content:center;
                    font-size:1.6rem;font-weight:bold;color:#fff;
                    background:{score_color};}}
    .summary {{background:#f8f9fa;border-left:4px solid #0d6efd;
               padding:12px 16px;border-radius:4px;margin-bottom:24px;}}
    .stats {{display:flex;gap:16px;margin-bottom:24px;}}
    .stat {{background:#f8f9fa;padding:12px 20px;border-radius:6px;text-align:center;}}
    .stat-num {{font-size:1.4rem;font-weight:bold;}}
    .issues h2 {{margin-bottom:12px;}}
    .issue {{border:1px solid #e9ecef;border-radius:6px;padding:14px;margin-bottom:12px;}}
    .issue-header {{display:flex;align-items:center;gap:8px;margin-bottom:8px;}}
    .badge {{color:#fff;padding:2px 8px;border-radius:4px;font-size:.8rem;}}
    .badge-cat {{background:#6c757d;}}
    .issue-line {{color:#888;font-size:.85rem;}}
    .issue-desc {{margin:4px 0;}}
    .issue-rec {{margin:4px 0;color:#555;font-size:.95rem;}}
    .no-issues {{color:#28a745;font-weight:bold;}}
  </style>
</head>
<body>
  <div class="container">
    <h1>Рецензия: {file_name}</h1>
    <div class="meta">Язык: {language} &nbsp;|&nbsp; Дата: {created}</div>

    <div class="score-block">
      <div class="score-circle">{score:.1f}</div>
      <div>
        <strong>Оценка качества кода</strong><br>
        <span style="color:#888">от 0 до 10</span>
      </div>
    </div>

    <div class="summary">{summary}</div>

    <div class="stats">
      <div class="stat">
        <div class="stat-num" style="color:#dc3545">{counts['critical']}</div>
        <div>Критических</div>
      </div>
      <div class="stat">
        <div class="stat-num" style="color:#fd7e14">{counts['major']}</div>
        <div>Значительных</div>
      </div>
      <div class="stat">
        <div class="stat-num" style="color:#6c757d">{counts['minor']}</div>
        <div>Незначительных</div>
      </div>
      <div class="stat">
        <div class="stat-num">{len(issues)}</div>
        <div>Всего замечаний</div>
      </div>
    </div>

    <div class="issues">
      <h2>Замечания</h2>
      {issues_html}
    </div>
  </div>
</body>
</html>"""

    # --------------------------------------------------------------- Markdown

    def _to_markdown(self, review: dict) -> str:
        result = review.get("result", {})
        score = result.get("score", 0)
        summary = result.get("summary", "")
        issues = result.get("issues", [])
        language = review.get("language", "")
        file_name = review.get("file_name") or "фрагмент кода"
        created = review.get("created_at", "")[:10]

        lines = [
            f"# Рецензия кода: {file_name}",
            f"",
            f"**Язык:** {language}  |  **Дата:** {created}  "
            f"|  **Оценка:** {score:.1f}/10",
            f"",
            f"## Резюме",
            f"",
            summary,
            f"",
            f"## Замечания ({len(issues)})",
            f"",
        ]

        if not issues:
            lines.append("_Замечаний не обнаружено._")
        else:
            for i, issue in enumerate(issues, 1):
                sev = SEVERITY_LABELS.get(issue.get("severity", "minor"), "")
                cat = CATEGORY_LABELS.get(issue.get("category", "style"), "")
                line = issue.get("line")
                line_str = f"строка {line}" if line else "общее"
                lines += [
                    f"### {i}. [{sev}] {cat} — {line_str}",
                    f"",
                    f"**Проблема:** {issue.get('description', '')}",
                    f"",
                    f"**Рекомендация:** {issue.get('recommendation', '')}",
                    f"",
                ]

        return "\n".join(lines)
