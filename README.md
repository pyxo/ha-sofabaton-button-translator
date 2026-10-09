# Sofabaton Button Translator

Developed by **Pyxo**. A local MQTT custom integration for Home Assistant **2026.10 or later**, with one hub per room, configurable virtual remotes, and native automation triggers. No cloud service or separate MQTT client is used.

## Installation

Version **1.0.1** adds power commands and continuous mapping editing. Install through HACS as a custom repository after the version is released. Physical-device and live-broker acceptance testing remains pending; see [VALIDATION.md](VALIDATION.md).

Add `https://github.com/pyxo/ha-sofabaton-button-translator` to **HACS → Custom repositories**, category **Integration**, download it and restart Home Assistant. This is a custom repository, not a claim of inclusion in the HACS default catalog.

For manual installation, copy `custom_components/sofabaton_button_translator` into your Home Assistant configuration's `custom_components` directory and restart. This integration uses Home Assistant 2026.10 APIs; older versions are not supported.

First configure Home Assistant's **MQTT** integration and arrange for your Sofabaton hub to publish button commands to that same broker. This integration does not configure the hub, broker, or Sofabaton app.

## Setup

1. Open **Settings → Devices & services → Add integration → Sofabaton Button Translator**.
2. Enter the MQTT ID manually, or select **Discover Remotes** and press buttons during the 15-second listening window. Discovery listens temporarily on `+/up`, validates button messages, and lists unconfigured hub IDs. You can return to manual entry. Cancelling discovery removes its subscription.
3. Enter the room name and optional Default Device ID. Supplying an ID automatically creates **Default Remote** with all 68 built-in mappings. Leaving it blank creates no virtual device.
4. Add more virtual devices and mappings, or choose **Finish setup** immediately. Each additional device begins with empty custom mappings.

A room is a separate configuration entry, containing one hub. MQTT IDs are case-sensitive and unique across rooms. Device IDs are non-negative integers, unique within their room; the same ID in another room is allowed. Room names need not be unique. There is no imposed virtual-device count limit. The hub and configured virtual devices appear in the device registry, with virtual devices linked to their hub. Unconfigured devices emit events but do not create registry devices.

## Configuration

Use the integration entry's **Configure** menu:

- **Room Settings:** rename the room or change its MQTT ID.
- **Manage Virtual Devices:** add, rename, or remove devices. Removal requires explicit confirmation and warns about affected automations. Numeric device IDs are immutable; remove and add a device to change its ID.
- **Change Default Device:** choose a configured device or no default. The selected device uses the shared, read-only built-in mappings. Its custom mappings remain stored and become active again when it is no longer the default.
- **Manage Button Mappings:** choose a non-default device, then add/edit a mapping by key ID, delete one mapping, or clear all mappings after confirmation. Removing mappings never removes the device.

Setup allows multiple edits before **Finish**. Adding, editing, deleting, or clearing a mapping returns to the same device's mapping menu. During Configure, each mapping change saves immediately, so closing the dialog retains saved changes. Use **Back to menu** to select another device or setting. Other Configure operations save and close the flow. Changes reload only this room, without restarting Home Assistant. The previous MQTT subscription is removed and the new one installed. Commands during the brief reload gap may be missed.

Permanent random room and hub IDs are created once and saved with the entry. Room/device/button names and MQTT IDs do not determine registry identity. Virtual-device identity uses the permanent hub ID plus numeric device ID. Changing names or MQTT routing preserves device automation references. Deleting a virtual device removes its registry entry and custom mappings; re-adding it is not guaranteed to repair old automations.

## MQTT and events

Subscribe topic: `<mqtt_id>/up`, for example `441BF641BD00/up`.

```json
{"device_id": 2, "key_id": 3}
```

Both IDs must be non-negative JSON integers. Strings, booleans, fractions, missing fields, malformed JSON and non-object payloads are ignored and logged at debug level, without logging raw payloads. Extra payload fields are ignored. Every valid command emits `sofabaton_button`, including unknown keys and unconfigured devices. Long presses use separate key IDs; no hold timers or debouncing are applied.

Events have **exactly eight fields**:

| Field | Type | Meaning |
| --- | --- | --- |
| `room` | string | Permanent room ID; copy it from a received event |
| `room_name` | string | Current friendly room name |
| `mqtt_id` | string | Current MQTT routing ID |
| `device_id` | integer | Numeric virtual-device ID, not HA's registry ID |
| `device_name` | string or null | Configured name, or null for unconfigured devices |
| `default_device` | boolean | Whether this is the designated default |
| `button_id` | integer | Raw numeric key ID |
| `button` | string or null | Translated name, or null when unmapped |

No raw payload or source-specific fields are included. Use **Developer tools → Events → Listen to events → `sofabaton_button`** to inspect the permanent room ID and incoming IDs.

```yaml
triggers:
  - trigger: event
    event_type: sofabaton_button
    event_data:
      room: COPY_PERMANENT_ROOM_ID_FROM_AN_EVENT
      device_id: 2
      button_id: 3
actions:
  - action: light.toggle
    target:
      entity_id: light.living_room
```

MQTT reconnect and resubscription are handled by Home Assistant's MQTT integration. Messages published while disconnected are subject to the broker's delivery behavior; no integration queue is added. Publish button commands **without retain**: a retained valid command is treated as a command when delivered again at subscription/reconnect and may run an automation. There is no deduplication.

## Native device triggers

In an automation, choose **Device**, select a virtual device, then **Button pressed or held**. The button selector lists current mapped names and numeric IDs, including separate long-press choices. You may also enter an unmapped numeric key ID. Device triggers persist only the HA registry device ID and numeric `key_id`, so custom button renames do not alter matching. Reopen the editor to load updated labels.

