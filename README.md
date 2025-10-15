# Octopus Energy Tariff Comparison - Home Assistant Integration

This Home Assistant integration compares electricity costs across different Octopus Energy tariffs based on your current day's usage.
It also provides today's rates for Agile, Go and Cozy tariffs.  

The rate entities match those provided for your current tariff by BottlecapDave's fantastic [HomeAssistant-OctopusEnergy](https://github.com/BottlecapDave/HomeAssistant-OctopusEnergy) integration.

This integration is compatible with lozzd's brilliant [Octopus Energy Rates Card](https://github.com/lozzd/octopus-energy-rates-card).

## Features

The integration creates the following sensors:
- **Current Tariff**: Your current tariff name
- **Total Consumption Today**: Total kWh consumed today
- **Number of Readings**: Number of smart meter readings received
- **Agile Octopus Cost Today**: Cost in pence if you were on Agile Octopus
- **Octopus Go Cost Today**: Cost in pence if you were on Octopus Go
- **Cosy Octopus Cost Today**: Cost in pence if you were on Cosy Octopus
- **Flexible Octopus Cost Today**: Cost in pence if you were on Flexible Octopus

And the following event entities with rate data:
- **Agile Octopus Rates**: Half-hourly rates for Agile tariff
- **Octopus Go Rates**: Half-hourly rates for Go tariff
- **Cosy Octopus Rates**: Half-hourly rates for Cosy tariff
- **Flexible Octopus Rates**: Half-hourly rates for Flexible tariff

<img width="440" height="319" alt="image" src="https://github.com/user-attachments/assets/dd4dc634-7fde-4492-bff1-5fbef8c0a6c1" />


## Installation

### HACS Installation

1. Add this repository as a custom repository in HACS
2. Install "Octopus Energy Tariff Comparison" 
3. Restart Home Assistant

## Configuration

1. Go to **Settings** → **Devices & Services**
2. Click **+ Add Integration**
3. Search for "Octopus Energy Tariff Comparison"
4. Enter your Octopus Energy account details:

   - **Account Number**: Your Octopus account number (e.g., A-EDF238B3)
   - **API Key**: Your Octopus Energy API key (get from your account dashboard)
   - **MPAN**: Your electricity meter MPAN number
   - **Serial Number**: Your smart meter serial number
   - **Region Code**: Your electricity region code (A-P, typically found at the end of your tariff code)

## Getting Your API Key

1. Log into your Octopus Energy account
2. Go to **Developer Dashboard** or account settings
3. Generate/copy your API key
4. The API key starts with `sk_live_`

## Finding Your Details

- **MPAN**: Found on your electricity bill (13-digit number)
- **Serial Number**: Found on your smart meter or bill
- **Region Code**: Usually the last letter of your current tariff code, or check your postcode area:
  - A: Eastern England
  - B: East Midlands  
  - C: London
  - D: Merseyside and Northern Wales
  - E: West Midlands
  - F: North Eastern England
  - G: North Western England
  - H: Southern England
  - J: South Eastern England
  - K: South Western England
  - L: South Wales
  - M: Scotland (Southern)
  - N: Scotland (Northern)
  - P: North Wales

## Data Updates

- The integration polls the Octopus Energy API every 30 minutes
- Cost calculations are based on your current day's consumption
- All costs include VAT and are shown in pence

## Octopus Energy Rates Card Example

```yaml
type: custom:octopus-energy-rates-card
currentEntity: event.agile_octopus_rates
cols: 3
hour12: false
showday: true
showpast: false
title: Agile Tariff Rate
unitstr: p
lowlimit: 15
mediumlimit: 20
highlimit: 27.27
roundUnits: 2
cheapest: true
multiplier: 100
```
<img width="444" height="803" alt="image" src="https://github.com/user-attachments/assets/42022a86-15b8-4cfc-8955-51b93cd8efee" />

## Apexcharts Card Example

```yaml
type: custom:apexcharts-card
header:
  show: true
  show_states: true
  colorize_states: true
  title: Current Agile Tariff Rates
experimental:
  color_threshold: true
graph_span: 2d
stacked: false
span:
  start: hour
apex_config:
  chart:
    height: 400
  legend:
    show: false
yaxis:
  - min: ~0
    max: ~35
    decimals: 1
series:
  - entity: event.agile_octopus_rates
    type: column
    name: ""
    color_threshold:
      - value: 0
        color: blue
      - value: 0
        color: green
      - value: 20
        color: orange
      - value: 27.27
        color: red
    opacity: 1
    stroke_width: 0
    unit: p
    show:
      in_header: false
      legend_value: false
    data_generator: |
      return entity.attributes.rates.map((entry) => {
      return [new Date(entry.start), entry.value_inc_vat * 100];
      });
    offset: "-15min"
  - entity: sensor.octopus_flex_rate
    opacity: 0.5
    stroke_width: 2
    stroke_dash: 6
    name: ""
    show:
      in_header: false
      legend_value: false
```
<img width="440" height="385" alt="image" src="https://github.com/user-attachments/assets/b37549b4-b66e-4982-aa2e-c61f40e49a11" />


