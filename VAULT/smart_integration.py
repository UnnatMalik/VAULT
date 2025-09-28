#!/usr/bin/env python3
"""
SMART Integration Module - Integrates SMART data with VAULT's reporting system
"""

import json
import logging
from datetime import datetime
from typing import Dict, List, Optional

try:
    from smart_worker import SMARTMonitor
    from smart_monitor import SMARTData, SMARTStatus
    SMART_AVAILABLE = True
except ImportError:
    SMART_AVAILABLE = False


class SMARTReportIntegrator:
    """Integrates SMART data with VAULT's reporting and certification system"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.smart_monitor = None
        
        if SMART_AVAILABLE:
            try:
                self.smart_monitor = SMARTMonitor()
            except Exception as e:
                self.logger.warning(f"Failed to initialize SMART monitor: {e}")
    
    def is_available(self) -> bool:
        """Check if SMART monitoring is available"""
        return self.smart_monitor is not None
    
    def collect_smart_data_for_report(self) -> Dict:
        """Collect SMART data for inclusion in refurbish reports"""
        if not self.smart_monitor:
            return {
                'smart_available': False,
                'error': 'SMART monitoring not available',
                'drives': []
            }
        
        try:
            drives = self.smart_monitor.get_available_drives()
            smart_data_list = []
            
            for drive_path in drives:
                smart_data = self.smart_monitor.get_smart_data(drive_path)
                if smart_data:
                    # Create a simplified version for reports
                    # Extract Phase 2 parameters from attributes
                    phase2_params = self._extract_phase2_parameters(smart_data)
                    
                    drive_report = {
                        'device_path': smart_data.device_path,
                        'device_model': smart_data.device_model,
                        'serial_number': smart_data.serial_number,
                        'capacity': smart_data.capacity,
                        'drive_type': smart_data.drive_type.value,
                        'smart_status': smart_data.smart_status.value,
                        'health_score': smart_data.health_score,
                        'temperature': smart_data.temperature,
                        'power_on_hours': smart_data.power_on_hours,
                        'power_cycle_count': smart_data.power_cycle_count,
                        'ssd_life_left': smart_data.ssd_life_left,
                        'reallocated_sectors': smart_data.reallocated_sectors,
                        'pending_sectors': smart_data.pending_sectors,
                        'bad_blocks': smart_data.bad_blocks,
                        'last_updated': smart_data.last_updated.isoformat(),
                        
                        # Phase 2: Extended SMART Attributes
                        'raw_read_error_rate': phase2_params.get('raw_read_error_rate'),
                        'spin_up_time': phase2_params.get('spin_up_time'),
                        'start_stop_count': phase2_params.get('start_stop_count'),
                        'seek_error_rate': phase2_params.get('seek_error_rate'),
                        'drive_temperature': smart_data.temperature,  # Alias for compatibility
                        
                        # Enhanced reporting
                        'critical_attributes': self._get_critical_attributes(smart_data),
                        'phase2_attributes': self._get_phase2_attributes(smart_data),
                        'health_assessment': self._assess_drive_health(smart_data),
                        'predictive_analysis': self._generate_predictive_analysis(smart_data)
                    }
                    smart_data_list.append(drive_report)
            
            return {
                'smart_available': True,
                'collection_timestamp': datetime.now().isoformat(),
                'total_drives': len(drives),
                'drives_with_data': len(smart_data_list),
                'drives': smart_data_list,
                'system_health_summary': self._generate_system_health_summary(smart_data_list)
            }
            
        except Exception as e:
            self.logger.error(f"Error collecting SMART data for report: {e}")
            return {
                'smart_available': True,
                'error': str(e),
                'drives': []
            }
    
    def _get_critical_attributes(self, smart_data: SMARTData) -> List[Dict]:
        """Extract critical SMART attributes"""
        critical_attrs = []
        
        # Define critical attribute IDs and their significance
        critical_ids = {
            5: 'Reallocated Sector Count',
            10: 'Spin Retry Count',
            187: 'Reported Uncorrectable Errors',
            188: 'Command Timeout',
            196: 'Reallocation Event Count',
            197: 'Current Pending Sector Count',
            198: 'Offline Uncorrectable',
            199: 'Ultra DMA CRC Error Count'
        }
        
        for attr_id, description in critical_ids.items():
            if attr_id in smart_data.attributes:
                attr = smart_data.attributes[attr_id]
                critical_attrs.append({
                    'id': attr.id,
                    'name': attr.name,
                    'description': description,
                    'value': attr.value,
                    'raw_value': attr.raw_value,
                    'threshold': attr.threshold,
                    'is_critical': attr.is_critical,
                    'status': 'CRITICAL' if attr.is_critical else 'OK'
                })
        
        return critical_attrs
    
    def _assess_drive_health(self, smart_data: SMARTData) -> Dict:
        """Assess overall drive health"""
        assessment = {
            'overall_status': 'UNKNOWN',
            'risk_level': 'UNKNOWN',
            'recommendations': [],
            'estimated_remaining_life': 'UNKNOWN'
        }
        
        # Determine overall status
        if smart_data.smart_status == SMARTStatus.FAILED:
            assessment['overall_status'] = 'FAILED'
            assessment['risk_level'] = 'CRITICAL'
            assessment['recommendations'].append('Immediate replacement required')
        elif smart_data.health_score < 20:
            assessment['overall_status'] = 'POOR'
            assessment['risk_level'] = 'HIGH'
            assessment['recommendations'].append('Replace soon - high failure risk')
        elif smart_data.health_score < 50:
            assessment['overall_status'] = 'FAIR'
            assessment['risk_level'] = 'MEDIUM'
            assessment['recommendations'].append('Monitor closely - consider replacement')
        elif smart_data.health_score < 80:
            assessment['overall_status'] = 'GOOD'
            assessment['risk_level'] = 'LOW'
            assessment['recommendations'].append('Continue monitoring')
        else:
            assessment['overall_status'] = 'EXCELLENT'
            assessment['risk_level'] = 'VERY_LOW'
            assessment['recommendations'].append('Drive appears healthy')
        
        # Additional recommendations based on specific metrics
        if smart_data.temperature and smart_data.temperature > 60:
            assessment['recommendations'].append('High temperature detected - improve cooling')
        
        if smart_data.reallocated_sectors and smart_data.reallocated_sectors > 0:
            assessment['recommendations'].append('Reallocated sectors detected - monitor for progression')
        
        if smart_data.pending_sectors and smart_data.pending_sectors > 0:
            assessment['recommendations'].append('Pending sectors detected - may indicate developing issues')
        
        # Estimate remaining life for SSDs
        if smart_data.ssd_life_left:
            assessment['estimated_remaining_life'] = f"{smart_data.ssd_life_left}% SSD life remaining"
        elif smart_data.power_on_hours:
            # Rough estimate for HDDs (typical lifespan 3-5 years of continuous use)
            hours_per_year = 8760
            typical_lifespan_years = 4
            usage_years = smart_data.power_on_hours / hours_per_year
            remaining_years = max(0, typical_lifespan_years - usage_years)
            assessment['estimated_remaining_life'] = f"Approximately {remaining_years:.1f} years (based on typical HDD lifespan)"
        
        return assessment
    
    def _extract_phase2_parameters(self, smart_data: SMARTData) -> Dict:
        """Extract Phase 2 SMART parameters from attributes"""
        phase2_params = {}
        
        # Phase 2 attribute mappings
        phase2_mappings = {
            1: 'raw_read_error_rate',
            3: 'spin_up_time', 
            4: 'start_stop_count',
            7: 'seek_error_rate'
        }
        
        for attr_id, param_name in phase2_mappings.items():
            if attr_id in smart_data.attributes:
                attr = smart_data.attributes[attr_id]
                phase2_params[param_name] = {
                    'value': attr.value,
                    'raw_value': attr.raw_value,
                    'threshold': attr.threshold,
                    'is_critical': attr.is_critical
                }
            else:
                phase2_params[param_name] = None
        
        return phase2_params
    
    def _get_phase2_attributes(self, smart_data: SMARTData) -> List[Dict]:
        """Get Phase 2 SMART attributes for detailed reporting"""
        phase2_attrs = []
        
        # Phase 2 critical attribute IDs and descriptions
        phase2_ids = {
            1: 'Raw Read Error Rate',
            3: 'Spin Up Time',
            4: 'Start/Stop Count', 
            7: 'Seek Error Rate'
        }
        
        for attr_id, description in phase2_ids.items():
            if attr_id in smart_data.attributes:
                attr = smart_data.attributes[attr_id]
                phase2_attrs.append({
                    'id': attr.id,
                    'name': attr.name,
                    'description': description,
                    'value': attr.value,
                    'raw_value': attr.raw_value,
                    'threshold': attr.threshold,
                    'is_critical': attr.is_critical,
                    'status': 'CRITICAL' if attr.is_critical else 'OK'
                })
        
        return phase2_attrs
    
    def _generate_predictive_analysis(self, smart_data: SMARTData) -> Dict:
        """Generate Phase 3 predictive analysis"""
        analysis = {
            'failure_risk': 'UNKNOWN',
            'estimated_lifespan': 'UNKNOWN',
            'wear_indicators': [],
            'performance_trends': [],
            'recommendations': []
        }
        
        # Failure risk assessment based on multiple factors
        risk_factors = 0
        risk_details = []
        
        # Critical attribute analysis
        if smart_data.reallocated_sectors and smart_data.reallocated_sectors > 0:
            risk_factors += 3
            risk_details.append(f'Reallocated sectors: {smart_data.reallocated_sectors}')
        
        if smart_data.pending_sectors and smart_data.pending_sectors > 0:
            risk_factors += 2
            risk_details.append(f'Pending sectors: {smart_data.pending_sectors}')
        
        if smart_data.bad_blocks and smart_data.bad_blocks > 0:
            risk_factors += 2
            risk_details.append(f'Bad blocks: {smart_data.bad_blocks}')
        
        # Temperature analysis
        if smart_data.temperature:
            if smart_data.temperature > 70:
                risk_factors += 2
                risk_details.append(f'Critical temperature: {smart_data.temperature}°C')
            elif smart_data.temperature > 60:
                risk_factors += 1
                risk_details.append(f'High temperature: {smart_data.temperature}°C')
        
        # Age analysis
        if smart_data.power_on_hours:
            years = smart_data.power_on_hours / 8760
            if years > 5:
                risk_factors += 2
                risk_details.append(f'Very old drive: {years:.1f} years')
            elif years > 3:
                risk_factors += 1
                risk_details.append(f'Aging drive: {years:.1f} years')
        
        # SSD wear analysis
        if smart_data.ssd_life_left:
            if smart_data.ssd_life_left < 10:
                risk_factors += 3
                risk_details.append(f'Critical SSD wear: {smart_data.ssd_life_left}% remaining')
            elif smart_data.ssd_life_left < 25:
                risk_factors += 2
                risk_details.append(f'High SSD wear: {smart_data.ssd_life_left}% remaining')
        
        # Determine overall risk
        if risk_factors >= 6:
            analysis['failure_risk'] = 'CRITICAL'
        elif risk_factors >= 4:
            analysis['failure_risk'] = 'HIGH'
        elif risk_factors >= 2:
            analysis['failure_risk'] = 'MEDIUM'
        else:
            analysis['failure_risk'] = 'LOW'
        
        analysis['risk_factors'] = risk_details
        
        # Estimated lifespan calculation
        if smart_data.ssd_life_left:
            # SSD lifespan estimation
            if smart_data.power_on_hours:
                hours_per_percent = smart_data.power_on_hours / (100 - smart_data.ssd_life_left)
                remaining_hours = smart_data.ssd_life_left * hours_per_percent
                remaining_years = remaining_hours / 8760
                analysis['estimated_lifespan'] = f'{remaining_years:.1f} years (SSD wear-based)'
        elif smart_data.power_on_hours:
            # HDD lifespan estimation (typical 4-5 year lifespan)
            years_used = smart_data.power_on_hours / 8760
            typical_lifespan = 4.5
            remaining_years = max(0, typical_lifespan - years_used)
            analysis['estimated_lifespan'] = f'{remaining_years:.1f} years (statistical estimate)'
        
        # Performance trend analysis
        if smart_data.attributes:
            # Analyze performance-related attributes
            performance_attrs = [1, 7, 3]  # Read errors, seek errors, spin-up time
            for attr_id in performance_attrs:
                if attr_id in smart_data.attributes:
                    attr = smart_data.attributes[attr_id]
                    if attr.is_critical:
                        analysis['performance_trends'].append(f'{attr.name}: DEGRADED')
                    elif hasattr(attr, 'raw_value') and isinstance(attr.raw_value, int) and attr.raw_value > 0:
                        analysis['performance_trends'].append(f'{attr.name}: {attr.raw_value} errors')
        
        # Generate recommendations
        if analysis['failure_risk'] in ['CRITICAL', 'HIGH']:
            analysis['recommendations'].append('Immediate backup and drive replacement recommended')
        elif analysis['failure_risk'] == 'MEDIUM':
            analysis['recommendations'].append('Increase backup frequency and monitor closely')
        
        if smart_data.temperature and smart_data.temperature > 60:
            analysis['recommendations'].append('Improve system cooling to reduce drive temperature')
        
        if smart_data.ssd_life_left and smart_data.ssd_life_left < 25:
            analysis['recommendations'].append('Plan SSD replacement within next 6 months')
        
        return analysis
    
    def _generate_system_health_summary(self, drives_data: List[Dict]) -> Dict:
        """Generate overall system health summary"""
        if not drives_data:
            return {
                'overall_health': 'UNKNOWN',
                'total_drives': 0,
                'healthy_drives': 0,
                'warning_drives': 0,
                'critical_drives': 0,
                'recommendations': ['No SMART data available']
            }
        
        total_drives = len(drives_data)
        healthy_drives = 0
        warning_drives = 0
        critical_drives = 0
        
        for drive in drives_data:
            health_score = drive.get('health_score', 0)
            if health_score >= 80:
                healthy_drives += 1
            elif health_score >= 50:
                warning_drives += 1
            else:
                critical_drives += 1
        
        # Determine overall health
        if critical_drives > 0:
            overall_health = 'CRITICAL'
        elif warning_drives > total_drives * 0.5:  # More than 50% in warning state
            overall_health = 'WARNING'
        elif healthy_drives >= total_drives * 0.8:  # 80% or more healthy
            overall_health = 'GOOD'
        else:
            overall_health = 'FAIR'
        
        # Generate recommendations
        recommendations = []
        if critical_drives > 0:
            recommendations.append(f'{critical_drives} drive(s) require immediate attention')
        if warning_drives > 0:
            recommendations.append(f'{warning_drives} drive(s) should be monitored closely')
        if healthy_drives == total_drives:
            recommendations.append('All drives appear healthy - continue regular monitoring')
        
        return {
            'overall_health': overall_health,
            'total_drives': total_drives,
            'healthy_drives': healthy_drives,
            'warning_drives': warning_drives,
            'critical_drives': critical_drives,
            'health_percentage': (healthy_drives / total_drives) * 100 if total_drives > 0 else 0,
            'recommendations': recommendations
        }
    
    def generate_smart_certificate_section(self) -> Dict:
        """Generate SMART data section for wipe certificates"""
        smart_data = self.collect_smart_data_for_report()
        
        if not smart_data.get('smart_available', False):
            return {
                'smart_monitoring': {
                    'available': False,
                    'note': 'SMART monitoring was not available during the wipe process'
                }
            }
        
        # Create certificate-specific summary
        certificate_data = {
            'smart_monitoring': {
                'available': True,
                'collection_timestamp': smart_data['collection_timestamp'],
                'total_drives_monitored': smart_data['total_drives'],
                'system_health_summary': smart_data['system_health_summary'],
                'drive_health_details': []
            }
        }
        
        # Add essential health data for each drive
        for drive in smart_data.get('drives', []):
            drive_summary = {
                'device_path': drive['device_path'],
                'model': drive['device_model'],
                'serial': drive['serial_number'],
                'smart_status': drive['smart_status'],
                'health_score': drive['health_score'],
                'health_assessment': drive['health_assessment']['overall_status'],
                'risk_level': drive['health_assessment']['risk_level'],
                'critical_issues': len([attr for attr in drive['critical_attributes'] if attr['is_critical']]) > 0
            }
            certificate_data['smart_monitoring']['drive_health_details'].append(drive_summary)
        
        return certificate_data
    
    def enhance_refurbish_report(self, base_report: Dict) -> Dict:
        """Enhance existing refurbish report with SMART data"""
        enhanced_report = base_report.copy()
        
        # Add SMART data section
        smart_data = self.collect_smart_data_for_report()
        enhanced_report['smart_health_analysis'] = smart_data
        
        # Update executive summary if SMART data is available
        if smart_data.get('smart_available', False) and 'executive_summary' in enhanced_report:
            summary = smart_data.get('system_health_summary', {})
            health_status = summary.get('overall_health', 'UNKNOWN')
            
            # Add SMART health to executive summary
            if 'drive_health' not in enhanced_report['executive_summary']:
                enhanced_report['executive_summary']['drive_health'] = {}
            
            enhanced_report['executive_summary']['drive_health'].update({
                'smart_monitoring_available': True,
                'overall_smart_health': health_status,
                'total_drives_monitored': summary.get('total_drives', 0),
                'drives_requiring_attention': summary.get('critical_drives', 0) + summary.get('warning_drives', 0)
            })
        
        return enhanced_report


# Utility functions for integration with existing VAULT components
def get_smart_integrator() -> Optional[SMARTReportIntegrator]:
    """Get SMART integrator instance if available"""
    try:
        return SMARTReportIntegrator()
    except Exception:
        return None


def add_smart_data_to_certificate(certificate_data: Dict) -> Dict:
    """Add SMART data to wipe certificate"""
    integrator = get_smart_integrator()
    if integrator and integrator.is_available():
        smart_section = integrator.generate_smart_certificate_section()
        certificate_data.update(smart_section)
    else:
        certificate_data['smart_monitoring'] = {
            'available': False,
            'note': 'SMART monitoring was not available during the wipe process'
        }
    
    return certificate_data


def enhance_refurbish_report_with_smart(report_data: Dict) -> Dict:
    """Enhance refurbish report with SMART data"""
    integrator = get_smart_integrator()
    if integrator and integrator.is_available():
        return integrator.enhance_refurbish_report(report_data)
    else:
        # Add note that SMART data is not available
        report_data['smart_health_analysis'] = {
            'smart_available': False,
            'note': 'SMART monitoring dependencies not available'
        }
        return report_data
