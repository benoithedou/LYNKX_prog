"""Core communication layer."""
from core.serial_manager import SerialManager
from core.lynkx_protocol import LYNKXProtocol

__all__ = ['SerialManager', 'LYNKXProtocol']
