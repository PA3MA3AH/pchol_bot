# utils/helpers.py
"""Общие утилиты для бота."""
import html as _html


def h(value: str) -> str:
    """HTML-escape для безопасной вставки пользовательских данных в Telegram HTML."""
    return _html.escape(str(value))
