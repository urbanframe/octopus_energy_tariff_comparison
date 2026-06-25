"""Config flow for Octopus Energy Tariff Comparison integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
)

from .const import (
    DOMAIN,
    CONF_ACCOUNT_NUMBER,
    CONF_API_KEY,
    CONF_MPAN,
    CONF_REGION_CODE,
    CONF_UPDATE_INTERVAL,
    DEFAULT_UPDATE_INTERVAL,
    MIN_UPDATE_INTERVAL,
    MAX_UPDATE_INTERVAL,
)
from .api import OctopusEnergyAPI

_LOGGER = logging.getLogger(__name__)

REGION_CODES = ["A", "B", "C", "D", "E", "F", "G", "H", "J", "K", "L", "M", "N", "P"]

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ACCOUNT_NUMBER): str,
        vol.Required(CONF_API_KEY): str,
        vol.Required(CONF_MPAN): str,
        vol.Required(CONF_REGION_CODE): vol.In(REGION_CODES),
    }
)


def _account_details_schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    """Build the account-details schema, pre-filling defaults when provided.

    Used by the reconfigure step so the form shows the user's existing values,
    which they can then amend.
    """
    defaults = defaults or {}
    return vol.Schema(
        {
            vol.Required(
                CONF_ACCOUNT_NUMBER, default=defaults.get(CONF_ACCOUNT_NUMBER)
            ): str,
            vol.Required(CONF_API_KEY, default=defaults.get(CONF_API_KEY)): str,
            vol.Required(CONF_MPAN, default=defaults.get(CONF_MPAN)): str,
            vol.Required(
                CONF_REGION_CODE, default=defaults.get(CONF_REGION_CODE)
            ): vol.In(REGION_CODES),
        }
    )


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.
    
    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    api = OctopusEnergyAPI(data)
    
    try:
        # Test the connection by trying to get account info
        await hass.async_add_executor_job(api.test_connection)
    except Exception as exc:
        _LOGGER.exception("Unexpected exception")
        raise CannotConnect from exc
    
    # Return info that you want to store in the config entry.
    return {"title": f"Octopus Account {data[CONF_ACCOUNT_NUMBER]}"}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Octopus Energy Tariff Comparison."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> "OptionsFlowHandler":
        """Get the options flow for this handler."""
        return OptionsFlowHandler()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(user_input[CONF_ACCOUNT_NUMBER])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle reconfiguration of the account details.

        Lets the user amend the account number, API key, MPAN and region code
        after initial setup. The form is pre-filled with the current values.
        """
        errors: dict[str, str] = {}
        reconfigure_entry = self._get_reconfigure_entry()

        if user_input is not None:
            try:
                await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                # The unique id is the account number; don't allow it to change
                # to a different account during reconfigure.
                await self.async_set_unique_id(user_input[CONF_ACCOUNT_NUMBER])
                self._abort_if_unique_id_mismatch(reason="wrong_account")
                return self.async_update_reload_and_abort(
                    reconfigure_entry,
                    data_updates=user_input,
                )

        # Pre-fill with submitted values (on error) or current entry data.
        defaults = user_input or dict(reconfigure_entry.data)
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_account_details_schema(defaults),
            errors=errors,
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options for the consumption update interval."""

    # Note: do NOT set self.config_entry in __init__. On HA 2025.12+ it is a
    # read-only property provided by the base OptionsFlow class, and assigning
    # it raises AttributeError (surfacing as a 500 when opening the options
    # dialog). The base class already exposes self.config_entry for us.

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current_interval = self.config_entry.options.get(
            CONF_UPDATE_INTERVAL,
            self.config_entry.data.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL),
        )

        options_schema = vol.Schema(
            {
                vol.Required(
                    CONF_UPDATE_INTERVAL, default=current_interval
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=MIN_UPDATE_INTERVAL,
                        max=MAX_UPDATE_INTERVAL,
                        step=1,
                        mode=NumberSelectorMode.BOX,
                        unit_of_measurement="minutes",
                    )
                ),
            }
        )

        return self.async_show_form(step_id="init", data_schema=options_schema)
