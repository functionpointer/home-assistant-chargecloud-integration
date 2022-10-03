"""Platform for sensor integration."""
from __future__ import annotations

import chargecloudapi
from chargecloudapi import Location

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import ChargeCloudDataUpdateCoordinator
from .const import DOMAIN, EvseId


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up a Geocaching sensor entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            ChargeCloudRealtimeSensor(
                evse_id=entry.data["evse_id"], coordinator=coordinator
            )
        ]
    )


class ChargeCloudRealtimeSensor(
    CoordinatorEntity[ChargeCloudDataUpdateCoordinator], SensorEntity
):
    """Main feature of this integration. This sensor represents an EVSE and shows its realtime availability status."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(
        self,
        evse_id: EvseId,
        coordinator: ChargeCloudDataUpdateCoordinator,
    ) -> None:
        """Initialize the Sensor."""
        super().__init__(coordinator)
        self.evse_id = evse_id
        self.coordinator = coordinator
        self._attr_unique_id = f"{evse_id}-realtime"
        self._attr_attribution = "chargecloud.de"
        self._attr_device_class = None
        self._attr_native_unit_of_measurement = None
        self._attr_state_class = None
        self._attr_device_info = DeviceInfo(
            name=self._get_location().name,
            identifiers={(DOMAIN, self.evse_id)},
            entry_type=None,
        )
        # read data from coordinator, which should have data by now
        self._read_coordinator_data()

    def _get_location(self) -> Location:
        for location in self.coordinator.data:
            for evse in location.evses:
                if evse.id == self.evse_id:
                    return location

    def _get_evse(self) -> chargecloudapi.Evse:
        for evse in self._get_location().evses:
            if evse.id == self.evse_id:
                return evse

    def _choose_icon(self, connectors: list[chargecloudapi.Connector]):
        iconmap: dict[str, str] = {
            "IEC_62196_T2": "mdi:ev-plug-type2",
            "IEC_62196_T2_COMBO": "mdi:ev-plug-ccs2",
            "CHADEMO": "mdi:ev-plug-chademo",
            "TESLA": "mdi:ev-plug-tesla",
            "DOMESTIC_F": "mdi:power-socket-eu",
        }
        if len(connectors) != 1:
            return "mdi:ev-station"
        return iconmap.get(connectors[0].standard, "mdi:ev-station")

    def _read_coordinator_data(self) -> None:
        location = self._get_location()
        evse = self._get_evse()
        self._attr_native_value = evse.status
        self._attr_icon = self._choose_icon(evse.connectors)
        extra_data = {
            "address": location.address,
            "city": location.city,
            "postal_code": location.postal_code,
            "country": location.country,
            "lat": location.coordinates.latitude,
            "lon": location.coordinates.longitude,
            "connectors": [
                {
                    "power_type": connector.power_type,
                    "ampere": connector.ampere,
                    "voltage": connector.voltage,
                    "max_power": connector.max_power,
                    "standard": connector.standard,
                    "format": connector.format,
                }
                for connector in evse.connectors
            ],
        }
        self._attr_extra_state_attributes = extra_data

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._read_coordinator_data()
        self.async_write_ha_state()
