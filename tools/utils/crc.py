"""CRC calculation utilities."""


def reverse_bytes_in_dwords(input_list: list) -> list:
    """
    Reverse bytes in each 32-bit word.

    Args:
        input_list: List of bytes (must be multiple of 4)

    Returns:
        List with reversed bytes in each dword
    """
    assert len(input_list) % 4 == 0, "Input length must be multiple of 4"

    output = [0] * len(input_list)

    for i in range(0, len(input_list), 4):
        output[i] = input_list[i + 3]
        output[i + 1] = input_list[i + 2]
        output[i + 2] = input_list[i + 1]
        output[i + 3] = input_list[i]

    return output


def calculate_crc32(data: list) -> int:
    """
    Calculate CRC32 with custom polynomial.

    Args:
        data: List of bytes

    Returns:
        CRC32 value
    """
    poly = 0x04C11DB7
    initial = 0xFFFFFFFF

    data = reverse_bytes_in_dwords(data)

    # Build CRC table
    table = [0] * 256
    for i in range(256):
        c = i << 24
        for j in range(8):
            if (c & 0x80000000) != 0:
                c = (c << 1) ^ poly
            else:
                c <<= 1
        table[i] = c

    # Calculate CRC (MSB first)
    crc = initial
    for byte in data:
        index = ((crc >> 24) ^ byte) & 0xFF
        crc = (crc << 8) ^ table[index]

    return crc & 0xFFFFFFFF


def calculate_crc8(data: bytes) -> int:
    """
    Calculate CRC8 for packet validation.

    Args:
        data: Bytes to calculate CRC for

    Returns:
        CRC8 value
    """
    crc = 0
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x80:
                crc = (crc << 1) ^ 0x07
            else:
                crc <<= 1
            crc &= 0xFF
    return crc
