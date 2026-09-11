"""Carrier-safe operations exposed by the local MCP server."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from .carriers import CarrierProfile
from .models import Message, PreparedAction
from .service import SmsService
from .store import MessageStore

_MAX_TOKEN_LIFETIME = timedelta(minutes=5)


class McpService:
    """Keep MCP handlers thin while enforcing prepare/confirm boundaries."""

    def __init__(
        self,
        service: SmsService,
        store: MessageStore,
        profile: CarrierProfile,
        *,
        token_lifetime: timedelta = timedelta(minutes=2),
    ) -> None:
        if token_lifetime <= timedelta() or token_lifetime > _MAX_TOKEN_LIFETIME:
            raise ValueError("token_lifetime must be between zero and five minutes")
        self.service = service
        self.store = store
        self.profile = profile
        self.token_lifetime = token_lifetime

    def close(self) -> None:
        self.store.close()

    def list_messages(self) -> list[dict[str, Any]]:
        return [_message_data(message) for message in self.service.sync_messages()]

    def read_message(self, message_id: int) -> dict[str, Any]:
        if isinstance(message_id, bool) or not isinstance(message_id, int) or message_id < 1:
            raise ValueError("message_id must be a positive integer")
        for message in self.service.sync_messages():
            if message.id == message_id:
                return _message_data(message)
        raise ValueError(f"unknown message ID: {message_id}")

    def get_credit(self) -> dict[str, str]:
        command = self.profile.credit_query()
        return {
            "carrier": self.profile.name,
            "ussd_code": self.profile.credit_ussd(),
            "response": self.service.query_credit(self.profile.credit_ussd()),
            "warning": "This is a carrier-side USSD request; billing depends on your tariff.",
            "source_url": command.source_url,
            "observed_at": command.observed_at.isoformat(),
        }

    def list_packages(self) -> list[dict[str, Any]]:
        return [
            {
                "id": package.id,
                "name": package.name,
                "allowance": package.allowance,
                "duration": package.duration,
                "price": package.price,
                "source_url": package.source_url,
                "observed_at": package.observed_at.isoformat(),
                "stale": package.is_stale(),
                "notes": package.notes,
            }
            for package in self.profile.packages
        ]

    def get_package_status(self, package_id: str) -> dict[str, Any]:
        package = self.profile.package(package_id)
        if "status" not in package.commands:
            raise ValueError(f"package {package_id} does not support status")
        return {
            "package_id": package.id,
            "package_name": package.name,
            "status": "requires_prepare",
            "warning": "Checking package status sends an SMS and must be prepared and confirmed.",
        }

    def prepare_send_sms(
        self,
        recipient: str,
        text: str,
        *,
        expires_at: datetime | None = None,
    ) -> dict[str, Any]:
        payload = {"number": recipient, "text": text}
        self._validate_send_payload(payload)
        prepared = self.store.prepare_action(
            kind="send_sms", payload=payload, expires_at=expires_at or self._expiry()
        )
        return _prepared_data(prepared, status="prepared", warning="No SMS has been sent.")

    def confirm_send_sms(self, token: str) -> dict[str, Any]:
        prepared = self._consume(token, "send_sms")
        message = self.service.send_message(prepared.payload["number"], prepared.payload["text"])
        return {
            "status": "dispatched_pending_confirmation",
            "message": _message_data(message),
            "warning": "The SMS was dispatched; no carrier or recipient confirmation has been received.",
        }

    def prepare_package_action(self, package_id: str, action: str) -> dict[str, Any]:
        preview = self.profile.prepare_package_action(package_id, action)
        payload = {"recipient": preview.command.recipient, "text": preview.command.text}
        prepared = self.store.prepare_action(
            kind="package_action", payload=payload, expires_at=self._expiry()
        )
        result = _prepared_data(
            prepared,
            status="prepared",
            warning="No SMS has been sent; carrier billing and outcome remain uncertain.",
        )
        result.update(
            {
                "package_id": preview.package_id,
                "package_name": preview.package_name,
                "action": preview.action,
                "price": preview.price,
                "source_url": preview.source_url,
                "observed_at": preview.observed_at.isoformat(),
                "stale": preview.stale,
                "notes": preview.notes,
            }
        )
        return result

    def confirm_package_action(self, token: str) -> dict[str, Any]:
        prepared = self._consume(token, "package_action")
        message = self.service.send_message(prepared.payload["recipient"], prepared.payload["text"])
        return {
            "status": "dispatched_pending_confirmation",
            "message": _message_data(message),
            "warning": "The SMS was dispatched; package activation or status is not confirmed until a carrier response is recorded.",
        }

    def _consume(self, token: str, expected_kind: str) -> PreparedAction:
        if not isinstance(token, str) or not token:
            raise ValueError("confirmation token must be a non-empty string")
        prepared = self.store.get_prepared_action(token)
        if prepared.kind != expected_kind:
            raise ValueError(f"confirmation token is not a {expected_kind} action")
        return self.store.consume_prepared_action(token, prepared.payload)

    def _expiry(self) -> datetime:
        return datetime.now(UTC) + self.token_lifetime

    @staticmethod
    def _validate_send_payload(payload: dict[str, str]) -> None:
        if not isinstance(payload["number"], str) or not payload["number"]:
            raise ValueError("recipient number cannot be empty")
        if not isinstance(payload["text"], str) or not payload["text"]:
            raise ValueError("message text cannot be empty")


def _message_data(message: Message) -> dict[str, Any]:
    return {
        "id": message.id,
        "modem_path": message.modem_path,
        "direction": message.direction.value,
        "number": message.number,
        "text": message.text,
        "timestamp": message.timestamp.isoformat() if message.timestamp else None,
        "state": message.state,
    }


def _prepared_data(prepared: PreparedAction, *, status: str, warning: str) -> dict[str, Any]:
    return {
        "status": status,
        "token": prepared.token,
        "expires_at": prepared.expires_at.isoformat(),
        "recipient": prepared.payload.get("recipient", prepared.payload.get("number")),
        "text": prepared.payload["text"],
        "warning": warning,
    }
