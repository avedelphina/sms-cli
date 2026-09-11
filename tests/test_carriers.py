import json
import tempfile
import unittest
from datetime import date
from importlib.resources import as_file, files
from pathlib import Path

from sms_cli.carriers import load_carrier_profile


class CarrierProfileTests(unittest.TestCase):
    def tmobile_profile_path(self):
        return as_file(files("sms_cli.resources.carriers").joinpath("tmobile-cz-twist.json"))

    def test_tmobile_twist_renders_verified_sms_commands(self):
        with self.tmobile_profile_path() as path:
            profile = load_carrier_profile(path)

        self.assertEqual(profile.credit_query().recipient, "4603")
        self.assertEqual(profile.credit_query().text, "KREDIT S")
        self.assertEqual(profile.credit_ussd(), "*101#")
        self.assertEqual(profile.package_command("internet-na-rok", "activate").text, "IROK2 A")
        self.assertEqual(profile.package_command("internet-na-rok", "status").text, "IROK2 S")
        with self.assertRaisesRegex(ValueError, "refreshed"):
            profile.package_command("neomezeny-internet-na-den", "activate")
        self.assertEqual(profile.package_command("neomezeny-internet-na-den", "status").text, "NIDEN S")

    def test_time_sensitive_package_is_stale_after_its_valid_until_date(self):
        with self.tmobile_profile_path() as path:
            profile = load_carrier_profile(path)

        package = profile.package("internet-na-rok")
        self.assertFalse(package.is_stale(on=date(2026, 9, 30)))
        self.assertTrue(package.is_stale(on=date(2026, 10, 1)) )

    def test_package_without_price_is_not_safe_to_purchase(self):
        with self.tmobile_profile_path() as path:
            profile = load_carrier_profile(path)

        self.assertFalse(profile.package("neomezeny-internet-na-den").is_safe_to_purchase())
        with self.assertRaisesRegex(ValueError, "refreshed price"):
            profile.prepare_package_action("neomezeny-internet-na-den", "activate")

    def test_activation_command_does_not_accept_a_caller_supplied_historical_date(self):
        with self.tmobile_profile_path() as path:
            profile = load_carrier_profile(path)

        with self.assertRaises(TypeError):
            profile.package_command("internet-na-rok", "activate", on=date(2026, 9, 1))

    def test_package_preview_contains_freshness_and_source_metadata(self):
        with self.tmobile_profile_path() as path:
            profile = load_carrier_profile(path)

        preview = profile.prepare_package_action("internet-na-rok", "activate", on=date(2026, 9, 11))

        self.assertEqual(preview.command.text, "IROK2 A")
        self.assertEqual(preview.source_url, "https://eshop.t-mobile.cz/predplacene-karty")
        self.assertFalse(preview.stale)

    def test_profile_rejects_package_without_source_metadata(self):
        profile = self.valid_profile()
        del profile["packages"][0]["source_url"]
        self.assert_invalid(profile, "source_url")

    def test_profile_rejects_malformed_price_and_future_observation(self):
        malformed_price = self.valid_profile()
        malformed_price["packages"][0]["price"] = "699"
        self.assert_invalid(malformed_price, "price")

        boolean_price = self.valid_profile()
        boolean_price["packages"][0]["price"]["regular_amount"] = True
        self.assert_invalid(boolean_price, "regular_amount")

        future_observation = self.valid_profile()
        future_observation["packages"][0]["observed_at"] = "2999-01-01"
        self.assert_invalid(future_observation, "future")

    def test_profile_rejects_boolean_schema_version(self):
        profile = self.valid_profile()
        profile["schema_version"] = True
        self.assert_invalid(profile, "schema_version")

    def valid_profile(self):
        return {
            "schema_version": 1,
            "id": "example",
            "name": "Example",
            "country": "CZ",
            "documentation_url": "https://example.test/docs",
            "commands": {
                "credit": {
                    "recipient": "123",
                    "text": "CREDIT",
                    "source_url": "https://example.test/credit",
                    "observed_at": "2026-09-11",
                }
            },
            "packages": [
                {
                    "id": "data",
                    "name": "Data",
                    "recipient": "123",
                    "commands": {"activate": "DATA A"},
                    "allowance": "1 GB",
                    "duration": "30 days",
                    "source_url": "https://example.test/data",
                    "observed_at": "2026-09-11",
                    "price": {"currency": "CZK", "regular_amount": 99, "valid_until": "2026-12-31"},
                }
            ],
        }

    def assert_invalid(self, profile, message):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "invalid.json"
            path.write_text(json.dumps(profile), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, message):
                load_carrier_profile(path)


if __name__ == "__main__":
    unittest.main()
