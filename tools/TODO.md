# TODO - Features to Implement

This document lists features from the original `production_test.py` that haven't been implemented yet in the refactored version.

## High Priority

### 1. QR Code Scanning 🎥
**Location**: `ui/test_tab.py` or create `utils/qr_scanner.py`

**Original Code**: Lines 309-351 in `production_test.py`

**Implementation**:
- Use OpenCV and pyzbar
- Create scanner button in Test Tab
- Implement camera capture and QR decode
- Update device ID fields

```python
# Example structure
class QRScanner:
    def scan(self) -> Optional[str]:
        # Open camera, decode QR code
        pass
```

### 2. Test Application Thread 🧪
**Location**: `services/test_runner.py` (new file)

**Original Code**: Lines 1655-1776 in `production_test.py`

**Purpose**: Monitors serial output during testing and auto-checks test boxes

**Implementation**:
- Create TestRunner class
- Parse device messages (LED_GREEN1, BC State OK, etc.)
- Update test checkboxes via state manager
- Extract and display pressure, RF measurements

```python
class TestRunner:
    def __init__(self, serial_manager, state):
        pass

    def start_monitoring(self):
        # Read serial line by line
        # Parse messages
        # Update state
        pass
```

### 3. File Manager 📁
**Location**: `services/file_manager.py` (new file) + UI in Terminal Tab

**Original Code**: Lines 1777-2000+ in `production_test.py`

**Features**:
- List logs on device
- Download log files with progress
- Delete logs
- Erase all logs
- File info display

**Already Implemented**:
- Protocol commands in `LYNKXProtocol` (get_log_count, etc.)

**Need to Add**:
- Complete protocol methods (get_log_list_page, read_log_chunk, delete_log)
- UI widgets in terminal_tab.py
- File download logic with CRC validation

### 4. Report Generation 📄
**Location**: `services/report_generator.py` (new file)

**Original Code**: Lines 2001-2200+ in `production_test.py`

**Implementation**:
- Use fpdf2 library
- Generate PDF with device info, test results, RF measurements
- Save to Reports/ directory with device ID in filename
- Include operator name, timestamp, pass/fail status

## Medium Priority

### 5. RF Measurements 📡
**Location**: `services/rf_measurement.py` (new file)

**Original Code**: Lines 1371-1550 in `production_test.py`

**Features**:
- TinySA spectrum analyzer integration
- LoRa frequency/power measurement
- BLE frequency/power measurement
- Bandwidth calculations

**Implementation**:
```python
class RFMeasurement:
    def __init__(self):
        self.tinysa_port = self._find_tinysa()

    def measure_lora(self) -> Tuple[float, float]:
        # Measure LoRa freq and power
        pass

    def measure_ble(self) -> Tuple[float, float]:
        # Measure BLE freq and power
        pass
```

### 6. Audio Testing 🎵
**Location**: `services/audio_test.py` (new file)

**Original Code**: Lines 1331-1370 in `production_test.py`

**Features**:
- Microphone warmup
- Audio recording (sounddevice)
- Power calculation
- Validation (3 samples)

### 7. Pressure Testing 🌡️
**Location**: `services/pressure_test.py` (new file)

**Original Code**: Lines 1271-1330 in `production_test.py`

**Features**:
- Environmental characteristics calculation
- Pressure status checking
- Altitude-based validation

## Low Priority

### 8. Logger Control UI 🎛️
**Location**: `ui/terminal_tab.py` (expand existing)

**Status**: Protocol methods already implemented in `LYNKXProtocol`

**Add to UI**:
- Start/Stop logger buttons
- Logger status display
- Log type selection

### 9. File Manager Debug Info 🔍
**Original Code**: Lines 2300+ in `production_test.py`

**Features**:
- Debug info button
- Display FM internal state
- Error diagnostics

### 10. Advanced Terminal Features 💻
**Location**: `ui/terminal_widget.py`

**Features**:
- UTF-8 emoji decoding
- Better text formatting
- Color coding for errors/success
- Message filtering

## Completed ✅

- ✅ Serial port management (SerialManager)
- ✅ LYNKX protocol (packet building, CRC, commands)
- ✅ Bootloader operations (erase, write, configure)
- ✅ Device configuration (MAC address, HW version)
- ✅ Firmware encryption
- ✅ Test workflow orchestration
- ✅ State management with events
- ✅ Basic UI (tabs, terminal, buttons)
- ✅ Battery reading
- ✅ Firmware version reading
- ✅ Threading model
- ✅ Error handling

## Implementation Notes

### Adding Features

1. **Create service module** in `services/`
2. **Inject dependencies** (serial_manager, state, etc.)
3. **Use state manager** for data sharing
4. **Emit events** for UI updates
5. **Add UI components** in appropriate tab
6. **Update ARCHITECTURE.md** with new components

### Example: Adding QR Scanner

```python
# 1. Create utils/qr_scanner.py
class QRScanner:
    def scan(self, callback):
        # Implementation
        pass

# 2. Add to test_tab.py
from ..utils.qr_scanner import QRScanner

class TestTab:
    def __init__(self, ...):
        self.qr_scanner = QRScanner()

    def _scan_qr(self):
        result = self.qr_scanner.scan()
        if result:
            self.qr_var.set(result)

# 3. Add button to UI
Button(self.frame, text="📷 Scan", command=self._scan_qr)
```

### Testing Strategy

For each new feature:
1. Test independently with a simple script
2. Integrate into main application
3. Test with real hardware
4. Document in ARCHITECTURE.md

## Priority Order

1. **Test Application Thread** - Critical for automatic testing
2. **QR Code Scanning** - Improves user workflow
3. **Report Generation** - Required for production
4. **RF Measurements** - Essential for complete testing
5. **File Manager** - Useful for debugging
6. Everything else as needed

## Estimated Effort

- Test Application Thread: 4-6 hours
- QR Code Scanning: 2-3 hours
- Report Generation: 3-4 hours
- RF Measurements: 6-8 hours (complex)
- File Manager: 4-6 hours
- Audio Testing: 2-3 hours
- Pressure Testing: 2-3 hours

**Total**: ~25-35 hours for full feature parity
