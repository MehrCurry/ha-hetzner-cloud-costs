"""Sensor entities for Hetzner Cloud Costs."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import HetznerCostsCoordinator

CURRENCY_EUR = "EUR"

# Hetzner server status enum (docs.hetzner.cloud/cloud.spec.json). "running" is
# the only one with standalone operational value, so it's the only one on by
# default - the rest are there for anyone debugging stuck transitions.
SERVER_STATUSES = [
    "running",
    "initializing",
    "starting",
    "stopping",
    "off",
    "deleting",
    "migrating",
    "rebuilding",
    "unknown",
]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: HetznerCostsCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            HetznerCostRateSensor(coordinator, entry),
            HetznerCostTotalSensor(coordinator, entry),
            HetznerActiveServerCountSensor(coordinator, entry),
            HetznerServersStartedSensor(coordinator, entry),
            HetznerOldestRunningSensor(coordinator, entry),
            *(
                HetznerStatusCountSensor(coordinator, entry, status)
                for status in SERVER_STATUSES
            ),
        ]
    )


class _HetznerCostsEntity(CoordinatorEntity[HetznerCostsCoordinator], SensorEntity):
    def __init__(
        self, coordinator: HetznerCostsCoordinator, entry: ConfigEntry, key: str
    ) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            entry_type=DeviceEntryType.SERVICE,
            name=entry.title,
            manufacturer="Hetzner",
            model="Cloud project",
            configuration_url="https://console.hetzner.cloud/",
        )


class HetznerCostRateSensor(_HetznerCostsEntity):
    _attr_name = "Hetzner Cloud cost rate"
    _attr_native_unit_of_measurement = f"{CURRENCY_EUR}/h"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 4

    def __init__(
        self, coordinator: HetznerCostsCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, entry, "cost_rate")

    @property
    def native_value(self) -> float:
        return float(self.coordinator.data.rate)


class HetznerCostTotalSensor(_HetznerCostsEntity):
    _attr_name = "Hetzner Cloud cost total"
    _attr_native_unit_of_measurement = CURRENCY_EUR
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = SensorStateClass.TOTAL
    _attr_suggested_display_precision = 4

    def __init__(
        self, coordinator: HetznerCostsCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, entry, "cost_total")

    @property
    def native_value(self) -> float:
        return float(self.coordinator.data.total_cost)


class HetznerActiveServerCountSensor(_HetznerCostsEntity):
    _attr_name = "Hetzner Cloud active servers"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self, coordinator: HetznerCostsCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, entry, "active_count")

    @property
    def native_value(self) -> int:
        return self.coordinator.data.active_count


class HetznerServersStartedSensor(_HetznerCostsEntity):
    _attr_name = "Hetzner Cloud servers started"
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_entity_registry_enabled_default = False

    def __init__(
        self, coordinator: HetznerCostsCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, entry, "started_total")

    @property
    def native_value(self) -> int:
        return self.coordinator.data.started_total


class HetznerOldestRunningSensor(_HetznerCostsEntity):
    _attr_name = "Hetzner Cloud oldest running server since"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(
        self, coordinator: HetznerCostsCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, entry, "oldest_running_since")

    @property
    def native_value(self):
        running = [
            s.created
            for s in self.coordinator.data.servers
            if s.status == "running"
        ]
        return min(running) if running else None


class HetznerStatusCountSensor(_HetznerCostsEntity):
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self, coordinator: HetznerCostsCoordinator, entry: ConfigEntry, status: str
    ) -> None:
        super().__init__(coordinator, entry, f"status_{status}")
        self._status = status
        self._attr_name = f"Hetzner Cloud servers {status}"
        self._attr_entity_registry_enabled_default = status == "running"

    @property
    def native_value(self) -> int:
        return sum(
            1 for s in self.coordinator.data.servers if s.status == self._status
        )
