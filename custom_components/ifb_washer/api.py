"""API client for IFB Washer."""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import os
import time
import urllib.parse
from typing import Any

from aiohttp import ClientError, ClientResponseError

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    APPLIANCE_BASE,
    AUTH_BASE,
    CONF_OAUTH_CONSUMER_KEY,
    CONF_OAUTH_CONSUMER_SECRET,
    CONF_OAUTH_TOKEN,
    CONF_OAUTH_TOKEN_SECRET,
    DEFAULT_APP_CLIENT_ID,
    DEFAULT_MQTT_HOST,
    DEFAULT_MQTT_PORT,
    LOGIN_BASE,
    MODEL_PROGRAMS,
    SPIN_SPEED_OPTIONS,
    DOOR_STATES,
    STATE_NAMES,
    TEMPERATURE_OPTIONS,
)

_LOGGER = logging.getLogger(__name__)


class IfbApiError(Exception):
    """Raised when IFB API calls fail."""


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def new_pkce() -> dict[str, str]:
    """Create a PKCE verifier/challenge pair."""
    verifier = _b64url(os.urandom(64))
    challenge = _b64url(hashlib.sha256(verifier.encode("ascii")).digest())
    return {"code_verifier": verifier, "code_challenge": challenge}


def _oauth_quote(value: Any) -> str:
    return urllib.parse.quote(str(value), safe="~-._")


def _oauth1_header(method: str, url: str, credentials: dict[str, Any]) -> str:
    consumer_key = credentials.get(CONF_OAUTH_CONSUMER_KEY)
    consumer_secret = credentials.get(CONF_OAUTH_CONSUMER_SECRET)
    token = credentials.get(CONF_OAUTH_TOKEN)
    token_secret = credentials.get(CONF_OAUTH_TOKEN_SECRET)
    if not all((consumer_key, consumer_secret, token, token_secret)):
        raise IfbApiError("Missing IFB app OAuth signing values.")
    parsed = urllib.parse.urlsplit(url)
    base_url = urllib.parse.urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path or "/", "", ""))
    params: dict[str, str] = {
        "oauth_consumer_key": str(consumer_key),
        "oauth_nonce": str(int.from_bytes(os.urandom(8), "big", signed=False)),
        "oauth_signature_method": "HMAC-SHA256",
        "oauth_timestamp": str(int(time.time())),
        "oauth_token": str(token),
        "oauth_version": "1.0",
    }
    signing_pairs = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    signing_pairs.extend(params.items())
    signing_pairs.sort(key=lambda item: (_oauth_quote(item[0]), _oauth_quote(item[1])))
    param_string = "&".join(f"{_oauth_quote(key)}={_oauth_quote(value)}" for key, value in signing_pairs)
    base_string = "&".join([method.upper(), _oauth_quote(base_url), _oauth_quote(param_string)])
    key = f"{_oauth_quote(consumer_secret)}&{_oauth_quote(token_secret)}"
    digest = hmac.new(key.encode(), base_string.encode(), hashlib.sha256).digest()
    params["oauth_signature"] = base64.b64encode(digest).decode("ascii").strip()
    return "OAuth " + ", ".join(f'{_oauth_quote(key)}="{_oauth_quote(value)}"' for key, value in sorted(params.items()))


def find_first_key(data: Any, keys: tuple[str, ...]) -> str | None:
    """Find the first matching key recursively."""
    lowered = {key.lower() for key in keys}
    if isinstance(data, dict):
        for key, value in data.items():
            if key in keys or key.lower() in lowered:
                if value not in (None, ""):
                    return str(value)
        for value in data.values():
            found = find_first_key(value, keys)
            if found:
                return found
    elif isinstance(data, list):
        for value in data:
            found = find_first_key(value, keys)
            if found:
                return found
    return None


def decode_progress(response: Any) -> dict[str, Any]:
    """Decode IFB progress response into entity-friendly data."""
    item: dict[str, Any] | None = None
    if isinstance(response, dict):
        data = response.get("data")
        if isinstance(data, list) and data and isinstance(data[0], dict):
            item = data[0]
        elif isinstance(data, dict):
            item = data
    if not item:
        return {"available": False}

    state = item.get("state")
    balance_high = int(item.get("balanceTimeHighByte") or 0)
    balance_low = int(item.get("balanceTimeLowByte") or 0)
    program_high = int(item.get("programTimeHighByte") or 0)
    program_low = int(item.get("programTimeLowByte") or 0)
    program_code = _as_int(item.get("programCode") or item.get("programCodeTL"))
    remaining = balance_high * 60 + balance_low
    program = program_high * 60 + program_low
    running_state = state not in (None, 0, 1, 13, 14, 65, 118)
    if state == 13:
        remaining = 0
        program = 0
    elif state in (1, 65, 118) and remaining == 0:
        program = 0
    progress = round(((program - remaining) / program) * 100) if program > 0 else (100 if state == 13 else 0)
    if not running_state and state != 13:
        progress = 0
    return {
        "available": True,
        "source": "rest",
        "serial": item.get("serial"),
        "status": item.get("status"),
        "online": item.get("status") == "Online",
        "state": state,
        "state_name": STATE_NAMES.get(state, f"unknown_{state}"),
        "program_code": program_code,
        "program_name": program_name(item.get("modelCode"), program_code),
        "remaining_minutes": remaining,
        "program_minutes": program,
        "progress_percent": progress,
        "childlock": item.get("childlockWasher"),
        "last_updated_at": item.get("lastUpdatedAt"),
    }


