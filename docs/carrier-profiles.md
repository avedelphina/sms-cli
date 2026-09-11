# Carrier profiles

Carrier profiles are versioned JSON data bundled with `sms-cli`. They describe carrier SMS and USSD commands without putting carrier-specific policy into the program.

## T-Mobile Czech Republic Twist

The bundled `tmobile-cz-twist` profile currently covers:

- credit query: `KREDIT S` to `4603` (alternative USSD: `*101#`)
- Internet na rok: `IROK2 A`, `IROK2 S`, `IROK2 D`, `IROK2 H`
- Neomezený internet v mobilu na den – TWIST: `NIDEN A`, `NIDEN S`, `NIDEN H`

The official command reference is:

<https://www.t-mobile.cz/podpora/prvni-pomoc/nastavte-si-sami/sms-kody-zakaznici-s-predplacenou-kartou-twist>

## Safety and freshness

Carrier offers change. Every carrier command and package in a profile has a source URL and observation date. A package price with a `valid_until` date becomes stale after that date. A client must show this warning and must not describe stale price information as current.

The daily-unlimited package deliberately has no price in the bundled profile: its official SMS-code table confirms the commands but not a stable price. A future purchase preview must refresh or obtain the price before asking for confirmation.

SMS dispatch is not proof of activation. Keep the carrier reply as the authoritative outcome.

## Updating a profile

1. Verify the command and conditions on the carrier’s official page.
2. Update the profile’s `source_url`, `observed_at`, allowance, price, and validity date together.
3. Do not infer unavailable command codes. Omit them and document the uncertainty in `notes`.
4. Add or update tests for every changed command and price-validity rule.
5. Release the changed profile so agents can identify the version of the carrier data they use.
