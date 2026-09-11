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

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("sms send", result.stdout)
        self.assertIn("Config file:", result.stdout)
        self.assertEqual(profile.returncode, 0, profile.stderr)
        self.assertIn('"id": "tmobile-cz-twist"', profile.stdout)


if __name__ == "__main__":
    unittest.main()
