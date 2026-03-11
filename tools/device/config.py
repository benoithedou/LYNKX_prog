"""Device configuration management."""
from typing import Optional
from utils.constants import (
    MAC_ADDRESS_PREFIX,
    PRODUCT_REF_STANDARD,
    PRODUCT_REF_SUMMIT,
    DEVICE_TYPE_STANDARD,
    DEVICE_TYPE_SUMMIT,
    HW_VERSION_1_02,
    HW_VERSION_1_04
)
from utils.crc import calculate_crc8


class DeviceConfig:
    """
    LYNKX device configuration.

    Encapsulates device configuration including MAC address,
    hardware version, and product type.
    """

    def __init__(
        self,
        mac_address: str,
        device_type: int,
        hardware_version: str
    ):
        """
        Initialize device configuration.

        Args:
            mac_address: Full MAC address (e.g., "8C:1F:64:EE:61:00:01:CF")
            device_type: Device type (0=SUMMIT, 1=STANDARD)
            hardware_version: Hardware version ("1.02" or "1.04")
        """
        self.mac_address = mac_address
        self.device_type = device_type
        self.hardware_version = hardware_version

        # Parse hardware version
        if hardware_version == HW_VERSION_1_04:
            self.hw_major = 1
            self.hw_minor = 4
        elif hardware_version == HW_VERSION_1_02:
            self.hw_major = 1
            self.hw_minor = 2
        else:
            raise ValueError(f"Unknown hardware version: {hardware_version}")

        # Set product reference
        if device_type == DEVICE_TYPE_SUMMIT:
            self.product_reference = bytearray(PRODUCT_REF_SUMMIT)
        else:
            self.product_reference = bytearray(PRODUCT_REF_STANDARD)

        # Parse MAC address
        self.mac_bytes = self._parse_mac_address(mac_address)

    @staticmethod
    def _parse_mac_address(mac_str: str) -> bytearray:
        """
        Parse MAC address string to bytes.

        Args:
            mac_str: MAC address string (e.g., "8C:1F:64:EE:61:00:01:CF")

        Returns:
            MAC address as bytearray
        """
        mac_parts = mac_str.split(":")
        mac_bytes = bytearray(int(part, 16) for part in mac_parts)
        return mac_bytes

    @staticmethod
    def validate_device_ids(qr_code: str, bar_code: str) -> Optional[int]:
        """
        Validate QR code and barcode match.

        Args:
            qr_code: QR code data (format: "xxx=xxxxxxxxx")
            bar_code: Barcode data

        Returns:
            Device type (0 or 1) if valid, None if invalid
        """
        if not qr_code or not bar_code:
            return None

        # Extract ID from QR code
        if '=' not in qr_code:
            return None

        qr_id = qr_code.split('=')[1]

        # Compare with barcode
        if qr_id != bar_code:
            return None

        # Determine device type from second character
        if len(qr_id) < 2:
            return None

        second_char = qr_id[1]
        if second_char == '0':
            return DEVICE_TYPE_SUMMIT
        elif second_char == '1':
            return DEVICE_TYPE_STANDARD
        else:
            return None

    @staticmethod
    def build_mac_address(device_id: str) -> str:
        """
        Build MAC address from device ID.

        Args:
            device_id: Device ID string

        Returns:
            Full MAC address string
        """
        mac = MAC_ADDRESS_PREFIX

        # Add device ID bytes in pairs
        for i in range(0, len(device_id), 2):
            if i + 1 < len(device_id):
                mac += f":{device_id[i]}{device_id[i+1]}"

        return mac

    def to_bytes(self) -> bytes:
        """
        Convert configuration to bytes for transmission.

        Returns:
            Configuration bytes
        """
        config = bytearray()

        # Product reference (16 bytes)
        config.extend(self.product_reference)

        # Hardware version (2 bytes)
        config.append(self.hw_major)
        config.append(self.hw_minor)

        # MAC address (8 bytes)
        config.extend(self.mac_bytes)

        return bytes(config)

    def __str__(self) -> str:
        """String representation."""
        device_name = "LYNKX+ SUMMIT" if self.device_type == DEVICE_TYPE_SUMMIT else "LYNKX+"
        return (
            f"DeviceConfig("
            f"type={device_name}, "
            f"hw={self.hardware_version}, "
            f"mac={self.mac_address})"
        )


class BeaconSettings:
    """Beacon settings (production config, not user-accessible)."""

    STRUCT_SIZE = 128  # Total size of beacon_settings_t

    def __init__(
        self,
        ble_scanner: int = 0,
        gnss_en: int = 1,
        p2p_en: int = 1,
        lora_repeater: int = 0,
        notification_en: int = 1,
        auto_power_off_en: int = 0,
        auto_power_off_delay: int = 0
    ):
        self.ble_scanner = ble_scanner
        self.gnss_en = gnss_en
        self.p2p_en = p2p_en
        self.lora_repeater = lora_repeater
        self.notification_en = notification_en
        self.auto_power_off_en = auto_power_off_en
        self.auto_power_off_delay = auto_power_off_delay  # uint16_t, minutes

    def to_bytes(self) -> bytes:
        """Build 128-byte beacon_settings_t struct with CRC."""
        data = bytearray(self.STRUCT_SIZE)
        data[0] = 8  # settings_number: 8 bytes of params
        data[1] = self.ble_scanner & 0xFF
        data[2] = self.gnss_en & 0xFF
        data[3] = self.p2p_en & 0xFF
        data[4] = self.lora_repeater & 0xFF
        data[5] = self.notification_en & 0xFF
        data[6] = self.auto_power_off_en & 0xFF
        data[7] = self.auto_power_off_delay & 0xFF          # uint16_t low byte
        data[8] = (self.auto_power_off_delay >> 8) & 0xFF   # uint16_t high byte
        # RFU bytes 9..126 = 0xFF
        for i in range(9, self.STRUCT_SIZE - 1):
            data[i] = 0xFF
        # CRC-8 over first 127 bytes
        data[self.STRUCT_SIZE - 1] = calculate_crc8(bytes(data[:self.STRUCT_SIZE - 1]))
        return bytes(data)


class UserSettings:
    """User settings (modifiable by end user via app)."""

    STRUCT_SIZE = 128  # Total size of user_settings_t

    INACTIVITY_MAP = {"Off": 0, "30s": 1, "60s": 2, "120s": 3, "180s": 4, "300s": 5}
    PROFILE_MAP = {"Perf": 0, "Balanced": 1, "Eco": 2, "Eco2": 3}

    def __init__(
        self,
        inactivity_duration: int = 0,
        power_profile: int = 1,
        power_on_charging: int = 1
    ):
        self.inactivity_duration = inactivity_duration
        self.power_profile = power_profile
        self.power_on_charging = power_on_charging

    def to_bytes(self) -> bytes:
        """Build 128-byte user_settings_t struct with CRC."""
        data = bytearray(self.STRUCT_SIZE)
        data[0] = 3  # settings_number: 3 bytes of params
        data[1] = self.inactivity_duration & 0xFF
        data[2] = self.power_profile & 0xFF
        data[3] = self.power_on_charging & 0xFF
        # RFU bytes 4..126 = 0xFF
        for i in range(4, self.STRUCT_SIZE - 1):
            data[i] = 0xFF
        # CRC-8 over first 127 bytes
        data[self.STRUCT_SIZE - 1] = calculate_crc8(bytes(data[:self.STRUCT_SIZE - 1]))
        return bytes(data)
