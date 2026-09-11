"""Safe command-line credit query using a carrier profile's USSD code."""

import argparse
import sys
from collections.abc import Callable
from importlib.resources import as_file, files
from typing import TextIO

from .carriers import load_carrier_profile
from .modemmanager import ModemManagerAdapter


def main(
    argv: list[str] | None = None,
    *,
    stdout: TextIO | None = None,
    adapter_factory: Callable[[str], ModemManagerAdapter] = ModemManagerAdapter,
) -> int:
    parser = argparse.ArgumentParser(
        prog="sms-credit", description="Query prepaid credit through carrier USSD."
    )
    parser.add_argument("--modem", required=True, help="ModemManager modem ID")
    parser.add_argument(
        "--dry-run", action="store_true", help="Show the USSD request without sending it"
    )
    arguments = parser.parse_args(argv)
    stdout = stdout or sys.stdout

    profile_resource = files("sms_cli.resources.carriers").joinpath("tmobile-cz-twist.json")
    with as_file(profile_resource) as profile_path:
        profile = load_carrier_profile(profile_path)
    ussd_code = profile.credit_ussd()

    if arguments.dry_run:
        print("DRY RUN: credit query", file=stdout)
        print(f"Modem: {arguments.modem}", file=stdout)
        print(f"USSD: {ussd_code}", file=stdout)
        print("No modem request was sent.", file=stdout)
        return 0

    response = adapter_factory(arguments.modem).initiate_ussd(ussd_code)
    print(response, file=stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
