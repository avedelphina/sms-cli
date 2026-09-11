"""Local stdio MCP server for sms-cli.

The server has no Hermes dependency and emits protocol traffic only on stdout.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from .carriers import load_carrier_profile
from .mcp_service import McpService
from .modemmanager import ModemManagerAdapter
from .service import SmsService
from .store import MessageStore


def create_server(service: McpService, modem_id: str) -> FastMCP:
    server = FastMCP(
        "sms-cli",
        instructions=(
            "Local cellular management. Prepare operations never send an SMS. "
            "Confirmation tokens expire quickly and cause one dispatch only; a "
            "dispatch is not carrier or recipient confirmation."
        ),
    )

    @server.tool(description="Report the configured local ModemManager modem. Read-only.")
    def get_modem_status() -> dict[str, str]:
        return {"modem_id": modem_id, "transport": "local ModemManager via mmcli"}

    @server.tool(description="Synchronize and return stored modem SMS messages. Read-only.")
    def list_messages() -> list[dict[str, Any]]:
        return service.list_messages()

    @server.tool(description="Synchronize and return one SMS by its local message ID. Read-only.")
    def read_message(message_id: int) -> dict[str, Any]:
        return service.read_message(message_id)

    @server.tool(
        description=(
            "Make the carrier profile's USSD credit query. This does not send SMS, "
            "but it contacts the carrier and tariff charging is carrier-dependent."
        )
    )
    def get_credit() -> dict[str, str]:
        return service.get_credit()

    @server.tool(description="List carrier package metadata and freshness. Read-only.")
    def list_packages() -> list[dict[str, Any]]:
        return service.list_packages()

    @server.tool(
        description=(
            "Describe package-status safety. A real status request is an SMS and "
            "must use prepare_package_action then confirm_package_action."
        )
    )
    def get_package_status(package_id: str) -> dict[str, Any]:
        return service.get_package_status(package_id)

    @server.tool(
        description=(
            "Prepare an SMS without sending it. Returns exact recipient/text and a "
            "short-lived local token required by confirm_send_sms."
        )
    )
    def prepare_send_sms(recipient: str, text: str) -> dict[str, Any]:
        return service.prepare_send_sms(recipient, text)

    @server.tool(
        description=(
            "Dispatch exactly the SMS bound to a prepared token. This is carrier-side "
            "activity and returns dispatched_pending_confirmation, not delivery confirmation."
        )
    )
    def confirm_send_sms(token: str) -> dict[str, Any]:
        return service.confirm_send_sms(token)

    @server.tool(
        description=(
            "Prepare a carrier package SMS without sending it. Returns source, date, "
            "price metadata and a token for confirm_package_action."
        )
    )
    def prepare_package_action(package_id: str, action: str) -> dict[str, Any]:
        return service.prepare_package_action(package_id, action)

    @server.tool(
        description=(
            "Dispatch exactly the package SMS bound to a prepared token. It does not "
            "confirm activation; wait for a recorded carrier response."
        )
    )
    def confirm_package_action(token: str) -> dict[str, Any]:
        return service.confirm_package_action(token)

    return server


def build_default_server() -> FastMCP:
    modem_id = os.environ.get("SMS_CLI_MODEM_ID", "0")
    state_home = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state"))
    store = MessageStore(state_home / "sms-cli" / "state.sqlite3")
    profile_path = Path(__file__).parent / "resources/carriers/tmobile-cz-twist.json"
    adapter = ModemManagerAdapter(modem_id)
    service = McpService(SmsService(adapter, store), store, load_carrier_profile(profile_path))
    return create_server(service, modem_id)


def main() -> None:
    build_default_server().run(transport="stdio")


if __name__ == "__main__":
    main()
