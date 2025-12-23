#!/usr/bin/env python3
"""
Bambulab Prometheus Exporter
A lightweight Prometheus exporter for Bambu Lab 3D printers.
"""

import time
import logging
import signal
import sys
from typing import Dict, List, Optional
from io import BytesIO
from threading import Thread
import yaml
from prometheus_client import start_http_server, Gauge, Counter, Enum, Info
from flask import Flask, send_file, Response
import bambulabs_api as bl


class BambuMetrics:
    """Prometheus metrics for Bambu Lab printers."""
    
    def __init__(self, printer_name: str):
        """Initialize metrics with printer-specific labels."""
        labels = ['printer']
        
        # Temperature metrics
        self.nozzle_temp = Gauge(
            'bambu_nozzle_temperature_celsius',
            'Current nozzle temperature',
            labels
        )
        self.nozzle_target_temp = Gauge(
            'bambu_nozzle_target_temperature_celsius',
            'Target nozzle temperature',
            labels
        )
        self.bed_temp = Gauge(
            'bambu_bed_temperature_celsius',
            'Current bed temperature',
            labels
        )
        self.bed_target_temp = Gauge(
            'bambu_bed_target_temperature_celsius',
            'Target bed temperature',
            labels
        )
        self.chamber_temp = Gauge(
            'bambu_chamber_temperature_celsius',
            'Chamber temperature',
            labels
        )
        
        # Print progress metrics
        self.print_progress = Gauge(
            'bambu_print_progress_percent',
            'Print completion percentage',
            labels
        )
        self.print_remaining_time = Gauge(
            'bambu_print_remaining_time_seconds',
            'Estimated time remaining for print',
            labels
        )
        self.current_layer = Gauge(
            'bambu_current_layer',
            'Current layer number',
            labels
        )
        self.total_layers = Gauge(
            'bambu_total_layers',
            'Total layers in print',
            labels
        )
        
        # Speed metrics
        self.print_speed = Gauge(
            'bambu_print_speed_percent',
            'Current print speed modifier',
            labels
        )
        
        # State metrics
        self.printer_online = Gauge(
            'bambu_online',
            'Printer connectivity status',
            labels
        )
        self.printer_state = Gauge(
            'bambu_printer_state',
            'Detailed printer state (0=IDLE, 1=PRINTING, 2=PAUSED, 3=FINISH, 4=FAILED)',
            labels
        )
        self.wifi_signal = Gauge(
            'bambu_wifi_signal_strength_dbm',
            'WiFi signal strength',
            labels
        )
        self.chamber_light = Gauge(
            'bambu_chamber_light',
            'Chamber light state (0=off, 1=on)',
            labels
        )
        self.error_code = Gauge(
            'bambu_error_code',
            'Current error code (0=no error)',
            labels
        )
        
        # Statistics
        self.total_prints = Counter(
            'bambu_total_prints',
            'Lifetime print count',
            labels
        )
        
        # Info metrics (stored as labels in gauges for easy querying)
        self.current_file = Gauge(
            'bambu_current_file_info',
            'Current file being printed (1=active, value in label)',
            labels + ['filename']
        )
        self.nozzle_info = Gauge(
            'bambu_nozzle_info',
            'Nozzle information (1=active, details in labels)',
            labels + ['nozzle_type', 'nozzle_diameter_mm']
        )
        self.printer_info = Info(
            'bambu_printer',
            'Printer information',
            labels
        )
        
        self.printer_name = printer_name


