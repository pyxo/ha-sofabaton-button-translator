"""Exercise UI forms through Home Assistant's actual flow manager."""

import asyncio
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.sofabaton_button_translator.config_flow import ConfigFlow
from custom_components.sofabaton_button_translator.const import DOMAIN
from custom_components.sofabaton_button_translator.model import mappings, new_room


async def start(hass):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    return result["flow_id"]


async def configure(hass, flow_id, **data):
    return await hass.config_entries.flow.async_configure(flow_id, data)


async def option(hass, entry, step, **data):
    result = await hass.config_entries.options.async_init(entry.entry_id)
    flow_id = result["flow_id"]
    await hass.config_entries.options.async_configure(flow_id, {"next_step_id": step})
    return await hass.config_entries.options.async_configure(flow_id, data)


async def test_mqtt_dependency(hass):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    assert result["reason"] == "mqtt_required"


async def test_manual_default_and_initial_custom_mapping(hass, mqtt_entry):
    flow_id = await start(hass)
    await configure(hass, flow_id, next_step_id="manual")
    result = await configure(
        hass, flow_id, room_name="Family Room", mqtt_id="HUB1", default_device_id="1"
    )
    assert result["step_id"] == "menu"
    await configure(hass, flow_id, next_step_id="devices")
    await configure(hass, flow_id, next_step_id="add_device")
    result = await configure(hass, flow_id, device_id="1", device_name="Duplicate")
    assert result["errors"] == {"base": "duplicate_device"}
    await configure(hass, flow_id, device_id="2", device_name="Sources")
    await configure(hass, flow_id, next_step_id="mappings")
    await configure(hass, flow_id, device_id="2")
    await configure(hass, flow_id, next_step_id="set_mapping")
    result = await configure(hass, flow_id, key_id="3", button_name="Apple TV 1")
    assert result["step_id"] == "mapping_menu"
    await configure(hass, flow_id, next_step_id="menu")
    with patch(
        "custom_components.sofabaton_button_translator.async_setup_entry",
        AsyncMock(return_value=True),
    ):
        result = await configure(hass, flow_id, next_step_id="finish")
        await hass.async_block_till_done()
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"]["devices"]["1"]["name"] == "Default Remote"
    assert result["data"]["devices"]["1"]["mappings"] == {}
    assert result["data"]["devices"]["2"]["mappings"] == {"3": "Apple TV 1"}
    assert len(mappings(result["data"], 1)) == 68


async def test_no_default_duplicate_hub_and_finish_race(hass, mqtt_entry, room_entry):
    flow_id = await start(hass)
    await configure(hass, flow_id, next_step_id="manual")
    result = await configure(hass, flow_id, room_name="Other", mqtt_id="HUB1")
    assert result["errors"]["base"] == "duplicate_mqtt"
    await configure(hass, flow_id, room_name="Other", mqtt_id="HUB2")
    other = MockConfigEntry(domain=DOMAIN, data=new_room("Concurrent", "HUB2"))
    other.add_to_hass(hass)
    result = await configure(hass, flow_id, next_step_id="finish")
    assert result["reason"] == "duplicate_mqtt"
    flow_id = await start(hass)
    await configure(hass, flow_id, next_step_id="manual")
    await configure(hass, flow_id, room_name="Other", mqtt_id="HUB3")
    with patch(
        "custom_components.sofabaton_button_translator.async_setup_entry",
        AsyncMock(return_value=True),
    ):
        result = await configure(hass, flow_id, next_step_id="finish")
        await hass.async_block_till_done()
    assert result["data"]["devices"] == {}
    assert result["data"]["default_device"] is None


async def test_options_preserve_ids_and_custom_maps(hass, room_entry):
    original = deepcopy(dict(room_entry.data))
    result = await option(hass, room_entry, "room", room_name="Living Room", mqtt_id="NEW_HUB")
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert room_entry.data["hub"] == original["hub"]
    assert room_entry.data["room"] == original["room"]
    assert room_entry.title == "Living Room"
    data = deepcopy(dict(room_entry.data))
    data["devices"]["2"] = {"name": "Sources", "mappings": {"3": "Apple TV"}}
    hass.config_entries.async_update_entry(room_entry, data=data)
    await option(hass, room_entry, "default", device_id="2")
    assert mappings(room_entry.data, 2)[3] == "down"
    assert room_entry.data["devices"]["2"]["mappings"] == {"3": "Apple TV"}
    await option(hass, room_entry, "default", device_id="none")
    assert mappings(room_entry.data, 2)[3] == "Apple TV"


