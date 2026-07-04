"""
Обработчики команд и callback-ов.

Каждый обработчик принимает update (dict) из Telegram и делает свою работу.
Весь I/O через telegram_api и api_2328.
"""
import logging

import api_2328
import config
import keyboards
import state
import telegram_api
import utils
from api_2328 import API2328Error
from telegram_api import TelegramError

log = logging.getLogger(__name__)


# ───────────────────────── Утилиты ─────────────────────────

def _safe_call(fn, *args, **kwargs):
    """Безопасно вызывает fn, возвращает (result, error_message)."""
    try:
        return fn(*args, **kwargs), None
    except API2328Error as e:
        log.exception("2328.io error")
        return None, f"Ошибка 2328.io: {e}"
    except TelegramError as e:
        log.exception("telegram error")
        return None, f"Ошибка Telegram: {e}"
    except Exception as e:  # noqa: BLE001
        log.exception("unexpected error")
        return None, f"Непредвиденная ошибка: {e}"


def _send(chat_id, text, reply_markup=None, reply_to=None):
    try:
        return telegram_api.send_message(chat_id, text, reply_markup=reply_markup, reply_to_message_id=reply_to)
    except TelegramError as e:
        log.error("send_message failed: %s", e)


# ───────────────────────── Команды ─────────────────────────

def cmd_start(update: dict):
    """Обработчик /start."""
    msg = update.get("message", {})
    chat_id = msg.get("chat", {}).get("id")
    user_id = msg.get("from", {}).get("id")

    if not config.is_admin(user_id):
        _send(chat_id, "⛔️ У вас нет доступа к этому боту.")
        return

    state.reset(user_id)
    name = msg.get("from", {}).get("first_name", "друг")
    text = (
        f"👋 Привет, <b>{name}</b>!\n\n"
        "Это бот для управления инвойсами <b>2328.io</b>.\n\n"
        "С помощью меню ниже ты можешь создавать платёжные ссылки, "
        "проверять статус инвойсов и просматривать историю.\n\n"
        "Также доступны команды:\n"
        "• <code>/pay &lt;сумма&gt; [валюта]</code> — быстрое создание инвойса\n"
        "• <code>/status &lt;uuid|order_id&gt;</code> — проверка статуса\n"
        "• <code>/list</code> — последние инвойсы\n"
        "• <code>/help</code> — справка"
    )
    _send(chat_id, text, reply_markup=keyboards.main_menu())


def cmd_help(update: dict):
    msg = update.get("message", {})
    chat_id = msg.get("chat", {}).get("id")
    text = (
        "<b>📋 Справка по боту 2328.io</b>\n\n"
        "<b>Команды:</b>\n"
        "• <code>/start</code> — главное меню\n"
        "• <code>/pay 100 USD</code> — создать инвойс на 100 USD\n"
        "• <code>/pay 0.001 BTC</code> — инвойс с крипто-суммой\n"
        "• <code>/status ORDER-12345</code> — статус по order_id\n"
        "• <code>/status &lt;uuid&gt;</code> — статус по UUID\n"
        "• <code>/list</code> — последние инвойсы\n"
        "• <code>/cancel</code> — отменить текущее действие\n\n"
        "<b>Кнопки в меню:</b>\n"
        "• <b>Создать инвойс</b> — пошаговый мастер\n"
        "• <b>Мои инвойсы</b> — последние N инвойсов (по умолчанию 10)\n"
        "• <b>Статус инвойса</b> — поиск по UUID или order_id\n\n"
        "💳 Платежи принимаются через 2328.io в криптовалюте. "
        "После создания инвойса плательщик переходит по ссылке и оплачивает "
        "в удобной криптовалюте и сети."
    )
    _send(chat_id, text, reply_markup=keyboards.back_to_menu())


