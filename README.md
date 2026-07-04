# Telegram-бот для 2328.io (на чистом `requests`)

Бот управляет крипто-инвойсами через [Payment API 2328.io](https://2328.io).
Без фреймворков вроде aiogram/telebot — только `requests` к Telegram Bot API и к API 2328.io.
Готов к деплою на **Render** как Background Worker (long polling).

## Возможности

- 🧾 **Создание инвойса** — пошаговый мастер (сумма → валюта → сеть → описание) или команда `/pay 100 USD`.
- 🔍 **Проверка статуса** — по `uuid` или `order_id`, с обновлением по кнопке.
- 📋 **Список инвойсов** — последние N инвойсов с их статусами.
- 🏠 **Inline-меню** — главное меню с кнопками.
- 🖼 **QR-код** — если 2328.io вернул `qr`, бот отправляет его как фото.
- 🔒 **Список админов** — доступ можно ограничить по `user_id`.
- ⏳ **Long polling** — стабильная работа в Render Background Worker.

## Команды

| Команда                     | Описание                                                |
|-----------------------------|---------------------------------------------------------|
| `/start`                    | Главное меню                                            |
| `/pay 100 USD`              | Быстрый инвойс на 100 USD                               |
| `/pay 0.001 BTC`            | Инвойс с крипто-суммой                                  |
| `/status <uuid\|order_id>`  | Статус инвойса                                          |
| `/list`                     | Последние инвойсы                                       |
| `/help`                     | Справка                                                 |
| `/cancel`                   | Отменить текущее действие                               |

## Структура проекта

```
tg-bot-2328/
├── bot.py              # Точка входа: цикл long polling + роутинг апдейтов
├── handlers.py         # Обработчики команд и callback-ов
├── api_2328.py         # Клиент 2328.io API с HMAC-подписью
├── telegram_api.py     # Обёртка над Telegram Bot API на requests
├── state.py            # FSM: состояния пользователей в памяти
├── keyboards.py        # Inline-клавиатуры
├── utils.py            # Форматирование, генерация order_id, декодирование QR
├── config.py           # Чтение env-переменных
├── requirements.txt    # Зависимости (requests + python-dotenv)
├── render.yaml         # Blueprint для Render Background Worker
├── Procfile            # Альтернативный старт для Render/Heroku
├── .env.example        # Шаблон переменных окружения
├── .gitignore
└── README.md           # этот файл
```

## Локальный запуск

1. **Установить Python 3.10+**.

2. **Клонировать репозиторий**:
   ```bash
   git clone <your-repo-url>
   cd tg-bot-2328
   ```

3. **Создать виртуальное окружение и установить зависимости**:
   ```bash
   python -m venv .venv
   source .venv/bin/activate          # на Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

4. **Создать `.env`** на основе `.env.example` и заполнить значения:
   ```bash
   cp .env.example .env
   ```
   Минимум нужно:
   - `TELEGRAM_BOT_TOKEN` — токен от [@BotFather](https://t.me/BotFather)
   - `PROJECT_UUID` — Project UUID из кабинета 2328.io
   - `API_KEY` — API key из кабинета 2328.io
   - `ADMIN_IDS` — твой Telegram user_id (узнать у [@userinfobot](https://t.me/userinfobot))

5. **Запустить бота**:
   ```bash
   python bot.py
   ```

## Деплой на Render

Проект уже подготовлен: есть `render.yaml` (Blueprint) и `Procfile`.

### Вариант A — через Blueprint (рекомендуется)

1. Залей проект в GitHub/GitLab.
2. На [render.com](https://render.com) → **New** → **Blueprint**.
3. Выбери репозиторий — Render автоматически подхватит `render.yaml`.
4. В разделе **Environment** сервиса `tg-bot-2328` задай секреты:
   - `TELEGRAM_BOT_TOKEN`
   - `PROJECT_UUID`
   - `API_KEY`
   - `ADMIN_IDS`
5. Render сам установит зависимости и запустит `python bot.py` как **Background Worker**.
6. Готово — бот работает 24/7, автоматически перезапускается при падении.

### Вариант B — вручную через Web UI

1. **New** → **Background Worker**.
2. Подключи репозиторий.
3. **Build Command**: `pip install -r requirements.txt`
4. **Start Command**: `python bot.py`
5. **Environment Variables** — добавь те же переменные, что и в `.env.example`.
6. Нажми **Create Background Worker**.

> ⚠️ На бесплатном тарифе Render Background Worker уходит в сон после неактивности.
> Для постоянной работы бота нужен платный тариф.

## ⚠️ Важно про подпись запросов (sign)

В `api_2328.py` подпись HMAC считается так:

```python
HMAC-SHA256( API_KEY, compact_sorted_json(body) ) → base64
```

Это стандартный вариант, который использует большинство подобных платёжных API.
**Если 2328.io ожидает другой формат подписи** (например, hex вместо base64,
или md5 вместо sha256, или подпись `body + API_KEY` без HMAC), —
поправь функцию `_sign()` в `api_2328.py`. Точная схема обычно описана
в закрытой документации проекта 2328.io или в личном кабинете.

## Получение ключей 2328.io

1. Зарегистрируйся на [2328.io](https://2328.io).
2. Создай проект (merchant).
3. В настройках проекта найди:
   - **Project UUID** — копируй в `PROJECT_UUID`
   - **API key** — копируй в `API_KEY` (хранится в секрете!)

## Получение токена Telegram

1. Открой [@BotFather](https://t.me/BotFather).
2. Команда `/newbot` → задай имя и username.
3. Полученный токен скопируй в `TELEGRAM_BOT_TOKEN`.
4. (Опц.) `/setcommands` → задай список команд — бот умеет делать это сам при старте через `setMyCommands`.

## Ограничение доступа

По умолчанию бот работает только для `ADMIN_IDS`. Это защищает его от случайных
пользователей. Чтобы сделать его публичным, оставь `ADMIN_IDS` пустым —
тогда бот будет отвечать всем.

## Возможные улучшения

- Вебхук-режим вместо long polling (нужен публичный HTTPS URL).
- Персистентное хранение инвойсов в SQLite/PostgreSQL.
- Уведомления о платежах через `url_callback` от 2328.io.
- Локализация (RU/EN).
- Мульти-валютные инвойсы с автоматической конвертацией.

## Лицензия

MIT — делай с кодом что хочешь.
