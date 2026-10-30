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
  Month-to-date and forecast only if trivial; utility_meter covers them.
- Tests with `pytest-homeassistant-custom-component`, API mocked from real
  response shapes. HACS metadata (`hacs.json`, `manifest.json`).

Out of scope for the MVP: volumes, primary IPs, snapshots, traffic, Storage Box,
invoices (Hetzner has no billing API).

## Open questions - verify before coding

1. Billing rule: per started hour from `created` to deletion, capped at the
   monthly price per calendar month? Confirm in Hetzner docs.
2. Is a primary IPv4 billed separately per hour for these servers? Price source?
3. Does deleting a server between two polls lose its last partial hour?
   (Mitigation: book on disappearance using last-seen time, round up.)

## Finish line

- Installs as a custom repository in HACS on the HA instance above.
- With label `ci-fleeting=true` the cost total matches a hand calculation
  over one day of fleet activity (server list from the API, rounded-up hours).
- `pytest` and `ruff` green. Old YAML package can be removed afterwards
  (the user decides).

## Constraints

- Hetzner token from Automic Vault: `av inject +HETZNER_HA_READONLY_TOKEN -- <cmd>`
  (needs human approval each time). Never print token values.
- Python via `uv` + `pyproject.toml`. Creating a public GitHub repo is
  outward-facing: ask first.
