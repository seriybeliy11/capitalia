"""
Вспомогательные функции: форматирование, генерация order_id, обработка QR.
"""
import base64
import time
import uuid as uuid_lib
from datetime import datetime, timezone


def gen_order_id(prefix: str = "TG") -> str:
    """Генерирует уникальный order_id до 128 символов."""
    return f"{prefix}-{int(time.time())}-{uuid_lib.uuid4().hex[:8]}"


def format_amount(value) -> str:
    """Преобразует число/строку в красивое строковое представление."""
    try:
        f = float(value)
        if f == int(f):
            return f"{int(f):,.0f}".replace(",", " ")
        return f"{f:,.2f}".replace(",", " ").rstrip("0").rstrip(".")
    except (TypeError, ValueError):
        return str(value)


def parse_iso_dt(iso: str | None) -> str:
    """Преобразует ISO 8601 в человекочитаемый вид. Возвращает исходную строку при ошибке."""
    if not iso:
        return "—"
    try:
        # 2328.io возвращает время в UTC, напр. "2026-01-11T20:00:00Z"
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return dt.strftime("%d.%m.%Y %H:%M UTC")
    except (ValueError, TypeError):
        return iso


# Человекочитаемые статусы платежа.
STATUS_LABELS = {
    "check":         "⏳ Ожидает оплаты",
    "paid":          "✅ Оплачен",
    "confirmed":     "✅ Подтверждён",
    "expired":       "❌ Истёк",
    "fail":          "❌ Ошибка",
    "cancel":        "❌ Отменён",
    "system_fail":   "❌ Системная ошибка",
    "wrong_amount":  "❌ Неверная сумма",
    "overpaid":      "⚠️ Переплата",
    "underpaid":     "⚠️ Недоплата",
}


def status_label(status: str | None) -> str:
    if not status:
        return "—"
    return STATUS_LABELS.get(status, status)


def decode_qr(data_uri: str | None) -> bytes | None:
    """
    Декодирует data URI вида "data:image/png;base64,iVBORw0..." в байты PNG.
    Возвращает None, если data_uri пустой или имеет неверный формат.
    """
    if not data_uri:
        return None
    if "," not in data_uri:
        return None
    _, b64 = data_uri.split(",", 1)
    try:
        return base64.b64decode(b64)
    except Exception:
        return None


def format_invoice_message(inv: dict) -> str:
    """Форматирует словарь платежа в HTML-сообщение для Telegram."""
    lines = [
        f"🧾 <b>Инвойс #{inv.get('order_id', '—')}</b>",
        "",
        f"💰 <b>Сумма:</b> {format_amount(inv.get('amount'))} {inv.get('currency', '')}",
    ]

    payer_amount = inv.get("payer_amount")
    payer_currency = inv.get("payer_currency")
    if payer_amount and payer_currency:
        lines.append(f"🔁 <b>К оплате:</b> {format_amount(payer_amount)} {payer_currency}")

    network = inv.get("network")
    if network:
        lines.append(f"🌐 <b>Сеть:</b> <code>{network}</code>")

    address = inv.get("address")
    if address:
        lines.append(f"📍 <b>Адрес:</b> <code>{address}</code>")

    rate = inv.get("exchange_rate")
    if rate:
        lines.append(f"📈 <b>Курс:</b> {rate}")

    lines.append(f"📦 <b>Статус:</b> {status_label(inv.get('payment_status'))}")
    lines.append(f"⏰ <b>Создан:</b> {parse_iso_dt(inv.get('created_at'))}")
    lines.append(f"⏳ <b>Истекает:</b> {parse_iso_dt(inv.get('expires_at'))}")

    txid = inv.get("txid")
    if txid:
        lines.append(f"🔗 <b>TXID:</b> <code>{txid}</code>")

    payment_amount = inv.get("payment_amount")
    if payment_amount:
        lines.append(f"💵 <b>Получено:</b> {format_amount(payment_amount)}")

    if inv.get("uuid"):
        lines.append(f"\n🆔 <code>{inv['uuid']}</code>")

    return "\n".join(lines)
