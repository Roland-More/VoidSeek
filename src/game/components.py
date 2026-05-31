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
    is_visible: bool = True
    atlas_index_front: int = 0
    atlas_index_back: int = 0

@dataclass
class Interactible:
    enabled: bool = True
    on_interact: callable = None # Referencia na funkciu/callback

@dataclass
class TextureAnimation:
    frames: list[int]
    frame_duration: float
    playback_mode: 'PlaybackMode'

@dataclass
class TextureAnimator:
    animations: dict
    current_animation: any
    current_frame: int = 0
    timer: float = 0.0
    playback_state: 'PlaybackState' = None
    direction: 'AnimationDirection' = None

@dataclass
class SpriteAnimation:
    frames_front: list[int]
    frames_back: list[int]
    frame_duration: float
    playback_mode: 'PlaybackMode'

@dataclass
class SpriteAnimator:
    animations: dict
    current_animation: any
    current_frame: int = 0
    timer: float = 0.0
    playback_state: 'PlaybackState' = None
    direction: 'AnimationDirection' = None

@dataclass
class Vent:
    is_open: bool
    timer: float
    time_to_open: float
    orientation: 'VentOrientation'
    destinations: tuple['Position', 'Position']

@dataclass
class TextEntity:
    text: str
    x: float
    y: float
    size: float
    color: tuple[float, float, float, float]
    font_id: int = 0

@dataclass
class FPSCounter:
    timer: float = 0.0
    frame_count: int = 0
    time_to_update: float = 0.25

@dataclass
class UIPosition:
    x: float
    y: float
    width: float
    height: float
    z_index: int = 0

@dataclass
class UISprite:
    color: tuple[float, float, float, float] = (1.0, 1.0, 1.0, 1.0)
    texture_id: int = -1
    use_texture: bool = False