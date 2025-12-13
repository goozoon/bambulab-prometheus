# Example PromQL Queries for Bambu Lab Printer Monitoring

## Current Temperatures

### Nozzle Temperature
```promql
bambu_nozzle_temperature_celsius{printer="bambu_a1"}
```

### Bed Temperature
```promql
bambu_bed_temperature_celsius{printer="bambu_a1"}
```

### Chamber Temperature
```promql
bambu_chamber_temperature_celsius{printer="bambu_a1"}
```

## Print Progress

### Current Progress Percentage
```promql
bambu_print_progress_percent{printer="bambu_a1"}
```

### Time Remaining (in hours)
```promql
bambu_print_remaining_time_seconds{printer="bambu_a1"} / 3600
```

### Estimated Completion Time
```promql
time() + bambu_print_remaining_time_seconds{printer="bambu_a1"}
```

### Layer Progress Percentage
```promql
(bambu_current_layer{printer="bambu_a1"} / bambu_total_layers{printer="bambu_a1"}) * 100
```

## Alerts

### High Nozzle Temperature
```promql
bambu_nozzle_temperature_celsius{printer="bambu_a1"} > 280
```

### High Bed Temperature
```promql
bambu_bed_temperature_celsius{printer="bambu_a1"} > 110
```

### Printer Offline
```promql
bambu_online{printer="bambu_a1"} == 0
```

### Print Stalled (progress not changing)
```promql
# No change in progress for 5 minutes while printing
(
  bambu_print_progress_percent{printer="bambu_a1"} > 0 
  and 
  bambu_print_progress_percent{printer="bambu_a1"} < 100
)
and
(
  delta(bambu_print_progress_percent{printer="bambu_a1"}[5m]) == 0
)
```

### Temperature Deviation
```promql
# Nozzle temperature more than 5°C from target
abs(
  bambu_nozzle_temperature_celsius{printer="bambu_a1"} 
  - 
  bambu_nozzle_target_temperature_celsius{printer="bambu_a1"}
) > 5
```

## Statistics

### Average Print Speed (last hour)
```promql
avg_over_time(bambu_print_speed_percent{printer="bambu_a1"}[1h])
```

### Fan Speed Average
```promql
avg_over_time(bambu_fan_speed_percent{printer="bambu_a1", fan="part_cooling"}[1h])
```

### WiFi Signal Trend
```promql
rate(bambu_wifi_signal_strength_dbm{printer="bambu_a1"}[5m])
```

## Multi-Printer Queries

### All Printers Online Status
```promql
bambu_online
```

### Compare Temperatures Across Printers
```promql
bambu_nozzle_temperature_celsius
```

### Total Active Prints
```promql
count(bambu_print_progress_percent > 0 and bambu_print_progress_percent < 100)
```

## Prometheus Alert Rules Example

Create `/etc/prometheus/rules/bambulab.yml`:

```yaml
groups:
  - name: bambulab_alerts
    interval: 30s
    rules:
      - alert: BambuPrinterOffline
        expr: bambu_online == 0
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Bambu Lab printer {{ $labels.printer }} is offline"
          description: "Printer {{ $labels.printer }} has been offline for more than 5 minutes."
      
      - alert: BambuHighNozzleTemp
        expr: bambu_nozzle_temperature_celsius > 290
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "High nozzle temperature on {{ $labels.printer }}"
          description: "Nozzle temperature is {{ $value }}°C on {{ $labels.printer }}"
      
      - alert: BambuPrintStalled
        expr: |
          bambu_print_progress_percent > 0 
          and bambu_print_progress_percent < 100
          and delta(bambu_print_progress_percent[10m]) == 0
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Print may be stalled on {{ $labels.printer }}"
          description: "No progress detected on {{ $labels.printer }} for 10 minutes"
      
      - alert: BambuTempDeviation
        expr: |
          abs(
            bambu_nozzle_temperature_celsius 
            - bambu_nozzle_target_temperature_celsius
          ) > 10
          and bambu_nozzle_target_temperature_celsius > 0
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Temperature deviation on {{ $labels.printer }}"
          description: "Nozzle temp is {{ $value }}°C away from target"
```

Add to prometheus.yml:
```yaml
rule_files:
  - "/etc/prometheus/rules/bambulab.yml"
```
