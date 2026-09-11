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
