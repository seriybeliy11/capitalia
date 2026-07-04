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
            chat_id = msg.get("chat", {}).get("id")
            user_id = msg.get("from", {}).get("id")

            # --- НАЧАЛО НОВОГО БЛОКА ---
            # Определяем, является ли сообщение командой
            is_command = False

            # 1. Проверяем, есть ли текст и начинается ли он с "/"
            text = msg.get("text")
            if text and text.startswith("/"):
                is_command = True

            # 2. Проверяем entities (на случай, если команда пришла без текста, например, через меню)
            entities = msg.get("entities")
            if not is_command and entities and isinstance(entities, list):
                for entity in entities:
                    if entity.get("type") == "bot_command":
                        is_command = True
                        break
            # --- КОНЕЦ НОВОГО БЛОКА ---

            # Логика состояния (FSM) теперь использует флаг is_command
            if user_id and state.get_state(user_id) != state.STATE_IDLE and not is_command:
                handlers.handle_text(update)
                return

            # Обработка команд с использованием нового флага
            if is_command:
                # Извлекаем команду безопасно
                cmd = text.split()[0].lower().split("@")[0] if text else ""
                if cmd == "/start":
                    handlers.cmd_start(update)
                    return

            handlers.handle_text(update)
            return

        elif "callback_query" in update:
            handlers.handle_callback(update)
            return

        log.debug("Unknown update type, skipping: %s", list(update.keys()))
    except Exception as e: # noqa: BLE001
        log.exception("route_update failed: %s", e)


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
