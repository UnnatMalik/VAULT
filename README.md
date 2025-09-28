# VAULT - Advanced Content Analysis & Secure Data Management System

## Project Overview

VAULT is a comprehensive, enterprise-grade system designed for **secure data purging**, **advanced content analysis**, and **system diagnostics**. Built with cutting-edge technologies, VAULT provides military-grade data destruction capabilities combined with intelligent content analysis and predictive analytics.

### Architecture
- **Frontend**: Modern PySide6 GUI with real-time progress tracking
- **Backend**: Distributed processing with multiprocessing for high-performance operations
- **AI/ML**: Advanced NLP models for content classification and analysis
- **Security**: Multi-pass encryption-based data overwriting with digital signatures

---

## Table of Contents

- [Core Features](#core-features)
- [Technology Stack](#technology-stack)
- [Installation Guide](#installation-guide)
- [Usage Documentation](#usage-documentation)
- [Module Documentation](#module-documentation)
- [API Reference](#api-reference)
- [Security Considerations](#security-considerations)
- [Contributing](#contributing)
- [License](#license)

---

## Core Features

### Secure Data Management
- **Multi-Pass Overwriting**: Military-grade data destruction with configurable passes (1-35)
- **Distributed Processing**: Parallel chunk processing for massive files and directories
- **Physical Device Wiping**: Cross-platform support for HDD/SSD secure erasure
- **Digital Certificates**: Cryptographically signed proof-of-destruction certificates
- **Manifest Logging**: SHA-256 hash tracking for verification and audit trails

### Advanced Content Analysis
- **Intelligent File Classification**: ML-powered content type detection
- **Sensitive Data Detection**: Pattern matching for PII, credentials, and confidential information
- **Metadata Extraction**: Comprehensive file and system metadata analysis
- **OCR Integration**: Text extraction from images and scanned documents
- **Language Detection**: Automatic language identification and processing

### System Diagnostics & Reporting
- **Hardware Analysis**: CPU, memory, storage, and battery health monitoring
- **Performance Metrics**: Real-time system performance tracking
- **PDF Report Generation**: Professional refurbishment and audit reports
- **Predictive Analytics**: ML-based wipe outcome prediction and recommendations

---

## Technology Stack

### Core Technologies
- **Python 3.11+** - Modern Python with type hints and async support
- **PySide6** - Cross-platform Qt6 GUI framework
- **SQLite3** - Embedded database for manifest and audit logging
- **Cryptography** - RSA digital signatures and encryption
- **ReportLab** - Professional PDF generation

### AI/ML & NLP
- **spaCy** - Advanced NLP and text processing
- **PyTorch** - Deep learning and transformer models
- **scikit-learn** - Traditional ML algorithms
- **Sentence Transformers** - Semantic text similarity
- **KeyBERT** - Automatic keyword extraction

### Computer Vision & Document Processing
- **PyMuPDF (fitz)** - Advanced PDF processing
- **Pillow (PIL)** - Image manipulation and processing
- **Tesseract OCR** - Text extraction from images
- **python-magic** - Advanced file type detection
- **python-docx/pptx** - Microsoft Office document processing

### System Integration
- **psutil** - Cross-platform system monitoring
- **multiprocessing** - Parallel processing and distributed computing
- **subprocess** - OS command execution and integration

---

## Installation Guide

### Prerequisites
- **Python 3.11+**
- **pip** (Python package manager)
- **Git** (for cloning repository)

### Step 1: Clone Repository
```bash
git clone https://github.com/your-repo/vault.git
cd vault
```

### Step 2: Create Virtual Environment (Recommended)
```bash
python -m venv venv
# Windows
venv\\Scripts\\activate
# macOS/Linux
source venv/bin/activate
```

### Step 3: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 4: Install System Dependencies

#### macOS (Homebrew)
```bash
# OCR for image text extraction
brew install tesseract

# File type detection
brew install libmagic

# GUI framework dependencies
brew install qt@6
```

#### Ubuntu/Debian
```bash
# OCR for image text extraction
sudo apt install tesseract-ocr

# File type detection
sudo apt install libmagic1 libmagic-dev

# GUI dependencies
sudo apt install qt6-base-dev
```

#### Windows
```powershell
# Download and install Tesseract OCR from:
# https://github.com/UB-Mannheim/tesseract/wiki

# Install libmagic equivalent (if needed)
# python-magic should work with pre-compiled wheels
```

### Step 5: Download Language Models
```bash
# Install spaCy English model
python -m spacy download en_core_web_sm
```

### Step 6: Verify Installation
```bash
python -c "import fitz, magic, spacy, PySide6, torch; print('All core dependencies installed successfully')"
```

---

## Usage Documentation

### Graphical User Interface (GUI)

Launch the main application:
```bash
python secure_purge.py
```

#### Interface Tabs:
- **Home**: System overview and storage summary
- **Maintenance**: Drive health, usage graphs, refurbish analytics
- **Metadata**: File and folder metadata analysis
- **Cleaning**: Secure deletion interface with progress tracking
- **Info**: Detailed system and hardware information

### Command Line Interface (CLI)

#### Secure File Deletion
```bash
# Delete single file with 7 passes
python secure_purge.py /path/to/file.txt --passes 7

# Delete directory recursively with 3 passes
python secure_purge.py /path/to/directory --passes 3
```

#### Manifest Verification
```bash
# Verify deletions from manifest database
python secure_purge.py --verify --database ./deleted_manifest.db
```

#### Physical Device Wiping
```bash
# Wipe entire disk (DANGEROUS - use with extreme caution)
python secure_purge.py --device /dev/sdb --passes 1
```

### Python API Usage

```python
from content_analyzer import ContentAnalyzer
from distributed_worker import DistributedWipeManager

# Content Analysis
analyzer = ContentAnalyzer()
analysis = analyzer.analyze_file("document.pdf")
print(f"Content type: {analysis.content_type}")
print(f"Sensitive info found: {len(analysis.sensitive_info)} items")

# Secure Wiping
with DistributedWipeManager(num_workers=4) as manager:
    task_id = manager.queue_file_wipe("sensitive_file.txt", passes=3)
    # Monitor progress...
```

---

## Module Documentation

### Content Analyzer (`content_analyzer.py`)

The **ContentAnalyzer** is VAULT's intelligent analysis engine that provides comprehensive file and content analysis capabilities.

#### Key Features:
- **Multi-Format Support**: 25+ file types including documents, images, archives, code files
- **Intelligent Classification**: ML-powered content type detection
- **Sensitive Data Detection**: Advanced pattern matching for PII, credentials, secrets
- **Metadata Extraction**: Comprehensive file system and content metadata
- **OCR Integration**: Text extraction from images and scanned documents
- **Language Detection**: Automatic language identification
- **Performance Optimization**: Caching system with SQLite backend

#### Core Classes:

```python
class ContentAnalyzer:
    """Advanced content analyzer with ML-powered classification."""

    def __init__(self, db_path: Optional[str] = None, n_threads: int = -1)
    def analyze_file(self, file_path: str) -> ContentAnalysis
    def analyze_directory(self, directory: str, recursive: bool = True) -> Dict[str, ContentAnalysis]
    def get_analysis_stats(self) -> Dict[str, Any]

class ContentAnalysis:
    """Container for comprehensive file analysis results."""

    content_type: ContentType          # Detected content type
    sensitive_info: List[Dict]         # Detected sensitive information
    keywords: List[str]                # Extracted keywords
    entities: List[Dict]               # Named entities found
    metadata: Dict[str, Any]           # File and system metadata
    checksum: str                      # File integrity hash
    sensitivity_score: float           # Risk assessment score
```

#### Content Types Supported:
- **Documents**: PDF, Word, Excel, PowerPoint, ODT, RTF
- **Images**: JPEG, PNG, TIFF, BMP, WebP
- **Archives**: ZIP, RAR, 7Z, TAR, GZ
- **Code**: Python, JavaScript, Java, C/C++, Go, Rust, etc.
- **Data**: CSV, JSON, XML, Databases
- **Media**: Audio, Video files

### Distributed Worker (`distributed_worker.py`)

The **DistributedWipeManager** provides high-performance, parallel data destruction capabilities using multiprocessing.

#### Key Features:
- **Parallel Processing**: Multi-core CPU utilization for maximum speed
- **Chunk-Based Operations**: Memory-efficient processing of large files
- **Progress Tracking**: Real-time monitoring of wipe operations
- **Error Handling**: Robust error recovery and reporting
- **Encryption Integration**: Optional encryption-based overwriting
- **Verification**: Checksum validation for each processed chunk

#### Core Classes:

```python
class DistributedWipeManager:
    """Manages distributed secure wipe operations."""

    def __init__(self, num_workers: int = None, chunk_size: int = 1024*1024)
    def queue_file_wipe(self, file_path: str, passes: int = 3) -> str
    def process_results(self, timeout: float = 0.1) -> Dict
    def get_task_status(self, task_id: str) -> Optional[Dict]

@dataclass
class ChunkInfo:
    """Information about a data chunk to be processed."""
    chunk_id: str
    target_path: str
    start_pos: int
    chunk_size: int
    total_size: int
    pass_num: int
    total_passes: int
```

#### Security Features:
- **Multi-Pass Overwriting**: Configurable number of random data passes
- **Cryptographic Security**: Optional Fernet encryption for enhanced security
- **Chunk Verification**: SHA-256 checksums for each processed chunk
- **Atomic Operations**: Transaction-like processing with rollback capability

---

## Security Considerations

### Data Destruction Standards
- **DoD 5220.22-M**: Department of Defense data sanitization standard
- **Gutmann Method**: 35-pass overwriting for magnetic media
- **Random Data**: Cryptographically secure pseudo-random number generation
- **Verification**: Post-wipe integrity checking and reporting

### Cryptographic Security
- **RSA-2048**: Digital signatures for certificate authenticity
- **SHA-256**: File integrity verification and checksums
- **AES-256**: Optional encryption-based overwriting
- **Key Management**: Secure key generation and storage

### Operational Security
- **Audit Logging**: Comprehensive operation tracking
- **Manifest Verification**: Post-deletion integrity checking
- **Certificate Generation**: Tamper-evident proof of destruction
- **Chain of Custody**: Complete operational history tracking

---

## Contributing

### Development Setup
1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Make your changes
4. Add tests for new functionality
5. Run the test suite: `python -m pytest`
6. Commit your changes: `git commit -m 'Add amazing feature'`
7. Push to the branch: `git push origin feature/amazing-feature`
8. Open a Pull Request

### Code Style
- **PEP 8**: Python style guide compliance
- **Type Hints**: Comprehensive type annotations
- **Documentation**: Docstring for all public methods
- **Testing**: Unit tests for core functionality

### Testing
```bash
# Run all tests
python -m pytest tests/

# Run specific test module
python -m pytest tests/test_content_analyzer.py

# Run with coverage
python -m pytest --cov=src tests/
```

---

## License

This project is licensed under the **MIT License** - see the [LICENSE](LICENSE) file for details.

### Third-Party Licenses
- **PySide6**: LGPL-3.0 License
- **spaCy**: MIT License
- **PyTorch**: BSD-3-Clause License
- **ReportLab**: BSD-3-Clause License

---

## Support & Troubleshooting

### Common Issues

#### Installation Problems
- **ModuleNotFoundError**: Ensure all dependencies are installed from `requirements.txt`
- **Import Errors**: Check Python version compatibility (3.11+ required)
- **GUI Issues**: Verify PySide6 installation and Qt6 system libraries

#### Runtime Issues
- **Memory Errors**: Reduce chunk size for large files
- **Permission Errors**: Run with appropriate system privileges
- **Performance Issues**: Adjust number of worker processes

#### System Compatibility
- **macOS**: Requires Homebrew for system dependencies
- **Linux**: May need additional Qt6 development packages
- **Windows**: Requires Visual C++ redistributables

### Getting Help
1. Check the [Issues](../../issues) section
2. Review the [Wiki](../../wiki) for detailed guides
3. Join our [Discord](https://discord.gg/vault) community
4. Contact: support@vault-project.com

---

## Roadmap

### Version 2.0 (Current)
- Distributed processing architecture
- Advanced content analysis with ML
- Cross-platform GUI interface
- Comprehensive security features

### Version 2.1 (Planned)
- Enhanced OCR capabilities
- Cloud storage integration
- Advanced encryption options
- Performance optimizations

### Version 3.0 (Future)
- Web-based interface
- API server mode
- Advanced threat detection
- Blockchain-based verification

---

## Acknowledgments

- **PySide6 Team** - Excellent cross-platform GUI framework
- **spaCy Team** - Advanced NLP capabilities
- **PyTorch Team** - Deep learning infrastructure
- **ReportLab** - Professional PDF generation
- **Open Source Community** - Countless libraries and tools

---

**WARNING**: This software performs **irreversible data destruction**. Always maintain secure backups of critical data and use with extreme caution in production environments.

