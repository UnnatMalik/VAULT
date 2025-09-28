#!/usr/bin/env python3
"""
SMART Monitor Module for VAULT
Comprehensive cross-platform SMART data collection and monitoring system
"""

import json
import logging
import platform
import re
import subprocess
import threading
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union, Any
import sqlite3

try:
    import psutil
except ImportError:
    psutil = None

try:
    from PySide6.QtCore import QObject, Signal, QThread, QTimer
    from PySide6.QtWidgets import QMessageBox
    GUI_AVAILABLE = True
except ImportError:
    GUI_AVAILABLE = False
    QObject = object
    Signal = lambda: None
    QThread = object


class SMARTStatus(Enum):
    """SMART status enumeration"""
    PASSED = "PASSED"
    FAILED = "FAILED"
    WARNING = "WARNING"
    UNKNOWN = "UNKNOWN"
    NOT_SUPPORTED = "NOT_SUPPORTED"


class DriveType(Enum):
    """Drive type enumeration"""
    HDD = "HDD"
    SSD = "SSD"
    NVME = "NVME"
    USB = "USB"
    UNKNOWN = "UNKNOWN"


@dataclass
class SMARTAttribute:
    """Individual SMART attribute data"""
    id: int
    name: str
    value: int
    worst: int
    threshold: int
    raw_value: Union[int, str]
    flags: str
    updated: str
    when_failed: str
    
    @property
    def is_critical(self) -> bool:
        """Check if attribute is in critical state"""
        return self.value <= self.threshold and self.threshold > 0
    
    @property
    def health_percentage(self) -> float:
        """Calculate health percentage for this attribute"""
        if self.threshold == 0:
            return 100.0
        return max(0.0, min(100.0, (self.value / self.threshold) * 100))


