"""Sensor platform for Octopus Energy Tariff Comparison."""
from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import OctopusEnergyCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensor platform."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    entities = [
        OctopusCurrentTariffSensor(coordinator),
        OctopusTotalConsumptionSensor(coordinator),
        OctopusReadingsCountSensor(coordinator),
        OctopusCurrentFlexibleRateSensor(coordinator),
        OctopusAgileCostSensor(coordinator),
        OctopusGoCostSensor(coordinator),
        OctopusCosyCostSensor(coordinator),
        OctopusFlexibleCostSensor(coordinator),
    ]
    
    async_add_entities(entities)


class OctopusBaseSensor(CoordinatorEntity, SensorEntity):
    """Base sensor for Octopus Energy Tariff Comparison."""

    def __init__(self, coordinator: OctopusEnergyCoordinator, sensor_key: str, name: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.sensor_key = sensor_key
        self._attr_name = name
        self._attr_unique_id = f"{coordinator.config['account_number']}_{sensor_key}"


class OctopusCurrentTariffSensor(OctopusBaseSensor):
    """Current tariff name sensor."""

    def __init__(self, coordinator: OctopusEnergyCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, "current_tariff_name", "Current Tariff")
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        if self.coordinator.data:
            return self.coordinator.data.get("current_tariff_name")
        return None

    @property
    def icon(self) -> str:
        """Return the icon of the sensor."""
        return "mdi:lightning-bolt"


class OctopusTotalConsumptionSensor(OctopusBaseSensor):
    """Total consumption sensor."""

    def __init__(self, coordinator: OctopusEnergyCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, "total_consumption", "Total Consumption Today")
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_state_class = SensorStateClass.TOTAL
        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        self._attr_suggested_display_precision = 3

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        if self.coordinator.data:
            return self.coordinator.data.get("total_consumption")
        return None


class OctopusReadingsCountSensor(OctopusBaseSensor):
    """Number of readings sensor."""

    def __init__(self, coordinator: OctopusEnergyCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, "number_of_readings", "Number of Readings")
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def native_value(self) -> int | None:
        """Return the state of the sensor."""
        if self.coordinator.data:
            return self.coordinator.data.get("number_of_readings")
        return None

    @property
    def icon(self) -> str:
        """Return the icon of the sensor."""
        return "mdi:counter"


class OctopusCurrentFlexibleRateSensor(OctopusBaseSensor):
    """Current Flexible Octopus rate sensor."""

    def __init__(self, coordinator: OctopusEnergyCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, "current_flexible_rate", "Current Flexible Rate")
        self._attr_device_class = SensorDeviceClass.MONETARY
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = "p/kWh"
        self._attr_suggested_display_precision = 2

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        if self.coordinator.data:
            return self.coordinator.data.get("current_flexible_rate")
        return None

    @property
    def icon(self) -> str:
        """Return the icon of the sensor."""
        return "mdi:flash"

    @property
    def extra_state_attributes(self) -> dict:
        """Return extra state attributes."""
        if self.coordinator.data and "current_flexible_rate" in self.coordinator.data:
            rate_pence = self.coordinator.data.get("current_flexible_rate", 0)
            return {
                "rate_gbp": round(rate_pence / 100, 4),
                "tariff_type": "Flexible Octopus"
            }
        return {}


class OctopusAgileCostSensor(OctopusBaseSensor):
    """Agile Octopus cost sensor."""

    def __init__(self, coordinator: OctopusEnergyCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, "agile_octopus_cost", "Agile Octopus Cost Today")
        self._attr_device_class = SensorDeviceClass.MONETARY
        self._attr_state_class = SensorStateClass.TOTAL
        self._attr_native_unit_of_measurement = "GBP"
        self._attr_suggested_display_precision = 2

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        if self.coordinator.data:
            cost_pence = self.coordinator.data.get("agile_octopus")
            if cost_pence is not None:
                return round(cost_pence / 100, 2)
        return None

    @property
    def icon(self) -> str:
        """Return the icon of the sensor."""
        return "mdi:cash"

    @property
    def extra_state_attributes(self) -> dict:
        """Return extra state attributes."""
        if self.coordinator.data and "agile_octopus" in self.coordinator.data:
            cost_pence = self.coordinator.data.get("agile_octopus", 0)
            return {
                "cost_pence": round(cost_pence, 2),
                "tariff_type": "Agile Octopus"
            }
        return {}


class OctopusGoCostSensor(OctopusBaseSensor):
    """Octopus Go cost sensor."""

    def __init__(self, coordinator: OctopusEnergyCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, "octopus_go_cost", "Octopus Go Cost Today")
        self._attr_device_class = SensorDeviceClass.MONETARY
        self._attr_state_class = SensorStateClass.TOTAL
        self._attr_native_unit_of_measurement = "GBP"
        self._attr_suggested_display_precision = 2

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        if self.coordinator.data:
            cost_pence = self.coordinator.data.get("octopus_go")
            if cost_pence is not None:
                return round(cost_pence / 100, 2)
        return None

    @property
    def icon(self) -> str:
        """Return the icon of the sensor."""
        return "mdi:cash"

    @property
    def extra_state_attributes(self) -> dict:
        """Return extra state attributes."""
        if self.coordinator.data and "octopus_go" in self.coordinator.data:
            cost_pence = self.coordinator.data.get("octopus_go", 0)
            return {
                "cost_pence": round(cost_pence, 2),
                "tariff_type": "Octopus Go"
            }
        return {}


class OctopusCosyCostSensor(OctopusBaseSensor):
    """Cosy Octopus cost sensor."""

    def __init__(self, coordinator: OctopusEnergyCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, "cosy_octopus_cost", "Cosy Octopus Cost Today")
        self._attr_device_class = SensorDeviceClass.MONETARY
        self._attr_state_class = SensorStateClass.TOTAL
        self._attr_native_unit_of_measurement = "GBP"
        self._attr_suggested_display_precision = 2

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        if self.coordinator.data:
            cost_pence = self.coordinator.data.get("cosy_octopus")
            if cost_pence is not None:
                return round(cost_pence / 100, 2)
        return None

    @property
    def icon(self) -> str:
        """Return the icon of the sensor."""
        return "mdi:cash"

    @property
    def extra_state_attributes(self) -> dict:
        """Return extra state attributes."""
        if self.coordinator.data and "cosy_octopus" in self.coordinator.data:
            cost_pence = self.coordinator.data.get("cosy_octopus", 0)
            return {
                "cost_pence": round(cost_pence, 2),
                "tariff_type": "Cosy Octopus"
            }
        return {}


class OctopusFlexibleCostSensor(OctopusBaseSensor):
    """Flexible Octopus cost sensor."""

    def __init__(self, coordinator: OctopusEnergyCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, "flexible_octopus_cost", "Flexible Octopus Cost Today")
        self._attr_device_class = SensorDeviceClass.MONETARY
        self._attr_state_class = SensorStateClass.TOTAL
        self._attr_native_unit_of_measurement = "GBP"
        self._attr_suggested_display_precision = 2

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        if self.coordinator.data:
            cost_pence = self.coordinator.data.get("flexible_octopus")
            if cost_pence is not None:
                return round(cost_pence / 100, 2)
        return None

    @property
    def icon(self) -> str:
        """Return the icon of the sensor."""
        return "mdi:cash"

    @property
    def extra_state_attributes(self) -> dict:
        """Return extra state attributes."""
        if self.coordinator.data and "flexible_octopus" in self.coordinator.data:
            cost_pence = self.coordinator.data.get("flexible_octopus", 0)
            return {
                "cost_pence": round(cost_pence, 2),
                "tariff_type": "Flexible Octopus"
            }
        return {}
