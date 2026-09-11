import hashlib
import json
import os
import secrets
import sqlite3
import stat
from datetime import UTC, datetime
from pathlib import Path

from .models import Message, MessageDirection, PreparedAction


class MessageStore:
    def __init__(self, database_path: Path):
        database_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        _require_owner_only(database_path.parent, "state directory")
        database_exists = database_path.exists()
        if database_exists:
            _require_owner_only(database_path, "state database")
        else:
            descriptor = os.open(
                database_path,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                0o600,
            )
            os.close(descriptor)
        self.connection = sqlite3.connect(database_path)
        _require_owner_only(database_path, "state database")
        self.connection.row_factory = sqlite3.Row
        self._migrate()

    def close(self) -> None:
        self.connection.close()

    def _migrate(self) -> None:
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY,
                modem_path TEXT NOT NULL UNIQUE,
                direction TEXT NOT NULL,
                number TEXT NOT NULL,
                text TEXT NOT NULL,
                timestamp TEXT,
                state TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS prepared_actions (
                id INTEGER PRIMARY KEY,
                token TEXT NOT NULL UNIQUE,
                kind TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                payload_digest TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                consumed_at TEXT
            );
            """
        )
        self.connection.commit()

    def upsert_message(self, message: Message) -> Message:
        timestamp = _format_datetime(message.timestamp)
        self.connection.execute(
            """
            INSERT INTO messages (modem_path, direction, number, text, timestamp, state)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(modem_path) DO UPDATE SET
                direction = excluded.direction,
                number = excluded.number,
                text = excluded.text,
                timestamp = excluded.timestamp,
                state = excluded.state
            """,
            (
                message.modem_path,
                message.direction.value,
                message.number,
                message.text,
                timestamp,
                message.state,
            ),
        )
        self.connection.commit()
        row = self.connection.execute(
            "SELECT * FROM messages WHERE modem_path = ?", (message.modem_path,)
        ).fetchone()
        return _message_from_row(row)

    def list_messages(self) -> list[Message]:
        rows = self.connection.execute(
            "SELECT * FROM messages ORDER BY timestamp DESC, id DESC"
        ).fetchall()
        return [_message_from_row(row) for row in rows]

    def prepare_action(
        self, kind: str, payload: dict[str, str], expires_at: datetime
    ) -> PreparedAction:
        if expires_at.tzinfo is None:
            raise ValueError("expires_at must include a timezone")
        payload_json = _canonical_payload(payload)
        token = secrets.token_urlsafe(32)
        cursor = self.connection.execute(
            """
            INSERT INTO prepared_actions (token, kind, payload_json, payload_digest, expires_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (token, kind, payload_json, _digest(payload_json), _format_datetime(expires_at)),
        )
        self.connection.commit()
        return PreparedAction(cursor.lastrowid, token, kind, payload, expires_at)

    def get_prepared_action(self, token: str) -> PreparedAction:
        row = self.connection.execute(
            "SELECT * FROM prepared_actions WHERE token = ?", (token,)
        ).fetchone()
        if row is None:
            raise ValueError("unknown confirmation token")
        expires_at = _parse_datetime(row["expires_at"])
        if expires_at is None:
            raise RuntimeError("prepared action has no expiry")
        return PreparedAction(
            row["id"],
            row["token"],
            row["kind"],
            json.loads(row["payload_json"]),
            expires_at,
            _parse_datetime(row["consumed_at"]),
        )

    def consume_prepared_action(
        self, token: str, payload: dict[str, str], now: datetime | None = None
    ) -> PreparedAction:
        now = now or datetime.now(UTC)
        if now.tzinfo is None:
            raise ValueError("now must include a timezone")
        now_text = _format_datetime(now)
        payload_json = _canonical_payload(payload)
        row = self.connection.execute(
            "SELECT * FROM prepared_actions WHERE token = ?", (token,)
        ).fetchone()
        if row is None:
            raise ValueError("unknown confirmation token")
        if row["consumed_at"] is not None:
            raise ValueError("confirmation token already used")
        if _parse_datetime(row["expires_at"]) <= now:
            raise ValueError("confirmation token expired")
        if not secrets.compare_digest(row["payload_digest"], _digest(payload_json)):
            raise ValueError("confirmation payload does not match prepared action")
        cursor = self.connection.execute(
            """
            UPDATE prepared_actions
            SET consumed_at = ?
            WHERE id = ? AND consumed_at IS NULL AND expires_at > ?
            """,
            (now_text, row["id"], now_text),
        )
        if cursor.rowcount != 1:
            self.connection.rollback()
            raise ValueError("confirmation token already used or expired")
        self.connection.commit()
        return PreparedAction(
            row["id"],
            row["token"],
            row["kind"],
            json.loads(row["payload_json"]),
            _parse_datetime(row["expires_at"]),
            _parse_datetime(now_text),
        )


def _require_owner_only(path: Path, description: str) -> None:
    mode = stat.S_IMODE(path.stat().st_mode)
    if mode & 0o077:
        raise ValueError(f"{description} must be owner-only (expected mode 0700 or 0600)")


def _canonical_payload(payload: dict[str, str]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _digest(payload_json: str) -> str:
    return hashlib.sha256(payload_json.encode("utf-8")).hexdigest()


def _format_datetime(value: datetime | None) -> str | None:
    return value.astimezone(UTC).isoformat() if value is not None else None


def _parse_datetime(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value is not None else None


def _message_from_row(row: sqlite3.Row) -> Message:
    return Message(
        id=row["id"],
        modem_path=row["modem_path"],
        direction=MessageDirection(row["direction"]),
        number=row["number"],
        text=row["text"],
        timestamp=_parse_datetime(row["timestamp"]),
        state=row["state"],
    )
