# sms-cli

Version 0.2.0 — carrier-aware credit querying is now available. See [CHANGELOG.md](CHANGELOG.md) for release notes.

A practical command-line SMS client for [ModemManager](https://modemmanager.org/).

`sms-cli` is a local ModemManager toolkit. The original `sms` command is a small Bash wrapper around `mmcli`; the Python core is growing carrier-aware, testable commands alongside it. It keeps ordinary cellular tasks close to hand: listing and reading stored SMS messages, sending a message, using message templates and named contacts, querying prepaid credit, and (for supported carriers) safely describing prepaid data packages.

The first carrier profile is T-Mobile Czech Republic Twist. See [Carrier profiles](docs/carrier-profiles.md) for dated package metadata and safety rules.

## Development and test setup

The repository's fresh-wheel integration test needs the `build` module. Create the project-local environment and install the test extra:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e '.[test]'
.venv/bin/python -m unittest discover -s tests -v
```

## Requirements

- Linux with ModemManager running
- `mmcli` available on `PATH`
- Bash 4+ (associative arrays are used for contacts and templates)

## Install

```bash
git clone https://github.com/avedelphina/sms-cli.git
cd sms-cli
mkdir -p ~/.local/bin ~/.config/sms-cli
cp sms ~/.local/bin/sms
cp sms.conf.example ~/.config/sms-cli/sms.conf
chmod +x ~/.local/bin/sms
```

Edit `~/.config/sms-cli/sms.conf` to set the modem ID and, optionally, credit-query, contact, and template settings.

To see detected modems:

```bash
mmcli -L
```

If the configured modem ID is unavailable, `sms` automatically uses the first detected modem unless `AUTO_DETECT_MODEM=0` is set.

## Usage

```text
sms list
sms read <id>
sms read-all
sms send <number-or-contact> <message>
sms send --dry-run <number-or-contact> <message>
sms reply <id> <message>
sms reply --dry-run <id> <message>
sms templates
sms contacts
sms send-template <name> [number] [template_args...]
sms credit-status
sms-credit --modem <id> --dry-run
sms-credit --modem <id>
```

Examples:

```bash
sms list
sms read 12
sms send +420123456789 "Running a few minutes late."
sms send --dry-run alice "I land at 18:30."
sms reply 12 "On my way."
sms send-template arrived
sms send-template eta +420123456789 15
sms credit-status
sms-credit --modem 5 --dry-run
sms-credit --modem 5
```

## Configuration

The default configuration path is `~/.config/sms-cli/sms.conf`. Override it for a particular invocation with `SMS_CONFIG=/path/to/file`.

See [`sms.conf.example`](sms.conf.example) for all supported settings. The configuration file is sourced by Bash, so keep it private if it contains information you would not share.

## Credit-query safety

For T-Mobile CZ Twist, `sms-credit --modem <id>` loads the bundled carrier profile and submits its documented `*101#` USSD credit request. It does not send an SMS. Use `--dry-run` first to see the exact modem ID and USSD code; that mode has no modem side effect. A real USSD query contacts the carrier; `sms-cli` does not make a claim about carrier charging, so check your current tariff terms if that matters.

The older `sms credit-status` command follows the local Bash configuration and can be configured to send an SMS. Prefer `sms-credit` for the T-Mobile Twist profile.

## Safety

Sending an SMS and querying credit by SMS both incur the usual carrier-side effects and charges. Check the recipient and text carefully before running `sms send`.

## Status

This is an early, working baseline. It already supports direct sends by number or configured contact name, dry-run previews, and replies by message ID. Planned improvements include a compact inbox view, searching, send confirmations, and shell completion.
