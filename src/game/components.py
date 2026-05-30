from dataclasses import dataclass

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

@dataclass
class Sprite:
    z: float = 0.0
    scale: float = 1.0 
    atlas_index: int = 0

@dataclass
class Interactible:
    enabled: bool = True
    on_interact: callable = None # Referencia na funkciu/callback