import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

from textual.widgets import TabbedContent

from sms_cli.models import Message, MessageDirection
from sms_cli.store import MessageStore
from sms_cli.tui import SmsTui


class FakeModem:
    def __init__(self):
        self.messages = [
            Message(
                modem_path="/org/freedesktop/ModemManager1/SMS/9",
                direction=MessageDirection.RECEIVED,
                number="+420123456789",
                text="Carrier reply",
                timestamp=datetime(2026, 9, 11, 16, 0, tzinfo=UTC),
                state="received",
            )
        ]
        self.sent = []

    def list_messages(self):
        return self.messages

    def initiate_ussd(self, code):
        return f"Credit response for {code}"

    def send_message(self, number, text):
        self.sent.append((number, text))
        return Message(
            modem_path="/org/freedesktop/ModemManager1/SMS/10",
            direction=MessageDirection.SENT,
            number=number,
            text=text,
            timestamp=None,
            state="sent",
        )


class SmsTuiTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store = MessageStore(Path(self.temp_dir.name) / "state.sqlite3")
        self.modem = FakeModem()
        self.app = SmsTui(self.modem, self.store)

    async def asyncTearDown(self):
        self.store.close()
        self.temp_dir.cleanup()

    async def test_inbox_refresh_shows_fixture_message_without_sending(self):
        async with self.app.run_test() as pilot:
            await pilot.pause()
            self.assertIn("Carrier reply", str(self.app.query_one("#inbox").renderable))
            self.assertEqual(self.modem.sent, [])

    async def test_compose_requires_final_confirmation_before_dispatch(self):
        async with self.app.run_test() as pilot:
            self.app.query_one(TabbedContent).active = "compose-tab"
            self.app._prepare_send("+420123456789", "Hello", label="SMS")
            await pilot.pause()
            self.assertEqual(self.modem.sent, [])
            self.assertIsNotNone(self.app.pending)
            self.assertIn("+420123456789", str(self.app.screen.query_one("#confirmation-details").renderable))
    async def test_contact_and_template_selection_fill_compose_fields(self):
        from sms_cli.tui_config import ComposeConfig

        self.app = SmsTui(
            self.modem,
            self.store,
            compose_config=ComposeConfig({"alice": "+420123456789"}, {"eta": "ETA 15"}),
        )
        async with self.app.run_test() as pilot:
            self.app.query_one(TabbedContent).active = "compose-tab"
            await pilot.pause()
            await pilot.press("tab")
            self.app.query_one("#contact").value = "+420123456789"
            self.app.query_one("#template").value = "ETA 15"
            await pilot.pause()

            self.assertEqual(self.app.query_one("#recipient").value, "+420123456789")
            self.assertEqual(self.app.query_one("#message-text").value, "ETA 15")

    async def test_reply_uses_received_sender_and_requires_confirmation(self):
        async with self.app.run_test() as pilot:
            self.app.query_one("#reply-id").value = "1"
            self.app.query_one("#reply-text").value = "Acknowledged"
            self.app._prepare_reply()
            await pilot.pause()

            self.assertEqual(self.modem.sent, [])
            details = str(self.app.screen.query_one("#confirmation-details").renderable)
            self.assertIn("+420123456789", details)
            self.assertIn("Acknowledged", details)

    async def test_stale_package_activation_is_rejected_without_confirmation(self):
        async with self.app.run_test() as pilot:
            self.app.query_one(TabbedContent).active = "carrier-tab"
            self.app.query_one("#package-id").value = "neomezeny-internet-na-den"
            self.app.query_one("#package-action").value = "activate"
            self.app._prepare_package_action()
            await pilot.pause()

            self.assertEqual(self.modem.sent, [])
            self.assertEqual(self.app.screen.id, "_default")
            self.assertIn("needs refreshed", str(self.app.query_one("#action-status").renderable))

    async def test_package_status_requires_confirmation_with_exact_command(self):
        async with self.app.run_test() as pilot:
            self.app.query_one(TabbedContent).active = "carrier-tab"
            self.app.query_one("#package-id").value = "internet-na-rok"
            self.app._prepare_package_action()
            await pilot.pause()

            self.assertEqual(self.modem.sent, [])
            details = str(self.app.screen.query_one("#confirmation-details").renderable)
            self.assertIn("IROK2 S", details)
            self.assertIn("4603", details)
            self.assertIn("not yet confirmed", details)

    async def test_confirming_prepared_sms_dispatches_once_with_qualified_status(self):
        async with self.app.run_test() as pilot:
            self.app._prepare_send("+420123456789", "Hello", label="SMS")
            await pilot.pause()
            await pilot.click("#confirm")
            await pilot.pause()

            self.assertEqual(self.modem.sent, [("+420123456789", "Hello")])
            self.assertIn("dispatched_pending_confirmation", str(self.app.query_one("#action-status").renderable))


if __name__ == "__main__":
    unittest.main()
