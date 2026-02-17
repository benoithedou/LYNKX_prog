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
