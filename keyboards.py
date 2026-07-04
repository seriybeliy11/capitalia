"""
Inline-клавиатуры для бота.

Все клавиатуры собираются как dict — так их понимает telegram_api.send_message.
Callback data короткие, чтобы уложиться в лимит 64 байта.
"""
import config

# Список популярных валют для выбора при создании инвойса.
FIAT_CURRENCIES = ["USD", "EUR", "RUB", "GBP", "UAH", "KZT", "TRY", "AED"]
CRYPTO_CURRENCIES = ["USDT", "TRX", "BTC", "ETH", "TON", "BNB", "SOL"]

# Сети для криптовалют (используется при выборе to_currency).
# Реальные коды нужно сверить с документацией 2328.io.
NETWORKS = {
    "USDT": ["TRX-TRC20", "ETH-ERC20", "BNB-BEP20", "TON"],
    "TRX":  ["TRX-TRC20"],
    "BTC":  ["BTC"],
    "ETH":  ["ETH-ERC20", "BNB-BEP20"],
    "TON":  ["TON"],
    "BNB":  ["BNB-BEP20"],
    "SOL":  ["SOL"],
}


def main_menu() -> dict:
    """Главное меню бота."""
    return {
        "inline_keyboard": [
            [{"text": "🧾 Создать инвойс", "callback_data": "new_invoice"}],
            [{"text": "📋 Мои инвойсы", "callback_data": "list_invoices"}],
            [{"text": "🔍 Статус инвойса", "callback_data": "status_search"}],
            [{"text": "❓ Помощь", "callback_data": "help"}],
        ]
    }


def currency_keyboard() -> dict:
    """Клавиатура выбора валюты суммы (fiat + crypto)."""
    rows = []
    # Fiat по 3 в ряд.
    for i in range(0, len(FIAT_CURRENCIES), 3):
        row = [{"text": c, "callback_data": f"cur:{c}"} for c in FIAT_CURRENCIES[i:i + 3]]
        rows.append(row)
    # Crypto по 3 в ряд.
    for i in range(0, len(CRYPTO_CURRENCIES), 3):
        row = [{"text": c, "callback_data": f"cur:{c}"} for c in CRYPTO_CURRENCIES[i:i + 3]]
        rows.append(row)
    rows.append([{"text": "✏️ Своя валюта", "callback_data": "cur:custom"}])
    rows.append([{"text": "← Отмена", "callback_data": "cancel"}])
    return {"inline_keyboard": rows}


def network_keyboard(currency: str) -> dict:
    """Клавиатура выбора сети для to_currency."""
    nets = NETWORKS.get(currency, [])
    if not nets:
        return {
            "inline_keyboard": [
                [{"text": "← Назад", "callback_data": "back_to_currency"}],
                [{"text": "← Отмена", "callback_data": "cancel"}],
            ]
        }
    rows = []
    for i in range(0, len(nets), 2):
        row = [{"text": n, "callback_data": f"net:{n}"} for n in nets[i:i + 2]]
        rows.append(row)
    rows.append([{"text": "⏭ Без выбора сети", "callback_data": "net:skip"}])
    rows.append([{"text": "← Назад", "callback_data": "back_to_currency"}])
    rows.append([{"text": "← Отмена", "callback_data": "cancel"}])
    return {"inline_keyboard": rows}


def invoice_actions(uuid: str, url: str | None) -> dict:
    """Клавиатура действий с созданным инвойсом."""
    rows = []
    if url:
        rows.append([{"text": "💳 Открыть страницу оплаты", "url": url}])
    rows.append([{"text": "🔄 Обновить статус", "callback_data": f"refresh:{uuid}"}])
    rows.append([{"text": "🏠 В меню", "callback_data": "main_menu"}])
    return {"inline_keyboard": rows}


def back_to_menu() -> dict:
    return {
        "inline_keyboard": [
            [{"text": "🏠 В меню", "callback_data": "main_menu"}],
        ]
    }


def cancel_keyboard() -> dict:
    return {
        "inline_keyboard": [
            [{"text": "← Отмена", "callback_data": "cancel"}],
        ]
    }