@dataclass
class SMARTData:
    """Complete SMART data for a drive"""
    device_path: str
    device_model: str
    serial_number: str
    firmware_version: str
    drive_type: DriveType
    capacity: str
    smart_status: SMARTStatus
    temperature: Optional[int]
    power_on_hours: Optional[int]
    power_cycle_count: Optional[int]
    ssd_life_left: Optional[float]
    bad_blocks: Optional[int]
    reallocated_sectors: Optional[int]
    pending_sectors: Optional[int]
    attributes: Dict[int, SMARTAttribute]
    health_score: float
    last_updated: datetime
    error_log: List[str]
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization"""
        data = asdict(self)
        data['drive_type'] = self.drive_type.value
        data['smart_status'] = self.smart_status.value
        data['last_updated'] = self.last_updated.isoformat()
        data['attributes'] = {str(k): asdict(v) for k, v in self.attributes.items()}
        return data
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'SMARTData':
        """Create from dictionary"""
        data['drive_type'] = DriveType(data['drive_type'])
        data['smart_status'] = SMARTStatus(data['smart_status'])
        data['last_updated'] = datetime.fromisoformat(data['last_updated'])
        
        attributes = {}
        for k, v in data['attributes'].items():
            attributes[int(k)] = SMARTAttribute(**v)
        data['attributes'] = attributes
        
        return cls(**data)


class SMARTCollector:
    """Cross-platform SMART data collector"""
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.platform = platform.system()
        self._smartctl_path = self.find_smartctl()
        
    def find_smartctl(self) -> Optional[str]:
        """Find smartctl executable"""
        possible_paths = [
            '/usr/local/bin/smartctl',
            '/opt/homebrew/bin/smartctl',
            '/usr/bin/smartctl',
            '/usr/sbin/smartctl',
            'smartctl'  # Try PATH
        ]
        
        for path in possible_paths:
            try:
                result = subprocess.run([path, '--version'], 
                                      capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    self.logger.info(f"Found smartctl at: {path}")
                    return path
            except (subprocess.SubprocessError, FileNotFoundError):
                continue
        
        self.logger.warning("smartctl not found in common locations")
        return None

    def get_available_drives_enhanced(self) -> List[str]:
        """Enhanced drive detection including NVMe and multiple drives"""
        drives = []
        
        if not self.smartctl_path:
            return drives
        
        try:
            # Use smartctl --scan to detect all SMART-capable drives
            result = subprocess.run([self.smartctl_path, '--scan'], 
                                  capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                for line in result.stdout.strip().split('\n'):
                    if line.strip():
                        # Parse smartctl --scan output
                        parts = line.split()
                        if parts:
                            device_path = parts[0]
                            drives.append(device_path)
                            self.logger.info(f"Detected SMART device: {device_path}")
            
            # If --scan didn't work or found nothing, fall back to manual detection
            if not drives:
                drives = self._manual_drive_detection()
                
        except subprocess.SubprocessError as e:
            self.logger.error(f"Error scanning for drives: {e}")
            drives = self._manual_drive_detection()
        
        return drives
    
    def _manual_drive_detection(self) -> List[str]:
        """Manual drive detection as fallback"""
        drives = []
        
        if self.platform == "Darwin":
            # macOS: Check both physical disks and NVMe devices
            physical_disks = ['/dev/disk0', '/dev/disk1', '/dev/disk2']
            
            for disk in physical_disks:
                if self._test_smart_access(disk):
                    drives.append(disk)
            
            # Also try to detect NVMe via IOService paths
            try:
                result = subprocess.run(['system_profiler', 'SPNVMeDataType', '-json'], 
                                      capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    import json
                    data = json.loads(result.stdout)
                    # Extract NVMe device paths if available
                    # This is a simplified approach - real implementation would parse the JSON
                    
            except Exception as e:
                self.logger.debug(f"NVMe detection failed: {e}")
        
        elif self.platform == "Linux":
            # Linux: Check common drive paths
            common_paths = ['/dev/sda', '/dev/sdb', '/dev/sdc', '/dev/nvme0n1', '/dev/nvme1n1']
            for path in common_paths:
                if self._test_smart_access(path):
                    drives.append(path)
        
        return drives
    
    def _test_smart_access(self, device_path: str) -> bool:
        """Test if we can access SMART data for a device"""
        if not self.smartctl_path:
            return False
        
        try:
            result = subprocess.run([self.smartctl_path, '-i', device_path], 
                                  capture_output=True, text=True, timeout=5)
            return result.returncode == 0
        except subprocess.SubprocessError:
            return False
    
    @property
    def smartctl_path(self) -> Optional[str]:
        """Get smartctl path"""
        return self._smartctl_path
    
    def check_dependencies(self) -> Tuple[bool, List[str]]:
        """Check if required dependencies are available"""
        missing = []
        
        if self.platform == "Darwin":
            if not self._smartctl_path:
                missing.append("smartmontools (brew install smartmontools)")
        elif self.platform == "Linux":
            if not self._smartctl_path:
                missing.append("smartmontools (apt install smartmontools / yum install smartmontools)")
        elif self.platform == "Windows":
            # Windows implementation will use WMI
            try:
                import wmi
            except ImportError:
                missing.append("WMI (pip install WMI)")
        
        return len(missing) == 0, missing
    
    def get_available_drives(self) -> List[str]:
        """Get list of available drives for SMART monitoring"""
        drives = []
        
        if self.platform == "Darwin":
            drives = self._get_macos_drives()
        elif self.platform == "Linux":
            drives = self._get_linux_drives()
        elif self.platform == "Windows":
            drives = self._get_windows_drives()
        
        return drives
    
    def _get_macos_drives(self) -> List[str]:
        """Get macOS drive list"""
        drives = []
        try:
            result = subprocess.run(['diskutil', 'list'], 
                                  capture_output=True, 
                                  text=True, 
                                  timeout=10)
            
            for line in result.stdout.split('\n'):
                if 'internal, physical' in line or 'external, physical' in line:
                    match = re.search(r'/dev/disk\d+', line)
                    if match:
                        drives.append(match.group())
        except Exception as e:
            self.logger.error(f"Error getting macOS drives: {e}")
        
        return drives
    
    def _get_linux_drives(self) -> List[str]:
        """Get Linux drive list"""
        drives = []
        try:
            # Use lsblk to get block devices
            result = subprocess.run(['lsblk', '-d', '-n', '-o', 'NAME,TYPE'], 
                                  capture_output=True, 
                                  text=True, 
                                  timeout=10)
            
            for line in result.stdout.split('\n'):
                if 'disk' in line:
                    device = line.split()[0]
                    drives.append(f'/dev/{device}')
        except Exception as e:
            self.logger.error(f"Error getting Linux drives: {e}")
        
        return drives
    
    def _get_windows_drives(self) -> List[str]:
        """Get Windows drive list"""
        drives = []
        try:
            if psutil:
                for partition in psutil.disk_partitions():
                    if 'fixed' in partition.opts:
                        drives.append(partition.device)
        except Exception as e:
            self.logger.error(f"Error getting Windows drives: {e}")
        
        return drives
    
    def get_smart_data(self, device_path: str) -> Optional[SMARTData]:
        """Get SMART data for a specific device"""
        try:
            # Import parser here to avoid circular imports
            from smart_parser import SMARTParser
            parser = SMARTParser(self)
            
            if self.platform == "Darwin":
                return parser.get_macos_smart_data(device_path)
            elif self.platform == "Linux":
                return parser.get_linux_smart_data(device_path)
            elif self.platform == "Windows":
                return parser.get_windows_smart_data(device_path)
        except Exception as e:
            self.logger.error(f"Error getting SMART data for {device_path}: {e}")
        
        return None
