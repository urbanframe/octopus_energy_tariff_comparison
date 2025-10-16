"""API client for Octopus Energy."""
from __future__ import annotations

import base64
import logging
from datetime import date, datetime
from typing import Any, Dict, List, Tuple

import requests

from .const import GRAPHQL_URL, REST_BASE_URL, TARIFFS_TO_COMPARE

_LOGGER = logging.getLogger(__name__)


class OctopusEnergyAPI:
    """API client for Octopus Energy."""

    def __init__(self, config: dict[str, str]) -> None:
        """Initialize the API client."""
        self.config = config
        self._kraken_token = None

    def test_connection(self) -> bool:
        """Test the connection to the API."""
        try:
            kraken_token = self._obtain_kraken_token()
            account_info = self._get_account_info(kraken_token)
            return account_info is not None
        except Exception as e:
            _LOGGER.error("Failed to connect to Octopus Energy API: %s", e)
            raise

    def _obtain_kraken_token(self) -> str:
        """Obtain a Kraken token for GraphQL authentication."""
        headers = {"Content-Type": "application/json"}
        
        mutation_variables = {
            "input": {
                "APIKey": self.config["api_key"]
            }
        }
        
        mutation = """
        mutation obtainKrakenToken($input: ObtainJSONWebTokenInput!) {
            obtainKrakenToken(input: $input) {
                token
            }
        }
        """
        
        payload = {
            "query": mutation,
            "variables": mutation_variables
        }
        
        try:
            response = requests.post(GRAPHQL_URL, json=payload, headers=headers, timeout=30)
            response.raise_for_status()
            result = response.json()
            
            if "errors" in result:
                raise Exception(f"Error obtaining Kraken token: {result['errors']}")
            
            token = result["data"]["obtainKrakenToken"]["token"]
            self._kraken_token = token
            return token
            
        except requests.exceptions.RequestException as e:
            _LOGGER.error("Error obtaining Kraken token: %s", e)
            raise

    def _execute_graphql_query(self, query: str, kraken_token: str) -> Dict:
        """Execute a GraphQL query against Octopus Energy API with Kraken token."""
        headers = {
            "Authorization": kraken_token,
            "Content-Type": "application/json"
        }
        
        payload = {"query": query}
        
        try:
            response = requests.post(GRAPHQL_URL, json=payload, headers=headers, timeout=30)
            response.raise_for_status()
            result = response.json()
            
            if "errors" in result:
                raise Exception(f"GraphQL errors: {result['errors']}")
            
            return result.get("data", {})
        except requests.exceptions.RequestException as e:
            _LOGGER.error("Error making GraphQL request: %s", e)
            raise

    def _rest_query(self, url: str, headers: Dict[str, str] = None) -> Dict:
        """Make a REST API call and return JSON response."""
        if headers is None:
            credentials = base64.b64encode(f"{self.config['api_key']}:".encode()).decode()
            headers = {"Authorization": f"Basic {credentials}"}
        
        try:
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            _LOGGER.error("Error making REST API request to %s: %s", url, e)
            raise

    def _get_account_info(self, kraken_token: str) -> Dict:
        """Get account information including current tariff."""
        query = f"""query{{
            account(
                accountNumber: "{self.config['account_number']}"
            ) {{
                electricityAgreements(active: true) {{
                    validFrom
                    validTo
                    meterPoint {{
                        meters(includeInactive: false) {{
                            smartDevices {{
                                deviceId
                            }}
                        }}
                        mpan
                        direction
                    }}
                    tariff {{
                        ... on HalfHourlyTariff {{
                            id
                            productCode
                            tariffCode
                            standingCharge
                        }}
                    }}
                }}
            }}
        }}"""
        
        result = self._execute_graphql_query(query, kraken_token)
        
        import_agreement = None
        for agreement in result.get("account", {}).get("electricityAgreements", []):
            meter_point = agreement.get("meterPoint", {})
            if (meter_point.get("direction") == "IMPORT" and 
                meter_point.get("mpan") == self.config["mpan"]):
                import_agreement = agreement
                break
        
        if not import_agreement:
            raise Exception("No matching IMPORT meter point found in account data")
        
        tariff = import_agreement.get("tariff")
        if not tariff:
            raise Exception("No tariff information found for the IMPORT meter")
        
        # Find device ID
        device_id = None
        meter_point = import_agreement.get("meterPoint", {})
        for meter in meter_point.get("meters", []):
            for device in meter.get("smartDevices", []):
                if "deviceId" in device:
                    device_id = device["deviceId"]
                    break
            if device_id:
                break
        
        if not device_id:
            raise Exception("No device ID found for the IMPORT meter")
        
        return {
            "tariff_code": tariff.get("tariffCode"),
            "standing_charge": tariff.get("standingCharge"),
            "region_code": tariff.get("tariffCode", "")[-1],
            "device_id": device_id
        }

    def _get_consumption_data(self, device_id: str, kraken_token: str) -> Tuple[List[Dict], date]:
        """Get consumption data for today."""
        today = date.today()
        
        query = f"""query {{
            smartMeterTelemetry(
                deviceId: "{device_id}"
                grouping: HALF_HOURLY
                start: "{today}T00:00:00Z"
                end: "{today}T23:59:59Z"
            ) {{
                readAt
                consumptionDelta
                costDeltaWithTax
            }}
        }}"""
        
        result = self._execute_graphql_query(query, kraken_token)
        consumption = result.get("smartMeterTelemetry", [])
        
        return consumption, today

    def _identify_current_tariff(self, tariff_code: str) -> str:
        """Identify the current tariff from tariff code."""
        tariff_code_upper = tariff_code.upper()
        
        if "AGILE" in tariff_code_upper:
            return "Agile Octopus"
        elif "GO" in tariff_code_upper:
            return "Octopus Go"
        elif "COSY" in tariff_code_upper:
            return "Cosy Octopus"
        elif "FLEX" in tariff_code_upper:
            return "Flexible Octopus"
        else:
            return f"Other tariff: {tariff_code}"

    def _get_potential_tariff_rates(self, tariff: str, region_code: str, analysis_date: date) -> Tuple[float, List[Dict], str]:
        """Get tariff rates for a specific tariff and region using REST API."""
        from datetime import timedelta
        
        try:
            all_products = self._rest_query(f"{REST_BASE_URL}/products/?brand=OCTOPUS_ENERGY&is_business=false")
            
            product = None
            # Try exact match first
            for p in all_products["results"]:
                if (p["display_name"] == tariff and p["direction"] == "IMPORT"):
                    product = p
                    break
            
            # Try partial match if exact match fails
            if product is None:
                for p in all_products["results"]:
                    if (tariff.lower() in p["display_name"].lower() and p["direction"] == "IMPORT"):
                        product = p
                        break
            
            if product is None:
                raise ValueError(f"No matching tariff found for '{tariff}'")
            
            product_link = next((
                item.get("href") for item in product.get("links", [])
                if item.get("rel", "").lower() == "self"
            ), None)
            
            if not product_link:
                raise ValueError(f"Self link not found for tariff {product['code']}")
            
            tariff_details = self._rest_query(product_link)
            
            # Get the standing charge including VAT
            region_code_key = f"_{region_code}"
            filtered_region = tariff_details.get("single_register_electricity_tariffs", {}).get(region_code_key)
            
            if filtered_region is None:
                raise ValueError(f"Region code not found {region_code_key}")
            
            region_tariffs = filtered_region.get("direct_debit_monthly") or filtered_region.get("varying")
            
            if region_tariffs is None:
                raise ValueError(f"No payment method found for region {region_code_key}")
            
            standing_charge_inc_vat = region_tariffs.get("standing_charge_inc_vat")
            
            if standing_charge_inc_vat is None:
                raise ValueError(f"Standing charge including VAT not found for region {region_code_key}")
            
            # Find the link for standard unit rates
            region_links = region_tariffs.get("links", [])
            unit_rates_link = next((
                item.get("href") for item in region_links
                if item.get("rel", "").lower() == "standard_unit_rates"
            ), None)
            
            if not unit_rates_link:
                raise ValueError(f"Standard unit rates link not found for region: {region_code_key}")
            
            # Get rates for today and tomorrow
            tomorrow = analysis_date + timedelta(days=1)
            unit_rates_link_with_time = f"{unit_rates_link}?period_from={analysis_date}T00:00:00Z&period_to={tomorrow}T23:59:59Z"
            unit_rates = self._rest_query(unit_rates_link_with_time)
            
            return standing_charge_inc_vat, unit_rates.get("results", []), product["code"]
            
        except Exception as e:
            _LOGGER.error("Error fetching tariff rates for %s: %s", tariff, e)
            raise

    def _calculate_cost_for_consumption(self, consumption_data: list, unit_rates: list, standing_charge: float) -> float:
        """Calculate the total cost for given consumption and rates."""
        total_energy_cost = 0.0
        
        # Create a mapping of time periods to rates
        rate_map = {}
        for rate in unit_rates:
            rate_map[rate["valid_from"]] = float(rate["value_inc_vat"])
        
        # Sort rates by time (most recent first)
        sorted_rates = sorted(rate_map.items(), reverse=True)
        
        for reading in consumption_data:
            try:
                consumption_kwh = float(reading["consumptionDelta"]) / 1000
            except (TypeError, ValueError):
                consumption_kwh = 0.0
            
            read_time = reading["readAt"]
            
            if consumption_kwh == 0:
                continue
            
            # Find the matching rate for this time period
            matching_rate = None
            for rate_time, rate_value in sorted_rates:
                if rate_time <= read_time:
                    matching_rate = rate_value
                    break
            
            if matching_rate is None and sorted_rates:
                matching_rate = sorted_rates[-1][1]
            
            if matching_rate is not None:
                total_energy_cost += consumption_kwh * float(matching_rate)
        
        # Add daily standing charge and convert to pence
        total_cost = total_energy_cost + float(standing_charge)
        
        return total_cost

    def get_tariff_data(self) -> Dict[str, Any]:
        """Get all tariff comparison data."""
        try:
            # Get Kraken token
            kraken_token = self._obtain_kraken_token()
            
            # Get account information
            account_info = self._get_account_info(kraken_token)
            
            # Get consumption data
            consumption_data, analysis_date = self._get_consumption_data(account_info["device_id"], kraken_token)
            
            if not consumption_data:
                _LOGGER.warning("No consumption data found")
                return {}
            
            # Identify current tariff
            current_tariff_name = self._identify_current_tariff(account_info["tariff_code"])
            
            # Calculate total consumption
            total_consumption = sum(float(reading.get("consumptionDelta", 0) or 0) / 1000 for reading in consumption_data)
            
            # Compare costs across tariffs and collect rates
            tariff_costs = {}
            tariff_rates = {}
            
            for tariff in TARIFFS_TO_COMPARE:
                try:
                    standing_charge, unit_rates, product_code = self._get_potential_tariff_rates(
                        tariff, account_info["region_code"], analysis_date)
                    
                    if not unit_rates:
                        _LOGGER.warning("No rate data available for %s on %s", tariff, analysis_date)
                        continue
                    
                    total_cost = self._calculate_cost_for_consumption(
                        consumption_data, unit_rates, standing_charge)
                    
                    tariff_key = tariff.lower().replace(" ", "_")
                    tariff_costs[tariff_key] = total_cost
                    
                    # Store rates for event entities
                    tariff_rates[tariff_key] = self._format_rates_for_event(unit_rates)
                    
                    # Store current rate for Flexible Octopus
                    if tariff == "Flexible Octopus":
                        current_flexible_rate = self._get_current_rate(unit_rates)
                        if current_flexible_rate is not None:
                            tariff_costs["current_flexible_rate"] = current_flexible_rate
                    
                except Exception as e:
                    _LOGGER.error("Error analyzing %s: %s", tariff, e)
            
            return {
                "current_tariff_name": current_tariff_name,
                "total_consumption": round(total_consumption, 3),
                "number_of_readings": len(consumption_data),
                "tariff_rates": tariff_rates,
                **tariff_costs
            }
            
        except Exception as e:
            _LOGGER.error("Error getting tariff data: %s", e)
            raise

    def _format_rates_for_event(self, unit_rates: List[Dict]) -> List[Dict]:
        """Format unit rates for event entity attributes with all half-hourly periods for today and tomorrow."""
        from datetime import datetime, timedelta, timezone
        
        if not unit_rates:
            return []
        
        # Filter for DIRECT_DEBIT rates that are currently valid (valid_to is null or in the future)
        now = datetime.now(timezone.utc).isoformat()
        filtered_rates = []
        
        for rate in unit_rates:
            # Prefer DIRECT_DEBIT, but fallback to any payment method if not available
            is_direct_debit = rate.get("payment_method") == "DIRECT_DEBIT"
            valid_to = rate.get("valid_to")
            valid_from = rate.get("valid_from")
            
            # Rate is valid if valid_to is None (ongoing) or in the future
            is_valid = valid_to is None or valid_to > now
            
            # Rate has started
            has_started = valid_from <= now
            
            if is_direct_debit and is_valid:
                filtered_rates.append(rate)
        
        # If no DIRECT_DEBIT rates found, fall back to all valid rates
        if not filtered_rates:
            filtered_rates = [r for r in unit_rates if (r.get("valid_to") is None or r.get("valid_to") > now)]
        
        # If still no rates, use all rates
        if not filtered_rates:
            filtered_rates = unit_rates
        
        # Create a map of rates by their valid_from time
        rate_map = {}
        for rate in filtered_rates:
            valid_from = rate["valid_from"]
            # For rates with the same valid_from, prefer DIRECT_DEBIT
            if valid_from not in rate_map or rate.get("payment_method") == "DIRECT_DEBIT":
                rate_map[valid_from] = float(rate["value_inc_vat"])
        
        # Sort rates by time to find the correct rate for any period
        sorted_rates = sorted(rate_map.items())
        
        # Get today's date at midnight in UTC
        today = datetime.now(timezone.utc).date()
        start_of_today = datetime(today.year, today.month, today.day, 0, 0, 0, tzinfo=timezone.utc)
        end_of_today = start_of_today + timedelta(days=1)
        end_of_tomorrow = start_of_today + timedelta(days=2)
        
        formatted_rates = []
        
        # Determine if we have tomorrow's data by checking if any rates exist after today
        has_tomorrow = any(rate_time >= end_of_today.isoformat().replace('+00:00', 'Z') for rate_time, _ in sorted_rates)
        
        # Create periods for today and tomorrow if available
        end_time = end_of_tomorrow if has_tomorrow else end_of_today
        
        current_time = start_of_today
        while current_time < end_time:
            period_start = current_time
            period_end = current_time + timedelta(minutes=30)
            
            # Find the applicable rate for this period
            applicable_rate = None
            period_start_iso = period_start.isoformat().replace('+00:00', 'Z')
            
            # Find the most recent rate that started before or at this period
            for rate_time, rate_value in reversed(sorted_rates):
                if rate_time <= period_start_iso:
                    applicable_rate = rate_value
                    break
            
            # If no rate found before this period, use the first available rate
            if applicable_rate is None and sorted_rates:
                applicable_rate = sorted_rates[0][1]
            
            if applicable_rate is not None:
                formatted_rates.append({
                    "start": period_start.isoformat(),
                    "end": period_end.isoformat(),
                    "value_inc_vat": round(applicable_rate / 100, 6),  # Convert pence to GBP
                    "is_capped": False
                })
            
            current_time = period_end
        
        # Return in chronological order (earliest first)
        return formatted_rates

    def _get_current_rate(self, unit_rates: List[Dict]) -> float:
        """Get the current rate from unit rates, preferring DIRECT_DEBIT with valid_to=null."""
        from datetime import datetime, timezone
        
        if not unit_rates:
            return None
        
        now = datetime.now(timezone.utc).isoformat()
        
        # Filter for DIRECT_DEBIT rates with valid_to=null (current ongoing rate)
        current_rates = [
            r for r in unit_rates 
            if r.get("payment_method") == "DIRECT_DEBIT" 
            and r.get("valid_to") is None
            and r.get("valid_from") <= now
        ]
        
        # If found, use the most recent one
        if current_rates:
            # Sort by valid_from descending to get the most recent
            current_rates.sort(key=lambda x: x["valid_from"], reverse=True)
            return round(float(current_rates[0]["value_inc_vat"]), 2)  # Return in pence
        
        # Fallback: find any valid rate for now
        valid_rates = [
            r for r in unit_rates
            if r.get("valid_from") <= now
            and (r.get("valid_to") is None or r.get("valid_to") > now)
        ]
        
        if valid_rates:
            # Prefer DIRECT_DEBIT, then sort by valid_from
            valid_rates.sort(key=lambda x: (
                x.get("payment_method") != "DIRECT_DEBIT",
                -1 if x.get("valid_from") else 0
            ), reverse=True)
            return round(float(valid_rates[0]["value_inc_vat"]), 2)  # Return in pence
        
        return None
