# Bambulab Prometheus Exporter - Installation Guide

## Prerequisites

### LXC Container Setup in Proxmox

1. **Create LXC Container**
   - OS: Debian 12 or Ubuntu 22.04+
   - CPU: 1 core
   - RAM: 512MB (1GB recommended)
   - Storage: 2GB
   - Network: Bridge to same VLAN as printer

2. **Container Configuration** (in Proxmox)
   ```bash
   # Make container start on boot
   pct set <CTID> -onboot 1
   
   # Set resource limits
   pct set <CTID> -memory 512 -cores 1
   ```

## Installation Methods

### Method 1: Automated Installation (Recommended)

```bash
# Inside LXC container as root
cd /tmp
wget https://raw.githubusercontent.com/goozoon/bambulab-prometheus/main/install.sh
chmod +x install.sh
./install.sh
```

### Method 2: Manual Installation

#### 1. Install Dependencies

```bash
apt update
apt install -y python3 python3-pip python3-venv git
```

#### 2. Create Service User

```bash
useradd -r -s /bin/false -m -d /opt/bambulab-prometheus bambuexporter
```

#### 3. Clone Repository

```bash
cd /opt
git clone https://github.com/YOUR_USERNAME/bambulab-prometheus.git
chown -R bambuexporter:bambuexporter bambulab-prometheus
cd bambulab-prometheus
```

#### 4. Setup Python Environment

```bash
# Switch to service user
su - bambuexporter -s /bin/bash

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Exit back to root
exit
```

#### 5. Configure Application

```bash
cd /opt/bambulab-prometheus
cp config.example.yaml config.yaml
nano config.yaml
```

**Edit config.yaml with your printer details:**

```yaml
exporter:
  port: 9100
  log_level: INFO
  update_interval: 5
  bind_address: "0.0.0.0"

printers:
  - name: "bambu_a1"
    ip: "192.168.1.100"          # Your printer IP
    access_code: "12345678"       # From printer network settings
    serial: "01S00A000000000"     # Your printer serial number
    enabled: true
```

**Finding Your Printer Credentials:**

1. **IP Address**: Check printer display: Settings → Network → IP Address
2. **Access Code**: Settings → Network → Access Code
3. **Serial Number**: On printer label or Settings → About

#### 6. Install Systemd Service

```bash
cp systemd/bambulab-exporter.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable bambulab-exporter
systemctl start bambulab-exporter
```

#### 7. Verify Installation

```bash
# Check service status
systemctl status bambulab-exporter

# View logs
journalctl -u bambulab-exporter -f

# Test metrics endpoint
curl http://localhost:9100/metrics
```

You should see output like:
```
# HELP bambu_nozzle_temperature_celsius Current nozzle temperature
# TYPE bambu_nozzle_temperature_celsius gauge
bambu_nozzle_temperature_celsius{printer="bambu_a1"} 34.15625
# HELP bambu_bed_temperature_celsius Current bed temperature
# TYPE bambu_bed_temperature_celsius gauge
bambu_bed_temperature_celsius{printer="bambu_a1"} 32.5
...
```

## Configure Prometheus

### Add Scrape Target

Edit your Prometheus configuration (usually `/etc/prometheus/prometheus.yml`):

```yaml
scrape_configs:
  - job_name: 'bambulab'
    scrape_interval: 10s
    static_configs:
      - targets: ['<LXC_CONTAINER_IP>:9100']
        labels:
          location: 'homelab'
          printer_type: 'bambu_a1'
```

Reload Prometheus:
```bash
systemctl reload prometheus
# or
curl -X POST http://localhost:9090/-/reload
```

### Verify in Prometheus

1. Open Prometheus UI: `http://<prometheus-ip>:9090`
2. Go to Status → Targets
3. Check that `bambulab` target is UP
4. Query some metrics: `bambu_nozzle_temperature_celsius`

## Configure Grafana Dashboard

### Method 1: Import Pre-built Dashboard

1. Open Grafana UI
2. Go to Dashboards → Import
3. Upload `grafana/dashboard.json` from this repository
4. Select your Prometheus data source
5. Click Import

### Method 2: Create Custom Dashboard

Example panels to create:

