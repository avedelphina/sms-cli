"""Signal-driven incoming SMS persistence and desktop notification helpers."""

from __future__ import annotations

import re
import subprocess
from datetime import datetime
from typing import Protocol

from .models import Message, MessageDirection
from .store import MessageStore

_SMS_PATH = re.compile(r"/org/freedesktop/ModemManager1/SMS/[0-9]+")
_MESSAGING_INTERFACE = "org.freedesktop.ModemManager1.Modem.Messaging"
_SMS_INTERFACE = "org.freedesktop.ModemManager1.Sms"
_PROPERTIES_INTERFACE = "org.freedesktop.DBus.Properties"
_MAX_NOTIFICATION_TITLE = 256
_MAX_NOTIFICATION_BODY = 4096


def _notification_text(text: str, limit: int) -> str:
    return text if len(text) <= limit else f"{text[: limit - 1]}…"


class Notifier(Protocol):
    def notify(self, title: str, body: str) -> None: ...


class DesktopNotifier:
    """Send a local desktop notification without forwarding SMS content elsewhere."""

    def notify(self, title: str, body: str) -> None:
        subprocess.run(["notify-send", "--app-name=sms-cli", title, body], check=True)


class IncomingSmsWatcher:
    """Persist network-received SMS before notifying, with restart-safe deduplication."""

    def __init__(self, store: MessageStore, notifier: Notifier) -> None:
        self.store = store
        self.notifier = notifier

    def handle_added(self, message: Message, *, received: bool) -> Message | None:
        if not received or message.direction is not MessageDirection.RECEIVED:
            return None
        known_paths = {stored.modem_path for stored in self.store.list_messages()}
        stored = self.store.upsert_message(message)
        if message.modem_path not in known_paths:
            self.notifier.notify(
                _notification_text(f"SMS from {stored.number}", _MAX_NOTIFICATION_TITLE),
                _notification_text(stored.text, _MAX_NOTIFICATION_BODY),
            )
        return stored


class DbusAddedSignal:
    """Recognize only received ``Messaging.Added`` signals for one modem path."""

    def __init__(self, modem_path: str) -> None:
        if not re.fullmatch(r"/org/freedesktop/ModemManager1/Modem/[0-9]+", modem_path):
            raise ValueError("modem path must be a ModemManager modem object path")
        self.modem_path = modem_path

    def parse(self, signal_text: str) -> str | None:
        if "Added" not in signal_text or "true" not in signal_text:
            return None
        if f"path={self.modem_path}" not in signal_text and not signal_text.startswith(
            f"{self.modem_path}:"
        ):
            return None
        match = _SMS_PATH.search(signal_text)
        return match.group(0) if match else None


class ModemManagerDbusWatcher:
    """Subscribe to ModemManager's ``Messaging.Added`` signal; never poll."""

    def __init__(self, modem_id: str, watcher: IncomingSmsWatcher) -> None:
        if not modem_id.isdecimal():
            raise ValueError("modem ID must be a decimal ModemManager ID")
        self.modem_path = f"/org/freedesktop/ModemManager1/Modem/{modem_id}"
        self.watcher = watcher

    async def run(self) -> None:
        from dbus_next.aio import MessageBus
        from dbus_next.constants import BusType

        bus = await MessageBus(bus_type=BusType.SYSTEM).connect()
        modem = await self._proxy_interface(bus, self.modem_path, _MESSAGING_INTERFACE)
        modem.on_added(self._on_added(bus))
        await bus.wait_for_disconnect()

    def _on_added(self, bus):
        def callback(sms_path: str, received: bool) -> None:
            if received:
                import asyncio

                asyncio.create_task(self._store_received(bus, sms_path))

        return callback

    async def _store_received(self, bus, sms_path: str) -> None:
        if not _SMS_PATH.fullmatch(sms_path):
            return
        properties = await self._proxy_interface(bus, sms_path, _PROPERTIES_INTERFACE)
        values = await properties.call_get_all(_SMS_INTERFACE)
        message = _message_from_dbus_values(sms_path, values)
        if message is not None:
            self.watcher.handle_added(message, received=True)

    @staticmethod
    async def _proxy_interface(bus, path: str, interface_name: str):
        introspection = await bus.introspect("org.freedesktop.ModemManager1", path)
        proxy = bus.get_proxy_object("org.freedesktop.ModemManager1", path, introspection)
        return proxy.get_interface(interface_name)


def _message_from_dbus_values(sms_path: str, values: dict[str, object]) -> Message | None:
    def value(name: str, default: str = "") -> str:
        item = values.get(name)
        return str(getattr(item, "value", default))

    if value("State") != "3":
        return None
    timestamp_text = value("Timestamp")
    try:
        timestamp = datetime.fromisoformat(timestamp_text) if timestamp_text else None
    except ValueError:
        timestamp = None
    return Message(
        modem_path=sms_path,
        direction=MessageDirection.RECEIVED,
        number=value("Number"),
        text=value("Text"),
        timestamp=timestamp,
        state="received",
    )
