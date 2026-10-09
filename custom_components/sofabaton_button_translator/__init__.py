"""Translate Sofabaton MQTT button commands into Home Assistant events."""

import logging
from dataclasses import dataclass, field
from datetime import datetime

from homeassistant.components import mqtt
from homeassistant.core import callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.util import dt as dt_util

from .const import DOMAIN, EVENT, PLATFORMS
from .model import device_identifier, event_data, hub_identifier, parse_payload

_LOGGER = logging.getLogger(__name__)


@dataclass
class Runtime:
    """Per-entry resources, with no shared mutable room state."""

    last_activity: datetime | None = None
    unsubscribers: list = field(default_factory=list)


def activity_signal(entry_id):
    return f"{DOMAIN}_{entry_id}_activity"


@callback
def register_devices(hass, entry):
    registry = dr.async_get(hass)
    data = entry.data
    hub_id = hub_identifier(data)
    hub = registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, hub_id)},
        name=f"{data['room_name']} Sofabaton Hub",
        manufacturer="Sofabaton",
        model="MQTT Hub",
    )
    wanted = {(DOMAIN, hub_id)}
    for device_id, device in data["devices"].items():
        identifier = (DOMAIN, device_identifier(data, device_id))
        wanted.add(identifier)
        registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={identifier},
            name=f"{data['room_name']} - {device['name']}",
            manufacturer="Pyxo",
            model="Sofabaton Virtual Device",
            via_device_id=hub.id,
        )
    for device in dr.async_entries_for_config_entry(registry, entry.entry_id):
        if not device.identifiers & wanted:
            registry.async_update_device(device.id, remove_config_entry_id=entry.entry_id)


async def async_setup_entry(hass, entry):
    if not await mqtt.async_wait_for_mqtt_client(hass):
        raise ConfigEntryNotReady("The MQTT integration must be configured")
    runtime = entry.runtime_data = Runtime()
    register_devices(hass, entry)

    @callback
    def message_received(message):
        parsed = parse_payload(message.payload)
        if parsed is None:
            _LOGGER.debug("Ignoring malformed Sofabaton command on %s", message.topic)
            return
        runtime.last_activity = dt_util.utcnow()
        hass.bus.async_fire(EVENT, event_data(entry.data, *parsed))
        async_dispatcher_send(hass, activity_signal(entry.entry_id))

    # HA owns broker reconnect and resubscription; do not create a second client.
    unsubscribe = await mqtt.async_subscribe(
        hass,
        f"{entry.data['mqtt_id']}/up",
        message_received,
        qos=0,
    )
    runtime.unsubscribers.append(unsubscribe)
    try:
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except BaseException:
        unsubscribe()
        runtime.unsubscribers.clear()
        raise
    entry.async_on_unload(entry.add_update_listener(async_update_options))
    return True


async def async_update_options(hass, entry):
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass, entry):
    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False
    for unsubscribe in entry.runtime_data.unsubscribers:
        unsubscribe()
    entry.runtime_data.unsubscribers.clear()
    return True


async def async_remove_config_entry_device(hass, entry, device_entry):
    """Use the options flow so configured devices cannot bypass confirmation."""
    return not any(
        domain == DOMAIN
        and (
            identifier == hub_identifier(entry.data)
            or identifier in {device_identifier(entry.data, key) for key in entry.data["devices"]}
        )
        for domain, identifier in device_entry.identifiers
    )
