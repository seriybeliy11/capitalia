"""
Тонкая обёртка над Telegram Bot API на Flask для работы с Webhooks.

Поддерживает:
  - Обработку вебхуков (основная функция)
  - sendMessage
  - editMessageText / editMessageReplyMarkup
  - answerCallbackQuery
  - deleteMessage
  - setMyCommands
"""
import json
import logging
import os
from typing import Dict, Any

import requests
from flask import Flask, request, abort

import config

# Создаем экземпляр Flask-приложения
app = Flask(__name__)

log = logging.getLogger(__name__)
API_URL = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}"
FILE_API_URL = f"https://api.telegram.org/file/bot{config.TELEGRAM_BOT_TOKEN}"


class TelegramError(Exception):
    def __init__(self, message: str, ok: bool = False, error_code: int | None = None):
        super().__init__(message)
        self.ok = ok
        self.error_code = error_code


def _call(method: str, **params) -> Dict[str, Any]:
    """
    Вызывает метод Telegram Bot API.
    Возвращает распарсенный JSON.
    """
    url = f"{API_URL}/{method}"

    # Клавиатуры и reply_markup сериализуем в JSON-строки.
    for key, value in list(params.items()):
        if isinstance(value, (dict, list)):
            params[key] = json.dumps(value, ensure_ascii=False)

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
) -> Dict[str, Any]:
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
) -> Dict[str, Any]:
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
) -> Dict[str, Any]:
    return _call(
        "editMessageReplyMarkup",
        chat_id=chat_id,
        message_id=message_id,
        reply_markup=reply_markup,
    )


def delete_message(chat_id: int | str, message_id: int) -> Dict[str, Any]:
    return _call("deleteMessage", chat_id=chat_id, message_id=message_id)


def answer_callback_query(callback_query_id: str, *, text: str | None = None, show_alert: bool = False) -> Dict[str, Any]:
    return _call(
        "answerCallbackQuery",
        callback_query_id=callback_query_id,
        text=text,
        show_alert=show_alert,
    )


# ───────────────────────── Вебхуки ─────────────────────────

@app.route('/webhook', methods=['POST'])
def handle_webhook():
    """
    Точка входа для всех обновлений от Telegram.
    """
    # Проверяем, что запрос пришел в формате JSON
    if request.is_json:
        update = request.get_json()
        log.info("Получено обновление: %s", update.get('update_id'))

        # Здесь должна быть ваша логика роутинга
        # Например:
        # if 'message' in update:
        #     handlers.handle_message(update)
        # elif 'callback_query' in update:
        #     handlers.handle_callback(update)

        # Обязательно возвращаем 'ok', чтобы Telegram знал, что мы обработали запрос
        return {'status': 'ok'}
    else:
        abort(400) # Bad Request


def set_webhook(url: str) -> Dict[str, Any]:
    """
    Устанавливает вебхук для бота.
    :param url: Полный URL до эндпоинта /webhook (включая https://)
    """
    return _call("setWebhook", url=f"{url}/webhook")


# ───────────────────────── Прочее ─────────────────────────

def set_my_commands(commands: list[dict]) -> Dict[str, Any]:
    """Устанавливает меню команд бота."""
    return _call("setMyCommands", commands=commands)


def send_photo(chat_id: int | str, photo: bytes, caption: str | None = None, reply_markup: dict | None = None) -> Dict[str, Any]:
    """Отправляет фото из байтов."""
    url = f"{API_URL}/sendPhoto"
    data = {"chat_id": chat_id, "parse_mode": "HTML"}
    if caption:
        data["caption"] = caption
    if reply_markup:
        data["reply_markup"] = json.dumps(reply_markup, ensure_ascii=False)
    resp = requests.post(url, data=data, files={"photo": ("qr.png", photo, "image/png")}, timeout=config.REQUEST_TIMEOUT)
    return resp.json().get("result", {})


# ───────────────────────── Запуск приложения ─────────────────────────

if __name__ == "__main__":
    # Настройка логирования остается прежней
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Запускаем Flask-приложение на всех интерфейсах и на порту от Render
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
