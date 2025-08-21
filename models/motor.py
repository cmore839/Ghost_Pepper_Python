# models/motor.py
from dataclasses import dataclass

@dataclass
class Motor:
    """Represents a discovered motor's LIVE properties."""
    id: int
    angle: float = 0.0
    velocity: float = 0.0
    current_q: float = 0.0
    phase_resistance: float = 0.0
    phase_inductance: float = 0.0
    is_enabled: bool = False # NEW: Added to track the motor's enabled state