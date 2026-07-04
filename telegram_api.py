"""
Тонкая обёртка над Telegram Bot API на чистом requests.

Поддерживает только то, что нужно боту:
  - sendMessage (с inline-клавиатурой и без)
  - editMessageText / editMessageReplyMarkup
  - answerCallbackQuery
  - deleteMessage
  - getUpdates (long polling)
  - setMyCommands

Никаких внешних Telegram-фреймворков — только HTTP.
"""
import json
import logging
import time

import requests

import config

log = logging.getLogger(__name__)

API_URL = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}"
FILE_API_URL = f"https://api.telegram.org/file/bot{config.TELEGRAM_BOT_TOKEN}"


class TelegramError(Exception):
    def __init__(self, message: str, ok: bool = False, error_code: int | None = None):
        super().__init__(message)
        self.ok = ok
        self.error_code = error_code


def _call(method: str, **params) -> dict:
    """
    Вызывает method Telegram Bot API.
    files и parse_mode поддерживаются.
    Возвращает распарсенный JSON.
    """
    url = f"{API_URL}/{method}"

    # Клавиатуры и reply_markup сериализуем в JSON-строки.
    if "reply_markup" in params and isinstance(params["reply_markup"], (dict, list)):
        params["reply_markup"] = json.dumps(params["reply_markup"], ensure_ascii=False)

    timeout = params.pop("_timeout", config.REQUEST_TIMEOUT)

    log.debug("→ TG %s params=%s", method, {k: v for k, v in params.items() if k != "reply_markup"})
    try:
        resp = requests.post(url, data=params, timeout=timeout)
    except requests.RequestException as e:
        raise TelegramError(f"Сетевая ошибка Telegram: {e}") from e

    try:
        data = resp.json()
    except ValueError:
        raise TelegramError(f"Telegram вернул не-JSON: {resp.text[:300]}")

    if not data.get("ok"):
        desc = data.get("description", "unknown error")
        code = data.get("error_code")
        log.warning("← TG %s error: %s (code=%s)", method, desc, code)
        raise TelegramError(desc, ok=False, error_code=code)

    return data.get("result", {})


# ───────────────────────── Сообщения ─────────────────────────

def send_message(
    chat_id: int | str,
    text: str,
    *,
    parse_mode: str = "HTML",
    disable_web_page_preview: bool = True,
    reply_markup: dict | None = None,
    reply_to_message_id: int | None = None,
) -> dict:
    return _call(
        "sendMessage",
        chat_id=chat_id,
        text=text,
        parse_mode=parse_mode,
        disable_web_page_preview=disable_web_page_preview,
        reply_markup=reply_markup,
        reply_to_message_id=reply_to_message_id,
    )


def edit_message_text(
    chat_id: int | str,
    message_id: int,
    text: str,
    *,
    parse_mode: str = "HTML",
    disable_web_page_preview: bool = True,
    reply_markup: dict | None = None,
) -> dict:
    return _call(
        "editMessageText",
        chat_id=chat_id,
        message_id=message_id,
        text=text,
        parse_mode=parse_mode,
        disable_web_page_preview=disable_web_page_preview,
        reply_markup=reply_markup,
    )


def edit_message_reply_markup(
    chat_id: int | str,
    message_id: int,
    reply_markup: dict | None,
) -> dict:
    return _call(
        "editMessageReplyMarkup",
        chat_id=chat_id,
        message_id=message_id,
        reply_markup=reply_markup,
    )


def delete_message(chat_id: int | str, message_id: int) -> dict:
    return _call("deleteMessage", chat_id=chat_id, message_id=message_id)


def answer_callback_query(callback_query_id: str, *, text: str | None = None, show_alert: bool = False) -> dict:
    return _call(
        "answerCallbackQuery",
        callback_query_id=callback_query_id,
        text=text,
        show_alert=show_alert,
    )


# ───────────────────────── Long polling ─────────────────────────

def get_updates(offset: int | None = None, timeout: int | None = None) -> list:
    """
    Получает обновления через long polling.
    :param offset: offset для подтверждения предыдущих обновлений
    :param timeout: long poll timeout в секундах
    """
    params = {"timeout": timeout or config.LONG_POLL_TIMEOUT}
    if offset:
        params["offset"] = offset
    # Используем суммарный HTTP-таймаут = poll timeout + буфер.
    http_timeout = (timeout or config.LONG_POLL_TIMEOUT) + 10
    try:
        resp = requests.post(f"{API_URL}/getUpdates", data=params, timeout=http_timeout)
        data = resp.json()
    except requests.RequestException as e:
        log.warning("getUpdates network error: %s", e)
        return []
    except ValueError:
        log.warning("getUpdates returned non-JSON")
        return []

    if not data.get("ok"):
        log.warning("getUpdates not ok: %s", data)
        return []
    return data.get("result", [])


# ───────────────────────── Прочее ─────────────────────────

def set_my_commands(commands: list[dict]) -> dict:
    """Устанавливает меню команд бота."""
    return _call("setMyCommands", commands=commands)


def send_photo(chat_id: int | str, photo: bytes, caption: str | None = None, reply_markup: dict | None = None) -> dict:
    """Отправляет фото из байтов (например, QR-код из base64)."""
    url = f"{API_URL}/sendPhoto"
    data = {"chat_id": chat_id, "parse_mode": "HTML"}
    if caption:
        data["caption"] = caption
    if reply_markup:
        data["reply_markup"] = json.dumps(reply_markup, ensure_ascii=False)
    resp = requests.post(url, data=data, files={"photo": ("qr.png", photo, "image/png")}, timeout=config.REQUEST_TIMEOUT)
    return resp.json().get("result", {})
