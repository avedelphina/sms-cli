import io
import unittest

from sms_cli.credit_cli import main


class CreditCliTests(unittest.TestCase):
    def test_dry_run_prints_the_exact_ussd_query_without_creating_an_adapter(self):
        output = io.StringIO()

        exit_code = main(
            ["--modem", "5", "--dry-run"],
            stdout=output,
            adapter_factory=lambda _modem: self.fail("adapter created"),
        )

        self.assertEqual(exit_code, 0)
        rendered = output.getvalue()
        self.assertIn("DRY RUN", rendered)
        self.assertIn("Modem: 5", rendered)
        self.assertIn("USSD: *101#", rendered)
        self.assertIn("No modem request was sent.", rendered)

    def test_query_prints_modem_response(self):
        output = io.StringIO()

        class Adapter:
            def initiate_ussd(self, code):
                self.code = code
                return "Balance: 123 Kč"

        adapter = Adapter()
        exit_code = main(
            ["--modem", "5"], stdout=output, adapter_factory=lambda _modem: adapter
        )

        self.assertEqual(exit_code, 0)
        self.assertEqual(adapter.code, "*101#")
        self.assertEqual(output.getvalue(), "Balance: 123 Kč\n")


if __name__ == "__main__":
    unittest.main()
