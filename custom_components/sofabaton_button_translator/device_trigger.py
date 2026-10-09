"""Native device trigger with live labels and stable numeric key matching."""

import probatio as vol
from homeassistant.components.device_automation import DEVICE_TRIGGER_BASE_SCHEMA
from homeassistant.components.homeassistant.triggers import event as event_trigger
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import selector

from .const import DOMAIN, EVENT
from .model import device_identifier, mappings, numeric_id

TRIGGER_SCHEMA = DEVICE_TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required("type"): "button_pressed",
        vol.Required("key_id"): numeric_id,
    }
)


def resolve_device(hass, registry_id):
    device = dr.async_get(hass).async_get(registry_id)
    if device:
        for entry_id in device.config_entries:
            entry = hass.config_entries.async_get_entry(entry_id)
            if entry is None or entry.domain != DOMAIN:
                continue
            for key in entry.data["devices"]:
                if (DOMAIN, device_identifier(entry.data, key)) in device.identifiers:
                    return entry, int(key)
    raise vol.Invalid("Select a configured Sofabaton virtual device")


async def async_get_triggers(hass, device_id):
    try:
        resolve_device(hass, device_id)
    except vol.Invalid:
        return []
    # A dynamic selector keeps names live without storing names as trigger identity.
    return [
        {"platform": "device", "domain": DOMAIN, "device_id": device_id, "type": "button_pressed"}
    ]


async def async_get_trigger_capabilities(hass, config):
    entry, device_id = resolve_device(hass, config["device_id"])
    options = [
        {"value": str(key), "label": f"{label} ({key})"}
        for key, label in sorted(mappings(entry.data, device_id).items())
    ]
    return {
        "extra_fields": vol.Schema(
            {
                vol.Required("key_id"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=options,
                        custom_value=True,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                )
            }
        )
    }


async def async_validate_trigger_config(hass, config):
    config = TRIGGER_SCHEMA(config)
    resolve_device(hass, config["device_id"])
    return config


async def async_attach_trigger(hass, config, action, trigger_info):
    entry, device_id = resolve_device(hass, config["device_id"])
    event_config = event_trigger.TRIGGER_SCHEMA(
        {
            "platform": "event",
            "event_type": EVENT,
            "event_data": {
                "room": entry.data["room"],
                "device_id": device_id,
                "button_id": numeric_id(config["key_id"]),
            },
        }
    )
    return await event_trigger.async_attach_trigger(
        hass,
        event_config,
        action,
        trigger_info,
        platform_type="device",
    )
