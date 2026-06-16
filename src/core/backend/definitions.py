import struct
import array
import ctypes
import glfw
import platform
from enum import Enum, auto

MAX_MAP_WIDTH = 128
MAX_MAP_HEIGHT = 128
MAX_MAP_TILES = 16384
TILE_SIZE = 64

if platform.system() == "Windows":
    user32 = ctypes.windll.user32
    RENDER_WIDTH, RENDER_HEIGHT = user32.GetSystemMetrics(0) // 4, user32.GetSystemMetrics(1) // 4
else:
    if glfw.init():
            monitor = glfw.get_primary_monitor()
            if monitor:
                mode = glfw.get_video_mode(monitor)
                # mode.size contains (width, height) of the monitor
                RENDER_WIDTH = mode.size.width // 4
                RENDER_HEIGHT = mode.size.height // 4
            glfw.terminate() # Clean up since this is just a definitions file

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