def cmd_pay(update: dict):
    """
    /pay <amount> [currency] — быстрое создание инвойса.

    Примеры:
      /pay 100 USD
      /pay 50.5 EUR
      /pay 0.001 BTC
    """
    msg = update.get("message", {})
    chat_id = msg.get("chat", {}).get("id")
    user_id = msg.get("from", {}).get("id")

    if not config.is_admin(user_id):
        _send(chat_id, "⛔️ Доступ запрещён.")
        return

    text = (msg.get("text") or "").strip()
    parts = text.split()
    # parts[0] = "/pay"
    if len(parts) < 2:
        _send(
            chat_id,
            "Использование: <code>/pay &lt;сумма&gt; [валюта]</code>\n"
            "Например: <code>/pay 100 USD</code>",
        )
        return

    amount = parts[1]
    currency = parts[2].upper() if len(parts) >= 3 else config.DEFAULT_CURRENCY

    order_id = utils.gen_order_id()
    desc = f"Оплата через Telegram-бота, order {order_id}"

    _send(chat_id, f"⏳ Создаю инвойс на <b>{utils.format_amount(amount)} {currency}</b>…")
    inv, err = _safe_call(
        api_2328.create_payment,
        amount=amount,
        currency=currency,
        order_id=order_id,
        description=desc,
        ttl_seconds=config.DEFAULT_TTL,
    )
    if err:
        _send(chat_id, f"❌ {err}")
        return

    _send_invoice_card(chat_id, inv)


def cmd_status(update: dict):
    """/status <uuid|order_id> — проверка статуса."""
    msg = update.get("message", {})
    chat_id = msg.get("chat", {}).get("id")
    user_id = msg.get("from", {}).get("id")

    if not config.is_admin(user_id):
        _send(chat_id, "⛔️ Доступ запрещён.")
        return

    text = (msg.get("text") or "").strip()
    parts = text.split(maxsplit=1)
    if len(parts) < 2:
        state.set_state(user_id, state.STATE_WAIT_STATUS_QUERY)
        _send(
            chat_id,
            "Пришли <b>UUID</b> или <b>order_id</b> инвойса, "
            "чтобы я проверил его статус.",
            reply_markup=keyboards.cancel_keyboard(),
        )
        return

    _show_status(chat_id, parts[1].strip())


def cmd_list(update: dict):
    """/list — последние инвойсы."""
    msg = update.get("message", {})
    chat_id = msg.get("chat", {}).get("id")
    user_id = msg.get("from", {}).get("id")

    if not config.is_admin(user_id):
        _send(chat_id, "⛔️ Доступ запрещён.")
        return

    _show_list(chat_id)


def cmd_cancel(update: dict):
    msg = update.get("message", {})
    chat_id = msg.get("chat", {}).get("id")
    user_id = msg.get("from", {}).get("id")
    state.reset(user_id)
    _send(chat_id, "❌ Действие отменено.", reply_markup=keyboards.main_menu())


# ───────────────────────── Текстовые ответы (FSM) ─────────────────────────

def handle_text(update: dict):
    """Обработка текстовых сообщений, когда пользователь в каком-то состоянии."""
    msg = update.get("message", {})
    chat_id = msg.get("chat", {}).get("id")
    user_id = msg.get("from", {}).get("id")
    text = (msg.get("text") or "").strip()

    if not config.is_admin(user_id):
        _send(chat_id, "⛔️ Доступ запрещён.")
        return

    s = state.get_state(user_id)

    if s == state.STATE_WAIT_AMOUNT:
        _fsm_amount(chat_id, user_id, text)
    elif s == state.STATE_WAIT_CURRENCY:
        _fsm_currency(chat_id, user_id, text)
    elif s == state.STATE_WAIT_DESC:
        _fsm_desc(chat_id, user_id, text)
    elif s == state.STATE_WAIT_STATUS_QUERY:
        _show_status(chat_id, text)
        state.reset(user_id)
    else:
        _send(
            chat_id,
            "Не понимаю эту команду. Открой меню /start или посмотри /help.",
            reply_markup=keyboards.main_menu(),
        )


