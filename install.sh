#!/bin/bash
#
# Installation script for Bambulab Prometheus Exporter
# Run as root in your LXC container
# Usage: ./install.sh  (as root or with 'su' if sudo not available)
#

set -e

echo "======================================"
echo "Bambulab Prometheus Exporter Installer"
echo "======================================"
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "Error: Please run as root (use 'su' to switch to root)"
    exit 1
fi

echo ""
echo "======================================"
echo "Step 1/6: Installing System Dependencies"
echo "======================================"
# Only update if package lists are older than 1 day
if [ ! -f /var/lib/apt/periodic/update-success-stamp ] || [ $(find /var/lib/apt/periodic/update-success-stamp -mtime +1 2>/dev/null | wc -l) -gt 0 ]; then
    apt update
fi
apt install -y python3 python3-pip python3-venv git adduser

echo ""
echo "======================================"
echo "Step 2/6: Creating Service User"
echo "======================================"
if ! id -u bambulab-prometheus > /dev/null 2>&1; then
    # Use full path to adduser (in case PATH is not set correctly)
    /usr/sbin/adduser --system --group --home /opt/bambulab-prometheus --shell /bin/false bambulab-prometheus
    echo "  ✓ User 'bambulab-prometheus' created"
else
    echo "  ✓ User 'bambulab-prometheus' already exists"
fi

echo ""
echo "======================================"
echo "Step 3/6: Setting Up Application"
echo "======================================"
if [ -d "/opt/bambulab-prometheus/.git" ]; then
    echo "  Repository already exists, updating..."
    cd /opt/bambulab-prometheus
    # Fix ownership before git operations to avoid dubious ownership error
    chown -R root:root /opt/bambulab-prometheus
    # Reset local changes to install.sh before pulling
    git checkout -- install.sh 2>/dev/null || true
    git pull
    # Fix ownership after pull
    chown -R bambulab-prometheus:bambulab-prometheus /opt/bambulab-prometheus
else
    echo "  Cloning repository..."
    cd /opt
    git clone https://github.com/goozoon/bambulab-prometheus.git
    chown -R bambulab-prometheus:bambulab-prometheus /opt/bambulab-prometheus
fi

cd /opt/bambulab-prometheus

echo ""
echo "======================================"
echo "Step 4/6: Setting Up Python Environment"
echo "======================================"
if [ ! -d "venv" ]; then
    # Create venv as root, then fix ownership
    python3 -m venv venv
    chown -R bambulab-prometheus:bambulab-prometheus venv
    echo "  ✓ Virtual environment created"
else
    echo "  ✓ Virtual environment already exists"
fi

echo ""
echo "======================================"
echo "Step 5/6: Installing Python Dependencies"
echo "======================================"
# Install as root, then fix ownership
venv/bin/pip install --upgrade pip
venv/bin/pip install -r requirements.txt
echo "  ✓ Installed: bambulabs_api, prometheus-client, PyYAML, Flask, Pillow"
chown -R bambulab-prometheus:bambulab-prometheus venv

echo ""
echo "======================================"
echo "Step 6/6: Configuring Printer Settings"
echo "======================================"

# Function to write the config header (overwrites file)
write_config_header() {
    echo "Creating new configuration file..." >&2
    cat > config.yaml <<'CONF_EOF'
# Bambulab Prometheus Exporter Configuration
exporter:
  port: 9100
  log_level: INFO
  update_interval: 5
  bind_address: "0.0.0.0"

printers:
CONF_EOF
    chown bambulab-prometheus:bambulab-prometheus config.yaml
}

# Function to append a printer block
append_printer_config() {
    local NAME="$1"
    local IP="$2"
    local CODE="$3"
    local SERIAL="$4"

    echo "Adding printer '$NAME' to configuration..." >&2
    cat >> config.yaml <<'CONF_EOF'
  - name: "$NAME"
    ip: "$IP"
    access_code: "$CODE"
    serial: "$SERIAL"
    enabled: true
CONF_EOF
    # Replace placeholder variables
    sed -i "s|\$NAME|$NAME|g; s|\$IP|$IP|g; s|\$CODE|$CODE|g; s|\$SERIAL|$SERIAL|g" config.yaml
    chown bambulab-prometheus:bambulab-prometheus config.yaml
}

