"""Carrier profile loading and safety metadata."""

import json
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path


_MAX_OBSERVATION_AGE = timedelta(days=90)
_SUPPORTED_ACTIONS = frozenset({"activate", "deactivate", "status", "help"})


@dataclass(frozen=True)
class SmsCommand:
    recipient: str
    text: str
    observed_at: date
    source_url: str

    def is_stale(self, on: date | None = None) -> bool:
        return _observation_is_stale(self.observed_at, on)


@dataclass(frozen=True)
class Package:
    id: str
    name: str
    recipient: str
    commands: dict[str, str]
    allowance: str
    duration: str
    source_url: str
    observed_at: date
    price: dict[str, object] | None
    notes: str | None

    def is_stale(self, on: date | None = None) -> bool:
        on = on or date.today()
        if _observation_is_stale(self.observed_at, on):
            return True
        if self.price is None or "valid_until" not in self.price:
            return True
        return on > date.fromisoformat(str(self.price["valid_until"]))

    def is_safe_to_purchase(self, on: date | None = None) -> bool:
        return "activate" in self.commands and not self.is_stale(on)


@dataclass(frozen=True)
class PackageActionPreview:
    package_id: str
    package_name: str
    action: str
    command: SmsCommand
    source_url: str
    observed_at: date
    price: dict[str, object] | None
    stale: bool
    notes: str | None


@dataclass(frozen=True)
class CarrierProfile:
    id: str
    name: str
    country: str
    documentation_url: str
    commands: dict[str, SmsCommand]
    packages: tuple[Package, ...]

    def credit_query(self) -> SmsCommand:
        return self.commands["credit"]

    def package(self, package_id: str) -> Package:
        for package in self.packages:
            if package.id == package_id:
                return package
        raise ValueError(f"unknown package: {package_id}")

    def package_command(self, package_id: str, action: str) -> SmsCommand:
        package = self.package(package_id)
        if action == "activate" and not package.is_safe_to_purchase():
            raise ValueError(
                f"package {package_id} needs refreshed price and conditions before activation"
            )
        try:
            text = package.commands[action]
        except KeyError as error:
            raise ValueError(f"package {package_id} does not support {action}") from error
        return SmsCommand(package.recipient, text, package.observed_at, package.source_url)

    def prepare_package_action(
        self, package_id: str, action: str, on: date | None = None
    ) -> PackageActionPreview:
        package = self.package(package_id)
        command = self.package_command(package_id, action)
        stale = package.is_stale(on)
        if action == "activate" and stale:
            raise ValueError(
                f"package {package_id} needs refreshed price and conditions before activation"
            )
        return PackageActionPreview(
            package_id=package.id,
            package_name=package.name,
            action=action,
            command=command,
            source_url=package.source_url,
            observed_at=package.observed_at,
            price=package.price,
            stale=stale,
            notes=package.notes,
        )


def load_carrier_profile(path: Path) -> CarrierProfile:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"invalid carrier profile JSON: {error.msg}") from error
    if not isinstance(raw, dict):
        raise ValueError("carrier profile root must be an object")
    schema_version = raw.get("schema_version")
    if isinstance(schema_version, bool) or not isinstance(schema_version, int) or schema_version != 1:
        raise ValueError("unsupported carrier profile schema_version")

    commands_raw = _required_object(raw, "commands")
    credit_raw = _required_object(commands_raw, "credit")
    credit = _load_command(credit_raw, "credit command")

    packages_raw = raw.get("packages")
    if not isinstance(packages_raw, list) or not packages_raw:
        raise ValueError("carrier profile must define a non-empty packages list")
    packages = tuple(_load_package(item) for item in packages_raw)
    if len({package.id for package in packages}) != len(packages):
        raise ValueError("carrier profile has duplicate package IDs")

    return CarrierProfile(
        id=_required_text(raw, "id"),
        name=_required_text(raw, "name"),
        country=_required_text(raw, "country"),
        documentation_url=_required_text(raw, "documentation_url"),
        commands={"credit": credit},
        packages=packages,
    )


def _load_command(raw: dict[str, object], context: str) -> SmsCommand:
    observed_at = _parse_observed_at(_required_text(raw, "observed_at"), context)
    return SmsCommand(
        recipient=_required_text(raw, "recipient"),
        text=_required_text(raw, "text"),
        observed_at=observed_at,
        source_url=_required_text(raw, "source_url"),
    )


def _load_package(raw: object) -> Package:
    if not isinstance(raw, dict):
        raise ValueError("package must be an object")
    commands_raw = _required_object(raw, "commands")
    if not commands_raw:
        raise ValueError("package commands must be a non-empty object")
    commands: dict[str, str] = {}
    for action, text in commands_raw.items():
        if action not in _SUPPORTED_ACTIONS:
            raise ValueError(f"unsupported package action: {action}")
        if not isinstance(text, str) or not text:
            raise ValueError(f"package command {action} must be a non-empty string")
        commands[action] = text
    price = _load_price(raw.get("price"))
    notes = raw.get("notes")
    if notes is not None and not isinstance(notes, str):
        raise ValueError("package notes must be a string or null")
    return Package(
        id=_required_text(raw, "id"),
        name=_required_text(raw, "name"),
        recipient=_required_text(raw, "recipient"),
        commands=commands,
        allowance=_required_text(raw, "allowance"),
        duration=_required_text(raw, "duration"),
        source_url=_required_text(raw, "source_url"),
        observed_at=_parse_observed_at(_required_text(raw, "observed_at"), "package"),
        price=price,
        notes=notes,
    )


def _load_price(raw: object) -> dict[str, object] | None:
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise ValueError("package price must be an object or null")
    _required_text(raw, "currency")
    valid_until = _required_text(raw, "valid_until")
    try:
        date.fromisoformat(valid_until)
    except ValueError as error:
        raise ValueError("package price valid_until must be an ISO date") from error
    for field in ("promotional_amount", "regular_amount"):
        if field in raw and (
            isinstance(raw[field], bool) or not isinstance(raw[field], int) or raw[field] < 0
        ):
            raise ValueError(f"package price {field} must be a non-negative integer")
    if "promotional_amount" not in raw and "regular_amount" not in raw:
        raise ValueError("package price needs promotional_amount or regular_amount")
    return raw


def _parse_observed_at(value: str, context: str) -> date:
    try:
        observed_at = date.fromisoformat(value)
    except ValueError as error:
        raise ValueError(f"{context} observed_at must be an ISO date") from error
    if observed_at > date.today():
        raise ValueError(f"{context} observed_at cannot be in the future")
    return observed_at


def _observation_is_stale(observed_at: date, on: date | None = None) -> bool:
    on = on or date.today()
    return observed_at < on - _MAX_OBSERVATION_AGE


def _required_text(raw: dict[str, object], field: str) -> str:
    value = raw.get(field)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field} must be a non-empty string")
    return value


def _required_object(raw: dict[str, object], field: str) -> dict[str, object]:
    value = raw.get(field)
    if not isinstance(value, dict):
        raise ValueError(f"{field} must be an object")
    return value
