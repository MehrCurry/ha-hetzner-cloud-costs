from dataclasses import dataclass
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from custom_components.hetzner_cloud_costs.coordinator import ServerInfo
from custom_components.hetzner_cloud_costs.event import (
    EVENT_REMOVED,
    EVENT_STARTED,
    HetznerLifecycleEvent,
)

NOW = datetime(2026, 10, 30, 12, 0, tzinfo=UTC)


@dataclass
class _FakeData:
    servers: list[ServerInfo]


def _server(server_id: int, created: datetime = NOW) -> ServerInfo:
    return ServerInfo(
        id=server_id,
        name=f"runner-{server_id}",
        status="running",
        server_type="cx22",
        location="fsn1",
        created=created,
    )


def _make_entity(servers: list[ServerInfo]) -> HetznerLifecycleEvent:
    coordinator = MagicMock()
    coordinator.data = _FakeData(servers=servers)
    entity = HetznerLifecycleEvent.__new__(HetznerLifecycleEvent)
    entity.coordinator = coordinator
    entity._known = {}
    return entity


def test_new_server_fires_started_event():
    entity = _make_entity([_server(1)])
    with (
        patch.object(entity, "_trigger_event") as trigger,
        patch(
            "homeassistant.helpers.update_coordinator.CoordinatorEntity"
            "._handle_coordinator_update"
        ),
    ):
        entity._handle_coordinator_update()
    trigger.assert_called_once_with(EVENT_STARTED, {
        "server_id": 1,
        "name": "runner-1",
        "server_type": "cx22",
        "location": "fsn1",
    })
    assert 1 in entity._known


def test_disappeared_server_fires_removed_event():
    entity = _make_entity([_server(1)])
    entity._known = {1: _server(1)}
    entity.coordinator.data = _FakeData(servers=[])
    with (
        patch.object(entity, "_trigger_event") as trigger,
        patch(
            "homeassistant.helpers.update_coordinator.CoordinatorEntity"
            "._handle_coordinator_update"
        ),
    ):
        entity._handle_coordinator_update()
    assert trigger.call_count == 1
    event_type, attrs = trigger.call_args[0]
    assert event_type == EVENT_REMOVED
    assert attrs["server_id"] == 1
    assert isinstance(attrs["lifetime_minutes"], int)
    assert entity._known == {}
