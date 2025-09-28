#!/usr/bin/env python3
"""
SMART Parser Module - Handles parsing of SMART data from different sources
"""

import re
import subprocess
from datetime import datetime
from typing import Dict, Optional

from smart_monitor import SMARTData, SMARTAttribute, SMARTStatus, DriveType


class SMARTParser:
    """Parser for SMART data from various sources"""
    
    def __init__(self, collector):
        self.collector = collector
        self.logger = collector.logger
    
    def get_macos_smart_data(self, device_path: str) -> Optional[SMARTData]:
        """Get SMART data on macOS using smartctl"""
        if not self.collector._smartctl_path:
            return None
        
        try:
            # Get basic device info
            info_cmd = [self.collector._smartctl_path, '-i', device_path]
            info_result = subprocess.run(info_cmd, capture_output=True, text=True, timeout=30)
            
            # Get SMART attributes
            smart_cmd = [self.collector._smartctl_path, '-A', device_path]
            smart_result = subprocess.run(smart_cmd, capture_output=True, text=True, timeout=30)
            
            # Get health status
            health_cmd = [self.collector._smartctl_path, '-H', device_path]
            health_result = subprocess.run(health_cmd, capture_output=True, text=True, timeout=30)
            
            return self.parse_smartctl_output(
                device_path, 
                info_result.stdout, 
                smart_result.stdout, 
                health_result.stdout
            )
            
        except Exception as e:
            self.logger.error(f"Error getting macOS SMART data: {e}")
            return None
    
    def get_linux_smart_data(self, device_path: str) -> Optional[SMARTData]:
        """Get SMART data on Linux using smartctl"""
        return self.get_macos_smart_data(device_path)  # Same implementation
    
    def get_windows_smart_data(self, device_path: str) -> Optional[SMARTData]:
        """Get SMART data on Windows using WMI"""
        try:
            import wmi
            c = wmi.WMI()
            
            # Get physical disk info
            for disk in c.Win32_DiskDrive():
                if device_path.replace('\\', '').lower() in disk.DeviceID.replace('\\', '').lower():
                    return self.parse_windows_smart_data(disk)
            
        except Exception as e:
            self.logger.error(f"Error getting Windows SMART data: {e}")
            return None
    
    def parse_smartctl_output(self, device_path: str, info_output: str, 
                              smart_output: str, health_output: str) -> Optional[SMARTData]:
        """Parse smartctl output and create SMARTData object with Phase 2 parameters"""
        try:
            # Parse device information
            device_model = "Unknown"
            serial_number = "Unknown"
            firmware_version = "Unknown"
            capacity = "Unknown"
            drive_type = DriveType.UNKNOWN
            
            for line in info_output.split('\n'):
                if 'Device Model:' in line or 'Model Number:' in line:
                    device_model = line.split(':', 1)[1].strip()
                elif 'Serial Number:' in line or 'Serial number:' in line:
                    serial_number = line.split(':', 1)[1].strip()
                elif 'Firmware Version:' in line:
                    firmware_version = line.split(':', 1)[1].strip()
                elif 'User Capacity:' in line:
                    capacity = line.split(':', 1)[1].strip().split('[')[0].strip()
                elif 'NVM' in line or 'NVMe' in line:
                    drive_type = DriveType.SSD
                elif 'SSD' in line:
                    drive_type = DriveType.SSD
                elif 'HDD' in line or 'disk' in line.lower():
                    drive_type = DriveType.HDD
            
            # Parse SMART status
            smart_status = SMARTStatus.UNKNOWN
            if 'PASSED' in health_output:
                smart_status = SMARTStatus.PASSED
            elif 'FAILED' in health_output:
                smart_status = SMARTStatus.FAILED
            
            # Check for NVMe drive
            is_nvme = 'NVMe' in info_output or 'nvme' in device_path.lower()
            if is_nvme:
                drive_type = DriveType.SSD
            
            # Initialize Phase 2 parameters
            attributes = {}
            temperature = None
            power_on_hours = None
            power_cycle_count = None
            reallocated_sectors = None
            pending_sectors = None
            
            # Phase 2: Extended SMART Attributes
            raw_read_error_rate = None
            spin_up_time = None
            start_stop_count = None
            seek_error_rate = None
            ssd_life_left = None
            bad_blocks = None
            
            # Parse NVMe-specific data if detected
            if is_nvme:
                nvme_data = self._parse_nvme_data(smart_output)
                temperature = nvme_data.get('temperature', temperature)
                power_on_hours = nvme_data.get('power_on_hours', power_on_hours)
                power_cycle_count = nvme_data.get('power_cycle_count', power_cycle_count)
                ssd_life_left = nvme_data.get('ssd_life_left', ssd_life_left)
                bad_blocks = nvme_data.get('bad_blocks', bad_blocks)
            
            in_attributes_section = False
            for line in smart_output.split('\n'):
                if 'ID# ATTRIBUTE_NAME' in line:
                    in_attributes_section = True
                    continue
                
                if in_attributes_section and line.strip():
                    parts = line.split()
                    if len(parts) >= 10 and parts[0].isdigit():
                        attr_id = int(parts[0])
                        attr_name = parts[1]
                        value = int(parts[3]) if parts[3].isdigit() else 0
                        worst = int(parts[4]) if parts[4].isdigit() else 0
                        threshold = int(parts[5]) if parts[5].isdigit() else 0
                        raw_value = parts[9] if len(parts) > 9 else "0"
                        
                        # Extract numeric raw value
                        try:
                            raw_numeric = int(raw_value.split()[0])
                        except (ValueError, IndexError):
                            raw_numeric = 0
                        
                        attributes[attr_id] = SMARTAttribute(
                            id=attr_id,
                            name=attr_name,
                            value=value,
                            worst=worst,
                            threshold=threshold,
                            raw_value=raw_numeric,
                            flags="",
                            updated="",
                            when_failed=""
                        )
                        
                        # Extract Phase 1 parameters
                        if attr_id == 194:  # Temperature_Celsius
                            temperature = raw_numeric
                        elif attr_id == 9:  # Power_On_Hours
                            power_on_hours = raw_numeric
                        elif attr_id == 12:  # Power_Cycle_Count
                            power_cycle_count = raw_numeric
                        elif attr_id == 5:  # Reallocated_Sector_Count
                            reallocated_sectors = raw_numeric
                        elif attr_id == 197:  # Current_Pending_Sector_Count
                            pending_sectors = raw_numeric
                        
                        # Extract Phase 2 parameters
                        elif attr_id == 1:  # Raw_Read_Error_Rate
                            raw_read_error_rate = raw_numeric
                        elif attr_id == 3:  # Spin_Up_Time
                            spin_up_time = raw_numeric
                        elif attr_id == 4:  # StartStop_Count
                            start_stop_count = raw_numeric
                        elif attr_id == 7:  # Seek_Error_Rate
                            seek_error_rate = raw_numeric
                        elif attr_id == 231:  # SSD_Life_Left (percentage remaining)
                            ssd_life_left = value  # Use value instead of raw for percentage
                        elif attr_id == 233:  # Media_Wearout_Indicator
                            if ssd_life_left is None:
                                ssd_life_left = value
                        elif attr_id == 184:  # End-to-End_Error / Bad_Blocks
                            bad_blocks = raw_numeric
                        elif attr_id == 187:  # Reported_Uncorrectable_Errors
                            if bad_blocks is None:
                                bad_blocks = raw_numeric
            
            # Enhanced health score calculation with Phase 2 parameters
            health_score = self.calculate_enhanced_health_score(attributes, smart_status)
            
            return SMARTData(
                device_path=device_path,
                device_model=device_model,
                serial_number=serial_number,
                firmware_version=firmware_version,
                drive_type=drive_type,
                capacity=capacity,
                smart_status=smart_status,
                temperature=temperature,
                power_on_hours=power_on_hours,
                power_cycle_count=power_cycle_count,
                ssd_life_left=ssd_life_left,
                bad_blocks=bad_blocks,
                reallocated_sectors=reallocated_sectors,
                pending_sectors=pending_sectors,
                attributes=attributes,
                health_score=health_score,
                last_updated=datetime.now(),
                error_log=[]
            )
            
        except Exception as e:
            self.logger.error(f"Error parsing smartctl output: {e}")
            return None
    def parse_windows_smart_data(self, disk) -> Optional[SMARTData]:
        """Parse Windows WMI disk data"""
        # Simplified Windows implementation
        return SMARTData(
            device_path=disk.DeviceID,
            device_model=disk.Model or "Unknown",
            serial_number=disk.SerialNumber or "Unknown",
            firmware_version="Unknown",
            drive_type=DriveType.UNKNOWN,
            capacity=f"{disk.Size // (1024**3)} GB" if disk.Size else "Unknown",
            smart_status=SMARTStatus.UNKNOWN,
            temperature=None,
            power_on_hours=None,
            power_cycle_count=None,
            ssd_life_left=None,
            bad_blocks=None,
            reallocated_sectors=None,
            pending_sectors=None,
            attributes={},
            health_score=50.0,  # Default score
            last_updated=datetime.now(),
            error_log=[]
        )
    
    def calculate_health_score(self, attributes: Dict[int, SMARTAttribute], 
                               status: SMARTStatus) -> float:
        """Calculate overall health score based on SMART attributes and status"""
        if status == SMARTStatus.FAILED:
            return 0.0
        
        base_score = 80.0 if status == SMARTStatus.PASSED else 50.0
        
        # Critical attributes that heavily impact health
        critical_penalties = {
            5: 20.0,   # Reallocated Sector Count
            197: 15.0, # Current Pending Sector Count
            198: 15.0, # Offline Uncorrectable
            187: 10.0, # Reported Uncorrectable Errors
            188: 10.0, # Command Timeout
        }
        
        penalty = 0.0
        for attr_id, penalty_weight in critical_penalties.items():
            if attr_id in attributes:
                attr = attributes[attr_id]
                if attr.is_critical:
                    penalty += penalty_weight
                elif hasattr(attr, 'raw_value') and isinstance(attr.raw_value, int) and attr.raw_value > 0:
                    # Partial penalty for non-zero values
                    penalty += penalty_weight * 0.3
        
        # Temperature impact
        if 194 in attributes:  # Temperature
            temp_attr = attributes[194]
            if hasattr(temp_attr, 'raw_value') and isinstance(temp_attr.raw_value, int):
                temp = temp_attr.raw_value
                if temp > 60:
                    penalty += 10.0
                elif temp > 50:
                    penalty += 5.0
        
        return max(0.0, min(100.0, base_score - penalty))

    def calculate_enhanced_health_score(self, attributes: Dict[int, SMARTAttribute], 
                                       status: SMARTStatus) -> float:
        """Enhanced health score calculation with Phase 2 parameters and predictive analytics"""
        if status == SMARTStatus.FAILED:
            return 0.0
        
        base_score = 85.0 if status == SMARTStatus.PASSED else 40.0
        
        # Phase 1 Critical attributes with enhanced weighting
        critical_penalties = {
            5: 25.0,   # Reallocated_Sector_Count (critical)
            197: 20.0, # Current_Pending_Sector_Count (critical)
            198: 20.0, # Offline_Uncorrectable (critical)
            187: 15.0, # Reported_Uncorrectable_Errors (high)
            188: 15.0, # Command_Timeout (high)
            184: 12.0, # End-to-End_Error (medium-high)
        }
        
        # Phase 2 Extended attributes
        extended_penalties = {
            1: 8.0,    # Raw_Read_Error_Rate (medium)
            7: 6.0,    # Seek_Error_Rate (medium)
            3: 3.0,    # Spin_Up_Time (low)
            4: 2.0,    # StartStop_Count (low)
        }
        
        penalty = 0.0
        # Apply critical penalties
        for attr_id, penalty_weight in critical_penalties.items():
            if attr_id in attributes:
                attr = attributes[attr_id]
                if attr.is_critical:
                    penalty += penalty_weight
                elif hasattr(attr, 'raw_value') and isinstance(attr.raw_value, int) and attr.raw_value > 0:
                    # Progressive penalty based on raw value
                    raw_val = attr.raw_value
                    if raw_val > 100:
                        penalty += penalty_weight * 0.8
                    elif raw_val > 10:
                        penalty += penalty_weight * 0.5
                    elif raw_val > 0:
                        penalty += penalty_weight * 0.2
        
        # Apply extended penalties
        for attr_id, penalty_weight in extended_penalties.items():
            if attr_id in attributes:
                attr = attributes[attr_id]
                if attr.is_critical:
                    penalty += penalty_weight
                elif hasattr(attr, 'raw_value') and isinstance(attr.raw_value, int):
                    # Threshold-based penalties for extended attributes
                    raw_val = attr.raw_value
                    if attr_id == 1 and raw_val > 1000000:  # Raw_Read_Error_Rate
                        penalty += penalty_weight * 0.6
                    elif attr_id == 7 and raw_val > 100000:  # Seek_Error_Rate
                        penalty += penalty_weight * 0.6
                    elif attr_id == 3 and raw_val > 10000:   # Spin_Up_Time (ms)
                        penalty += penalty_weight * 0.4
                    elif attr_id == 4 and raw_val > 50000:   # StartStop_Count
                        penalty += penalty_weight * 0.3
        
        # Enhanced temperature analysis
        if 194 in attributes:  # Temperature_Celsius
            temp_attr = attributes[194]
            if hasattr(temp_attr, 'raw_value') and isinstance(temp_attr.raw_value, int):
                temp = temp_attr.raw_value
                if temp > 70:
                    penalty += 15.0  # Critical temperature
                elif temp > 60:
                    penalty += 10.0  # High temperature
                elif temp > 50:
                    penalty += 5.0   # Elevated temperature
        
        # SSD-specific health analysis
        if 231 in attributes or 233 in attributes:  # SSD life indicators
            ssd_life_attr = attributes.get(231) or attributes.get(233)
            if ssd_life_attr and hasattr(ssd_life_attr, 'value'):
                life_remaining = ssd_life_attr.value
                if life_remaining < 10:
                    penalty += 30.0  # Critical SSD wear
                elif life_remaining < 25:
                    penalty += 20.0  # High SSD wear
                elif life_remaining < 50:
                    penalty += 10.0  # Moderate SSD wear
        
        # Power cycle analysis for predictive health
        if 12 in attributes:  # Power_Cycle_Count
            power_cycles = attributes[12]
            if hasattr(power_cycles, 'raw_value') and isinstance(power_cycles.raw_value, int):
                cycles = power_cycles.raw_value
                if cycles > 100000:
                    penalty += 8.0   # Very high power cycles
                elif cycles > 50000:
                    penalty += 4.0   # High power cycles
        
        # Power-on hours analysis
        if 9 in attributes:  # Power_On_Hours
            power_hours = attributes[9]
            if hasattr(power_hours, 'raw_value') and isinstance(power_hours.raw_value, int):
                hours = power_hours.raw_value
                years = hours / 8760  # Convert to years
                if years > 5:
                    penalty += 12.0  # Very old drive
                elif years > 3:
                    penalty += 6.0   # Old drive
                elif years > 1:
                    penalty += 2.0   # Moderate age
        
        return max(0.0, min(100.0, base_score - penalty))
    
    def _parse_nvme_data(self, smart_output: str) -> Dict:
        """Parse NVMe-specific SMART data"""
        nvme_data = {}
        
        for line in smart_output.split('\n'):
            line = line.strip()
            
            # Temperature
            if 'Temperature:' in line:
                try:
                    temp_str = line.split('Temperature:')[1].strip()
                    temp_val = int(temp_str.split()[0])
                    nvme_data['temperature'] = temp_val
                except (ValueError, IndexError):
                    pass
            
            # Power On Hours
            elif 'Power On Hours:' in line:
                try:
                    hours_str = line.split('Power On Hours:')[1].strip()
                    hours_val = int(hours_str.replace(',', ''))
                    nvme_data['power_on_hours'] = hours_val
                except (ValueError, IndexError):
                    pass
            
            # Power Cycles
            elif 'Power Cycles:' in line:
                try:
                    cycles_str = line.split('Power Cycles:')[1].strip()
                    cycles_val = int(cycles_str.replace(',', ''))
                    nvme_data['power_cycle_count'] = cycles_val
                except (ValueError, IndexError):
                    pass
            
            # Percentage Used (inverse of SSD life left)
            elif 'Percentage Used:' in line:
                try:
                    used_str = line.split('Percentage Used:')[1].strip()
                    used_val = int(used_str.replace('%', ''))
                    nvme_data['ssd_life_left'] = 100 - used_val
                except (ValueError, IndexError):
                    pass
            
            # Media and Data Integrity Errors
            elif 'Media and Data Integrity Errors:' in line:
                try:
                    errors_str = line.split('Media and Data Integrity Errors:')[1].strip()
                    errors_val = int(errors_str.replace(',', ''))
                    nvme_data['bad_blocks'] = errors_val
                except (ValueError, IndexError):
                    pass
            
            # Available Spare (another health indicator)
            elif 'Available Spare:' in line:
                try:
                    spare_str = line.split('Available Spare:')[1].strip()
                    spare_val = int(spare_str.replace('%', ''))
                    # If spare is low, it indicates wear
                    if spare_val < 100 and 'ssd_life_left' not in nvme_data:
                        nvme_data['ssd_life_left'] = spare_val
                except (ValueError, IndexError):
                    pass
        
        return nvme_data