def _fsm_amount(chat_id, user_id, text):
    try:
        amount = float(text.replace(",", "."))
        if amount <= 0:
            raise ValueError
    except ValueError:
        _send(chat_id, "❌ Неверная сумма. Введи число, например <code>100</code> или <code>0.001</code>:")
        return
    state.update_data(user_id, amount=amount)
    state.set_state(user_id, state.STATE_WAIT_CURRENCY)
    _send(
        chat_id,
        f"✅ Сумма: <b>{utils.format_amount(amount)}</b>\n"
        "Теперь выбери валюту:",
        reply_markup=keyboards.currency_keyboard(),
    )


def _fsm_currency(chat_id, user_id, text):
    cur = text.upper()
    state.update_data(user_id, currency=cur)
    # Если это криптовалюта из нашего списка — предложим выбрать сеть.
    if cur in keyboards.NETWORKS:
        state.set_state(user_id, state.STATE_WAIT_NETWORK)
        _send(
            chat_id,
            f"✅ Валюта: <b>{cur}</b>\nВыбери сеть:",
            reply_markup=keyboards.network_keyboard(cur),
        )
    else:
        state.set_state(user_id, state.STATE_WAIT_DESC)
        _send(
            chat_id,
            f"✅ Валюта: <b>{cur}</b>\n"
            "Введи описание (или отправь <code>-</code>, чтобы пропустить):",
            reply_markup=keyboards.cancel_keyboard(),
        )


def _fsm_desc(chat_id, user_id, text):
    desc = None if text == "-" else text[:200]
    state.update_data(user_id, description=desc)
    _create_invoice_from_session(chat_id, user_id)


def _create_invoice_from_session(chat_id, user_id):
    data = state.get_data(user_id)
    amount = data.get("amount")
    currency = data.get("currency")
    network = data.get("network")
    to_currency = currency if currency in keyboards.NETWORKS else None
    desc = data.get("description")
    order_id = utils.gen_order_id()

    _send(chat_id, f"⏳ Создаю инвойс на <b>{utils.format_amount(amount)} {currency}</b>…")

    inv, err = _safe_call(
        api_2328.create_payment,
        amount=amount,
        currency=currency,
        order_id=order_id,
        to_currency=to_currency,
        network=network,
        description=desc or f"Оплата через бота, order {order_id}",
        ttl_seconds=config.DEFAULT_TTL,
    )
    if err:
        state.reset(user_id)
        _send(chat_id, f"❌ {err}", reply_markup=keyboards.main_menu())
        return

    state.reset(user_id)
    _send_invoice_card(chat_id, inv)


# ───────────────────────── Callback queries ─────────────────────────

