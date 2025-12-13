# Troubleshooting: "No Data" in Grafana Dashboard

If you see "No Data" everywhere in Grafana after importing the dashboard, follow these steps:

## Step 1: Verify Exporter is Running

On your LXC:
```bash
systemctl status bambulab-prometheus
```

Should show: `active (running)`

Check logs:
```bash
journalctl -u bambulab-prometheus -f
```

You should see:
- "Successfully connected to printer 'a1'"
- "Starting metric collection (interval: 5s)"
- State, speed, and file messages every 5 seconds

## Step 2: Verify Metrics Endpoint

Test the exporter endpoint:
```bash
curl http://localhost:9100/metrics
```

Or from another machine:
```bash
curl http://YOUR_LXC_IP:9100/metrics
```

You should see output like:
```
# HELP bambu_nozzle_temperature_celsius Current nozzle temperature
# TYPE bambu_nozzle_temperature_celsius gauge
bambu_nozzle_temperature_celsius{printer="a1"} 25.0
...
```

If this fails, check:
- Firewall: `ufw status` (make sure port 9100 is allowed)
- Service logs for errors

## Step 3: Verify Prometheus is Scraping

On your Prometheus server, check targets:
```
http://YOUR_PROMETHEUS_IP:9090/targets
```

Look for your `bambulab` job. It should show:
- **State**: UP (green)
- **Labels**: Should show your LXC IP
- **Last Scrape**: Should be recent (< 30 seconds ago)

If the target is DOWN or missing:
1. Check your `prometheus.yml` has the correct LXC IP
2. Reload Prometheus: `systemctl reload prometheus`
3. Check Prometheus can reach the LXC: `curl http://LXC_IP:9100/metrics` (from Prometheus host)

## Step 4: Verify Grafana Data Source

In Grafana:
1. Go to **Configuration** → **Data Sources**
2. Click your Prometheus data source
3. Scroll down and click **Save & Test**
4. Should show: "Data source is working"

If it fails:
- Check Prometheus URL is correct
- Verify Grafana can reach Prometheus server
- Check Prometheus is running: `systemctl status prometheus`

## Step 5: Check Dashboard Configuration

In the dashboard:
1. Click any panel's title → **Edit**
2. Look at the **Query** section
3. You should see: `bambu_nozzle_temperature_celsius{printer="$printer"}`
4. At the top, check the **$printer** variable dropdown
   - Should show your printer name (e.g., "a1")
   - If empty, the exporter hasn't sent data yet

## Step 6: Test a Simple Query

In Grafana, go to **Explore** (compass icon in left sidebar):
1. Select your Prometheus data source
2. Try this query:
   ```
   bambu_nozzle_temperature_celsius
   ```
3. Click **Run Query**

If you see data:
- Dashboard variable might be wrong (check step 5)
- Wait a few minutes for data to populate

If you don't see data:
- Prometheus isn't scraping the exporter (go back to Step 3)
- Metrics aren't being exposed (go back to Step 2)

## Common Issues

### Issue: Dashboard shows "No data" but metrics endpoint works

**Solution**: Check the `$printer` variable in the dashboard
1. Dashboard Settings (gear icon) → **Variables**
2. Edit the `printer` variable
3. Query should be: `label_values(bambu_online, printer)`
4. Make sure it returns your printer name

### Issue: Target shows UP but no metrics in Grafana

**Solution**: Wait 1-2 minutes for Prometheus to scrape data, then refresh Grafana

### Issue: Port 9100 connection refused

**Solution**: Check firewall on LXC
```bash
# If using ufw:
ufw allow 9100/tcp
ufw reload

# If using iptables:
iptables -A INPUT -p tcp --dport 9100 -j ACCEPT
```

### Issue: Exporter crashes or restarts constantly

**Solution**: Check logs for Python errors
```bash
journalctl -u bambulab-prometheus -n 100
```

Common causes:
- Wrong printer IP (can't reach printer)
- Wrong access code
- Printer not in LAN mode

### Issue: Old printer names appear in dropdown

**Symptom**: Dashboard dropdown shows multiple printer names (e.g., "A1", "a1", "BambulabA1") from previous configurations

**Cause**: Prometheus retains all historical label values in its time-series database. When you change the printer name in `config.yaml`, the old names remain in Prometheus's memory.

**Solutions**:

**Option 1: Ignore old names** (Recommended)
- Old printer names won't have current data - panels will show "No Data"
- Only the current printer name (matching `config.yaml`) has active metrics
- Old labels will eventually expire based on Prometheus retention settings

**Option 2: Clear Prometheus data**
```bash
systemctl stop prometheus
rm -rf /var/lib/prometheus/data/*
systemctl start prometheus
systemctl restart bambulab-prometheus
```
**Warning**: This deletes all historical data, not just printer metrics

**Option 3: Use consistent printer naming**
- Edit `/opt/bambulab-prometheus/config.yaml`
- Set `name` to your preferred value (e.g., "A1")
- Restart: `systemctl restart bambulab-prometheus`
- Wait 30 seconds for new metrics to appear

### Issue: Want to change printer name after installation

**Solution**: Edit the config file and restart the service

1. Edit the config:
```bash
nano /opt/bambulab-prometheus/config.yaml
```

2. Change the `name` field under `printers`:
```yaml
printers:
  - name: "A1"  # Change this to your preferred name
    ip: "192.168.0.29"
    access_code: "your_code"
    serial: "your_serial"
    enabled: true
```

3. Restart the service:
```bash
systemctl restart bambulab-prometheus
```

4. Verify new name appears in metrics:
```bash
curl -s http://localhost:9100/metrics | grep 'printer='
```

**Note**: The old printer name will still appear in Grafana's dropdown until Prometheus data expires or is cleared (see "Old printer names" issue above).

## Quick Verification Commands

Run these on your LXC to verify everything:

```bash
# 1. Service status
systemctl status bambulab-prometheus

# 2. Recent logs
journalctl -u bambulab-prometheus -n 20

# 3. Metrics endpoint
curl -s http://localhost:9100/metrics | grep bambu_online

# 4. Check if Prometheus can reach us (from Prometheus host)
# curl http://YOUR_LXC_IP:9100/metrics | head -20
```

All should return data. If any fail, that's where the problem is!
