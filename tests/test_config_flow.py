from unittest.mock import patch

import aiohttp
from homeassistant import config_entries
from homeassistant.const import CONF_API_TOKEN
from homeassistant.core import HomeAssistant

from custom_components.hetzner_cloud_costs.const import DOMAIN


async def test_user_flow_success(hass: HomeAssistant, aioclient_mock):
    aioclient_mock.get(
        "https://api.hetzner.cloud/v1/servers",
        json={"servers": [], "meta": {"pagination": {"next_page": None}}},
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"

    with (
        patch(
            "custom_components.hetzner_cloud_costs.coordinator.HetznerCostsCoordinator._async_update_data"
        ),
        patch("custom_components.hetzner_cloud_costs.otel.ensure_tracer_provider"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_API_TOKEN: "test-token"}
        )

    assert result["type"] == "create_entry"
    assert result["data"][CONF_API_TOKEN] == "test-token"


async def test_user_flow_network_error_shows_cannot_connect(
    hass: HomeAssistant, aioclient_mock
):
    aioclient_mock.get("https://api.hetzner.cloud/v1/servers", exc=aiohttp.ClientError)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_TOKEN: "test-token"}
    )

    assert result["errors"] == {"base": "cannot_connect"}
