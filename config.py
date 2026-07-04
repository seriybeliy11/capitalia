"""
Конфигурация бота через переменные окружения.

Все значения загружаются из env — это безопасно для git и Render.
"""
import os
from dotenv import load_dotenv

load_dotenv()


# ───────────────────────── Telegram ─────────────────────────
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")

# Список Telegram user_id администраторов через запятую.
# Пример: "123456789,987654321"
# Если пусто — бот доступен всем (можно использовать как личного бота).
ADMIN_IDS = {
    int(uid.strip())
    for uid in os.getenv("ADMIN_IDS", "").split(",")
    if uid.strip().isdigit()
}


# ───────────────────────── 2328.io API ─────────────────────────
# Project UUID из личного кабинета 2328.io
PROJECT_UUID = os.getenv("PROJECT_UUID", "")

# API key из личного кабинета 2328.io (используется как HMAC-секрет)
API_KEY = os.getenv("API_KEY", "")

# Базовый URL API 2328.io
API_BASE_URL = os.getenv("API_BASE_URL", "https://api.2328.io/api/v1")

# User-Agent, который видит 2328.io
API_USER_AGENT = os.getenv(
    "API_USER_AGENT",
    "TgBot2328/1.0 (+https://github.com/)"
)

# URL для callback-уведомлений от 2328.io (webhook).
# На Render можно включить webhook-режим, указав публичный URL.
CALLBACK_URL = os.getenv("CALLBACK_URL", "")  # напр. https://my-bot.onrender.com/webhook

# URL, на который 2328.io вернёт пользователя после успешной оплаты.
SUCCESS_URL = os.getenv("SUCCESS_URL", "")

# URL возврата (после отмены/завершения).
RETURN_URL = os.getenv("RETURN_URL", "")


# ───────────────────────── Поведение бота ─────────────────────────
# Дефолтная валюта инвойса, если не указана явно.
DEFAULT_CURRENCY = os.getenv("DEFAULT_CURRENCY", "USD")

# Дефолтный TTL инвойса в секундах (1 час = 3600).
DEFAULT_TTL = int(os.getenv("DEFAULT_TTL", "3600"))

# Сколько последних инвойсов показывать в /list.
LIST_LIMIT = int(os.getenv("LIST_LIMIT", "10"))

# Таймаут сетевых запросов в секундах.
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "30"))

# Long polling timeout для Telegram getUpdates (секунды).
LONG_POLL_TIMEOUT = int(os.getenv("LONG_POLL_TIMEOUT", "30"))


def is_admin(user_id: int) -> bool:
    """Возвращает True, если user_id — администратор, либо список админов пуст."""
    if not ADMIN_IDS:
        return True
    return user_id in ADMIN_IDS


def validate() -> list:
    """Проверка обязательных переменных окружения. Возвращает список ошибок."""
    errors = []
    if not TELEGRAM_BOT_TOKEN:
        errors.append("TELEGRAM_BOT_TOKEN не задан.")
    if not PROJECT_UUID:
        errors.append("PROJECT_UUID не задан (Project UUID из 2328.io).")
    if not API_KEY:
        errors.append("API_KEY не задан (API key из 2328.io).")
    return errors