def _as_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def program_name(model_code: Any, program_code: int | None) -> str | None:
    """Return the IFB app program name for a model/program code pair."""
    if program_code is None:
        return None
    programs = MODEL_PROGRAMS.get(str(model_code or ""))
    if not programs:
        programs = next(iter(MODEL_PROGRAMS.values()))
    return programs.get(program_code) or f"Program {program_code}"


def option_name(options: dict[int, str], code: int | None) -> str | None:
    """Return an option label for an observed washer option code."""
    if code is None:
        return None
    return options.get(code) or f"Code {code}"


def door_state_name(code: int | None) -> str | None:
    """Return an IFB app door state label."""
    if code is None:
        return None
    return DOOR_STATES.get(code) or f"Code {code}"


ALARM1_ERRORS = {
    1: "Door Error",
    2: "Triac Short",
    4: "Unknown Error",
    8: "Motor Failure",
    16: "Water Overflow",
    32: "Over Heat",
    64: "Pressure Switch Failure",
    128: "Door Error",
}

ALARM2_ERRORS = {
    1: "No Water / Low water Pressure",
    2: "No Water / Low water Pressure",
    4: "Heating Error",
    8: "Temperature Sensor Error",
    16: "Drain Pump Failure",
    32: "Low Voltage",
    64: "High Voltage",
    128: "Unbalance Error",
}

ALARM3_ERRORS = {
    1: "Blocked rotor error",
    2: "Clothes not drying - Dryer Sensor fault",
    4: "Dryer Fan Fault",
    8: "Motor over current",
    16: "IPM overheat",
    32: "Power board communication error",
    64: "Hot",
    128: "Clothes not drying - Dryer Heater Fault",
}

ALARM4_ERRORS = {
    1: "Clothes not drying - Drying Sensor Fault",
}

AUTO_DD_ERRORS = {
    1: "Softener Low",
    2: "Detergent Low",
    3: "DD Tray not closed",
    4: "Detergent dispensing Pump error (AD1)",
    5: "Softener dispensing Pump error (AD2)",
}


def decode_washer_errors(
    alarm1: int | None,
    alarm2: int | None,
    alarm3: int | None,
    alarm4: int | None = None,
    auto_dd_state_error: int | None = None,
) -> list[dict[str, Any]]:
    """Return MyIFB front-load washer errors decoded from alarm bytes."""
    decoded: list[dict[str, Any]] = []
    for source, value, mapping in (
        ("alarm1", alarm1, ALARM1_ERRORS),
        ("alarm2", alarm2, ALARM2_ERRORS),
        ("alarm3", alarm3, ALARM3_ERRORS),
        ("alarm4", alarm4, ALARM4_ERRORS),
        ("auto_dd_state_error", auto_dd_state_error, AUTO_DD_ERRORS),
    ):
        if value in (None, 0):
            continue
        decoded.append(
            {
                "source": source,
                "code": value,
                "title": mapping.get(value, "Unknown Error"),
            }
        )
    return decoded


