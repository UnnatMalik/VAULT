from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QPushButton, QFileDialog,
    QMessageBox, QTextEdit, QLabel, QSpinBox, QHBoxLayout, QTabWidget,
    QGroupBox, QFormLayout, QTableWidget, QAbstractItemView, QLineEdit,
    QProgressBar, QTableWidgetItem, QSplitter, QFrame, QHeaderView,
    QScrollArea, QSizePolicy
)
from pathlib import Path
from typing import Optional
from datetime import datetime
from PySide6.QtCore import QObject, Signal, QThread, Qt, QDateTime, QSize
from PySide6.QtGui import QFont, QIcon, QColor
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from metadata_worker import MetadataWorker
import uuid
import subprocess
import platform
import re
import traceback
# Import all required dependencies from secure_purge.py
from secure_purge import (
    SystemInfoCollector,
    LogDatabaseManager, 
    WipeOrchestratorMCP,
    ConsoleLogger,
    Logger,
    verify_manifest_deletions,
    ensure_keys,
    _perform_secure_purge_logic
)

# Import SMART monitoring components
try:
    from smart_gui import SMARTOverviewWidget, SMARTDetailWidget
    from smart_worker import SMARTMonitor
    SMART_AVAILABLE = True
except ImportError as e:
    print(f"SMART monitoring not available: {e}")
    SMART_AVAILABLE = False


APP_COLORS = {
    "background": "#0E1116",
    "panel": "#141617",
    "card": "#1A1D21",
    "border": "#333333",
    "text_primary": "#E6E6E6",
    "text_muted": "#9AA0A6",
    "signal_green": "#4CAF50",
    "signal_amber": "#FFC107",
    "signal_red": "#FF3B30",
    "accent_blue": "#3A7AFE"
}

APP_FONT_FAMILY = "Inter, 'Segoe UI', sans-serif"

LOG_FONT_FAMILY = "Consolas, 'Courier New', monospace"


def create_log_font(point_size: int = 12) -> QFont:
    font = QFont("Consolas")
    if font.family().lower() != "consolas":
        font.setStyleHint(QFont.TypeWriter)
    font.setPointSize(point_size)
    return font

PRIMARY_BUTTON_STYLE = f"""
QPushButton {{
    background-color: {APP_COLORS["signal_green"]};
    border: none;
    border-radius: 10px;
    padding: 10px 18px;
    color: #0E1116;
    font-weight: 600;
}}
QPushButton:hover {{
    background-color: #5EC85F;
}}
QPushButton:pressed {{
    background-color: #3D8B3F;
}}
QPushButton:disabled {{
    background-color: #2C332F;
    color: {APP_COLORS["text_muted"]};
}}
"""

SECONDARY_BUTTON_STYLE = f"""
QPushButton {{
    background-color: transparent;
    border: 1px solid {APP_COLORS["text_muted"]};
    border-radius: 10px;
    padding: 8px 16px;
    color: {APP_COLORS["text_muted"]};
    font-weight: 500;
}}
QPushButton:hover {{
    border-color: {APP_COLORS["signal_green"]};
    color: {APP_COLORS["text_primary"]};
}}
QPushButton:pressed {{
    background-color: rgba(76, 175, 80, 0.15);
}}
"""

