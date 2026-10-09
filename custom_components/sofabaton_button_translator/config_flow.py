"""UI setup, bounded traffic discovery and transactional configuration editing."""

import asyncio
from copy import deepcopy

import probatio as vol
from homeassistant import config_entries
from homeassistant.components import mqtt
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import DISCOVERY_SECONDS, DOMAIN
from .model import mqtt_id, name, new_room, numeric_id, parse_payload


def select(options):
    return selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=[{"value": key, "label": label} for key, label in options.items()],
            mode=selector.SelectSelectorMode.DROPDOWN,
        )
    )


class Editor:
    """Shared setup/options editing steps; only complete validated edits are saved."""

    data: dict
    selected: str

    def duplicate_mqtt(self, value):
        current = getattr(self, "editing_entry_id", None)
        return any(
            entry.entry_id != current and entry.data["mqtt_id"] == value
            for entry in self.hass.config_entries.async_entries(DOMAIN)
        )

    async def async_step_devices(self, user_input=None):
        return self.async_show_menu(
            step_id="devices",
            menu_options=[
                "add_device",
                "rename_device",
                "remove_device",
                "menu",
            ],
        )

    async def async_step_add_device(self, user_input=None):
        errors = {}
        if user_input is not None:
            try:
                key = str(numeric_id(user_input["device_id"]))
                label = name(user_input["device_name"])
                if key in self.data["devices"]:
                    raise ValueError("duplicate_device")
                self.data["devices"][key] = {"name": label, "mappings": {}}
                return await self.saved()
            except ValueError as err:
                errors["base"] = str(err)
        return self.async_show_form(
            step_id="add_device",
            errors=errors,
            data_schema=vol.Schema(
                {
                    vol.Required("device_id"): str,
                    vol.Required("device_name"): str,
                }
            ),
        )

    async def pick_device(self, step, user_input, next_step, custom_only=False):
        choices = {
            key: f"{device['name']} ({key})"
            for key, device in self.data["devices"].items()
            if not custom_only or int(key) != self.data["default_device"]
        }
        if not choices:
            if user_input is not None:
                return await self.async_step_menu()
            return self.async_show_form(
                step_id=step,
                data_schema=vol.Schema({}),
                errors={"base": "no_custom_devices" if custom_only else "no_devices"},
            )
        if user_input is not None:
            if user_input["device_id"] not in choices:
                return self.async_abort(reason="invalid_device")
            self.selected = user_input["device_id"]
            return await getattr(self, f"async_step_{next_step}")()
        return self.async_show_form(
            step_id=step,
            data_schema=vol.Schema(
                {
                    vol.Required("device_id"): select(choices),
                }
            ),
        )

    async def async_step_rename_device(self, user_input=None):
        return await self.pick_device("rename_device", user_input, "rename")

    async def async_step_rename(self, user_input=None):
        errors = {}
        if user_input is not None:
            try:
                self.data["devices"][self.selected]["name"] = name(user_input["device_name"])
                return await self.saved()
            except ValueError as err:
                errors["base"] = str(err)
        return self.async_show_form(
            step_id="rename",
            errors=errors,
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "device_name", default=self.data["devices"][self.selected]["name"]
                    ): str,
                }
            ),
        )

    async def async_step_remove_device(self, user_input=None):
        return await self.pick_device("remove_device", user_input, "confirm_remove")

    async def async_step_confirm_remove(self, user_input=None):
        if user_input is not None:
            if user_input["confirm"]:
                del self.data["devices"][self.selected]
                if self.data["default_device"] == int(self.selected):
                    self.data["default_device"] = None
                return await self.saved()
            return await self.async_step_menu()
        return self.async_show_form(
            step_id="confirm_remove",
            description_placeholders={
                "device": self.data["devices"][self.selected]["name"],
            },
            data_schema=vol.Schema({vol.Required("confirm", default=False): bool}),
        )

    async def async_step_default(self, user_input=None):
        choices = {
            "none": "No default device",
            **{key: f"{device['name']} ({key})" for key, device in self.data["devices"].items()},
        }
        if user_input is not None:
            value = user_input["device_id"]
            if value not in choices:
                return self.async_abort(reason="invalid_device")
            self.data["default_device"] = None if value == "none" else int(value)
            return await self.saved()
        default = self.data["default_device"]
        return self.async_show_form(
            step_id="default",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "device_id", default="none" if default is None else str(default)
                    ): select(choices),
                }
            ),
        )

    async def async_step_mappings(self, user_input=None):
        return await self.pick_device("mappings", user_input, "mapping_menu", custom_only=True)

    async def async_step_mapping_menu(self, user_input=None):
        return self.async_show_menu(
            step_id="mapping_menu",
            menu_options=[
                "set_mapping",
                "delete_mapping",
                "clear_mappings",
                "menu",
            ],
        )

    def editable_mappings(self):
        if int(self.selected) == self.data["default_device"]:
            raise ValueError("read_only")
        return self.data["devices"][self.selected]["mappings"]

    async def async_step_set_mapping(self, user_input=None):
        errors = {}
        if user_input is not None:
            try:
                key = str(numeric_id(user_input["key_id"]))
                label = name(user_input["button_name"])
                self.editable_mappings()[key] = label
                return await self.saved()
            except ValueError as err:
                errors["base"] = str(err)
        existing = self.data["devices"][self.selected]["mappings"]
        return self.async_show_form(
            step_id="set_mapping",
            errors=errors,
            description_placeholders={
                "mappings": ", ".join(f"{k}: {v}" for k, v in existing.items()) or "None"
            },
            data_schema=vol.Schema({vol.Required("key_id"): str, vol.Required("button_name"): str}),
        )

    async def async_step_delete_mapping(self, user_input=None):
        try:
            choices = self.editable_mappings()
        except ValueError:
            return self.async_abort(reason="read_only")
        if not choices:
            if user_input is not None:
                return await self.async_step_mapping_menu()
            return self.async_show_form(
                step_id="delete_mapping", data_schema=vol.Schema({}), errors={"base": "no_mappings"}
            )
        if user_input is not None:
            choices.pop(user_input["key_id"], None)
            return await self.saved()
        return self.async_show_form(
            step_id="delete_mapping",
            data_schema=vol.Schema(
                {
                    vol.Required("key_id"): select({k: f"{v} ({k})" for k, v in choices.items()}),
                }
            ),
        )

    async def async_step_clear_mappings(self, user_input=None):
        if user_input is not None:
            if user_input["confirm"]:
                try:
                    self.editable_mappings().clear()
                except ValueError:
                    return self.async_abort(reason="read_only")
                return await self.saved()
            return await self.async_step_menu()
        return self.async_show_form(
            step_id="clear_mappings",
            data_schema=vol.Schema(
                {
                    vol.Required("confirm", default=False): bool,
                }
            ),
        )


