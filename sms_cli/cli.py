"""Installed entry point for the bundled Bash SMS command."""

import os
import subprocess
import sys
from contextlib import ExitStack
from importlib.resources import as_file, files


def main() -> None:
    with ExitStack() as stack:
        script = stack.enter_context(as_file(files("sms_cli.resources").joinpath("sms")))
        environment = os.environ.copy()
        environment["SMS_CLI_BUNDLED"] = "1"
        completed = subprocess.run(["bash", str(script), *sys.argv[1:]], env=environment)
    raise SystemExit(completed.returncode)


if __name__ == "__main__":
    main()
