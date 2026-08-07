"""Button entities for IFB Washer commands."""

from __future__ import annotations

from dataclasses import dataclass
from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DATA_COORDINATOR, DATA_MQTT
from .coordinator import IfbWasherCoordinator, IfbWasherMqttClient
from .entity import IfbWasherEntity


@dataclass(frozen=True, kw_only=True)
class IfbWasherButtonDescription(ButtonEntityDescription):
    """Describe an IFB washer button."""

    command: str


BUTTONS: tuple[IfbWasherButtonDescription, ...] = (
    IfbWasherButtonDescription(key="turn_on", translation_key="turn_on", icon="mdi:power", command="turn_on"),
    IfbWasherButtonDescription(key="start", translation_key="start", icon="mdi:play", command="start"),
    IfbWasherButtonDescription(key="pause", translation_key="pause", icon="mdi:pause", command="pause"),
    IfbWasherButtonDescription(key="cancel", translation_key="cancel", icon="mdi:cancel", command="cancel"),
    IfbWasherButtonDescription(key="turn_off", translation_key="turn_off", icon="mdi:power", command="turn_off"),
    IfbWasherButtonDescription(
        key="child_lock_on",
        translation_key="child_lock_on",
        icon="mdi:lock",
        command="child_lock_on",
        entity_category=EntityCategory.CONFIG,
    ),
    IfbWasherButtonDescription(
        key="child_lock_off",
        translation_key="child_lock_off",
        icon="mdi:lock-open-variant",
        command="child_lock_off",
        entity_category=EntityCategory.CONFIG,
    ),
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up IFB washer buttons."""
    coordinator: IfbWasherCoordinator = hass.data[entry.domain][entry.entry_id][DATA_COORDINATOR]
    async_add_entities(IfbWasherButton(coordinator, entry, description) for description in BUTTONS)


class IfbWasherButton(IfbWasherEntity, ButtonEntity):
    """IFB washer command button."""

    entity_description: IfbWasherButtonDescription

    def __init__(
        self,
        coordinator: IfbWasherCoordinator,
        entry: ConfigEntry,
        description: IfbWasherButtonDescription,
    ) -> None:
        super().__init__(coordinator, entry, description.key)
        self.entity_description = description

    @property
    def available(self) -> bool:
        """Return if command publishing is available."""
        return super().available and self.entry.entry_id in self.hass.data[self.entry.domain]

    async def async_press(self) -> None:
        """Send the command over MQTT."""
        mqtt_client: IfbWasherMqttClient | None = self.hass.data[self.entry.domain][self.entry.entry_id].get(DATA_MQTT)
        if mqtt_client is None:
            return
        await mqtt_client.async_send_command(self.entity_description.command)
