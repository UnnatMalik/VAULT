# VAULT SMART Monitoring Setup Guide

## Overview

VAULT's SMART (Self-Monitoring, Analysis and Reporting Technology) module provides comprehensive drive health monitoring with cross-platform support for macOS, Linux, and Windows. This guide covers installation, configuration, and usage of the SMART monitoring system.

## Features

### Core Features
- **Real-time SMART data collection** from all supported drives
- **Cross-platform compatibility** (macOS, Linux, Windows)
- **Health scoring algorithm** with predictive analytics
- **Background monitoring service** with configurable intervals
- **Alert system** for critical drive conditions
- **Historical data tracking** with SQLite database
- **GUI integration** with the main VAULT interface
- **CLI interface** for command-line operations
- **Report integration** with wipe certificates and refurbish reports

### Monitored Parameters
- **SMART Status** - Overall drive health status
- **Health Score** - Calculated health percentage (0-100%)
- **Temperature** - Current drive temperature
- **Power On Hours** - Total operational time
- **Power Cycle Count** - Number of power cycles
- **SSD Life Left** - Remaining SSD lifespan percentage
- **Reallocated Sectors** - Bad sectors that have been remapped
- **Pending Sectors** - Sectors waiting for reallocation
- **Critical SMART Attributes** - All standard SMART parameters

## System Requirements

### Dependencies by Platform

#### macOS
```bash
# Install smartmontools via Homebrew
brew install smartmontools

# Verify installation
smartctl --version
```

#### Linux (Ubuntu/Debian)
```bash
# Install smartmontools
sudo apt update
sudo apt install smartmontools

# For RHEL/CentOS/Fedora
sudo yum install smartmontools
# OR
sudo dnf install smartmontools

# For Arch Linux
sudo pacman -S smartmontools

# Verify installation
smartctl --version
```

#### Windows
```bash
# Install WMI support (usually pre-installed)
pip install WMI

# Optional: Install smartmontools for Windows
# Download from: https://www.smartmontools.org/wiki/Download#InstalltheWindowspackage
```

### Python Dependencies
```bash
# Core dependencies (automatically installed with VAULT)
pip install PySide6 psutil sqlite3

# Optional for enhanced Windows support
pip install WMI
```

## Installation

### 1. Verify SMART Module Installation
The SMART module is included with VAULT. Verify it's properly installed:

```bash
cd /path/to/VAULT
python3 -c "from smart_monitor import SMARTMonitor; print('SMART module available')"
```

### 2. Check System Compatibility
```bash
# Using the CLI tool
python3 smart_cli.py --check-deps

# Or using Python
python3 -c "
from smart_worker import SMARTMonitor
monitor = SMARTMonitor()
compatible, missing = monitor.check_system_compatibility()
print(f'Compatible: {compatible}')
if missing: print(f'Missing: {missing}')
"
```

### 3. Test Drive Detection
```bash
# List available drives
python3 smart_cli.py --list-drives

# Test SMART data collection
python3 smart_cli.py --device /dev/disk0 --verbose
```

## Configuration

### GUI Configuration
1. **Open VAULT application**
2. **Navigate to SMART tab**
3. **Configure monitoring settings** for each drive:
   - Enable/disable monitoring
   - Set health score threshold (default: 20%)
   - Set temperature threshold (default: 60°C)
   - Set monitoring interval (default: 300 seconds)

### CLI Configuration
```bash
# View current configuration for a device
python3 smart_cli.py --device /dev/disk0 --health-report

# Start background monitoring
python3 smart_cli.py --start-monitoring
```

### Database Configuration
The SMART module uses SQLite for data storage. Default location: `smart_history.db`

```python
# Custom database location
from smart_database import SMARTDatabase
db = SMARTDatabase("/custom/path/smart_data.db")
```

## Usage

### GUI Usage

#### Main SMART Tab
- **Overview dashboard** with drive health cards
- **Real-time monitoring** status
- **Drive health table** with color-coded status
- **Temperature monitoring** with alerts

#### Maintenance Tab Integration
- **Enhanced drive health table** with SMART data
- **Color-coded health indicators**
- **Temperature monitoring**
- **Real-time status updates**

### CLI Usage

#### Basic Commands
```bash
# Check all drives
python3 smart_cli.py --all-devices

# Check specific drive with details
python3 smart_cli.py --device /dev/disk0 --verbose

# Generate health report
python3 smart_cli.py --device /dev/disk0 --health-report

# View historical data
python3 smart_cli.py --device /dev/disk0 --history 30

# Check for alerts
python3 smart_cli.py --alerts

# Output as JSON
python3 smart_cli.py --device /dev/disk0 --json
```

