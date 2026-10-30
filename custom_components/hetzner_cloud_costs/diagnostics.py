"""Diagnostics for Hetzner Cloud Costs - the full server field set lives here."""

from __future__ import annotations

from dataclasses import asdict

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import HetznerCostsCoordinator


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict:
    coordinator: HetznerCostsCoordinator = hass.data[DOMAIN][entry.entry_id]
    data = coordinator.data
    return {
        "rate": str(data.rate),
        "total_cost": str(data.total_cost),
        "active_count": data.active_count,
        "started_total": data.started_total,
        "servers": [
            {**asdict(s), "created": s.created.isoformat()} for s in data.servers
        ],
    }
