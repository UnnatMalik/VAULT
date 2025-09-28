"""
API Client for sending wipe certificates to Django backend.
Handles automatic detection and transmission of wipe certificate data.
"""

import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any
import urllib.request
import urllib.parse
import urllib.error
import ssl


class WipeCertificateAPIClient:
    """Client for sending wipe certificates to Django backend API."""
    
    def __init__(self, api_endpoint: str, timeout: int = 30):
        """
        Initialize the API client.
        
        Args:
            api_endpoint: The Django backend API endpoint URL
            timeout: Request timeout in seconds
        """
        self.api_endpoint = api_endpoint
        self.timeout = timeout
        self.logger = logging.getLogger(__name__)
        
        # Configure logging if not already configured
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)
    
    def send_wipe_certificate(self, certificate_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Send wipe certificate data to Django backend.
        
        Args:
            certificate_data: The wipe certificate JSON data
            
        Returns:
            Dict containing success status and response data
        """
        try:
            # Prepare the request data
            json_data = json.dumps(certificate_data).encode('utf-8')
            
            # Create the request
            req = urllib.request.Request(
                self.api_endpoint,
                data=json_data,
                headers={
                    'Content-Type': 'application/json',
                    'User-Agent': 'VAULT-SecurePurge/1.0',
                    'Accept': 'application/json'
                },
                method='POST'
            )
            
            # Create SSL context that doesn't verify certificates (for development)
            # In production, you might want to verify certificates
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            self.logger.info(f"Sending wipe certificate to {self.api_endpoint}")
            
            # Send the request
            with urllib.request.urlopen(req, timeout=self.timeout, context=ssl_context) as response:
                response_data = response.read().decode('utf-8')
                status_code = response.getcode()
                
                if status_code == 200 or status_code == 201:
                    self.logger.info("Wipe certificate sent successfully")
                    try:
                        response_json = json.loads(response_data) if response_data else {}
                    except json.JSONDecodeError:
                        response_json = {"raw_response": response_data}
                    
                    return {
                        "success": True,
                        "status_code": status_code,
                        "response": response_json,
                        "message": "Certificate sent successfully"
                    }
                else:
                    self.logger.warning(f"Unexpected status code: {status_code}")
                    return {
                        "success": False,
                        "status_code": status_code,
                        "response": response_data,
                        "message": f"Server returned status code {status_code}"
                    }
                    
        except urllib.error.HTTPError as e:
            error_msg = f"HTTP Error {e.code}: {e.reason}"
            try:
                error_response = e.read().decode('utf-8')
                self.logger.error(f"{error_msg} - Response: {error_response}")
                return {
                    "success": False,
                    "status_code": e.code,
                    "response": error_response,
                    "message": error_msg
                }
            except Exception:
                self.logger.error(error_msg)
                return {
                    "success": False,
                    "status_code": e.code,
                    "response": None,
                    "message": error_msg
                }
                
        except urllib.error.URLError as e:
            error_msg = f"URL Error: {e.reason}"
            self.logger.error(error_msg)
            return {
                "success": False,
                "status_code": None,
                "response": None,
                "message": error_msg
            }
            
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            self.logger.error(error_msg)
            return {
                "success": False,
                "status_code": None,
                "response": None,
                "message": error_msg
            }
    
    def send_wipe_certificate_from_file(self, certificate_file_path: Path) -> Dict[str, Any]:
        """
        Load and send wipe certificate from JSON file.
        
        Args:
            certificate_file_path: Path to the wipe certificate JSON file
            
        Returns:
            Dict containing success status and response data
        """
        try:
            if not certificate_file_path.exists():
                error_msg = f"Certificate file not found: {certificate_file_path}"
                self.logger.error(error_msg)
                return {
                    "success": False,
                    "status_code": None,
                    "response": None,
                    "message": error_msg
                }
            
            # Load the certificate data
            with open(certificate_file_path, 'r', encoding='utf-8') as f:
                certificate_data = json.load(f)
            
            self.logger.info(f"Loaded certificate from {certificate_file_path}")
            
            # Send the certificate
            result = self.send_wipe_certificate(certificate_data)
            
            # Add file path to result for reference
            result["source_file"] = str(certificate_file_path)
            
            return result
            
        except json.JSONDecodeError as e:
            error_msg = f"Invalid JSON in certificate file: {e}"
            self.logger.error(error_msg)
            return {
                "success": False,
                "status_code": None,
                "response": None,
                "message": error_msg,
                "source_file": str(certificate_file_path)
            }
            
        except Exception as e:
            error_msg = f"Error loading certificate file: {str(e)}"
            self.logger.error(error_msg)
            return {
                "success": False,
                "status_code": None,
                "response": None,
                "message": error_msg,
                "source_file": str(certificate_file_path)
            }


class WipeCertificateDetector:
    """Detects newly created wipe certificate files."""
    
    def __init__(self, model_artifacts_dir: Path):
        """
        Initialize the certificate detector.
        
        Args:
            model_artifacts_dir: Directory where certificates are stored
        """
        self.model_artifacts_dir = model_artifacts_dir
        self.logger = logging.getLogger(__name__)
        
        # Configure logging if not already configured
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)
    
    def find_wipe_certificate_files(self) -> list[Path]:
        """
        Find all wipe certificate JSON files in the model_artifacts directory.
        
        Returns:
            List of paths to wipe certificate JSON files
        """
        try:
            if not self.model_artifacts_dir.exists():
                self.logger.warning(f"Model artifacts directory not found: {self.model_artifacts_dir}")
                return []
            
            # Look for files matching the pattern: *_wipe_certificate.json
            certificate_files = list(self.model_artifacts_dir.glob("*_wipe_certificate.json"))
            
            self.logger.info(f"Found {len(certificate_files)} wipe certificate files")
            return certificate_files
            
        except Exception as e:
            self.logger.error(f"Error finding certificate files: {str(e)}")
            return []
    
    def find_latest_wipe_certificate(self) -> Optional[Path]:
        """
        Find the most recently created wipe certificate file.
        
        Returns:
            Path to the latest wipe certificate file, or None if none found
        """
        certificate_files = self.find_wipe_certificate_files()
        
        if not certificate_files:
            return None
        
        # Sort by modification time (most recent first)
        try:
            latest_file = max(certificate_files, key=lambda p: p.stat().st_mtime)
            self.logger.info(f"Latest wipe certificate: {latest_file}")
            return latest_file
        except Exception as e:
            self.logger.error(f"Error finding latest certificate: {str(e)}")
            return None


def auto_send_wipe_certificate(
    certificate_id: str,
    model_artifacts_dir: Path,
    api_endpoint: str,
    gui_logger=None
) -> Dict[str, Any]:
    """
    Automatically detect and send a wipe certificate to the Django backend.
    
    Args:
        certificate_id: The certificate ID to look for
        model_artifacts_dir: Directory containing certificate files
        api_endpoint: Django backend API endpoint
        gui_logger: Optional GUI logger instance
        
    Returns:
        Dict containing success status and response data
    """
    logger = logging.getLogger(__name__)
    
    try:
        # Create the expected certificate filename
        certificate_filename = f"{certificate_id}_wipe_certificate.json"
        certificate_path = model_artifacts_dir / certificate_filename
        
        if gui_logger:
            gui_logger.log(f"[API] Looking for certificate: {certificate_filename}")
        
        # Initialize API client
        api_client = WipeCertificateAPIClient(api_endpoint)
        
        # Send the certificate
        result = api_client.send_wipe_certificate_from_file(certificate_path)
        
        if result["success"]:
            success_msg = "[API] Certificate sent successfully to Django backend"
            logger.info(success_msg)
            if gui_logger:
                gui_logger.log(success_msg)
        else:
            error_msg = f"[API] Failed to send certificate: {result['message']}"
            logger.error(error_msg)
            if gui_logger:
                gui_logger.log(error_msg)
        
        return result
        
    except Exception as e:
        error_msg = f"[API] Unexpected error in auto_send_wipe_certificate: {str(e)}"
        logger.error(error_msg)
        if gui_logger:
            gui_logger.log(error_msg)
        
        return {
            "success": False,
            "status_code": None,
            "response": None,
            "message": error_msg
        }