"""Test workflow orchestration."""
import time
import threading
from typing import Optional, Callable
from services.state_manager import AppState
from core.serial_manager import SerialManager
from device.bootloader import Bootloader, BootloaderError
from utils.constants import MEMORY_EXT_BACKUP, BEACON_SETTINGS_ADDRESS, USER_SETTINGS_ADDRESS
from device.config import DeviceConfig, BeaconSettings, UserSettings
from firmware.encryption import FirmwareEncryption


class TestWorkflowError(Exception):
    """Test workflow error."""
    pass


class TestWorkflow:
    """
    Orchestrates full device configuration and testing workflow.

    This class manages the complete device programming and test sequence,
    coordinating between bootloader, firmware, and device configuration.
    """

    def __init__(
        self,
        serial_manager: SerialManager,
        state: AppState,
        progress_callback: Optional[Callable[[str], None]] = None
    ):
        """
        Initialize test workflow.

        Args:
            serial_manager: Serial manager instance
            state: Application state
            progress_callback: Optional callback for progress updates
        """
        self._serial = serial_manager
        self._state = state
        self._bootloader = Bootloader(serial_manager)
        self._progress_callback = progress_callback
        self._stop_flag = False

    def _log(self, message: str) -> None:
        """Log message via progress callback."""
        if self._progress_callback:
            self._progress_callback(message)

    def validate_device_ids(self) -> DeviceConfig:
        """
        Validate device IDs and create configuration.

        Returns:
            Device configuration

        Raises:
            TestWorkflowError: If validation fails
        """
        qr_code = self._state.device_id_qr
        bar_code = self._state.device_id_bar

        # Validate IDs match
        device_type = DeviceConfig.validate_device_ids(qr_code, bar_code)
        if device_type is None:
            raise TestWorkflowError("Device IDs don't match or are invalid")

        # Extract device ID from QR code
        device_id = qr_code.split('=')[1] if '=' in qr_code else bar_code

        # Build MAC address
        mac_address = DeviceConfig.build_mac_address(device_id)

        # Update state
        self._state.set_device_config(device_type, mac_address)

        # Create configuration
        config = DeviceConfig(
            mac_address=mac_address,
            device_type=device_type,
            hardware_version=self._state.hardware_version
        )

        self._log(f"✓ Device configuration: {config}")
        return config

    def run_full_configuration(
        self,
        test_firmware_path: str,
        backup_firmware_path: str
    ) -> bool:
        """
        Run complete device configuration workflow.

        This includes:
        1. Device ID validation
        2. Serial connection
        3. Device detection
        4. Memory erase
        5. Firmware programming
        6. Device configuration
        7. Jump to application

        Args:
            test_firmware_path: Path to test firmware
            backup_firmware_path: Path to backup firmware

        Returns:
            True if successful

        Raises:
            TestWorkflowError: If any step fails
        """
        try:
            # Enter exclusive mode to block reader loops
            self._serial.enter_exclusive_mode()

            # Step 1: Validate device IDs
            self._log("📋 Validating device IDs...")
            config = self.validate_device_ids()

            # Step 2: Open serial port
            if not self._serial.is_open:
                self._log("🔌 Opening serial port...")
                port = self._state.serial_port
                if not port:
                    raise TestWorkflowError("No serial port selected")
                self._serial.open(port)
                self._state.set_serial_connected(True, port)

            # Step 3: Wait for device
            self._log("⏳ Waiting for device (plug in with cable)...")
            if not self._serial.wait_for_device(timeout=30.0):
                raise TestWorkflowError("Device not detected (timeout)")

            self._log("✅ Device connected")

            # Wait for device to stabilize (same as original)
            time.sleep(2.0)

            # Set longer timeout for operations
            self._serial.set_timeout(10.0)

            # Step 4: Erase internal memory
            self._log("🗑️  Erasing internal memory...")
            self._bootloader.erase_internal_memory()
            self._log("✓ Internal memory erased")

            # Step 5: Erase external memory
            self._log("🗑️  Erasing external memory...")
            self._bootloader.erase_external_memory()
            self._log("✓ External memory erased")

            # Step 6: Write test firmware to internal memory
            self._log(f"📝 Writing test firmware: {test_firmware_path}")
            test_firmware_data = FirmwareEncryption.read_firmware(test_firmware_path)

            def progress_callback(current, total):
                if current % 10 == 0 or current == total:
                    self._log(f"   Writing page {current}/{total}")

            self._bootloader.write_internal_memory(
                test_firmware_data,
                progress_callback=progress_callback
            )
            self._log("✓ Test firmware written")

            # Step 7: Write backup firmware to external memory
            self._log(f"📝 Writing backup firmware: {backup_firmware_path}")
            backup_firmware_data = FirmwareEncryption.read_firmware(backup_firmware_path)

            self._bootloader.write_external_memory(
                backup_firmware_data,
                address=MEMORY_EXT_BACKUP,
                progress_callback=progress_callback
            )
            self._log("✓ Backup firmware written")

            # Step 8: Configure device
            self._log("⚙️  Configuring device...")
            self._bootloader.configure_device(config)
            self._log("✓ Device configured")

            # Step 9: Jump to main application
            self._log("🚀 Jumping to main application...")
            self._bootloader.jump_to_application()
            self._log("✓ Device started")

            self._log("✅ Configuration complete! Device is ready for testing.")
            return True

        except BootloaderError as e:
            self._log(f"❌ Bootloader error: {str(e)}")
            raise TestWorkflowError(f"Bootloader operation failed: {str(e)}")

        except Exception as e:
            self._log(f"❌ Unexpected error: {str(e)}")
            raise TestWorkflowError(f"Configuration failed: {str(e)}")

        finally:
            # Always exit exclusive mode
            self._serial.exit_exclusive_mode()

    def run_firmware_update(
        self,
        firmware_path: str,
        backup_firmware_path: Optional[str] = None,
        write_config: bool = True,
        beacon_settings: Optional[BeaconSettings] = None,
        user_settings: Optional[UserSettings] = None
    ) -> bool:
        """
        Run firmware update workflow.

        Similar to full configuration but assumes device is already configured.

        Args:
            firmware_path: Path to firmware
            backup_firmware_path: Path to backup firmware (optional)
            write_config: Whether to write device configuration
            beacon_settings: Beacon settings to write (None to skip)
            user_settings: User settings to write (None to skip)

        Returns:
            True if successful
        """
        try:
            # Enter exclusive mode to block reader loops
            self._serial.enter_exclusive_mode()

            # Validate device IDs only if config write is needed
            config = None
            if write_config:
                self._log("📋 Validating device IDs...")
                config = self.validate_device_ids()
            else:
                self._log("⏭️  Device ID validation skipped (config disabled)")

            # Open serial if needed
            if not self._serial.is_open:
                self._log("🔌 Opening serial port...")
                port = self._state.serial_port
                if not port:
                    raise TestWorkflowError("No serial port selected")
                self._serial.open(port)
                self._state.set_serial_connected(True, port)

            # Wait for device
            self._log("⏳ Waiting for device...")
            if not self._serial.wait_for_device(timeout=30.0):
                raise TestWorkflowError("Device not detected")

            self._log("✅ Device connected")

            # Wait for device to stabilize (same as original)
            time.sleep(2.0)

            # Set timeout
            self._serial.set_timeout(10.0)

            # Erase internal memory
            self._log("🗑️  Erasing internal memory...")
            self._bootloader.erase_internal_memory()

            # Write firmware
            self._log(f"📝 Writing firmware: {firmware_path}")
            firmware_data = FirmwareEncryption.read_firmware(firmware_path)

            def progress_callback(current, total):
                if current % 10 == 0 or current == total:
                    self._log(f"   Page {current}/{total}")

            self._bootloader.write_internal_memory(
                firmware_data,
                progress_callback=progress_callback
            )

            # Erase and write backup only if path is provided (after internal write, same order as original)
            if backup_firmware_path:
                self._log("🗑️  Erasing external memory...")
                self._bootloader.erase_external_memory()
                self._log(f"📝 Writing backup: {backup_firmware_path}")
                backup_data = FirmwareEncryption.read_firmware(backup_firmware_path)
                self._bootloader.write_external_memory(
                    backup_data,
                    address=MEMORY_EXT_BACKUP,
                    progress_callback=progress_callback
                )
                self._log("✓ Backup written")
            else:
                self._log("⏭️  Backup skipped (disabled)")

            # Write settings to external flash
            if beacon_settings:
                self._log("⚙️  Writing beacon settings...")
                self._bootloader.write_external_memory(
                    beacon_settings.to_bytes(),
                    address=BEACON_SETTINGS_ADDRESS
                )
                self._log("✓ Beacon settings written")
            if user_settings:
                self._log("⚙️  Writing user settings...")
                self._bootloader.write_external_memory(
                    user_settings.to_bytes(),
                    address=USER_SETTINGS_ADDRESS
                )
                self._log("✓ User settings written")

            # Configure device (only if write_config is enabled)
            if write_config:
                self._log("⚙️  Configuring device...")
                self._bootloader.configure_device(config)
            else:
                self._log("⏭️  Config skipped (disabled)")

            self._log("🚀 Jumping to application...")
            self._bootloader.jump_to_application()

            self._log("✅ Update complete!")
            return True

        except Exception as e:
            self._log(f"❌ Update failed: {str(e)}")
            return False

        finally:
            # Always exit exclusive mode
            self._serial.exit_exclusive_mode()

    def stop(self) -> None:
        """Stop workflow (for cancellation)."""
        self._stop_flag = True
