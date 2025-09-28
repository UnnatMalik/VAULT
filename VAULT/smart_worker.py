#!/usr/bin/env python3
"""
SMART Worker Module - Background monitoring and alerting
"""

import logging
from datetime import datetime
from typing import List, Dict, Callable, Tuple, Optional

try:
    from PySide6.QtCore import QThread, Signal
    GUI_AVAILABLE = True
except ImportError:
    GUI_AVAILABLE = False
    QThread = object
    Signal = lambda: None

from smart_monitor import SMARTCollector, SMARTData
from smart_database import SMARTDatabase
from smart_parser import SMARTParser


if GUI_AVAILABLE:
    class SMARTMonitorWorker(QThread):
        """Background worker for SMART monitoring"""
        
        data_updated = Signal(str, object)  # device_path, SMARTData
        error_occurred = Signal(str, str)   # device_path, error_message
        alert_triggered = Signal(str, str, str)  # device_path, message, severity
        
        def __init__(self, device_paths: List[str], interval: int = 300):
            super().__init__()
            self.device_paths = device_paths
            self.interval = interval  # seconds
            self.collector = SMARTCollector()
            self.parser = SMARTParser(self.collector)
            self.database = SMARTDatabase()
            self.running = False
            self.logger = logging.getLogger(__name__)
        
        def run(self):
            """Main monitoring loop"""
            self.running = True
            self.logger.info(f"Starting SMART monitoring for {len(self.device_paths)} devices")
            
            while self.running:
                for device_path in self.device_paths:
                    if not self.running:
                        break
                    
                    try:
                        # Check if monitoring is enabled for this device
                        config = self.database.get_device_config(device_path)
                        if not config.get('monitoring_enabled', True):
                            continue
                        
                        smart_data = self.collector.get_smart_data(device_path)
                        if smart_data:
                            # Store in database
                            self.database.store_smart_data(smart_data)
                            
                            # Check for alerts
                            self._check_alerts(smart_data, config)
                            
                            # Emit signal
                            self.data_updated.emit(device_path, smart_data)
                        else:
                            self.error_occurred.emit(device_path, "Failed to collect SMART data")
                    except Exception as e:
                        self.error_occurred.emit(device_path, str(e))
                        self.logger.error(f"Error monitoring {device_path}: {e}")
                
                # Wait for next interval
                for _ in range(self.interval):
                    if not self.running:
                        break
                    self.msleep(1000)
        
        def stop(self):
            """Stop monitoring"""
            self.running = False
            self.logger.info("Stopping SMART monitoring")
            self.wait()
        
        def _check_alerts(self, smart_data: SMARTData, config: Dict):
            """Check for alert conditions"""
            health_threshold = config.get('alert_threshold_health', 20.0)
            temp_threshold = config.get('alert_threshold_temp', 60)
            
            # Check SMART status
            if smart_data.smart_status.value == "FAILED":
                message = "SMART status indicates drive failure"
                self.database.store_alert(smart_data.device_path, "smart_failed", "critical", message)
                self.alert_triggered.emit(smart_data.device_path, message, "critical")
            
            # Check health score
            if smart_data.health_score < health_threshold:
                message = f"Health score below threshold: {smart_data.health_score:.1f}% (threshold: {health_threshold}%)"
                severity = "critical" if smart_data.health_score < 10 else "warning"
                self.database.store_alert(smart_data.device_path, "low_health", severity, message)
                self.alert_triggered.emit(smart_data.device_path, message, severity)
            
            # Check temperature
            if smart_data.temperature and smart_data.temperature > temp_threshold:
                message = f"High temperature: {smart_data.temperature}°C (threshold: {temp_threshold}°C)"
                severity = "critical" if smart_data.temperature > 70 else "warning"
                self.database.store_alert(smart_data.device_path, "high_temperature", severity, message)
                self.alert_triggered.emit(smart_data.device_path, message, severity)
            
            # Check reallocated sectors
            if smart_data.reallocated_sectors and smart_data.reallocated_sectors > 0:
                message = f"Reallocated sectors detected: {smart_data.reallocated_sectors}"
                self.database.store_alert(smart_data.device_path, "reallocated_sectors", "warning", message)
                self.alert_triggered.emit(smart_data.device_path, message, "warning")
            
            # Check pending sectors
            if smart_data.pending_sectors and smart_data.pending_sectors > 0:
                message = f"Pending sectors detected: {smart_data.pending_sectors}"
                self.database.store_alert(smart_data.device_path, "pending_sectors", "warning", message)
                self.alert_triggered.emit(smart_data.device_path, message, "warning")