def handle_callback(update: dict):
    cb = update.get("callback_query", {})
    cb_id = cb.get("id", "")
    data = cb.get("data", "")
    msg = cb.get("message", {})
    chat_id = msg.get("chat", {}).get("id")
    user_id = cb.get("from", {}).get("id")
    message_id = msg.get("message_id")

    if not config.is_admin(user_id):
        try:
            telegram_api.answer_callback_query(cb_id, text="⛔️ Доступ запрещён", show_alert=True)
        except TelegramError:
            pass
        return

    # Всегда отвечаем на callback, чтобы стрелочка крутилась.
    try:
        telegram_api.answer_callback_query(cb_id)
    except TelegramError:
        pass

    # Маршрутизация.
    if data == "main_menu":
        state.reset(user_id)
        _edit_or_send(chat_id, message_id, _menu_text(), keyboards.main_menu())

    elif data == "help":
        _edit_or_send(chat_id, message_id, _help_text(), keyboards.back_to_menu())

    elif data == "cancel":
        state.reset(user_id)
        _edit_or_send(chat_id, message_id, "❌ Действие отменено.", keyboards.main_menu())

    elif data == "new_invoice":
        state.set_state(user_id, state.STATE_WAIT_AMOUNT)
        _edit_or_send(
            chat_id,
            message_id,
            "🧾 <b>Создание инвойса</b>\n\nПришли сумму числом, например: <code>100</code> или <code>0.001</code>",
            keyboards.cancel_keyboard(),
        )

    elif data == "list_invoices":
        state.reset(user_id)
        _show_list(chat_id, edit_message_id=message_id)

    elif data == "status_search":
        state.set_state(user_id, state.STATE_WAIT_STATUS_QUERY)
        _edit_or_send(
            chat_id,
            message_id,
            "🔍 Пришли <b>UUID</b> или <b>order_id</b> инвойса:",
            keyboards.cancel_keyboard(),
        )

    elif data.startswith("cur:"):
        cur = data.split(":", 1)[1]
        if cur == "custom":
            state.set_state(user_id, state.STATE_WAIT_CURRENCY)
            _edit_or_send(
                chat_id,
                message_id,
                "✏️ Введи код валюты (например, <code>USD</code>, <code>USDT</code>, <code>BTC</code>):",
                keyboards.cancel_keyboard(),
            )
            return
        state.update_data(user_id, currency=cur)
        if cur in keyboards.NETWORKS:
            state.set_state(user_id, state.STATE_WAIT_NETWORK)
            _edit_or_send(
                chat_id,
                message_id,
                f"✅ Валюта: <b>{cur}</b>\nВыбери сеть:",
                keyboards.network_keyboard(cur),
            )
        else:
            state.set_state(user_id, state.STATE_WAIT_DESC)
            _edit_or_send(
                chat_id,
                message_id,
                f"✅ Валюта: <b>{cur}</b>\nВведи описание (или <code>-</code>, чтобы пропустить):",
                keyboards.cancel_keyboard(),
            )

    elif data.startswith("net:"):
        net = data.split(":", 1)[1]
        if net == "skip":
            state.update_data(user_id, network=None)
        else:
            state.update_data(user_id, network=net)
        cur = state.get_data(user_id).get("currency", "")
        state.set_state(user_id, state.STATE_WAIT_DESC)
        _edit_or_send(
            chat_id,
            message_id,
            f"✅ Сеть: <b>{net if net != 'skip' else '—'}</b>\n"
            f"Валюта: <b>{cur}</b>\n\n"
            "Введи описание (или <code>-</code>, чтобы пропустить):",
            keyboards.cancel_keyboard(),
        )

    elif data == "back_to_currency":
        state.set_state(user_id, state.STATE_WAIT_CURRENCY)
        _edit_or_send(
            chat_id,
            message_id,
            "Выбери валюту:",
            keyboards.currency_keyboard(),
        )

    elif data.startswith("refresh:"):
        uid = data.split(":", 1)[1]
        inv, err = _safe_call(api_2328.payment_info, uuid=uid)
        if err:
            _send(chat_id, f"❌ {err}")
            return
        _edit_or_send(
            chat_id,
            message_id,
            utils.format_invoice_message(inv),
            keyboards.invoice_actions(inv.get("uuid"), inv.get("url")),
        )

    else:
        log.warning("Unknown callback data: %s", data)


# ───────────────────────── Хелперы вывода ─────────────────────────

def _edit_or_send(chat_id, message_id, text, reply_markup):
    """Пытается отредактировать существующее сообщение, иначе отправляет новое."""
    try:
        telegram_api.edit_message_text(
            chat_id, message_id, text, reply_markup=reply_markup
        )
        return
    except TelegramError as e:
        # Если контент не изменился — это не ошибка, просто выходим.
        if "message is not modified" in str(e).lower():
            return
        log.debug("edit failed (%s), sending new message", e)
    _send(chat_id, text, reply_markup=reply_markup)


