# Hetzner Cloud Costs

[![test](https://github.com/MehrCurry/ha-hetzner-cloud-costs/actions/workflows/test.yml/badge.svg)](https://github.com/MehrCurry/ha-hetzner-cloud-costs/actions/workflows/test.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A [Home Assistant](https://www.home-assistant.io/) custom integration that
tracks what your [Hetzner Cloud](https://www.hetzner.com/cloud/) servers
cost, filtered by label. Built for ephemeral fleets - e.g. autoscaled GitLab
CI runners that live a few minutes and get a new name each time - where
Hetzner's own hourly billing is easy to approximate wrong with a naive
integral.

## Why not just read Hetzner's own cost report?

Hetzner has no billing API. The only way to know what a set of servers cost
is to track their lifetime yourself and apply Hetzner's own billing rule:
full hours, rounded up, from creation to deletion. That's what this
integration does.

## Features

- Polls `GET /v1/servers`, optionally filtered by `label_selector`.
- Billing-exact cost ledger: tracks each server's creation time and hourly
  price, books `ceil(lifetime_hours) * price_hourly` when a server
  disappears. Survives Home Assistant restarts (persisted via
  `helpers.storage.Store`).
- One device per config entry, with:
  - **Cost rate** (EUR/h) and **cost total** (EUR, `state_class: total` -
    add a `utility_meter` helper for daily/monthly rollups).
  - **Active server count**, **servers started** (lifetime counter).
  - **Oldest running server since** (catches stuck/leaked servers).
  - Per-status count sensors (`running` enabled by default, others
    available but disabled to avoid entity clutter).
  - A **lifecycle event** entity (`server_started` / `server_removed`) for
    automations and the logbook.
- Diagnostics download with the full raw server list, for support requests.

## Installation

### HACS (custom repository)

1. HACS -> the three-dot menu -> **Custom repositories**.
2. Add this repository's URL, category **Integration**.
3. Install **Hetzner Cloud Costs**, restart Home Assistant.

### Manual

Copy `custom_components/hetzner_cloud_costs` into your Home Assistant
`config/custom_components/` directory and restart.

## Configuration

Settings -> Devices & Services -> Add Integration -> **Hetzner Cloud Costs**.

| Field | Required | Description |
|---|---|---|
| API token | yes | A Hetzner Cloud **read-only** project token is enough. |
| Label selector | no | e.g. `ci-fleeting=true`. Empty tracks every server in the project. |
| Poll interval | no | Seconds between polls, default 60. |

## Known limitations

- Primary IPv4 addresses are billed separately (~€0.50/mo) and are **not**
  included in the cost total - it undercounts by that amount per server.
- Volumes, snapshots, traffic, load balancers, and Storage Box are out of
  scope.
- A server's monthly price cap (`price_monthly`) is not enforced - fine for
  short-lived servers, a gap for anything running close to a full month.

## Development

```sh
uv sync
uv run ruff check .
uv run pytest
```

A `docker-compose.yml` is included to run a disposable Home Assistant
instance with this integration live-mounted:

```sh
docker compose up -d
docker compose restart homeassistant  # after editing custom_components/
```

## Support

If this saves you from guessing your CI fleet's Hetzner bill, consider
[sponsoring on GitHub](https://github.com/sponsors/MehrCurry).

## License

[MIT](LICENSE)