def decode_mqtt_payload(payload: bytes, model_code: Any = None) -> dict[str, Any]:
    """Decode observed washer MQTT status frame."""
    data: dict[str, Any] = {
        "available": True,
        "source": "mqtt",
    }
    if len(payload) < 36:
        data["state_name"] = "unknown"
        return data
    state = payload[30]
    program_code = payload[6]
    iot_function = payload[7]
    spin_speed_code = payload[8]
    temperature_code = payload[10]
    remaining = payload[17] * 60 + payload[18]
    program = payload[32] * 60 + payload[33]
    door_code = payload[35]
    alarm3 = payload[24]
    unbalance = payload[25]
    alarm1 = payload[26]
    alarm2 = payload[27]
    auto_dd_state_error = payload[38] if len(payload) > 38 else None
    alarm4 = payload[41] if len(payload) > 41 else None
    active_errors = decode_washer_errors(alarm1, alarm2, alarm3, alarm4, auto_dd_state_error)
    active_error = active_errors[0] if active_errors else None
    running_state = state not in (None, 0, 1, 13, 14, 65, 118)
    if state == 13:
        remaining = 0
        program = 0
    elif not running_state and state not in (0, 14):
        remaining = 0
        program = 0
    progress = round(((program - remaining) / program) * 100) if program > 0 else (100 if state == 13 else 0)
    data.update(
        {
            "appliance_type_code": payload[4],
            "user_control": payload[5],
            "state": state,
            "state_name": STATE_NAMES.get(state, f"unknown_{state}"),
            "program_code": program_code,
            "program_name": program_name(model_code, program_code),
            "iot_function": iot_function,
            "standby_flag": bool(iot_function & 64),
            "spin_speed_code": spin_speed_code,
            "spin_speed": option_name(SPIN_SPEED_OPTIONS, spin_speed_code),
            "extra_rinse": payload[9],
            "temperature_code": temperature_code,
            "temperature": option_name(TEMPERATURE_OPTIONS, temperature_code),
            "option2": payload[11],
            "delay_start_high": payload[12],
            "delay_start_low": payload[13],
            "delay_start_minutes": payload[12] * 60 + payload[13],
            "soak": payload[14],
            "childlock": payload[15],
            "group_code": payload[16],
            "balance_time_high": payload[17],
            "balance_time_low": payload[18],
            "motor_speed_high": payload[19],
            "motor_speed_low": payload[20],
            "motor_speed_raw": (payload[19] << 8) + payload[20],
            "water_temperature": payload[21],
            "water_level_frequency_high": payload[22],
            "water_level_frequency_low": payload[23],
            "water_level_frequency_raw": (payload[22] << 8) + payload[23],
            "alarm3": alarm3,
            "unbalance": unbalance,
            "alarm1": alarm1,
            "alarm2": alarm2,
            "dryer_options": payload[28],
            "option_enable1": payload[29],
            "load_flag": payload[31],
            "program_time_high": payload[32],
            "program_time_low": payload[33],
            "smart_model_type": payload[34],
            "door": door_code,
            "door_state": door_state_name(door_code),
            "remaining_minutes": remaining,
            "program_minutes": program,
            "progress_percent": progress,
            "alarm4": alarm4,
            "auto_dd_state_error": auto_dd_state_error,
            "active_errors": active_errors,
            "active_error_title": active_error["title"] if active_error else None,
            "active_error_source": active_error["source"] if active_error else None,
            "active_error_code": active_error["code"] if active_error else None,
            "fault": bool(active_errors),
            "unbalance_fault": alarm2 == 128,
            "online": True,
            "status": "Online",
        }
    )
    return data


