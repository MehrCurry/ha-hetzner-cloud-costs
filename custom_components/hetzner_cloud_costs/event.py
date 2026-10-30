"""Server lifecycle event entity for Hetzner Cloud Costs."""

from __future__ import annotations

from datetime import UTC, datetime

from homeassistant.components.event import EventEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import HetznerCostsCoordinator, ServerInfo

EVENT_STARTED = "server_started"
EVENT_REMOVED = "server_removed"


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: HetznerCostsCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([HetznerLifecycleEvent(coordinator, entry)])


class HetznerLifecycleEvent(CoordinatorEntity[HetznerCostsCoordinator], EventEntity):
    _attr_name = "Hetzner Cloud server lifecycle"
    _attr_event_types = [EVENT_STARTED, EVENT_REMOVED]

    def __init__(
        self, coordinator: HetznerCostsCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_lifecycle"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            entry_type=DeviceEntryType.SERVICE,
            name=entry.title,
            manufacturer="Hetzner",
            model="Cloud project",
            configuration_url="https://console.hetzner.cloud/",
        )
        # ponytail: known-ids tracked in-memory only, not persisted. A restart
        # re-baselines without firing events for servers that changed while
        # down - acceptable, this is informational, the cost ledger is the
        # source of truth and is persisted separately.
        self._known: dict[int, ServerInfo] = {
            s.id: s for s in coordinator.data.servers
        }

    def _handle_coordinator_update(self) -> None:
        current = {s.id: s for s in self.coordinator.data.servers}

        for server_id, info in current.items():
            if server_id not in self._known:
                self._trigger_event(
                    EVENT_STARTED,
                    {
                        "server_id": info.id,
                        "name": info.name,
                        "server_type": info.server_type,
                        "location": info.location,
                    },
                )

        for server_id, info in self._known.items():
            if server_id not in current:
                lifetime_minutes = round(
                    (datetime.now(UTC) - info.created).total_seconds() / 60
                )
                self._trigger_event(
                    EVENT_REMOVED,
                    {
                        "server_id": info.id,
                        "name": info.name,
                        "server_type": info.server_type,
                        "location": info.location,
                        "lifetime_minutes": lifetime_minutes,
                    },
                )

        self._known = current
        super()._handle_coordinator_update()
