"""LYNKX protocol implementation."""
import struct
import time
from typing import Optional, Tuple, List, Callable
from core.serial_manager import SerialManager
from utils.crc import calculate_crc8
from utils.constants import LYNKXCommand, LYNKXError, FM_LIST_PAGE_MAX


class LYNKXProtocol:
    """
    LYNKX protocol handler.

    Implements packet building, CRC calculation, and command/response logic.

    Response format from device (UART):
        [0]       groupe echo (counter)
        [1..N-1]  payload (specific to command)
        [N]       CRC-8

    All multi-byte fields in responses are BIG-ENDIAN.

    Set debug=True or assign a debug_callback to get detailed logging.
    """

    def __init__(self, serial_manager: SerialManager, debug: bool = False):
        self._serial = serial_manager
        self._cmd_id_counter = 0
        self.debug = debug
        self.debug_callback: Optional[Callable[[str], None]] = None

    def _dbg(self, msg: str) -> None:
        """Log a debug message if debug is enabled."""
        if not self.debug:
            return
        if self.debug_callback:
            self.debug_callback(msg)
        else:
            print(f"[PROTO] {msg}")

    def _next_cmd_id(self) -> int:
        """Get next command ID and increment counter."""
        cmd_id = self._cmd_id_counter
        self._cmd_id_counter = (self._cmd_id_counter + 1) % 256
        return cmd_id

    def build_packet(self, payload: bytes) -> bytes:
        """
        Build LYNKX packet with framing and CRC.

        Format: @ [length] [cmd_id] [payload] [crc8]
        """
        cmd_id = self._next_cmd_id()
        frame = bytes([cmd_id]) + payload
        crc = calculate_crc8(frame)
        length = len(frame) + 1  # frame + crc
        packet = b'@' + bytes([length]) + frame + bytes([crc])
        return packet

    def send_packet(
        self,
        payload: bytes,
        response_timeout: float = 1.0,
        expected_len: Optional[int] = None,
        idle_timeout: float = 0.3,
        pre_delay: float = 0.1
    ) -> Tuple[bool, bytes]:
        """
        Send packet and receive response.

        Args:
            payload: Packet payload
            response_timeout: Max wait time for full response
            expected_len: Expected response length (breaks early when reached)
            idle_timeout: Max silence after last byte before giving up
            pre_delay: Delay before sending (device settling time)

        Returns:
            Tuple of (success, response_data)
        """
        if not self._serial.is_open:
            self._dbg("send_packet: port serie non ouvert")
            return False, b''

        try:
            self._serial.begin_command()
            if pre_delay > 0:
                time.sleep(pre_delay)
            self._serial.reset_input_buffer()

            packet = self.build_packet(payload)
            self._dbg(f"TX: {packet.hex(' ')}")
            self._serial.write(packet)

            response = b''
            start_time = time.time()
            last_read_time = start_time

            while time.time() - start_time < response_timeout:
                # Read in bulk when we know how many bytes we expect
                remaining = expected_len - len(response) if expected_len else 1
                read_size = max(1, min(remaining, 256))
                data = self._serial.read(read_size)

                if data:
                    response += data
                    last_read_time = time.time()

                    if expected_len and len(response) >= expected_len:
                        break
                else:
                    if response and time.time() - last_read_time > idle_timeout:
                        break

            elapsed = time.time() - start_time
            self._dbg(f"RX: {response.hex(' ') if response else '(vide)'} "
                       f"({len(response)}B, {elapsed:.3f}s)")
            return True, response

        except Exception as e:
            self._dbg(f"send_packet exception: {e}")
            return False, b''

        finally:
            self._serial.end_command()

    def send_command(
        self,
        cmd_id: int,
        payload: bytes = b'',
        response_timeout: float = 1.0,
        expected_len: Optional[int] = None,
        idle_timeout: float = 0.3,
        pre_delay: float = 0.1
    ) -> Tuple[bool, bytes]:
        """Send LYNKX command."""
        command_payload = bytes([cmd_id]) + payload
        return self.send_packet(
            command_payload, response_timeout, expected_len,
            idle_timeout=idle_timeout, pre_delay=pre_delay
        )

    def _check_response(self, response: bytes, min_len: int, cmd_name: str) -> Optional[str]:
        """
        Validate response. Returns None if OK, error string if not.
        Also logs debug info.
        """
        if len(response) == 0:
            msg = f"{cmd_name}: reponse vide (timeout)"
            self._dbg(msg)
            return msg
        if len(response) < min_len:
            msg = f"{cmd_name}: reponse trop courte ({len(response)}B, min={min_len}) data={response.hex(' ')}"
            self._dbg(msg)
            return msg
        crc_calc = calculate_crc8(response[:-1])
        crc_recv = response[-1]
        if crc_calc != crc_recv:
            msg = f"{cmd_name}: CRC invalide (calc=0x{crc_calc:02X}, recv=0x{crc_recv:02X}) data={response.hex(' ')}"
            self._dbg(msg)
            return msg
        return None

    # ==================== DEVICE COMMANDS ====================

    def read_battery_level(self) -> Tuple[Optional[int], str]:
        """Read battery level (0-100). Returns (value, error_msg)."""
        success, response = self.send_command(LYNKXCommand.GET_BAT_LEVEL, expected_len=4)
        if not success:
            return None, "envoi echoue"
        err = self._check_response(response, 4, "GET_BAT_LEVEL")
        if err:
            return None, err

        # [counter] [status] [level] [crc8]
        status = response[1]
        if status != LYNKXError.OK:
            return None, f"status=0x{status:02X}"
        return response[2], ""

    def read_firmware_version(self) -> Tuple[Optional[str], str]:
        """Read firmware version. Returns (version_str, error_msg)."""
        success, response = self.send_command(LYNKXCommand.GET_FIRM_VER, expected_len=5)
        if not success:
            return None, "envoi echoue"
        err = self._check_response(response, 5, "GET_FIRM_VER")
        if err:
            return None, err

        # [counter] [status] [major] [minor] [crc8]
        status = response[1]
        if status != LYNKXError.OK:
            return None, f"status=0x{status:02X}"
        return f"{response[2]}.{response[3]:02d}", ""

    # ==================== FILE MANAGER COMMANDS ====================

    def fm_is_busy(self) -> Tuple[Optional[dict], str]:
        """
        Check if File Manager is busy + erase progress (0x20).
        Returns (info_dict, error_msg).
        info_dict: {'busy': bool, 'erase_percent': int}
        """
        success, response = self.send_command(LYNKXCommand.FM_IS_ERASING, expected_len=5)
        if not success:
            return None, "envoi echoue"
        err = self._check_response(response, 5, "FM_IS_ERASING")
        if err:
            return None, err

        # [echo] [busy] [erase_percent] [status] [crc]
        busy = response[1]
        erase_percent = response[2]
        status = response[3]
        if status != LYNKXError.OK:
            return None, f"status=0x{status:02X}"
        return {'busy': busy == 1, 'erase_percent': erase_percent}, ""

    def fm_get_log_count(self) -> Tuple[Optional[int], str]:
        """
        Get number of non-deleted logs (0x21).
        Returns (count, error_msg).
        """
        success, response = self.send_command(LYNKXCommand.FM_GET_LOG_COUNT, expected_len=5)
        if not success:
            return None, "envoi echoue"
        err = self._check_response(response, 5, "FM_GET_LOG_COUNT")
        if err:
            return None, err

        # [echo] [count_msb] [count_lsb] [status] [crc]
        count = (response[1] << 8) | response[2]
        status = response[3]
        if status != LYNKXError.OK:
            return None, f"status=0x{status:02X}"
        return count, ""

    def fm_get_list_page(self, start_index: int, out_max: int = FM_LIST_PAGE_MAX) -> Tuple[Optional[List[dict]], str]:
        """
        Get paginated list of logs (0x22).
        Returns (entries_list, error_msg).
        """
        out_max = min(out_max, FM_LIST_PAGE_MAX)
        payload = struct.pack(">HB", start_index, out_max)
        expected = 1 + 20 * out_max + 2
        success, response = self.send_command(
            LYNKXCommand.FM_GET_LIST_PAGE, payload=payload,
            response_timeout=2.0, expected_len=expected
        )
        if not success:
            return None, "envoi echoue"
        err = self._check_response(response, 4, "FM_GET_LIST_PAGE")
        if err:
            return None, err

        status = response[-2]
        data = response[1:-2]

        if len(data) % 20 != 0:
            msg = f"FM_GET_LIST_PAGE: taille payload invalide ({len(data)}B, pas multiple de 20)"
            self._dbg(msg)
            return None, msg

        entries = []
        for offset in range(0, len(data), 20):
            fields = struct.unpack_from(">IBBHIII", data, offset)
            entries.append({
                'log_id': fields[0],
                'log_type': fields[1],
                'state': fields[2],
                'rfu': fields[3],
                'start_unix': fields[4],
                'end_unix': fields[5],
                'size_bytes': fields[6],
            })

        if status != LYNKXError.OK:
            return entries, f"status=0x{status:02X} (donnees partielles)"
        return entries, ""

    def fm_get_log_info(self, log_id: int) -> Tuple[Optional[dict], str]:
        """
        Get info for a specific log (0x23).
        Returns (entry_dict, error_msg).
        """
        payload = struct.pack(">I", log_id)
        success, response = self.send_command(
            LYNKXCommand.FM_GET_LOG_INFO, payload=payload, expected_len=23
        )
        if not success:
            return None, "envoi echoue"
        if len(response) < 3:
            return None, f"reponse trop courte ({len(response)}B)"
        err = self._check_response(response, 3, "FM_GET_LOG_INFO")
        if err:
            return None, err

        if len(response) < 23:
            return None, f"log #{log_id} non trouve (reponse courte: {len(response)}B)"

        status = response[-2]
        if status != LYNKXError.OK:
            return None, f"status=0x{status:02X}"

        data = response[1:21]
        fields = struct.unpack_from(">IBBHIII", data, 0)
        return {
            'log_id': fields[0],
            'log_type': fields[1],
            'state': fields[2],
            'rfu': fields[3],
            'start_unix': fields[4],
            'end_unix': fields[5],
            'size_bytes': fields[6],
        }, ""

    def fm_read_log_chunk(self, log_id: int, offset: int, length: int) -> Tuple[Optional[bytes], int, str]:
        """
        Read a chunk of log data (0x24).

        Returns:
            Tuple of (data_bytes, out_read, error_msg).
            data_bytes=None on error, empty bytes on EOF (out_read==0).
        """
        payload = struct.pack(">IIH", log_id, offset, length)
        expected = 1 + length + 4
        success, response = self.send_command(
            LYNKXCommand.FM_READ_LOG_CHUNK, payload=payload,
            response_timeout=10.0, expected_len=expected,
            idle_timeout=0.05, pre_delay=0.0
        )
        if not success:
            return None, 0, "envoi echoue"
        err = self._check_response(response, 5, "FM_READ_LOG_CHUNK")
        if err:
            return None, 0, err

        status = response[-2]
        if status != LYNKXError.OK:
            return None, 0, f"status=0x{status:02X}"

        out_read = (response[-4] << 8) | response[-3]
        if out_read == 0:
            return b'', 0, ""

        data = response[1:-4]
        self._dbg(f"READ_CHUNK: offset={offset} out_read={out_read} actual={len(data)}")
        return bytes(data), out_read, ""

    def fm_delete_log(self, log_id: int) -> Tuple[bool, str]:
        """
        Delete a log (logical deletion) (0x25).
        Returns (success, error_msg).
        """
        payload = struct.pack(">I", log_id)
        success, response = self.send_command(
            LYNKXCommand.FM_DELETE_LOG, payload=payload, expected_len=3
        )
        if not success:
            return False, "envoi echoue"
        err = self._check_response(response, 3, "FM_DELETE_LOG")
        if err:
            return False, err
        if response[1] != LYNKXError.OK:
            return False, f"status=0x{response[1]:02X}"
        return True, ""

    def fm_erase_all_blocking(self) -> Tuple[bool, str]:
        """
        Erase all logs - BLOCKING (0x26). Takes 10-20s.
        Returns (success, error_msg).
        """
        success, response = self.send_command(
            LYNKXCommand.FM_ERASE_ALL_BLOCKING,
            response_timeout=30.0, expected_len=3
        )
        if not success:
            return False, "envoi echoue"
        err = self._check_response(response, 3, "FM_ERASE_ALL_BLOCKING")
        if err:
            return False, err
        if response[1] != LYNKXError.OK:
            return False, f"status=0x{response[1]:02X}"
        return True, ""

    def fm_erase_all_async(self) -> Tuple[bool, str]:
        """
        Launch async erase (0x27). Returns immediately.
        Use fm_is_busy() to poll progress.
        Returns (success, error_msg).
        """
        success, response = self.send_command(
            LYNKXCommand.FM_ERASE_ALL_ASYNC, expected_len=3,
            response_timeout=5.0
        )
        if not success:
            return False, "envoi echoue (serial?)"
        err = self._check_response(response, 3, "FM_ERASE_ALL_ASYNC")
        if err:
            return False, err

        # [echo] [status] [crc]
        status = response[1]
        if status != LYNKXError.OK:
            return False, f"status=0x{status:02X} (busy ou erreur)"
        return True, ""

    def fm_get_debug_info(self) -> Tuple[Optional[dict], str]:
        """
        Get FileManager internal state (0x28).
        Returns (info_dict, error_msg).
        """
        success, response = self.send_command(
            LYNKXCommand.FM_GET_DEBUG_INFO, expected_len=17
        )
        if not success:
            return None, "envoi echoue"
        err = self._check_response(response, 17, "FM_GET_DEBUG_INFO")
        if err:
            return None, err

        status = response[-2]
        if status != LYNKXError.OK:
            return None, f"status=0x{status:02X}"

        data = response[1:15]
        return {
            's_data_wr_ptr': struct.unpack_from(">I", data, 0)[0],
            's_dir_wr_ptr': struct.unpack_from(">I", data, 4)[0],
            's_next_log_id': struct.unpack_from(">I", data, 8)[0],
            's_dir_seq': struct.unpack_from(">H", data, 12)[0],
        }, ""

    # ==================== LOGGER COMMANDS ====================

    def logger_get_status(self) -> Tuple[Optional[dict], str]:
        """
        Get logger status (0x29).
        Returns (status_dict, error_msg).
        """
        success, response = self.send_command(
            LYNKXCommand.LOGGER_GET_STATUS, expected_len=5
        )
        if not success:
            return None, "envoi echoue"
        err = self._check_response(response, 5, "LOGGER_GET_STATUS")
        if err:
            return None, err

        # [echo] [running] [last_error] [LYNKX_OK] [crc]
        running = response[1]
        last_error = response[2]
        status = response[3]

        if status != LYNKXError.OK:
            return None, f"status=0x{status:02X}"
        return {
            'running': running == 1,
            'last_error': last_error,
        }, ""

    def logger_stop(self) -> Tuple[bool, int, str]:
        """
        Stop the logger (0x2A).
        Returns (success, error_code, error_msg).
        """
        success, response = self.send_command(
            LYNKXCommand.LOGGER_STOP, expected_len=4
        )
        if not success:
            return False, -1, "envoi echoue"
        err = self._check_response(response, 4, "LOGGER_STOP")
        if err:
            return False, -1, err

        # [echo] [status] [error_code] [crc]
        status = response[1]
        error_code = response[2]
        if status != LYNKXError.OK:
            return False, error_code, f"status=0x{status:02X}, logger_err={error_code}"
        return True, error_code, ""

    def logger_start(self, log_type: int = 2) -> Tuple[bool, int, str]:
        """
        Start a logging session (0x2B).

        Args:
            log_type: 0=RANDO, 1=PARA, 2=DEBUG

        Returns (success, error_code, error_msg).
        """
        success, response = self.send_command(
            LYNKXCommand.LOGGER_START,
            payload=bytes([log_type]),
            expected_len=4
        )
        if not success:
            return False, -1, "envoi echoue"
        err = self._check_response(response, 4, "LOGGER_START")
        if err:
            return False, -1, err

        # [echo] [status] [error_code] [crc]
        status = response[1]
        error_code = response[2]
        if status != LYNKXError.OK:
            return False, error_code, f"status=0x{status:02X}, logger_err={error_code}"
        return True, error_code, ""

    # ==================== LEGACY ALIASES ====================
    # These preserve the old return signatures for code that hasn't been updated

    def get_log_count(self) -> Optional[int]:
        """Alias for fm_get_log_count (returns only count)."""
        count, _ = self.fm_get_log_count()
        return count

    def get_logger_status(self) -> Optional[dict]:
        """Alias for logger_get_status (returns only dict)."""
        result, _ = self.logger_get_status()
        return result

    def start_logger(self, log_type: int = 2) -> bool:
        """Legacy alias - returns only success bool."""
        ok, _, _ = self.logger_start(log_type)
        return ok

    def stop_logger(self) -> bool:
        """Legacy alias - returns only success bool."""
        ok, _, _ = self.logger_stop()
        return ok
