# Architecture Documentation

## Overview

This is a clean, modular refactoring of the LYNKX production test tool. The architecture follows clean separation of concerns with no global variables and proper dependency injection.

## Directory Structure

```
tools/
├── core/              # Low-level communication
│   ├── serial_manager.py      # Thread-safe serial port management
│   └── lynkx_protocol.py      # LYNKX protocol implementation
│
├── device/            # Device control
│   ├── config.py              # Device configuration (MAC, HW version)
│   └── bootloader.py          # Bootloader operations (erase, write, configure)
│
├── firmware/          # Firmware management
│   └── encryption.py          # AES encryption and CRC calculation
│
├── services/          # Business logic
│   ├── state_manager.py       # Centralized state management with events
│   └── test_workflow.py       # Test and update workflows
│
├── ui/                # User interface
│   ├── main_window.py         # Main window and header
│   ├── terminal_widget.py     # Reusable terminal widget
│   ├── test_tab.py            # Test tab
│   ├── update_tab.py          # Update tab
│   └── terminal_tab.py        # Terminal tab
│
├── utils/             # Utilities
│   ├── crc.py                 # CRC calculations
│   └── constants.py           # Application constants
│
└── main.py            # Entry point
```

## Key Design Principles

### 1. No Global Variables

All state is managed through class instances:
- `AppState`: Centralized application state
- `SerialManager`: Serial port state
- Each tab has its own state

### 2. Dependency Injection

Components receive dependencies in constructors:
```python
class TestWorkflow:
    def __init__(self, serial_manager: SerialManager, state: AppState):
        self._serial = serial_manager
        self._state = state
```

### 3. Event-Driven Communication

Components communicate via events instead of direct calls:
```python
# Subscribe to events
state.subscribe('battery_level', callback)

# Emit events
state.set_battery_level(85)
```

### 4. Thread Safety

- `SerialManager` uses `RLock` for thread-safe operations
- All UART operations go through the serial manager
- `command_in_progress` flag coordinates command/logging threads

### 5. Separation of Concerns

- **UI**: Only handles display and user interaction
- **Services**: Business logic and workflows
- **Core**: Low-level communication
- **Device**: Hardware control

## Component Interactions

### Serial Communication Flow

```
UI Component (e.g., TestTab)
    ↓
TestWorkflow
    ↓
Bootloader / LYNKXProtocol
    ↓
SerialManager
    ↓
pyserial
```

### State Management Flow

```
UI Component
    ↓ (update)
AppState
    ↓ (emit event)
All Subscribers
```

## Key Classes

### SerialManager

Thread-safe serial port management:
- Opens/closes connection
- Provides locked read/write operations
- Manages command_in_progress flag
- Handles device detection

### LYNKXProtocol

Implements LYNKX protocol:
- Builds packets with CRC
- Sends commands and receives responses
- High-level command methods (battery, logger, etc.)

### Bootloader

Bootloader operations:
- Memory erase (internal/external)
- Firmware writing with progress callbacks
- Device configuration
- Jump to application

### DeviceConfig

Device configuration:
- MAC address parsing
- Hardware version management
- Device ID validation
- Product reference

### TestWorkflow

Orchestrates device programming:
- Validates device IDs
- Coordinates bootloader operations
- Provides progress updates
- Handles errors gracefully

### AppState

Centralized state management:
- Stores all application state
- Event subscription/emission
- Thread-safe state access

## UART Management Between Tabs

### Problem in Original Code

The original code had 3 tabs sharing a global `ser` variable with manual locking and coordination issues.

### Solution

1. **Single SerialManager Instance**: Shared between all tabs via dependency injection
2. **Thread-Safe Operations**: All read/write through locked methods
3. **Command Coordination**: `command_in_progress` flag prevents reader conflicts
4. **Separate Terminals**: Each tab has its own `TerminalWidget` but shares the same serial manager

### Example Usage

```python
# In TestTab
def __init__(self, parent, state, serial_manager, protocol):
    self.serial_manager = serial_manager  # Injected
    self.protocol = protocol              # Injected

# In TerminalTab
def _send_command(self):
    if self.serial_manager.is_open:  # Check state
        success, response = self.protocol.send_packet(payload)
```

## Adding New Features

### Adding a New Command

1. Add command ID to `utils/constants.py`:
```python
class LYNKXCommand:
    NEW_COMMAND = 0x50
```

2. Add method to `LYNKXProtocol`:
```python
def new_command(self, param: int) -> bool:
    success, response = self.send_command(
        LYNKXCommand.NEW_COMMAND,
        payload=bytes([param])
    )
    return success
```

3. Call from UI:
```python
result = self.protocol.new_command(42)
```

### Adding a New Test

1. Add test name to `utils/constants.py`:
```python
TEST_NAMES = [..., 'NEW_TEST']
```

2. Add test logic to test workflow or create new service

3. Update UI to show test status

## Error Handling

All exceptions are handled at appropriate levels:
- Low-level: `BootloaderError`, `serial.SerialException`
- Mid-level: `TestWorkflowError`
- UI-level: `messagebox` dialogs

## Threading Model

- **Main Thread**: UI updates only
- **Worker Threads**: Long-running operations (configuration, encryption)
- **Reader Thread**: Continuous serial reading (in Terminal tab)

All threads are daemon threads and terminate when the application closes.

## Future Improvements

1. **Add unit tests** for core components
2. **Add file manager** implementation (currently in original only)
3. **Add RF measurement** services
4. **Add report generation** service
5. **Add QR code scanning** utility
6. **Improve error messages** with localization
