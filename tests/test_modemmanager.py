import subprocess
import unittest

from sms_cli.modemmanager import ModemManagerAdapter


class ModemManagerAdapterTests(unittest.TestCase):
    def test_initiate_ussd_uses_mmcli_and_returns_its_response(self):
        calls = []

        def runner(arguments, **kwargs):
            calls.append((arguments, kwargs))
            return subprocess.CompletedProcess(arguments, 0, "Balance: 123 Kč\n", "")

        adapter = ModemManagerAdapter("5", runner=runner)

        response = adapter.initiate_ussd("*101#")

        self.assertEqual(response, "Balance: 123 Kč")
        self.assertEqual(calls[0][0], ["mmcli", "-m", "5", "--3gpp-ussd-initiate=*101#"])
        self.assertTrue(calls[0][1]["check"])
        self.assertTrue(calls[0][1]["text"])

    def test_list_messages_and_send_message_use_mmcli(self):
        calls = []

        def runner(arguments, **kwargs):
            calls.append((arguments, kwargs))
            if "--messaging-list-sms" in arguments:
                return subprocess.CompletedProcess(
                    arguments,
                    0,
                    "  /org/freedesktop/ModemManager1/SMS/42 (received)\n",
                    "",
                )
            if arguments[1] == "-s":
                return subprocess.CompletedProcess(
                    arguments,
                    0,
                    "  -------------------------\n  content: 'Hello'\n  number: '+420123456789'\n  state: 'received'\n",
                    "",
                )
            if "--messaging-create-sms=number='+420123456789',text='ETA 18:30'" in arguments:
                return subprocess.CompletedProcess(
                    arguments, 0, "/org/freedesktop/ModemManager1/SMS/43\n", ""
                )
            return subprocess.CompletedProcess(arguments, 0, "", "")

        adapter = ModemManagerAdapter("5", runner=runner)

        received = adapter.list_messages()
        sent = adapter.send_message("+420123456789", "ETA 18:30")

        self.assertEqual(received[0].text, "Hello")
        self.assertEqual(received[0].number, "+420123456789")
        self.assertEqual(sent.state, "sent")
        self.assertEqual(calls[-1][0], ["mmcli", "-s", "/org/freedesktop/ModemManager1/SMS/43", "--send"])

    def test_read_message_uses_a_validated_sms_path(self):
        calls = []

        def runner(arguments, **kwargs):
            calls.append(arguments)
            return subprocess.CompletedProcess(
                arguments,
                0,
                "  content: 'Hello'\n  number: '+420123456789'\n  state: 'received'\n",
                "",
            )

        message = ModemManagerAdapter("5", runner=runner).read_message(
            "/org/freedesktop/ModemManager1/SMS/42"
        )

        self.assertEqual(message.text, "Hello")
        self.assertEqual(calls, [["mmcli", "-s", "/org/freedesktop/ModemManager1/SMS/42"]])
        with self.assertRaisesRegex(ValueError, "SMS path"):
            ModemManagerAdapter("5", runner=runner).read_message("/tmp/other")

    def test_list_messages_preserves_unknown_state_without_calling_it_sent(self):
        def runner(arguments, **kwargs):
            if "--messaging-list-sms" in arguments:
                return subprocess.CompletedProcess(
                    arguments, 0, "/org/freedesktop/ModemManager1/SMS/42\n", ""
                )
            return subprocess.CompletedProcess(
                arguments,
                0,
                "  content: 'Waiting'\n  number: '+420123456789'\n  state: 'mystery'\n",
                "",
            )

        message = ModemManagerAdapter("5", runner=runner).list_messages()[0]

        self.assertEqual(message.direction.value, "unknown")
        self.assertEqual(message.state, "mystery")

    def test_initiate_ussd_surfaces_mmcli_failures(self):
        def runner(arguments, **kwargs):
            raise subprocess.CalledProcessError(1, arguments, "", "modem unavailable")

        adapter = ModemManagerAdapter("5", runner=runner)

        with self.assertRaises(subprocess.CalledProcessError):
            adapter.initiate_ussd("*101#")

    def test_initiate_ussd_rejects_invalid_modem_ids_and_ussd_codes(self):
        with self.assertRaisesRegex(ValueError, "modem ID"):
            ModemManagerAdapter("--verbose")

        adapter = ModemManagerAdapter("5", runner=lambda *_args, **_kwargs: self.fail("ran"))
        with self.assertRaisesRegex(ValueError, "USSD code"):
            adapter.initiate_ussd("*101#;unexpected")

    def test_initiate_ussd_rejects_an_empty_code_without_running_mmcli(self):
        adapter = ModemManagerAdapter("5", runner=lambda *_args, **_kwargs: self.fail("ran"))

        with self.assertRaisesRegex(ValueError, "cannot be empty"):
            adapter.initiate_ussd("")



if __name__ == "__main__":
    unittest.main()
