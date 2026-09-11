from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class MessageDirection(StrEnum):
    RECEIVED = "received"
    SENT = "sent"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class Message:
    modem_path: str
    direction: MessageDirection
    number: str
    text: str
    timestamp: datetime | None
    state: str
    id: int | None = None


@dataclass(frozen=True)
class PreparedAction:
    id: int
    token: str
    kind: str
    payload: dict[str, str]
    expires_at: datetime
    consumed_at: datetime | None = None
