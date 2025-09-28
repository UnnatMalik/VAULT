#!/usr/bin/env python3
"""
SMART GUI Components - GUI integration for SMART monitoring
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional

try:
    from PySide6.QtCore import Qt, QTimer, Signal, QThread
    from PySide6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget, 
        QTableWidgetItem, QPushButton, QProgressBar, QGroupBox,
        QCheckBox, QSpinBox, QDoubleSpinBox, QComboBox, QTextEdit,
        QTabWidget, QMessageBox, QHeaderView, QFrame
    )
    from PySide6.QtGui import QFont, QColor, QPalette
    GUI_AVAILABLE = True
except ImportError:
    GUI_AVAILABLE = False
    QWidget = object

from smart_worker import SMARTMonitor
from smart_monitor import SMARTData, SMARTStatus, DriveType


if GUI_AVAILABLE:
    class SMARTOverviewWidget(QWidget):
        """SMART overview widget for the main dashboard"""
        
        def __init__(self, parent=None):
            super().__init__(parent)
            self.smart_monitor = SMARTMonitor()
            self.logger = logging.getLogger(__name__)
            self.setup_ui()
            self.setup_monitoring()
        
        def setup_ui(self):
            """Setup the UI components"""
            layout = QVBoxLayout(self)
            
            # Header
            header = QLabel("SMART Drive Health")
            header.setFont(QFont("Inter", 14, QFont.Weight.Bold))
            layout.addWidget(header)
            
            # Status cards container
            cards_layout = QHBoxLayout()
            
            # Total drives card
            self.total_drives_card = self._create_status_card("Total Drives", "0", "#4CAF50")
            cards_layout.addWidget(self.total_drives_card)
            
            # Healthy drives card
            self.healthy_drives_card = self._create_status_card("Healthy", "0", "#4CAF50")
            cards_layout.addWidget(self.healthy_drives_card)
            
            # Warning drives card
            self.warning_drives_card = self._create_status_card("Warning", "0", "#FFC107")
            cards_layout.addWidget(self.warning_drives_card)
            
            # Critical drives card
            self.critical_drives_card = self._create_status_card("Critical", "0", "#FF3B30")
            cards_layout.addWidget(self.critical_drives_card)
            
            layout.addLayout(cards_layout)
            
            # Drive list table
            self.drive_table = QTableWidget()
            self.drive_table.setColumnCount(6)
            self.drive_table.setHorizontalHeaderLabels([
                "Drive", "Model", "Health", "Temperature", "Status", "Last Updated"
            ])
            self.drive_table.horizontalHeader().setStretchLastSection(True)
            self.drive_table.setAlternatingRowColors(True)
            layout.addWidget(self.drive_table)
            
            # Refresh button
            refresh_btn = QPushButton("Refresh SMART Data")
            refresh_btn.clicked.connect(self.refresh_smart_data)
            layout.addWidget(refresh_btn)
        
        def _create_status_card(self, title: str, value: str, color: str) -> QWidget:
            """Create a status card widget"""
            card = QFrame()
            card.setFrameStyle(QFrame.Shape.Box)
            card.setStyleSheet(f"""
                QFrame {{
                    border: 1px solid #333;
                    border-radius: 8px;
                    background-color: #1a1a1a;
                    padding: 10px;
                }}
            """)
            
            layout = QVBoxLayout(card)
            
            title_label = QLabel(title)
            title_label.setFont(QFont("Inter", 10))
            title_label.setStyleSheet("color: #9AA0A6;")
            layout.addWidget(title_label)
            
            value_label = QLabel(value)
            value_label.setFont(QFont("Inter", 18, QFont.Weight.Bold))
            value_label.setStyleSheet(f"color: {color};")
            layout.addWidget(value_label)
            
            # Store value label for updates
            card.value_label = value_label
            
            return card
        
        def setup_monitoring(self):
            """Setup SMART monitoring"""
            # Check system compatibility
            compatible, missing = self.smart_monitor.check_system_compatibility()
            if not compatible:
                self.logger.warning(f"SMART monitoring not fully supported. Missing: {missing}")
            
            # Start monitoring
            drives = self.smart_monitor.get_available_drives()
            if drives:
                self.smart_monitor.start_monitoring(drives, interval=300)  # 5 minutes
                self.smart_monitor.add_alert_callback(self._handle_smart_alert)
            
            # Setup refresh timer
            self.refresh_timer = QTimer()
            self.refresh_timer.timeout.connect(self.refresh_smart_data)
            self.refresh_timer.start(60000)  # Refresh every minute
        
        def refresh_smart_data(self):
            """Refresh SMART data display"""
            drives = self.smart_monitor.get_available_drives()
            
            # Update status cards
            total_drives = len(drives)
            healthy_count = 0
            warning_count = 0
            critical_count = 0
            
            # Clear and populate table
            self.drive_table.setRowCount(len(drives))
            
            for i, drive_path in enumerate(drives):
                smart_data = self.smart_monitor.get_smart_data(drive_path)
                
                if smart_data:
                    # Categorize drive health
                    if smart_data.health_score >= 80:
                        healthy_count += 1
                        health_color = "#4CAF50"
                    elif smart_data.health_score >= 50:
                        warning_count += 1
                        health_color = "#FFC107"
                    else:
                        critical_count += 1
                        health_color = "#FF3B30"
                    
                    # Populate table row
                    self.drive_table.setItem(i, 0, QTableWidgetItem(drive_path))
                    self.drive_table.setItem(i, 1, QTableWidgetItem(smart_data.device_model))
                    
                    health_item = QTableWidgetItem(f"{smart_data.health_score:.1f}%")
                    health_item.setForeground(QColor(health_color))
                    self.drive_table.setItem(i, 2, health_item)
                    
                    temp_text = f"{smart_data.temperature}°C" if smart_data.temperature else "N/A"
                    self.drive_table.setItem(i, 3, QTableWidgetItem(temp_text))
                    
                    status_item = QTableWidgetItem(smart_data.smart_status.value)
                    if smart_data.smart_status == SMARTStatus.FAILED:
                        status_item.setForeground(QColor("#FF3B30"))
                    elif smart_data.smart_status == SMARTStatus.WARNING:
                        status_item.setForeground(QColor("#FFC107"))
                    else:
                        status_item.setForeground(QColor("#4CAF50"))
                    self.drive_table.setItem(i, 4, status_item)
                    
                    self.drive_table.setItem(i, 5, QTableWidgetItem(
                        smart_data.last_updated.strftime("%Y-%m-%d %H:%M")
                    ))
                else:
                    # Drive data unavailable
                    self.drive_table.setItem(i, 0, QTableWidgetItem(drive_path))
                    self.drive_table.setItem(i, 1, QTableWidgetItem("Unknown"))
                    self.drive_table.setItem(i, 2, QTableWidgetItem("N/A"))
                    self.drive_table.setItem(i, 3, QTableWidgetItem("N/A"))
                    self.drive_table.setItem(i, 4, QTableWidgetItem("Unknown"))
                    self.drive_table.setItem(i, 5, QTableWidgetItem("Never"))
            
            # Update status cards
            self.total_drives_card.value_label.setText(str(total_drives))
            self.healthy_drives_card.value_label.setText(str(healthy_count))
            self.warning_drives_card.value_label.setText(str(warning_count))
            self.critical_drives_card.value_label.setText(str(critical_count))
        
        def _handle_smart_alert(self, alert_data: Dict):
            """Handle SMART alerts"""
            severity = alert_data['severity']
            message = alert_data['message']
            device_path = alert_data['device_path']
            
            if severity == "critical":
                QMessageBox.critical(
                    self, 
                    "Critical SMART Alert", 
                    f"Drive {device_path}:\n{message}\n\nImmediate backup recommended!"
                )
            elif severity == "warning":
                QMessageBox.warning(
                    self, 
                    "SMART Warning", 
                    f"Drive {device_path}:\n{message}"
                )


    class SMARTDetailWidget(QWidget):
        """Detailed SMART information widget"""
        
        def __init__(self, device_path: str, parent=None):
            super().__init__(parent)
            self.device_path = device_path
            self.smart_monitor = SMARTMonitor()
            self.setup_ui()
            self.load_smart_data()
        
        def setup_ui(self):
            """Setup the detailed UI"""
            layout = QVBoxLayout(self)
            
            # Header with device path
            header = QLabel(f"SMART Details: {self.device_path}")
            header.setFont(QFont("Inter", 14, QFont.Weight.Bold))
            layout.addWidget(header)
            
            # Tab widget for different views
            tab_widget = QTabWidget()
            
            # Current status tab
            self.status_tab = self._create_status_tab()
            tab_widget.addTab(self.status_tab, "Current Status")
            
            # Attributes tab
            self.attributes_tab = self._create_attributes_tab()
            tab_widget.addTab(self.attributes_tab, "SMART Attributes")
            
            # History tab
            self.history_tab = self._create_history_tab()
            tab_widget.addTab(self.history_tab, "History")
            
            # Configuration tab
            self.config_tab = self._create_config_tab()
            tab_widget.addTab(self.config_tab, "Configuration")
            
            layout.addWidget(tab_widget)
        
        def _create_status_tab(self) -> QWidget:
            """Create status overview tab"""
            widget = QWidget()
            layout = QVBoxLayout(widget)
            
            # Device info group
            device_group = QGroupBox("Device Information")
            device_layout = QVBoxLayout(device_group)
            
            self.device_info_labels = {}
            for key in ["Model", "Serial", "Firmware", "Capacity", "Type"]:
                label = QLabel(f"{key}: Loading...")
                self.device_info_labels[key] = label
                device_layout.addWidget(label)
            
            layout.addWidget(device_group)
            
            # Health status group
            health_group = QGroupBox("Health Status")
            health_layout = QVBoxLayout(health_group)
            
            self.health_score_label = QLabel("Health Score: Loading...")
            self.health_score_label.setFont(QFont("Inter", 12, QFont.Weight.Bold))
            health_layout.addWidget(self.health_score_label)
            
            self.health_progress = QProgressBar()
            self.health_progress.setRange(0, 100)
            health_layout.addWidget(self.health_progress)
            
            self.smart_status_label = QLabel("SMART Status: Loading...")
            health_layout.addWidget(self.smart_status_label)
            
            layout.addWidget(health_group)
            
            # Key metrics group
            metrics_group = QGroupBox("Key Metrics")
            metrics_layout = QVBoxLayout(metrics_group)
            
            self.metrics_labels = {}
            for key in ["Temperature", "Power On Hours", "Power Cycles", "SSD Life Left"]:
                label = QLabel(f"{key}: Loading...")
                self.metrics_labels[key] = label
                metrics_layout.addWidget(label)
            
            layout.addWidget(metrics_group)
            
            return widget
        
        def _create_attributes_tab(self) -> QWidget:
            """Create SMART attributes tab"""
            widget = QWidget()
            layout = QVBoxLayout(widget)
            
            self.attributes_table = QTableWidget()
            self.attributes_table.setColumnCount(8)
            self.attributes_table.setHorizontalHeaderLabels([
                "ID", "Attribute", "Value", "Worst", "Threshold", "Raw Value", "Flags", "Status"
            ])
            self.attributes_table.horizontalHeader().setStretchLastSection(True)
            layout.addWidget(self.attributes_table)
            
            return widget
        
        def _create_history_tab(self) -> QWidget:
            """Create history tab"""
            widget = QWidget()
            layout = QVBoxLayout(widget)
            
            # History controls
            controls_layout = QHBoxLayout()
            controls_layout.addWidget(QLabel("Days:"))
            
            self.history_days_spin = QSpinBox()
            self.history_days_spin.setRange(1, 365)
            self.history_days_spin.setValue(30)
            self.history_days_spin.valueChanged.connect(self.load_history)
            controls_layout.addWidget(self.history_days_spin)
            
            refresh_history_btn = QPushButton("Refresh")
            refresh_history_btn.clicked.connect(self.load_history)
            controls_layout.addWidget(refresh_history_btn)
            
            controls_layout.addStretch()
            layout.addLayout(controls_layout)
            
            # History table
            self.history_table = QTableWidget()
            self.history_table.setColumnCount(6)
            self.history_table.setHorizontalHeaderLabels([
                "Timestamp", "Health Score", "Temperature", "Status", "Power Hours", "Issues"
            ])
            layout.addWidget(self.history_table)
            
            return widget
        
        def _create_config_tab(self) -> QWidget:
            """Create configuration tab"""
            widget = QWidget()
            layout = QVBoxLayout(widget)
            
            # Monitoring settings
            monitoring_group = QGroupBox("Monitoring Settings")
            monitoring_layout = QVBoxLayout(monitoring_group)
            
            self.monitoring_enabled_cb = QCheckBox("Enable monitoring for this drive")
            monitoring_layout.addWidget(self.monitoring_enabled_cb)
            
            # Alert thresholds
            thresholds_layout = QHBoxLayout()
            
            thresholds_layout.addWidget(QLabel("Health threshold:"))
            self.health_threshold_spin = QDoubleSpinBox()
            self.health_threshold_spin.setRange(0.0, 100.0)
            self.health_threshold_spin.setValue(20.0)
            self.health_threshold_spin.setSuffix("%")
            thresholds_layout.addWidget(self.health_threshold_spin)
            
            thresholds_layout.addWidget(QLabel("Temperature threshold:"))
            self.temp_threshold_spin = QSpinBox()
            self.temp_threshold_spin.setRange(30, 100)
            self.temp_threshold_spin.setValue(60)
            self.temp_threshold_spin.setSuffix("°C")
            thresholds_layout.addWidget(self.temp_threshold_spin)
            
            monitoring_layout.addLayout(thresholds_layout)
            
            # Monitoring interval
            interval_layout = QHBoxLayout()
            interval_layout.addWidget(QLabel("Monitoring interval:"))
            self.interval_spin = QSpinBox()
            self.interval_spin.setRange(60, 3600)
            self.interval_spin.setValue(300)
            self.interval_spin.setSuffix(" seconds")
            interval_layout.addWidget(self.interval_spin)
            
            monitoring_layout.addLayout(interval_layout)
            
            layout.addWidget(monitoring_group)
            
            # Save button
            save_config_btn = QPushButton("Save Configuration")
            save_config_btn.clicked.connect(self.save_configuration)
            layout.addWidget(save_config_btn)
            
            layout.addStretch()
            
            return widget
        
        def load_smart_data(self):
            """Load current SMART data"""
            smart_data = self.smart_monitor.get_smart_data(self.device_path)
            
            if smart_data:
                # Update device info
                self.device_info_labels["Model"].setText(f"Model: {smart_data.device_model}")
                self.device_info_labels["Serial"].setText(f"Serial: {smart_data.serial_number}")
                self.device_info_labels["Firmware"].setText(f"Firmware: {smart_data.firmware_version}")
                self.device_info_labels["Capacity"].setText(f"Capacity: {smart_data.capacity}")
                self.device_info_labels["Type"].setText(f"Type: {smart_data.drive_type.value}")
                
                # Update health status
                self.health_score_label.setText(f"Health Score: {smart_data.health_score:.1f}%")
                self.health_progress.setValue(int(smart_data.health_score))
                
                # Color code health score
                if smart_data.health_score >= 80:
                    color = "#4CAF50"
                elif smart_data.health_score >= 50:
                    color = "#FFC107"
                else:
                    color = "#FF3B30"
                
                self.health_score_label.setStyleSheet(f"color: {color};")
                
                self.smart_status_label.setText(f"SMART Status: {smart_data.smart_status.value}")
                
                # Update metrics
                temp_text = f"{smart_data.temperature}°C" if smart_data.temperature else "N/A"
                self.metrics_labels["Temperature"].setText(f"Temperature: {temp_text}")
                
                hours_text = str(smart_data.power_on_hours) if smart_data.power_on_hours else "N/A"
                self.metrics_labels["Power On Hours"].setText(f"Power On Hours: {hours_text}")
                
                cycles_text = str(smart_data.power_cycle_count) if smart_data.power_cycle_count else "N/A"
                self.metrics_labels["Power Cycles"].setText(f"Power Cycles: {cycles_text}")
                
                life_text = f"{smart_data.ssd_life_left}%" if smart_data.ssd_life_left else "N/A"
                self.metrics_labels["SSD Life Left"].setText(f"SSD Life Left: {life_text}")
                
                # Update attributes table
                self.load_attributes(smart_data.attributes)
            
            # Load configuration
            self.load_configuration()
        
        def load_attributes(self, attributes: Dict):
            """Load SMART attributes into table"""
            self.attributes_table.setRowCount(len(attributes))
            
            for i, (attr_id, attr) in enumerate(attributes.items()):
                self.attributes_table.setItem(i, 0, QTableWidgetItem(str(attr.id)))
                self.attributes_table.setItem(i, 1, QTableWidgetItem(attr.name))
                self.attributes_table.setItem(i, 2, QTableWidgetItem(str(attr.value)))
                self.attributes_table.setItem(i, 3, QTableWidgetItem(str(attr.worst)))
                self.attributes_table.setItem(i, 4, QTableWidgetItem(str(attr.threshold)))
                self.attributes_table.setItem(i, 5, QTableWidgetItem(str(attr.raw_value)))
                self.attributes_table.setItem(i, 6, QTableWidgetItem(attr.flags))
                
                # Status based on critical state
                status = "Critical" if attr.is_critical else "OK"
                status_item = QTableWidgetItem(status)
                if attr.is_critical:
                    status_item.setForeground(QColor("#FF3B30"))
                else:
                    status_item.setForeground(QColor("#4CAF50"))
                
                self.attributes_table.setItem(i, 7, status_item)
        
        def load_history(self):
            """Load historical data"""
            days = self.history_days_spin.value()
            history = self.smart_monitor.get_device_history(self.device_path, days)
            
            self.history_table.setRowCount(len(history))
            
            for i, record in enumerate(history):
                timestamp = datetime.fromisoformat(record['timestamp']).strftime("%Y-%m-%d %H:%M")
                self.history_table.setItem(i, 0, QTableWidgetItem(timestamp))
                self.history_table.setItem(i, 1, QTableWidgetItem(f"{record['health_score']:.1f}%"))
                
                temp_text = f"{record['temperature']}°C" if record['temperature'] else "N/A"
                self.history_table.setItem(i, 2, QTableWidgetItem(temp_text))
                
                self.history_table.setItem(i, 3, QTableWidgetItem(record['smart_status']))
                
                hours_text = str(record['power_on_hours']) if record['power_on_hours'] else "N/A"
                self.history_table.setItem(i, 4, QTableWidgetItem(hours_text))
                
                # Simple issues summary
                issues = []
                if record['reallocated_sectors'] and record['reallocated_sectors'] > 0:
                    issues.append(f"Reallocated: {record['reallocated_sectors']}")
                if record['pending_sectors'] and record['pending_sectors'] > 0:
                    issues.append(f"Pending: {record['pending_sectors']}")
                
                issues_text = ", ".join(issues) if issues else "None"
                self.history_table.setItem(i, 5, QTableWidgetItem(issues_text))
        
        def load_configuration(self):
            """Load device configuration"""
            config = self.smart_monitor.get_device_config(self.device_path)
            
            self.monitoring_enabled_cb.setChecked(config.get('monitoring_enabled', True))
            self.health_threshold_spin.setValue(config.get('alert_threshold_health', 20.0))
            self.temp_threshold_spin.setValue(config.get('alert_threshold_temp', 60))
            self.interval_spin.setValue(config.get('monitoring_interval', 300))
        
        def save_configuration(self):
            """Save device configuration"""
            config = {
                'monitoring_enabled': self.monitoring_enabled_cb.isChecked(),
                'alert_threshold_health': self.health_threshold_spin.value(),
                'alert_threshold_temp': self.temp_threshold_spin.value(),
                'monitoring_interval': self.interval_spin.value()
            }
            
            self.smart_monitor.configure_device_monitoring(self.device_path, config)
            QMessageBox.information(self, "Configuration Saved", "Device monitoring configuration has been saved.")


else:
    # Dummy classes when GUI is not available
    class SMARTOverviewWidget:
        def __init__(self, parent=None):
            pass
    
    class SMARTDetailWidget:
        def __init__(self, device_path: str, parent=None):
            pass
