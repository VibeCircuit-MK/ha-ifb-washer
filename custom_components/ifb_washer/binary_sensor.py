"""Binary sensors for IFB Washer."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity, BinarySensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DATA_COORDINATOR, DOMAIN
from .coordinator import IfbWasherCoordinator
from .entity import IfbWasherEntity


@dataclass(frozen=True, kw_only=True)
class IfbBinarySensorDescription(BinarySensorEntityDescription):
    """IFB binary sensor description."""

    value_fn: Callable[[dict[str, Any]], bool | None]


BINARY_SENSORS: tuple[IfbBinarySensorDescription, ...] = (
    IfbBinarySensorDescription(
        key="online",
        translation_key="online",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        value_fn=lambda data: data.get("online"),
    ),
    IfbBinarySensorDescription(
        key="child_lock",
        translation_key="child_lock",
        device_class=BinarySensorDeviceClass.LOCK,
        value_fn=lambda data: bool(data.get("childlock")) if data.get("childlock") is not None else None,
    ),
    IfbBinarySensorDescription(
        key="running",
        translation_key="running",
        value_fn=lambda data: data.get("state") not in (None, 0, 1, 13, 14, 65, 118),
    ),
    IfbBinarySensorDescription(
        key="fault",
        translation_key="fault",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda data: bool(data.get("fault")),
    ),
    IfbBinarySensorDescription(
        key="unbalance",
        translation_key="unbalance",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: bool(data.get("unbalance_fault")),
    ),
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up IFB washer binary sensors."""
    coordinator: IfbWasherCoordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
    async_add_entities(IfbWasherBinarySensor(coordinator, entry, description) for description in BINARY_SENSORS)


class IfbWasherBinarySensor(IfbWasherEntity, BinarySensorEntity):
    """IFB washer binary sensor."""

    entity_description: IfbBinarySensorDescription

    def __init__(
        self,
        coordinator: IfbWasherCoordinator,
        entry: ConfigEntry,
        description: IfbBinarySensorDescription,
    ) -> None:
        super().__init__(coordinator, entry, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool | None:
        """Return native value."""
        if not self.coordinator.data:
            return None
        return self.entity_description.value_fn(self.coordinator.data)
