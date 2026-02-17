# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Python-based firmware programming and production testing toolset for LYNKX+ hardware devices (beacon products). The project includes tools for firmware encryption, device programming, and comprehensive production testing with automated report generation.

## Environment Setup

### Virtual Environment
The project uses a Python virtual environment. Setup commands:

```bash
# Remove existing venv if needed
rm -rf venv

# Create new virtual environment
/usr/local/bin/python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### macOS-Specific Setup
For QR code scanning functionality on macOS:

```bash
# Verify tkinter is working
python3 -m tkinter

# Link zbar library
mkdir -p ~/lib
ln -s "$(brew --prefix zbar)/lib/libzbar.dylib" ~/lib/libzbar.dylib
```

## Running the Tools

### Production Test GUI
```bash
# Activate virtual environment first
source venv/bin/activate

# Run production test application
python3 production_test.py
```

### Firmware Encryption
```bash
python3 Encrypt_LYNKX_firmware.py
```

This script:
- Reads unencrypted firmware from `../LYNKX_firmware/output/LYNKX_firmware_HARD_14_Debug.bin`
- Encrypts using AES-CBC (256-byte blocks)
- Computes CRC32 checksums for both clear and encrypted versions
- Outputs encrypted firmware to `firmwares/` directory with naming format:
  `LYNKXF{hw_ver}_{timestamp}_{major}.{minor}_{crc_clear}_{crc_encrypted}.blf`

### Firmware Programming
```bash
python3 LYNKX_firmware_update.py
```

This script programs devices via serial bootloader. Key configuration at top of file:
- `COM_PORT`: Serial port (macOS: `/dev/cu.usbserial-*`, Windows: `COMx`)
- Flags control which operations to perform (erase, program, configure, etc.)

## Architecture

### Serial Bootloader Protocol
All three scripts communicate with LYNKX+ devices using a custom serial protocol (921600 baud, 8E1):

**Key Commands:**
- `?` - Probe for device presence (response: `Y`)
- `E` - Erase internal flash
- `F` - Erase external flash
- `W` - Write to internal memory (0x08006000)
- `X` - Write to external memory
- `C` - Configure device (ProductReference, MAC, hardware version)
- `U` - Update firmware from external to internal flash
- `G` - Jump to main application
- `H` - Enter shipping mode

**Write Protocol:**
1. Send command byte, wait for echo
2. Send 4-byte address (MSB first)
3. Send 4-byte page count
4. Send data in 256-byte pages
5. Wait for ACK after each page

### Firmware Encryption System
The encryption system (`Encrypt_LYNKX_firmware.py`) implements:

- **Algorithm**: AES-CBC with fixed IV and key (hardcoded)
- **Block Size**: 256 bytes (files padded to multiple of 256)
- **Version Extraction**: Reads firmware version from bytes 0x49-0x4B of second block
- **Integrity**: CRC32 validation using custom polynomial (0x04C11DB7) with byte-order reversal
- **Output Format**: `.blf` files with embedded version and checksum information in filename

### Production Test Application
`production_test.py` is a comprehensive tkinter-based GUI (~3200 lines) that performs:

**Device Identification:**
- QR code scanning (using pyzbar + opencv)
- Barcode scanning
- MAC address validation (format: `8C:1F:64:EE:xx:xx:xx:xx`)
- Device type detection (LYNKX+ vs LYNKX+ SUMMIT)

**Hardware Testing:**
- Battery level measurement
- Audio output testing (using sounddevice)
- RF testing for LoRa and BLE (using TinySA spectrum analyzer)
- Environmental pressure sensor validation
- Firmware version verification

**Test Results:**
- PDF report generation (using fpdf2)
- Reports saved to `Reports/Device_ID_{device_id}_{status}.pdf`
- Terminal logging with UTF-8 emoji support

**Key Classes/Functions:**
- `LYNKXConfig`: Device configuration (MAC, hardware version, product reference)
- `TerminalApp`: Terminal window management
- `checkMacAddress()`: Validates QR/barcode consistency
- `measure_freq_power_zoom()`: RF spectrum measurement with TinySA
- `record_audio()`: Audio capture and power calculation
- Threading for non-blocking serial communication and UI updates

### Hardware Version Support
- **v1.2**: Standard LYNKX+ hardware
- **v1.4**: Current production hardware
- Hardware version stored in device configuration and firmware filename

### Device Types
- **LYNKX+**: Standard beacon (type 1)
- **LYNKX+ SUMMIT**: Summit variant (type 0)

## File Structure

- `production_test.py` - Main production test GUI application
- `LYNKX_firmware_update.py` - Command-line firmware programmer
- `Encrypt_LYNKX_firmware.py` - Firmware encryption utility
- `firmwares/` - Encrypted (.blf) and unencrypted (.bin) firmware files
- `Reports/` - Production test PDF reports
- `venv/` - Python virtual environment
- `requirements.txt` - Python dependencies

## Important Notes

### Serial Port Configuration
The serial port path must be updated before running:
- macOS: Find port with `ls /dev/cu.usbserial-*`
- Windows: Check Device Manager for `COMx`

### Firmware Paths
Update firmware paths in scripts before encryption/programming:
- `Encrypt_LYNKX_firmware.py`: Lines 123-124
- `LYNKX_firmware_update.py`: Lines 73-79

### Testing Equipment Requirements
Production testing requires:
- USB camera for QR/barcode scanning
- Audio equipment for microphone testing
- TinySA spectrum analyzer for RF measurements
- Pressure chamber for sensor testing

### Memory Map
- **Internal Flash Base**: 0x08006000 (application start)
- **External Flash Base**: 0x00000000 (firmware storage)
- **External Flash Backup**: 0x001C0000 (backup firmware)
