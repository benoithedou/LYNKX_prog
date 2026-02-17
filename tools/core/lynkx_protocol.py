"""LYNKX protocol implementation."""
import time
from typing import Optional, Tuple
from core.serial_manager import SerialManager
from utils.crc import calculate_crc8
from utils.constants import LYNKXCommand, LYNKXError


class LYNKXProtocol:
    """
    LYNKX protocol handler.

    Implements packet building, CRC calculation, and command/response logic.
    """

    def __init__(self, serial_manager: SerialManager):
        """
        Initialize protocol handler.

        Args:
            serial_manager: Serial manager instance
        """
        self._serial = serial_manager
        self._cmd_id_counter = 0

    def _next_cmd_id(self) -> int:
        """Get next command ID and increment counter."""
        cmd_id = self._cmd_id_counter
        self._cmd_id_counter = (self._cmd_id_counter + 1) % 256
        return cmd_id

    def build_packet(self, payload: bytes) -> bytes:
        """
        Build LYNKX packet with framing and CRC.

        Format: @ [length] [cmd_id] [payload] [crc8]

        Args:
            payload: Command payload

        Returns:
            Complete packet bytes
        """
        cmd_id = self._next_cmd_id()

        # Build frame: cmd_id + payload
        frame = bytes([cmd_id]) + payload

        # Calculate CRC8 on frame
        crc = calculate_crc8(frame)

        # Build packet: @ + length + frame + crc
        length = len(frame) + 1  # frame + crc
        packet = b'@' + bytes([length]) + frame + bytes([crc])

        return packet

    def send_packet(
        self,
        payload: bytes,
        response_timeout: float = 1.0,
        expected_len: Optional[int] = None,
        idle_timeout: float = 0.3
    ) -> Tuple[bool, bytes]:
        """
        Send packet and receive response.

        Args:
            payload: Command payload
            response_timeout: Maximum time to wait for response
            expected_len: Expected response length (None = read until idle)
            idle_timeout: Time of silence to consider response complete

        Returns:
            Tuple of (success, response_data)
        """
        if not self._serial.is_open:
            return False, b''

        try:
            # Mark command in progress
            self._serial.begin_command()

            # Wait a bit for reader loop to pause
            time.sleep(0.1)

            # Clear any pending data in buffer
            self._serial.reset_input_buffer()

            # Build and send packet
            packet = self.build_packet(payload)
            self._serial.write(packet)

            # Read response
            response = b''
            start_time = time.time()
            last_read_time = start_time

            while time.time() - start_time < response_timeout:
                data = self._serial.read(1)

                if data:
                    response += data
                    last_read_time = time.time()

                    # Check if we have expected length
                    if expected_len and len(response) >= expected_len:
                        break
                else:
                    # Check for idle timeout
                    if time.time() - last_read_time > idle_timeout:
                        break

            return True, response

        except Exception as e:
            print(f"Error sending packet: {e}")
            return False, b''

        finally:
            self._serial.end_command()

    def send_command(
        self,
        cmd_id: int,
        payload: bytes = b'',
        response_timeout: float = 1.0,
        expected_len: Optional[int] = None
    ) -> Tuple[bool, bytes]:
        """
        Send LYNKX command.

        Args:
            cmd_id: Command ID
            payload: Command payload
            response_timeout: Response timeout
            expected_len: Expected response length

        Returns:
            Tuple of (success, response_data)
        """
        command_payload = bytes([cmd_id]) + payload
        return self.send_packet(command_payload, response_timeout, expected_len)

    def read_battery_level(self) -> Optional[int]:
        """
        Read battery level.

        Returns:
            Battery level (0-100) or None if error
        """
        success, response = self.send_command(LYNKXCommand.GET_BAT_LEVEL, expected_len=4)

        if not success or len(response) < 4:
            return None

        # Response format: [counter] [status] [level] [crc8]
        status = response[1]
        level = response[2]

        if status == LYNKXError.OK:
            return level

        return None

    def read_firmware_version(self) -> Optional[str]:
        """
        Read firmware version.

        Returns:
            Version string (e.g., "2.10") or None if error
        """
        success, response = self.send_command(LYNKXCommand.GET_FIRM_VER, expected_len=5)

        if not success or len(response) < 5:
            return None

        # Response format: [counter] [status] [major] [minor] [crc8]
        status = response[1]
        major = response[2]
        minor = response[3]

        if status == LYNKXError.OK:
            return f"{major}.{minor:02d}"

        return None

    def get_log_count(self) -> Optional[int]:
        """
        Get number of logs on device.

        Returns:
            Log count or None if error
        """
        success, response = self.send_command(
            LYNKXCommand.FM_GET_LOG_COUNT,
            expected_len=5
        )

        if not success or len(response) < 5:
            return None

        # Response format: [counter] [status] [count_msb] [count_lsb] [crc8]
        status = response[1]

        if status == LYNKXError.OK:
            count = (response[2] << 8) | response[3]
            return count

        return None

    def start_logger(self, log_type: int = 0) -> bool:
        """
        Start data logger.

        Args:
            log_type: Type of log to start (0 = DEBUG)

        Returns:
            True if successful
        """
        success, response = self.send_command(
            LYNKXCommand.LOGGER_START,
            payload=bytes([log_type]),
            expected_len=3
        )

        if not success or len(response) < 3:
            return False

        # Response format: [counter] [status] [crc8]
        status = response[1]
        return status == LYNKXError.OK

    def stop_logger(self) -> bool:
        """
        Stop data logger.

        Returns:
            True if successful
        """
        success, response = self.send_command(
            LYNKXCommand.LOGGER_STOP,
            expected_len=3
        )

        if not success or len(response) < 3:
            return False

        status = response[1]
        return status == LYNKXError.OK

    def get_logger_status(self) -> Optional[dict]:
        """
        Get logger status.

        Returns:
            Dictionary with status info or None if error
        """
        success, response = self.send_command(
            LYNKXCommand.LOGGER_GET_STATUS,
            expected_len=4
        )

        if not success or len(response) < 4:
            return None

        # Response format: [counter] [status] [running] [crc8]
        status = response[1]
        running = response[2]

        if status == LYNKXError.OK:
            return {
                'running': running == 1,
                'status': status
            }

        return None