class BambuExporter:
    """Main exporter class for Bambu Lab printers."""
    
    def __init__(self, config_path: str = 'config.yaml'):
        """Initialize the exporter with configuration."""
        self.config = self._load_config(config_path)
        self.logger = self._setup_logging()
        self.printers: Dict[str, bl.Printer] = {}
        self.metrics: Dict[str, BambuMetrics] = {}
        self.running = False
        self.flask_app = Flask(__name__)
        self._setup_flask_routes()
        
    def _load_config(self, config_path: str) -> dict:
        """Load configuration from YAML file."""
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    
    def _setup_logging(self) -> logging.Logger:
        """Setup logging configuration."""
        log_level = self.config.get('exporter', {}).get('log_level', 'INFO')
        logging.basicConfig(
            level=getattr(logging, log_level),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        return logging.getLogger(__name__)
    
    def _setup_flask_routes(self):
        """Setup Flask routes for camera feed."""
        
        @self.flask_app.route('/camera')
        def camera_feed():
            """Serve camera image from the first available printer."""
            try:
                # Get first available printer
                if not self.printers:
                    return Response("No printers connected", status=503)
                
                printer = next(iter(self.printers.values()))
                
                # Get camera image
                img = printer.get_camera_image()
                if img is None:
                    return Response("Camera image not available", status=404)
                
                # Convert PIL image to JPEG bytes
                img_io = BytesIO()
                img.save(img_io, 'JPEG', quality=85)
                img_io.seek(0)
                
                return send_file(img_io, mimetype='image/jpeg')
                
            except Exception as e:
                self.logger.error(f"Error serving camera image: {e}")
                return Response(f"Error: {str(e)}", status=500)
        
        @self.flask_app.route('/camera.html')
        def camera_html():
            """Serve HTML page with auto-refreshing camera."""
            html = '''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Printer Camera</title>
    <style>
        body { margin: 0; padding: 0; background: #000; display: flex; justify-content: center; align-items: center; height: 100vh; }
        img { max-width: 100%; max-height: 100vh; object-fit: contain; }
    </style>
</head>
<body>
    <img id="camera" src="/camera">
    <script>
        setInterval(function() {
            document.getElementById('camera').src = '/camera?' + Date.now();
        }, 2000);
    </script>
</body>
</html>
            '''
            return Response(html, mimetype='text/html')
        
        @self.flask_app.route('/health')
        def health():
            """Health check endpoint."""
            return {'status': 'ok', 'printers': len(self.printers)}
    
    def connect_printers(self):
        """Connect to all enabled printers."""
        for printer_config in self.config.get('printers', []):
            if not printer_config.get('enabled', True):
                continue
                
            name = printer_config['name']
            ip = printer_config['ip']
            access_code = printer_config['access_code']
            serial = printer_config['serial']
            
            self.logger.info(f"Connecting to printer '{name}' at {ip}")
            
            try:
                printer = bl.Printer(ip, access_code, serial)
                printer.connect()
                
                # Wait a moment for connection to establish
                time.sleep(2)
                
                self.printers[name] = printer
                self.metrics[name] = BambuMetrics(name)
                
                # Set initial online status
                self.metrics[name].printer_online.labels(printer=name).set(1)
                
                self.logger.info(f"Successfully connected to printer '{name}'")
                
            except Exception as e:
                self.logger.error(f"Failed to connect to printer '{name}': {e}")
    
    def disconnect_printers(self):
        """Disconnect from all printers."""
        for name, printer in self.printers.items():
            try:
                self.logger.info(f"Disconnecting from printer '{name}'")
                printer.disconnect()
            except Exception as e:
                self.logger.error(f"Error disconnecting from printer '{name}': {e}")
    
    def update_metrics(self):
        """Update metrics for all connected printers."""
        for name, printer in self.printers.items():
            try:
                metrics = self.metrics[name]
                
                # Check if printer is connected
                if not printer.mqtt_client_connected():
                    self.logger.warning(f"Printer '{name}' not connected to MQTT")
                    metrics.printer_online.labels(printer=name).set(0)
                    
                    # Clear all metrics when printer is offline
                    metrics.nozzle_temp.labels(printer=name).set(0)
                    metrics.nozzle_target_temp.labels(printer=name).set(0)
                    metrics.bed_temp.labels(printer=name).set(0)
                    metrics.bed_target_temp.labels(printer=name).set(0)
                    metrics.chamber_temp.labels(printer=name).set(0)
                    metrics.print_progress.labels(printer=name).set(0)
                    metrics.print_remaining_time.labels(printer=name).set(0)
                    metrics.current_layer.labels(printer=name).set(0)
                    metrics.total_layers.labels(printer=name).set(0)
                    metrics.print_speed.labels(printer=name).set(0)
                    metrics.error_code.labels(printer=name).set(0)
                    metrics.printer_state.labels(printer=name).set(0)
                    continue
                
                # Check if we're actually receiving data (printer might be off but MQTT still connected)
                data_received = False
                
                # Temperature metrics - use individual getter methods
                try:
                    nozzle_temp = printer.get_nozzle_temperature()
                    if nozzle_temp is not None:
                        metrics.nozzle_temp.labels(printer=name).set(nozzle_temp)
                        data_received = True
                        # Note: API doesn't provide target temps via getter, only current
                except Exception as e:
                    self.logger.debug(f"Error getting nozzle temp for '{name}': {e}")
                
                try:
                    bed_temp = printer.get_bed_temperature()
                    if bed_temp is not None:
                        metrics.bed_temp.labels(printer=name).set(bed_temp)
                        data_received = True
                except Exception as e:
                    self.logger.debug(f"Error getting bed temp for '{name}': {e}")
                
                try:
                    chamber_temp = printer.get_chamber_temperature()
                    if chamber_temp is not None:
                        metrics.chamber_temp.labels(printer=name).set(chamber_temp)
                        data_received = True
                except Exception as e:
                    self.logger.debug(f"Error getting chamber temp for '{name}': {e}")
                
                # Set online status based on whether we received any data
                if data_received:
                    metrics.printer_online.labels(printer=name).set(1)
                else:
                    self.logger.warning(f"Printer '{name}' connected but not sending data (might be powered off)")
                    metrics.printer_online.labels(printer=name).set(0)
                    
                    # Clear all metrics when printer is offline to avoid stale data in Grafana
                    metrics.nozzle_temp.labels(printer=name).set(0)
                    metrics.nozzle_target_temp.labels(printer=name).set(0)
                    metrics.bed_temp.labels(printer=name).set(0)
                    metrics.bed_target_temp.labels(printer=name).set(0)
                    metrics.chamber_temp.labels(printer=name).set(0)
                    metrics.print_progress.labels(printer=name).set(0)
                    metrics.print_remaining_time.labels(printer=name).set(0)
                    metrics.current_layer.labels(printer=name).set(0)
                    metrics.total_layers.labels(printer=name).set(0)
                    metrics.print_speed.labels(printer=name).set(0)
                    metrics.error_code.labels(printer=name).set(0)
                    metrics.printer_state.labels(printer=name).set(0)
                    self.logger.debug(f"Cleared metrics for offline printer '{name}'")
                    continue
                
                # Print progress metrics
                try:
                    progress = printer.get_percentage()
                    if progress is not None:
                        metrics.print_progress.labels(printer=name).set(progress)
                except Exception as e:
                    self.logger.debug(f"Error getting progress for '{name}': {e}")
                
                try:
                    remaining_time = printer.get_time()
                    if remaining_time is not None:
                        # Convert minutes to seconds
                        metrics.print_remaining_time.labels(printer=name).set(remaining_time * 60)
                except Exception as e:
                    self.logger.debug(f"Error getting remaining time for '{name}': {e}")
                
                try:
                    current_layer = printer.current_layer_num()
                    if current_layer is not None:
                        metrics.current_layer.labels(printer=name).set(current_layer)
                except Exception as e:
                    self.logger.debug(f"Error getting current layer for '{name}': {e}")
                
                try:
                    total_layers = printer.total_layer_num()
                    if total_layers is not None:
                        metrics.total_layers.labels(printer=name).set(total_layers)
                except Exception as e:
                    self.logger.debug(f"Error getting total layers for '{name}': {e}")
                
                # Speed metrics
                try:
                    print_speed = printer.get_print_speed()
                    if print_speed is not None:
                        metrics.print_speed.labels(printer=name).set(print_speed)
                        self.logger.info(f"Printer '{name}' speed: {print_speed}%")
                    else:
                        self.logger.warning(f"Printer '{name}' speed is None")
                except Exception as e:
                    self.logger.warning(f"Error getting print speed for '{name}': {e}")
                
                # WiFi signal
                try:
                    wifi_signal = printer.wifi_signal()
                    if wifi_signal is not None:
                        # Convert from string like "-63dBm" to number
                        signal_str = str(wifi_signal).replace('dBm', '').strip()
                        metrics.wifi_signal.labels(printer=name).set(float(signal_str))
                except Exception as e:
                    self.logger.debug(f"Error getting WiFi signal for '{name}': {e}")
                
                # Chamber light
                try:
                    light_state = printer.get_light_state()
                    if light_state is not None:
                        # API returns string 'on' or 'off', not boolean
                        is_on = str(light_state).lower() == 'on'
                        metrics.chamber_light.labels(printer=name).set(1 if is_on else 0)
                except Exception as e:
                    self.logger.debug(f"Error getting light state for '{name}': {e}")
                
                # Detailed printer state
                try:
                    # Use get_state() instead of get_current_state() - get_current_state() returns stale data
                    state = printer.get_state()
                    
                    # Also check gcode_state attribute for more accurate state
                    gcode_state = None
                    try:
                        gcode_state = printer.gcode_state
                    except:
                        pass
                    
                    if state is not None:
                        # Map state enum to numeric value
                        state_mapping = {
                            'IDLE': 0,
                            'PRINTING': 1,
                            'RUNNING': 1,  # RUNNING is the same as PRINTING
                            'PAUSED': 2,
                            'FINISH': 3,
                            'FAILED': 4
                        }
                        state_str = str(state).upper()
                        
                        # Override with gcode_state if available
                        if gcode_state:
                            gcode_str = str(gcode_state).upper()
                            if gcode_str in state_mapping:
                                state_str = gcode_str
                        
                        state_value = state_mapping.get(state_str, 0)
                        metrics.printer_state.labels(printer=name).set(state_value)
                        self.logger.info(f"Printer '{name}' state: {state_str} -> {state_value} (gcode_state: {gcode_state})")
                except Exception as e:
                    self.logger.warning(f"Error getting printer state for '{name}': {e}")
                
                # Error code
                try:
                    error_code = printer.print_error_code()
                    if error_code is not None:
                        metrics.error_code.labels(printer=name).set(int(error_code) if error_code else 0)
                except Exception as e:
                    self.logger.debug(f"Error getting error code for '{name}': {e}")
                
                # Current file info
                try:
                    filename = printer.get_file_name()
                    if filename:
                        # Clear old values first
                        metrics.current_file._metrics.clear()
                        # Set new value with filename in label
                        metrics.current_file.labels(printer=name, filename=str(filename)).set(1)
                        self.logger.info(f"Printer '{name}' file: {filename}")
                    else:
                        self.logger.warning(f"Printer '{name}' filename is None/empty")
                except Exception as e:
                    self.logger.warning(f"Error getting file name for '{name}': {e}")
                
                # Nozzle info (static data)
                try:
                    nozzle_type = printer.nozzle_type()
                    nozzle_diameter = printer.nozzle_diameter()
                    if nozzle_type is not None and nozzle_diameter is not None:
                        # Clear old values first
                        metrics.nozzle_info._metrics.clear()
                        metrics.nozzle_info.labels(
                            printer=name,
                            nozzle_type=str(nozzle_type),
                            nozzle_diameter_mm=str(nozzle_diameter)
                        ).set(1)
                except Exception as e:
                    self.logger.debug(f"Error getting nozzle info for '{name}': {e}")
                
                self.logger.debug(f"Updated metrics for printer '{name}'")
                
            except Exception as e:
                self.logger.error(f"Error updating metrics for printer '{name}': {e}")
                self.metrics[name].printer_online.labels(printer=name).set(0)
    
    def run(self):
        """Run the exporter main loop."""
        self.running = True
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        # Start Prometheus HTTP server
        port = self.config.get('exporter', {}).get('port', 9100)
        bind_address = self.config.get('exporter', {}).get('bind_address', '0.0.0.0')
        
        self.logger.info(f"Starting Prometheus HTTP server on {bind_address}:{port}")
        start_http_server(port, addr=bind_address)
        
        # Start Flask server in background thread for camera feed
        flask_port = port + 1  # Use next port for Flask (9101 by default)
        self.logger.info(f"Starting camera server on {bind_address}:{flask_port}")
        flask_thread = Thread(
            target=lambda: self.flask_app.run(host=bind_address, port=flask_port, debug=False, use_reloader=False),
            daemon=True
        )
        flask_thread.start()
        
        # Connect to printers
        self.connect_printers()
        
        if not self.printers:
            self.logger.error("No printers connected. Exiting.")
            return
        
        # Main loop
        update_interval = self.config.get('exporter', {}).get('update_interval', 5)
        self.logger.info(f"Starting metric collection (interval: {update_interval}s)")
        
        while self.running:
            try:
                self.update_metrics()
                time.sleep(update_interval)
            except Exception as e:
                self.logger.error(f"Error in main loop: {e}")
                time.sleep(update_interval)
        
        # Cleanup
        self.disconnect_printers()
        self.logger.info("Exporter stopped")
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        self.logger.info(f"Received signal {signum}, shutting down...")
        self.running = False


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Bambulab Prometheus Exporter')
    parser.add_argument(
        '--config',
        default='config.yaml',
        help='Path to configuration file (default: config.yaml)'
    )
    
    args = parser.parse_args()
    
    try:
        exporter = BambuExporter(args.config)
        exporter.run()
    except FileNotFoundError:
        print(f"Error: Configuration file '{args.config}' not found")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nShutting down...")
        sys.exit(0)
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
