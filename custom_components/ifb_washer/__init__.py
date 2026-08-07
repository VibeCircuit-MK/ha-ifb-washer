"""IFB Washer integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .api import IfbApiClient
from .const import DATA_CLIENT, DATA_COORDINATOR, DATA_MQTT, DOMAIN, PLATFORMS
from .coordinator import IfbWasherCoordinator, IfbWasherMqttClient


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up IFB Washer from a config entry."""
    client = IfbApiClient(hass, dict(entry.data))
    coordinator = IfbWasherCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()

    mqtt_client = IfbWasherMqttClient(hass, entry, client, coordinator)
    await mqtt_client.async_start()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        DATA_CLIENT: client,
        DATA_COORDINATOR: coordinator,
        DATA_MQTT: mqtt_client,
    }
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload IFB Washer."""
    data = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if data and (mqtt_client := data.get(DATA_MQTT)):
        await mqtt_client.async_stop()

    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unloaded
