# Bambu Lab Prometheus Exporter - Available Metrics

## Overview
This document lists all metrics collected by the Bambu Lab Prometheus exporter from your 3D printer.

## Metric Categories

### Connection & Status Metrics

| Metric | Type | Description | Labels |
|--------|------|-------------|--------|
| `bambu_online` | Gauge | Printer connectivity status (0=offline, 1=online) | `printer` |
| `bambu_printer_state` | Gauge | Detailed printer state (0=IDLE, 1=PRINTING, 2=PAUSED, 3=FINISH, 4=FAILED) | `printer` |
| `bambu_wifi_signal_strength_dbm` | Gauge | WiFi signal strength in dBm | `printer` |
| `bambu_chamber_light` | Gauge | Chamber light state (0=off, 1=on) | `printer` |
| `bambu_error_code` | Gauge | Current error code (0=no error) | `printer` |

### Temperature Metrics

| Metric | Type | Description | Labels |
|--------|------|-------------|--------|
| `bambu_nozzle_temperature_celsius` | Gauge | Current nozzle temperature in °C | `printer` |
| `bambu_bed_temperature_celsius` | Gauge | Current bed temperature in °C | `printer` |
| `bambu_chamber_temperature_celsius` | Gauge | Current chamber temperature in °C | `printer` |

### Print Progress Metrics

| Metric | Type | Description | Labels |
|--------|------|-------------|--------|
| `bambu_print_progress_percent` | Gauge | Print completion percentage (0-100) | `printer` |
| `bambu_print_remaining_time_seconds` | Gauge | Estimated time remaining for print in seconds | `printer` |
| `bambu_current_layer` | Gauge | Current layer number being printed | `printer` |
| `bambu_total_layers` | Gauge | Total layers in the current print | `printer` |
| `bambu_print_speed_percent` | Gauge | Current print speed modifier (%) | `printer` |

### Information Metrics (Label-based)

| Metric | Type | Description | Labels |
|--------|------|-------------|--------|
| `bambu_current_file_info` | Gauge | Current file being printed (value=1 when active) | `printer`, `filename` |
| `bambu_nozzle_info` | Gauge | Nozzle information (value=1 when active) | `printer`, `nozzle_type`, `nozzle_diameter_mm` |

## Grafana Dashboard Panels

The comprehensive dashboard includes:

### Row 1: Status Overview
- **Printer Status** - Online/Offline indicator
- **Printer State** - IDLE/PRINTING/PAUSED/FINISHED/FAILED
- **WiFi Signal** - Signal strength gauge (-30 to -90 dBm)
- **Chamber Light** - On/Off indicator

### Row 2: Print Progress
- **Print Progress** - Large circular gauge (0-100%)
- **Print Progress Over Time** - Time series graph

### Row 3: Print Details
- **Time Remaining** - Estimated completion time
- **Current Layer** - Active layer number
- **Total Layers** - Total layer count
- **Print Speed** - Speed modifier percentage

### Row 4: Temperature Monitoring
- **Temperature Monitoring** - Combined time series graph for all temperatures
  - Nozzle (red line)
  - Bed (orange line)
  - Chamber (blue line)

### Row 5: Temperature Gauges
- **Nozzle Temperature** - Gauge (0-300°C)
- **Bed Temperature** - Gauge (0-120°C)
- **Chamber Temperature** - Gauge (0-80°C)

### Row 6: Additional Info
- **Error Code** - Current error state
- **Current File** - Name of file being printed

### Row 7: Hardware Info
- **Nozzle Type** - Installed nozzle type
- **Nozzle Diameter** - Nozzle size in mm

## Query Examples

### PromQL Queries

```promql
# Get current print progress
bambu_print_progress_percent{printer="a1"}

# Calculate time elapsed (when total time available)
bambu_print_remaining_time_seconds{printer="a1"} / bambu_print_progress_percent{printer="a1"} * 100

# Check if printer is actively printing
bambu_printer_state{printer="a1"} == 1

# Monitor temperature differential
bambu_nozzle_temperature_celsius{printer="a1"} - bambu_chamber_temperature_celsius{printer="a1"}

# Get all temperatures at once
{__name__=~"bambu_(nozzle|bed|chamber)_temperature_celsius", printer="a1"}

# Check for errors
bambu_error_code{printer="a1"} != 0

# Layer progress percentage
(bambu_current_layer{printer="a1"} / bambu_total_layers{printer="a1"}) * 100
```

### Alert Examples

```yaml
# Alert when printer goes offline
- alert: PrinterOffline
  expr: bambu_online == 0
  for: 5m
  annotations:
    summary: "Bambu Lab printer {{ $labels.printer }} is offline"

# Alert on print failure
- alert: PrintFailed
  expr: bambu_printer_state == 4
  annotations:
    summary: "Print failed on {{ $labels.printer }}"

# Alert on high nozzle temperature
- alert: NozzleOverheating
  expr: bambu_nozzle_temperature_celsius > 280
  for: 2m
  annotations:
    summary: "Nozzle temperature above 280°C on {{ $labels.printer }}"

# Alert when print completes
- alert: PrintComplete
  expr: bambu_printer_state == 3
  annotations:
    summary: "Print completed on {{ $labels.printer }}"
```

## Notes

### Fan Speed Monitoring
Fan speeds are **NOT available** in this exporter. The bambulabs_api library only provides setter methods (`set_part_fan_speed()`, `set_aux_fan_speed()`, `set_chamber_fan_speed()`) but no getter methods to read current fan speeds.

### Data Update Frequency
- Metrics are collected every **5 seconds**
- The exporter maintains persistent MQTT connections to printers
- Dashboard auto-refreshes every **5 seconds**

### Online Detection
The `bambu_online` metric uses smart detection:
- Checks MQTT connection status
- Verifies actual data reception (temperature readings)
- Sets offline (0) if printer is powered off but MQTT still connected

### Printer State Values
```
0 = IDLE       - Printer ready, no job
1 = PRINTING   - Actively printing
2 = PAUSED     - Print paused
3 = FINISH     - Print completed successfully
4 = FAILED     - Print failed/error
```

## Dashboard Import

To import the comprehensive dashboard into Grafana:

1. Copy `grafana/comprehensive-dashboard.json`
2. In Grafana: Dashboards → Import
3. Paste JSON or upload file
4. Select your Prometheus data source
5. Click Import

## Troubleshooting

### No Data Showing
1. Check exporter is running: `systemctl status bambulab-prometheus`
2. Check metrics endpoint: `curl http://localhost:9100/metrics`
3. Verify Prometheus is scraping: Check Prometheus targets page
4. Check printer is on and connected to network

### Missing Metrics
Some metrics only appear during active printing:
- `bambu_current_layer`, `bambu_total_layers` - Only during print
- `bambu_print_remaining_time_seconds` - Only during print
- `bambu_current_file_info` - Only when file is loaded

### Incorrect Values
- Temperature sensors may show ambient temp when cold
- Print progress stays at 0 when idle
- Layer counts are 0 when not printing
- Error code 0 means no error
