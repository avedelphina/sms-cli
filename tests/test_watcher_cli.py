import unittest
from unittest.mock import patch

from sms_cli.watcher_cli import main


class WatcherCliTests(unittest.TestCase):
    def test_requires_explicit_modem_id(self):
        with self.assertRaisesRegex(SystemExit, "2"):
            main([])

    def test_constructs_dbus_watcher_without_starting_it_when_dry_run(self):
        with patch("sms_cli.watcher_cli.asyncio.run") as run:
            main(["--modem", "6", "--dry-run"])

        run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
