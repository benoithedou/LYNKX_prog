# Quick Start Guide

## Running the Application

### Option 1: Using the launcher script (macOS/Linux)

```bash
# From the LYNKX_prog directory
./run_tools.sh
```

### Option 2: Manual launch

```bash
# Activate virtual environment
source venv/bin/activate

# Navigate to tools directory
cd tools

# Run the application
python3 main.py
```

## First Time Setup

If you haven't set up the virtual environment yet:

```bash
# Remove old venv if needed
rm -rf venv

# Create new virtual environment
python3 -m venv venv

# Activate it
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# For macOS QR code scanning support
mkdir -p ~/lib
ln -s "$(brew --prefix zbar)/lib/libzbar.dylib" ~/lib/libzbar.dylib
```

## Basic Workflow

### Device Configuration & Testing

1. **Enter Device Information**
   - Enter operator name
   - Scan or enter QR code
   - Scan or enter barcode
   - Select hardware version (1.02 or 1.04)
   - Select COM port

2. **Select Firmware Files** (Test Tab)
   - Click "Test Firmware" to select test firmware (.bin)
   - Click "Prod Firmware" to select production firmware (.blf)
   - Or let it auto-select the most recent files

3. **Configure Device**
   - Click "Configure" button
   - Wait for device detection prompt
   - Plug in device with programming cable
   - Watch progress in terminal

4. **Run Tests**
   - After configuration, device will start test mode
   - Check boxes will be enabled as tests complete
   - Monitor RF measurements and battery level

### Firmware Update

1. **Select Firmware** (Update Tab)
   - Click "Update Firmware" to select new firmware
   - Click "Backup Firmware" to select backup firmware

2. **Update Device**
   - Click "Update Firmware" button
   - Wait for device detection
   - Plug in device
   - Wait for update to complete

3. **Encrypt Firmware** (optional)
   - Select unencrypted .bin file
   - Click "Encrypt Firmware"
   - Encrypted .blf file will be saved to firmwares/

### Terminal Communication

1. **Open Serial Connection** (Terminal Tab)
   - Select COM port in header
   - Click "Open Serial"
   - Terminal will show continuous output

2. **Send Commands**
   - Text commands: Type and press Enter
   - Hex commands: Format as `@01A2B3` (@ prefix)
   - Example: `@0305` to read battery

3. **Read Battery**
   - Click "Read Battery" button
   - Battery level will be displayed

4. **Terminal Logging**
   - Check "Log Terminal" checkbox
   - Browse to select log file location
   - All terminal output will be saved

## Troubleshooting

### Serial Port Not Found

- On macOS: `ls /dev/cu.usbserial-*`
- On Windows: Check Device Manager
- Click refresh button (↻) to update port list

### Device Not Detected

- Ensure device is powered off before plugging in
- Use the programming cable (back port)
- Check that bootloader is responding (`?` → `Y`)

### Import Errors

Make sure you're in the tools directory when running:
```bash
cd /Volumes/LYNKX_drive/rep/LYNKX_prog/tools
python3 main.py
```

### Permission Denied on macOS

Give permission to access serial ports:
```bash
sudo dseditgroup -o edit -a $USER -t user dialout
```

## Architecture Benefits

Compared to the original `production_test.py`:

✅ **No global variables** - All state managed through classes
✅ **Thread-safe UART** - Single SerialManager with proper locking
✅ **Modular design** - Easy to test and extend
✅ **Clean separation** - UI, business logic, and hardware control separated
✅ **Event-driven** - Components communicate via events
✅ **Better error handling** - Exceptions properly propagated and displayed

## Next Steps

- See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed architecture documentation
- Add custom tests in `services/test_workflow.py`
- Add new commands in `core/lynkx_protocol.py`
- Customize UI in `ui/` modules