async def test_removal_confirmation_cancel_and_accept(hass, room_entry):
    async def removal(confirm):
        result = await hass.config_entries.options.async_init(room_entry.entry_id)
        flow_id = result["flow_id"]
        for data in (
            {"next_step_id": "devices"},
            {"next_step_id": "remove_device"},
            {"device_id": "1"},
        ):
            result = await hass.config_entries.options.async_configure(flow_id, data)
        assert result["step_id"] == "confirm_remove"
        return await hass.config_entries.options.async_configure(flow_id, {"confirm": confirm})

    result = await removal(False)
    assert result["step_id"] == "menu"
    assert "1" in room_entry.data["devices"]
    hass.config_entries.options.async_abort(result["flow_id"])
    result = await removal(True)
    assert room_entry.data["devices"] == {}
    assert room_entry.data["default_device"] is None


async def test_discovery_filters_and_cleans_up(hass, mqtt_entry, transport):
    flow = ConfigFlow()
    flow.hass = hass
    with patch("custom_components.sofabaton_button_translator.config_flow.DISCOVERY_SECONDS", 0.01):
        task = asyncio.create_task(flow._discover())
        await asyncio.sleep(0)
        receive = transport[0]["+/up"]
        receive(SimpleNamespace(topic="HUB_A/up", payload='{"device_id":1,"key_id":1}'))
        receive(SimpleNamespace(topic="HUB_A/up", payload='{"device_id":1,"key_id":2}'))
        receive(SimpleNamespace(topic="not_remote/up", payload="{}"))
        receive(SimpleNamespace(topic="nested/topic/up", payload='{"device_id":1,"key_id":1}'))
        await task
    assert flow.discovered == {"HUB_A"}
    assert transport[1] == ["+/up"]
    assert transport[0] == {}


async def test_discovery_cancel_unsubscribes(hass, mqtt_entry, transport):
    flow = ConfigFlow()
    flow.hass = hass
    flow.discovery_task = asyncio.create_task(flow._discover())
    await asyncio.sleep(0)
    flow.async_remove()
    try:
        await flow.discovery_task
    except asyncio.CancelledError:
        pass
    assert transport[0] == {}
    assert transport[1] == ["+/up"]


async def test_empty_device_lists_do_not_discard_setup(hass, mqtt_entry):
    flow_id = await start(hass)
    await configure(hass, flow_id, next_step_id="manual")
    await configure(hass, flow_id, room_name="Empty", mqtt_id="EMPTY")
    result = await configure(hass, flow_id, next_step_id="mappings")
    assert result["errors"]["base"] == "no_custom_devices"
    result = await configure(hass, flow_id)
    assert result["step_id"] == "menu"
    hass.config_entries.flow.async_abort(flow_id)


async def test_mapping_edit_delete_clear_and_read_only(hass, room_entry):
    from custom_components.sofabaton_button_translator.config_flow import OptionsFlow

    flow = OptionsFlow()
    flow.hass = hass
    flow.data = deepcopy(dict(room_entry.data))
    flow.data["devices"]["2"] = {"name": "Sources", "mappings": {"3": "Old"}}
    flow.selected = "1"
    result = await flow.async_step_set_mapping({"key_id": "1", "button_name": "Forbidden"})
    assert result["errors"]["base"] == "read_only"
    flow.selected = "2"
    with patch.object(flow, "saved", AsyncMock(return_value={"saved": True})):
        await flow.async_step_set_mapping({"key_id": "3", "button_name": "Renamed"})
        assert flow.data["devices"]["2"]["mappings"] == {"3": "Renamed"}
        await flow.async_step_delete_mapping({"key_id": "3"})
        assert flow.data["devices"]["2"]["mappings"] == {}
        await flow.async_step_set_mapping({"key_id": "4", "button_name": "Kodi"})
        await flow.async_step_clear_mappings({"confirm": True})
        assert flow.data["devices"]["2"]["mappings"] == {}


