"""DataUpdateCoordinator for Octopus Energy Tariff Comparison."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any, Dict

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import OctopusEnergyAPI
from .const import DOMAIN, CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)


class OctopusEnergyCoordinator(DataUpdateCoordinator):
    """Coordinator handling consumption polling and cached daily rates.

    The update interval governs only the consumption/cost refresh. The 48
    half-hourly rates are cached inside the API client and refetched at most
    once a day after ~4pm, independently of this interval.
    """

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize my coordinator."""
        interval_minutes = int(
            entry.options.get(
                CONF_UPDATE_INTERVAL,
                entry.data.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL),
            )
        )

        super().__init__(
            hass,
            _LOGGER,
            # Name of the data. For logging purposes.
            name=DOMAIN,
            # Polling interval. Will only be polled if there are subscribers.
            update_interval=timedelta(minutes=interval_minutes),
        )
        self.entry = entry
        self.api = OctopusEnergyAPI(entry.data)
        self.config = entry.data

    async def _async_update_data(self) -> Dict[str, Any]:
        """Fetch data from API endpoint.

        This is the place to pre-process the data to lookup tables
        so entities can quickly look up their data.
        """
        try:
            # Note: asyncio.TimeoutError and aiohttp.ClientError are already
            # handled by the data update coordinator.
            data = await self.hass.async_add_executor_job(self.api.get_tariff_data)
            return data
        except Exception as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err
