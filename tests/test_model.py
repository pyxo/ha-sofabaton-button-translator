"""Protocol and identity contracts."""

import json

import pytest

from custom_components.sofabaton_button_translator.button_mappings import DEFAULT_BUTTONS
from custom_components.sofabaton_button_translator.model import (
    device_identifier,
    event_data,
    mappings,
    mqtt_id,
    new_room,
    numeric_id,
    parse_payload,
)


def test_exact_68_mappings():
    expected = "up up_long down down_long left left_long right right_long ok ok_long return return_long home home_long menu menu_long volume_up volume_up_long volume_down volume_down_long mute mute_long channel_down channel_down_long channel_up channel_up_long rewind rewind_long fast_forward fast_forward_long dvr dvr_long guide guide_long exit exit_long play play_long pause pause_long a a_long b b_long c c_long red red_long green green_long yellow yellow_long blue blue_long num_0 num_1 num_2 num_3 num_4 num_5 num_6 num_7 num_8 num_9 num_dash num_e".split()
    expected += ["power_on", "power_off"]
    assert dict(DEFAULT_BUTTONS) == dict(enumerate(expected, 1))
    with pytest.raises(TypeError):
        DEFAULT_BUTTONS[1] = "changed"


@pytest.mark.parametrize(
    "payload",
    [
        "bad",
        "[]",
        "null",
        "{}",
        '{"device_id":1}',
        '{"device_id":true,"key_id":2}',
        '{"device_id":1,"key_id":1.5}',
        '{"device_id":"1","key_id":2}',
        '{"device_id":-1,"key_id":2}',
        b"\xff",
        "[" * 1200,
    ],
)
def test_invalid_messages(payload):
    assert parse_payload(payload) is None


@pytest.mark.parametrize("value", [-1, True, 1.5, "", "1.0", "oops"])
def test_invalid_ui_ids(value):
    with pytest.raises(ValueError):
        numeric_id(value)


@pytest.mark.parametrize("value", ["", "a/b", "a+", "a#", "$SYS", "x\x00"])
def test_invalid_topic(value):
    with pytest.raises(ValueError):
        mqtt_id(value)


def test_event_contract_and_identity():
    data = new_room("Family Room", "HUB", 1)
    assert parse_payload(json.dumps({"device_id": 1, "key_id": 1})) == (1, 1)
    assert set(event_data(data, 1, 1)) == {
        "room",
        "room_name",
        "mqtt_id",
        "device_id",
        "device_name",
        "default_device",
        "button_id",
        "button",
    }
    assert event_data(data, 1, 1)["button"] == "up"
    assert event_data(data, 1, 67)["button"] == "power_on"
    assert event_data(data, 1, 68)["button"] == "power_off"
    assert event_data(data, 1, 999)["button"] is None
    assert event_data(data, 9, 1)["device_name"] is None
    assert event_data(data, 9, 1)["button"] is None
    identity = device_identifier(data, 1)
    data.update(room_name="New room", mqtt_id="NEW_HUB")
    assert device_identifier(data, 1) == identity
    assert new_room("Other", "OTHER", 1)["hub"] != data["hub"]


def test_default_switch_preserves_custom_mapping():
    data = new_room("Room", "HUB", 1)
    data["devices"]["2"] = {"name": "Sources", "mappings": {"1": "Kodi"}}
    data["default_device"] = 2
    assert mappings(data, 2)[1] == "up"
    assert mappings(data, 1) == {}
    data["default_device"] = None
    assert mappings(data, 2)[1] == "Kodi"
