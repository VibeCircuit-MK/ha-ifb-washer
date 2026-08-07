"""Coordinator and MQTT bridge for IFB Washer."""

from __future__ import annotations

import logging
import ssl
from datetime import datetime
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import IfbApiClient, IfbApiError, decode_mqtt_payload
from .command import build_fixed_command, build_program_command
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class IfbWasherCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinate IFB washer state."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, client: IfbApiClient) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{entry.entry_id}",
            update_interval=DEFAULT_SCAN_INTERVAL,
        )
        self.entry = entry
        self.client = client

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            data = await self.client.get_progress()
        except IfbApiError as err:
            raise UpdateFailed(str(err)) from err
        merged = dict(self.data or {})
        merged.update(data)
        data = merged
        data["updated_at"] = datetime.now().isoformat(timespec="seconds")
        return data

    def apply_mqtt_update(self, data: dict[str, Any]) -> None:
        """Push MQTT state into coordinator data."""
        merged = dict(self.data or {})
        merged.update(data)
        merged["updated_at"] = datetime.now().isoformat(timespec="seconds")
        self.async_set_updated_data(merged)


class IfbWasherMqttClient:
    """Small paho-mqtt bridge feeding Home Assistant coordinator."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: IfbApiClient,
        coordinator: IfbWasherCoordinator,
    ) -> None:
        self.hass = hass
        self.entry = entry
        self.client = client
        self.coordinator = coordinator
        self._mqtt: Any | None = None
        self._started = False

    async def async_start(self) -> None:
        """Start MQTT listener in a paho background thread."""
        if self._started:
            return
        await self.hass.async_add_executor_job(self._start)
        self._started = True

    def _start(self) -> None:
        import paho.mqtt.client as mqtt

        washer = self.entry.data["washer"]
        topic_id = washer.get("mac") or washer.get("serial")
        serial = washer.get("serial")
        token = self.client.data.get("access_token")
        mqtt_client_id = self.entry.data.get("mqtt_client_id")
        if not topic_id or not serial or not token or not mqtt_client_id:
            _LOGGER.warning("Missing MQTT settings; IFB Washer will use REST polling only")
            return

        response_topic = f"Response/{topic_id}"

        def on_connect(mqtt_client: Any, userdata: Any, flags: Any, rc: int, properties: Any = None) -> None:
            if rc != 0:
                _LOGGER.warning("IFB MQTT connect failed with rc=%s", rc)
                return
            mqtt_client.subscribe(response_topic)
            _LOGGER.debug("Subscribed to IFB MQTT topic %s", response_topic)

        def on_message(mqtt_client: Any, userdata: Any, message: Any) -> None:
            decoded = decode_mqtt_payload(bytes(message.payload), self.client.data.get("washer", {}).get("modelCode"))
            self.hass.loop.call_soon_threadsafe(self.coordinator.apply_mqtt_update, decoded)

        mqttc = mqtt.Client(client_id=mqtt_client_id, protocol=mqtt.MQTTv311)
        mqttc.username_pw_set(serial, token)
        mqttc.tls_set(cert_reqs=ssl.CERT_NONE)
        mqttc.tls_insecure_set(True)
        mqttc.on_connect = on_connect
        mqttc.on_message = on_message
        mqttc.connect(self.entry.data.get("mqtt_host", "mqtt2.ifbcloud.in"), int(self.entry.data.get("mqtt_port", 8883)), keepalive=30)
        mqttc.loop_start()
        self._mqtt = mqttc

    async def async_select_program(self, program_code: int) -> None:
        """Publish a program selection command."""
        payload = build_program_command(program_code)
        await self.hass.async_add_executor_job(self._publish_command, payload)

    async def async_send_command(self, command: str) -> None:
        """Publish a fixed washer command."""
        payload = build_fixed_command(command)
        await self.hass.async_add_executor_job(self._publish_command, payload)

    def _publish_command(self, payload: bytes) -> None:
        if not self._mqtt:
            raise IfbApiError("MQTT is not connected.")
        washer = self.entry.data["washer"]
        topic_id = washer.get("mac") or washer.get("serial")
        if not topic_id:
            raise IfbApiError("No washer MQTT topic id available.")
        result = self._mqtt.publish(f"Command/{topic_id}", payload, qos=0)
        if getattr(result, "rc", 0) != 0:
            raise IfbApiError(f"MQTT publish failed rc={result.rc}")

    async def async_stop(self) -> None:
        """Stop MQTT listener."""
        if not self._mqtt:
            return
        mqttc = self._mqtt
        self._mqtt = None
        self._started = False
        await self.hass.async_add_executor_job(self._stop, mqttc)

    @staticmethod
    def _stop(mqttc: Any) -> None:
        mqttc.loop_stop()
        mqttc.disconnect()
