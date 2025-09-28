#!/usr/bin/env python3
"""
SMART Database Module - Handles storage and retrieval of SMART data history
"""

import json
import sqlite3
from datetime import datetime
from typing import Dict, List, Tuple

from smart_monitor import SMARTData


class SMARTDatabase:
    """SQLite database for storing SMART data history"""
    
    def __init__(self, db_path: str = "smart_history.db"):
        self.db_path = db_path
        self._init_database()
    
    def _init_database(self):
        """Initialize database tables"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS smart_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    device_path TEXT NOT NULL,
                    device_model TEXT,
                    serial_number TEXT,
                    smart_status TEXT,
                    health_score REAL,
                    temperature INTEGER,
                    power_on_hours INTEGER,
                    power_cycle_count INTEGER,
                    ssd_life_left REAL,
                    reallocated_sectors INTEGER,
                    pending_sectors INTEGER,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    full_data TEXT
                )
            ''')
            
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_device_timestamp 
                ON smart_history(device_path, timestamp)
            ''')
            
            # Create alerts table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS smart_alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    device_path TEXT NOT NULL,
                    alert_type TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    message TEXT NOT NULL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    acknowledged BOOLEAN DEFAULT FALSE
                )
            ''')
            
            # Create device configuration table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS device_config (
                    device_path TEXT PRIMARY KEY,
                    monitoring_enabled BOOLEAN DEFAULT TRUE,
                    alert_threshold_health REAL DEFAULT 20.0,
                    alert_threshold_temp INTEGER DEFAULT 60,
                    monitoring_interval INTEGER DEFAULT 300,
                    last_configured DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
    
    def store_smart_data(self, smart_data: SMARTData):
        """Store SMART data in database"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT INTO smart_history (
                    device_path, device_model, serial_number, smart_status,
                    health_score, temperature, power_on_hours, power_cycle_count,
                    ssd_life_left, reallocated_sectors, pending_sectors, full_data
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                smart_data.device_path,
                smart_data.device_model,
                smart_data.serial_number,
                smart_data.smart_status.value,
                smart_data.health_score,
                smart_data.temperature,
                smart_data.power_on_hours,
                smart_data.power_cycle_count,
                smart_data.ssd_life_left,
                smart_data.reallocated_sectors,
                smart_data.pending_sectors,
                json.dumps(smart_data.to_dict())
            ))
    
    def get_device_history(self, device_path: str, days: int = 30) -> List[Dict]:
        """Get historical data for a device"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute('''
                SELECT * FROM smart_history 
                WHERE device_path = ? AND timestamp > datetime('now', '-{} days')
                ORDER BY timestamp DESC
            '''.format(days), (device_path,))
            
            return [dict(row) for row in cursor.fetchall()]
    
    def get_health_trend(self, device_path: str, days: int = 7) -> List[Tuple[datetime, float]]:
        """Get health score trend for a device"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                SELECT timestamp, health_score FROM smart_history 
                WHERE device_path = ? AND timestamp > datetime('now', '-{} days')
                ORDER BY timestamp ASC
            '''.format(days), (device_path,))
            
            return [(datetime.fromisoformat(row[0]), row[1]) for row in cursor.fetchall()]
    
    def store_alert(self, device_path: str, alert_type: str, severity: str, message: str):
        """Store SMART alert in database"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT INTO smart_alerts (device_path, alert_type, severity, message)
                VALUES (?, ?, ?, ?)
            ''', (device_path, alert_type, severity, message))
    
    def get_unacknowledged_alerts(self, device_path: str = None) -> List[Dict]:
        """Get unacknowledged alerts"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            
            if device_path:
                cursor = conn.execute('''
                    SELECT * FROM smart_alerts 
                    WHERE device_path = ? AND acknowledged = FALSE
                    ORDER BY timestamp DESC
                ''', (device_path,))
            else:
                cursor = conn.execute('''
                    SELECT * FROM smart_alerts 
                    WHERE acknowledged = FALSE
                    ORDER BY timestamp DESC
                ''')
            
            return [dict(row) for row in cursor.fetchall()]
    
    def acknowledge_alert(self, alert_id: int):
        """Mark alert as acknowledged"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                UPDATE smart_alerts SET acknowledged = TRUE 
                WHERE id = ?
            ''', (alert_id,))
    
    def get_device_config(self, device_path: str) -> Dict:
        """Get device monitoring configuration"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute('''
                SELECT * FROM device_config WHERE device_path = ?
            ''', (device_path,))
            
            row = cursor.fetchone()
            if row:
                return dict(row)
            else:
                # Return default config
                return {
                    'device_path': device_path,
                    'monitoring_enabled': True,
                    'alert_threshold_health': 20.0,
                    'alert_threshold_temp': 60,
                    'monitoring_interval': 300
                }
    
    def update_device_config(self, device_path: str, config: Dict):
        """Update device monitoring configuration"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT OR REPLACE INTO device_config 
                (device_path, monitoring_enabled, alert_threshold_health, 
                 alert_threshold_temp, monitoring_interval, last_configured)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', (
                device_path,
                config.get('monitoring_enabled', True),
                config.get('alert_threshold_health', 20.0),
                config.get('alert_threshold_temp', 60),
                config.get('monitoring_interval', 300)
            ))
    
    def get_all_monitored_devices(self) -> List[str]:
        """Get list of all devices configured for monitoring"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                SELECT device_path FROM device_config 
                WHERE monitoring_enabled = TRUE
            ''')
            
            return [row[0] for row in cursor.fetchall()]
    
    def cleanup_old_data(self, days_to_keep: int = 90):
        """Clean up old SMART data to prevent database bloat"""
        with sqlite3.connect(self.db_path) as conn:
            # Clean old history data
            conn.execute('''
                DELETE FROM smart_history 
                WHERE timestamp < datetime('now', '-{} days')
            '''.format(days_to_keep))
            
            # Clean old acknowledged alerts
            conn.execute('''
                DELETE FROM smart_alerts 
                WHERE acknowledged = TRUE AND timestamp < datetime('now', '-30 days')
            ''')
            
            # Vacuum database to reclaim space
            conn.execute('VACUUM')
    
    def get_statistics(self) -> Dict:
        """Get database statistics"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            
            # Count records
            cursor = conn.execute('SELECT COUNT(*) as count FROM smart_history')
            history_count = cursor.fetchone()['count']
            
            cursor = conn.execute('SELECT COUNT(*) as count FROM smart_alerts WHERE acknowledged = FALSE')
            alert_count = cursor.fetchone()['count']
            
            cursor = conn.execute('SELECT COUNT(*) as count FROM device_config WHERE monitoring_enabled = TRUE')
            monitored_devices = cursor.fetchone()['count']
            
            # Get oldest and newest records
            cursor = conn.execute('SELECT MIN(timestamp) as oldest, MAX(timestamp) as newest FROM smart_history')
            time_range = cursor.fetchone()
            
            return {
                'total_history_records': history_count,
                'unacknowledged_alerts': alert_count,
                'monitored_devices': monitored_devices,
                'oldest_record': time_range['oldest'],
                'newest_record': time_range['newest']
            }
