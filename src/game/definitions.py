from enum import Enum
from typing import Callable

VENT_OFFSET = 0.15
PLAYER_RADIUS = 0.15
INTERACT_DISTANCE = 1.5
TIME_TO_OPEN_VENT = 10.0

class PlaybackState(Enum):
    PLAYING = 1
    STOPPED = 2

class PlaybackMode(Enum):
    ONCE = 1
    LOOP = 2

class AnimationDirection(Enum):
    FORWARD = 1
    BACKWARD = 2

class VentAnim(Enum):
    OPENING = 1
    CLOSING = 2

class DoorAnim(Enum):
    OPENING = 1
    CLOSING = 2

# We'll use tuples or dataclasses for AnimKey in python if needed, 
# but strings like "VentAnim.OPENING" or just tuples like ("Vent", VentAnim.OPENING) are easier.

class VentOrientation(Enum):
    NONE = 0
    HORIZONTAL = 1
    VERTICAL = 2
