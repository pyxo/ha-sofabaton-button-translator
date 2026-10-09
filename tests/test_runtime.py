"""Real HA registry, sensor, event bus and device automation integration tests."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

from homeassistant.core import State
from homeassistant.helpers import device_registry as dr
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import mock_restore_cache_with_extra_data

from custom_components.sofabaton_button_translator.const import DOMAIN, EVENT
from custom_components.sofabaton_button_translator.device_trigger import (
    async_attach_trigger,
    async_get_trigger_capabilities,
    async_get_triggers,
    async_validate_trigger_config,
)
from custom_components.sofabaton_button_translator.model import device_identifier


async def setup(hass, entry):
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def test_events_registry_and_unload(hass, room_entry, transport):
    await setup(hass, room_entry)
    events = []
    unsub = hass.bus.async_listen(EVENT, events.append)
    subscriptions, removed = transport
    receive = subscriptions["HUB1/up"]
    receive(SimpleNamespace(payload='{"device_id":1,"key_id":2}', topic="HUB1/up"))
    receive(SimpleNamespace(payload='{"device_id":9,"key_id":999}', topic="HUB1/up"))
    receive(SimpleNamespace(payload="garbage", topic="HUB1/up"))
    await hass.async_block_till_done()
    assert len(events) == 2
    assert events[0].data["button"] == "up_long"
    assert events[1].data["device_name"] is None
    assert room_entry.runtime_data.last_activity is not None
    assert len(dr.async_entries_for_config_entry(dr.async_get(hass), room_entry.entry_id)) == 2
    assert await hass.config_entries.async_unload(room_entry.entry_id)
    assert removed == ["HUB1/up"]
    unsub()


async def test_trigger_keeps_numeric_identity_after_rename(hass, room_entry, transport):
    await setup(hass, room_entry)
    device = dr.async_get(hass).async_get_device_by_identifier(
        (DOMAIN, device_identifier(room_entry.data, 1)), room_entry.entry_id
    )
    triggers = await async_get_triggers(hass, device.id)
    config = await async_validate_trigger_config(hass, {**triggers[0], "key_id": "2"})
    capabilities = await async_get_trigger_capabilities(hass, config)
    assert capabilities["extra_fields"]({"key_id": "2"}) == {"key_id": "2"}
    action = AsyncMock()
    detach = await async_attach_trigger(
        hass,
        config,
        action,
        {"name": "test", "trigger_data": {"id": "0", "idx": "0"}, "variables": {}},
    )
    data = dict(room_entry.data)
    data.update(room_name="Renamed", mqtt_id="OTHER")
    hass.config_entries.async_update_entry(room_entry, data=data)
    # Listener reload is tested separately; this test feeds the new room data.
    from custom_components.sofabaton_button_translator.model import event_data

    hass.bus.async_fire(EVENT, event_data(data, 1, 2))
    await hass.async_block_till_done()
    assert action.call_count == 1
    hass.bus.async_fire(EVENT, event_data(data, 2, 2))
    hass.bus.async_fire(EVENT, event_data(data, 1, 3))
    await hass.async_block_till_done()
    assert action.call_count == 1
    detach()
    assert await hass.config_entries.async_unload(room_entry.entry_id)


async def test_last_activity_sensor_restore_and_update(hass, room_entry, transport):
    entity_id = "sensor.family_room_sofabaton_hub_last_activity"
    previous = dt_util.parse_datetime("2026-10-01T12:00:00+00:00")
    mock_restore_cache_with_extra_data(
        hass,
        [
            (
                State(entity_id, previous.isoformat()),
                {
                    "native_value": {
                        "__type": "<class 'datetime.datetime'>",
                        "isoformat": previous.isoformat(),
                    },
                    "native_unit_of_measurement": None,
                },
            )
        ],
    )
    assert await hass.config_entries.async_setup(room_entry.entry_id)
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == previous.isoformat()
    transport[0]["HUB1/up"](SimpleNamespace(payload='{"device_id":7,"key_id":4}', topic="HUB1/up"))
    await hass.async_block_till_done()
    assert (
        hass.states.get(entity_id).state
        == room_entry.runtime_data.last_activity.replace(microsecond=0).isoformat()
    )
    assert room_entry.runtime_data.last_activity > previous
    assert await hass.config_entries.async_unload(room_entry.entry_id)


async def test_registry_removal_and_stable_hub(hass, room_entry, transport):

    await setup(hass, room_entry)
    registry = dr.async_get(hass)
    original = dr.async_entries_for_config_entry(registry, room_entry.entry_id)
    original_ids = {device.id for device in original}
    data = dict(room_entry.data)
    data.update(room_name="New", mqtt_id="NEW")
    hass.config_entries.async_update_entry(room_entry, data=data)
    await hass.async_block_till_done()
    assert {
        device.id for device in dr.async_entries_for_config_entry(registry, room_entry.entry_id)
    } == original_ids
    assert "HUB1/up" not in transport[0]
    assert "NEW/up" in transport[0]
    assert transport[1] == ["HUB1/up"]
    data = {**data, "devices": {}, "default_device": None}
    hass.config_entries.async_update_entry(room_entry, data=data)
    await hass.async_block_till_done()
    assert len(dr.async_entries_for_config_entry(registry, room_entry.entry_id)) == 1

    assert await hass.config_entries.async_unload(room_entry.entry_id)
