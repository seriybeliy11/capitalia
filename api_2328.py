"""
Клиент 2328.io Payment API.

Все методы используют библиотеку requests и подписывают запросы HMAC.
Поддерживаются: создание инвойса, получение статуса, список инвойсов.

⚠️ ВАЖНО про подпись (sign):
   2328.io ожидает в заголовке `sign` HMAC-подпись тела запроса.
   Стандартный способ — HMAC-SHA256 от JSON-тела с использованием API_KEY в качестве секрета,
   результат закодирован в base64. Если ваш проект использует другой алгоритм
   (например, hex, или md5 как у Cryptomus), измените функцию `_sign`.
"""
import base64
import hashlib
import hmac
import json
import logging

import requests

import config

log = logging.getLogger(__name__)


class API2328Error(Exception):
    """Ошибка при вызове 2328.io API."""

    def __init__(self, message: str, status_code: int | None = None, payload: dict | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload or {}


def _sign(body: dict) -> str:
    """
    Вычисляет подпись HMAC для запроса к 2328.io.

    Используется: HMAC-SHA256( API_KEY, compact JSON body ) → base64.
    JSON сортируется по ключам, чтобы подпись была детерминированной.
    """
    payload_str = json.dumps(body, separators=(",", ":"), sort_keys=True, ensure_ascii=False)
    digest = hmac.new(
        key=config.API_KEY.encode("utf-8"),
        msg=payload_str.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).digest()
    return base64.b64encode(digest).decode("utf-8")


def _headers(body: dict) -> dict:
    """Собирает заголовки для запроса к 2328.io."""
    return {
        "Content-Type": "application/json",
        "User-Agent": config.API_USER_AGENT,
        "project": config.PROJECT_UUID,
        "sign": _sign(body),
    }


def _request(method: str, path: str, body: dict) -> dict:
    """Базовый POST-запрос к 2328.io. Возвращает result из ответа."""
    url = f"{config.API_BASE_URL}{path}"
    headers = _headers(body)

    # Убираем ключи со значением None / "" — API их не ждёт.
    clean_body = {k: v for k, v in body.items() if v not in (None, "", [])}

    log.debug("→ 2328.io %s body=%s", url, clean_body)
    try:
        resp = requests.post(
            url,
            data=json.dumps(clean_body, ensure_ascii=False).encode("utf-8"),
            headers=headers,
            timeout=config.REQUEST_TIMEOUT,
        )
    except requests.RequestException as e:
        raise API2328Error(f"Сетевая ошибка: {e}") from e

    try:
        data = resp.json()
    except ValueError:
        raise API2328Error(
            f"Не удалось распарсить JSON. HTTP {resp.status_code}. Body: {resp.text[:300]}",
            status_code=resp.status_code,
        )

    if resp.status_code >= 400 or data.get("state") not in (0, None):
        raise API2328Error(
            data.get("message") or data.get("error") or f"HTTP {resp.status_code}",
            status_code=resp.status_code,
            payload=data,
        )

    return data.get("result", data)


# ───────────────────────── Публичные методы ─────────────────────────

def create_payment(
    amount: str | float,
    currency: str,
    order_id: str,
    *,
    to_currency: str | None = None,
    network: str | None = None,
    description: str | None = None,
    ttl_seconds: int | None = None,
    fee_split: float | None = None,
    price_markup: float | None = None,
    invite_code: str | None = None,
) -> dict:
    """
    Создаёт платёжную сессию.

    :param amount:        Сумма, напр. "100.00"
    :param currency:      Валюта суммы (USD, EUR, RUB, USDT, BTC, …)
    :param order_id:      Ваш order ID (до 128 символов)
    :param to_currency:   Целевая криптовалюта (опц.)
    :param network:       Сеть (обязателен, если задан to_currency)
    :param description:   Описание инвойса (до 200 символов)
    :param ttl_seconds:   Время жизни инвойса (300..86400)
    :param fee_split:     Доля комиссии, оплачиваемая плательщиком (0..100)
    :param price_markup:  Наценка/скидка (-99..100)
    :param invite_code:   Реферальный код
    :return:              Словарь с полями uuid, url, qr, payment_status, …
    """
    body = {
        "amount": str(amount),
        "currency": currency,
        "order_id": order_id,
    }
    if to_currency:
        body["to_currency"] = to_currency
    if network:
        body["network"] = network
    if description:
        body["description"] = description[:200]
    if ttl_seconds:
        body["ttl_seconds"] = int(ttl_seconds)
    if fee_split is not None:
        body["fee_split"] = fee_split
    if price_markup is not None:
        body["price_markup"] = price_markup
    if invite_code:
        body["invite_code"] = invite_code
    if config.CALLBACK_URL:
        body["url_callback"] = config.CALLBACK_URL
    if config.SUCCESS_URL:
        body["url_success"] = config.SUCCESS_URL
    if config.RETURN_URL:
        body["url_return"] = config.RETURN_URL

    return _request("POST", "/payment", body)


def payment_info(*, uuid: str | None = None, order_id: str | None = None) -> dict:
    """
    Получает информацию о платеже по uuid или order_id.
    Хотя бы один из параметров обязателен.
    """
    if not uuid and not order_id:
        raise API2328Error("Нужно указать uuid или order_id")
    body = {}
    if uuid:
        body["uuid"] = uuid
    if order_id:
        body["order_id"] = order_id
    return _request("POST", "/payment/info", body)


def payment_list(
    *,
    status: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    page: int = 1,
    per_page: int = 15,
) -> dict:
    """
    Получает список платежей с фильтром и пагинацией.
    :param status:    Фильтр по статусу (check, paid, expired, …)
    :param date_from: Дата начала (YYYY-MM-DD)
    :param date_to:   Дата конца (YYYY-MM-DD)
    :param page:      Номер страницы
    :param per_page:  Записей на страницу (макс. 5000)
    """
    body = {
        "page": page,
        "per_page": per_page,
    }
    if status:
        body["status"] = status
    if date_from:
        body["date_from"] = date_from
    if date_to:
        body["date_to"] = date_to
    return _request("POST", "/payment/list", body)
