"""API client for Octopus Energy."""
from __future__ import annotations

import base64
import logging
from datetime import date, datetime, time
from typing import Any, Dict, List, Tuple

import requests

from .const import GRAPHQL_URL, REST_BASE_URL, TARIFFS_TO_COMPARE

_LOGGER = logging.getLogger(__name__)


class OctopusEnergyAPI:
    """API client for Octopus Energy."""

    # Time-of-day tariff schedules (in UK local time)
    # Go tariff: cheap rate from 00:30 to 05:30
    GO_NIGHT_START = time(0, 30)
    GO_NIGHT_END = time(5, 30)
    
    # Cosy tariff: three cheap periods
    COSY_PERIODS = [
        (time(4, 0), time(7, 0)),    # 04:00-07:00
        (time(13, 0), time(16, 0)),  # 13:00-16:00  
        (time(22, 0), time(0, 0)),   # 22:00-00:00 (crosses midnight)
    ]
    COSY_PEAK_START = time(16, 0)
    COSY_PEAK_END = time(19, 0)

    def __init__(self, config: dict[str, str]) -> None:
        """Initialize the API client."""
        self.config = config
        self._kraken_token = None

    def _is_time_in_period(self, check_time: time, start: time, end: time) -> bool:
        """Check if a time falls within a period, handling midnight crossover."""
        if start < end:
            # Simple case: period doesn't cross midnight
            return start <= check_time < end
        else:
            # Period crosses midnight (e.g., 22:00 to 00:00)
            return check_time >= start or check_time < end
    
    def _get_go_rate_for_time(self, dt: datetime, day_rate: float, night_rate: float) -> float:
        """
        Get the applicable Go tariff rate for a specific datetime.
        
        Args:
            dt: Datetime in UK timezone
            day_rate: Day rate in pence/kWh
            night_rate: Night rate in pence/kWh
            
        Returns:
            Applicable rate in pence/kWh
        """
        t = dt.time()
        if self._is_time_in_period(t, self.GO_NIGHT_START, self.GO_NIGHT_END):
            return night_rate
        return day_rate
    
    def _get_cosy_rate_for_time(self, dt: datetime, day_rate: float, cosy_rate: float, peak_rate: float) -> float:
        """
        Get the applicable Cosy tariff rate for a specific datetime.
        
        Args:
            dt: Datetime in UK timezone
            day_rate: Standard day rate in pence/kWh
            cosy_rate: Cosy period rate in pence/kWh
            peak_rate: Peak period rate in pence/kWh
            
        Returns:
            Applicable rate in pence/kWh
        """
        t = dt.time()
        
        # Check if in peak period
        if self._is_time_in_period(t, self.COSY_PEAK_START, self.COSY_PEAK_END):
            return peak_rate
        
        # Check if in any cosy period
        for start, end in self.COSY_PERIODS:
            if self._is_time_in_period(t, start, end):
                return cosy_rate
        
        # Otherwise, use day rate
        return day_rate

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
        """Get consumption data for today (UK time)."""
        from datetime import datetime, timezone
        from zoneinfo import ZoneInfo
        
        # Get current time in UK timezone
        uk_tz = ZoneInfo("Europe/London")
        now_uk = datetime.now(uk_tz)
        today_uk = now_uk.date()
        
        # Create start and end times for today in UK time
        start_of_day_uk = datetime(today_uk.year, today_uk.month, today_uk.day, 0, 0, 0, tzinfo=uk_tz)
        end_of_day_uk = datetime(today_uk.year, today_uk.month, today_uk.day, 23, 59, 59, tzinfo=uk_tz)
        
        # Convert to UTC for API request
        start_utc = start_of_day_uk.astimezone(timezone.utc)
        end_utc = end_of_day_uk.astimezone(timezone.utc)
        
        query = f"""query {{
            smartMeterTelemetry(
                deviceId: "{device_id}"
                grouping: HALF_HOURLY
                start: "{start_utc.strftime('%Y-%m-%dT%H:%M:%SZ')}"
                end: "{end_utc.strftime('%Y-%m-%dT%H:%M:%SZ')}"
            ) {{
                readAt
                consumptionDelta
                costDeltaWithTax
            }}
        }}"""
        
        result = self._execute_graphql_query(query, kraken_token)
        consumption = result.get("smartMeterTelemetry", [])
        
        return consumption, today_uk

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
        """Get tariff rates for a specific tariff and region using REST API (UK timezone)."""
        from datetime import datetime, timedelta, timezone
        from zoneinfo import ZoneInfo
        
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
            
            # Convert analysis_date to UK timezone for proper date boundaries
            uk_tz = ZoneInfo("Europe/London")
            start_of_day_uk = datetime(analysis_date.year, analysis_date.month, analysis_date.day, 0, 0, 0, tzinfo=uk_tz)
            
            # Get rates from start of today to end of tomorrow (UK time)
            # We need tomorrow's rates for the event entities
            end_of_tomorrow_uk = start_of_day_uk + timedelta(days=2)
            
            # Convert to UTC for API request
            start_utc = start_of_day_uk.astimezone(timezone.utc)
            end_utc = end_of_tomorrow_uk.astimezone(timezone.utc)
            
            _LOGGER.debug(f"Fetching rates from {start_utc} to {end_utc} (UK: {start_of_day_uk} to {end_of_tomorrow_uk})")
            
            # Get rates for today and tomorrow (UK time)
            unit_rates_link_with_time = f"{unit_rates_link}?period_from={start_utc.strftime('%Y-%m-%dT%H:%M:%SZ')}&period_to={end_utc.strftime('%Y-%m-%dT%H:%M:%SZ')}"
            unit_rates = self._rest_query(unit_rates_link_with_time)
            
            return standing_charge_inc_vat, unit_rates.get("results", []), product["code"]
            
        except Exception as e:
            _LOGGER.error("Error fetching tariff rates for %s: %s", tariff, e)
            raise

    def _calculate_cost_for_consumption(self, consumption_data: list, unit_rates: list, standing_charge: float, analysis_date: date, tariff_name: str = None) -> float:
        """Calculate the total cost for given consumption and rates (UK timezone aware)."""
        from datetime import datetime, timedelta, timezone
        from zoneinfo import ZoneInfo
        
        total_energy_cost = 0.0
        uk_tz = ZoneInfo("Europe/London")
        
        # Determine if this is a time-of-day tariff
        is_go_tariff = tariff_name and "go" in tariff_name.lower() and "agile" not in tariff_name.lower()
        is_cosy_tariff = tariff_name and "cosy" in tariff_name.lower()
        is_time_of_day_tariff = is_go_tariff or is_cosy_tariff
        
        if is_time_of_day_tariff:
            # For Go and Cosy tariffs: Extract the different rate tiers from API response
            # These tariffs return 2-4 rates total, not half-hourly rates
            
            # Filter for DIRECT_DEBIT rates
            dd_rates = [r for r in unit_rates if r.get("payment_method") == "DIRECT_DEBIT"]
            if not dd_rates:
                dd_rates = unit_rates
            
            # Extract unique rate values
            rate_values = sorted(set(float(r["value_inc_vat"]) for r in dd_rates))
            
            if is_go_tariff:
                # Go has 2 rates: night (cheap) and day (expensive)
                if len(rate_values) < 2:
                    _LOGGER.error(f"Expected 2 rates for Go tariff, got {len(rate_values)}: {rate_values}")
                    # Fallback to generic calculation
                    is_time_of_day_tariff = False
                else:
                    night_rate = min(rate_values)  # Cheapest is night rate
                    day_rate = max(rate_values)    # Most expensive is day rate
                    
                    _LOGGER.info(f"Go tariff rates: night={night_rate}p/kWh, day={day_rate}p/kWh (period: {self.GO_NIGHT_START.strftime('%H:%M')}-{self.GO_NIGHT_END.strftime('%H:%M')})")
            
            elif is_cosy_tariff:
                # Cosy has 3 rates: cosy (cheap), day (medium), peak (expensive)
                if len(rate_values) < 3:
                    _LOGGER.error(f"Expected 3 rates for Cosy tariff, got {len(rate_values)}: {rate_values}")
                    is_time_of_day_tariff = False
                else:
                    rate_values_sorted = sorted(rate_values)
                    cosy_rate = rate_values_sorted[0]  # Cheapest
                    day_rate = rate_values_sorted[1]   # Middle
                    peak_rate = rate_values_sorted[2]  # Most expensive
                    
                    _LOGGER.info(f"Cosy tariff rates: cosy={cosy_rate}p/kWh, day={day_rate}p/kWh, peak={peak_rate}p/kWh")
        
        # For Agile/Flexible: prepare rate data once before processing readings
        if not is_time_of_day_tariff:
            # Get UK timezone boundaries for the analysis date
            start_of_day_uk = datetime(analysis_date.year, analysis_date.month, analysis_date.day, 0, 0, 0, tzinfo=uk_tz)
            end_of_day_uk = start_of_day_uk + timedelta(days=1)
            
            # Convert to UTC for comparison
            start_of_day_utc = start_of_day_uk.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z')
            end_of_day_utc = end_of_day_uk.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z')
            
            # Filter rates to only those that apply to TODAY in UK time
            applicable_rates = []
            for rate in unit_rates:
                valid_from = rate.get("valid_from")
                valid_to = rate.get("valid_to")
                
                # Only include DIRECT_DEBIT rates
                if rate.get("payment_method") != "DIRECT_DEBIT":
                    continue
                
                # Rate must have started before end of today
                if valid_from and valid_from < end_of_day_utc:
                    # Rate must still be valid (no valid_to, or valid_to is after start of today)
                    if valid_to is None or valid_to > start_of_day_utc:
                        applicable_rates.append(rate)
            
            # If no DIRECT_DEBIT rates, fall back to any rates
            if not applicable_rates:
                applicable_rates = [r for r in unit_rates if r.get("valid_from", "") < end_of_day_utc]
            
            # Create a mapping of time periods to rates
            rate_map = {}
            for rate in applicable_rates:
                valid_from = rate["valid_from"]
                if valid_from not in rate_map or rate.get("payment_method") == "DIRECT_DEBIT":
                    rate_map[valid_from] = float(rate["value_inc_vat"])
            
            # Sort rates by time (earliest first)
            sorted_rates = sorted(rate_map.items())
        
        # Process each consumption reading
        for reading in consumption_data:
            try:
                consumption_kwh = float(reading["consumptionDelta"]) / 1000
            except (TypeError, ValueError):
                consumption_kwh = 0.0
            
            if consumption_kwh == 0:
                continue
            
            read_time_str = reading["readAt"]
            read_time_utc = datetime.fromisoformat(read_time_str.replace('Z', '+00:00'))
            read_time_uk = read_time_utc.astimezone(uk_tz)
            
            # Get the applicable rate
            if is_time_of_day_tariff:
                # Use time-of-day logic
                if is_go_tariff:
                    matching_rate = self._get_go_rate_for_time(read_time_uk, day_rate, night_rate)
                elif is_cosy_tariff:
                    matching_rate = self._get_cosy_rate_for_time(read_time_uk, day_rate, cosy_rate, peak_rate)
                else:
                    matching_rate = None
            else:
                # For Agile and Flexible: use timestamp-based matching
                # Find the rate that applies to this reading
                # Use < not <= because readAt is end of consumption period
                matching_rate = None
                for rate_time, rate_value in reversed(sorted_rates):
                    if rate_time < read_time_str:
                        matching_rate = rate_value
                        break
                
                # Fallback to first rate if no match
                if matching_rate is None and sorted_rates:
                    matching_rate = sorted_rates[0][1]
            
            if matching_rate is not None:
                cost = consumption_kwh * float(matching_rate)
                total_energy_cost += cost
        
        # Add daily standing charge (in pence) to get total cost in pence
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
            
            _LOGGER.info(f"Processing data for {analysis_date} (UK time)")
            _LOGGER.info(f"Total consumption: {total_consumption}kWh from {len(consumption_data)} readings")
            
            # Compare costs across tariffs and collect rates
            tariff_costs = {}
            tariff_rates = {}
            
            for tariff in TARIFFS_TO_COMPARE:
                try:
                    standing_charge, unit_rates, product_code = self._get_potential_tariff_rates(
                        tariff, account_info["region_code"], analysis_date)
                    
                    _LOGGER.info(f"{tariff}: Fetched {len(unit_rates)} rate periods, standing charge: {standing_charge}p")
                    
                    if not unit_rates:
                        _LOGGER.warning("No rate data available for %s on %s", tariff, analysis_date)
                        continue
                    
                    total_cost = self._calculate_cost_for_consumption(
                        consumption_data, unit_rates, standing_charge, analysis_date, tariff)
                    
                    tariff_key = tariff.lower().replace(" ", "_")
                    tariff_costs[tariff_key] = total_cost
                    
                    _LOGGER.info(f"{tariff}: Total cost = {total_cost}p (energy: {total_cost - standing_charge}p + standing: {standing_charge}p)")
                    
                    # Store rates for event entities
                    tariff_rates[tariff_key] = self._format_rates_for_event(unit_rates)
                    
                    # Store current rate for Flexible Octopus
                    if tariff == "Flexible Octopus":
                        current_flexible_rate = self._get_current_rate(unit_rates)
                        if current_flexible_rate is not None:
                            tariff_costs["current_flexible_rate"] = current_flexible_rate
                    
                except Exception as e:
                    _LOGGER.error("Error analyzing %s: %s", tariff, e, exc_info=True)
            
            return {
                "current_tariff_name": current_tariff_name,
                "total_consumption": round(total_consumption, 3),
                "number_of_readings": len(consumption_data),
                "tariff_rates": tariff_rates,
                **tariff_costs
            }
            
        except Exception as e:
            _LOGGER.error("Error getting tariff data: %s", e, exc_info=True)
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
