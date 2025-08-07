# models/can_message.py
from dataclasses import dataclass

@dataclass
class CanMessage:
    """
    A simple data class for CAN messages.
    """
    arbitration_id: int
    data: bytearray