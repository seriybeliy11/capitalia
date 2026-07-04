"""
Точка входа: Telegram-бот для управления инвойсами 2328.io.

Адаптировано для работы с Webhooks через Flask.
Идеально подходит для Render Web Service.
"""
import logging
import sys
import os

from flask import Flask, request, jsonify, abort

import config
import handlers
import state
import telegram_api
from telegram_api import TelegramError

# ───────────────────────── Логирование ─────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
# Уменьшаем спам от requests.
logging.getLogger("urllib3").setLevel(logging.WARNING)
log = logging.getLogger("bot")

# ───────────────────────── Инициализация Flask ─────────────────────────
app = Flask(__name__)

# ───────────────────────── Роутинг апдейтов (без изменений) ─────────────────────────

def route_update(update: dict):
    """Маршрутизирует апдейт в нужный обработчик."""
    try:
        if "message" in update:
            msg = update["message"]
            text = (msg.get("text") or "").strip()
            chat_id = msg.get("chat", {}).get("id")
            user_id = msg.get("from", {}).get("id")

            # Если пользователь в каком-то состоянии — сначала обрабатываем FSM.
            if (
                user_id
                and state.get_state(user_id) != state.STATE_IDLE
                and not text.startswith("/")
            ):
                handlers.handle_text(update)
                return

            # Команды.
            if text.startswith("/"):
                cmd = text.split()[0].lower().split("@")[0]
                if cmd in ("/start", "/help", "/pay", "/status", "/list", "/cancel"):
                    {
                        "/start":  handlers.cmd_start,
                        "/help":   handlers.cmd_help,
                        "/pay":    handlers.cmd_pay,
                        "/status": handlers.cmd_status,
                        "/list":   handlers.cmd_list,
                        "/cancel": handlers.cmd_cancel,
                    }[cmd](update)
                    return
                # Неизвестная команда.
                telegram_api.send_message(
                    chat_id,
                    f"Неизвестная команда: <code>{cmd}</code>. Напиши /help.",
                )
                return

            # Обычный текст (без состояния).
            handlers.handle_text(update)
            return

        if "callback_query" in update:
            handlers.handle_callback(update)
            return

        log.debug("Unknown update type, skipping: %s", list(update.keys()))
    except Exception:  # noqa: BLE001
        log.exception("route_update failed")


# ───────────────────────── Вебхук для Telegram ─────────────────────────

@app.route('/webhook', methods=['POST'])
def webhook_handler():
    """
    Точка входа для всех обновлений от Telegram.
    """
    # Проверяем, что запрос пришел в формате JSON
    if not request.is_json:
        log.warning("Получен не-JSON запрос на /webhook")
        abort(400) # Bad Request

    # Парсим JSON из тела запроса
    update = request.get_json()
    log.info(f"Получено обновление: {update.get('update_id')}")

    # Передаем обновление в наш роутер
    route_update(update)

    # Telegram ожидает ответ 'ok' (код 200), чтобы понять, что сообщение доставлено успешно.
    return jsonify({'status': 'ok'})


# ───────────────────────── Команды для управления ботом ─────────────────────────

@app.route('/set_webhook', methods=['GET'])
def set_webhook_route():
    """
    Эндпоинт для установки вебхука. Вызывается один раз при запуске приложения.
    """
    # Render автоматически подставляет внешний URL вашего сервиса в эту переменную.
    external_url = os.getenv('RENDER_EXTERNAL_URL')
    
    if not external_url:
        return "Переменная окружения RENDER_EXTERNAL_URL не задана.", 500

    try:
        # Используем функцию из telegram_api.py для установки вебхука
        result = telegram_api.set_webhook(f"{external_url}/webhook")
        log.info(f"Webhook установлен: {result}")
        return f"Webhook установлен на {external_url}/webhook"
    except Exception as e:
        log.error(f"Ошибка при установке вебхука: {e}")
        return f"Ошибка: {e}", 500


# ───────────────────────── Запуск приложения ─────────────────────────

if __name__ == "__main__":
    # Валидация конфига при локальном запуске
    errors = config.validate()
    if errors:
        log.error("Конфигурация неполная:")
        for e in errors:
            log.error("  • %s", e)
        sys.exit(1)

    log.info("Flask-приложение запущено. Задайте команды бота.")
    handlers.setup_bot_commands()

    # Запускаем сервер. Render сам передаст порт через переменную окружения.
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
