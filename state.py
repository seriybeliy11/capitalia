"""
Простое управление состояниями пользователей (FSM на чистом Python).

Хранится в памяти процесса. После рестарта состояния сбрасываются —
это нормально для бота в long polling режиме. Если нужна персистентность,
можно добавить сохранение в JSON-файл (см. миграции в README).
"""
from dataclasses import dataclass, field
from typing import Any

# Возможные состояния.
STATE_IDLE = "idle"
STATE_WAIT_AMOUNT = "wait_amount"
STATE_WAIT_CURRENCY = "wait_currency"
STATE_WAIT_NETWORK = "wait_network"
STATE_WAIT_ORDER_ID = "wait_order_id"
STATE_WAIT_DESC = "wait_desc"
STATE_WAIT_STATUS_QUERY = "wait_status_query"


@dataclass
class UserSession:
    user_id: int
    state: str = STATE_IDLE
    data: dict = field(default_factory=dict)  # накопленные данные для текущей операции

    def reset(self):
        self.state = STATE_IDLE
        self.data = {}


# Хранилище: user_id → UserSession
_sessions: dict[int, UserSession] = {}


def get_session(user_id: int) -> UserSession:
    if user_id not in _sessions:
        _sessions[user_id] = UserSession(user_id=user_id)
    return _sessions[user_id]


def set_state(user_id: int, state: str, **data):
    s = get_session(user_id)
    s.state = state
    if data:
        s.data.update(data)


def update_data(user_id: int, **data):
    s = get_session(user_id)
    s.data.update(data)


def reset(user_id: int):
    s = get_session(user_id)
    s.reset()


def get_data(user_id: int) -> dict:
    return get_session(user_id).data


def get_state(user_id: int) -> str:
    return get_session(user_id).state