**Temperature Panel (Graph)**
```promql
bambu_nozzle_temperature_celsius{printer="bambu_a1"}
bambu_nozzle_target_temperature_celsius{printer="bambu_a1"}
bambu_bed_temperature_celsius{printer="bambu_a1"}
bambu_bed_target_temperature_celsius{printer="bambu_a1"}
```

**Print Progress (Gauge)**
```promql
bambu_print_progress_percent{printer="bambu_a1"}
```

**Time Remaining (Stat)**
```promql
bambu_print_remaining_time_seconds{printer="bambu_a1"} / 60
```

**Current Layer (Stat)**
```promql
bambu_current_layer{printer="bambu_a1"}
```

**Print Status (Stat)**
```promql
bambu_online{printer="bambu_a1"}
```

## Troubleshooting

### Service Won't Start

```bash
# Check logs for errors
journalctl -u bambulab-exporter -n 50

# Check file permissions
ls -la /opt/bambulab-prometheus
chown -R bambuexporter:bambuexporter /opt/bambulab-prometheus

# Test manually
su - bambuexporter -s /bin/bash
cd /opt/bambulab-prometheus
source venv/bin/activate
python src/exporter.py
```

### Can't Connect to Printer

```bash
# Test network connectivity
ping <PRINTER_IP>

# Check printer is in LAN mode
# On printer: Settings → Network → LAN Mode (must be enabled)

# Verify credentials
# On printer: Settings → Network → Access Code

# Check firewall
iptables -L -n
```

### No Metrics Appearing

```bash
# Test locally
curl http://localhost:9100/metrics

# Check if port is listening
ss -tlnp | grep 9100

# Test from Prometheus server
curl http://<LXC_IP>:9100/metrics

# Check Prometheus logs
journalctl -u prometheus -f
```

### Metrics Are Stale

```bash
# Check update interval in config
cat /opt/bambulab-prometheus/config.yaml | grep update_interval

# Verify printer is responding
journalctl -u bambulab-exporter -f
```

### High CPU/Memory Usage

```bash
# Check resource usage
systemctl status bambulab-exporter

# Adjust update interval to reduce load
nano /opt/bambulab-prometheus/config.yaml
# Set update_interval: 10 or higher

# Restart service
systemctl restart bambulab-exporter
```

## Updating

```bash
cd /opt/bambulab-prometheus
sudo -u bambuexporter git pull
sudo -u bambuexporter venv/bin/pip install -r requirements.txt
systemctl restart bambulab-exporter
```

## Uninstallation

```bash
# Stop and disable service
systemctl stop bambulab-exporter
systemctl disable bambulab-exporter
rm /etc/systemd/system/bambulab-exporter.service
systemctl daemon-reload

# Remove application
rm -rf /opt/bambulab-prometheus

# Remove user
userdel bambuexporter
```

## Multi-Printer Setup

To monitor multiple printers, simply add more entries to `config.yaml`:

```yaml
printers:
  - name: "bambu_a1_workshop"
    ip: "192.168.1.100"
    access_code: "12345678"
    serial: "01S00A000000000"
    enabled: true
    
  - name: "bambu_p1s_office"
    ip: "192.168.1.101"
    access_code: "87654321"
    serial: "01P00A000000001"
    enabled: true
    
  - name: "bambu_a1_garage"
    ip: "192.168.1.102"
    access_code: "11223344"
    serial: "01S00A000000002"
    enabled: false  # Temporarily disabled
```

All metrics will include a `printer` label to distinguish between printers in Grafana.

## Security Recommendations

1. **Firewall Rules**: Limit access to port 9100
   ```bash
   # Only allow Prometheus server
   iptables -A INPUT -p tcp -s <PROMETHEUS_IP> --dport 9100 -j ACCEPT
   iptables -A INPUT -p tcp --dport 9100 -j DROP
   ```

2. **Network Isolation**: Keep printers on isolated VLAN

3. **LAN Only Mode**: Enable "LAN Only Mode" on printer (no cloud connection)

4. **Regular Updates**: Keep system and Python packages updated
   ```bash
   apt update && apt upgrade
   cd /opt/bambulab-prometheus
   sudo -u bambuexporter venv/bin/pip install --upgrade -r requirements.txt
   ```
