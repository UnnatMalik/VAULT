#!/usr/bin/env python3
"""
SMART CLI Interface - Command line interface for SMART monitoring
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from smart_worker import SMARTMonitor
from smart_monitor import SMARTStatus, DriveType


def print_smart_data(smart_data, verbose=False):
    """Print SMART data in a formatted way"""
    print(f"\n{'='*60}")
    print(f"SMART Data for {smart_data.device_path}")
    print(f"{'='*60}")
    
    # Device information
    print(f"Model:          {smart_data.device_model}")
    print(f"Serial:         {smart_data.serial_number}")
    print(f"Firmware:       {smart_data.firmware_version}")
    print(f"Capacity:       {smart_data.capacity}")
    print(f"Type:           {smart_data.drive_type.value}")
    print(f"Last Updated:   {smart_data.last_updated.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Health status
    print(f"\n{'Health Status':=^40}")
    status_color = ""
    if smart_data.smart_status == SMARTStatus.PASSED:
        status_color = "✅"
    elif smart_data.smart_status == SMARTStatus.FAILED:
        status_color = "❌"
    elif smart_data.smart_status == SMARTStatus.WARNING:
        status_color = "⚠️"
    else:
        status_color = "❓"
    
    print(f"SMART Status:   {status_color} {smart_data.smart_status.value}")
    
    health_color = ""
    if smart_data.health_score >= 80:
        health_color = "✅"
    elif smart_data.health_score >= 50:
        health_color = "⚠️"
    else:
        health_color = "❌"
    
    print(f"Health Score:   {health_color} {smart_data.health_score:.1f}%")
    
    # Key metrics
    print(f"\n{'Key Metrics':=^40}")
    if smart_data.temperature:
        temp_color = "🌡️"
        if smart_data.temperature > 60:
            temp_color = "🔥"
        elif smart_data.temperature > 50:
            temp_color = "⚠️"
        print(f"Temperature:    {temp_color} {smart_data.temperature}°C")
    else:
        print(f"Temperature:    N/A")
    
    if smart_data.power_on_hours:
        hours = smart_data.power_on_hours
        days = hours // 24
        print(f"Power On Hours: {hours:,} ({days:,} days)")
    else:
        print(f"Power On Hours: N/A")
    
    if smart_data.power_cycle_count:
        print(f"Power Cycles:   {smart_data.power_cycle_count:,}")
    else:
        print(f"Power Cycles:   N/A")
    
    if smart_data.ssd_life_left:
        life_color = "✅" if smart_data.ssd_life_left > 80 else "⚠️" if smart_data.ssd_life_left > 50 else "❌"
        print(f"SSD Life Left:  {life_color} {smart_data.ssd_life_left}%")
    
    # Issues
    issues = []
    if smart_data.reallocated_sectors and smart_data.reallocated_sectors > 0:
        issues.append(f"Reallocated sectors: {smart_data.reallocated_sectors}")
    if smart_data.pending_sectors and smart_data.pending_sectors > 0:
        issues.append(f"Pending sectors: {smart_data.pending_sectors}")
    if smart_data.bad_blocks and smart_data.bad_blocks > 0:
        issues.append(f"Bad blocks: {smart_data.bad_blocks}")
    
    if issues:
        print(f"\n{'Issues Found':=^40}")
        for issue in issues:
            print(f"❌ {issue}")
    else:
        print(f"\n✅ No critical issues detected")
    
    # Verbose output
    if verbose and smart_data.attributes:
        print(f"\n{'SMART Attributes':=^60}")
        print(f"{'ID':<3} {'Attribute':<25} {'Value':<5} {'Worst':<5} {'Thresh':<6} {'Raw Value':<15} {'Status'}")
        print("-" * 80)
        
        for attr_id, attr in sorted(smart_data.attributes.items()):
            status = "FAIL" if attr.is_critical else "OK"
            status_symbol = "❌" if attr.is_critical else "✅"
            
            print(f"{attr.id:<3} {attr.name:<25} {attr.value:<5} {attr.worst:<5} {attr.threshold:<6} "
                  f"{str(attr.raw_value):<15} {status_symbol} {status}")


def print_health_report(report):
    """Print health report in a formatted way"""
    print(f"\n{'='*60}")
    print(f"Health Report for {report['device_info']['path']}")
    print(f"{'='*60}")
    
    # Device info
    info = report['device_info']
    print(f"Model:     {info['model']}")
    print(f"Serial:    {info['serial']}")
    print(f"Capacity:  {info['capacity']}")
    print(f"Type:      {info['type']}")
    
    # Current status
    status = report['current_status']
    print(f"\n{'Current Status':=^40}")
    print(f"SMART Status:   {status['smart_status']}")
    print(f"Health Score:   {status['health_score']:.1f}%")
    if status['temperature']:
        print(f"Temperature:    {status['temperature']}°C")
    if status['power_on_hours']:
        print(f"Power On Hours: {status['power_on_hours']:,}")
    if status['ssd_life_left']:
        print(f"SSD Life Left:  {status['ssd_life_left']}%")
    
    # Trend analysis
    trend = report['trend_analysis']
    print(f"\n{'Trend Analysis':=^40}")
    print(f"Direction:      {trend['direction'].upper()}")
    print(f"Data Points:    {trend['data_points']}")
    print(f"Monitoring:     {trend['monitoring_days']} days")
    
    # Issues
    issues = report['issues']
    if issues['critical']:
        print(f"\n{'Critical Issues':=^40}")
        for issue in issues['critical']:
            print(f"❌ {issue}")
    
    if issues['warnings']:
        print(f"\n{'Warnings':=^40}")
        for warning in issues['warnings']:
            print(f"⚠️ {warning}")
    
    if not issues['critical'] and not issues['warnings']:
        print(f"\n✅ No issues detected")
    
    # Recommendations
    print(f"\n{'Recommendations':=^40}")
    for rec in report['recommendations']:
        print(f"💡 {rec}")
    
    # Alerts
    if 'alerts' in report and report['alerts']:
        print(f"\n{'Unacknowledged Alerts':=^40}")
        for alert in report['alerts']:
            severity_symbol = "❌" if alert['severity'] == 'critical' else "⚠️"
            print(f"{severity_symbol} {alert['message']} ({alert['timestamp']})")


def main():
    parser = argparse.ArgumentParser(description="SMART Drive Health Monitoring CLI")
    parser.add_argument('--list-drives', action='store_true', 
                       help='List all available drives for SMART monitoring')
    parser.add_argument('--check-deps', action='store_true',
                       help='Check system dependencies for SMART monitoring')
    parser.add_argument('--device', '-d', type=str,
                       help='Specific device path to monitor (e.g., /dev/disk0)')
    parser.add_argument('--all-devices', action='store_true',
                       help='Show SMART data for all available devices')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Show detailed SMART attributes')
    parser.add_argument('--json', action='store_true',
                       help='Output data in JSON format')
    parser.add_argument('--health-report', action='store_true',
                       help='Generate comprehensive health report')
    parser.add_argument('--history', type=int, metavar='DAYS',
                       help='Show historical data for specified days')
    parser.add_argument('--start-monitoring', action='store_true',
                       help='Start background monitoring (requires GUI)')
    parser.add_argument('--alerts', action='store_true',
                       help='Show unacknowledged alerts')
    
    args = parser.parse_args()
    
    # Initialize SMART monitor
    try:
        smart_monitor = SMARTMonitor()
    except Exception as e:
        print(f"❌ Failed to initialize SMART monitor: {e}")
        return 1
    
    # Check dependencies
    if args.check_deps:
        print("Checking SMART monitoring dependencies...")
        compatible, missing = smart_monitor.check_system_compatibility()
        
        if compatible:
            print("✅ All dependencies satisfied!")
        else:
            print("❌ Missing dependencies:")
            for dep in missing:
                print(f"  - {dep}")
        return 0 if compatible else 1
    
    # List available drives
    if args.list_drives:
        print("Available drives for SMART monitoring:")
        drives = smart_monitor.get_available_drives()
        
        if not drives:
            print("❌ No drives found or SMART tools not available")
            return 1
        
        for i, drive in enumerate(drives, 1):
            print(f"{i}. {drive}")
        return 0
    
    # Show alerts
    if args.alerts:
        alerts = smart_monitor.get_unacknowledged_alerts()
        
        if not alerts:
            print("✅ No unacknowledged alerts")
            return 0
        
        print(f"Found {len(alerts)} unacknowledged alerts:")
        for alert in alerts:
            severity_symbol = "❌" if alert['severity'] == 'critical' else "⚠️"
            timestamp = datetime.fromisoformat(alert['timestamp']).strftime('%Y-%m-%d %H:%M')
            print(f"{severity_symbol} [{alert['device_path']}] {alert['message']} ({timestamp})")
        return 0
    
    # Get target devices
    target_devices = []
    if args.device:
        target_devices = [args.device]
    elif args.all_devices:
        target_devices = smart_monitor.get_available_drives()
        if not target_devices:
            print("❌ No drives found for monitoring")
            return 1
    else:
        # Default to showing help if no specific action
        if not any([args.start_monitoring, args.history]):
            parser.print_help()
            return 0
    
    # Process each device
    for device_path in target_devices:
        try:
            if args.health_report:
                # Generate health report
                report = smart_monitor.generate_health_report(device_path)
                
                if 'error' in report:
                    print(f"❌ Error generating report for {device_path}: {report['error']}")
                    continue
                
                if args.json:
                    print(json.dumps(report, indent=2))
                else:
                    print_health_report(report)
            
            elif args.history:
                # Show historical data
                history = smart_monitor.get_device_history(device_path, args.history)
                
                if args.json:
                    print(json.dumps(history, indent=2, default=str))
                else:
                    print(f"\nHistorical data for {device_path} (last {args.history} days):")
                    print("-" * 80)
                    
                    if not history:
                        print("No historical data available")
                    else:
                        print(f"{'Timestamp':<20} {'Health':<8} {'Temp':<6} {'Status':<10} {'Hours':<10}")
                        print("-" * 60)
                        
                        for record in history[:10]:  # Show last 10 records
                            timestamp = datetime.fromisoformat(record['timestamp']).strftime('%Y-%m-%d %H:%M')
                            health = f"{record['health_score']:.1f}%" if record['health_score'] else "N/A"
                            temp = f"{record['temperature']}°C" if record['temperature'] else "N/A"
                            status = record['smart_status'] or "N/A"
                            hours = str(record['power_on_hours']) if record['power_on_hours'] else "N/A"
                            
                            print(f"{timestamp:<20} {health:<8} {temp:<6} {status:<10} {hours:<10}")
            
            else:
                # Show current SMART data
                smart_data = smart_monitor.get_smart_data(device_path)
                
                if not smart_data:
                    print(f"❌ Unable to collect SMART data for {device_path}")
                    continue
                
                if args.json:
                    print(json.dumps(smart_data.to_dict(), indent=2, default=str))
                else:
                    print_smart_data(smart_data, args.verbose)
        
        except Exception as e:
            print(f"❌ Error processing {device_path}: {e}")
            continue
    
    # Start monitoring
    if args.start_monitoring:
        print("Starting background SMART monitoring...")
        try:
            drives = smart_monitor.get_available_drives()
            if drives:
                smart_monitor.start_monitoring(drives)
                print(f"✅ Monitoring started for {len(drives)} drives")
                print("Press Ctrl+C to stop monitoring")
                
                # Keep running until interrupted
                import time
                try:
                    while True:
                        time.sleep(1)
                except KeyboardInterrupt:
                    print("\nStopping monitoring...")
                    smart_monitor.stop_monitoring()
                    print("✅ Monitoring stopped")
            else:
                print("❌ No drives available for monitoring")
                return 1
        except Exception as e:
            print(f"❌ Failed to start monitoring: {e}")
            return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