def choose_washer(devices: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Choose the best Wi-Fi washer from device/all."""
    washers = [device for device in devices if device.get("applianceType") == "WASHING_MACHINE"]
    if not washers:
        return None

    def score(device: dict[str, Any]) -> tuple[int, int, int, int]:
        return (
            1 if device.get("connectivity") == "WiFi" else 0,
            1 if device.get("status") == "Online" else 0,
            1 if device.get("isPrimary") else 0,
            1 if device.get("mac") else 0,
        )

    return sorted(washers, key=score, reverse=True)[0]


class IfbApiClient:
    """Small async client for the IFB cloud APIs."""

    def __init__(self, hass: HomeAssistant, data: dict[str, Any]) -> None:
        self.hass = hass
        self.data = data
        self._session = async_get_clientsession(hass)

    async def _post(
        self,
        base_url: str,
        path: str,
        body: dict[str, Any] | None = None,
        token: str | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> Any:
        url = base_url.rstrip("/") + "/" + path.lstrip("/")
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json; charset=utf-8",
            "x-channel-key": "mobile",
            "User-Agent": "okhttp/4.12.0 HomeAssistant-IFBWasher/0.1",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        if extra_headers:
            headers.update(extra_headers)
        try:
            async with self._session.post(url, json=body or {}, headers=headers, timeout=30) as response:
                text = await response.text()
                if response.status >= 400:
                    raise IfbApiError(f"{response.status}: {text[:300]}")
                if not text:
                    return {}
                return await response.json(content_type=None)
        except (ClientError, ClientResponseError) as err:
            raise IfbApiError(str(err)) from err

    async def _signed_post(self, path: str, body: dict[str, Any]) -> Any:
        url = LOGIN_BASE.rstrip("/") + "/" + path.lstrip("/")
        return await self._post(
            LOGIN_BASE,
            path,
            body,
            extra_headers={"Authorization": _oauth1_header("POST", url, self.data)},
        )

    async def request_otp(self, identifier: str, login_type: str, calling_code: str) -> dict[str, Any]:
        """Request an OTP."""
        body = {"method": "mailotp" if login_type == "email" else "phone", "calling_code": calling_code}
        if login_type == "email":
            body["username"] = identifier
        else:
            body["phonenumber"] = identifier
        pkce = new_pkce()
        response = await self._signed_post("rest/V1/restapi/login", body)
        return {"response": response, **pkce}

    async def verify_otp(
        self,
        identifier: str,
        login_type: str,
        calling_code: str,
        otp: str,
        code_challenge: str,
    ) -> Any:
        """Verify OTP and receive cloud authorization data."""
        body = {
            "method": "mail" if login_type == "email" else "phone",
            "otp": otp,
            "calling_code": calling_code,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
            "base_version": 2,
        }
        if login_type == "email":
            body["username"] = identifier
        else:
            body["phonenumber"] = identifier
        return await self._signed_post("rest/V1/restapi/otpverify", body)

    async def exchange_token(self, verify_response: Any, code_verifier: str) -> dict[str, Any]:
        """Exchange cloud authorization code for access and refresh tokens."""
        code = find_first_key(verify_response, ("code", "authorization_code"))
        client_id = find_first_key(verify_response, ("clientId", "client_id")) or DEFAULT_APP_CLIENT_ID
        if not code or not client_id:
            raise IfbApiError("OTP verified, but no authorization code/client_id was returned.")
        body = {
            "code_verifier": code_verifier,
            "code": code,
            "client_id": client_id,
            "grant_type": "authorization_code",
        }
        token_response = await self._post(AUTH_BASE, "auth/token", body)
        access_token = find_first_key(token_response, ("accessToken", "access_token", "token_val"))
        refresh_token = find_first_key(token_response, ("refreshToken", "refresh_token"))
        expires_in = find_first_key(token_response, ("expiresIn", "expires_in"))
        if not access_token:
            raise IfbApiError("Token exchange succeeded, but no access token was returned.")
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "expires_in": int(expires_in or 0),
            "client_id": client_id,
            "token_response": token_response,
        }

    async def refresh_access_token(self) -> dict[str, Any] | None:
        """Refresh the access token when possible."""
        refresh_token = self.data.get("refresh_token")
        client_id = self.data.get("client_id") or DEFAULT_APP_CLIENT_ID
        if not refresh_token:
            return None
        body = {"refresh_token": refresh_token, "client_id": client_id, "grant_type": "refresh_token"}
        response = await self._post(AUTH_BASE, "auth/token", body)
        access_token = find_first_key(response, ("accessToken", "access_token", "token_val"))
        new_refresh = find_first_key(response, ("refreshToken", "refresh_token")) or refresh_token
        expires_in = find_first_key(response, ("expiresIn", "expires_in"))
        if not access_token:
            return None
        self.data.update({"access_token": access_token, "refresh_token": new_refresh, "expires_in": int(expires_in or 0)})
        return dict(self.data)

    async def cloud_post(self, path: str, body: dict[str, Any] | None = None) -> Any:
        """Call IFB appliance API with current bearer token."""
        token = self.data.get("access_token")
        if not token:
            raise IfbApiError("No access token available.")
        try:
            return await self._post(APPLIANCE_BASE, path, body, token=token)
        except IfbApiError as err:
            if not str(err).startswith("401"):
                raise
            if await self.refresh_access_token():
                return await self._post(APPLIANCE_BASE, path, body, token=self.data["access_token"])
            raise

    async def discover(self) -> dict[str, Any]:
        """Discover washer and MQTT settings."""
        device_all = await self.cloud_post("device/all")
        devices = device_all.get("data", []) if isinstance(device_all, dict) else []
        washer = choose_washer([device for device in devices if isinstance(device, dict)])
        if not washer:
            raise IfbApiError("No Wi-Fi washing machine found on this IFB account.")
        mqtt_response = await self.cloud_post("config/update/mqttClient")
        mqtt_client_id = find_first_key(mqtt_response, ("clientID", "clientId", "client_id"))
        if not mqtt_client_id:
            raise IfbApiError("No MQTT client ID returned.")
        progress = await self.cloud_post("device/smart/progress")
        return {
            "washer": washer,
            "mqtt_client_id": mqtt_client_id,
            "mqtt_host": DEFAULT_MQTT_HOST,
            "mqtt_port": DEFAULT_MQTT_PORT,
            "progress": decode_progress(progress),
        }

    async def get_progress(self) -> dict[str, Any]:
        """Read washer progress via REST."""
        return decode_progress(await self.cloud_post("device/smart/progress"))
