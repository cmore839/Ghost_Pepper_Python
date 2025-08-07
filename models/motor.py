# models/motor.py
from dataclasses import dataclass

@dataclass
class Motor:
    """Represents a discovered motor's LIVE properties."""
    id: int
    angle: float = 0.0
    velocity: float = 0.0
    current_q: float = 0.0