class ConfigFlow(Editor, config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self):
        self.discovery_task = None
        self.discovered = set()
        self.discovered_id = ""

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return OptionsFlow()

    async def async_step_user(self, user_input=None):
        if not self.hass.config_entries.async_entries("mqtt"):
            return self.async_abort(reason="mqtt_required")
        return self.async_show_menu(step_id="user", menu_options=["manual", "discover"])

    async def async_step_manual(self, user_input=None):
        errors = {}
        if user_input is not None:
            try:
                topic = mqtt_id(user_input["mqtt_id"])
                if self.duplicate_mqtt(topic):
                    raise ValueError("duplicate_mqtt")
                raw_default = user_input.get("default_device_id", "").strip()
                default = numeric_id(raw_default) if raw_default else None
                self.data = new_room(user_input["room_name"], topic, default)
                return await self.async_step_menu()
            except ValueError as err:
                errors["base"] = str(err)
        return self.async_show_form(
            step_id="manual",
            errors=errors,
            data_schema=vol.Schema(
                {
                    vol.Required("room_name"): str,
                    vol.Required("mqtt_id", default=self.discovered_id): str,
                    vol.Optional("default_device_id", default=""): str,
                }
            ),
        )

    async def _discover(self):
        if not await mqtt.async_wait_for_mqtt_client(self.hass):
            return

        @callback
        def received(message):
            if parse_payload(message.payload) is None:
                return
            try:
                topic = mqtt_id(message.topic.removesuffix("/up"))
            except ValueError:
                return
            if not self.duplicate_mqtt(topic):
                self.discovered.add(topic)

        unsubscribe = await mqtt.async_subscribe(self.hass, "+/up", received)
        try:
            await asyncio.sleep(DISCOVERY_SECONDS)
        finally:
            unsubscribe()

    async def async_step_discover(self, user_input=None):
        if self.discovery_task is None:
            self.discovered.clear()
            self.discovery_task = self.hass.async_create_task(self._discover())
        if self.discovery_task.done():
            try:
                self.discovery_task.result()
            except Exception:
                self.discovery_task = None
                return self.async_show_progress_done(next_step_id="discovery_failed")
            self.discovery_task = None
            return self.async_show_progress_done(next_step_id="discovered")
        return self.async_show_progress(
            step_id="discover", progress_action="discover", progress_task=self.discovery_task
        )

    async def async_step_discovery_failed(self, user_input=None):
        return self.async_show_menu(step_id="discovery_failed", menu_options=["manual", "discover"])

    async def async_step_discovered(self, user_input=None):
        choices = {value: value for value in sorted(self.discovered)}
        choices["__manual__"] = "Enter MQTT ID manually"
        if user_input is not None:
            self.discovered_id = user_input["mqtt_id"]
            if self.discovered_id == "__manual__":
                self.discovered_id = ""
            return await self.async_step_manual()
        return self.async_show_form(
            step_id="discovered",
            data_schema=vol.Schema(
                {
                    vol.Required("mqtt_id"): select(choices),
                }
            ),
        )

    @callback
    def async_remove(self):
        if self.discovery_task and not self.discovery_task.done():
            self.discovery_task.cancel()
        super().async_remove()

    async def async_step_menu(self, user_input=None):
        return self.async_show_menu(
            step_id="menu",
            menu_options=[
                "devices",
                "default",
                "mappings",
                "finish",
            ],
        )

    async def saved(self):
        return await self.async_step_menu()

    async def async_step_finish(self, user_input=None):
        # Recheck after the multi-step wizard in case another room was added.
        if self.duplicate_mqtt(self.data["mqtt_id"]):
            return self.async_abort(reason="duplicate_mqtt")
        await self.async_set_unique_id(self.data["hub"])
        return self.async_create_entry(title=self.data["room_name"], data=self.data)


