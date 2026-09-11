"""Command line entry point for the local incoming-SMS watcher."""

from __future__ import annotations

import argparse
import asyncio
import os
from pathlib import Path

from .store import MessageStore
from .watcher import DesktopNotifier, IncomingSmsWatcher, ModemManagerDbusWatcher


def main(arguments: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="sms-watch",
        description="Watch ModemManager D-Bus signals and notify for incoming SMS.",
    )
    parser.add_argument("--modem", required=True, help="decimal ModemManager modem ID")
    parser.add_argument(
        "--dry-run", action="store_true", help="validate configuration without subscribing"
    )
    args = parser.parse_args(arguments)
    if not args.modem.isdecimal():
        parser.error("--modem must be a decimal ModemManager modem ID")
    if args.dry_run:
        print(f"DRY RUN: would watch received SMS signals on modem {args.modem}")
        return
    state_home = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state"))
    store = MessageStore(state_home / "sms-cli" / "state.sqlite3")
    watcher = IncomingSmsWatcher(store, DesktopNotifier())
    try:
        asyncio.run(ModemManagerDbusWatcher(args.modem, watcher).run())
    finally:
        store.close()


if __name__ == "__main__":
    main()