def _send_invoice_card(chat_id, inv: dict):
    """Отправляет карточку инвойса: текст + QR (если есть) + кнопки."""
    text = utils.format_invoice_message(inv)
    kb = keyboards.invoice_actions(inv.get("uuid"), inv.get("url"))

    # Если есть QR — отправим его как фото с подписью.
    qr_bytes = utils.decode_qr(inv.get("qr"))
    if qr_bytes:
        try:
            telegram_api.send_photo(chat_id, qr_bytes, caption=text, reply_markup=kb)
            return
        except TelegramError as e:
            log.warning("send_photo failed: %s — fallback to text", e)

    _send(chat_id, text, reply_markup=kb)


def _show_status(chat_id, query: str):
    """Показывает статус инвойса по UUID или order_id."""
    _send(chat_id, f"⏳ Проверяю <code>{query}</code>…")
    # Если строка похожа на UUID (содержит дефисы и длиной > 20) — ищем по uuid,
    # иначе считаем это order_id.
    if "-" in query and len(query) > 20:
        inv, err = _safe_call(api_2328.payment_info, uuid=query)
    else:
        inv, err = _safe_call(api_2328.payment_info, order_id=query)
    if err:
        _send(chat_id, f"❌ {err}", reply_markup=keyboards.back_to_menu())
        return
    _send_invoice_card(chat_id, inv)


def _show_list(chat_id, edit_message_id: int | None = None):
    """Показывает последние инвойсы."""
    res, err = _safe_call(api_2328.payment_list, page=1, per_page=config.LIST_LIMIT)
    if err:
        _send(chat_id, f"❌ {err}", reply_markup=keyboards.back_to_menu())
        return

    items = res.get("items") or res.get("data") or []
    # Иногда API возвращает просто список.
    if isinstance(res, list):
        items = res
    if not items:
        text = "📭 У тебя ещё нет инвойсов."
    else:
        lines = [f"📋 <b>Последние {len(items)} инвойсов:</b>\n"]
        for it in items:
            status = utils.status_label(it.get("payment_status"))
            amt = utils.format_amount(it.get("amount"))
            cur = it.get("currency", "")
            oid = it.get("order_id", "—")
            uid = it.get("uuid", "")
            lines.append(
                f"• <b>{amt} {cur}</b> — {status}\n"
                f"  order: <code>{oid}</code>\n"
                f"  uuid: <code>{uid[:24]}…</code>" if uid else f"  order: <code>{oid}</code>"
            )
            # Кнопка обновления — добавим в конце в виде инлайн-клавиатуры
            # (упрощённо: просто текстом)
        text = "\n".join(lines)
        text += "\n\nЧтобы проверить детальный статус, нажми «🔍 Статус инвойса» в меню."

    if edit_message_id:
        _edit_or_send(chat_id, edit_message_id, text, keyboards.back_to_menu())
    else:
        _send(chat_id, text, reply_markup=keyboards.back_to_menu())


def _menu_text() -> str:
    return (
        "🏠 <b>Главное меню</b>\n\n"
        "Выбери действие:"
    )


def _help_text() -> str:
    return (
        "<b>📋 Справка по боту 2328.io</b>\n\n"
        "• <code>/start</code> — главное меню\n"
        "• <code>/pay 100 USD</code> — создать инвойс\n"
        "• <code>/status &lt;id&gt;</code> — статус инвойса\n"
        "• <code>/list</code> — последние инвойсы\n"
        "• <code>/cancel</code> — отменить действие"
    )


# ───────────────────────── Регистрация команд ─────────────────────────

def setup_bot_commands():
    """Устанавливает меню команд бота в Telegram."""
    commands = [
        {"command": "start",   "description": "Открыть главное меню"},
        {"command": "pay",     "description": "Создать инвойс: /pay 100 USD"},
        {"command": "status",  "description": "Статус инвойса"},
        {"command": "list",    "description": "Последние инвойсы"},
        {"command": "help",    "description": "Справка"},
        {"command": "cancel",  "description": "Отменить текущее действие"},
    ]
    try:
        telegram_api.set_my_commands(commands)
        log.info("Bot commands registered.")
    except TelegramError as e:
        log.warning("setMyCommands failed: %s", e)
