"""Run the real Home Assistant runtime with only MQTT transport replaced."""

from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.sofabaton_button_translator.const import DOMAIN
from custom_components.sofabaton_button_translator.model import new_room


@pytest.fixture(autouse=True)
def custom_integrations(enable_custom_integrations):
    with (
        patch("homeassistant.components.mqtt.async_setup", AsyncMock(return_value=True)),
        patch("homeassistant.components.mqtt.async_setup_entry", AsyncMock(return_value=True)),
    ):
        yield


@pytest.fixture
def room_entry(hass):
    entry = MockConfigEntry(
        domain=DOMAIN, title="Family Room", data=new_room("Family Room", "HUB1", 1)
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
def mqtt_entry(hass):
    entry = MockConfigEntry(domain="mqtt", data={"broker": "localhost"})
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
def transport():
    subscriptions = {}
    removed = []

    async def subscribe(hass, topic, callback, **kwargs):
        subscriptions[topic] = callback

        def unsubscribe():
            removed.append(topic)
            subscriptions.pop(topic, None)

        return unsubscribe

    with (
        patch(
            "homeassistant.components.mqtt.async_wait_for_mqtt_client", AsyncMock(return_value=True)
        ),
        patch("homeassistant.components.mqtt.async_subscribe", side_effect=subscribe),
    ):
        yield subscriptions, removed
