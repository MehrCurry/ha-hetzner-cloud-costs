"""Config flow for Hetzner Cloud Costs."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_API_TOKEN
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    API_BASE_URL,
    CONF_LABEL_SELECTOR,
    CONF_POLL_INTERVAL,
    DEFAULT_POLL_INTERVAL,
    DOMAIN,
)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_TOKEN): str,
        vol.Optional(CONF_LABEL_SELECTOR, default=""): str,
        vol.Optional(CONF_POLL_INTERVAL, default=DEFAULT_POLL_INTERVAL): vol.All(
            vol.Coerce(int), vol.Range(min=10)
        ),
    }
)


class InvalidAuth(HomeAssistantError):
    """Token rejected by the Hetzner API."""


async def _validate_token(hass, token: str) -> None:
    session = async_get_clientsession(hass)
    async with session.get(
        f"{API_BASE_URL}/servers",
        headers={"Authorization": f"Bearer {token}"},
        params={"per_page": 1},
    ) as response:
        if response.status == 401:
            raise InvalidAuth
        if response.status != 200:
            raise HomeAssistantError(f"Hetzner API returned {response.status}")


class HetznerCloudCostsConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                await _validate_token(self.hass, user_input[CONF_API_TOKEN])
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except HomeAssistantError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(
                    title="Hetzner Cloud Costs", data=user_input
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )
