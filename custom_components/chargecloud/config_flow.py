"""Config flow for chargecloud integration."""
from __future__ import annotations

import logging
import re
from typing import Any

import chargecloudapi
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required("evse_id"): str,
    }
)


def evse_id(value: str) -> str:
    """Verify evse_id is syntactically correct."""
    match = re.fullmatch(
        r"^(([A-Z]{2}\*?[A-Z0-9]{3}\*?E[A-Z0-9\*]{1,30})|(\+?[0-9]{1,3}\*[0-9]{3}\*[0-9\*]{1,32}))$",
        value,
    )
    if match is None:
        raise vol.Invalid(message="malformed evse-id")
    return value


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    try:
        evse_id(data["evse_id"])
    except vol.Invalid as exc:
        raise MalformedEvseId() from exc

    api = chargecloudapi.Api(websession=async_get_clientsession(hass))
    try:
        location, _ = await api.perform_smart_api_call(data["evse_id"], None)
    except Exception as exc:
        _LOGGER.exception(f"validate_info failed", exc)
        raise CannotConnect(exc) from exc

    if not location:
        raise EmptyResponse()

    if location.evses[0].id != data["evse_id"]:
        data["evse_id"] = location.evses[0].id

    return data


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for chargecloud."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        errors = {}
        if await self.is_duplicate(user_input):
            return self.async_abort(reason="already_configured")

        try:
            user_input = await validate_input(self.hass, user_input)
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except MalformedEvseId:
            errors["evse_id"] = "malformed_evse_id"
        except EmptyResponse:
            errors["base"] = "empty_response"
        except FoundDifferentEvseId as instead:
            errors["base"] = "found_different_evse"
            user_input["evse_id"] = instead.instead
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            if await self.is_duplicate(user_input):
                return self.async_abort(reason="already_configured")
            return self.async_create_entry(title=user_input["evse_id"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def is_duplicate(self, user_input) -> bool:
        """Check if current device is already configured."""
        for other_evse in self._async_current_entries():
            if other_evse.data["evse_id"] == user_input["evse_id"]:
                return True
        return False


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class EmptyResponse(HomeAssistantError):
    """Error to indicate we didn't find the evse."""


class MalformedEvseId(HomeAssistantError):
    """Error to indicate a syntactically wrong evse-id."""
