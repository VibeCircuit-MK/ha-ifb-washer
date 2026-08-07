"""Base entities for IFB Washer."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import IfbWasherCoordinator


class IfbWasherEntity(CoordinatorEntity[IfbWasherCoordinator]):
    """Base IFB washer entity."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: IfbWasherCoordinator, entry: ConfigEntry, key: str) -> None:
        super().__init__(coordinator)
        self.entry = entry
        self.key = key
        washer = entry.data["washer"]
        serial = washer.get("serial") or entry.unique_id or entry.entry_id
        self._attr_unique_id = f"{serial}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(serial))},
            manufacturer="IFB",
            model=washer.get("model"),
            name=washer.get("deviceName") or washer.get("model") or "IFB Washer",
            serial_number=str(serial),
            sw_version=washer.get("firmwareVersion"),
            hw_version=washer.get("firmwareVersionWifi"),
        )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return bool(self.coordinator.data and self.coordinator.data.get("available", True))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return shared state attributes."""
        data = self.coordinator.data or {}
        washer = self.entry.data.get("washer", {})
        return {
            "washer_model": washer.get("model"),
            "model_code": washer.get("modelCode"),
            "updated_at": data.get("updated_at"),
            "last_updated_at": data.get("last_updated_at"),
            "state": data.get("state"),
            "state_name": data.get("state_name"),
            "program_code": data.get("program_code"),
            "program_name": data.get("program_name"),
            "remaining_minutes": data.get("remaining_minutes"),
            "program_minutes": data.get("program_minutes"),
            "progress_percent": data.get("progress_percent"),
            "standby_flag": data.get("standby_flag"),
            "iot_function": data.get("iot_function"),
            "delay_start_minutes": data.get("delay_start_minutes"),
            "soak": data.get("soak"),
            "childlock": data.get("childlock"),
            "door": data.get("door"),
            "door_state": data.get("door_state"),
            "spin_speed": data.get("spin_speed"),
            "spin_speed_code": data.get("spin_speed_code"),
            "temperature": data.get("temperature"),
            "temperature_code": data.get("temperature_code"),
            "water_temperature": data.get("water_temperature"),
            "motor_speed_raw": data.get("motor_speed_raw"),
            "water_level_frequency_raw": data.get("water_level_frequency_raw"),
            "alarm1": data.get("alarm1"),
            "alarm2": data.get("alarm2"),
            "alarm3": data.get("alarm3"),
            "alarm4": data.get("alarm4"),
            "auto_dd_state_error": data.get("auto_dd_state_error"),
            "unbalance": data.get("unbalance"),
            "unbalance_fault": data.get("unbalance_fault"),
            "load_flag": data.get("load_flag"),
            "fault": data.get("fault"),
            "active_error_title": data.get("active_error_title"),
            "active_error_source": data.get("active_error_source"),
            "active_error_code": data.get("active_error_code"),
            "active_errors": data.get("active_errors"),
        }
