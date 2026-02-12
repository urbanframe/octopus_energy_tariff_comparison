"""Constants for the Octopus Energy Tariff Comparison integration."""

DOMAIN = "octopus_energy_tariff_comparison"

# Configuration keys
CONF_ACCOUNT_NUMBER = "account_number"
CONF_API_KEY = "api_key"
CONF_MPAN = "mpan"
CONF_SERIAL_NUMBER = "serial_number"
CONF_REGION_CODE = "region_code"

# API Constants
GRAPHQL_URL = "https://api.octopus.energy/v1/graphql/"
REST_BASE_URL = "https://api.octopus.energy/v1"

# Update interval (every 30 minutes)
UPDATE_INTERVAL = 5

# Tariffs to compare
TARIFFS_TO_COMPARE = [
    "Agile Octopus",
    "Octopus Go", 
    "Cosy Octopus",
    "Flexible Octopus"
]