# Function to ask for printer details
ask_printer_details() {
    echo ""
    echo "Please enter your printer details:"
    
    read -p "Printer Name (e.g. bambu_a1): " P_NAME
    P_NAME=${P_NAME:-bambu_a1}
    
    P_IP=""
    while [ -z "$P_IP" ]; do
        read -p "Printer IP Address: " P_IP
    done
    
    P_CODE=""
    while [ -z "$P_CODE" ]; do
        read -p "Access Code: " P_CODE
    done
    
    P_SERIAL=""
    while [ -z "$P_SERIAL" ]; do
        read -p "Serial Number: " P_SERIAL
    done
    
    echo ""
    echo "You entered:"
    echo "  Name:   $P_NAME"
    echo "  IP:     $P_IP"
    echo "  Code:   $P_CODE"
    echo "  Serial: $P_SERIAL"
    echo ""
}

# Function to update camera IP in dashboards
update_camera_ip() {
    local LXC_IP="$1"
    echo ""
    echo "Updating camera feed URL in Grafana dashboards..."
    if [ -f "grafana/a1-dashboard.json" ]; then
        # Use different delimiter and escape dots in IP pattern
        sed -i "s#http://[0-9.]\+:9101/camera\.html#http://$LXC_IP:9101/camera.html#g" grafana/a1-dashboard.json
        echo "  ✓ Updated a1-dashboard.json"
    fi
    if [ -f "grafana/comprehensive-dashboard.json" ]; then
        sed -i "s#http://[0-9.]\+:9101/camera\.html#http://$LXC_IP:9101/camera.html#g" grafana/comprehensive-dashboard.json
        echo "  ✓ Updated comprehensive-dashboard.json"
    fi
    echo "  Camera feed URL: http://$LXC_IP:9101/camera.html"
}

# Main Configuration Logic
if [ ! -f config.yaml ]; then
    # Case 1: No config exists -> Create new
    echo "No configuration found. Starting fresh setup."
    write_config_header
    ask_printer_details
    append_printer_config "$P_NAME" "$P_IP" "$P_CODE" "$P_SERIAL"
    
    # Get LXC IP and update camera URLs
    echo ""
    echo "Now let's configure the camera feed for Grafana dashboards."
    LXC_IP=$(hostname -I | awk '{print $1}')
    echo "Detected LXC IP: $LXC_IP"
    read -p "Is this correct? [Y/n]: " CONFIRM_IP
    if [[ "$CONFIRM_IP" =~ ^[Nn] ]]; then
        read -p "Enter LXC IP address: " LXC_IP
    fi
    update_camera_ip "$LXC_IP"
else
    # Case 2: Config exists -> Ask what to do
    echo "Configuration file exists."
    echo "1. Add another printer"
    echo "2. Reset and Reconfigure (Fixes empty/broken config)"
    echo "3. Skip configuration"
    read -p "Choose [1-3]: " CHOICE

    case "$CHOICE" in
        1)
            ask_printer_details
            append_printer_config "$P_NAME" "$P_IP" "$P_CODE" "$P_SERIAL"
            ;;
        2)
            write_config_header
            ask_printer_details
            append_printer_config "$P_NAME" "$P_IP" "$P_CODE" "$P_SERIAL"
            
            # Update camera IP when reconfiguring
            echo ""
            LXC_IP=$(hostname -I | awk '{print $1}')
            echo "Detected LXC IP: $LXC_IP"
            read -p "Update camera feed URL with this IP? [Y/n]: " CONFIRM_IP
            if [[ ! "$CONFIRM_IP" =~ ^[Nn] ]]; then
                update_camera_ip "$LXC_IP"
            fi
            ;;
        *)
            echo "Skipping configuration."
            ;;
    esac
fi

echo ""
echo "======================================"
echo "Installing Systemd Service"
echo "======================================"
cp systemd/bambulab-prometheus.service /etc/systemd/system/
systemctl daemon-reload
echo "  ✓ Service installed"

# Enable and manage service
echo ""
echo "======================================"
echo "Service Management"
echo "======================================"

systemctl enable bambulab-prometheus
systemctl restart bambulab-prometheus

echo "Service restarted. Checking status..."
sleep 2
systemctl status bambulab-prometheus --no-pager

echo ""
echo "Installation Complete."
echo "If the service is not running, check /opt/bambulab-prometheus/config.yaml"
