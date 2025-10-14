"""Event platform for Octopus Energy Tariff Comparison."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.event import EventEntity, EventDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import OctopusEnergyCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up event platform."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    entities = [
        OctopusAgileRatesEvent(coordinator),
        OctopusGoRatesEvent(coordinator),
        OctopusCosyRatesEvent(coordinator),
        OctopusFlexibleRatesEvent(coordinator),
    ]
    
    async_add_entities(entities)


class OctopusRatesEventBase(CoordinatorEntity, EventEntity):
    """Base event entity for Octopus Energy rates."""

    _attr_event_types = ["rates_updated"]

    def __init__(
        self, 
        coordinator: OctopusEnergyCoordinator, 
        tariff_key: str,
        name: str
    ) -> None:
        """Initialize the event entity."""
        super().__init__(coordinator)
        self.tariff_key = tariff_key
        self._attr_name = name
        self._attr_unique_id = f"{coordinator.config['account_number']}_{tariff_key}_rates"
        self._attr_has_entity_name = True
        self._last_rates_update = None

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self.coordinator.data and "tariff_rates" in self.coordinator.data:
            rates = self.coordinator.data["tariff_rates"].get(self.tariff_key)
            if rates:
                # Trigger event when rates are updated
                current_update = str(rates)
                if current_update != self._last_rates_update:
                    self._trigger_event("rates_updated", {"rates": rates})
                    self._last_rates_update = current_update
                    self.async_write_ha_state()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        if self.coordinator.data and "tariff_rates" in self.coordinator.data:
            rates = self.coordinator.data["tariff_rates"].get(self.tariff_key, [])
            return {
                "rates": rates,
                "last_updated": datetime.now().isoformat(),
                "rate_count": len(rates)
            }
        return {"rates": []}

    @property
    def icon(self) -> str:
        """Return the icon of the event."""
        return "mdi:cash-clock"


class OctopusAgileRatesEvent(OctopusRatesEventBase):
    """Agile Octopus rates event entity."""

    def __init__(self, coordinator: OctopusEnergyCoordinator) -> None:
        """Initialize the event entity."""
        super().__init__(coordinator, "agile_octopus", "Agile Octopus Rates")


class OctopusGoRatesEvent(OctopusRatesEventBase):
    """Octopus Go rates event entity."""

    def __init__(self, coordinator: OctopusEnergyCoordinator) -> None:
        """Initialize the event entity."""
        super().__init__(coordinator, "octopus_go", "Octopus Go Rates")


class OctopusCosyRatesEvent(OctopusRatesEventBase):
    """Cosy Octopus rates event entity."""

    def __init__(self, coordinator: OctopusEnergyCoordinator) -> None:
        """Initialize the event entity."""
        super().__init__(coordinator, "cosy_octopus", "Cosy Octopus Rates")


class OctopusFlexibleRatesEvent(OctopusRatesEventBase):
    """Flexible Octopus rates event entity."""

    def __init__(self, coordinator: OctopusEnergyCoordinator) -> None:
        """Initialize the event entity."""
        super().__init__(coordinator, "flexible_octopus", "Flexible Octopus Rates")
