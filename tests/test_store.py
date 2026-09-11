import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sms_cli.models import Message, MessageDirection
from sms_cli.store import MessageStore


class MessageStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store = MessageStore(Path(self.temp_dir.name) / "state.sqlite3")

    def tearDown(self):
        self.store.close()
        self.temp_dir.cleanup()

    def test_upsert_received_message_is_idempotent(self):
        message = Message(
            modem_path="/org/freedesktop/ModemManager1/SMS/42",
            direction=MessageDirection.RECEIVED,
            number="+420123456789",
            text="Train arrives at 18:30.",
            timestamp=datetime(2026, 9, 11, 16, 0, tzinfo=UTC),
            state="received",
        )

        first = self.store.upsert_message(message)
        second = self.store.upsert_message(message)

        self.assertEqual(first.id, second.id)
        self.assertEqual(self.store.list_messages(), [first])

    def test_confirmation_token_is_bound_to_exact_payload_and_expires(self):
        prepared = self.store.prepare_action(
            kind="send_sms",
            payload={"number": "+420123456789", "text": "ETA 18:30"},
            expires_at=datetime.now(UTC) + timedelta(minutes=2),
        )

        action = self.store.consume_prepared_action(
            prepared.token,
            {"number": "+420123456789", "text": "ETA 18:30"},
        )

        self.assertEqual(action.id, prepared.id)
        with self.assertRaisesRegex(ValueError, "already used"):
            self.store.consume_prepared_action(prepared.token, action.payload)

    def test_confirmation_token_rejects_changed_payload(self):
        prepared = self.store.prepare_action(
            kind="package_action",
            payload={"recipient": "4603", "text": "IROK2 A"},
            expires_at=datetime.now(UTC) + timedelta(minutes=2),
        )

        with self.assertRaisesRegex(ValueError, "does not match"):
            self.store.consume_prepared_action(
                prepared.token,
                {"recipient": "4603", "text": "NIDEN A"},
            )

    def test_confirmation_token_rejects_naive_current_time(self):
        prepared = self.store.prepare_action(
            kind="send_sms",
            payload={"number": "+420123456789", "text": "ETA 18:30"},
            expires_at=datetime.now(UTC) + timedelta(minutes=2),
        )

        with self.assertRaisesRegex(ValueError, "now must include a timezone"):
            self.store.consume_prepared_action(
                prepared.token,
                prepared.payload,
                now=datetime.now(),
            )


if __name__ == "__main__":
    unittest.main()