# The `HomeTab` class in Python creates a graphical user interface for displaying storage and system
# information using Qt widgets.
class HomeTab(QWidget):
        def __init__(self):
            super().__init__()
            self.setObjectName("HomeTab")
            self.system_info_collector = SystemInfoCollector()
            main_layout = QVBoxLayout()
            main_layout.setContentsMargins(24, 24, 24, 24)
            main_layout.setSpacing(14)
            self.setLayout(main_layout)

            self._apply_theme()
            self._setup_ui()
            # Load data asynchronously after GUI is shown to prevent blocking
            from PySide6.QtCore import QTimer
            QTimer.singleShot(100, self._load_data)

        def _setup_ui(self):
            layout = self.layout()

            title_label = QLabel("System Details")
            title_label.setObjectName("homeTitle")
            layout.addWidget(title_label)

            subtitle = QLabel("Unified view of platform health, storage utilization, and key system diagnostics.")
            subtitle.setObjectName("homeSubtitle")
            layout.addWidget(subtitle)

            cards_layout = QHBoxLayout()
            cards_layout.setSpacing(12)
            cards_layout.setContentsMargins(0, 0, 0, 0)
            self.summary_metrics = {}
            metric_specs = [
                ("os", "Operating System"),
                ("cpu", "CPU Load"),
                ("memory", "Memory"),
                ("battery", "Battery"),
            ]
            for key, label_text in metric_specs:
                card, value_label = self._create_metric_card(label_text)
                cards_layout.addWidget(card)
                self.summary_metrics[key] = value_label
            cards_layout.addStretch()
            layout.addLayout(cards_layout)

            self.details_group = QGroupBox("System Details")
            self.details_group.setObjectName("homeSectionGroup")
            details_layout = QFormLayout()
            details_layout.setLabelAlignment(Qt.AlignLeft)
            details_layout.setFormAlignment(Qt.AlignTop)
            details_layout.setHorizontalSpacing(36)
            details_layout.setVerticalSpacing(10)
            self.system_details_labels = {
                "Node": QLabel("—"),
                "Architecture": QLabel("—"),
                "Processor": QLabel("—"),
                "Cores": QLabel("—"),
            }
            for title, value_label in self.system_details_labels.items():
                value_label.setObjectName("homeDetailValue")
                details_layout.addRow(self._detail_label(title), value_label)
            self.details_group.setLayout(details_layout)
            layout.addWidget(self.details_group)

            self.drive_group = QGroupBox("Storage Devices")
            self.drive_group.setObjectName("homeSectionGroup")
            drive_group_layout = QVBoxLayout()
            drive_group_layout.setContentsMargins(16, 12, 16, 16)
            drive_group_layout.setSpacing(12)

            self.drive_scroll = QScrollArea()
            self.drive_scroll.setWidgetResizable(True)
            self.drive_scroll.setObjectName("driveScroll")

            self.drive_container = QWidget()
            self.drive_container_layout = QVBoxLayout()
            self.drive_container_layout.setContentsMargins(0, 0, 0, 0)
            self.drive_container_layout.setSpacing(12)
            self.drive_container.setLayout(self.drive_container_layout)

            self.drive_scroll.setWidget(self.drive_container)
            drive_group_layout.addWidget(self.drive_scroll)
            self.drive_group.setLayout(drive_group_layout)
            layout.addWidget(self.drive_group, 1)

            layout.addStretch()

        def _load_data(self):
            disk_info = self.system_info_collector.get_disk_info()
            self._update_storage_visualization(disk_info)
            self._update_system_summary()

        def _update_storage_visualization(self, disk_info):
            while self.drive_container_layout.count():
                child = self.drive_container_layout.takeAt(0)
                if child.widget():
                    child.widget().deleteLater()

            if not disk_info:
                empty_label = QLabel("No storage devices detected.")
                empty_label.setObjectName("homeMutedLabel")
                self.drive_container_layout.addWidget(empty_label)
                return

            for disk in disk_info:
                disk_card = QFrame()
                disk_card.setObjectName("driveCard")
                disk_layout = QVBoxLayout(disk_card)
                disk_layout.setContentsMargins(16, 12, 16, 12)
                disk_layout.setSpacing(6)

                header = QLabel(f"{disk.get('Device', 'Unknown')} · {disk.get('Mountpoint', '-')}")
                header.setObjectName("driveHeader")
                header.setWordWrap(True)
                disk_layout.addWidget(header)

                usage_label = QLabel(f"{disk.get('Used', '0')} of {disk.get('Total', '0')} used · {disk.get('Free', '0')} free")
                usage_label.setObjectName("homeMutedLabel")
                disk_layout.addWidget(usage_label)

                progress = QProgressBar()
                progress.setRange(0, 100)
                try:
                    percentage = float(disk.get('Percentage', '0').replace('%', ''))
                except (ValueError, TypeError):
                    percentage = 0.0
                progress.setValue(int(percentage))
                progress.setFormat(f"{percentage:.1f}% occupied")
                progress.setAlignment(Qt.AlignCenter)
                progress.setFixedHeight(26)

                chunk_color = APP_COLORS["accent_blue"]
                if percentage >= 90:
                    chunk_color = APP_COLORS["signal_red"]
                elif percentage >= 75:
                    chunk_color = APP_COLORS["signal_amber"]

                progress.setStyleSheet(
                    f"""
                    QProgressBar {{
                        background-color: {APP_COLORS['panel']};
                        border: 1px solid #1F2428;
                        border-radius: 10px;
                        color: {APP_COLORS['text_primary']};
                        font-weight: 600;
                    }}
                    QProgressBar::chunk {{
                        border-radius: 10px;
                        background-color: {chunk_color};
                    }}
                    """
                )
                disk_layout.addWidget(progress)

                meta_label = QLabel(
                    f"Type: {disk.get('Type', '—')} · SMART: {disk.get('SMART Status', 'Unavailable')} · Temp: {disk.get('Temperature', 'N/A')}"
                )
                meta_label.setObjectName("homeMutedLabel")
                meta_label.setWordWrap(True)
                disk_layout.addWidget(meta_label)

                self.drive_container_layout.addWidget(disk_card)
        
        def _create_text_battery(self, percentage_str: str) -> str:
            # This method is no longer used for visualization, but kept for potential debugging/legacy
            percentage = float(percentage_str.replace('%', ''))
            blocks = int(percentage // 10)
            return f"[{'#' * blocks}{'-' * (10 - blocks)}] {percentage:.1f}%"

        def _update_system_summary(self):
            os_info = self.system_info_collector.get_os_info()
            cpu_info = self.system_info_collector.get_cpu_info()
            mem_info = self.system_info_collector.get_memory_info()
            detailed_hardware_info = self.system_info_collector.get_detailed_hardware_info()

            os_summary = f"{os_info.get('System', '-') } {os_info.get('Release', '')}".strip()
            cpu_summary = f"{cpu_info.get('Total Usage', '-')} @ {cpu_info.get('Current Frequency', '-') }"
            memory_summary = f"{mem_info.get('Used', '-') } / {mem_info.get('Total', '-') } ({mem_info.get('Percentage', '-')})"

            battery_info = self.system_info_collector.get_battery_info()
            if 'Charge' in battery_info:
                battery_summary = f"{battery_info['Charge']} ({battery_info.get('Status', '-')})"
            else:
                battery_summary = battery_info.get('Status', 'Unavailable')

            self.summary_metrics['os'].setText(os_summary or '—')
            self.summary_metrics['cpu'].setText(cpu_summary)
            self.summary_metrics['memory'].setText(memory_summary)
            self.summary_metrics['battery'].setText(battery_summary)

            self.system_details_labels['Node'].setText(os_info.get('Node Name', '—'))
            self.system_details_labels['Architecture'].setText(f"{os_info.get('Machine', '-') } / {os_info.get('Processor', '-') }")
            processor_display = cpu_info.get('Brand') or cpu_info.get('Processor') or cpu_info.get('Current Frequency', '—')
            self.system_details_labels['Processor'].setText(processor_display)
            self.system_details_labels['Cores'].setText(f"{cpu_info.get('Total Cores', '—')} cores")

            if detailed_hardware_info:
                extra_details = []
                for key, value in detailed_hardware_info.items():
                    extra_details.append(f"{key}: {value}")
                self.details_group.setToolTip("\n".join(extra_details))
            else:
                self.details_group.setToolTip("")

        def _create_metric_card(self, title: str):
            card = QFrame()
            card.setObjectName("homeMetricCard")
            layout = QVBoxLayout(card)
            layout.setContentsMargins(18, 16, 18, 16)
            layout.setSpacing(8)

            title_label = QLabel(title)
            title_label.setObjectName("homeMetricTitle")
            value_label = QLabel("—")
            value_label.setObjectName("homeMetricValue")

            layout.addWidget(title_label)
            layout.addWidget(value_label)
            layout.addStretch()

            return card, value_label

        def _detail_label(self, text: str):
            label = QLabel(text.upper())
            label.setObjectName("homeDetailLabel")
            return label

        def _apply_theme(self):
            self.setStyleSheet(
                f"""
                QWidget#HomeTab {{
                    background-color: {APP_COLORS['background']};
                    color: {APP_COLORS['text_primary']};
                    font-family: {APP_FONT_FAMILY};
                }}
                QLabel#homeTitle {{
                    font-size: 28px;
                    font-weight: 700;
                }}
                QLabel#homeSubtitle {{
                    font-size: 14px;
                    color: {APP_COLORS['text_muted']};
                }}
                QFrame#homeMetricCard {{
                    background-color: {APP_COLORS['panel']};
                    border-radius: 18px;
                    border: 1px solid #1F2428;
                    min-width: 200px;
                }}
                QLabel#homeMetricTitle {{
                    font-size: 12px;
                    letter-spacing: 1px;
                    text-transform: uppercase;
                    color: {APP_COLORS['text_muted']};
                    font-weight: 600;
                }}
                QLabel#homeMetricValue {{
                    font-size: 22px;
                    font-weight: 700;
                }}
                QGroupBox#homeSectionGroup {{
                    background-color: {APP_COLORS['panel']};
                    border-radius: 20px;
                    border: 1px solid #1F2428;
                    margin-top: 22px;
                    font-size: 13px;
                    font-weight: 600;
                    text-transform: uppercase;
                    letter-spacing: 1px;
                    color: {APP_COLORS['text_muted']};
                }}
                QGroupBox#homeSectionGroup::title {{
                    subcontrol-origin: margin;
                    subcontrol-position: top left;
                    padding: 6px 12px;
                }}
                QLabel#homeDetailLabel {{
                    font-size: 11px;
                    font-weight: 600;
                    color: {APP_COLORS['text_muted']};
                    letter-spacing: 1px;
                }}
                QLabel#homeDetailValue {{
                    font-size: 15px;
                    font-weight: 600;
                    color: {APP_COLORS['text_primary']};
                }}
                QLabel#homeMutedLabel {{
                    color: {APP_COLORS['text_muted']};
                    font-size: 12px;
                }}
                QLabel#driveHeader {{
                    font-size: 16px;
                    font-weight: 700;
                }}
                QFrame#driveCard {{
                    background-color: {APP_COLORS['card']};
                    border-radius: 16px;
                    border: 1px solid #1F2428;
                }}
                QScrollArea#driveScroll {{
                    border: none;
                    background: transparent;
                }}
                QScrollArea#driveScroll > QWidget {{
                    background: transparent;
                }}
                QScrollArea#homeScrollArea {{
                    border: none;
                    background: transparent;
                }}
                QScrollArea#homeScrollArea > QWidget {{
                    background: transparent;
                }}
                """
            )


# The `MaintenanceTab` class in Python creates a GUI tab for displaying drive health status, drive
# usage graph, and refurbish analytics using Qt widgets and matplotlib.
class MaintenanceTab(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("MaintenanceTab")
        self.system_info_collector = SystemInfoCollector()
        self._state_colors = {
            "critical": "#EF4444",
            "warning": "#F59E0B",
            "stable": "#22C55E"
        }
        
        # Initialize SMART monitoring if available
        self.smart_monitor = None
        if SMART_AVAILABLE:
            try:
                self.smart_monitor = SMARTMonitor()
            except Exception as e:
                print(f"Failed to initialize SMART monitor in MaintenanceTab: {e}")

        self._scroll_area = QScrollArea()
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setFrameShape(QFrame.NoFrame)
        self._scroll_area.setObjectName("maintenanceScrollArea")

        self._content_widget = QWidget()
        self._content_layout = QVBoxLayout()
        self._content_layout.setContentsMargins(24, 24, 24, 24)
        self._content_layout.setSpacing(12)
        self._content_widget.setLayout(self._content_layout)

        self._scroll_area.setWidget(self._content_widget)

        outer_layout = QVBoxLayout()
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.addWidget(self._scroll_area)
        self.setLayout(outer_layout)

        self._apply_theme()
        self._setup_ui()
        # Load data asynchronously after GUI is shown to prevent blocking
        from PySide6.QtCore import QTimer
        QTimer.singleShot(200, self._load_data)
        
        # SMART monitoring removed for cleaner interface

    def _setup_ui(self):
        layout = self._content_layout

        title = QLabel("Maintenance Dashboard")
        title.setObjectName("sectionTitle")
        layout.addWidget(title)

        metrics_layout = QHBoxLayout()
        metrics_layout.setContentsMargins(0, 0, 0, 0)
        metrics_layout.setSpacing(12)
        self.drive_count_card, self.drive_count_value = self._create_metric_card("Detected Drives", "0")
        self.avg_usage_card, self.avg_usage_value = self._create_metric_card("Average Utilization", "0%")
        self.hotspot_card, self.hotspot_value = self._create_metric_card("Most Utilized Drive", "—")
        metrics_layout.addWidget(self.drive_count_card)
        metrics_layout.addWidget(self.avg_usage_card)
        metrics_layout.addWidget(self.hotspot_card)
        metrics_layout.addStretch()
        layout.addLayout(metrics_layout)

        # SMART Health Overview Section - REMOVED for cleaner interface

        # Drive Health Section (Maintenance Signals)
        self.drive_health_group = QGroupBox("Drive Health Status")
        self.drive_health_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        drive_health_layout = QVBoxLayout()
        drive_health_layout.setContentsMargins(12, 10, 12, 12)
        drive_health_layout.setSpacing(12)

        self.drive_health_intro = QLabel("Real-time maintenance signals derived from live storage telemetry.")
        self.drive_health_intro.setObjectName("driveHealthIntro")
        self.drive_health_intro.setWordWrap(True)
        drive_health_layout.addWidget(self.drive_health_intro)

        self.drive_health_scroll = QScrollArea()
        self.drive_health_scroll.setObjectName("driveHealthScroll")
        self.drive_health_scroll.setWidgetResizable(True)
        self.drive_health_scroll.setFrameShape(QFrame.NoFrame)
        self.drive_health_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.drive_health_list_container = QWidget()
        self.drive_health_list_layout = QVBoxLayout(self.drive_health_list_container)
        self.drive_health_list_layout.setContentsMargins(0, 0, 0, 0)
        self.drive_health_list_layout.setSpacing(10)
        self.drive_health_scroll.setWidget(self.drive_health_list_container)

        drive_health_layout.addWidget(self.drive_health_scroll)

        self.drive_health_timestamp = QLabel("Last refreshed —")
        self.drive_health_timestamp.setObjectName("driveHealthTimestamp")
        drive_health_layout.addWidget(self.drive_health_timestamp)

        drive_health_layout.addStretch()
        self.drive_health_group.setLayout(drive_health_layout)
        layout.addWidget(self.drive_health_group)

        # Drive Usage Visualization Section (Maintenance Planner)
        self.graph_group = QGroupBox("Drive Usage Distribution")
        graph_layout = QVBoxLayout()
        graph_layout.setContentsMargins(16, 14, 16, 16)
        graph_layout.setSpacing(12)

        self.maintenance_overview_label = QLabel("Translate utilization into actionable cleanup and rotation plans.")
        self.maintenance_overview_label.setObjectName("maintenanceOverview")
        self.maintenance_overview_label.setWordWrap(True)
        graph_layout.addWidget(self.maintenance_overview_label)

        self.maintenance_summary_frame = QFrame()
        self.maintenance_summary_frame.setObjectName("maintenanceSummaryFrame")
        summary_layout = QHBoxLayout(self.maintenance_summary_frame)
        summary_layout.setContentsMargins(0, 0, 0, 0)
        summary_layout.setSpacing(12)
        self.maintenance_summary_chips = {}
        summary_specs = [
            ("critical", "Critical Alerts", self._state_colors["critical"]),
            ("warning", "Scheduled Tasks", self._state_colors["warning"]),
            ("stable", "Healthy Drives", self._state_colors["stable"])
        ]
        for key, title_text, color in summary_specs:
            chip = self._create_status_chip(title_text, color)
            chip["widget"].setAccessibleName(f"{title_text} summary chip")
            summary_layout.addWidget(chip["widget"])
            self.maintenance_summary_chips[key] = chip
        summary_layout.addStretch()
        graph_layout.addWidget(self.maintenance_summary_frame)

        self.maintenance_schedule_table = QTableWidget(0, 4)
        self.maintenance_schedule_table.setObjectName("maintenanceScheduleTable")
        self.maintenance_schedule_table.setHorizontalHeaderLabels([
            "Device", "Priority", "Recommended Action", "Suggested Window"
        ])
        self.maintenance_schedule_table.setAlternatingRowColors(True)
        self.maintenance_schedule_table.setShowGrid(False)
        self.maintenance_schedule_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.maintenance_schedule_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.maintenance_schedule_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.maintenance_schedule_table.verticalHeader().setVisible(False)
        schedule_header = self.maintenance_schedule_table.horizontalHeader()
        schedule_header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        schedule_header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        schedule_header.setSectionResizeMode(2, QHeaderView.Stretch)
        schedule_header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.maintenance_schedule_table.setMinimumHeight(240)
        self.maintenance_schedule_table.setAccessibleName("Drive maintenance recommendation table")
        graph_layout.addWidget(self.maintenance_schedule_table)

        self.timeline_container = QWidget()
        self.timeline_container.setObjectName("timelineContainer")
        self.timeline_layout = QVBoxLayout(self.timeline_container)
        self.timeline_layout.setContentsMargins(0, 4, 0, 0)
        self.timeline_layout.setSpacing(10)
        graph_layout.addWidget(self.timeline_container)

        self.graph_group.setLayout(graph_layout)
        layout.addWidget(self.graph_group)


        layout.addStretch()

    # SMART overview section removed for cleaner interface
    
    # SMART timer setup removed for cleaner interface

    # SMART card creation methods removed for cleaner interface
    
    
    

    # SMART overview update method removed for cleaner interface
    
    # SMART default values method removed for cleaner interface
    
    # SMART metric row update method removed for cleaner interface
    
    def _format_power_hours(self, power_hours_values):
        """Format power hours for display"""
        if not power_hours_values:
            return "N/A"
        
        avg_hours = sum(power_hours_values) / len(power_hours_values)
        
        # Convert to days for better readability
        if avg_hours > 8760:  # More than a year
            years = avg_hours / 8760
            return f"{years:.1f}y"
        elif avg_hours > 24:  # More than a day
            days = avg_hours / 24
            return f"{days:.0f}d"
        else:
            return f"{avg_hours:.0f}h"

    def _load_data(self):
        self._update_drive_health()
        self._update_drive_usage_visualization()

    def _update_drive_health(self):
        disks = self.system_info_collector.get_disk_info()

        drive_states = []
        usage_percentages = []
        most_utilized_state = None

        for disk in disks:
            state = self._evaluate_drive_state(disk)
            drive_states.append(state)
            if state["usage_percent"] is not None:
                usage_percentages.append(state["usage_percent"])
                if not most_utilized_state or state["usage_percent"] > most_utilized_state["usage_percent"]:
                    most_utilized_state = state

        drive_states.sort(key=lambda entry: entry["priority"])
        self._latest_drive_states = drive_states

        self.drive_count_value.setText(str(len(drive_states)))
        if usage_percentages:
            avg_usage = sum(usage_percentages) / len(usage_percentages)
            self.avg_usage_value.setText(f"{avg_usage:.0f}%")
            if most_utilized_state:
                hotspot_text = f"{most_utilized_state['device']} ({most_utilized_state['usage_percent']:.0f}%)"
                self.hotspot_value.setText(hotspot_text)
                self.hotspot_value.setStyleSheet(
                    f"font-size: 22px; font-weight: 700; color: {most_utilized_state['severity_color']};"
                )
        else:
            self.avg_usage_value.setText("0%")
            self.hotspot_value.setText("—")
            self.hotspot_value.setStyleSheet(
                f"font-size: 22px; font-weight: 700; color: {APP_COLORS['text_muted']};"
            )

        self._render_drive_health_signals(drive_states)

    def _update_drive_usage_visualization(self):
        """Update the drive maintenance planner with actionable tasks"""
        try:
            drive_states = getattr(self, "_latest_drive_states", None)
            if drive_states is None:
                disk_info = self.system_info_collector.get_disk_info()
                drive_states = [self._evaluate_drive_state(disk) for disk in disk_info]
                drive_states.sort(key=lambda entry: entry["priority"])
                self._latest_drive_states = drive_states

            for key, chip in self.maintenance_summary_chips.items():
                chip["value_label"].setText("0")

            self.maintenance_schedule_table.setRowCount(0)
            self._clear_layout(self.timeline_layout)

            if not drive_states:
                empty_label = QLabel("No drives detected. Connect a storage device to plan maintenance tasks.")
                empty_label.setObjectName("driveUsageEmpty")
                empty_label.setAlignment(Qt.AlignCenter)
                self.timeline_layout.addWidget(empty_label)
                self.timeline_layout.addStretch()
                return

            counts = {"critical": 0, "warning": 0, "stable": 0}
            for state in drive_states:
                counts[state["severity"]] += 1

            for key, value in counts.items():
                if key in self.maintenance_summary_chips:
                    self.maintenance_summary_chips[key]["value_label"].setText(str(value))

            self.maintenance_schedule_table.setRowCount(len(drive_states))
            for row, state in enumerate(drive_states):
                device_item = QTableWidgetItem(state["device"])
                device_item.setToolTip(f"Mount: {state['mountpoint']} • FS: {state['filesystem']}")
                priority_item = QTableWidgetItem(state["severity_label"])
                priority_item.setForeground(QColor(state["severity_color"]))
                action_item = QTableWidgetItem(state["action"])
                window_item = QTableWidgetItem(state["window"])
                for item in (device_item, priority_item, action_item, window_item):
                    item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                self.maintenance_schedule_table.setItem(row, 0, device_item)
                self.maintenance_schedule_table.setItem(row, 1, priority_item)
                self.maintenance_schedule_table.setItem(row, 2, action_item)
                self.maintenance_schedule_table.setItem(row, 3, window_item)

            actionable_states = [state for state in drive_states if state["severity"] != "stable"]
            if not actionable_states and drive_states:
                actionable_states = drive_states[:1]

            for state in actionable_states[:3]:
                card = self._create_timeline_card(state)
                self.timeline_layout.addWidget(card)

            self.timeline_layout.addStretch()

        except Exception as e:
            print(f"Error updating drive maintenance planner: {e}")
    
    def _parse_size_string(self, size_str: str) -> float:
        """Parse size string like '100 GB' to bytes"""
        if not size_str or size_str == '—':
            return 0.0
        
        parts = size_str.strip().split()
        if len(parts) != 2:
            return 0.0
        
        try:
            value = float(parts[0])
            unit = parts[1].upper()
            
            multipliers = {
                'B': 1,
                'KB': 1024,
                'MB': 1024**2,
                'GB': 1024**3,
                'TB': 1024**4
            }
            
            return value * multipliers.get(unit, 1)
        except (ValueError, KeyError):
            return 0.0
    
    def _apply_theme(self):
        self.setStyleSheet(
            f"""
            QWidget#MaintenanceTab {{
                background-color: {APP_COLORS["background"]};
                color: {APP_COLORS["text_primary"]};
                font-family: {APP_FONT_FAMILY};
            }}
            QLabel#sectionTitle {{
                font-size: 24px;
                font-weight: 700;
                color: {APP_COLORS["text_primary"]};
            }}
            QGroupBox {{
                background-color: {APP_COLORS["panel"]};
                border: 1px solid #1F2428;
                border-radius: 14px;
                margin-top: 20px;
                padding: 20px 16px 16px 16px;
                font-size: 13px;
                font-weight: 600;
                text-transform: uppercase;
                letter-spacing: 1px;
                color: {APP_COLORS["text_muted"]};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 8px 12px;
                margin-top: -10px;
                background-color: transparent;
                color: {APP_COLORS["text_primary"]};
                font-weight: 700;
                font-size: 14px;
            }}
            QTableWidget {{
                background-color: {APP_COLORS["card"]};
                border: 1px solid #1F2428;
                border-radius: 10px;
                gridline-color: #1F2428;
                selection-background-color: rgba(76, 175, 80, 0.2);
                selection-color: {APP_COLORS["text_primary"]};
            }}
            QHeaderView::section {{
                background-color: {APP_COLORS["panel"]};
                color: {APP_COLORS["text_muted"]};
                border: none;
                padding: 8px 10px;
                font-weight: 600;
            }}
            QTableWidget::item {{
                padding: 8px;
            }}
            QFrame#metricCardFrame {{
                background-color: {APP_COLORS["panel"]};
                border: 1px solid #1F2428;
                border-radius: 16px;
            }}
            QLabel#metricTitle {{
                font-size: 12px;
                font-weight: 600;
                text-transform: uppercase;
                color: {APP_COLORS["text_muted"]};
                letter-spacing: 1px;
            }}
            QLabel#metricValue {{
                font-size: 22px;
                font-weight: 700;
                color: {APP_COLORS["text_primary"]};
            }}
            QScrollArea#maintenanceScrollArea {{
                border: none;
                background: transparent;
            }}
            QScrollArea#maintenanceScrollArea > QWidget {{
                background: transparent;
            }}
            QLabel#driveUsageEmpty {{
                font-size: 14px;
                color: {APP_COLORS["text_muted"]};
                padding: 20px;
            }}
            QLabel#driveHealthIntro {{
                font-size: 12px;
                color: {APP_COLORS["text_muted"]};
            }}
            QScrollArea#driveHealthScroll {{
                border: none;
                background: transparent;
            }}
            QScrollArea#driveHealthScroll > QWidget {{
                background: transparent;
            }}
            QFrame#driveHealthRow {{
                background-color: {APP_COLORS["card"]};
                border: 1px solid #2A2D32;
                border-radius: 12px;
            }}
            QLabel#driveHealthDevice {{
                font-size: 13px;
                font-weight: 600;
                color: {APP_COLORS["text_primary"]};
            }}
            QLabel#driveHealthMeta {{
                font-size: 11px;
                color: {APP_COLORS["text_muted"]};
            }}
            QLabel#driveHealthAction {{
                font-size: 12px;
                color: {APP_COLORS["text_primary"]};
            }}
            QLabel#driveHealthTimestamp {{
                font-size: 11px;
                color: {APP_COLORS["text_muted"]};
            }}
            QLabel#maintenanceOverview {{
                font-size: 12px;
                color: {APP_COLORS["text_muted"]};
            }}
            QFrame#maintenanceSummaryFrame {{
                background-color: transparent;
            }}
            QFrame#statusChip {{
                background-color: {APP_COLORS["card"]};
                border-radius: 12px;
                border: 1px solid #2A2D32;
            }}
            QLabel#statusChipTitle {{
                font-size: 11px;
                font-weight: 600;
                color: {APP_COLORS["text_muted"]};
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }}
            QLabel#statusChipValue {{
                font-size: 18px;
                font-weight: 700;
                color: {APP_COLORS["text_primary"]};
            }}
            QTableWidget#maintenanceScheduleTable {{
                background-color: {APP_COLORS["card"]};
                border: 1px solid #1F2428;
                border-radius: 10px;
                gridline-color: #1F2428;
                selection-background-color: rgba(34, 197, 94, 0.18);
                selection-color: {APP_COLORS["text_primary"]};
            }}
            QFrame#timelineCard {{
                background-color: {APP_COLORS["card"]};
                border: 1px solid #2A2D32;
                border-radius: 12px;
            }}
            QLabel#timelineTitle {{
                font-size: 13px;
                font-weight: 600;
                color: {APP_COLORS["text_primary"]};
            }}
            QLabel#timelineWindow {{
                font-size: 12px;
                color: {APP_COLORS["text_primary"]};
            }}
            QLabel#timelineDetails {{
                font-size: 11px;
                color: {APP_COLORS["text_muted"]};
            }}
            """
        )

    def _create_metric_card(self, title: str, value: str):
        card = QFrame()
        card.setObjectName("metricCardFrame")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(6)
        title_label = QLabel(title)
        title_label.setObjectName("metricTitle")
        value_label = QLabel(value)
        value_label.setObjectName("metricValue")
        layout.addWidget(title_label)
        layout.addWidget(value_label)
        layout.addStretch()
        card.setMinimumWidth(180)
        return card, value_label

    def _create_status_chip(self, title: str, color: str):
        chip = QFrame()
        chip.setObjectName("statusChip")
        chip_layout = QHBoxLayout(chip)
        chip_layout.setContentsMargins(12, 10, 12, 10)
        chip_layout.setSpacing(10)

        indicator = QFrame()
        indicator.setFixedWidth(4)
        indicator.setObjectName("statusChipIndicator")
        indicator.setStyleSheet(f"background-color: {color}; border-radius: 2px;")
        chip_layout.addWidget(indicator)

        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(2)

        title_label = QLabel(title)
        title_label.setObjectName("statusChipTitle")
        value_label = QLabel("0")
        value_label.setObjectName("statusChipValue")

        text_layout.addWidget(title_label)
        text_layout.addWidget(value_label)
        chip_layout.addLayout(text_layout)

        return {"widget": chip, "value_label": value_label}

    def _render_drive_health_signals(self, drive_states: list[dict]):
        self._clear_layout(self.drive_health_list_layout)

        if not drive_states:
            empty_label = QLabel("No drive telemetry available.")
            empty_label.setObjectName("driveUsageEmpty")
            empty_label.setAlignment(Qt.AlignCenter)
            self.drive_health_list_layout.addWidget(empty_label)
            self.drive_health_timestamp.setText("Last refreshed —")
            return

        for state in drive_states:
            row = self._create_health_signal_row(state)
            self.drive_health_list_layout.addWidget(row)

        self.drive_health_list_layout.addStretch()
        self.drive_health_timestamp.setText(f"Last refreshed {datetime.now().strftime('%H:%M:%S')}")

    def _create_health_signal_row(self, state: dict):
        row = QFrame()
        row.setObjectName("driveHealthRow")
        row.setAccessibleName(
            f"{state['device']} status {state['severity_label']} with action {state['action']}"
        )
        row.setFocusPolicy(Qt.StrongFocus)

        layout = QVBoxLayout(row)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(8)

        indicator = QLabel()
        indicator.setFixedSize(10, 10)
        indicator.setStyleSheet(
            f"background-color: {state['severity_color']}; border-radius: 5px;"
        )
        indicator.setAccessibleName(f"{state['severity_label']} indicator")
        header_layout.addWidget(indicator)

        device_label = QLabel(f"{state['device']} • {state['model']}")
        device_label.setObjectName("driveHealthDevice")
        device_label.setToolTip(f"Mounted at {state['mountpoint']} ({state['filesystem']})")
        header_layout.addWidget(device_label)

        header_layout.addStretch()

        badge = QLabel(state["severity_label"])
        badge.setStyleSheet(
            f"border: 1px solid {state['severity_color']}; border-radius: 9px; padding: 2px 8px;"
            f"color: {state['severity_color']}; font-size: 11px; font-weight: 600; text-transform: uppercase;"
        )
        header_layout.addWidget(badge)

        layout.addLayout(header_layout)

        progress = QProgressBar()
        progress.setRange(0, 100)
        progress.setValue(int(state["usage_percent"] or 0))
        progress.setTextVisible(False)
        progress.setFixedHeight(8)
        progress.setStyleSheet(
            "QProgressBar { background-color: #0E1116; border: 1px solid #2A2D32; border-radius: 4px; }"
            f"QProgressBar::chunk {{ background-color: {state['severity_color']}; border-radius: 4px; }}"
        )
        layout.addWidget(progress)

        meta_label = QLabel(
            f"Utilization {state['usage_percent']:.1f}% • Free {state['free_display']} • Total {state['total_display']}"
        )
        meta_label.setObjectName("driveHealthMeta")
        layout.addWidget(meta_label)

        action_label = QLabel(state["action"])
        action_label.setObjectName("driveHealthAction")
        action_label.setWordWrap(True)
        layout.addWidget(action_label)

        return row

    def _create_timeline_card(self, state: dict):
        card = QFrame()
        card.setObjectName("timelineCard")
        card.setAccessibleName(
            f"{state['severity_label']} task for {state['device']} within {state['window']}"
        )
        card.setFocusPolicy(Qt.StrongFocus)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        title_layout = QHBoxLayout()
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(8)

        indicator = QLabel()
        indicator.setFixedSize(10, 10)
        indicator.setStyleSheet(
            f"background-color: {state['severity_color']}; border-radius: 5px;"
        )
        title_layout.addWidget(indicator)

        title_label = QLabel(state["action"])
        title_label.setObjectName("timelineTitle")
        title_layout.addWidget(title_label)
        title_layout.addStretch()

        window_label = QLabel(state["window"])
        window_label.setObjectName("timelineWindow")
        window_label.setStyleSheet(f"color: {state['severity_color']}; font-weight: 600;")
        title_layout.addWidget(window_label)

        layout.addLayout(title_layout)

        subtitle = QLabel(f"Target: {state['device']} • {state['severity_label']}")
        subtitle.setObjectName("timelineDetails")
        layout.addWidget(subtitle)

        detail_label = QLabel(
            f"Mount {state['mountpoint']} • Free {state['free_display']} • Filesystem {state['filesystem']}"
        )
        detail_label.setObjectName("timelineDetails")
        layout.addWidget(detail_label)

        return card

    def _clear_layout(self, layout: QVBoxLayout):
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())

    def _evaluate_drive_state(self, disk: dict) -> dict:
        device = disk.get("Device", "Unknown")
        model = disk.get("Model") or disk.get("Filesystem Type", "Unknown FS")
        mountpoint = disk.get("Mountpoint", "—")
        filesystem = disk.get("Filesystem Type", "—")
        usage_raw = disk.get("Percentage", "0%")
        free_display = disk.get("Free", "—")
        total_display = disk.get("Total", "—")

        try:
            usage_percent = float(str(usage_raw).replace("%", ""))
        except (TypeError, ValueError):
            usage_percent = 0.0

        free_bytes = self._parse_size_string(free_display)
        total_bytes = self._parse_size_string(total_display)

        if usage_percent >= 90:
            severity = "critical"
            severity_label = "Critical"
            priority = 0
        elif usage_percent >= 75:
            severity = "warning"
            severity_label = "Warning"
            priority = 1
        else:
            severity = "stable"
            severity_label = "Stable"
            priority = 2

        action, window = self._derive_action_plan(severity, usage_percent, free_bytes)

        return {
            "device": device.replace("/dev/", ""),
            "model": model,
            "mountpoint": mountpoint,
            "filesystem": filesystem,
            "usage_percent": usage_percent,
            "free_display": free_display,
            "total_display": total_display,
            "severity": severity,
            "severity_label": severity_label,
            "severity_color": self._state_colors.get(severity, self._state_colors["stable"]),
            "priority": priority,
            "action": action,
            "window": window
        }

    def _derive_action_plan(self, severity: str, usage_percent: float, free_bytes: float) -> tuple[str, str]:
        free_gb = free_bytes / (1024 ** 3) if free_bytes else 0

        if severity == "critical":
            return (
                "Initiate emergency purge and migrate cold data immediately.",
                "Within 24 hours"
            )
        if severity == "warning":
            if free_gb <= 50:
                return (
                    "Schedule archive rotation and extend storage capacity.",
                    "Within 72 hours"
                )
            return (
                "Prioritize cleanup of stale artifacts and confirm backup integrity.",
                "Next maintenance window"
            )
        return (
            "Monitor utilization trend and verify quarterly health checkpoints.",
            "Routine cadence"
        )


# This class represents a GUI tab for analyzing metadata of selected files or folders, displaying
# real-time logs and extracted metadata.
class MetadataTab(QWidget):
    def __init__(self):
        super().__init__()
        self._thread: Optional[QThread] = None
        self._worker: Optional[MetadataWorker] = None
        self.setObjectName("MetadataTab")

        self._scroll_area = QScrollArea()
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setFrameShape(QFrame.NoFrame)
        self._scroll_area.setObjectName("metadataScrollArea")

        self._content_widget = QWidget()
        self._content_layout = QVBoxLayout()
        self._content_layout.setContentsMargins(24, 24, 24, 24)
        self._content_layout.setSpacing(10)
        self._content_widget.setLayout(self._content_layout)

        self._scroll_area.setWidget(self._content_widget)

        outer_layout = QVBoxLayout()
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.addWidget(self._scroll_area)
        self.setLayout(outer_layout)

        self._apply_theme()

        title_label = QLabel("Metadata Analyzer")
        title_label.setObjectName("sectionTitle")
        self._content_layout.addWidget(title_label)

        subtitle = QLabel("Inspect metadata signatures and monitor extraction activity in real time.")
        subtitle.setObjectName("sectionSubtitle")
        self._content_layout.addWidget(subtitle)

        # --- Selection Section ---
        selection_group = QGroupBox("Select File/Folder")
        selection_layout = QHBoxLayout()
        selection_layout.setContentsMargins(12, 12, 12, 12)
        selection_layout.setSpacing(10)
        self.selected_path_label = QLabel("No file or folder selected.")
        self.selected_path_label.setWordWrap(True)
        self.selected_path_label.setObjectName("selectedPathLabel")
        selection_layout.addWidget(self.selected_path_label, 1)

        self.select_path_button = QPushButton("Select Path")
        self.select_path_button.clicked.connect(self._select_path_for_analysis)
        self.select_path_button.setCursor(Qt.PointingHandCursor)
        self.select_path_button.setStyleSheet(PRIMARY_BUTTON_STYLE)
        selection_layout.addWidget(self.select_path_button)

        self.clear_outputs_button = QPushButton("Clear")
        self.clear_outputs_button.clicked.connect(self._reset_outputs)
        self.clear_outputs_button.setCursor(Qt.PointingHandCursor)
        self.clear_outputs_button.setStyleSheet(SECONDARY_BUTTON_STYLE)
        selection_layout.addWidget(self.clear_outputs_button)
        selection_group.setLayout(selection_layout)
        self._content_layout.addWidget(selection_group)

        # --- Metadata Display Section ---
        metadata_group = QGroupBox("Extracted Metadata")
        metadata_layout = QVBoxLayout()
        metadata_layout.setContentsMargins(14, 14, 14, 14)
        metadata_layout.setSpacing(10)
        self.metadata_display = QTextEdit()
        self.metadata_display.setReadOnly(True)
        self.metadata_display.setFontPointSize(10)
        self.metadata_display.setObjectName("metadataDisplay")
        self.metadata_display.setPlaceholderText("Select a file or folder to extract its metadata.")
        self.metadata_display.setFont(create_log_font(12))
        metadata_layout.addWidget(self.metadata_display)
        metadata_group.setLayout(metadata_layout)

        # --- Real-time Logs Section ---
        log_group = QGroupBox("Analysis Logs")
        log_layout = QVBoxLayout()
        log_layout.setContentsMargins(14, 14, 14, 14)
        log_layout.setSpacing(10)
        self.realtime_logs = QTextEdit()
        self.realtime_logs.setReadOnly(True)
        self.realtime_logs.setObjectName("metadataLogs")
        self.realtime_logs.setPlaceholderText("Analysis progress, warnings, and events will stream here.")
        self.realtime_logs.setFont(create_log_font(12))
        self.logger = Logger(self.realtime_logs) # Logger for this tab
        log_layout.addWidget(self.realtime_logs)
        log_group.setLayout(log_layout)

        self.content_splitter = QSplitter(Qt.Vertical)
        self.content_splitter.setObjectName("metadataSplitter")
        self.content_splitter.addWidget(metadata_group)
        self.content_splitter.addWidget(log_group)
        self.content_splitter.setSizes([320, 200])
        self._content_layout.addWidget(self.content_splitter, 1)

    def _select_path_for_analysis(self):
        path = QFileDialog.getExistingDirectory(self, "Select Folder for Metadata Analysis")
        if not path:
            path = QFileDialog.getOpenFileName(self, "Select File for Metadata Analysis")[0]
        
        if path:
            self.selected_path_label.setText(f"Selected: {path}")
            self.metadata_display.clear()
            self.realtime_logs.clear()
            self.logger.log(f"[i] Starting metadata analysis for: {path}")
            self._start_metadata_analysis(Path(path))
        else:
            self.selected_path_label.setText("No file or folder selected.")

    def _start_metadata_analysis(self, target_path: Path):
        if self._worker and self._thread and self._thread.isRunning():
            self.logger.log("[WARN] Metadata analysis already in progress. Please wait.")
            return

        self._thread = QThread()
        self._worker = MetadataWorker(target_path, self.logger)
        self._worker.moveToThread(self._thread)
        
        self._thread.started.connect(self._worker.run)
        self._worker.log_signal.connect(self.logger.log)
        self._worker.result_signal.connect(self._on_analysis_finished)
        self._worker.finished_signal.connect(self._thread.quit)
        self._worker.finished_signal.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)

        self._thread.start()

    def _on_analysis_finished(self, results: dict):
        self.logger.log("[i] Metadata analysis finished.")
        if results:
            formatted_output = ""
            for path, metadata in results.items():
                formatted_output += f"<b>Path:</b> {path}<br/>"
                for key, value in metadata.items():
                    formatted_output += f"&nbsp;&nbsp;&nbsp;&nbsp;<b>{key}:</b> {value}<br/>"
                formatted_output += "<br/>"
            self.metadata_display.setHtml(formatted_output)
        else:
            self.metadata_display.setText("No metadata extracted or target not found.")

    def _reset_outputs(self):
        self.selected_path_label.setText("No file or folder selected.")
        self.metadata_display.clear()
        self.metadata_display.setPlaceholderText("Select a file or folder to extract its metadata.")
        self.realtime_logs.clear()
        self.realtime_logs.setPlaceholderText("Analysis progress, warnings, and events will stream here.")
        if self.logger:
            self.logger.log("[i] Cleared metadata analysis outputs.")

    def _apply_theme(self):
        self.setStyleSheet(
            f"""
            QWidget#MetadataTab {{
                background-color: {APP_COLORS["background"]};
                color: {APP_COLORS["text_primary"]};
                font-family: {APP_FONT_FAMILY};
            }}
            QLabel#sectionTitle {{
                font-size: 24px;
                font-weight: 700;
            }}
            QLabel#sectionSubtitle {{
                font-size: 14px;
                color: {APP_COLORS["text_muted"]};
            }}
            QLabel#selectedPathLabel {{
                color: {APP_COLORS["text_muted"]};
                font-size: 12px;
            }}
            QGroupBox {{
                background-color: {APP_COLORS["panel"]};
                border-radius: 16px;
                border: 1px solid #1F2428;
                margin-top: 20px;
                padding: 20px 16px 16px 16px;
                font-size: 13px;
                font-weight: 600;
                text-transform: uppercase;
                letter-spacing: 0.8px;
                color: {APP_COLORS["text_muted"]};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 8px 12px;
                margin-top: -10px;
                background-color: transparent;
                color: {APP_COLORS["text_primary"]};
                font-weight: 700;
                font-size: 14px;
            }}
            QTextEdit#metadataDisplay {{
                background-color: {APP_COLORS["card"]};
                border-radius: 12px;
                border: 1px solid #1F2428;
                padding: 12px;
                color: {APP_COLORS["text_primary"]};
            }}
            QTextEdit#metadataLogs {{
                background-color: {APP_COLORS["card"]};
                border-radius: 12px;
                border: 1px solid #1F2428;
                padding: 12px;
                color: {APP_COLORS["text_primary"]};
            }}
            QSplitter#metadataSplitter::handle {{
                background-color: {APP_COLORS["background"]};
                height: 6px;
                margin: 6px 0;
            }}
            QSplitter#metadataSplitter::handle:pressed {{
                background-color: {APP_COLORS["signal_green"]};
            }}
            QScrollArea#metadataScrollArea {{
                border: none;
                background: transparent;
            }}
            QScrollArea#metadataScrollArea > QWidget {{
                background: transparent;
            }}
            """
        )


