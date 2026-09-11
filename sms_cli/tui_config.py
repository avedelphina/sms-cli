"""Safe reader for simple contacts/templates in the existing Bash config."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

_ASSIGNMENT = re.compile(
    r"(?:^|\s)(?P<name>SMS_CONTACTS|SMS_TEMPLATES)(?:=\()?\[(?P<key>[^]\s]+)\]\s*=\s*(?P<value>'[^']*'|\"[^\"]*\")"
)


@dataclass(frozen=True)
class ComposeConfig:
    contacts: dict[str, str]
    templates: dict[str, str]


def config_path_from_environment() -> Path:
    return Path(os.environ.get("SMS_CONFIG", Path.home() / ".config/sms-cli/sms.conf"))


def load_compose_config(path: Path) -> ComposeConfig:
    """Parse only literal array assignments; never source user configuration."""
    contacts: dict[str, str] = {}
    templates: dict[str, str] = {}
    if not path.is_file():
        return ComposeConfig(contacts, templates)
    for line in path.read_text(encoding="utf-8").splitlines():
        match = _ASSIGNMENT.search(line)
        if match is None:
            continue
        value = match.group("value")[1:-1]
        target = contacts if match.group("name") == "SMS_CONTACTS" else templates
        target[match.group("key")] = value
    return ComposeConfig(contacts, templates)