#### Background Monitoring
```bash
# Start monitoring all drives
python3 smart_cli.py --start-monitoring

# Monitor runs until Ctrl+C
```

### Programmatic Usage

#### Basic SMART Data Collection
```python
from smart_worker import SMARTMonitor

# Initialize monitor
monitor = SMARTMonitor()

# Get available drives
drives = monitor.get_available_drives()
print(f"Found {len(drives)} drives: {drives}")

# Get SMART data for a specific drive
smart_data = monitor.get_smart_data('/dev/disk0')
if smart_data:
    print(f"Health Score: {smart_data.health_score}%")
    print(f"Temperature: {smart_data.temperature}°C")
    print(f"SMART Status: {smart_data.smart_status.value}")
```

#### Background Monitoring with Alerts
```python
from smart_worker import SMARTMonitor

def alert_callback(alert_data):
    print(f"ALERT: {alert_data['device_path']} - {alert_data['message']}")

monitor = SMARTMonitor()
monitor.add_alert_callback(alert_callback)
monitor.start_monitoring(['/dev/disk0', '/dev/disk1'], interval=300)

# Monitoring runs in background thread
```

#### Health Report Generation
```python
from smart_worker import SMARTMonitor

monitor = SMARTMonitor()
report = monitor.generate_health_report('/dev/disk0')

print(f"Device: {report['device_info']['model']}")
print(f"Health: {report['current_status']['health_score']}%")
print(f"Trend: {report['trend_analysis']['direction']}")

for issue in report['issues']['critical']:
    print(f"CRITICAL: {issue}")

for rec in report['recommendations']:
    print(f"RECOMMENDATION: {rec}")
```

## Alert System

### Alert Types
- **Critical**: SMART failure, health score < 10%
- **Warning**: Health score < threshold, high temperature
- **Info**: Monitoring status changes

### Alert Configuration
```python
# Configure device-specific thresholds
config = {
    'monitoring_enabled': True,
    'alert_threshold_health': 20.0,  # Health score threshold
    'alert_threshold_temp': 60,      # Temperature threshold (°C)
    'monitoring_interval': 300       # Check interval (seconds)
}

monitor.configure_device_monitoring('/dev/disk0', config)
```

### Alert Handling
```python
# Get unacknowledged alerts
alerts = monitor.get_unacknowledged_alerts()

for alert in alerts:
    print(f"{alert['severity']}: {alert['message']}")
    
    # Acknowledge alert
    monitor.acknowledge_alert(alert['id'])
```

## Integration with VAULT Reports

### Wipe Certificates
SMART data is automatically included in wipe certificates when available:

```python
from smart_integration import add_smart_data_to_certificate

certificate_data = {
    'wipe_id': 'example-wipe-id',
    'timestamp': '2024-01-01T00:00:00Z',
    # ... other certificate data
}

# Add SMART data
enhanced_certificate = add_smart_data_to_certificate(certificate_data)
```

### Refurbish Reports
```python
from smart_integration import enhance_refurbish_report_with_smart

report_data = {
    'system_info': {...},
    'wipe_summary': {...},
    # ... other report data
}

# Enhance with SMART data
enhanced_report = enhance_refurbish_report_with_smart(report_data)
```

## Troubleshooting

### Common Issues

#### 1. "smartctl not found"
```bash
# macOS
brew install smartmontools

# Linux
sudo apt install smartmontools

# Verify PATH
which smartctl
```

#### 2. "Permission denied" errors
```bash
# Run with appropriate permissions
sudo python3 smart_cli.py --device /dev/disk0

# Or add user to disk group (Linux)
sudo usermod -a -G disk $USER
```

#### 3. "No drives found"
```bash
# Check if drives are detected by system
# macOS
diskutil list

# Linux
lsblk

# Verify SMART support
smartctl --scan
```

#### 4. "SMART not supported"
Some drives (especially USB/external) may not support SMART:
```bash
# Check SMART availability
smartctl -i /dev/disk0
```

### Debug Mode
```bash
# Enable debug logging
export PYTHONPATH=/path/to/VAULT
python3 -c "
import logging
logging.basicConfig(level=logging.DEBUG)
from smart_worker import SMARTMonitor
monitor = SMARTMonitor()
data = monitor.get_smart_data('/dev/disk0')
"
```