## Sensors Details

### Cost Sensors
Each cost sensor shows:
- **State**: Cost in pence for today's consumption
- **Attributes**: 
  - `cost_pounds`: Cost converted to pounds
  - `tariff_type`: The tariff name

### Consumption Sensor
- **State**: Total kWh consumed today
- **Unit**: kWh
- **Precision**: 3 decimal places

### Diagnostic Sensors
- **Current Tariff**: Shows your current tariff name
- **Number of Readings**: Count of half-hourly readings received

## Event Entities

### Rate Events
Each tariff has an event entity that contains the half-hourly rates as attributes:

**Attributes format:**
```yaml
rates:
  - start: '2025-10-14T23:30:00+00:00'
    end: '2025-10-14T24:00:00+00:00'
    value_inc_vat: 0.003051  # in GBP (not pence)
    is_capped: false
  - start: '2025-10-14T23:00:00+00:00'
    end: '2025-10-14T23:30:00+00:00'
    value_inc_vat: 0.000850
    is_capped: false
  # ... (48 periods total, in reverse chronological order)
```

**Notes:**
- Rates are in **GBP** (pounds), not pence
- All 48 half-hourly periods are included (even if the tariff rate doesn't change)
- Rates are in **reverse chronological order** (most recent first)

**Available event entities:**
- `event.agile_octopus_rates`
- `event.octopus_go_rates`
- `event.cosy_octopus_rates`
- `event.flexible_octopus_rates`

Each event entity fires a `rates_updated` event when new rate data is received.

## Troubleshooting

### No consumption data
- Check your smart meter is sending data to Octopus
- Verify your MPAN and serial number are correct
- Some meters take time to start reporting data

### API errors
- Verify your API key is correct and active
- Check your account number format
- Ensure your account has the necessary permissions

### Missing tariff costs
- Some tariffs may not have rate data available for the current day
- Regional availability varies for different tariffs

## Automation Examples

### Using rate data to find cheapest periods
```yaml
automation:
  - alias: "Find Cheapest Rate Period"
    trigger:
      - platform: state
        entity_id: event.agile_octopus_rates
    action:
      - service: notify.notify
        data:
          message: >
            {% set rates = state_attr('event.agile_octopus_rates', 'rates') %}
            {% set cheapest = rates | sort(attribute='value_inc_vat') | first %}
            Cheapest rate today: {{ cheapest.value_inc_vat }}p/kWh 
            from {{ cheapest.start }} to {{ cheapest.end }}
```

### Alert when savings are available
```yaml
automation:
  - alias: "Tariff Savings Available"
    trigger:
      - platform: numeric_state
        entity_id: sensor.agile_octopus_cost_today
        below: sensor.current_tariff_cost_today  # You'd need to add this sensor
    action:
      - service: notify.notify
        data:
          message: "Potential savings available on Agile Octopus tariff today!"
```

### Daily cost comparison
```yaml
automation:
  - alias: "Daily Tariff Summary"
    trigger:
      - platform: time
        at: "23:00:00"
    action:
      - service: notify.notify
        data:
          message: >
            Today's costs:
            Agile: £{{ (states('sensor.agile_octopus_cost_today') | float / 100) | round(2) }}
            Go: £{{ (states('sensor.octopus_go_cost_today') | float / 100) | round(2) }}
            Cosy: £{{ (states('sensor.cosy_octopus_cost_today') | float / 100) | round(2) }}
            Flexible: £{{ (states('sensor.flexible_octopus_cost_today') | float / 100) | round(2) }}
```

## Support

This integration is based on the Octopus Energy GraphQL and REST APIs. For API issues, check the [Octopus Energy API documentation](https://developer.octopus.energy/).

## Disclaimer

This integration provides cost estimates based on current tariff rates and your consumption data. Actual costs may vary due to rate changes, meter accuracy, and billing cycles. Always refer to your official Octopus Energy bill for accurate charges.
