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
class SphereCollider:
    radius: float

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
    on_interact: callable = None

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
    alignment: str = "left"

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
    atlas_index: int = -1

@dataclass
class UIButton:
    text: str
    on_click: callable = None
    font_size: float = 0.3
    color_normal: tuple[float, float, float, float] = (0.2, 0.2, 0.3, 1.0)
    color_hover: tuple[float, float, float, float] = (0.3, 0.3, 0.5, 1.0)
    text_color: tuple[float, float, float, float] = (1.0, 1.0, 1.0, 1.0)
    is_hovered: bool = False

@dataclass
class UITextInput:
    text: str = ""
    placeholder: str = ""
    max_length: int = 32
    is_active: bool = False
    on_submit: callable = None
    font_size: float = 0.3
    color_normal: tuple[float, float, float, float] = (0.15, 0.15, 0.2, 1.0)
    color_active: tuple[float, float, float, float] = (0.2, 0.2, 0.35, 1.0)
    text_color: tuple[float, float, float, float] = (1.0, 1.0, 1.0, 1.0)
    placeholder_color: tuple[float, float, float, float] = (0.5, 0.5, 0.5, 1.0)
    cursor_blink_timer: float = 0.0

@dataclass
class ServerConfig:
    name: str
    max_players: int
    player_speed: float
    player_reach: float
    player_radius: float
    vent_open_time: float
    tick_rate: int

@dataclass
class NetworkPlayer:
    client_id: int
    name: str
    is_ready: bool = False

@dataclass
class NetworkIdentity:
    player_id: int
    role: str

@dataclass
class RemotePlayer:
    player_id: int

@dataclass
class Key:
    pass

@dataclass
class Portal:
    is_open: bool = False