# The `CleaningTab` class in Python represents a GUI tab for managing device cleaning operations,
# including device detection, wipe operations, file/folder deletion, manifest verification, and
# real-time logging.
class DeviceRefreshWorker(QObject):
    finished = Signal(list, str)

    def __init__(self, system_info_collector: SystemInfoCollector, include_disk_images: bool):
        super().__init__()
        self.system_info_collector = system_info_collector
        self.include_disk_images = include_disk_images

    def run(self):
        try:
            disks = self.system_info_collector.get_physical_disks(include_disk_images=self.include_disk_images)
            self.finished.emit(disks, "")
        except Exception:
            error_msg = traceback.format_exc()
            self.finished.emit([], error_msg)


class CleaningTab(QWidget):
    def __init__(self, db_manager: 'LogDatabaseManager', passes_spin_val_func, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.passes_spin_val_func = passes_spin_val_func
        self.system_info_collector = SystemInfoCollector()
        self.selected_device_path = None

        self.setObjectName("CleaningTab")

        self._device_columns = ["Path", "Model", "Serial", "Type", "Size"]

        # Create the local logger for CleaningTab
        self.realtime_logs = QTextEdit()
        self.realtime_logs.setReadOnly(True)
        self.realtime_logs.setFont(create_log_font(12))
        self.realtime_logs.setObjectName("cleaningLogs")
        self.logger = Logger(self.realtime_logs) # This is the GUI logger for this tab

        # Initialize MCP Orchestrator here, using the CleaningTab's logger
        mcp_console_logger = ConsoleLogger()
        self.mcp_orchestrator = WipeOrchestratorMCP(self.db_manager, self.logger, mcp_console_logger, self.system_info_collector)
        self.logger.log(f"[MCP] Initialized WipeOrchestratorMCP. Current model: {self.mcp_orchestrator.model_version}")

        self._scroll_area = QScrollArea()
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setFrameShape(QFrame.NoFrame)
        self._scroll_area.setObjectName("cleaningScrollArea")

        self._content_widget = QWidget()
        self._content_layout = QVBoxLayout()
        self._content_layout.setContentsMargins(24, 24, 24, 24)
        self._content_layout.setSpacing(18)
        self._content_widget.setLayout(self._content_layout)

        self._scroll_area.setWidget(self._content_widget)

        outer_layout = QVBoxLayout()
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.addWidget(self._scroll_area)
        self.setLayout(outer_layout)

        self._apply_theme()

        title = QLabel("Secure Cleaning Orchestrator")
        title.setObjectName("sectionTitle")
        self._content_layout.addWidget(title)

        subtitle = QLabel("Manage device wipes, targeted purges, and compliance verification.")
        subtitle.setObjectName("sectionSubtitle")
        self._content_layout.addWidget(subtitle)

        # --- Metrics row ---
        metrics_layout = QHBoxLayout()
        metrics_layout.setSpacing(12)
        metrics_layout.setContentsMargins(0, 0, 0, 0)
        self.metric_cards = {}
        for key, label in [("devices", "Detected Devices"), ("passes", "Overwrite Passes"), ("last", "Last Action")]:
            card = QFrame()
            card.setObjectName("cleanMetricCard")
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(16, 14, 16, 14)
            card_layout.setSpacing(6)
            title_label = QLabel(label)
            title_label.setObjectName("cleanMetricTitle")
            value_label = QLabel("—")
            value_label.setObjectName("cleanMetricValue")
            card_layout.addWidget(title_label)
            card_layout.addWidget(value_label)
            card_layout.addStretch()
            metrics_layout.addWidget(card)
            self.metric_cards[key] = value_label
        metrics_layout.addStretch()
        self._content_layout.addLayout(metrics_layout)

        # --- Detected Devices Section ---
        self.devices_group = self._create_device_section()
        self._content_layout.addWidget(self.devices_group, 2)

        # --- Wipe Operation Section ---
        wipe_operation_group = QGroupBox("Wipe Operation")
        wipe_operation_group.setObjectName("cleanSectionGroup")
        wipe_operation_layout = QVBoxLayout()
        wipe_operation_layout.setContentsMargins(14, 12, 14, 16)
        wipe_operation_layout.setSpacing(12)

        self.selected_device_label = QLabel("Selected Device: None")
        self.selected_device_label.setObjectName("cleanSelectedDevice")
        wipe_operation_layout.addWidget(self.selected_device_label)

        self.selected_device_details_label = QLabel("Path: -, Model: -, Serial: -, Size: -")
        self.selected_device_details_label.setObjectName("cleanDeviceDetails")
        wipe_operation_layout.addWidget(self.selected_device_details_label)

        form_layout = QFormLayout()
        form_layout.setLabelAlignment(Qt.AlignLeft)
        form_layout.setFormAlignment(Qt.AlignTop)
        form_layout.setHorizontalSpacing(28)
        form_layout.setVerticalSpacing(10)
        confirm_label = QLabel("CONFIRM")
        confirm_label.setObjectName("cleanFormLabel")
        self.confirmation_input = QLineEdit()
        self.confirmation_input.setPlaceholderText("Type 'WIPE' or device serial")
        form_layout.addRow(confirm_label, self.confirmation_input)
        wipe_operation_layout.addLayout(form_layout)

        self.start_wipe_button = QPushButton("Start Wipe")
        self.start_wipe_button.setObjectName("primaryActionButton")
        self.start_wipe_button.setEnabled(False)
        self.start_wipe_button.clicked.connect(self._start_device_wipe)
        wipe_operation_layout.addWidget(self.start_wipe_button)

        wipe_operation_group.setLayout(wipe_operation_layout)
        self._content_layout.addWidget(wipe_operation_group)

        # --- Operations Row ---
        ops_row = QHBoxLayout()
        ops_row.setSpacing(12)
        ops_row.setContentsMargins(0, 0, 0, 0)

        # Overwrite passes card
        passes_card = QFrame()
        passes_card.setObjectName("cleanSectionCard")
        passes_layout = QVBoxLayout(passes_card)
        passes_layout.setContentsMargins(16, 16, 16, 16)
        passes_layout.setSpacing(12)
        passes_title = QLabel("Overwrite Passes")
        passes_title.setObjectName("cleanSubheading")
        passes_layout.addWidget(passes_title)

        passes_controls = QHBoxLayout()
        passes_controls.setSpacing(8)
        passes_label = QLabel("Passes")
        passes_label.setObjectName("cleanFormLabel")
        passes_controls.addWidget(passes_label)
        self.passes_spin = QSpinBox()
        self.passes_spin.setRange(1, 50)
        self.passes_spin.setValue(3)
        self.passes_spin.valueChanged.connect(self._on_passes_changed)
        passes_controls.addWidget(self.passes_spin)
        passes_controls.addStretch()
        passes_layout.addLayout(passes_controls)

        ops_row.addWidget(passes_card)

        # File operations card
        file_ops_card = QFrame()
        file_ops_card.setObjectName("cleanSectionCard")
        file_ops_layout = QVBoxLayout(file_ops_card)
        file_ops_layout.setContentsMargins(16, 16, 16, 16)
        file_ops_layout.setSpacing(10)
        file_ops_title = QLabel("File & Folder Actions")
        file_ops_title.setObjectName("cleanSubheading")
        file_ops_layout.addWidget(file_ops_title)

        btn_delete_file = QPushButton("Select File & Secure Delete")
        btn_delete_file.setStyleSheet(PRIMARY_BUTTON_STYLE)
        btn_delete_file.setCursor(Qt.PointingHandCursor)
        btn_delete_file.clicked.connect(self.select_and_delete_file)
        file_ops_layout.addWidget(btn_delete_file)

        btn_delete_dir = QPushButton("Select Folder & Secure Purge")
        btn_delete_dir.setStyleSheet(PRIMARY_BUTTON_STYLE)
        btn_delete_dir.setCursor(Qt.PointingHandCursor)
        btn_delete_dir.clicked.connect(self.select_and_delete_dir)
        file_ops_layout.addWidget(btn_delete_dir)

        btn_verify = QPushButton("Verify Manifest")
        btn_verify.setStyleSheet(SECONDARY_BUTTON_STYLE)
        btn_verify.setCursor(Qt.PointingHandCursor)
        btn_verify.clicked.connect(self.verify_manifest)
        file_ops_layout.addWidget(btn_verify)
        file_ops_layout.addStretch()

        ops_row.addWidget(file_ops_card, 1)

        self._content_layout.addLayout(ops_row)

        # Initialize metric defaults
        self.metric_cards["devices"].setText("0")
        self.metric_cards["passes"].setText(f"{self.passes_spin.value()}x")
        self.metric_cards["last"].setText("Monitoring")

        # --- Real-time Logs ---
        log_group = QGroupBox("Operational Telemetry")
        log_group.setObjectName("cleanSectionGroup")
        log_layout = QVBoxLayout()
        log_layout.setContentsMargins(16, 16, 16, 16)
        log_layout.setSpacing(10)
        self.realtime_logs.setPlaceholderText("Secure purge engine activity will be streamed here.")
        log_layout.addWidget(self.realtime_logs)
        log_group.setLayout(log_layout)
        self._content_layout.addWidget(log_group, 1)

        self._thread: Optional[QThread] = None
        self._worker: Optional[DeleteWorker] = None
        self._device_thread: Optional[QThread] = None
        self._device_worker: Optional[DeviceRefreshWorker] = None
        self._last_detected_devices: list[dict] = []
        self._refresh_button_default_text = self.refresh_button.text()

        self._refresh_devices() # Initial device scan

    def _create_device_section(self) -> QGroupBox:
        group = QGroupBox("Detected Devices")
        group.setObjectName("cleanSectionGroup")
        group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        layout = QVBoxLayout()
        layout.setContentsMargins(14, 12, 14, 16)
        layout.setSpacing(12)

        self.device_table = QTableWidget()
        self.device_table.setColumnCount(len(self._device_columns))
        self.device_table.setHorizontalHeaderLabels(self._device_columns)
        self.device_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.device_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.device_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.device_table.verticalHeader().setVisible(False)
        self.device_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.device_table.itemSelectionChanged.connect(self._device_selection_changed)
        self.device_table.setObjectName("deviceTable")
        self.device_table.setMinimumHeight(360)
        self.device_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(self.device_table, 1)

        button_row = QHBoxLayout()
        button_row.setContentsMargins(0, 0, 0, 0)
        button_row.setSpacing(8)
        button_row.addStretch()

        self.refresh_button = QPushButton("Refresh Devices")
        self.refresh_button.setStyleSheet(SECONDARY_BUTTON_STYLE)
        self.refresh_button.setCursor(Qt.PointingHandCursor)
        self.refresh_button.clicked.connect(self._refresh_devices)
        button_row.addWidget(self.refresh_button)
        button_row.addStretch()

        layout.addLayout(button_row)
        group.setLayout(layout)
        return group

    def _populate_device_table(self, disks: list[dict]):
        self.device_table.blockSignals(True)
        self.device_table.setUpdatesEnabled(False)
        self.device_table.clearSpans()

        target_rows = len(disks)

        if target_rows == 0:
            self.device_table.setRowCount(1)
            self.device_table.setColumnCount(len(self._device_columns))
            self.device_table.setHorizontalHeaderLabels(self._device_columns)
            placeholder = QTableWidgetItem("No storage devices detected")
            placeholder.setFlags(Qt.ItemIsEnabled)
            placeholder.setTextAlignment(Qt.AlignCenter)
            self.device_table.setItem(0, 0, placeholder)
            self.device_table.setSpan(0, 0, 1, len(self._device_columns))
            self.device_table.verticalScrollBar().setValue(0)
            self.device_table.setUpdatesEnabled(True)
            self.device_table.blockSignals(False)
            self._last_detected_devices = []
            return

        current_rows = self.device_table.rowCount()

        # Ensure table has enough rows
        while current_rows < target_rows:
            row_position = self.device_table.rowCount()
            self.device_table.insertRow(row_position)
            for col_idx in range(len(self._device_columns)):
                self.device_table.setItem(row_position, col_idx, QTableWidgetItem(""))
            current_rows += 1

        # Remove excess rows
        while current_rows > target_rows:
            current_rows -= 1
            self.device_table.removeRow(current_rows)

        # Update cell contents
        column_keys = ["Path", "Model", "Serial", "Type", "Size"]
        for row, disk in enumerate(disks):
            for col_idx, key in enumerate(column_keys):
                value = disk.get(key, "-")
                item = self.device_table.item(row, col_idx)
                if item is None:
                    item = QTableWidgetItem()
                    self.device_table.setItem(row, col_idx, item)
                item.setText(value)

        self.device_table.setUpdatesEnabled(True)
        self.device_table.blockSignals(False)
        self.device_table.resizeColumnsToContents()
        self.device_table.viewport().update()
        self.device_table.verticalScrollBar().setValue(0)
        self.device_table.clearSelection()

        self._last_detected_devices = disks

    def _refresh_devices(self):
        if self._device_thread and self._device_thread.isRunning():
            self.logger.log("[warn] Device refresh already in progress. Please wait...")
            return

        self.logger.log("[i] Detecting devices asynchronously...")
        if self._last_detected_devices:
            self.metric_cards["devices"].setText(f"{len(self._last_detected_devices)} (refreshing)")
        else:
            self.metric_cards["devices"].setText("Scanning...")

        self.refresh_button.setEnabled(False)
        self.refresh_button.setText("Refreshing…")

        self._device_thread = QThread()
        self._device_worker = DeviceRefreshWorker(self.system_info_collector, include_disk_images=False)
        self._device_worker.moveToThread(self._device_thread)

        self._device_thread.started.connect(self._device_worker.run)
        self._device_worker.finished.connect(self._on_device_refresh_finished, Qt.QueuedConnection)
        self._device_worker.finished.connect(self._device_thread.quit)
        self._device_worker.finished.connect(self._device_worker.deleteLater)
        self._device_thread.finished.connect(self._clear_device_thread)

        self._device_thread.start()

    def _clear_device_thread(self):
        if self._device_thread:
            self._device_thread.deleteLater()
        self._device_thread = None
        self._device_worker = None

    def _on_device_refresh_finished(self, disks: list, error_msg: str):
        self.refresh_button.setEnabled(True)
        self.refresh_button.setText(self._refresh_button_default_text)

        if error_msg:
            self.logger.log(f"[ERR] Device detection failed: {error_msg}")
            QMessageBox.critical(self, "Device Detection Failed", "Unable to detect devices. Check logs for details.")
            if self._last_detected_devices:
                self.metric_cards["devices"].setText(str(len(self._last_detected_devices)))
                self._populate_device_table(self._last_detected_devices)
            else:
                self.metric_cards["devices"].setText("Error")
            return

        self._populate_device_table(disks)
        self.logger.log(f"[i] Detected {len(disks)} devices.")
        self.metric_cards["devices"].setText(str(len(disks)))

    def _device_selection_changed(self):
        selected_items = self.device_table.selectedItems()
        if selected_items:
            row = selected_items[0].row()
            path = self.device_table.item(row, 0).text()
            model = self.device_table.item(row, 1).text()
            serial = self.device_table.item(row, 2).text()
            disk_type = self.device_table.item(row, 3).text()
            size = self.device_table.item(row, 4).text()

            self.selected_device_path = path
            self.selected_device_label.setText(f"Selected Device: {path}")
            self.selected_device_details_label.setText(f"Path: {path}, Model: {model}, Serial: {serial}, Type: {disk_type}, Size: {size}")
            self.start_wipe_button.setEnabled(False) # Re-disable until confirmation
            self.confirmation_input.setText("") # Clear confirmation input
            # Disconnect previous connection before connecting to avoid multiple connections
            try:
                self.confirmation_input.textChanged.disconnect(self._check_wipe_confirmation)
            except TypeError: # Handle case where it's not connected yet
                pass
            self.confirmation_input.textChanged.connect(self._check_wipe_confirmation) # Connect for live check
        else:
            self.selected_device_path = None
            self.selected_device_label.setText("Selected Device: None")
            self.selected_device_details_label.setText("Path: -, Model: -, Serial: -, Size: -")
            self.start_wipe_button.setEnabled(False)
            try:
                self.confirmation_input.textChanged.disconnect(self._check_wipe_confirmation) # Disconnect if no device
            except TypeError:
                pass

    def _check_wipe_confirmation(self, text):
        if self.selected_device_path and (text == "WIPE" or text == self.device_table.item(self.device_table.currentRow(), 2).text()): # Check against serial
            self.start_wipe_button.setEnabled(True)
        else:
            self.start_wipe_button.setEnabled(False)

    def _start_device_wipe(self, is_system_wipe=False):
        if not self.selected_device_path:
            self.logger.log("[ERR] No device selected for wiping.")
            QMessageBox.warning(self, "Error", "No device selected for wiping.")
            return
        
        # Additional check for full system wipe - include all detected disks including disk images
        if is_system_wipe:
            self.logger.log("[i] Full system wipe requested - checking for additional disk images...")
            all_disks = self.system_info_collector.get_physical_disks(include_disk_images=True)
            system_disks = [disk for disk in all_disks if disk["Path"] != self.selected_device_path]
            
            if system_disks:
                disk_list = "\n".join([f"- {disk['Path']} ({disk['Model']}, {disk['Size']})" for disk in system_disks])
                msg = f"The following additional storage devices were detected and will also be wiped:\n\n{disk_list}"
                QMessageBox.information(self, "Additional Devices", msg)

        # Add a more serious confirmation dialog for full device wipe
        warning_msg = "WARNING: You are about to securely wipe the entire device:"
        if is_system_wipe:
            warning_msg = "WARNING: You are about to perform a FULL SYSTEM WIPE including all detected storage devices:"
            
        resp = QMessageBox.question(
            self, "CRITICAL CONFIRMATION",
            f"<span style=\"color:red; font-weight:bold;\">{warning_msg}</span>\n<br/><br/><b>{self.selected_device_path}</b><br/><br/>This action is IRREVERSIBLE and will PERMANENTLY ERASE ALL DATA. Are you absolutely sure you want to proceed?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if resp != QMessageBox.Yes:
            self.logger.log("[i] Device wipe cancelled by user.")
            self._set_last_action("Wipe cancelled")
            return

        self.logger.log(f"[+] Starting {'full system' if is_system_wipe else 'device'} wipe for: {self.selected_device_path}")
        self._set_last_action("Wipe initiated")
        
        mcp_console_logger = ConsoleLogger() # Need a console logger for the worker
        self._thread = QThread()
        wipe_job_id = str(uuid.uuid4())  # Generate a new wipe_job_id for physical wipe
        
        # Create workers for all devices if this is a system wipe
        if is_system_wipe:
            all_disks = self.system_info_collector.get_physical_disks(include_disk_images=True)
            # Create worker for each disk
            self._workers = []
            for disk in all_disks:
                worker = PhysicalDeviceWipeWorker(
                    disk["Path"],
                    self.passes_spin_val_func(),
                    wipe_job_id,
                    mcp_console_logger,
                    is_system_wipe=True
                )
                self._workers.append(worker)
            # Set the main worker as the first one
            self._worker = self._workers[0]
        else:
            # Just create a single worker for the selected device
            self._worker = PhysicalDeviceWipeWorker(
                self.selected_device_path,
                self.passes_spin_val_func(),
                wipe_job_id,
                mcp_console_logger,
                is_system_wipe=False
            )
        # Move all workers to thread and set up connections
        if is_system_wipe:
            for worker in self._workers:
                worker.moveToThread(self._thread)
                worker.log.connect(self.logger.log)  # Connect each worker's log
                worker.finished.connect(lambda s, m, wid, w=worker: self._on_physical_wipe_progress(s, m, wid, w))
            
            # Last worker's completion will trigger thread cleanup
            self._workers[-1].finished.connect(self._thread.quit)
            self._workers[-1].finished.connect(lambda: [w.deleteLater() for w in self._workers])
            
            # Connect thread start to first worker
            self._thread.started.connect(self._workers[0].run)
            
            # Chain workers together
            for i in range(len(self._workers)-1):
                self._workers[i].finished.connect(self._workers[i+1].run)
        else:
            self._worker.moveToThread(self._thread)
            self._thread.started.connect(self._worker.run)
            self._worker.log.connect(self.logger.log)
            self._worker.finished.connect(self._on_physical_wipe_finished)
            self._worker.finished.connect(self._thread.quit)
            self._worker.finished.connect(self._worker.deleteLater)

        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.start()
        
        # Log appropriate message
        if is_system_wipe:
            self.logger.log("[+] Started full system wipe with multiple workers")
            for worker in self._workers:
                self.logger.log(f"[+] - Worker added for: {worker.device_path}")
        else:
            self.logger.log(f"[+] Started physical device wipe worker for {self.selected_device_path}")
        # QMessageBox.information(self, "Wipe Initiated", f"Simulating wipe for {self.selected_device_path}. Real wiping logic needs to be implemented.")
        # self.logger.log(f"[✓] Simulated full device wipe for {self.selected_device_path}. (Actual wiping logic not yet implemented)")
        # self.db_manager.update_wipe_job_status(str(uuid.uuid4()), "SIMULATED_DEVICE_WIPE", actual_result="SUCCESS", verification_artifact="N/A") # Log simulation

    def _on_physical_wipe_progress(self, success: bool, message: str, wipe_job_id: str, worker):
        """Handle completion of individual workers during system wipe"""
        self.logger.log(f"[PhysicalDeviceWipeWorker-GUI] Worker finished for {worker.device_path}: {message}")
        if not success:
            self.logger.log(f"[ERR] Failed to wipe {worker.device_path}: {message}")
            # Continue with remaining wipes but log the error
            
        if worker == self._workers[-1]:  # Last worker completed
            all_success = all(hasattr(w, 'last_result') and w.last_result[0] for w in self._workers)
            final_message = "System wipe completed. "
            if all_success:
                final_message += "All devices were successfully wiped."
            else:
                final_message += "Some devices failed to wipe completely. Check the logs for details."
            self._on_physical_wipe_finished(all_success, final_message, wipe_job_id)

    def _on_physical_wipe_finished(self, success: bool, message: str, wipe_job_id: str):
        self.logger.log(f"[PhysicalDeviceWipeWorker-GUI] Worker finished: {message}")
        if success:
            QMessageBox.information(self, "Physical Wipe Complete", f"{message}\n\nWipe ID: {wipe_job_id}\n\nGo to the \"Verify\" section of the VAULT website and paste this WIPE ID there to get your certificate.")
            # Here, you would trigger MCP verification for the physical wipe if applicable
            # For now, we'll just log success and update DB manually
            self.db_manager.update_wipe_job_status(
                wipe_job_id, # Use the wipe_job_id from the worker
                "COMPLETED_PHYSICAL_WIPE",
                actual_result="SUCCESS",
                verification_artifact="N/A" # Actual physical verification is complex, keep as N/A for now
            )
            # Generate certificate for physical wipe
            self.mcp_orchestrator._generate_and_store_certificates(wipe_job_id)
        else:
            QMessageBox.critical(self, "Physical Wipe Failed", f"{message}\n\nWipe ID: {wipe_job_id}") # Added wipe_job_id
            self.db_manager.update_wipe_job_status(
                wipe_job_id,
                "FAILED_PHYSICAL_WIPE",
                actual_result="FAILURE",
                verification_artifact="N/A"
            )
        self._set_last_action("Wipe completed" if success else "Wipe failed")
        # Re-enable the wipe button after completion
        self.start_wipe_button.setEnabled(True)
        self.confirmation_input.setText("") # Clear confirmation input
        self._refresh_devices() # Refresh device list to show post-wipe state (e.g. unmounted)

    def select_and_delete_file(self):
        fname, _ = QFileDialog.getOpenFileName(self, "Select file to securely delete")
        if not fname:
            return
        self._set_last_action("File purge scheduled")
        self._start_worker_for_target(fname)

    def select_and_delete_dir(self):
        dname = QFileDialog.getExistingDirectory(self, "Select folder to securely purge")
        if not dname:
            return
        self._set_last_action("Folder purge scheduled")
        self._start_worker_for_target(dname)

    def _start_worker_for_target(self, target_path: str):
        passes = self.passes_spin_val_func() # Get value from main GUI through the function
        resp = QMessageBox.question(
            self, "Confirm Deletion",
            f"Are you sure you want to securely delete:\n{target_path}\n\nThis will compute SHA-256(s), append to manifest database ({self.db_manager.db_path}), overwrite {passes} passes and permanently remove the file(s).",
            QMessageBox.Yes | QMessageBox.No
        )
        if resp != QMessageBox.Yes:
            return

        # DeleteWorker will now connect directly to self.logger (CleaningTab's logger)

        assessment_result = self.mcp_orchestrator.assess_asset(Path(target_path), passes)
        predicted_label = assessment_result["result"]["predicted_label"]
        wipe_job_id = assessment_result["result"]["wipe_job_id"]

        if predicted_label == "MANUAL_REVIEW":
            QMessageBox.warning(self, "Manual Review Needed", f'The AI model recommends manual review for {target_path}:\n\n{assessment_result["result"]["explain"]}')
            self.logger.log(f"[MCP] Operation halted for {target_path} due to manual review recommendation.")
            return

        if assessment_result["result"]["method"] == "physical_destroy":
            self.logger.log(f"[MCP] Requesting multi-party approval for physical_destroy on {target_path}.")
            QMessageBox.information(self, "Approval Needed", f"Multi-party approval required for physical_destroy on {target_path}. Please get approval before proceeding.")
            return

        if not self.mcp_orchestrator.start_wipe(wipe_job_id):
            self.logger.log(f"[MCP-ERR] Failed to start wipe job {wipe_job_id}.")
            QMessageBox.critical(self, "Error", f"Failed to initiate wipe job {wipe_job_id} through MCP.")
            return

        self._thread = QThread()
        self._worker = DeleteWorker(Path(target_path), passes, self.db_manager, wipe_job_id)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.log.connect(self.logger.log) # Connect worker's log signal directly to CleaningTab's logger
        self._worker.finished.connect(
            lambda success, message: self._on_worker_finished_mcp(wipe_job_id, success, message, assessment_result["mcp_logs"]),
            Qt.QueuedConnection
        )
        self._worker.finished.connect(lambda *_: self._thread.quit())
        self._worker.finished.connect(lambda success, message: self._on_worker_finished(success, message, wipe_job_id)) # Connect worker's finished to _on_worker_finished with wipe_job_id
        self._worker.finished.connect(lambda *_: self._worker.deleteLater())
        self._thread.finished.connect(self._thread.deleteLater)

        self._thread.start()
        self._set_last_action("Secure delete running")
        self.logger.log(f"[i] Started secure delete worker for {target_path}")
    
    def _on_worker_finished_mcp(self, wipe_job_id: str, success: bool, message: str, mcp_buffered_logs: list):
        actual_result = "SUCCESS" if success else "FAILURE"
        verification_artifact = f"SimulatedVerificationArtifact_{uuid.uuid4()}"
        is_signed = True
        self.mcp_orchestrator.verify_wipe(wipe_job_id, verification_artifact, is_signed, actual_result)
        # The call to _on_worker_finished is moved to the direct connection above.
        # self._on_worker_finished(success, message)

    def _on_worker_finished(self, success: bool, message: str, wipe_job_id: str): # Added wipe_job_id
        if success:
            QMessageBox.information(self, "Done", f"{message}\n\nWipe ID: {wipe_job_id}\n\nGo to the \"Verify\" section of the VAULT website and paste this WIPE ID there to get your certificate.")
        else:
            QMessageBox.warning(self, "Failed", f"{message}\n\nWipe ID: {wipe_job_id}") # Added wipe_job_id
        self.logger.log(f"[i] Worker finished: {message}")
        self._set_last_action("Secure delete done" if success else "Secure delete failed")

    def verify_manifest(self):
        results = verify_manifest_deletions(self.db_manager, self.logger)
        missing = [r for r in results if r[1] == "MISSING"]
        present = [r for r in results if r[1].startswith("PRESENT")]
        if not results:
            QMessageBox.information(self, "Verification", "Manifest empty or unreadable (see logs).")
            self.logger.log("[i] Manifest empty or unreadable.") # Log to CleaningTab's logger
            return
        summary = f"Total entries checked: {len(results)}\nMissing (expected deleted): {len(missing)}\nPresent (unexpected): {len(present)}"
        QMessageBox.information(self, "Verification Summary", summary)
        self.logger.log(summary) # Log to CleaningTab's logger
        self._set_last_action("Manifest verified")

    def _on_passes_changed(self, value: int):
        self.passes_spin_val_func(value)
        self.metric_cards["passes"].setText(f"{value}x")

    def _set_last_action(self, text: str):
        self.metric_cards["last"].setText(text)

    def _apply_theme(self):
        self.setStyleSheet(
            f"""
            QWidget#CleaningTab {{
                background-color: {APP_COLORS['background']};
                color: {APP_COLORS['text_primary']};
                font-family: {APP_FONT_FAMILY};
            }}
            QLabel.sectionTitle {{}}
            QLabel#sectionTitle {{
                font-size: 24px;
                font-weight: 700;
            }}
            QLabel#sectionSubtitle {{
                font-size: 14px;
                color: {APP_COLORS['text_muted']};
            }}
            QFrame#cleanMetricCard {{
                background-color: {APP_COLORS['panel']};
                border-radius: 18px;
                border: 1px solid #1F2428;
                min-width: 190px;
            }}
            QLabel#cleanMetricTitle {{
                font-size: 11px;
                text-transform: uppercase;
                letter-spacing: 1px;
                color: {APP_COLORS['text_muted']};
                font-weight: 600;
            }}
            QLabel#cleanMetricValue {{
                font-size: 20px;
                font-weight: 700;
            }}
            QGroupBox#cleanSectionGroup {{
                background-color: {APP_COLORS['panel']};
                border-radius: 20px;
                border: 1px solid #1F2428;
                margin-top: 20px;
                padding: 20px 16px 16px 16px;
                font-size: 13px;
                font-weight: 600;
                text-transform: uppercase;
                color: {APP_COLORS['text_muted']};
            }}
            QGroupBox#cleanSectionGroup::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 8px 12px;
                margin-top: -10px;
                background-color: transparent;
                color: {APP_COLORS['text_primary']};
                font-weight: 700;
                font-size: 14px;
            }}
            QLabel#cleanSelectedDevice {{
                font-size: 14px;
                font-weight: 600;
            }}
            QLabel#cleanDeviceDetails {{
                font-size: 12px;
                color: {APP_COLORS['text_muted']};
            }}
            QLabel#cleanFormLabel {{
                font-size: 11px;
                font-weight: 600;
                color: {APP_COLORS['text_muted']};
                letter-spacing: 1px;
            }}
            QLineEdit {{
                padding: 10px 12px;
                border-radius: 12px;
                border: 1px solid #23282E;
                background-color: {APP_COLORS['card']};
                color: {APP_COLORS['text_primary']};
            }}
            QLineEdit:focus {{
                border-color: {APP_COLORS['signal_green']};
            }}
            QPushButton#primaryActionButton {{
                background-color: {APP_COLORS['signal_green']};
                border: none;
                border-radius: 12px;
                padding: 12px 20px;
                font-weight: 600;
                color: #0E1116;
            }}
            QPushButton#primaryActionButton:hover {{
                background-color: #5EC85F;
            }}
            QPushButton#primaryActionButton:disabled {{
                background-color: #2C332F;
                color: {APP_COLORS['text_muted']};
            }}
            QFrame#cleanSectionCard {{
                background-color: {APP_COLORS['panel']};
                border-radius: 18px;
                border: 1px solid #2A2D32;
                padding: 4px;
            }}
            QLabel#cleanSubheading {{
                font-size: 14px;
                font-weight: 700;
                color: {APP_COLORS['text_primary']};
                text-transform: uppercase;
                letter-spacing: 1px;
                margin-bottom: 8px;
            }}
            QLabel#cleanFormLabel {{
                font-size: 12px;
                font-weight: 600;
                color: {APP_COLORS['text_muted']};
            }}
            QSpinBox {{
                background-color: {APP_COLORS['card']};
                border: 1px solid #2A2D32;
                border-radius: 8px;
                padding: 8px 12px;
                color: {APP_COLORS['text_primary']};
                font-size: 14px;
                font-weight: 600;
                min-width: 80px;
            }}
            QSpinBox::up-button, QSpinBox::down-button {{
                background-color: {APP_COLORS['background']};
                border: 1px solid #2A2D32;
                border-radius: 4px;
                width: 20px;
            }}
            QSpinBox::up-button:hover, QSpinBox::down-button:hover {{
                background-color: {APP_COLORS['signal_green']};
            }}
            QTextEdit#cleaningLogs {{
                background-color: {APP_COLORS['card']};
                border-radius: 12px;
                border: 1px solid #1F2428;
                padding: 12px;
                color: {APP_COLORS['text_primary']};
            }}
            QTableWidget#deviceTable {{
                background-color: {APP_COLORS['card']};
                border-radius: 12px;
                border: 1px solid #1F2428;
                gridline-color: #1F2428;
                selection-background-color: rgba(76, 175, 80, 0.25);
                selection-color: {APP_COLORS['text_primary']};
            }}
            QHeaderView::section {{
                background-color: {APP_COLORS['panel']};
                border: none;
                padding: 10px;
                color: {APP_COLORS['text_muted']};
                font-weight: 600;
            }}
            QScrollArea#cleaningScrollArea {{
                border: none;
                background: transparent;
            }}
            QScrollArea#cleaningScrollArea > QWidget {{
                background: transparent;
            }}
            """
        )


# The `InfoTab` class in Python sets up a user interface to display system information using Qt
# widgets and a `SystemInfoCollector` object.
class InfoTab(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("InfoTab")
        self.system_info_collector = SystemInfoCollector()
        self._setup_ui()
        self._apply_theme()
        self._load_data()

    def _setup_ui(self):
        self._scroll_area = QScrollArea()
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setFrameShape(QFrame.NoFrame)
        self._scroll_area.setObjectName("infoScrollArea")

        self._content_widget = QWidget()
        self._content_layout = QVBoxLayout()
        self._content_layout.setContentsMargins(24, 24, 24, 24)
        self._content_layout.setSpacing(16)
        self._content_widget.setLayout(self._content_layout)

        self._scroll_area.setWidget(self._content_widget)

        outer_layout = QVBoxLayout()
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.addWidget(self._scroll_area)
        self.setLayout(outer_layout)

        title = QLabel("System Intelligence Snapshot")
        title.setObjectName("sectionTitle")
        self._content_layout.addWidget(title)

        subtitle = QLabel("Key device metrics refreshed on demand.")
        subtitle.setObjectName("sectionSubtitle")
        self._content_layout.addWidget(subtitle)

        # System Overview Section
        self.system_overview_group = QGroupBox("System Overview")
        self.system_overview_group.setObjectName("infoSectionGroup")
        system_layout = QFormLayout()
        system_layout.setLabelAlignment(Qt.AlignLeft)
        system_layout.setFormAlignment(Qt.AlignLeft | Qt.AlignTop)
        system_layout.setHorizontalSpacing(40)
        system_layout.setVerticalSpacing(12)
        self.system_overview_group.setLayout(system_layout)
        self._content_layout.addWidget(self.system_overview_group)

        # Hardware Diagnostics Section
        self.hardware_group = QGroupBox("Hardware Diagnostics")
        self.hardware_group.setObjectName("infoSectionGroup")
        hardware_layout = QFormLayout()
        hardware_layout.setLabelAlignment(Qt.AlignLeft)
        hardware_layout.setFormAlignment(Qt.AlignLeft | Qt.AlignTop)
        hardware_layout.setHorizontalSpacing(40)
        hardware_layout.setVerticalSpacing(12)
        self.hardware_group.setLayout(hardware_layout)
        self._content_layout.addWidget(self.hardware_group)

        # Storage Overview Section
        self.storage_group = QGroupBox("Storage Overview")
        self.storage_group.setObjectName("infoSectionGroup")
        storage_layout = QFormLayout()
        storage_layout.setLabelAlignment(Qt.AlignLeft)
        storage_layout.setFormAlignment(Qt.AlignLeft | Qt.AlignTop)
        storage_layout.setHorizontalSpacing(40)
        storage_layout.setVerticalSpacing(12)
        self.storage_group.setLayout(storage_layout)
        self._content_layout.addWidget(self.storage_group)

        # Performance Metrics Section
        self.performance_group = QGroupBox("Performance Metrics")
        self.performance_group.setObjectName("infoSectionGroup")
        performance_layout = QFormLayout()
        performance_layout.setLabelAlignment(Qt.AlignLeft)
        performance_layout.setFormAlignment(Qt.AlignLeft | Qt.AlignTop)
        performance_layout.setHorizontalSpacing(40)
        performance_layout.setVerticalSpacing(12)
        self.performance_group.setLayout(performance_layout)
        self._content_layout.addWidget(self.performance_group)

        # Network Information Section
        self.network_group = QGroupBox("Network Information")
        self.network_group.setObjectName("infoSectionGroup")
        network_layout = QFormLayout()
        network_layout.setLabelAlignment(Qt.AlignLeft)
        network_layout.setFormAlignment(Qt.AlignLeft | Qt.AlignTop)
        network_layout.setHorizontalSpacing(40)
        network_layout.setVerticalSpacing(12)
        self.network_group.setLayout(network_layout)
        self._content_layout.addWidget(self.network_group)

        # Security Status Section
        self.security_group = QGroupBox("Security Status")
        self.security_group.setObjectName("infoSectionGroup")
        security_layout = QFormLayout()
        security_layout.setLabelAlignment(Qt.AlignLeft)
        security_layout.setFormAlignment(Qt.AlignLeft | Qt.AlignTop)
        security_layout.setHorizontalSpacing(40)
        security_layout.setVerticalSpacing(12)
        self.security_group.setLayout(security_layout)
        self._content_layout.addWidget(self.security_group)

        # Last updated label
        self.last_updated_label = QLabel("")
        self.last_updated_label.setObjectName("lastUpdatedLabel")
        self._content_layout.addWidget(self.last_updated_label)

        controls_layout = QHBoxLayout()
        controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_layout.setSpacing(10)
        self.refresh_button = QPushButton("Refresh Snapshot")
        self.refresh_button.setCursor(Qt.PointingHandCursor)
        self.refresh_button.setStyleSheet(PRIMARY_BUTTON_STYLE)
        self.refresh_button.clicked.connect(self._load_data)
        controls_layout.addWidget(self.refresh_button)
        controls_layout.addStretch()
        self._content_layout.addLayout(controls_layout)

        self._content_layout.addStretch()

    def _load_data(self):
        # Clear existing sections
        self._clear_form_layout(self.system_overview_group.layout())
        self._clear_form_layout(self.hardware_group.layout())
        self._clear_form_layout(self.storage_group.layout())
        self._clear_form_layout(self.performance_group.layout())
        self._clear_form_layout(self.network_group.layout())
        self._clear_form_layout(self.security_group.layout())

        # Get system information
        os_info = self.system_info_collector.get_os_info()
        cpu_info = self.system_info_collector.get_cpu_info()
        mem_info = self.system_info_collector.get_memory_info()
        disk_info = self.system_info_collector.get_disk_info()
        battery_info = self.system_info_collector.get_battery_info()

        # System Overview Section
        system_layout = self.system_overview_group.layout()
        os_str = f"{os_info.get('System', 'Unknown')} {os_info.get('Release', '')}"
        system_layout.addRow(self._bold("OS:"), self._value_label(os_str))
        
        cpu_brand = cpu_info.get('Brand', cpu_info.get('Processor', 'Unknown'))
        system_layout.addRow(self._bold("CPU:"), self._value_label(cpu_brand))
        
        ram_usage = f"{mem_info.get('Used', '0')} / {mem_info.get('Total', '0')} ({mem_info.get('Percentage', '0%')})"
        system_layout.addRow(self._bold("RAM Usage:"), self._value_label(ram_usage))

        # Hardware Diagnostics Section
        hardware_layout = self.hardware_group.layout()
        cpu_details = f"{os_info.get('Machine', 'Unknown')} / {os_info.get('Processor', 'Unknown')}"
        hardware_layout.addRow(self._bold("CPU:"), self._value_label(cpu_details))
        
        cores = cpu_info.get('Total Cores', 'Unknown')
        hardware_layout.addRow(self._bold("Cores:"), self._value_label(str(cores)))
        
        memory_total = mem_info.get('Total', 'Unknown')
        hardware_layout.addRow(self._bold("Memory:"), self._value_label(memory_total))

        # Storage Overview Section
        storage_layout = self.storage_group.layout()
        if disk_info:
            for i, disk in enumerate(disk_info[:3]):  # Show first 3 disks
                device_name = disk.get('Device', f'Drive {i+1}').replace('/dev/', '')
                free_space = disk.get('Free', 'Unknown')
                storage_layout.addRow(self._bold(f"Device {i+1}:"), self._value_label(f"{device_name} - {free_space} free"))
        else:
            storage_layout.addRow(self._bold("Storage:"), self._value_label("No devices detected"))

        # Performance Metrics Section
        performance_layout = self.performance_group.layout()
        cpu_usage = cpu_info.get('Total Usage', 'Unknown')
        performance_layout.addRow(self._bold("CPU Usage:"), self._value_label(cpu_usage))

        # Network Information Section (simplified - would need additional system calls for real data)
        network_layout = self.network_group.layout()
        try:
            import psutil
            net_io = psutil.net_io_counters()
            data_sent = self._format_bytes(net_io.bytes_sent)
            data_recv = self._format_bytes(net_io.bytes_recv)
            network_layout.addRow(self._bold("Data Sent:"), self._value_label(data_sent))
            network_layout.addRow(self._bold("Data Received:"), self._value_label(data_recv))
        except:
            network_layout.addRow(self._bold("Data Sent:"), self._value_label("Unavailable"))
            network_layout.addRow(self._bold("Data Received:"), self._value_label("Unavailable"))

        # Security Status Section (simplified)
        security_layout = self.security_group.layout()
        firewall_status = self._detect_firewall_status()

        security_layout.addRow(self._bold("Firewall:"), self._value_label(firewall_status))
        security_layout.addRow(self._bold("Updates:"), self._value_label("Check System Preferences"))

        # Update timestamp
        if hasattr(self, "last_updated_label"):
            self.last_updated_label.setText(
                f"Last refreshed: {QDateTime.currentDateTime().toString('MMM d, yyyy hh:mm ap')}"
            )

    def _clear_form_layout(self, layout):
        """Clear all rows from a QFormLayout"""
        while layout.rowCount() > 0:
            layout.removeRow(0)

    def _format_bytes(self, bytes_val):
        """Format bytes to human readable string"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes_val < 1024.0:
                return f"{bytes_val:.1f} {unit}"
            bytes_val /= 1024.0
        return f"{bytes_val:.1f} PB"

    def _bold(self, text):
        l = QLabel(text)
        l.setStyleSheet(
            f"font-weight: 600; font-size: 13px; color: {APP_COLORS['text_muted']}; text-transform: uppercase; letter-spacing: 1px;"
        )
        return l
    
    def _value_label(self, text):
        l = QLabel(text)
        l.setStyleSheet(
            f"font-size: 16px; font-weight: 600; color: {APP_COLORS['text_primary']};"
        )
        return l

    def _detect_firewall_status(self) -> str:
        system = platform.system()

        detector_chain = []

        if system == "Darwin":
            detector_chain.extend([
                (["/usr/libexec/ApplicationFirewall/socketfilterfw", "--getglobalstate"], self._parse_macos_socketfilterfw),
                (["/usr/bin/defaults", "read", "/Library/Preferences/com.apple.alf", "globalstate"], self._parse_macos_defaults)
            ])
        elif system == "Windows":
            detector_chain.extend([
                (["powershell", "-NoProfile", "-Command", "(Get-NetFirewallProfile | Where-Object {$_.Enabled -eq 1}).Enabled"], self._parse_windows_powershell_firewall),
                (["netsh", "advfirewall", "show", "allprofiles"], self._parse_windows_netsh_firewall)
            ])
        else:  # Linux / Other Unix
            detector_chain.extend([
                (["/usr/sbin/ufw", "status"], self._parse_linux_ufw),
                (["/usr/bin/firewall-cmd", "--state"], self._parse_linux_firewalld)
            ])

        for command, parser in detector_chain:
            try:
                result = subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                    timeout=5,
                    check=False
                )
                parsed = parser(result)
                if parsed:
                    return parsed
            except FileNotFoundError:
                continue
            except Exception:
                continue

        return "Unknown"

    @staticmethod
    def _parse_macos_socketfilterfw(result: subprocess.CompletedProcess) -> Optional[str]:
        if result.returncode != 0:
            return None
        output = result.stdout.lower()
        if "enabled" in output:
            return "Active"
        if "disabled" in output:
            return "Inactive"
        return None

    @staticmethod
    def _parse_macos_defaults(result: subprocess.CompletedProcess) -> Optional[str]:
        if result.returncode != 0:
            return None
        value = result.stdout.strip()
        mapping = {
            "0": "Inactive",
            "1": "Active",
            "2": "Block all"
        }
        return mapping.get(value)

    @staticmethod
    def _parse_windows_powershell_firewall(result: subprocess.CompletedProcess) -> Optional[str]:
        if result.returncode != 0:
            return None
        output = result.stdout.strip()
        if not output:
            return None
        return "Active" if any(token.lower() == "true" or token == "1" for token in output.split()) else "Inactive"

    @staticmethod
    def _parse_windows_netsh_firewall(result: subprocess.CompletedProcess) -> Optional[str]:
        if result.returncode != 0:
            return None
        output = result.stdout.lower()
        if "state" not in output:
            return None
        return "Active" if "state on" in output or "enabled" in output else "Inactive"

    @staticmethod
    def _parse_linux_ufw(result: subprocess.CompletedProcess) -> Optional[str]:
        if result.returncode != 0:
            return None
        output = result.stdout.lower()
        if "inactive" in output:
            return "Inactive"
        if "active" in output:
            return "Active"
        return None

    @staticmethod
    def _parse_linux_firewalld(result: subprocess.CompletedProcess) -> Optional[str]:
        if result.returncode != 0:
            return None
        output = result.stdout.strip().lower()
        if output == "running":
            return "Active"
        if output == "not running":
            return "Inactive"
        return None

    def _apply_theme(self):
        self.setStyleSheet(
            f"""
            QWidget#InfoTab {{
                background-color: {APP_COLORS["background"]};
                color: {APP_COLORS["text_primary"]};
                font-family: {APP_FONT_FAMILY};
            }}
            QLabel#sectionTitle {{
                font-size: 24px;
                font-weight: 700;
            }}
            QLabel#sectionSubtitle {{
                font-size: 14px;
                color: {APP_COLORS["text_muted"]};
            }}
            QLabel#lastUpdatedLabel {{
                font-size: 12px;
                color: {APP_COLORS["text_muted"]};
            }}
            QGroupBox#infoSectionGroup {{
                background-color: {APP_COLORS["panel"]};
                border-radius: 16px;
                border: 1px solid #1F2428;
                margin-top: 8px;
                padding-top: 32px;
                font-size: 13px;
                font-weight: 600;
                text-transform: uppercase;
                letter-spacing: 0.8px;
                color: {APP_COLORS["text_muted"]};
            }}
            QGroupBox#infoSectionGroup::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 8px 16px;
                background-color: {APP_COLORS['background']};
                border: 1px solid #2A2D32;
                border-radius: 8px;
                color: {APP_COLORS['text_primary']};
                font-weight: 700;
                margin-top: 4px;
            }}
            QScrollArea#infoScrollArea {{
                border: none;
                background: transparent;
            }}
            QScrollArea#infoScrollArea > QWidget {{
                background: transparent;
            }}
            """
        )


# The `SecureDeleteGUI` class sets up a GUI application with tabs for home, maintenance, metadata,
# cleaning, and info, with functionality to get and set the number of passes for data cleaning.
class SecureDeleteGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("VAULT") # Changed window title
        self.resize(760, 520)
        self.showMaximized() # Open in maximized mode

        main_layout = QVBoxLayout()

        self.tabs = QTabWidget()
        self.current_passes_value = 3 # To store the passes value

        self.db_path = Path.cwd() / "deleted_manifest.db"
        self.db_manager = LogDatabaseManager(self.db_path)
        
        # Global logger for SecureDeleteGUI - now just a console logger
        self.logger = ConsoleLogger() 
        # self.logger.log(f"[i] Using manifest database: {self.db_path}") # This log will be handled by CleaningTab

        # mcp_console_logger is only used by MCP orchestrator, can be a ConsoleLogger
        # self.mcp_orchestrator is now instantiated in CleaningTab
        # Additional icon setup for better visibility
        try:
            if "icon_path" in locals() and icon_path.exists():
                icon = QIcon(str(icon_path))
                if not icon.isNull():
                    # Add multiple sizes for better scaling
                    icon.addFile(str(icon_path), QSize(16, 16))
                    icon.addFile(str(icon_path), QSize(24, 24))
                    icon.addFile(str(icon_path), QSize(32, 32))
                    icon.addFile(str(icon_path), QSize(48, 48))
                    self.setWindowIcon(icon)
                    # Force icon update
                    self.update()
        except Exception as e:
            print(f"Additional icon setup failed: {e}")
        # Ensure RSA keys are generated at startup - NEW
        ensure_keys()
        
        # Create and add tabs with individual error handling
        try:
            # Home tab
            try:
                self.home_tab = HomeTab()
                self.tabs.addTab(self.home_tab, "Home")
                print("✅ Home tab created successfully")
            except Exception as e:
                print(f"❌ Error creating Home tab: {e}")
                # Create a fallback tab
                fallback_home = QWidget()
                fallback_layout = QVBoxLayout(fallback_home)
                fallback_layout.addWidget(QLabel("Home tab failed to load"))
                self.tabs.addTab(fallback_home, "Home")
            
            # Maintenance tab
            try:
                self.maintenance_tab = MaintenanceTab()
                self.tabs.addTab(self.maintenance_tab, "Maintenance")
                print("✅ Maintenance tab created successfully")
            except Exception as e:
                print(f"❌ Error creating Maintenance tab: {e}")
                import traceback
                traceback.print_exc()
                # Create a fallback tab
                fallback_maintenance = QWidget()
                fallback_layout = QVBoxLayout(fallback_maintenance)
                fallback_layout.addWidget(QLabel("Maintenance tab failed to load"))
                fallback_layout.addWidget(QLabel(f"Error: {str(e)}"))
                self.tabs.addTab(fallback_maintenance, "Maintenance")
            
            # Metadata tab
            try:
                self.metadata_tab = MetadataTab()
                self.tabs.addTab(self.metadata_tab, "Metadata")
                print("✅ Metadata tab created successfully")
            except Exception as e:
                print(f"❌ Error creating Metadata tab: {e}")
                # Create a fallback tab
                fallback_metadata = QWidget()
                fallback_layout = QVBoxLayout(fallback_metadata)
                fallback_layout.addWidget(QLabel("Metadata tab failed to load"))
                self.tabs.addTab(fallback_metadata, "Metadata")
            
            # Cleaning tab
            try:
                self.cleaning_tab = CleaningTab(self.db_manager, self.get_passes_value)
                self.tabs.addTab(self.cleaning_tab, "Cleaning")
                print("✅ Cleaning tab created successfully")
            except Exception as e:
                print(f"❌ Error creating Cleaning tab: {e}")
                # Create a fallback tab
                fallback_cleaning = QWidget()
                fallback_layout = QVBoxLayout(fallback_cleaning)
                fallback_layout.addWidget(QLabel("Cleaning tab failed to load"))
                self.tabs.addTab(fallback_cleaning, "Cleaning")
            
            # Info tab
            try:
                self.info_tab = InfoTab()
                self.tabs.addTab(self.info_tab, "Info")
                print("✅ Info tab created successfully")
            except Exception as e:
                print(f"❌ Error creating Info tab: {e}")
                # Create a fallback tab
                fallback_info = QWidget()
                fallback_layout = QVBoxLayout(fallback_info)
                fallback_layout.addWidget(QLabel("Info tab failed to load"))
                self.tabs.addTab(fallback_info, "Info")
            
            print(f"✅ GUI initialized with {self.tabs.count()} tabs")
            
        except Exception as e:
            print(f"❌ Critical error during tab creation: {e}")
            import traceback
            traceback.print_exc()
        
        # Add tabs to main layout and set layout
        main_layout.addWidget(self.tabs)
        self.setLayout(main_layout)

    def get_passes_value(self, value=None):
        if value is not None:
            self.current_passes_value = value
        return self.current_passes_value


# The `DeleteWorker` class in Python defines a worker object that performs secure file deletion with
# specified passes and emits signals for logging and completion with a unique wipe job ID.
class DeleteWorker(QObject):
    log = Signal(str)
    finished = Signal(bool, str, str) # Added wipe_job_id to signal

    def __init__(self, target: str, passes: int, db_manager: LogDatabaseManager, wipe_job_id: str):
        super().__init__()
        self.target = Path(target)
        self.passes = int(passes)
        self.db_manager = db_manager
        self.wipe_job_id = wipe_job_id

    def _emit(self, message: str):
        self.log.emit(message)

    def _append_manifest_entry(self, abs_path: Path, sha256: str):
        self.db_manager.add_entry(abs_path, sha256)

    def run(self):
        finished_emitter = lambda success, message: self.finished.emit(success, message, self.wipe_job_id) # Pass wipe_job_id
        _perform_secure_purge_logic(self.target, self.passes, self.db_manager, self._emit, finished_emitter, self.wipe_job_id)


# The `PhysicalDeviceWipeWorker` class performs secure wiping of physical devices on different
# operating systems using platform-specific commands and emits signals for logging and completion
# tracking.
class PhysicalDeviceWipeWorker(QObject):
    log = Signal(str)
    finished = Signal(bool, str, str) # Added wipe_job_id to signal

    def __init__(self, device_path: str, passes: int, wipe_job_id: str, logger: ConsoleLogger, is_system_wipe: bool = False):
        super().__init__()
        self.device_path = device_path
        self.passes = passes
        self.wipe_job_id = wipe_job_id
        self.logger = logger # Use the console logger for worker internal logs
        self.is_system_wipe = is_system_wipe # Whether this is a full system wipe

    def _emit_log(self, message: str):
        self.log.emit(message)
        self.logger.log(f"[PhysicalDeviceWipeWorker] {message}")

    def run(self):
        self._emit_log(f"Starting physical device wipe for {self.device_path} with {self.passes} passes.")
        success = False
        message = "Wipe failed due to unknown error."

        # For disk images in system wipe mode, we need special handling
        is_disk_image = False
        if self.is_system_wipe:
            if platform.system() == "Darwin" and not re.match(r'^/dev/disk\d+$', self.device_path):
                is_disk_image = True
                self._emit_log(f"Detected disk image: {self.device_path}")

        try:
            if platform.system() == "Darwin": # macOS
                # diskutil secureErase only supports specific levels, not arbitrary passes.
                # Level 0: single pass of zeros (fastest, least secure)
                # Level 1: single pass of random data (sufficient for modern drives)
                # Level 4: 7-pass erase (very slow, deprecated by NIST for SSDs)
                # We'll use a single pass of random data as a reasonable secure default.
                self._emit_log(f"macOS: Using diskutil secureErase randomData for {self.device_path}")
                command = ["diskutil", "secureErase", "randomData", self.device_path]
                
                process = subprocess.run(command, capture_output=True, text=True, check=True)
                self._emit_log(f"diskutil stdout:\n{process.stdout}")
                if process.stderr: self._emit_log(f"diskutil stderr:\n{process.stderr}")
                success = True
                message = f"Physical wipe of {self.device_path} completed successfully (macOS diskutil secureErase)."

            elif platform.system() == "Linux": # Linux
                # Use shred for robust multi-pass wiping
                self._emit_log(f"Linux: Using shred -v -n {self.passes} for {self.device_path}")
                # bs=4M for better performance, status=progress for feedback
                command = ["sudo", "shred", "-v", "-n", str(self.passes), self.device_path]
                
                # Capture output in real-time if possible, or wait
                process = subprocess.run(command, capture_output=True, text=True, check=True)
                self._emit_log(f"shred stdout:\n{process.stdout}")
                if process.stderr: self._emit_log(f"shred stderr:\n{process.stderr}")
                success = True
                message = f"Physical wipe of {self.device_path} completed successfully (Linux shred)."

            elif platform.system() == "Windows": # Windows
                # This is tricky. For raw disk wipe, diskpart script is needed.
                # The device_path will likely be something like '\\.\PHYSICALDRIVE0'
                self._emit_log(f"Windows: Preparing diskpart script for {self.device_path}")
                
                # Pre-process the device path to remove the problematic prefix outside the f-string
                disk_index_str = self.device_path.replace(r'\\.\\PHYSICALDRIVE', '')
                script_content = f"select disk {disk_index_str}\nclean all\nexit\n"
                script_file = Path(f"diskpart_wipe_{self.wipe_job_id}.txt")
                try:
                    script_file.write_text(script_content)
                    self._emit_log(f"diskpart script created: {script_file}")
                    command = ["diskpart", "/s", str(script_file)]
                    
                    # diskpart often requires elevation, which we assume is already present.
                    # We use shell=True for diskpart to find it in PATH
                    process = subprocess.run(command, capture_output=True, text=True, check=True, shell=True)
                    self._emit_log(f"diskpart stdout:\n{process.stdout}")
                    if process.stderr: self._emit_log(f"diskpart stderr:\n{process.stderr}")
                    success = True
                    message = f"Physical wipe of {self.device_path} completed successfully (Windows diskpart clean all)."
                finally:
                    if script_file.exists():
                        script_file.unlink(missing_ok=True)
                        self._emit_log(f"diskpart script removed: {script_file}")

            else:
                message = f"Unsupported OS for physical device wipe: {platform.system()}"
                self._emit_log(message)

        except subprocess.CalledProcessError as e:
            message = f"Physical wipe command failed with error for {self.device_path}: {e}"
            self._emit_log(message)
            if e.stdout: self._emit_log(f"stdout: {e.stdout}")
            if e.stderr: self._emit_log(f"stderr: {e.stderr}")
        except Exception as e:
            message = f"An unexpected error occurred during physical wipe for {self.device_path}: {e}"
            self._emit_log(message)
            import traceback
            self._emit_log(traceback.format_exc())
        
        # Store result for system wipe tracking
        self.last_result = (success, message)
        # Emit completion signal
        self.finished.emit(success, message, self.wipe_job_id)

        self.finished.emit(success, message, self.wipe_job_id)
