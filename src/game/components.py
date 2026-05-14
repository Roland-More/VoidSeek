from dataclasses import dataclass
from .input import InputState

@dataclass
class Position:
    x: float
    y: float

@dataclass
class Rotation:
    angle: float

@dataclass
class Velocity:
    speed: float
    dx: float = 0.0
    dy: float = 0.0

@dataclass
class PlayerController:
    sensitivity: float = 0.0015
