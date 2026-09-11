import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sms_cli.carriers import load_carrier_profile
from sms_cli.mcp_service import McpService
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
        self.ussd: list[str] = []

    def list_messages(self):
        return self.messages

    def initiate_ussd(self, code):
        self.ussd.append(code)
        return f"USSD response for {code}"

    def send_message(self, number, text):
        self.sent.append((number, text))
        return Message(
            modem_path=f"/org/freedesktop/ModemManager1/SMS/{len(self.sent) + 7}",
            direction=MessageDirection.SENT,
            number=number,
            text=text,
            timestamp=datetime.now(UTC),
            state="sent",
        )


class McpServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        store = MessageStore(Path(self.temp_dir.name) / "state.sqlite3")
        self.adapter = FakeModemAdapter()
        profile_path = (
            Path(__file__).parent.parent
            / "sms_cli/resources/carriers/tmobile-cz-twist.json"
        )
        self.mcp = McpService(
            SmsService(self.adapter, store),
            store,
            load_carrier_profile(profile_path),
            token_lifetime=timedelta(minutes=2),
        )

    def tearDown(self):
        self.mcp.close()
        self.temp_dir.cleanup()

    def test_read_only_tools_do_not_send_an_sms(self):
        messages = self.mcp.list_messages()
        credit = self.mcp.get_credit()
        packages = self.mcp.list_packages()

        self.assertEqual(messages[0]["text"], "Carrier reply")
        self.assertEqual(credit["response"], "USSD response for *101#")
        self.assertEqual(packages[0]["id"], "internet-na-rok")
        self.assertEqual(self.adapter.sent, [])

    def test_prepare_send_is_side_effect_free_and_confirm_dispatches_once(self):
        prepared = self.mcp.prepare_send_sms("+420123456789", "ETA 18:30")

        self.assertEqual(self.adapter.sent, [])
        self.assertEqual(prepared["status"], "prepared")
        sent = self.mcp.confirm_send_sms(prepared["token"])

        self.assertEqual(self.adapter.sent, [("+420123456789", "ETA 18:30")])
        self.assertEqual(sent["status"], "dispatched_pending_confirmation")
        with self.assertRaisesRegex(ValueError, "already used"):
            self.mcp.confirm_send_sms(prepared["token"])

    def test_confirmation_rejects_expired_and_wrong_action_kind(self):
        expired = self.mcp.prepare_send_sms(
            "+420123456789", "ETA 18:30", expires_at=datetime.now(UTC) - timedelta(seconds=1)
        )
        package = self.mcp.prepare_package_action("internet-na-rok", "status")

        with self.assertRaisesRegex(ValueError, "expired"):
            self.mcp.confirm_send_sms(expired["token"])
        with self.assertRaisesRegex(ValueError, "not a send_sms"):
            self.mcp.confirm_send_sms(package["token"])
        dispatched = self.mcp.confirm_package_action(package["token"])
        self.assertEqual(dispatched["status"], "dispatched_pending_confirmation")
        self.assertEqual(self.adapter.sent, [("4603", "IROK2 S")])


if __name__ == "__main__":
    unittest.main()
