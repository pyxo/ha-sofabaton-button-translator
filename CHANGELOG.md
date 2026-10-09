# Changelog

## 1.0.1 — 2026-10-09

- Add default commands `67: power_on` and `68: power_off`, bringing the built-in set to 68 mappings.
- Return to the selected device's mapping menu after adding, editing, deleting, or clearing mappings. Configure saves each change immediately and allows repeated edits without reopening the dialog.

## 1.0.0 — 2026-10-09

- UI configuration for one MQTT hub per room, manual entry and bounded traffic discovery.
- Permanent room and hub IDs; virtual-device add/rename/removal with confirmation.
- Exact 66 built-in default mappings and independent, preserved custom mappings.
- Eight-field `sofabaton_button` events for every valid command, including unmapped devices/keys.
- Native device triggers with dynamic button labels and numeric identity.
- Restored diagnostic Last Activity timestamp sensor.
- HACS metadata, English translations, tests, CI, documentation and AI disclosure.

Initial release for HACS custom-repository installation. Physical-device and live-broker acceptance remain pending.
