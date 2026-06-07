import struct
import array
import ctypes
from enum import Enum, auto

MAX_MAP_WIDTH = 96
MAX_MAP_HEIGHT = 96
MAX_MAP_TILES = 9216
TILE_SIZE = 64
user32 = ctypes.windll.user32
RENDER_WIDTH, RENDER_HEIGHT = user32.GetSystemMetrics(0) // 4, user32.GetSystemMetrics(1) // 4
MAX_SPRITES = 4096

class BindScope(Enum):
    Camera = auto()
    Map = auto()
    AtlasTexture = auto()
    BlitTexture = auto()
    RayHits = auto()
    ComputeRayHits = auto()
    SpriteInstances = auto()
    FontAtlas = auto()
    TextInstances = auto()
    UIInstances = auto()
    UISpriteInstances = auto()

class RenderPipelineType(Enum):
    Raycast = auto()
    Blit = auto()
    Sprite = auto()
    Text = auto()
    UI = auto()
    UISprite = auto()

class ComputePipelineType(Enum):
    Raycast = auto()

class CameraResources:
    def __init__(self, bind_group, buffer):
        self.bind_group = bind_group
        self.buffer = buffer

class MapResources:
    def __init__(self, bind_group, data_buffer, settings_buffer):
        self.bind_group = bind_group
        self.data_buffer = data_buffer
        self.settings_buffer = settings_buffer

class AtlasResources:
    def __init__(self, bind_group, texture_view):
        self.bind_group = bind_group
        self.texture_view = texture_view

class AtlasSpriteResources:
    def __init__(self, bind_group, texture_view):
        self.bind_group = bind_group
        self.texture_view = texture_view

class BlitResources:
    def __init__(self, offscreen_texture, bind_group):
        self.offscreen_texture = offscreen_texture
        self.bind_group = bind_group

class FontResources:
    def __init__(self, bind_group, texture_view):
        self.bind_group = bind_group
        self.texture_view = texture_view

class TextInstanceResources:
    def __init__(self, bind_group, buffer):
        self.bind_group = bind_group
        self.buffer = buffer

class UIInstanceResources:
    def __init__(self, bind_group, buffer):
        self.bind_group = bind_group
        self.buffer = buffer
