#!/usr/bin/env python3
"""Black-box tests for the sms command-line interface."""

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
SMS = PROJECT / "sms"


class SmsCliTests(unittest.TestCase):
    def run_sms(self, *args, config: str, mmcli_output: str = ""):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            log = temp / "mmcli.log"
            fake_mmcli = temp / "mmcli"
            fake_mmcli.write_text(
                "#!/usr/bin/env bash\n"
                "printf '%s\\n' \"$*\" >> \"$MMCLI_LOG\"\n"
                "printf '%s' \"${MMCLI_OUTPUT:-}\"\n"
                "exit 0\n",
                encoding="utf-8",
            )
            fake_mmcli.chmod(0o755)
            environment = os.environ | {
                "PATH": f"{temp}:{os.environ['PATH']}",
                "SMS_CONFIG": config,
                "MMCLI_LOG": str(log),
                "MMCLI_OUTPUT": mmcli_output,
            }
            result = subprocess.run(
                [str(SMS), *args], text=True, capture_output=True, env=environment, check=False
            )
            calls = log.read_text(encoding="utf-8") if log.exists() else ""
            return result, calls

    def test_send_dry_run_resolves_a_named_contact_without_calling_modem(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config = Path(temp_dir) / "sms.conf"
            config.write_text(
                'declare -A SMS_CONTACTS=([alice]="+42015550123")\n', encoding="utf-8"
            )
            result, mmcli_calls = self.run_sms(
                "send", "--dry-run", "alice", "Hello from the train", config=str(config)
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("DRY RUN", result.stdout)
        self.assertIn("+42015550123", result.stdout)
        self.assertIn("Hello from the train", result.stdout)
        self.assertEqual(mmcli_calls, "")

    def test_credit_status_dry_run_cannot_be_overridden_by_sms_config(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config = Path(temp_dir) / "sms.conf"
            config.write_text(
                "CREDIT_METHOD=sms\nCREDIT_SMS_NUMBER=4603\nCREDIT_SMS_TEXT='KREDIT S'\n",
                encoding="utf-8",
            )
            result, mmcli_calls = self.run_sms("credit-status", "--dry-run", config=str(config))

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("DRY RUN", result.stdout)
        self.assertIn("4603", result.stdout)
        self.assertIn("KREDIT S", result.stdout)
        self.assertEqual(mmcli_calls, "")

    def test_credit_status_dry_run_for_ussd_does_not_call_modem(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config = Path(temp_dir) / "sms.conf"
            config.write_text("CREDIT_METHOD=ussd\nCREDIT_USSD='*101#'\n", encoding="utf-8")
            result, mmcli_calls = self.run_sms("credit-status", "--dry-run", config=str(config))

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("DRY RUN", result.stdout)
        self.assertIn("*101#", result.stdout)
        self.assertEqual(mmcli_calls, "")

    def test_credit_status_rejects_unknown_options_without_calling_modem(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config = Path(temp_dir) / "sms.conf"
            config.write_text("CREDIT_METHOD=ussd\n", encoding="utf-8")
            result, mmcli_calls = self.run_sms("credit-status", "--unexpected", config=str(config))

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Usage: sms credit-status", result.stderr)
        self.assertEqual(mmcli_calls, "")

    def test_reply_dry_run_uses_sender_number_from_an_sms(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config = Path(temp_dir) / "sms.conf"
            config.write_text("MODEM_ID=0\n", encoding="utf-8")
            result, mmcli_calls = self.run_sms(
                "reply",
                "--dry-run",
                "42",
                "On my way",
                config=str(config),
                mmcli_output="number: +42015551234\n",
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("+42015551234", result.stdout)
        self.assertIn("On my way", result.stdout)
        self.assertIn("-s /org/freedesktop/ModemManager1/SMS/42", mmcli_calls)
        self.assertNotIn("--send", mmcli_calls)


if __name__ == "__main__":
    unittest.main()
