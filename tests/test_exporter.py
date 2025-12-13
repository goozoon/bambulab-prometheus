"""
Unit tests for Bambulab Prometheus Exporter
"""

import pytest
from unittest.mock import Mock, patch
import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from exporter import BambuExporter, BambuMetrics


class TestBambuMetrics:
    """Test BambuMetrics class."""
    
    def test_metrics_initialization(self):
        """Test that metrics are properly initialized."""
        metrics = BambuMetrics("test_printer")
        assert metrics.printer_name == "test_printer"
        assert metrics.nozzle_temp is not None
        assert metrics.bed_temp is not None
        assert metrics.print_progress is not None


class TestBambuExporter:
    """Test BambuExporter class."""
    
    def test_config_loading(self, tmp_path):
        """Test configuration loading."""
        config_file = tmp_path / "test_config.yaml"
        config_file.write_text("""
exporter:
  port: 9100
  log_level: INFO
  update_interval: 5

printers:
  - name: "test_printer"
    ip: "192.168.1.100"
    access_code: "12345678"
    serial: "TEST123"
    enabled: true
""")
        
        exporter = BambuExporter(str(config_file))
        assert exporter.config['exporter']['port'] == 9100
        assert len(exporter.config['printers']) == 1
        assert exporter.config['printers'][0]['name'] == "test_printer"
    
    @patch('exporter.bl.Printer')
    def test_connect_printers(self, mock_printer_class, tmp_path):
        """Test printer connection."""
        config_file = tmp_path / "test_config.yaml"
        config_file.write_text("""
exporter:
  port: 9100

printers:
  - name: "test_printer"
    ip: "192.168.1.100"
    access_code: "12345678"
    serial: "TEST123"
    enabled: true
""")
        
        mock_printer = Mock()
        mock_printer_class.return_value = mock_printer
        
        exporter = BambuExporter(str(config_file))
        exporter.connect_printers()
        
        mock_printer.connect.assert_called_once()
        assert "test_printer" in exporter.printers
        assert "test_printer" in exporter.metrics


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
