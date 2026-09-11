"""Small, injectable ModemManager CLI adapter."""

import re
import subprocess
from collections.abc import Callable
from datetime import UTC, datetime

from .models import Message, MessageDirection

_MODEM_ID = re.compile(r"^[0-9]+$")
_USSD_CODE = re.compile(r"^[*#0-9]+$")
_SMS_PATH = re.compile(r"/org/freedesktop/ModemManager1/SMS/[0-9]+")
_DETAIL_FIELD = re.compile(r"^\s*([a-z-]+):\s*'?(.+?)'?\s*$", re.IGNORECASE)


class ModemManagerAdapter:
    """Run local ModemManager operations through the ``mmcli`` executable."""

    def __init__(
        self,
        modem_id: str,
        runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    ) -> None:
        if not _MODEM_ID.fullmatch(modem_id):
            raise ValueError("modem ID must be a decimal ModemManager ID")
        self.modem_id = modem_id
        self._runner = runner

    def initiate_ussd(self, code: str) -> str:
        if not code:
            raise ValueError("USSD code cannot be empty")
        if not _USSD_CODE.fullmatch(code):
            raise ValueError("USSD code must contain only digits, asterisks, and hashes")
        return self._run(["mmcli", "-m", self.modem_id, f"--3gpp-ussd-initiate={code}"]).strip()

    def list_messages(self) -> list[Message]:
        listing = self._run(["mmcli", "-m", self.modem_id, "--messaging-list-sms"])
        messages: list[Message] = []
        for path in _SMS_PATH.findall(listing):
            details = self._run(["mmcli", "-s", path])
            messages.append(_parse_message(path, details))
        return messages

    def read_message(self, sms_path: str) -> Message:
        if not _SMS_PATH.fullmatch(sms_path):
            raise ValueError("SMS path must be a ModemManager SMS object path")
        return _parse_message(sms_path, self._run(["mmcli", "-s", sms_path]))

    def send_message(self, number: str, text: str) -> Message:
        if not isinstance(number, str) or not number or "\n" in number or "\r" in number:
            raise ValueError("recipient number must be a non-empty single-line string")
        if not isinstance(text, str) or not text or "\n" in text or "\r" in text:
            raise ValueError("message text must be a non-empty single-line string")
        created = self._run(
            [
                "mmcli",
                "-m",
                self.modem_id,
                f"--messaging-create-sms=number='{_escape_mmcli(number)}',text='{_escape_mmcli(text)}'",
            ]
        )
        match = _SMS_PATH.search(created)
        if match is None:
            raise RuntimeError("could not determine SMS path from mmcli output")
        path = match.group(0)
        self._run(["mmcli", "-s", path, "--send"])
        return Message(
            modem_path=path,
            direction=MessageDirection.SENT,
            number=number,
            text=text,
            timestamp=datetime.now(UTC),
            state="sent",
        )

    def _run(self, arguments: list[str]) -> str:
        result = self._runner(arguments, check=True, text=True, capture_output=True)
        return result.stdout


def _escape_mmcli(value: str) -> str:
    return value.replace("'", "\\'")


def _parse_message(path: str, details: str) -> Message:
    fields: dict[str, str] = {}
    for line in details.splitlines():
        match = _DETAIL_FIELD.match(line)
        if match:
            fields[match.group(1).lower()] = match.group(2)
    state = fields.get("state", "unknown")
    if state == "received":
        direction = MessageDirection.RECEIVED
    elif state in {"sent", "sending"}:
        direction = MessageDirection.SENT
    else:
        direction = MessageDirection.UNKNOWN
    return Message(
        modem_path=path,
        direction=direction,
        number=fields.get("number", ""),
        text=fields.get("content", ""),
        timestamp=None,
        state=state,
    )
