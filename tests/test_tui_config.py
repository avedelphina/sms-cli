import os
import tempfile
import unittest
from pathlib import Path

from sms_cli.tui_config import config_path_from_environment, load_compose_config


class TuiConfigTests(unittest.TestCase):
    def test_loads_literal_bash_contacts_and_templates_without_executing_config(self):
        with tempfile.TemporaryDirectory() as temporary:
            config = Path(temporary) / "sms.conf"
            sentinel = Path(temporary) / "should-not-run"
            config.write_text(
                "declare -A SMS_CONTACTS=([alice]='+420123456789')\n"
                "SMS_TEMPLATES[eta]='ETA {1}'\n"
                f"touch {sentinel}\n",
                encoding="utf-8",
            )

            compose = load_compose_config(config)

            self.assertEqual(compose.contacts, {"alice": "+420123456789"})
            self.assertEqual(compose.templates, {"eta": "ETA {1}"})
            self.assertFalse(sentinel.exists())
    def test_config_path_honours_sms_config_environment(self):
        with tempfile.TemporaryDirectory() as temporary:
            configured = Path(temporary) / "chosen.conf"
            previous = os.environ.get("SMS_CONFIG")
            os.environ["SMS_CONFIG"] = str(configured)
            try:
                self.assertEqual(config_path_from_environment(), configured)
            finally:
                if previous is None:
                    os.environ.pop("SMS_CONFIG", None)
                else:
                    os.environ["SMS_CONFIG"] = previous


if __name__ == "__main__":
    unittest.main()
