"""Firmware encryption utilities."""
import os
import time
from Cryptodome.Cipher import AES
from Cryptodome.Util.Padding import pad
from typing import Tuple, Optional
from utils.crc import calculate_crc32
from utils.constants import AES_KEY, AES_IV, AES_BLOCK_SIZE


class FirmwareEncryption:
    """Handles firmware encryption and CRC calculation."""

    @staticmethod
    def read_firmware(file_path: str) -> bytes:
        """
        Read firmware from file.

        Args:
            file_path: Path to firmware file

        Returns:
            Firmware data

        Raises:
            FileNotFoundError: If file doesn't exist
        """
        with open(file_path, 'rb') as f:
            return f.read()

    @staticmethod
    def extract_version_info(data: bytes) -> Tuple[int, int, int, int]:
        """
        Extract version info from firmware data.

        Version info is located at offset 0x49-0x4B in the second block (block 1).

        Args:
            data: Firmware data

        Returns:
            Tuple of (hardware_version_min_major, hardware_version_min_minor, version_major, version_minor)
        """
        # Second block starts at offset 256
        if len(data) < 256 + 0x4C:
            return 0, 0, 0

        offset = 256  # Second block
        version_major = data[offset + 0x49]
        version_minor = data[offset + 0x4A]
        hardware_version_min_major = data[offset + 0x4B]
        hardware_version_min_minor = data[offset + 0x4c]

        return hardware_version_min_major, hardware_version_min_minor, version_major, version_minor

    @staticmethod
    def encrypt_firmware(
        input_path: str,
        output_dir: str = './firmwares'
    ) -> Tuple[bool, Optional[str], str]:
        """
        Encrypt firmware file.

        Args:
            input_path: Path to unencrypted firmware
            output_dir: Directory for encrypted output

        Returns:
            Tuple of (success, output_path, message)
        """
        try:
            # Read and pad firmware
            data = FirmwareEncryption.read_firmware(input_path)

            # Pad to AES_BLOCK_SIZE
            if len(data) % AES_BLOCK_SIZE:
                data = pad(data, len(data) + AES_BLOCK_SIZE - len(data) % AES_BLOCK_SIZE)

            # Calculate CRC32 of clear data
            crc32_clear = calculate_crc32(list(data))

            # Encrypt data
            cipher = AES.new(AES_KEY, AES.MODE_CBC, AES_IV)
            encrypted_data = cipher.encrypt(data)

            # Calculate CRC32 of encrypted data
            crc32_crypted = calculate_crc32(list(encrypted_data))

            # Extract version info from clear data
            hardware_version_min_major, hardware_version_min_minor, version_major, version_minor = \
                FirmwareEncryption.extract_version_info(data)
            version = version_major + version_minor/100
            hardware_version_min = hardware_version_min_major + hardware_version_min_minor/100

            # Build output filename
            timestamp = int(time.time())
            filename = (
                f'LYNKXF_{hardware_version_min:05.2f}_{timestamp}_'
                f'{version:05.2f}_{crc32_clear:08x}_{crc32_crypted:08x}.blf'
            )
            

            # Ensure output directory exists
            os.makedirs(output_dir, exist_ok=True)

            # Write encrypted file
            output_path = os.path.join(output_dir, filename)
            with open(output_path, 'wb') as f:
                f.write(encrypted_data)

            message = (
                f"Encryption successful:\n"
                f"HW: {hardware_version_min}\n"
                f"Version: {version_major}.{version_minor:02d}\n"
                f"CRC Clear: {crc32_clear:08x}\n"
                f"CRC Encrypted: {crc32_crypted:08x}\n"
                f"Output: {filename}"
            )

            return True, output_path, message

        except Exception as e:
            return False, None, f"Encryption failed: {str(e)}"

    @staticmethod
    def validate_firmware_padding(data: bytes) -> bool:
        """
        Check if firmware is properly padded to AES_BLOCK_SIZE.

        Args:
            data: Firmware data

        Returns:
            True if properly padded
        """
        return len(data) % AES_BLOCK_SIZE == 0