class OptionsFlow(Editor, config_entries.OptionsFlow):
    async def async_step_init(self, user_input=None):
        self.data = deepcopy(dict(self.config_entry.data))
        self.original_data = deepcopy(self.data)
        self.editing_entry_id = self.config_entry.entry_id
        return await self.async_step_menu()

    async def async_step_menu(self, user_input=None):
        return self.async_show_menu(
            step_id="menu",
            menu_options=[
                "room",
                "devices",
                "default",
                "mappings",
            ],
        )

    async def async_step_room(self, user_input=None):
        errors = {}
        if user_input is not None:
            try:
                topic = mqtt_id(user_input["mqtt_id"])
                label = name(user_input["room_name"])
                if self.duplicate_mqtt(topic):
                    raise ValueError("duplicate_mqtt")
                self.data.update(mqtt_id=topic, room_name=label)
                return await self.saved()
            except ValueError as err:
                errors["base"] = str(err)
        return self.async_show_form(
            step_id="room",
            errors=errors,
            data_schema=vol.Schema(
                {
                    vol.Required("room_name", default=self.data["room_name"]): str,
                    vol.Required("mqtt_id", default=self.data["mqtt_id"]): str,
                }
            ),
        )

    async def saved(self):
        if dict(self.config_entry.data) != self.original_data:
            return self.async_abort(reason="settings_changed")
        if self.duplicate_mqtt(self.data["mqtt_id"]):
            return self.async_abort(reason="duplicate_mqtt")
        self.hass.config_entries.async_update_entry(
            self.config_entry,
            data=self.data,
            title=self.data["room_name"],
        )
        return self.async_create_entry(title="", data={})
