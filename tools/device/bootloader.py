"""Bootloader operations for LYNKX devices."""
import math
from typing import Callable, Optional
from device.config import DeviceConfig
from core.serial_manager import SerialManager
from utils.constants import MEMORY_INT_BASE, MEMORY_EXT_BASE, MEMORY_EXT_BACKUP


class BootloaderError(Exception):
    """Bootloader operation error."""
    pass


class Bootloader:
    """
    LYNKX bootloader interface.

    Handles low-level bootloader operations like memory erase,
    firmware writing, and device configuration.
    """

    def __init__(self, serial_manager: SerialManager):
        """
        Initialize bootloader.

        Args:
            serial_manager: Serial manager instance
        """
        self._serial = serial_manager

    def _send_command(self, command: bytes) -> bytes:
        """
        Send bootloader command and get acknowledgment.

        Args:
            command: Command byte(s)

        Returns:
            Response byte

        Raises:
            BootloaderError: If command fails
        """
        if not self._serial.is_open:
            raise BootloaderError("Serial port not open")

        self._serial.write(command)
        response = self._serial.read(1)

        if not response:
            raise BootloaderError(f"No response to command {command.hex()}")

        return response

    def erase_internal_memory(self) -> None:
        """
        Erase internal flash memory.

        Raises:
            BootloaderError: If erase fails
        """
        self._serial.reset_input_buffer()

        # Send erase command
        response = self._send_command(b'E')
        if response != b'E':
            raise BootloaderError(f"Erase command not acknowledged: {response.hex()}")

        # Wait for erase completion
        response = self._serial.read(1)
        if response != b'Y':
            raise BootloaderError(f"Erase failed: {response.hex()}")

    def erase_external_memory(self, page_count: int = 0xFFFF) -> None:
        """
        Erase external flash memory.

        Args:
            page_count: Number of pages to erase (0xFFFF = mass erase)

        Raises:
            BootloaderError: If erase fails
        """
        # Send erase command
        response = self._send_command(b'F')
        if response != b'F':
            raise BootloaderError(f"Erase command not acknowledged: {response.hex()}")

        # Send page count (MSB first)
        self._serial.write(bytes([(page_count >> 8) & 0xFF]))
        self._serial.write(bytes([page_count & 0xFF]))

        # Wait for ACK
        self._serial.read(1)

    def write_internal_memory(
        self,
        data: bytes,
        address: int = MEMORY_INT_BASE,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> None:
        """
        Write data to internal memory.

        Args:
            data: Data to write (will be padded to 256-byte pages)
            address: Start address
            progress_callback: Optional callback(current_page, total_pages)

        Raises:
            BootloaderError: If write fails
        """
        # Pad data to 256-byte pages
        data_list = list(data)
        page_size = 256
        orphan_bytes = len(data_list) % page_size

        if orphan_bytes != 0:
            padding = [0] * (page_size - orphan_bytes)
            data_list.extend(padding)

        page_count = len(data_list) // page_size

        # Send write command
        response = self._send_command(b'W')
        if response != b'W':
            raise BootloaderError(f"Write command not acknowledged: {response.hex()}")

        # Send address (MSB first, 4 bytes)
        for shift in [24, 16, 8, 0]:
            self._serial.write(bytes([(address >> shift) & 0xFF]))
        self._serial.read(1)  # Wait for ACK

        # Send page count (MSB first, 4 bytes)
        for shift in [24, 16, 8, 0]:
            self._serial.write(bytes([(page_count >> shift) & 0xFF]))
        self._serial.read(1)  # Wait for ACK

        # Send data pages
        for i in range(page_count):
            page_data = data_list[i * page_size:(i + 1) * page_size]
            self._serial.write(bytes(page_data))
            self._serial.read(1)  # Wait for ACK after each page

            if progress_callback:
                progress_callback(i + 1, page_count)

        # Final ACK
        self._serial.read(1)

    def write_external_memory(
        self,
        data: bytes,
        address: int = MEMORY_EXT_BASE,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> None:
        """
        Write data to external memory.

        Args:
            data: Data to write (will be padded to 256-byte pages)
            address: Start address
            progress_callback: Optional callback(current_page, total_pages)

        Raises:
            BootloaderError: If write fails
        """
        # Pad data to 256-byte pages
        data_list = list(data)
        page_size = 256
        orphan_bytes = len(data_list) % page_size

        if orphan_bytes != 0:
            padding = [0] * (page_size - orphan_bytes)
            data_list.extend(padding)

        page_count = len(data_list) // page_size

        # Send write command
        response = self._send_command(b'X')
        if response != b'X':
            raise BootloaderError(f"Write command not acknowledged: {response.hex()}")

        # Send address (MSB first, 4 bytes)
        for shift in [24, 16, 8, 0]:
            self._serial.write(bytes([(address >> shift) & 0xFF]))
        self._serial.read(1)  # Wait for ACK

        # Send page count (MSB first, 4 bytes)
        for shift in [24, 16, 8, 0]:
            self._serial.write(bytes([(page_count >> shift) & 0xFF]))
        self._serial.read(1)  # Wait for ACK

        # Send data pages
        for i in range(page_count):
            page_data = data_list[i * page_size:(i + 1) * page_size]
            self._serial.write(bytes(page_data))
            self._serial.read(1)  # Wait for ACK after each page

            if progress_callback:
                progress_callback(i + 1, page_count)

        # Final ACK
        self._serial.read(1)

    def configure_device(self, config: DeviceConfig) -> None:
        """
        Configure device with MAC address and hardware version.

        Args:
            config: Device configuration

        Raises:
            BootloaderError: If configuration fails
        """
        # Send configure command
        response = self._send_command(b'C')
        if response != b'C':
            raise BootloaderError(f"Configure command not acknowledged: {response.hex()}")

        # Send product reference (16 bytes)
        self._serial.write(config.product_reference)
        self._serial.read(1)  # Wait for ACK

        # Send hardware version (2 bytes)
        self._serial.write(bytes([config.hw_major]))
        self._serial.write(bytes([config.hw_minor]))
        self._serial.read(1)  # Wait for ACK

        # Send MAC address (8 bytes)
        for byte in config.mac_bytes:
            self._serial.write(bytes([byte]))
        self._serial.read(1)  # Wait for ACK

    def jump_to_application(self) -> None:
        """
        Jump to main application.

        Raises:
            BootloaderError: If jump fails
        """
        response = self._send_command(b'G')
        if response != b'G':
            raise BootloaderError(f"Jump command not acknowledged: {response.hex()}")

    def enter_shipping_mode(self) -> None:
        """
        Enter shipping mode (low power).

        Raises:
            BootloaderError: If command fails
        """
        response = self._send_command(b'H')
        if response != b'H':
            raise BootloaderError(f"Shipping mode command not acknowledged: {response.hex()}")
