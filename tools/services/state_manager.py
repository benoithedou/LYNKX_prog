"""Application state management."""
from typing import Optional, Dict, Any, Callable
import threading


class AppState:
    """
    Centralized application state manager.

    Manages all application state and provides thread-safe access.
    Uses event callbacks to notify listeners of state changes.
    """

    def __init__(self):
        """Initialize application state."""
        self._lock = threading.RLock()
        self._listeners: Dict[str, list] = {}

        # Serial state
        self.serial_port: Optional[str] = None
        self.serial_connected: bool = False

        # Device configuration
        self.device_id_qr: str = ""
        self.device_id_bar: str = ""
        self.device_type: Optional[int] = None
        self.mac_address: str = ""
        self.hardware_version: str = "1.04"

        # Operator info
        self.operator_name: str = ""

        # Firmware paths
        self.test_firmware_path: str = ""
        self.production_firmware_path: str = ""
        self.update_firmware_path: str = ""
        self.backup_firmware_path: str = ""

        # Test results
        self.test_results: Dict[str, bool] = {}

        # RF measurements
        self.max_freq_lora: float = 0.0
        self.max_power_lora: float = 0.0
        self.max_freq_ble: float = 0.0
        self.max_power_ble: float = 0.0

        # Environmental measurements
        self.current_pressure: float = 0.0

        # Battery level
        self.battery_level: Optional[int] = None

        # Firmware version
        self.firmware_version: Optional[str] = None

        # File manager state
        self.fm_entries: list = []
        self.fm_selected_id: Optional[int] = None

        # Terminal log
        self.terminal_log_enabled: bool = False
        self.terminal_log_path: str = "log.txt"

    def subscribe(self, event: str, callback: Callable[[Any], None]) -> None:
        """
        Subscribe to state change events.

        Args:
            event: Event name (e.g., 'serial_connected', 'battery_level')
            callback: Function to call when event occurs
        """
        with self._lock:
            if event not in self._listeners:
                self._listeners[event] = []
            self._listeners[event].append(callback)

    def unsubscribe(self, event: str, callback: Callable[[Any], None]) -> None:
        """
        Unsubscribe from state change events.

        Args:
            event: Event name
            callback: Function to remove
        """
        with self._lock:
            if event in self._listeners and callback in self._listeners[event]:
                self._listeners[event].remove(callback)

    def emit(self, event: str, data: Any = None) -> None:
        """
        Emit event to all listeners.

        Args:
            event: Event name
            data: Event data
        """
        with self._lock:
            if event in self._listeners:
                for callback in self._listeners[event]:
                    try:
                        callback(data)
                    except Exception as e:
                        print(f"Error in event listener for {event}: {e}")

    def set_serial_connected(self, connected: bool, port: Optional[str] = None) -> None:
        """Update serial connection state."""
        with self._lock:
            self.serial_connected = connected
            if port:
                self.serial_port = port
            self.emit('serial_connected', {'connected': connected, 'port': port})

    def set_device_ids(self, qr_code: str, bar_code: str) -> None:
        """Update device IDs."""
        with self._lock:
            self.device_id_qr = qr_code
            self.device_id_bar = bar_code
            self.emit('device_ids_changed', {'qr': qr_code, 'bar': bar_code})

    def set_device_config(self, device_type: int, mac_address: str) -> None:
        """Update device configuration."""
        with self._lock:
            self.device_type = device_type
            self.mac_address = mac_address
            self.emit('device_config_changed', {
                'type': device_type,
                'mac': mac_address
            })

    def set_battery_level(self, level: Optional[int]) -> None:
        """Update battery level."""
        with self._lock:
            self.battery_level = level
            self.emit('battery_level', level)

    def set_firmware_version(self, version: Optional[str]) -> None:
        """Update firmware version."""
        with self._lock:
            self.firmware_version = version
            self.emit('firmware_version', version)

    def set_test_result(self, test_name: str, passed: bool) -> None:
        """Update test result."""
        with self._lock:
            self.test_results[test_name] = passed
            self.emit('test_result', {'test': test_name, 'passed': passed})

    def set_rf_measurements(
        self,
        lora_freq: float = None,
        lora_power: float = None,
        ble_freq: float = None,
        ble_power: float = None
    ) -> None:
        """Update RF measurements."""
        with self._lock:
            if lora_freq is not None:
                self.max_freq_lora = lora_freq
            if lora_power is not None:
                self.max_power_lora = lora_power
            if ble_freq is not None:
                self.max_freq_ble = ble_freq
            if ble_power is not None:
                self.max_power_ble = ble_power

            self.emit('rf_measurements', {
                'lora_freq': self.max_freq_lora,
                'lora_power': self.max_power_lora,
                'ble_freq': self.max_freq_ble,
                'ble_power': self.max_power_ble
            })

    def set_pressure(self, pressure: float) -> None:
        """Update pressure measurement."""
        with self._lock:
            self.current_pressure = pressure
            self.emit('pressure', pressure)

    def set_hardware_version(self, version: str) -> None:
        """Update hardware version."""
        with self._lock:
            self.hardware_version = version
            self.emit('hardware_version', {'version': version})

    def get_state_dict(self) -> Dict[str, Any]:
        """Get complete state as dictionary."""
        with self._lock:
            return {
                'serial_port': self.serial_port,
                'serial_connected': self.serial_connected,
                'device_id_qr': self.device_id_qr,
                'device_id_bar': self.device_id_bar,
                'device_type': self.device_type,
                'mac_address': self.mac_address,
                'hardware_version': self.hardware_version,
                'operator_name': self.operator_name,
                'test_results': self.test_results.copy(),
                'battery_level': self.battery_level,
                'firmware_version': self.firmware_version,
            }