### Log Files
- **Application logs**: Check VAULT's main log output
- **SMART database**: `smart_history.db` in VAULT directory
- **System logs**: 
  - macOS: `/var/log/system.log`
  - Linux: `/var/log/syslog`

## Performance Considerations

### Monitoring Intervals
- **Default**: 300 seconds (5 minutes)
- **Minimum recommended**: 60 seconds
- **For critical systems**: 30 seconds
- **For normal use**: 300-600 seconds

### Database Maintenance
```python
from smart_database import SMARTDatabase

db = SMARTDatabase()

# Clean old data (keeps last 90 days)
db.cleanup_old_data(days_to_keep=90)

# Get database statistics
stats = db.get_statistics()
print(f"Total records: {stats['total_history_records']}")
```

### Resource Usage
- **CPU**: Minimal impact (< 1% during collection)
- **Memory**: ~10-50MB depending on number of drives
- **Disk**: ~1MB per drive per month of monitoring data

## Security Considerations

### Permissions
- SMART data collection requires **read access** to drive devices
- No **write access** to drives is required
- **Administrative privileges** may be needed on some systems

### Data Privacy
- SMART data contains **drive serial numbers** and usage patterns
- Historical data is stored **locally** in SQLite database
- **No data is transmitted** externally by the SMART module

### Network Security
- SMART monitoring operates **entirely offline**
- No network connections are made
- All data remains on the local system

## Advanced Configuration

### Custom Health Scoring
```python
# Modify health calculation weights
from smart_parser import SMARTParser

class CustomSMARTParser(SMARTParser):
    def calculate_health_score(self, attributes, status):
        # Custom health scoring logic
        base_score = 100.0
        # ... custom calculations
        return base_score
```

### Custom Alert Conditions
```python
def custom_alert_check(smart_data):
    alerts = []
    
    # Custom alert logic
    if smart_data.power_on_hours > 50000:  # 5+ years
        alerts.append(('warning', 'Drive approaching end of typical lifespan'))
    
    return alerts

# Add to monitoring worker
worker._custom_alert_checks.append(custom_alert_check)
```

### Integration with External Systems
```python
# Export SMART data to external monitoring
def export_to_external_system(smart_data):
    # Convert to external format
    external_data = {
        'device': smart_data.device_path,
        'health': smart_data.health_score,
        'timestamp': smart_data.last_updated.isoformat()
    }
    
    # Send to external system
    # requests.post('https://monitoring.example.com/api/smart', json=external_data)

# Add export callback
monitor.add_alert_callback(export_to_external_system)
```

## API Reference

### Core Classes

#### SMARTMonitor
Main interface for SMART monitoring operations.

#### SMARTData
Data structure containing complete SMART information for a drive.

#### SMARTCollector
Cross-platform SMART data collection engine.

#### SMARTDatabase
SQLite database interface for historical data storage.

### Key Methods

#### SMARTMonitor Methods
- `get_available_drives()` - List drives available for monitoring
- `get_smart_data(device_path)` - Get current SMART data
- `start_monitoring(devices, interval)` - Start background monitoring
- `generate_health_report(device_path)` - Generate comprehensive report

#### SMARTData Properties
- `health_score` - Overall health percentage
- `smart_status` - SMART status enum
- `temperature` - Current temperature
- `attributes` - Dictionary of SMART attributes

## Support and Contributing

### Getting Help
1. Check this documentation
2. Review troubleshooting section
3. Check VAULT's main documentation
4. Submit issues with detailed system information

### Contributing
1. Follow VAULT's contribution guidelines
2. Include tests for new features
3. Update documentation
4. Ensure cross-platform compatibility

### System Information for Bug Reports
```bash
# Collect system info for bug reports
python3 -c "
import platform
from smart_worker import SMARTMonitor

print(f'OS: {platform.system()} {platform.release()}')
print(f'Python: {platform.python_version()}')

monitor = SMARTMonitor()
compatible, missing = monitor.check_system_compatibility()
print(f'SMART Compatible: {compatible}')
if missing: print(f'Missing deps: {missing}')

drives = monitor.get_available_drives()
print(f'Available drives: {len(drives)}')
"
```

---

## Quick Start Checklist

- [ ] Install system dependencies (`smartmontools`)
- [ ] Verify SMART module installation
- [ ] Check system compatibility
- [ ] Test drive detection
- [ ] Configure monitoring settings
- [ ] Start monitoring service
- [ ] Verify alerts are working
- [ ] Review historical data collection

For additional help, refer to VAULT's main documentation or submit an issue with your system information.
