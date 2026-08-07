"""Sensors for IFB Washer."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorEntityDescription, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, PERCENTAGE, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DATA_COORDINATOR, DOMAIN
from .coordinator import IfbWasherCoordinator
from .entity import IfbWasherEntity


@dataclass(frozen=True, kw_only=True)
class IfbSensorDescription(SensorEntityDescription):
    """IFB sensor description."""

    value_fn: Callable[[dict[str, Any]], Any]


SENSORS: tuple[IfbSensorDescription, ...] = (
    IfbSensorDescription(
        key="phase",
        translation_key="phase",
        value_fn=lambda data: data.get("state_name"),
    ),
    IfbSensorDescription(
        key="fault",
        translation_key="fault",
        value_fn=lambda data: data.get("active_error_title") or "No fault",
    ),
    IfbSensorDescription(
        key="program",
        translation_key="program",
        value_fn=lambda data: data.get("program_name"),
    ),
    IfbSensorDescription(
        key="spin_speed",
        translation_key="spin_speed",
        value_fn=lambda data: data.get("spin_speed"),
    ),
    IfbSensorDescription(
        key="temperature",
        translation_key="temperature",
        value_fn=lambda data: data.get("temperature"),
    ),
    IfbSensorDescription(
        key="door",
        translation_key="door",
        value_fn=lambda data: data.get("door_state"),
    ),
    IfbSensorDescription(
        key="remaining_time",
        translation_key="remaining_time",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.get("remaining_minutes"),
    ),
    IfbSensorDescription(
        key="program_time",
        translation_key="program_time",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.get("program_minutes"),
    ),
    IfbSensorDescription(
        key="progress",
        translation_key="progress",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.get("progress_percent"),
    ),
    IfbSensorDescription(
        key="raw_state",
        translation_key="raw_state",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.get("state"),
    ),
    IfbSensorDescription(
        key="load",
        translation_key="load",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.get("load_flag"),
    ),
    IfbSensorDescription(
        key="unbalance",
        translation_key="unbalance",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.get("unbalance"),
    ),
    IfbSensorDescription(
        key="water_temperature",
        translation_key="water_temperature",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.get("water_temperature"),
    ),
    IfbSensorDescription(
        key="motor_speed_raw",
        translation_key="motor_speed_raw",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.get("motor_speed_raw"),
    ),
    IfbSensorDescription(
        key="alarm1",
        translation_key="alarm1",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.get("alarm1"),
    ),
    IfbSensorDescription(
        key="alarm2",
        translation_key="alarm2",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.get("alarm2"),
    ),
    IfbSensorDescription(
        key="alarm3",
        translation_key="alarm3",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.get("alarm3"),
    ),
    IfbSensorDescription(
        key="alarm4",
        translation_key="alarm4",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.get("alarm4"),
    ),
    IfbSensorDescription(
        key="auto_dd_state_error",
        translation_key="auto_dd_state_error",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.get("auto_dd_state_error"),
    ),
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up IFB washer sensors."""
    coordinator: IfbWasherCoordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
    async_add_entities(IfbWasherSensor(coordinator, entry, description) for description in SENSORS)


class IfbWasherSensor(IfbWasherEntity, SensorEntity):
    """IFB washer sensor."""

    entity_description: IfbSensorDescription

    def __init__(self, coordinator: IfbWasherCoordinator, entry: ConfigEntry, description: IfbSensorDescription) -> None:
        super().__init__(coordinator, entry, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> Any:
        """Return native value."""
        if not self.coordinator.data:
            return None
        return self.entity_description.value_fn(self.coordinator.data)
