import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

from sms_cli.models import Message, MessageDirection
from sms_cli.service import SmsService
from sms_cli.store import MessageStore


class FakeModemAdapter:
    def __init__(self):
        self.messages = [
            Message(
                modem_path="/org/freedesktop/ModemManager1/SMS/7",
                direction=MessageDirection.RECEIVED,
                number="+420123456789",
                text="Carrier reply",
                timestamp=datetime(2026, 9, 11, 16, 0, tzinfo=UTC),
                state="received",
            )
        ]
        self.sent: list[tuple[str, str]] = []

    def list_messages(self):
        return self.messages

    def initiate_ussd(self, code):
        return f"USSD response for {code}"

    def send_message(self, number, text):
        self.sent.append((number, text))
        return Message(
            modem_path="/org/freedesktop/ModemManager1/SMS/8",
            direction=MessageDirection.SENT,
            number=number,
            text=text,
            timestamp=None,
            state="stored",
        )


class SmsServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store = MessageStore(Path(self.temp_dir.name) / "state.sqlite3")
        self.adapter = FakeModemAdapter()
        self.service = SmsService(self.adapter, self.store)

    def tearDown(self):
        self.store.close()
        self.temp_dir.cleanup()

    def test_sync_stores_messages_from_modem_adapter(self):
        messages = self.service.sync_messages()

        self.assertEqual(messages[0].text, "Carrier reply")
        self.assertEqual(self.store.list_messages(), messages)

    def test_credit_query_uses_ussd_without_sending_an_sms(self):
        result = self.service.query_credit("*101#")

        self.assertEqual(result, "USSD response for *101#")
        self.assertEqual(self.adapter.sent, [])

    def test_send_records_the_message_returned_by_adapter(self):
        sent = self.service.send_message("+420987654321", "ETA 18:30")

        self.assertEqual(self.adapter.sent, [("+420987654321", "ETA 18:30")])
        self.assertEqual(self.store.list_messages(), [sent])


if __name__ == "__main__":
    unittest.main()
