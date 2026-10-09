# Validation and release acceptance

## Automated scope

The pinned test environment uses Python 3.14 and Home Assistant 2026.10.0. Tests cover the exact mapping table, invalid payloads, eight-field events, manual setup, default auto-creation, optional default, duplicate hub/device rejection, concurrent setup checks, discovery filtering and cancellation, custom mapping preservation, removal confirmation, stable identities, real sensor-platform restore, event-trigger dispatch and entry reload/unload. MQTT network calls are mocked; the rest of Home Assistant runs in its test harness.

Local tests: **40 passed, 89% integration-code coverage**. Linux CI also passed the 40-test suite and Ruff checks. GitHub CI validates manifest/translations with hassfest and HACS metadata; review the current check results on the PR.

HACS's integration manifest and `hacs.json` checks passed, but its repository-license check is expected to fail on this initial PR: GitHub exposes license metadata from the default branch, and `main` intentionally contains only the empty initialization commit until review. The complete MIT `LICENSE` is in this feature branch. Keep the license check enabled and rerun after merge once GitHub recognizes it. This does not indicate a missing license file in the proposed package. The HACS brands check is explicitly excluded until an upstream brand submission is approved.

## Manual acceptance before a release

- Install the feature branch manually on a test HA 2026.10+ instance with MQTT configured.
- Check setup and Configure forms in the browser, including discovery progress, manual fallback, empty lists, raw key entry, and readable native-trigger labels.
- Receive short/long-press commands from a physical Sofabaton remote; compare all used key IDs with the built-in table.
- Configure two hubs/rooms with the same virtual-device IDs and verify events/automations remain isolated.
- Add custom mappings; rename a button and room; change MQTT ID. Existing numeric automations must still fire, registry IDs must stay unchanged, and old-topic traffic must stop triggering.
- Change the default device twice and confirm custom mappings return. Default mappings must not be editable.
- Cancel and confirm virtual-device removal; verify registry cleanup and affected automation behavior.
- Restart HA and confirm configuration and Last Activity restore.
- Restart the broker, then press buttons and verify Home Assistant restores subscriptions. Confirm no duplicate subscription delivery.
- Exercise HACS installation, upgrade and uninstall after merge/release; verify entries/devices are removed as expected.

No physical hub, live broker, browser session connected to Home Assistant, or HACS installation was available during development. These checks must not be reported as completed from unit/integration test results.
