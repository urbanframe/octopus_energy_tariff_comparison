"""Event platform for Octopus Energy Tariff Comparison."""
from __future__ import annotations

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

    # Keep the bulky rate arrays out of the recorder database. The rates list
    # can hold up to 96 half-hourly periods per entity; recording it on every
    # state write bloats the DB for no benefit. The data is still available live
    # in the state machine for templates/automations.
    _unrecorded_attributes = frozenset({"rates"})

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
        data = self.coordinator.data
        if not data or "tariff_rates" not in data:
            return

        rates = data["tariff_rates"].get(self.tariff_key)
        if not rates:
            return

        # Fire 'rates_updated' only when the published rates actually change.
        # We key off a content signature computed when new rates are cached
        # (changes once a day after ~4pm), NOT off the formatted list — the
        # formatted list could otherwise appear to change as periods elapse.
        signature = data.get("rates_signature", {}).get(self.tariff_key)
        if signature != self._last_rates_update:
            self._trigger_event("rates_updated", {"rates": rates})
            self._last_rates_update = signature
            self.async_write_ha_state()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes.

        Note: we deliberately do NOT include a wall-clock timestamp here. A
        changing timestamp would make the attribute payload differ on every
        coordinator tick, forcing a recorder write even when the rates are
        unchanged. The rates only change once a day.
        """
        if self.coordinator.data and "tariff_rates" in self.coordinator.data:
            rates = self.coordinator.data["tariff_rates"].get(self.tariff_key, [])
            attrs: dict[str, Any] = {
                "rates": rates,
                "rate_count": len(rates),
            }
            # Anchor "last updated" to the data itself (the first period's start)
            # rather than now(), so it only changes when the rates change.
            if rates:
                attrs["valid_from"] = rates[0].get("start")
                attrs["valid_to"] = rates[-1].get("end")
            return attrs
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
