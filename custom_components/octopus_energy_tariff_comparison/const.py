"""Constants for the Octopus Energy Tariff Comparison integration."""

DOMAIN = "octopus_energy_tariff_comparison"

# Configuration keys
CONF_ACCOUNT_NUMBER = "account_number"
CONF_API_KEY = "api_key"
CONF_MPAN = "mpan"
CONF_REGION_CODE = "region_code"

# Options keys
CONF_UPDATE_INTERVAL = "update_interval"

# API Constants
GRAPHQL_URL = "https://api.octopus.energy/v1/graphql/"
REST_BASE_URL = "https://api.octopus.energy/v1"

# Kraken tokens are valid ~1 hour. Refresh a little early to be safe.
KRAKEN_TOKEN_TTL_MINUTES = 50

# Consumption / cost update interval (minutes).
# This governs how often consumption + cost figures refresh. The 48 half-hourly
# rates only change once a day (published ~4pm) and are cached separately, so
# this interval does NOT drive rate API calls.
DEFAULT_UPDATE_INTERVAL = 5
MIN_UPDATE_INTERVAL = 1
MAX_UPDATE_INTERVAL = 60

# Rate publication window (UK local time).
# Octopus publishes the next day's 48 half-hourly rates from ~4pm. We make the
# first attempt at 16:00 and retry at most every RATE_RETRY_MINUTES until the
# response actually contains tomorrow's rates, giving up after RATE_WINDOW_END.
RATE_WINDOW_START_HOUR = 16
RATE_WINDOW_END_HOUR = 22
RATE_RETRY_MINUTES = 30

# Tariffs to compare
TARIFFS_TO_COMPARE = [
    "Agile Octopus",
    "Octopus Go",
    "Cosy Octopus",
    "Flexible Octopus"
]
