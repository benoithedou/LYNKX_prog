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
    FM_ERASE_ALL_ASYNC = 0x27
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
BEACON_SETTINGS_ADDRESS = 0x00044000  # Sector 68 - Beacon settings
USER_SETTINGS_ADDRESS = 0x00045000  # Sector 69 - User settings

# Firmware Encryption
AES_KEY = bytes([0x3d, 0x0b, 0x0a, 0x8a, 0x1b, 0x5d, 0x17, 0xe2,
                 0x41, 0x23, 0x8d, 0xa9, 0xbb, 0x6c, 0x37, 0x8d])
AES_IV = bytes([0xad, 0x3f, 0xc1, 0x48, 0x9a, 0x75, 0xe3, 0x43,
                0x97, 0x82, 0xbd, 0x12, 0x0b, 0x05, 0xe3, 0x78])
AES_BLOCK_SIZE = 256

# File Manager Constants
FM_LIST_PAGE_MAX = 16
FM_READ_CHUNK_MAX = 120  # Max chunk size for READ_LOG_CHUNK (limited by BLE MTU)

# Logger Log Types
LOG_TYPE_RANDO = 0   # Randonnée/secours
LOG_TYPE_PARA = 1    # Parapente/vol libre
LOG_TYPE_DEBUG = 2   # Debug complet

LOG_TYPE_NAMES = {0: "RANDO", 1: "PARA", 2: "DEBUG"}
LOG_STATE_NAMES = {0: "OPEN", 1: "CLOSED", 2: "DELETED"}

# Logger error labels (shared)
LOGGER_ERROR_LABELS = {
    0: "Aucune erreur",
    1: "Logger pas demarre",
    2: "Logger deja actif",
    3: "Echec FileManager",
    4: "Erreur serialisation",
    5: "File vide",
}

# Flash memory layout
LOG_DATA_BASE = 0x00046000
LOG_DIR_BASE = 0x001F0000
LOG_DIR_END = 0x00200000

# Log file block types
BLK_TIME_SYNC = 0x01
BLK_STATUS = 0x02
BLK_EVENT = 0x03
BLK_GNSS_1HZ = 0x10
BLK_BARO_1HZ = 0x11
BLK_BARO_5HZ = 0x12
BLK_ACCEL_SUMMARY = 0x20
BLK_ACCEL_RAW = 0x21
BLK_BLE_ANCHORS = 0x30
BLK_BLE_PAYLOAD = 0x31
BLK_LORAWAN_FRAME = 0x40
BLK_LORA_P2P_FRAME = 0x41

BLK_TYPE_NAMES = {
    0x01: "TIME_SYNC", 0x02: "STATUS", 0x03: "EVENT",
    0x10: "GNSS_1HZ", 0x11: "BARO_1HZ", 0x12: "BARO_5HZ",
    0x20: "ACCEL_SUMMARY", 0x21: "ACCEL_RAW",
    0x30: "BLE_ANCHORS", 0x31: "BLE_PAYLOAD",
    0x40: "LORAWAN_FRAME", 0x41: "LORA_P2P_FRAME",
}

EVENT_ID_NAMES = {
    0x01: "SHORT_CLIC", 0x02: "LONG_CLIC", 0x03: "DOUBLE_CLIC",
    0x04: "TRIPLE_CLIC", 0x05: "SHORT_LONG_CLIC",
    0x06: "EMERGENCY", 0x07: "EMERGENCY_TEST", 0x08: "EMERGENCY_END",
    0x10: "SINGLE_TAP", 0x11: "DOUBLE_TAP",
    0x14: "SLEEP", 0x15: "WAKE_UP",
    0x20: "TAKEOFF_DETECTED", 0x21: "LANDING_DETECTED",
    0x30: "BLE_CONNECTED", 0x31: "BLE_DISCONNECTED",
    0x40: "GNSS_FIX_ACQUIRED", 0x41: "GNSS_FIX_LOST",
    0x60: "UNPLUGGED", 0x61: "CHARGING",
}

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

# TinySA Spectrum Analyzer
TINYSA_VID = 0x0483
TINYSA_PID = 0x5740
TINYSA_SCALE = 174

# Audio Test
AUDIO_POWER_THRESHOLD = -35  # dB
AUDIO_DURATION = 3  # seconds
AUDIO_SAMPLE_RATE = 44100

# RF Test - BLE
BLE_POWER_THRESHOLD = -50  # dBm
BLE_F_LOW = 2439500000
BLE_F_HIGH = 2440500000
BLE_POINTS = 2000

# RF Test - LoRa
LORA_POWER_THRESHOLD = -80  # dBm
LORA_F_LOW = 867750000
LORA_F_HIGH = 868250000
LORA_POINTS = 1000

# Pressure Test
PRESSURE_TOLERANCE = 1.0  # % relative error
WEATHER_API_KEY = "d388abe96ec97541bde0a9fd799f6ddb"
WEATHER_CITY = "Meylan"
WEATHER_ALTITUDE = 1000  # meters
