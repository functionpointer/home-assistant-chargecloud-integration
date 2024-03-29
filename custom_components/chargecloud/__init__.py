"""The chargecloud integration."""
from __future__ import annotations

import logging

import async_timeout
import chargecloudapi

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, UPDATE_INTERVAL, EvseId
import traceback
_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up chargecloud from a config entry."""

    hass.data.setdefault(DOMAIN, {})

    api = chargecloudapi.Api(websession=async_get_clientsession(hass))
    # missing: validate api connection

    coordinator = ChargeCloudDataUpdateCoordinator(hass, api, entry.data["evse_id"])
    hass.data[DOMAIN][entry.entry_id] = coordinator
    await coordinator.async_config_entry_first_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class ChargeCloudDataUpdateCoordinator(DataUpdateCoordinator):
    """My custom coordinator."""

    def __init__(self, hass, api: chargecloudapi.Api, evse_id: EvseId):
        """Initialize my coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )
        self.api = api
        self.evse_id = evse_id
        self.smart_call_data: chargecloudapi.SmartCallData | None = None

    async def _async_update_data(self) -> chargecloudapi.Location | None:
        """Fetch data from API endpoint.

        This is the place to pre-process the data to lookup tables
        so entities can quickly look up their data.
        """
        # Note: asyncio.TimeoutError and aiohttp.ClientError are already
        # handled by the data update coordinator.
        async with async_timeout.timeout(10):
            location, smart_call_data = await self.api.perform_smart_api_call(self.evse_id, self.smart_call_data)
            self.smart_call_data = smart_call_data
            if location is None:
                _LOGGER.info("received empty update")
            return location