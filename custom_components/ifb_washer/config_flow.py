"""Config flow for IFB Washer."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import IfbApiClient, IfbApiError
from .const import (
    CONF_CALLING_CODE,
    CONF_IDENTIFIER,
    CONF_LOGIN_TYPE,
    CONF_OAUTH_CONSUMER_KEY,
    CONF_OAUTH_CONSUMER_SECRET,
    CONF_OAUTH_TOKEN,
    CONF_OAUTH_TOKEN_SECRET,
    DEFAULT_CALLING_CODE,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


LOGIN_TYPES = {"phone": "Phone", "email": "Email"}


class IfbWasherConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle an IFB Washer config flow."""

    VERSION = 1

    def __init__(self) -> None:
        self._identifier: str | None = None
        self._login_type: str = "phone"
        self._calling_code: str = DEFAULT_CALLING_CODE
        self._oauth_credentials: dict[str, str] = {}
        self._code_verifier: str | None = None
        self._code_challenge: str | None = None

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> config_entries.FlowResult:
        """Ask for the mobile/email and request OTP."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._identifier = user_input[CONF_IDENTIFIER].strip()
            self._login_type = user_input[CONF_LOGIN_TYPE]
            self._calling_code = user_input.get(CONF_CALLING_CODE, DEFAULT_CALLING_CODE).strip() or DEFAULT_CALLING_CODE
            self._oauth_credentials = {
                CONF_OAUTH_CONSUMER_KEY: user_input[CONF_OAUTH_CONSUMER_KEY].strip(),
                CONF_OAUTH_CONSUMER_SECRET: user_input[CONF_OAUTH_CONSUMER_SECRET].strip(),
                CONF_OAUTH_TOKEN: user_input[CONF_OAUTH_TOKEN].strip(),
                CONF_OAUTH_TOKEN_SECRET: user_input[CONF_OAUTH_TOKEN_SECRET].strip(),
            }
            client = IfbApiClient(self.hass, dict(self._oauth_credentials))
            try:
                result = await client.request_otp(self._identifier, self._login_type, self._calling_code)
            except IfbApiError:
                _LOGGER.exception("Failed requesting IFB OTP")
                errors["base"] = "cannot_connect"
            else:
                self._code_verifier = result["code_verifier"]
                self._code_challenge = result["code_challenge"]
                return await self.async_step_otp()

        schema = vol.Schema(
            {
                vol.Required(CONF_IDENTIFIER): str,
                vol.Required(CONF_LOGIN_TYPE, default="phone"): vol.In(LOGIN_TYPES),
                vol.Required(CONF_CALLING_CODE, default=DEFAULT_CALLING_CODE): str,
                vol.Required(CONF_OAUTH_CONSUMER_KEY): str,
                vol.Required(CONF_OAUTH_CONSUMER_SECRET): str,
                vol.Required(CONF_OAUTH_TOKEN): str,
                vol.Required(CONF_OAUTH_TOKEN_SECRET): str,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_otp(self, user_input: dict[str, Any] | None = None) -> config_entries.FlowResult:
        """Verify OTP, exchange token, and discover the washer."""
        errors: dict[str, str] = {}
        if user_input is not None:
            assert self._identifier is not None
            assert self._code_verifier is not None
            assert self._code_challenge is not None
            client = IfbApiClient(self.hass, dict(self._oauth_credentials))
            try:
                verify_response = await client.verify_otp(
                    self._identifier,
                    self._login_type,
                    self._calling_code,
                    user_input["otp"].strip(),
                    self._code_challenge,
                )
                token_data = await client.exchange_token(verify_response, self._code_verifier)
                client.data.update(token_data)
                discovery = await client.discover()
            except IfbApiError as err:
                _LOGGER.warning("IFB login/discovery failed: %s", err)
                errors["base"] = "invalid_auth"
            else:
                washer = discovery["washer"]
                serial = washer.get("serial") or self._identifier
                await self.async_set_unique_id(str(serial))
                self._abort_if_unique_id_configured(
                    updates={
                        "access_token": token_data["access_token"],
                        "refresh_token": token_data.get("refresh_token"),
                        "client_id": token_data.get("client_id"),
                        "mqtt_client_id": discovery["mqtt_client_id"],
                        "mqtt_host": discovery["mqtt_host"],
                        "mqtt_port": discovery["mqtt_port"],
                        "washer": washer,
                        **self._oauth_credentials,
                    }
                )
                return self.async_create_entry(
                    title=washer.get("deviceName") or washer.get("model") or "IFB Washer",
                    data={
                        CONF_IDENTIFIER: self._identifier,
                        CONF_LOGIN_TYPE: self._login_type,
                        CONF_CALLING_CODE: self._calling_code,
                        "access_token": token_data["access_token"],
                        "refresh_token": token_data.get("refresh_token"),
                        "client_id": token_data.get("client_id"),
                        "mqtt_client_id": discovery["mqtt_client_id"],
                        "mqtt_host": discovery["mqtt_host"],
                        "mqtt_port": discovery["mqtt_port"],
                        "washer": washer,
                        **self._oauth_credentials,
                    },
                )

        return self.async_show_form(
            step_id="otp",
            data_schema=vol.Schema({vol.Required("otp"): str}),
            errors=errors,
            description_placeholders={"identifier": self._identifier or ""},
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> config_entries.OptionsFlow:
        """No options yet."""
        return IfbWasherOptionsFlow()


class IfbWasherOptionsFlow(config_entries.OptionsFlow):
    """Placeholder options flow."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> config_entries.FlowResult:
        return self.async_create_entry(title="", data={})
