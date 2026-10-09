"""Restored diagnostic last-command timestamp for each hub."""

from homeassistant.components.sensor import RestoreSensor, SensorDeviceClass
from homeassistant.const import EntityCategory
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo

from . import activity_signal
from .const import DOMAIN
from .model import hub_identifier


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([LastActivity(entry)])


class LastActivity(RestoreSensor):
    _attr_has_entity_name = True
    _attr_translation_key = "last_activity"
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_should_poll = False

    def __init__(self, entry):
        self.entry = entry
        self._attr_unique_id = f"{entry.data['hub']}_last_activity"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, hub_identifier(entry.data))})

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        runtime = self.entry.runtime_data
        if runtime.last_activity is None and (previous := await self.async_get_last_sensor_data()):
            runtime.last_activity = previous.native_value
        self._attr_native_value = runtime.last_activity
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                activity_signal(self.entry.entry_id),
                self._activity_updated,
            )
        )

    @callback
    def _activity_updated(self):
        self._attr_native_value = self.entry.runtime_data.last_activity
        self.async_write_ha_state()
