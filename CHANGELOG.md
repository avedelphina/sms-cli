# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0] - 2026-09-11

### Added

- Bundled, validated T-Mobile Czech Republic Twist carrier profile, including dated package metadata and command safety gates.
- `sms-credit` command for the profile's `*101#` USSD credit query, with a no-modem-action `--dry-run` preview.
- Narrow ModemManager adapter for validated USSD requests and a shared service-level credit-query method.
- Test dependency extra (`.[test]`) for repeatable fresh-wheel verification.

### Changed

- `sms credit-status --dry-run` is now explicit and safe for both SMS and USSD configuration modes; unknown options fail before contacting ModemManager.
- Packaged and source Bash commands are tested for identical credit-query safeguards.

## [0.1.0] - 2026-09-11

### Added

- Bash command-line wrapper for ModemManager SMS operations: list, read, send, templates, contacts, and prepaid-credit queries.
- Dry-run sending, contact-name resolution, and replies by stored SMS ID.
- Python core with a mockable modem-adapter boundary.
- SQLite persistence for normalised messages and prepared actions.
- One-time, payload-bound, expiring confirmation tokens for future MCP and TUI actions.
- Automated unit tests that run without a modem.

[Unreleased]: https://github.com/avedelphina/sms-cli/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/avedelphina/sms-cli/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/avedelphina/sms-cli/releases/tag/v0.1.0
