"""Serial port management with thread safety."""
import serial
import threading
import time
from typing import Optional, Callable
from utils.constants import (
    SERIAL_BAUDRATE, SERIAL_TIMEOUT, SERIAL_PARITY,
    SERIAL_STOPBITS, SERIAL_BYTESIZE
)


class SerialManager:
    """
    Thread-safe serial port manager.

    Manages serial connection lifecycle and ensures thread-safe access
    to the serial port across multiple consumers.
    """

    def __init__(self):
        """Initialize the serial manager."""
        self._serial: Optional[serial.Serial] = None
        self._lock = threading.RLock()
        self._port: Optional[str] = None
        self._is_open = False
        self._command_in_progress = False
        self._exclusive_mode = False  # For long operations like firmware update

    @property
    def is_open(self) -> bool:
        """Check if serial port is open."""
        with self._lock:
            return self._is_open and self._serial is not None

    @property
    def port(self) -> Optional[str]:
        """Get current port name."""
        return self._port

    def open(self, port: str) -> None:
        """
        Open serial connection.

        Args:
            port: Serial port path (e.g., '/dev/cu.usbserial-1120')

        Raises:
            serial.SerialException: If port cannot be opened
        """
        with self._lock:
            if self._is_open:
                self.close()

            self._serial = serial.Serial(
                port=port,
                baudrate=SERIAL_BAUDRATE,
                bytesize=SERIAL_BYTESIZE,
                parity=SERIAL_PARITY,
                stopbits=SERIAL_STOPBITS,
                timeout=SERIAL_TIMEOUT
            )
            self._port = port
            self._is_open = True

    def close(self) -> None:
        """Close serial connection."""
        with self._lock:
            if self._serial:
                try:
                    self._serial.close()
                except Exception:
                    pass
                finally:
                    self._serial = None
                    self._is_open = False
                    self._port = None

    def write(self, data: bytes) -> int:
        """
        Write data to serial port (thread-safe).

        Args:
            data: Bytes to write

        Returns:
            Number of bytes written

        Raises:
            RuntimeError: If port is not open
        """
        with self._lock:
            if not self._is_open or not self._serial:
                raise RuntimeError("Serial port not open")
            return self._serial.write(data)

    def read(self, size: int = 1) -> bytes:
        """
        Read data from serial port (thread-safe).

        Args:
            size: Number of bytes to read

        Returns:
            Bytes read

        Raises:
            RuntimeError: If port is not open
        """
        with self._lock:
            if not self._is_open or not self._serial:
                raise RuntimeError("Serial port not open")
            return self._serial.read(size)

    def readline(self) -> bytes:
        """
        Read line from serial port (thread-safe).

        Returns:
            Bytes read until newline

        Raises:
            RuntimeError: If port is not open
        """
        with self._lock:
            if not self._is_open or not self._serial:
                raise RuntimeError("Serial port not open")
            return self._serial.readline()

    def reset_input_buffer(self) -> None:
        """Clear input buffer."""
        with self._lock:
            if self._is_open and self._serial:
                self._serial.reset_input_buffer()

    def reset_output_buffer(self) -> None:
        """Clear output buffer."""
        with self._lock:
            if self._is_open and self._serial:
                self._serial.reset_output_buffer()

    def set_timeout(self, timeout: Optional[float]) -> None:
        """Set read timeout."""
        with self._lock:
            if self._is_open and self._serial:
                self._serial.timeout = timeout

    def begin_command(self) -> None:
        """Mark that a command is in progress (for logging coordination)."""
        self._command_in_progress = True

    def end_command(self) -> None:
        """Mark that command has completed."""
        self._command_in_progress = False

    @property
    def command_in_progress(self) -> bool:
        """Check if a command is currently in progress."""
        return self._command_in_progress

    def enter_exclusive_mode(self) -> None:
        """Enter exclusive mode (blocks reader loops during long operations)."""
        self._exclusive_mode = True

    def exit_exclusive_mode(self) -> None:
        """Exit exclusive mode."""
        self._exclusive_mode = False

    @property
    def exclusive_mode(self) -> bool:
        """Check if exclusive mode is active."""
        return self._exclusive_mode

    def wait_for_device(self, timeout: float = 30.0, probe_interval: float = 0.4) -> bool:
        """
        Wait for device to respond to probe.

        Sends '?' and waits for 'Y' response.

        Args:
            timeout: Maximum time to wait in seconds
            probe_interval: Time between probes in seconds

        Returns:
            True if device responded, False if timeout
        """
        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                with self._lock:
                    if not self._is_open or not self._serial:
                        return False

                    self._serial.write(b'?')
                    response = self._serial.read(1)

                    if response == b'Y':
                        return True
            except Exception:
                pass

            time.sleep(probe_interval)

        return False