class SMARTMonitor:
    """Main SMART monitoring system"""
    
    def __init__(self):
        self.collector = SMARTCollector()
        self.parser = SMARTParser(self.collector)
        self.database = SMARTDatabase()
        self.logger = logging.getLogger(__name__)
        self._monitoring_worker = None
        self._alert_callbacks = []
    def check_system_compatibility(self) -> Tuple[bool, List[str]]:
        """Check if system supports SMART monitoring"""
        return self.collector.check_dependencies()
    
    def get_available_drives(self) -> List[str]:
        """Get list of available drives for SMART monitoring with enhanced detection"""
        if not self.collector:
            return []
        
        try:
            # Try enhanced detection first
            if hasattr(self.collector, 'get_available_drives_enhanced'):
                drives = self.collector.get_available_drives_enhanced()
                if drives:
                    return drives
            
            # Fall back to basic detection
            return self.collector.get_available_drives()
        except Exception as e:
            self.logger.error(f"Error getting available drives: {e}")
            return []
    
    def get_smart_data(self, device_path: str) -> Optional['SMARTData']:
        """Get SMART data for a specific device"""
        try:
            return self.collector.get_smart_data(device_path)
        except Exception as e:
            self.logger.error(f"Error getting SMART data for {device_path}: {e}")
            return None
    
    def start_monitoring(self, device_paths: List[str] = None, interval: int = 300):
        """Start background monitoring of specified drives"""
        if not GUI_AVAILABLE:
            self.logger.warning("GUI not available, monitoring disabled")
        
        if device_paths is None:
            device_paths = self.database.get_all_monitored_devices()
            if not device_paths:
                device_paths = self.get_available_drives()
        
        if self._monitoring_worker and self._monitoring_worker.isRunning():
            self.stop_monitoring()
        
        self._monitoring_worker = SMARTMonitorWorker(device_paths, interval)
        self._monitoring_worker.data_updated.connect(self._handle_data_update)
        self._monitoring_worker.error_occurred.connect(self._handle_error)
        self._monitoring_worker.alert_triggered.connect(self._handle_alert)
        self._monitoring_worker.start()
        
        self.logger.info(f"Started SMART monitoring for {len(device_paths)} drives")
    
    def stop_monitoring(self):
        """Stop background monitoring"""
        if self._monitoring_worker:
            self._monitoring_worker.stop()
            self._monitoring_worker = None
            self.logger.info("Stopped SMART monitoring")
    
    def add_alert_callback(self, callback):
        """Add callback for SMART alerts"""
        self._alert_callbacks.append(callback)
    
    def _handle_data_update(self, device_path: str, smart_data: SMARTData):
        """Handle SMART data update"""
        self.logger.debug(f"SMART data updated for {device_path}: Health {smart_data.health_score:.1f}%")
    
    def _handle_error(self, device_path: str, error_message: str):
        """Handle monitoring error"""
        self.logger.error(f"SMART monitoring error for {device_path}: {error_message}")
    
    def _handle_alert(self, device_path: str, message: str, severity: str):
        """Handle SMART alert"""
        alert_data = {
            'device_path': device_path,
            'message': message,
            'severity': severity,
            'timestamp': datetime.now()
        }
        
        self.logger.warning(f"SMART Alert [{severity.upper()}] {device_path}: {message}")
        
        for callback in self._alert_callbacks:
            try:
                callback(alert_data)
            except Exception as e:
                self.logger.error(f"Error in alert callback: {e}")
    
    def get_device_history(self, device_path: str, days: int = 30) -> List[Dict]:
        """Get historical SMART data for a device"""
        return self.database.get_device_history(device_path, days)
    
    def get_health_trend(self, device_path: str, days: int = 7) -> List[Tuple[datetime, float]]:
        """Get health score trend for a device"""
        return self.database.get_health_trend(device_path, days)
    
    def get_unacknowledged_alerts(self, device_path: str = None) -> List[Dict]:
        """Get unacknowledged alerts"""
        return self.database.get_unacknowledged_alerts(device_path)
    
    def acknowledge_alert(self, alert_id: int):
        """Acknowledge an alert"""
        self.database.acknowledge_alert(alert_id)
    
    def configure_device_monitoring(self, device_path: str, config: Dict):
        """Configure monitoring settings for a device"""
        self.database.update_device_config(device_path, config)
    
    def get_device_config(self, device_path: str) -> Dict:
        """Get device monitoring configuration"""
        return self.database.get_device_config(device_path)
    
    def generate_health_report(self, device_path: str) -> Dict:
        """Generate comprehensive health report for a device"""
        smart_data = self.get_smart_data(device_path)
        if not smart_data:
            return {'error': 'Unable to collect SMART data'}
        
        history = self.get_device_history(device_path, 30)
        trend = self.get_health_trend(device_path, 7)
        alerts = self.get_unacknowledged_alerts(device_path)
        
        # Calculate trend direction
        trend_direction = "stable"
        if len(trend) >= 2:
            recent_avg = sum(score for _, score in trend[-3:]) / min(3, len(trend))
            older_avg = sum(score for _, score in trend[:3]) / min(3, len(trend))
            if recent_avg < older_avg - 5:
                trend_direction = "declining"
            elif recent_avg > older_avg + 5:
                trend_direction = "improving"
        
        # Identify critical issues
        critical_issues = []
        warnings = []
        
        if smart_data.smart_status.value == "FAILED":
            critical_issues.append("SMART status indicates drive failure")
        
        if smart_data.health_score < 20:
            critical_issues.append(f"Very low health score: {smart_data.health_score:.1f}%")
        elif smart_data.health_score < 50:
            warnings.append(f"Low health score: {smart_data.health_score:.1f}%")
        
        if smart_data.temperature and smart_data.temperature > 60:
            warnings.append(f"High operating temperature: {smart_data.temperature}°C")
        
        if smart_data.reallocated_sectors and smart_data.reallocated_sectors > 0:
            critical_issues.append(f"Reallocated sectors detected: {smart_data.reallocated_sectors}")
        
        if smart_data.pending_sectors and smart_data.pending_sectors > 0:
            warnings.append(f"Pending sectors detected: {smart_data.pending_sectors}")
        
        # Recommendations
        recommendations = []
        if critical_issues:
            recommendations.append("Immediate backup recommended - drive may fail soon")
            recommendations.append("Consider replacing this drive")
        elif warnings:
            recommendations.append("Monitor drive closely")
            recommendations.append("Ensure adequate cooling")
            recommendations.append("Regular backups recommended")
        else:
            recommendations.append("Drive appears healthy")
            recommendations.append("Continue regular monitoring")
        
        return {
            'device_info': {
                'path': smart_data.device_path,
                'model': smart_data.device_model,
                'serial': smart_data.serial_number,
                'capacity': smart_data.capacity,
                'type': smart_data.drive_type.value
            },
            'current_status': {
                'smart_status': smart_data.smart_status.value,
                'health_score': smart_data.health_score,
                'temperature': smart_data.temperature,
                'power_on_hours': smart_data.power_on_hours,
                'ssd_life_left': smart_data.ssd_life_left
            },
            'trend_analysis': {
                'direction': trend_direction,
                'data_points': len(trend),
                'monitoring_days': len(history)
            },
            'issues': {
                'critical': critical_issues,
                'warnings': warnings
            },
            'recommendations': recommendations,
            'alerts': alerts,
            'last_updated': smart_data.last_updated.isoformat()
        }
    
    def get_device_history(self, device_path: str, days: int = 30) -> List[Dict]:
        """Get historical SMART data for a device"""
        try:
            return self.database.get_device_history(device_path, days)
        except Exception as e:
            self.logger.error(f"Error getting device history: {e}")
            return []
    
    def get_unacknowledged_alerts(self, device_path: str = None) -> List[Dict]:
        """Get unacknowledged alerts"""
        try:
            return self.database.get_unacknowledged_alerts(device_path)
        except Exception as e:
            self.logger.error(f"Error getting alerts: {e}")
            return []
    
    def acknowledge_alert(self, alert_id: int):
        """Acknowledge an alert"""
        try:
            self.database.acknowledge_alert(alert_id)
        except Exception as e:
            self.logger.error(f"Error acknowledging alert: {e}")
    
    def configure_device_monitoring(self, device_path: str, config: Dict):
        """Configure monitoring settings for a device"""
        try:
            self.database.update_device_config(device_path, config)
        except Exception as e:
            self.logger.error(f"Error updating device config: {e}")
