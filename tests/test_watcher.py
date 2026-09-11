import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

from sms_cli.models import Message, MessageDirection
from sms_cli.store import MessageStore
from sms_cli.watcher import (
    DbusAddedSignal,
    IncomingSmsWatcher,
    _message_from_dbus_values,
)


class FakeNotifier:
    def __init__(self):
        self.notifications: list[tuple[str, str]] = []

    def notify(self, title: str, body: str) -> None:
        self.notifications.append((title, body))


class IncomingSmsWatcherTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store = MessageStore(Path(self.temp_dir.name) / "state.sqlite3")
        self.notifier = FakeNotifier()
        self.watcher = IncomingSmsWatcher(self.store, self.notifier)

    def tearDown(self):
        self.store.close()
        self.temp_dir.cleanup()

    def test_received_message_is_stored_before_one_notification(self):
        message = Message(
            modem_path="/org/freedesktop/ModemManager1/SMS/42",
            direction=MessageDirection.RECEIVED,
            number="+420123456789",
            text="Train is arriving.",
            timestamp=datetime(2026, 9, 11, 16, 0, tzinfo=UTC),
            state="received",
        )

        stored = self.watcher.handle_added(message, received=True)

        self.assertEqual(self.store.list_messages(), [stored])
        self.assertEqual(self.notifier.notifications, [("SMS from +420123456789", "Train is arriving.")])

    def test_notification_payload_is_bounded_but_stored_message_is_intact(self):
        message = Message(
            modem_path="/org/freedesktop/ModemManager1/SMS/44",
            direction=MessageDirection.RECEIVED,
            number="+420" + "1" * 300,
            text="x" * 5000,
            timestamp=None,
            state="received",
        )

        self.watcher.handle_added(message, received=True)

        title, body = self.notifier.notifications[0]
        self.assertLessEqual(len(title), 256)
        self.assertLessEqual(len(body), 4096)
        self.assertTrue(title.endswith("…"))
        self.assertTrue(body.endswith("…"))
        self.assertEqual(self.store.list_messages()[0].text, message.text)

    def test_duplicate_and_non_received_messages_do_not_notify(self):
        received = Message(
            modem_path="/org/freedesktop/ModemManager1/SMS/42",
            direction=MessageDirection.RECEIVED,
            number="+420123456789",
            text="Train is arriving.",
            timestamp=None,
            state="received",
        )
        sent = Message(
            modem_path="/org/freedesktop/ModemManager1/SMS/43",
            direction=MessageDirection.SENT,
            number="+420123456789",
            text="ETA 18:30",
            timestamp=None,
            state="sent",
        )

        self.watcher.handle_added(received, received=True)
        self.watcher.handle_added(received, received=True)
        self.watcher.handle_added(sent, received=False)

        self.assertEqual(len(self.notifier.notifications), 1)
        self.assertEqual(len(self.store.list_messages()), 1)
    def test_dbus_added_signal_only_accepts_received_paths_for_this_modem(self):
        signal = DbusAddedSignal("/org/freedesktop/ModemManager1/Modem/6")

        self.assertEqual(
            signal.parse(
                "signal time=0 sender=:1.2 -> destination=(null destination) "
                "path=/org/freedesktop/ModemManager1/Modem/6; "
                "interface=org.freedesktop.ModemManager1.Modem.Messaging; member=Added\n"
                "   object path \"/org/freedesktop/ModemManager1/SMS/42\"\n"
                "   boolean true"
            ),
            "/org/freedesktop/ModemManager1/SMS/42",
        )
        self.assertIsNone(
            signal.parse(
                "signal time=0 path=/org/freedesktop/ModemManager1/Modem/6; member=Added\n"
                "   object path \"/org/freedesktop/ModemManager1/SMS/42\"\n"
                "   boolean false"
            )
        )
        self.assertIsNone(
            signal.parse(
                "signal time=0 path=/org/freedesktop/ModemManager1/Modem/5; member=Added\n"
                "   object path \"/org/freedesktop/ModemManager1/SMS/42\"\n"
                "   boolean true"
            )
        )
    def test_dbus_properties_create_a_received_message(self):
        class Variant:
            def __init__(self, value):
                self.value = value

        message = _message_from_dbus_values(
            "/org/freedesktop/ModemManager1/SMS/42",
            {
                "Number": Variant("+420123456789"),
                "Text": Variant("Carrier reply"),
                "Timestamp": Variant("2026-09-11T16:00:00+00:00"),
                "State": Variant(3),
            },
        )

        self.assertEqual(message.direction, MessageDirection.RECEIVED)
        self.assertEqual(message.number, "+420123456789")
        self.assertEqual(message.timestamp, datetime(2026, 9, 11, 16, 0, tzinfo=UTC))
        self.assertIsNone(
            _message_from_dbus_values(
                "/org/freedesktop/ModemManager1/SMS/42", {"State": Variant(2)}
            )
        )


if __name__ == "__main__":
    unittest.main()