async def test_options_repeated_mapping_edits_save_and_keep_menu(hass, room_entry):
    data = deepcopy(dict(room_entry.data))
    data["devices"]["2"] = {"name": "Sources", "mappings": {}}
    hass.config_entries.async_update_entry(room_entry, data=data)
    result = await hass.config_entries.options.async_init(room_entry.entry_id)
    flow_id = result["flow_id"]

    async def edit(**values):
        return await hass.config_entries.options.async_configure(flow_id, values)

    await edit(next_step_id="mappings")
    await edit(device_id="2")
    for key, label in (("3", "Apple TV"), ("4", "Kodi"), ("3", "Apple TV renamed")):
        before = deepcopy(dict(room_entry.data))
        await edit(next_step_id="set_mapping")
        result = await edit(key_id=key, button_name=label)
        assert result["type"] == FlowResultType.MENU
        assert result["step_id"] == "mapping_menu"
        assert room_entry.data["devices"]["2"]["mappings"][key] == label
        assert before != dict(room_entry.data)

    await edit(next_step_id="delete_mapping")
    result = await edit(key_id="3")
    assert result["step_id"] == "mapping_menu"
    assert room_entry.data["devices"]["2"]["mappings"] == {"4": "Kodi"}
    await edit(next_step_id="clear_mappings")
    result = await edit(confirm=False)
    assert result["step_id"] == "mapping_menu"
    assert room_entry.data["devices"]["2"]["mappings"] == {"4": "Kodi"}
    await edit(next_step_id="clear_mappings")
    result = await edit(confirm=True)
    assert result["step_id"] == "mapping_menu"
    assert room_entry.data["devices"]["2"]["mappings"] == {}

    await edit(next_step_id="set_mapping")
    await edit(key_id="7", button_name="Saved before closing")
    await edit(next_step_id="menu")
    hass.config_entries.options.async_abort(flow_id)
    assert room_entry.data["devices"]["2"]["mappings"] == {"7": "Saved before closing"}
    assert room_entry.data["devices"]["1"]["mappings"] == {}


async def test_options_mapping_edits_detect_concurrent_changes(hass, room_entry):
    data = deepcopy(dict(room_entry.data))
    data["devices"]["2"] = {"name": "Sources", "mappings": {}}
    hass.config_entries.async_update_entry(room_entry, data=data)
    result = await hass.config_entries.options.async_init(room_entry.entry_id)
    flow_id = result["flow_id"]
    for values in (
        {"next_step_id": "mappings"},
        {"device_id": "2"},
        {"next_step_id": "set_mapping"},
        {"key_id": "3", "button_name": "Saved"},
    ):
        await hass.config_entries.options.async_configure(flow_id, values)
    external = deepcopy(dict(room_entry.data))
    external["room_name"] = "Changed elsewhere"
    hass.config_entries.async_update_entry(room_entry, data=external)
    await hass.config_entries.options.async_configure(flow_id, {"next_step_id": "set_mapping"})
    result = await hass.config_entries.options.async_configure(
        flow_id, {"key_id": "4", "button_name": "Must not overwrite"}
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "settings_changed"
    assert room_entry.data["room_name"] == "Changed elsewhere"
    assert room_entry.data["devices"]["2"]["mappings"] == {"3": "Saved"}


async def test_discovery_progress_flow(hass, mqtt_entry, transport):
    flow_id = await start(hass)
    with patch("custom_components.sofabaton_button_translator.config_flow.DISCOVERY_SECONDS", 0.01):
        result = await configure(hass, flow_id, next_step_id="discover")
        assert result["type"] == FlowResultType.SHOW_PROGRESS
        await asyncio.sleep(0)
        transport[0]["+/up"](
            SimpleNamespace(topic="DISCOVERED/up", payload='{"device_id":1,"key_id":1}')
        )
        await asyncio.sleep(0.02)
        result = await hass.config_entries.flow.async_configure(flow_id)
        if result["type"] == FlowResultType.SHOW_PROGRESS_DONE:
            result = await hass.config_entries.flow.async_configure(flow_id)
        assert result["step_id"] == "discovered"
        result = await configure(hass, flow_id, mqtt_id="DISCOVERED")
        assert result["step_id"] == "manual"
        assert transport[0] == {}
    hass.config_entries.flow.async_abort(flow_id)
