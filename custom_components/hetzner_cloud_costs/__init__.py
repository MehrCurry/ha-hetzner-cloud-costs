"""Hetzner Cloud Costs integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_TOKEN, Platform
from homeassistant.core import HomeAssistant

from . import otel
from .const import (
    CONF_LABEL_SELECTOR,
    CONF_POLL_INTERVAL,
    DEFAULT_POLL_INTERVAL,
    DOMAIN,
)
from .coordinator import HetznerCostsCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR, Platform.EVENT]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    # ponytail: gated on debug level at setup time, not live - toggling the
    # HA debug switch at runtime needs a reload of this entry to take effect.
    # Unbounded JSONL growth with no rotation is acceptable for a debug-only
    # trace file; add rotation if that stops being true.
    if _LOGGER.isEnabledFor(logging.DEBUG):
        await hass.async_add_executor_job(
            otel.ensure_tracer_provider, hass.config.path(f"{DOMAIN}_traces.jsonl")
        )
    coordinator = HetznerCostsCoordinator(
        hass,
        entry,
        token=entry.data[CONF_API_TOKEN],
        label_selector=entry.data.get(CONF_LABEL_SELECTOR, ""),
        poll_interval=entry.data.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL),
    )
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unloaded
