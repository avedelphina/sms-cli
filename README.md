# sms-cli

A practical command-line SMS client for [ModemManager](https://modemmanager.org/).

`sms-cli` is a small Bash wrapper around `mmcli`. It keeps ordinary cellular tasks close to hand: listing and reading stored SMS messages, sending a message, using message templates and named contacts, and querying prepaid credit by USSD or SMS.

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
```

## Configuration

The default configuration path is `~/.config/sms-cli/sms.conf`. Override it for a particular invocation with `SMS_CONFIG=/path/to/file`.

See [`sms.conf.example`](sms.conf.example) for all supported settings. The configuration file is sourced by Bash, so keep it private if it contains information you would not share.

## Safety

Sending an SMS and querying credit by SMS both incur the usual carrier-side effects and charges. Check the recipient and text carefully before running `sms send`.

## Status

This is an early, working baseline. It already supports direct sends by number or configured contact name, dry-run previews, and replies by message ID. Planned improvements include a compact inbox view, searching, send confirmations, and shell completion.
