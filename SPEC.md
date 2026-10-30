# Hetzner Cloud Costs - Home Assistant custom integration (MVP)

## Goal

A HACS-installable custom integration that shows what Hetzner Cloud servers
cost, filtered by label. No existing integration does this (checked
2026-10-30): Lunar0sh/hetzner-homeassistant has server metrics only,
Dixet/homeassistant_hetzner covers Storage Box only, HA core has none.

First user: an autoscaled GitLab CI fleet. Servers carry the label
`ci-fleeting=true`, live 1-60 min, and get a new name each time.

## Prior art (the YAML package this replaces)

HA instance: `ssh -i ~/.ssh/id_rsa -o IdentitiesOnly=yes root@homeassistant.internal`,
HA 2026.10.4, config repo `/config` (git, commit after each change).
- `/config/configuration.d/ci_fleet_watchdog.yaml`: REST sensor on
  `GET /v1/servers?label_selector=ci-fleeting%3Dtrue` every 300 s, sums
  `server_type.prices[].price_hourly.gross` where `price.location == server.location.name`
  (`server.datacenter` is null on these servers), Riemann integral,
  utility_meter daily/monthly, linear month forecast.
- `/config/dashboards/ci_fleet.yaml`: dashboard page.
Weakness: integral counts real runtime, Hetzner bills started hours, so the
value is low by up to 1 h per server start; servers shorter than one poll are missed.

## MVP scope

- Config flow: API token (read-only is enough), optional label selector,
  poll interval (default 60 s).
- `DataUpdateCoordinator` polling `GET /v1/servers` (paginate).
- Billing-exact accounting: track each server id with `created` and hourly
  gross price; when a server disappears, book `ceil(lifetime_h) * price_hourly`;
  running servers count as accrued-so-far. Persist ledger in `helpers.storage.Store`
  so restarts lose nothing.
- Entities: current cost rate (EUR/h, measurement), cost total (EUR, monetary,
  `state_class: total` so statistics/energy-style graphs work), active server count.
  Month-to-date and forecast: no custom code. Daily/monthly rollup is a
  `utility_meter` helper added by the user on the cost total entity
  (`state_class: total` already supports it) - document this in the README
  instead of building it. Forecast is dropped (YAGNI): CI-fleeting load
  varies too much day to day for a linear projection to mean anything.
- Tests with `pytest-homeassistant-custom-component`, API mocked from real
  response shapes. HACS metadata (`hacs.json`, `manifest.json`).

Out of scope for the MVP: volumes, primary IPs, snapshots, traffic, Storage Box,
invoices (Hetzner has no billing API).

## Open questions - resolved

1. Billing rule: confirmed. Hetzner bills `min(hours_used * price_hourly.gross,
   price_monthly.gross)` per server, hours rounded up (any partial hour, even
   seconds, counts as a full hour). No per-calendar-month reset within a
   server's life - the cap is against total price_monthly for that server's
   lifetime. Source: docs.hetzner.com/cloud/billing/faq. MVP's
   `ceil(lifetime_h) * price_hourly` is correct for CI-fleeting servers
   (lifetime 1-60 min, nowhere near the monthly cap) - cap logic can be
   skipped as dead code for this use case, but note it as a known gap if the
   integration is ever pointed at long-lived servers.
2. Primary IPv4 is billed separately per hour (~€0.0007-0.001/h, €0.50/mo
   flat, its own `price_monthly`/`price_hourly` fields, not part of
   `server_type.prices[]`). Source: docs.hetzner.com/general/.../ipv4-pricing.
   Moot for MVP: primary IPs are already out of scope (see above) - cost
   entities will undercount actual spend by the IPv4 surcharge. Worth one
   line in the README/dashboard so the number isn't mistaken for the full bill.
3. Confirmed by design, not docs: `GET /v1/servers` only lists servers that
   still exist, so a server deleted between two polls is invisible on the
   next poll - there's no delete timestamp to read. Mitigation already in
   MVP scope stands: on disappearance, book using last-seen time rounded up
   to the next full hour.

## Finish line

- Installs as a custom repository in HACS on the HA instance above.
- With label `ci-fleeting=true` the cost total matches a hand calculation
  over one day of fleet activity (server list from the API, rounded-up hours).
- `pytest` and `ruff` green. Old YAML package can be removed afterwards
  (the user decides).

**Verified 2026-10-30** (docker-compose test instance, real token/label against
the production Hetzner project): config flow accepts the real read-only
token, `GET /v1/servers?label_selector=ci-fleeting%3Dtrue` returns the live
CI worker. `datacenter` is always `null` on these servers (confirmed via a
direct curl against the live API, not just the prior-art YAML's claim) -
`_location_name()` always falls back to `location.name`, so the fallback
path is the only path exercised and `coordinator.py` no longer pretends
otherwise. The ledger produces a plausible
`rate=0.0161840000000000 EUR/h` / `active=1` matching the production YAML
package's own reading for the same server at the same time. OTel JSONL
traces (`<config>/hetzner_cloud_costs_traces.jsonl`) plus
`logger.logs.custom_components.hetzner_cloud_costs: debug` made the
diagnosis (wrong token/selector on first setup attempt) a 2-minute fix
instead of blind guessing. Still unverified: the 1-day hand-calculation
cross-check and the disappearance-booking path (needs a server to actually
be deleted while being watched).

## Canary testing

HA ships a new core version monthly; a breaking change should surface in CI,
not in the user's dashboard. `.github/workflows/canary.yml` runs on the 3rd
of each month: upgrades `homeassistant` and `pytest-homeassistant-custom-component`
to latest, runs `ruff` + `pytest`, and files a `canary-failure`-labeled issue
on failure (deduped, won't spam). Requires the `canary-failure` label to
exist once the repo is public (`gh label create canary-failure`) and Actions
enabled. `workflow_dispatch` lets it be run on demand too.

## Constraints

- Hetzner token from Automic Vault: `av inject +HETZNER_HA_READONLY_TOKEN -- <cmd>`
  (needs human approval each time). Never print token values.
- Python via `uv` + `pyproject.toml`. Creating a public GitHub repo is
  outward-facing: ask first.
