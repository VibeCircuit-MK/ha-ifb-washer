"""Select entities for IFB Washer."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DATA_COORDINATOR, DATA_MQTT, DOMAIN, MODEL_PROGRAM_DURATIONS, MODEL_PROGRAMS
from .coordinator import IfbWasherCoordinator, IfbWasherMqttClient
from .entity import IfbWasherEntity


def _format_time(minutes: int | None) -> str:
    if not minutes:
        return "--:--"
    hours = minutes // 60
    mins = minutes % 60
    return f"{hours}:{mins:02d}"


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up IFB washer select entities."""
    coordinator: IfbWasherCoordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
    async_add_entities([IfbWasherProgramSelect(coordinator, entry)])


class IfbWasherProgramSelect(IfbWasherEntity, SelectEntity):
    """Program selector for IFB washer."""

    _attr_icon = "mdi:washing-machine"
    _attr_translation_key = "program_select"

    def __init__(self, coordinator: IfbWasherCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "program_select")
        model_code = str(entry.data["washer"].get("modelCode") or "")
        self._programs = MODEL_PROGRAMS.get(model_code) or next(iter(MODEL_PROGRAMS.values()))
        self._durations = MODEL_PROGRAM_DURATIONS.get(model_code, {})
        self._option_to_code = {
            self._option_label(code, name): code for code, name in sorted(self._programs.items())
        }
        self._code_to_option = {code: option for option, code in self._option_to_code.items()}

    def _option_label(self, code: int, name: str) -> str:
        return f"{name} ({_format_time(self._durations.get(code))})"

    @property
    def options(self) -> list[str]:
        """Return available programs."""
        return list(self._option_to_code)

    @property
    def current_option(self) -> str | None:
        """Return currently selected program."""
        data = self.coordinator.data or {}
        code = data.get("program_code")
        if code in self._code_to_option:
            return self._code_to_option[code]
        return None

    async def async_select_option(self, option: str) -> None:
        """Select a washer program."""
        program_code = self._option_to_code[option]
        mqtt_client: IfbWasherMqttClient = self.coordinator.hass.data[DOMAIN][self.entry.entry_id][DATA_MQTT]
        await mqtt_client.async_select_program(program_code)
        merged = dict(self.coordinator.data or {})
        merged.update(
            {
                "program_code": program_code,
                "program_name": self._programs.get(program_code),
                "program_minutes": self._durations.get(program_code, 0),
                "state": 0,
                "state_name": "selected",
            }
        )
        self.coordinator.async_set_updated_data(merged)
