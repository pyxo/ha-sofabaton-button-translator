"""Pure validation and event translation, independent of Home Assistant."""

import json
import re
from uuid import uuid4

from .button_mappings import DEFAULT_BUTTONS


def numeric_id(value):
    """Normalize UI IDs; reject booleans, fractions, negatives and blank input."""
    if type(value) is int and value >= 0:
        return value
    if isinstance(value, str) and re.fullmatch(r"[0-9]+", value.strip()):
        return int(value)
    raise ValueError("invalid_id")


def mqtt_id(value):
    """Accept one literal, non-system MQTT topic level, preserving its case."""
    value = value.strip()
    if not value or any(c in value for c in "/+#\x00") or value.startswith("$"):
        raise ValueError("invalid_mqtt_id")
    if len(value.encode("utf-8")) > 65532:
        raise ValueError("invalid_mqtt_id")
    return value


def name(value):
    value = value.strip()
    if not value:
        raise ValueError("invalid_name")
    return value


def new_room(room_name, topic_id, default_id=None):
    """Names and routing never participate in permanent identity."""
    data = {
        "room": uuid4().hex,
        "hub": uuid4().hex,
        "room_name": name(room_name),
        "mqtt_id": mqtt_id(topic_id),
        "default_device": default_id,
        "devices": {},
    }
    if default_id is not None:
        data["devices"][str(default_id)] = {"name": "Default Remote", "mappings": {}}
    return data


def mappings(data, device_id):
    if data["default_device"] == device_id:
        return DEFAULT_BUTTONS
    device = data["devices"].get(str(device_id), {})
    return {int(key): value for key, value in device.get("mappings", {}).items()}


def parse_payload(payload):
    """Wire IDs must be JSON integers, not strings, floats or booleans."""
    try:
        decoded = json.loads(payload)
        if not isinstance(decoded, dict):
            return None
        device, key = decoded.get("device_id"), decoded.get("key_id")
        if type(device) is not int or type(key) is not int or min(device, key) < 0:
            return None
        return device, key
    except ValueError, TypeError, UnicodeError, RecursionError:
        return None


def event_data(data, device_id, key_id):
    device = data["devices"].get(str(device_id))
    return {
        "room": data["room"],
        "room_name": data["room_name"],
        "mqtt_id": data["mqtt_id"],
        "device_id": device_id,
        "device_name": device["name"] if device else None,
        "default_device": data["default_device"] == device_id,
        "button_id": key_id,
        "button": mappings(data, device_id).get(key_id),
    }


def hub_identifier(data):
    return f"hub:{data['hub']}"


def device_identifier(data, device_id):
    return f"{hub_identifier(data)}:device:{device_id}"
