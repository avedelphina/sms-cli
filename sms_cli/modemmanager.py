"""Small, injectable ModemManager CLI adapter."""

import re
import subprocess
from collections.abc import Callable

_MODEM_ID = re.compile(r"^[0-9]+$")
_USSD_CODE = re.compile(r"^[*#0-9]+$")


class ModemManagerAdapter:
    """Run read-only USSD requests through the local mmcli executable."""

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
        result = self._runner(
            ["mmcli", "-m", self.modem_id, f"--3gpp-ussd-initiate={code}"],
            check=True,
            text=True,
            capture_output=True,
        )
        return result.stdout.strip()
