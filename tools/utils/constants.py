"""Application constants."""

# Serial Configuration
SERIAL_BAUDRATE = 921600
SERIAL_TIMEOUT = 0.2
SERIAL_PARITY = 'N'  # No parity (same as original production_test.py)
SERIAL_STOPBITS = 1
SERIAL_BYTESIZE = 8

# LYNKX Command IDs
class LYNKXCommand:
    """LYNKX protocol command IDs."""
    GET_BAT_LEVEL = 0x03
    GET_FIRM_VER = 0x05

    # File Manager Commands
    FM_IS_ERASING = 0x20
    FM_GET_LOG_COUNT = 0x21
    FM_GET_LIST_PAGE = 0x22
    FM_GET_LOG_INFO = 0x23
    FM_READ_LOG_CHUNK = 0x24
    FM_DELETE_LOG = 0x25
    FM_ERASE_ALL_BLOCKING = 0x26
    FM_ERASE_ALL_STEP = 0x27
    FM_GET_DEBUG_INFO = 0x28

    # Logger Commands
    LOGGER_GET_STATUS = 0x29
    LOGGER_STOP = 0x2A
    LOGGER_START = 0x2B


# Error Codes
class LYNKXError:
    """LYNKX protocol error codes."""
    OK = 0x00
    KO = 0x01
    BAD_PARAMETER = 0x02
    NOT_SUPPORTED = 0x03
    BAD_CRC8 = 0x04
    FIRM_BAD_CRC32 = 0x05
    FIRM_LOW_BAT = 0x06
    VERS = 0x07
    BOOT_BAD_CRC32 = 0x08
    BOOT_LOW_BAT = 0x09
    UNKNOWN_PARAMETER = 0x0A


# Logger Error Codes
class LoggerError:
    """Logger-specific error codes."""
    OK = 0
    NOT_RUNNING = 1
    ALREADY_RUNNING = 2
    FM = 3
    SERIALIZE = 4
    QUEUE_EMPTY = 5


# Device Configuration
MAC_ADDRESS_PREFIX = "8C:1F:64:EE"
PRODUCT_REF_STANDARD = b'LYNKX+          '
PRODUCT_REF_SUMMIT = b'LYNKX+ SUMMIT   '

# Memory Addresses
MEMORY_INT_BASE = 0x08006000  # Internal flash base address
MEMORY_EXT_BASE = 0x00000000  # External flash base address
MEMORY_EXT_BACKUP = 0x001C0000  # External flash backup address

# Firmware Encryption
AES_KEY = bytes([0x3d, 0x0b, 0x0a, 0x8a, 0x1b, 0x5d, 0x17, 0xe2,
                 0x41, 0x23, 0x8d, 0xa9, 0xbb, 0x6c, 0x37, 0x8d])
AES_IV = bytes([0xad, 0x3f, 0xc1, 0x48, 0x9a, 0x75, 0xe3, 0x43,
                0x97, 0x82, 0xbd, 0x12, 0x0b, 0x05, 0xe3, 0x78])
AES_BLOCK_SIZE = 256

# File Manager Constants
FM_LIST_PAGE_MAX = 16
FM_READ_CHUNK_MAX = 20

# Test Names
TEST_NAMES = [
    'LED_GREEN1', 'LED_GREEN2', 'LED_RED1', 'LED_RED2',
    'LED_FLASH', 'SOUND', 'PRESSURE', 'ACCELEROMETER',
    'BC_STATE', 'BLE', 'LORA', 'GNSS', 'FLASH', 'EMERGENCY_TAB'
]

# Hardware Versions
HW_VERSION_1_02 = "1.02"
HW_VERSION_1_04 = "1.04"

# Device Types
DEVICE_TYPE_STANDARD = 1
DEVICE_TYPE_SUMMIT = 0
