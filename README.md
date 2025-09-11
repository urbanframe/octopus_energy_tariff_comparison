# octopus_energy_tariff_comparison
Home Assistant entities to compare tariff costs for the current day.




alias: Check if current tariff is cheapest
description: Compare tariff costs and notify if current tariff is not the cheapest
triggers:
  - at: "06:00:00"
    trigger: time
conditions: []
actions:
  - variables:
      agile_cost: "{{ states('sensor.agile_octopus_cost_today') | float(0) }}"
      octopus_go_cost: "{{ states('sensor.octopus_go_cost_today') | float(0) }}"
      cosy_cost: "{{ states('sensor.cosy_octopus_cost_today') | float(0) }}"
      flexible_cost: "{{ states('sensor.flexible_octopus_cost_today') | float(0) }}"
      current_tariff: "{{ states('sensor.current_tariff') }}"
      min_cost: |
        {{ [agile_cost, octopus_go_cost, cosy_cost, flexible_cost] | min }}
      cheapest_tariff: |
        {% if agile_cost == min_cost %}
          Agile Octopus
        {% elif octopus_go_cost == min_cost %}
          Octopus Go
        {% elif cosy_cost == min_cost %}
          Cosy Octopus
        {% else %}
          Flexible Octopus
        {% endif %}
      current_cost: |
        {% if current_tariff == 'Agile Octopus' %}
          {{ states('sensor.agile_octopus_cost_today') | float(0) }}
        {% elif current_tariff == 'Octopus Go' %}
          {{ octopus_go_cost }}
        {% elif current_tariff == 'Cosy Octopus' %}
          {{ cosy_cost }}
        {% elif current_tariff == 'Flexible Octopus' %}
          {{ flexible_cost }}
        {% else %}
          0
        {% endif %}
      savings: "{{ (current_cost | float(0)) - (min_cost | float(0)) }}"
  - condition: template
    value_template: "{{ current_tariff != cheapest_tariff }}"
  - action: notify.mobile_app_davids_iphone
    data:
      title: ⚡ Tariff Alert
      message: |
        Your current tariff ({{ current_tariff }}) is not the cheapest today!
                
                Current cost: {{ current_cost | round(2) }}p
                Cheapest tariff: {{ cheapest_tariff }}
                Cheapest cost: £{{ min_cost | round(2) }}
                Potential savings: £{{ savings | round(2) }}
                
mode: single