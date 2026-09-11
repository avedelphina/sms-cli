"""Local Textual interface for the shared sms-cli core."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime
from importlib.resources import as_file, files
from typing import Callable

from textual.app import App, ComposeResult
from textual.containers import Horizontal
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    Footer,
    Header,
    Input,
    Select,
    Static,
    TabbedContent,
    TabPane,
)

from .carriers import CarrierProfile, load_carrier_profile
from .mcp_service import McpService
from .service import ModemAdapter, SmsService
from .store import MessageStore
from .tui_config import ComposeConfig, config_path_from_environment, load_compose_config


@dataclass(frozen=True)
class PendingAction:
    token: str
    description: str
    confirm: Callable[[str], dict]


class ConfirmActionScreen(ModalScreen[bool]):
    """A final local confirmation; opening it never contacts the modem."""

    def __init__(self, description: str) -> None:
        super().__init__()
        self.description = description

    def compose(self) -> ComposeResult:
        yield Static(self.description, id="confirmation-details")
        with Horizontal():
            yield Button("Confirm dispatch", id="confirm", variant="error")
            yield Button("Cancel", id="cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "confirm")


class SmsTui(App[None]):
    """A small local TUI; all external effects use McpService prepare/confirm."""

    TITLE = "sms-cli"
    BINDINGS = [("r", "refresh", "Refresh inbox"), ("q", "quit", "Quit")]

    def __init__(
        self,
        modem: ModemAdapter,
        store: MessageStore,
        profile: CarrierProfile | None = None,
        compose_config: ComposeConfig | None = None,
    ) -> None:
        super().__init__()
        self.store = store
        self.service = SmsService(modem, store)
        self.profile = profile or _default_profile()
        self.compose_config = compose_config or ComposeConfig({}, {})
        self.actions = McpService(self.service, store, self.profile)
        self.pending: PendingAction | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with TabbedContent(initial="inbox-tab"):
            with TabPane("Inbox", id="inbox-tab"):
                yield Button("Refresh local inbox", id="refresh")
                yield Static("Loading inbox…", id="inbox")
                yield Static("Select a message to reply using its local ID.", id="message-view")
                yield Input(placeholder="Local message ID to reply to", id="reply-id")
                yield Input(placeholder="Reply text", id="reply-text")
                yield Button("Prepare reply", id="prepare-reply")
            with TabPane("Compose", id="compose-tab"):
                yield Select(
                    [(name, number) for name, number in self.compose_config.contacts.items()],
                    prompt="Choose configured contact (optional)",
                    id="contact",
                )
                yield Select(
                    [(name, text) for name, text in self.compose_config.templates.items()],
                    prompt="Choose configured template (optional)",
                    id="template",
                )
                yield Input(placeholder="Recipient number", id="recipient")
                yield Input(placeholder="Message text", id="message-text")
                yield Static(
                    "Select a literal contact/template from ~/.config/sms-cli/sms.conf, or type values directly. "
                    "The config is never executed by the TUI.",
                    id="compose-help",
                )
                yield Button("Prepare SMS", id="send", variant="warning")
            with TabPane("Carrier", id="carrier-tab"):
                yield Static(self._package_catalogue(), id="packages")
                yield Button("Prepare credit query", id="prepare-credit")
                yield Input(placeholder="Package ID", id="package-id")
                yield Select(
                    [("Status", "status"), ("Deactivate", "deactivate"), ("Activate", "activate")],
                    value="status",
                    id="package-action",
                )
                yield Button("Prepare package action", id="prepare-package-action")
            with TabPane("Modem", id="modem-tab"):
                yield Button("Refresh modem/message status", id="modem-status")
                yield Static("No modem query has been made.", id="modem-info")
        yield Static("Read-only until an action is prepared and confirmed.", id="action-status")
        yield Footer()

    def on_mount(self) -> None:
        self.refresh_inbox()

    def action_refresh(self) -> None:
        self.refresh_inbox()

    def refresh_inbox(self) -> None:
        try:
            messages = self.service.sync_messages()
            lines = [
                f"#{message.id} {message.direction.value:8} {message.state:9} "
                f"{message.timestamp.isoformat() if message.timestamp else '-'} "
                f"{message.number}: {message.text[:120]}"
                for message in messages
            ]
            self.query_one("#inbox", Static).update("\n".join(lines) or "No stored messages.")
            self.query_one("#modem-info", Static).update(f"Synced {len(messages)} message(s) from ModemManager.")
        except Exception as error:
            self._status(f"Refresh failed: {error}")

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "contact" and isinstance(event.value, str):
            self.query_one("#recipient", Input).value = event.value
        elif event.select.id == "template" and isinstance(event.value, str):
            self.query_one("#message-text", Input).value = event.value

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id
        if button_id in {"refresh", "modem-status"}:
            self.refresh_inbox()
        elif button_id == "send":
            self._prepare_send(
                self.query_one("#recipient", Input).value,
                self.query_one("#message-text", Input).value,
                label="SMS",
            )
        elif button_id == "prepare-reply":
            self._prepare_reply()
        elif button_id == "prepare-credit":
            self._prepare_credit()
        elif button_id == "prepare-package-action":
            self._prepare_package_action()

    def _prepare_send(self, recipient: str, text: str, *, label: str) -> None:
        try:
            prepared = self.actions.prepare_send_sms(recipient, text)
        except ValueError as error:
            self._status(f"Cannot prepare {label}: {error}")
            return
        self._show_confirmation(
            PendingAction(
                prepared["token"],
                f"Final confirmation required. Send {label} to {prepared['recipient']}:\n{prepared['text']}\n\nThis dispatch is not delivery confirmation.",
                self.actions.confirm_send_sms,
            )
        )

    def _prepare_reply(self) -> None:
        try:
            message_id = int(self.query_one("#reply-id", Input).value)
            message = self.actions.read_message(message_id)
        except (ValueError, TypeError) as error:
            self._status(f"Cannot prepare reply: {error}")
            return
        self._prepare_send(str(message["number"]), self.query_one("#reply-text", Input).value, label="reply")

    def _prepare_credit(self) -> None:
        command = self.profile.credit_query()
        self._status(
            f"Credit query is carrier-side USSD ({self.profile.credit_ussd()}); billing depends on tariff. "
            "Use sms-credit for the explicit query."
        )
        # This view deliberately does not make USSD requests: it has no confirmation-token type yet.
        del command

    def _prepare_package_action(self) -> None:
        package_id = self.query_one("#package-id", Input).value
        action = self.query_one("#package-action", Select).value
        if not isinstance(action, str):
            self._status("Choose a package action first.")
            return
        try:
            prepared = self.actions.prepare_package_action(package_id, action)
        except ValueError as error:
            self._status(f"Cannot prepare package {action}: {error}")
            return
        price = prepared["price"]
        price_text = json.dumps(price, sort_keys=True) if price is not None else "price unknown"
        self._show_confirmation(
            PendingAction(
                prepared["token"],
                f"Final confirmation required. {action.title()} package {prepared['package_name']} via SMS to "
                f"{prepared['recipient']}:\n{prepared['text']}\nPrice/conditions: {price_text}\n"
                f"Source observed: {prepared['observed_at']}\n\nCarrier outcome is not yet confirmed.",
                self.actions.confirm_package_action,
            )
        )

    def _show_confirmation(self, pending: PendingAction) -> None:
        self.pending = pending
        self._status("Prepared. Review the exact recipient and text in the final confirmation.")
        self.push_screen(ConfirmActionScreen(pending.description), self._confirmed)

    def _confirmed(self, confirmed: bool) -> None:
        pending, self.pending = self.pending, None
        if not confirmed:
            self._status("Action cancelled. Nothing was sent.")
        elif pending is not None:
            try:
                result = pending.confirm(pending.token)
                self._status(f"{result['status']}: {result['warning']}")
                self.refresh_inbox()
            except ValueError as error:
                self._status(f"Confirmation failed: {error}")

    def _package_catalogue(self) -> str:
        return "\n".join(
            f"{package.id}: {package.name} — {package.allowance}, {package.duration}; "
            f"{'stale/activation blocked' if package.is_stale() else 'conditions current'}"
            for package in self.profile.packages
        )

    def _status(self, text: str) -> None:
        self.query_one("#action-status", Static).update(text)


def _default_profile() -> CarrierProfile:
    resource = files("sms_cli.resources.carriers").joinpath("tmobile-cz-twist.json")
    with as_file(resource) as profile_path:
        return load_carrier_profile(profile_path)


def main() -> None:
    import os
    from pathlib import Path

    from .modemmanager import ModemManagerAdapter

    modem_id = os.environ.get("SMS_CLI_MODEM_ID", "0")
    state_home = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state"))
    store = MessageStore(state_home / "sms-cli" / "state.sqlite3")
    SmsTui(
        ModemManagerAdapter(modem_id),
        store,
        compose_config=load_compose_config(config_path_from_environment()),
    ).run()


if __name__ == "__main__":
    main()
