import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]


class InstalledCliTests(unittest.TestCase):
    def test_built_wheel_installs_sms_command(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            dist = temp / "dist"
            environment = temp / "environment"

            subprocess.run(
                [sys.executable, "-m", "build", "--wheel", "--outdir", str(dist)],
                cwd=PROJECT,
                check=True,
            )
            wheel = next(dist.glob("sms_cli-*.whl"))
            subprocess.run([sys.executable, "-m", "venv", str(environment)], check=True)
            subprocess.run(
                [
                    environment / "bin" / "python",
                    "-m",
                    "pip",
                    "install",
                    "--no-index",
                    "--no-deps",
                    str(wheel),
                ],
                check=True,
            )
            result = subprocess.run(
                [environment / "bin" / "sms", "--help"],
                cwd=temp,
                text=True,
                capture_output=True,
                check=False,
            )
            profile = subprocess.run(
                [
                    environment / "bin" / "python",
                    "-c",
                    "from importlib.resources import files; "
                    "print(files('sms_cli.resources.carriers').joinpath('tmobile-cz-twist.json').read_text())",
                ],
                cwd=temp,
                text=True,
                capture_output=True,
                check=False,
            )
            mcp_entry_point = subprocess.run(
                [
                    environment / "bin" / "python",
                    "-c",
                    "from importlib.metadata import entry_points; "
                    "print(any(entry.name == 'smscp' and entry.value == 'sms_cli.mcp_server:main' "
                    "for entry in entry_points(group='console_scripts')))",
                ],
                cwd=temp,
                text=True,
                capture_output=True,
                check=False,
            )
            watcher_entry_point = subprocess.run(
                [
                    environment / "bin" / "sms-watch",
                    "--modem",
                    "5",
                    "--dry-run",
                ],
                cwd=temp,
                text=True,
                capture_output=True,
                check=False,
            )
            fake_bin = temp / "fake-bin"
            fake_bin.mkdir()
            mmcli_log = temp / "mmcli.log"
            fake_mmcli = fake_bin / "mmcli"
            fake_mmcli.write_text(
                "#!/bin/sh\nprintf '%s\\n' \"$@\" > \"$MMCLI_LOG\"\nprintf 'Balance: 123 Kč\\n'\n",
                encoding="utf-8",
            )
            fake_mmcli.chmod(0o755)
            environment_vars = os.environ | {
                "PATH": f"{fake_bin}:{os.environ['PATH']}",
                "MMCLI_LOG": str(mmcli_log),
            }
            live_credit = subprocess.run(
                [environment / "bin" / "sms-credit", "--modem", "5"],
                cwd=temp,
                env=environment_vars,
                text=True,
                capture_output=True,
                check=False,
            )
            fake_mmcli_output = mmcli_log.read_text(encoding="utf-8")
            mmcli_log.unlink()
            config = temp / "sms.conf"
            config.write_text("CREDIT_METHOD=ussd\nCREDIT_USSD='*101#'\n", encoding="utf-8")
            dry_run = subprocess.run(
                [environment / "bin" / "sms", "credit-status", "--dry-run"],
                cwd=temp,
                env=environment_vars | {"SMS_CONFIG": str(config)},
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertFalse(mmcli_log.exists(), "installed dry-run must not invoke mmcli")
            invalid_option = subprocess.run(
                [environment / "bin" / "sms", "credit-status", "--unexpected"],
                cwd=temp,
                env=environment_vars | {"SMS_CONFIG": str(config)},
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertFalse(mmcli_log.exists(), "invalid installed command must not invoke mmcli")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("sms send", result.stdout)
        self.assertIn("Config file:", result.stdout)
        self.assertEqual(profile.returncode, 0, profile.stderr)
        self.assertIn('"id": "tmobile-cz-twist"', profile.stdout)
        self.assertEqual(mcp_entry_point.returncode, 0, mcp_entry_point.stderr)
        self.assertEqual(mcp_entry_point.stdout.strip(), "True")
        self.assertEqual(watcher_entry_point.returncode, 0, watcher_entry_point.stderr)
        self.assertIn("DRY RUN", watcher_entry_point.stdout)
        self.assertEqual(dry_run.returncode, 0, dry_run.stderr)
        self.assertIn("DRY RUN", dry_run.stdout)
        self.assertEqual(invalid_option.returncode, 1)
        self.assertIn("Usage: sms credit-status", invalid_option.stderr)
        self.assertEqual(live_credit.stdout, "Balance: 123 Kč\n")
        self.assertEqual(fake_mmcli_output, "-m\n5\n--3gpp-ussd-initiate=*101#\n")


if __name__ == "__main__":
    unittest.main()
