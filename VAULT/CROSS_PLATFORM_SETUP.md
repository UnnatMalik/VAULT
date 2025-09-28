# VAULT Cross-Platform Setup Guide

VAULT is designed to run seamlessly across **Windows**, **macOS**, and **Linux** systems. This guide provides comprehensive setup instructions for all supported platforms.

## Quick Start

### 1. Check Dependencies (All Platforms)
```bash
python secure_purge.py --check-deps
```

### 2. Install Python Dependencies
```bash
pip install -r requirements.txt
python -m spacy download en_core_web_sm
```

### 3. Platform-Specific Setup
Choose your platform below for detailed instructions.

---

## macOS Setup

### Prerequisites
- macOS 12.0+ (Monterey or later)
- Python 3.11+
- Homebrew (recommended)

### Installation Steps

#### 1. Install Homebrew (if not installed)
```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

#### 2. Install System Dependencies
```bash
brew install tesseract libmagic
```

#### 3. Install Python Dependencies
```bash
pip install -r requirements.txt
python -m spacy download en_core_web_sm
```

#### 4. Verify Installation
```bash
python secure_purge.py --check-deps
```

### macOS-Specific Features
- Native disk detection via `diskutil`
- Hardware profiling via `system_profiler`
- Battery monitoring via `pmset`
- Full GUI support with native look and feel

---

## Windows Setup

### Prerequisites
- Windows 10/11 (64-bit)
- Python 3.11+
- Administrator privileges (for some features)

### Installation Steps

#### 1. Install Tesseract OCR
1. Download from: https://github.com/UB-Mannheim/tesseract/wiki
2. Install to: `C:\Program Files\Tesseract-OCR`
3. Add to PATH: `C:\Program Files\Tesseract-OCR`

#### 2. Install libmagic for Windows
**Option A (Recommended):**
```cmd
pip install python-magic-bin
```

#### 3. Install Visual C++ Redistributable (if needed)
Download from: https://aka.ms/vs/17/release/vc_redist.x64.exe

#### 4. Install Python Dependencies
```cmd
pip install -r requirements.txt
python -m spacy download en_core_web_sm
```

#### 5. Verify Installation
```cmd
python secure_purge.py --check-deps
```

### Windows-Specific Features
- Hardware detection via `wmic` and PowerShell
- Battery monitoring via Windows APIs
- Full GUI support with Windows theming
- Automatic fallback for deprecated commands

---

## Linux Setup

### Prerequisites
- Ubuntu 20.04+, Debian 11+, or equivalent
- Python 3.11+
- sudo access

### Installation Steps

#### Ubuntu/Debian
```bash
# Update package list
sudo apt update

# Install system dependencies
sudo apt install util-linux upower dmidecode tesseract-ocr libmagic1 libmagic-dev

# Install Python dependencies
pip install -r requirements.txt
python -m spacy download en_core_web_sm
```

#### RHEL/CentOS/Fedora
```bash
# Install system dependencies
sudo dnf install util-linux upower dmidecode tesseract libmagic libmagic-devel

# Install Python dependencies
pip install -r requirements.txt
python -m spacy download en_core_web_sm
```

#### Arch Linux
```bash
# Install system dependencies
sudo pacman -S util-linux upower dmidecode tesseract libmagic

# Install Python dependencies
pip install -r requirements.txt
python -m spacy download en_core_web_sm
```

#### Verify Installation
```bash
python secure_purge.py --check-deps
```

### Linux-Specific Features
- Disk detection via `lsblk`
- Hardware profiling via `lscpu` and `dmidecode`
- Battery monitoring via `upower`
- Permission-aware hardware detection
- Full GUI support with Qt theming

---

## Troubleshooting

### Common Issues

#### Python Package Errors
```bash
# Missing critical packages
pip install --upgrade PySide6 psutil scikit-learn cryptography

# Missing optional packages
pip install PyMuPDF python-magic spacy sentence-transformers
```

#### Platform-Specific Issues

**macOS:**
- **GUI not starting:** Install Xcode Command Line Tools
  ```bash
  xcode-select --install
  ```

**Windows:**
- **DLL errors:** Install Visual C++ Redistributable
- **Permission errors:** Run as Administrator for hardware detection

**Linux:**
- **Command not found:** Install missing system packages
  ```bash
  sudo apt install util-linux upower dmidecode
  ```
- **Permission denied:** Some features require root access
  ```bash
  sudo python secure_purge.py --check-deps
  ```

### Dependency Check Tool

Use the built-in dependency checker to diagnose issues:

```bash
# Check all dependencies
python secure_purge.py --check-deps

# Check specific components
python -c "import PySide6, psutil, sklearn; print('Core packages OK')"
```

---

## Feature Matrix

| Feature | Windows | macOS | Linux |
|---------|---------|-------|-------|
| GUI Interface | Yes | Yes | Yes |
| Secure File Deletion | Yes | Yes | Yes |
| Hardware Detection | Yes | Yes | Yes |
| Battery Monitoring | Yes | Yes | Yes |
| Disk Analysis | Yes | Yes | Yes |
| Content Analysis | Yes | Yes | Yes |
| PDF Reports | Yes | Yes | Yes |
| Digital Signatures | Yes | Yes | Yes |

---

## Support

If you encounter issues:

1. **Run dependency check:** `python secure_purge.py --check-deps`
2. **Check logs:** Look for error messages in the console output
3. **Platform-specific help:** Refer to the troubleshooting section above
4. **System requirements:** Ensure your system meets the minimum requirements

---

## Updates

To update VAULT:

```bash
# Update Python dependencies
pip install --upgrade -r requirements.txt

# Update spaCy model
python -m spacy download en_core_web_sm --upgrade

# Check for system dependency changes
python secure_purge.py --check-deps
```

---

*This guide covers VAULT v2.0+ with hybrid architecture support for Windows, macOS, and Linux.*