```yaml
triggers:
  - trigger: device
    domain: sofabaton_button_translator
    device_id: COPY_HOME_ASSISTANT_REGISTRY_DEVICE_ID
    type: button_pressed
    key_id: 3
actions:
  - action: light.toggle
    target:
      entity_id: light.living_room
```

For unconfigured devices use the raw event trigger above. Native triggers are available only on configured virtual devices, not the hub. Home Assistant's native trigger UI is implemented as a dynamic button selector under one trigger type, rather than a separate static trigger type for every custom name.

## Last Activity

Each hub has one enabled-by-default diagnostic timestamp sensor, **Last Activity**. It updates on every valid command, even if the device/key is unknown, and restores its last timestamp after restart or entry reload. It starts unknown before any command has been received. No availability, connectivity or heartbeat sensor is created; an idle hub is not declared offline.

## Default mappings

The default device uses the 68 mappings supplied by Pyxo, including `67: power_on` and `68: power_off`. They are packaged as one immutable constant; no `buttons.yaml` is required. Custom mappings are never overwritten by changing the default designation.

| Key | Button | Key | Button |
| --- | --- | --- | --- |
| 1 | `up` | 34 | `guide_long` |
| 2 | `up_long` | 35 | `exit` |
| 3 | `down` | 36 | `exit_long` |
| 4 | `down_long` | 37 | `play` |
| 5 | `left` | 38 | `play_long` |
| 6 | `left_long` | 39 | `pause` |
| 7 | `right` | 40 | `pause_long` |
| 8 | `right_long` | 41 | `a` |
| 9 | `ok` | 42 | `a_long` |
| 10 | `ok_long` | 43 | `b` |
| 11 | `return` | 44 | `b_long` |
| 12 | `return_long` | 45 | `c` |
| 13 | `home` | 46 | `c_long` |
| 14 | `home_long` | 47 | `red` |
| 15 | `menu` | 48 | `red_long` |
| 16 | `menu_long` | 49 | `green` |
| 17 | `volume_up` | 50 | `green_long` |
| 18 | `volume_up_long` | 51 | `yellow` |
| 19 | `volume_down` | 52 | `yellow_long` |
| 20 | `volume_down_long` | 53 | `blue` |
| 21 | `mute` | 54 | `blue_long` |
| 22 | `mute_long` | 55 | `num_0` |
| 23 | `channel_down` | 56 | `num_1` |
| 24 | `channel_down_long` | 57 | `num_2` |
| 25 | `channel_up` | 58 | `num_3` |
| 26 | `channel_up_long` | 59 | `num_4` |
| 27 | `rewind` | 60 | `num_5` |
| 28 | `rewind_long` | 61 | `num_6` |
| 29 | `fast_forward` | 62 | `num_7` |
| 30 | `fast_forward_long` | 63 | `num_8` |
| 31 | `dvr` | 64 | `num_9` |
| 32 | `dvr_long` | 65 | `num_dash` |
| 33 | `guide` | 66 | `num_e` |
| 67 | `power_on` | 68 | `power_off` |

## Troubleshooting

- **MQTT required:** configure Home Assistant's MQTT integration first.
- **Nothing discovered:** confirm both systems use the same broker and MQTT credentials allow `+/up`. Press a button during discovery; discovery requires a valid payload. Manual setup avoids the wildcard subscription.
- **No events:** listen to `<mqtt_id>/up` in MQTT's configuration panel. IDs and topic case must match the setup above. Check the hub's virtual-device and key IDs.
- **Unmapped button:** a null `button` is expected for unknown keys. Configure a mapping or trigger by numeric ID.
- **Cannot edit mappings:** default-device mappings are read-only; change its designation or use a custom device.
- **Unexpected repeat after reload:** remove retained button messages at the broker and publish commands without retain.
- **Renames don't appear:** HA user-defined device/entity names take precedence over integration-provided names. Reopen automation configuration to refresh mapping labels.

Optional debug logging:

```yaml
logger:
  logs:
    custom_components.sofabaton_button_translator: debug
```

Remove a room through Home Assistant's integration entry menu. Remove an individual virtual device through **Configure**, where confirmation is enforced. For complete uninstall, remove entries, uninstall from HACS (or remove the custom component directory), then restart. Automations using removed devices must be reviewed.

## Development, validation and AI disclosure

AI tools, including **OpenAI ChatGPT and Codex**, assisted with architecture, code generation, documentation, debugging, and test development. **Pyxo** is the developer and maintainer. This independent community integration is not affiliated with or endorsed by Sofabaton or Home Assistant.

```sh
python3.14 -m venv .venv
.venv/bin/pip install -r requirements-test.txt
.venv/bin/python -m pytest --cov=custom_components.sofabaton_button_translator
.venv/bin/ruff check .
.venv/bin/ruff format --check .
```

Tests use the real Home Assistant 2026.10 runtime, config-flow manager, event bus, device/entity registries and sensor platform, with the MQTT transport mocked. CI runs the tests, Ruff, Home Assistant hassfest, and HACS repository validation. HACS brand validation is skipped because upstream brand registration is outside this repository.

Before a release, complete the hardware checklist in [VALIDATION.md](VALIDATION.md). Automated tests do not prove real remote behavior, broker reconnect delivery, browser rendering, or HACS installation/update/removal. The release workflow only runs when a maintainer deliberately pushes a matching version tag; creating this PR does not publish a release.

API references: [Home Assistant config flows](https://developers.home-assistant.io/docs/config_entries_config_flow_handler/), [device triggers](https://developers.home-assistant.io/docs/device_automation_trigger/), and [MQTT](https://www.home-assistant.io/integrations/mqtt/).
