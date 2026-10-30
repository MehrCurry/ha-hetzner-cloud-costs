"""DataUpdateCoordinator for Hetzner Cloud Costs."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from . import otel
from .const import API_BASE_URL, DOMAIN
from .ledger import CostLedger, CostSnapshot

_LOGGER = logging.getLogger(__name__)

STORAGE_VERSION = 1
# ponytail: debounce ledger writes - an immediate async_save on every poll
# wears flash storage (SD cards) for no benefit, a few seconds of lost
# bookkeeping on a crash is an acceptable tradeoff.
SAVE_DELAY = 10


@dataclass
class ServerInfo:
    id: int
    name: str
    status: str
    server_type: str
    location: str
    created: datetime


@dataclass
class HetznerCostsData:
    rate: Decimal
    total_cost: Decimal
    active_count: int
    started_total: int
    servers: list[ServerInfo]


def _price_for_location(server_type: dict, location_name: str) -> Decimal:
    for price in server_type["prices"]:
        if price["location"] == location_name:
            return Decimal(price["price_hourly"]["gross"])
    name = server_type["name"]
    raise UpdateFailed(f"no price for {location_name!r} in server_type {name!r}")


def _location_name(server: dict) -> str:
    # `datacenter` is always null on ci-fleeting servers (confirmed live
    # 2026-10-30); `location` is the only field that ever carries this.
    return server["location"]["name"]


class HetznerCostsCoordinator(DataUpdateCoordinator[HetznerCostsData]):
    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        token: str,
        label_selector: str,
        poll_interval: int,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=poll_interval),
        )
        self._token = token
        self._label_selector = label_selector
        self._session = async_get_clientsession(hass)
        self._store: Store = Store(hass, STORAGE_VERSION, f"{DOMAIN}_{entry.entry_id}")
        self._ledger: CostLedger | None = None

    async def _async_load_ledger(self) -> CostLedger:
        if self._ledger is None:
            stored = await self._store.async_load()
            self._ledger = CostLedger.from_dict(stored) if stored else CostLedger()
        return self._ledger

    async def _fetch_servers(self) -> list[dict]:
        with otel.tracer.start_as_current_span("fetch_servers") as span:
            span_id = otel.span_id_hex(span)
            servers: list[dict] = []
            page = 1
            headers = {"Authorization": f"Bearer {self._token}"}
            while True:
                params = {"page": page, "per_page": 50}
                if self._label_selector:
                    params["label_selector"] = self._label_selector
                async with self._session.get(
                    f"{API_BASE_URL}/servers", headers=headers, params=params
                ) as response:
                    if response.status == 401:
                        raise ConfigEntryAuthFailed("Hetzner API token rejected")
                    if response.status != 200:
                        raise UpdateFailed(f"Hetzner API returned {response.status}")
                    payload = await response.json()
                page_servers = payload["servers"]
                servers.extend(page_servers)
                count = len(page_servers)
                _LOGGER.debug(
                    "fetch_servers span_id=%s page=%d got=%d", span_id, page, count
                )
                next_page = payload["meta"]["pagination"]["next_page"]
                if not next_page:
                    break
                page = next_page
            return servers

    async def _async_update_data(self) -> HetznerCostsData:
        with otel.tracer.start_as_current_span("update_cycle") as span:
            span_id = otel.span_id_hex(span)
            ledger = await self._async_load_ledger()
            raw_servers = await self._fetch_servers()

            current: dict[int, tuple[datetime, Decimal]] = {}
            servers: list[ServerInfo] = []
            for server in raw_servers:
                created = datetime.fromisoformat(server["created"])
                location = _location_name(server)
                price_hourly = _price_for_location(server["server_type"], location)
                current[server["id"]] = (created, price_hourly)
                servers.append(
                    ServerInfo(
                        id=server["id"],
                        name=server["name"],
                        status=server["status"],
                        server_type=server["server_type"]["name"],
                        location=location,
                        created=created,
                    )
                )

            snapshot: CostSnapshot = ledger.update(current, datetime.now(UTC))
            self._store.async_delay_save(ledger.to_dict, SAVE_DELAY)

            _LOGGER.debug(
                "update_cycle span_id=%s active=%d rate=%s total=%s",
                span_id,
                snapshot.active_count,
                snapshot.rate,
                snapshot.total_cost,
            )
            return HetznerCostsData(
                rate=snapshot.rate,
                total_cost=snapshot.total_cost,
                active_count=snapshot.active_count,
                started_total=snapshot.started_total,
                servers=servers,
            )
