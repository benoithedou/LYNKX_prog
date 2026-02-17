# Documentation Index

Quick navigation guide for the LYNKX Production Test Tool refactored codebase.

## 📚 Documentation Files

| File | Purpose | When to Read |
|------|---------|--------------|
| [README.md](README.md) | Project overview | First read |
| [QUICKSTART.md](QUICKSTART.md) | How to run the app | Getting started |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Detailed architecture | Understanding design |
| [COMPARISON.md](COMPARISON.md) | Before/After comparison | Understanding benefits |
| [TODO.md](TODO.md) | Features to implement | Contributing |
| [SUMMARY.md](SUMMARY.md) | Refactoring summary | Overview |
| **INDEX.md** | This file | Navigation |

## 🗂️ Code Organization

### Entry Point
- [main.py](main.py) - Application launcher

### User Interface (`ui/`)
- [main_window.py](ui/main_window.py) - Main window & header
- [test_tab.py](ui/test_tab.py) - Test tab (device configuration)
- [update_tab.py](ui/update_tab.py) - Update tab (firmware update)
- [terminal_tab.py](ui/terminal_tab.py) - Terminal tab (UART communication)
- [terminal_widget.py](ui/terminal_widget.py) - Reusable terminal widget

### Business Logic (`services/`)
- [state_manager.py](services/state_manager.py) - Centralized state management
- [test_workflow.py](services/test_workflow.py) - Test orchestration

### Hardware Communication (`core/`)
- [serial_manager.py](core/serial_manager.py) - Thread-safe serial port management
- [lynkx_protocol.py](core/lynkx_protocol.py) - LYNKX protocol implementation

### Device Control (`device/`)
- [config.py](device/config.py) - Device configuration management
- [bootloader.py](device/bootloader.py) - Bootloader operations

### Firmware Management (`firmware/`)
- [encryption.py](firmware/encryption.py) - AES encryption & CRC

### Utilities (`utils/`)
- [crc.py](utils/crc.py) - CRC calculations
- [constants.py](utils/constants.py) - Application constants

## 🎯 Quick Links by Task

### I want to...

#### Run the application
→ [QUICKSTART.md](QUICKSTART.md#running-the-application)

#### Understand the architecture
→ [ARCHITECTURE.md](ARCHITECTURE.md)

#### Add a new command
→ [ARCHITECTURE.md](ARCHITECTURE.md#adding-a-new-command)

#### Add a new test
→ [ARCHITECTURE.md](ARCHITECTURE.md#adding-a-new-test)

#### Understand UART management
→ [ARCHITECTURE.md](ARCHITECTURE.md#uart-management-between-tabs)

#### See what's not implemented yet
→ [TODO.md](TODO.md)

#### Compare with original code
→ [COMPARISON.md](COMPARISON.md)

#### Understand the refactoring benefits
→ [SUMMARY.md](SUMMARY.md#key-improvements)

## 🔍 Finding Specific Functionality

### Serial Communication
- Opening/closing port: [serial_manager.py](core/serial_manager.py#L30-L60)
- Thread-safe read/write: [serial_manager.py](core/serial_manager.py#L70-L100)
- Device detection: [serial_manager.py](core/serial_manager.py#L140-L170)

### Protocol
- Packet building: [lynkx_protocol.py](core/lynkx_protocol.py#L20-L40)
- Sending commands: [lynkx_protocol.py](core/lynkx_protocol.py#L45-L100)
- Battery reading: [lynkx_protocol.py](core/lynkx_protocol.py#L120-L140)

### Device Programming
- Memory erase: [bootloader.py](device/bootloader.py#L30-L65)
- Firmware writing: [bootloader.py](device/bootloader.py#L70-L130)
- Device configuration: [bootloader.py](device/bootloader.py#L170-L200)

### State Management
- Event system: [state_manager.py](services/state_manager.py#L30-L70)
- State updates: [state_manager.py](services/state_manager.py#L75-L170)

### UI Components
- Main window setup: [main_window.py](ui/main_window.py#L20-L90)
- Tab creation: [main_window.py](ui/main_window.py#L90-L130)
- Terminal widget: [terminal_widget.py](ui/terminal_widget.py#L10-L100)

## 📊 Code Statistics

| Category | Count |
|----------|-------|
| Python modules | 21 |
| Documentation files | 7 |
| Total lines of code | ~2,900 |
| Classes | 10 |
| Global variables | 0 |

## 🛠️ Development Workflow

### For New Features

1. **Design**: Read [ARCHITECTURE.md](ARCHITECTURE.md)
2. **Check TODO**: See [TODO.md](TODO.md)
3. **Implement**: Follow existing patterns
4. **Test**: Test module in isolation
5. **Integrate**: Add UI if needed
6. **Document**: Update relevant .md files

### For Bug Fixes

1. **Identify**: Which module is affected?
2. **Read code**: Understand the logic
3. **Fix**: Make minimal changes
4. **Test**: Verify fix works
5. **Check side effects**: Test related features

### For Understanding

1. **Start**: [README.md](README.md)
2. **Quick start**: [QUICKSTART.md](QUICKSTART.md)
3. **Deep dive**: [ARCHITECTURE.md](ARCHITECTURE.md)
4. **Compare**: [COMPARISON.md](COMPARISON.md)
5. **Read code**: Start with [main.py](main.py), follow imports

## 🎓 Learning Path

### Beginner (New to codebase)
1. Read README.md
2. Run the application (QUICKSTART.md)
3. Understand basic flow (main.py → main_window.py)
4. Read COMPARISON.md to see improvements

### Intermediate (Want to add features)
1. Read ARCHITECTURE.md
2. Study relevant service module
3. Check TODO.md for ideas
4. Implement small feature
5. Follow patterns from existing code

### Advanced (Want to refactor/optimize)
1. Understand entire architecture
2. Read all service/core modules
3. Identify improvement areas
4. Propose changes
5. Test thoroughly

## 🔗 External Resources

### Python Libraries Used
- **pyserial**: Serial port communication
- **tkinter**: GUI framework
- **pycryptodomex**: AES encryption
- **opencv-python**: QR code scanning (not yet implemented)
- **pyzbar**: Barcode decoding (not yet implemented)
- **sounddevice**: Audio testing (not yet implemented)
- **fpdf2**: PDF generation (not yet implemented)

### Documentation
- [PySerial docs](https://pyserial.readthedocs.io/)
- [Tkinter docs](https://docs.python.org/3/library/tkinter.html)
- [Python threading](https://docs.python.org/3/library/threading.html)

## 💡 Tips

### Reading the Code
- Start from main.py
- Follow dependency injection chain
- Use an IDE with "Go to definition"
- Look at constants.py for protocol definitions

### Debugging
- Check terminal output first
- Use proper exception messages
- Test modules independently
- Use print/log statements strategically

### Contributing
- Follow existing patterns
- Keep functions small (<50 lines)
- Use type hints
- Document complex logic
- No global variables!

## 📞 Getting Help

### Questions About...

**Architecture**: Read [ARCHITECTURE.md](ARCHITECTURE.md)
**Running the app**: Read [QUICKSTART.md](QUICKSTART.md)
**Missing features**: Check [TODO.md](TODO.md)
**Comparing with old code**: See [COMPARISON.md](COMPARISON.md)
**Implementation details**: Read the source code + comments

### File an Issue

If you find bugs or have suggestions:
1. Check if issue already exists
2. Provide clear description
3. Include error messages
4. Describe expected vs actual behavior

---

**Last Updated**: 2026-02-10
**Version**: 1.0 (Initial refactoring)
**Status**: Production-ready foundation, features in progress
