import wgpu
import random
from core.scene import Scene
from .ecs import World
from .components import UIPosition, UIButton, UITextInput, TextEntity, UISprite
from core.backend.definitions import RENDER_WIDTH, RENDER_HEIGHT

class MenuScene(Scene):
    def __init__(self, renderer, scene_manager):
        self.renderer = renderer
        self.scene_manager = scene_manager
        self.world = World()
        
        center_x = RENDER_WIDTH / 2
        
        # Názov hry
        title_entity = self.world.create_entity()
        self.world.add_component(title_entity, TextEntity(text="VOIDSEEK", x=center_x, y=RENDER_HEIGHT * 0.15, size=1.0, color=(1.0, 1.0, 1.0, 1.0), alignment="center"))
        
        # Meno hráča - border
        bg_name = self.world.create_entity()
        name_y = RENDER_HEIGHT * 0.35
        self.world.add_component(bg_name, UIPosition(x=center_x - 100, y=name_y, width=200, height=40, z_index=1))
        self.world.add_component(bg_name, UISprite(color=(0.1, 0.1, 0.1, 1.0), use_texture=False))
        
        # Meno hráča - input
        self.name_input = self.world.create_entity()
        self.world.add_component(self.name_input, UIPosition(x=center_x - 96, y=name_y + 4, width=192, height=32, z_index=2))
        self.world.add_component(self.name_input, UITextInput(
            placeholder="Player Name", text=f"Player{random.randint(1, 999)}", max_length=13,
            color_normal=(0.2, 0.0, 0.0, 1.0), color_active=(0.4, 0.0, 0.0, 1.0)
        ))
        
        # Hľadať servery - border
        bg_servers = self.world.create_entity()
        servers_y = RENDER_HEIGHT * 0.55
        self.world.add_component(bg_servers, UIPosition(x=center_x - 100, y=servers_y, width=200, height=50, z_index=1))
        self.world.add_component(bg_servers, UISprite(color=(0.1, 0.1, 0.1, 1.0), use_texture=False))
        
        btn_servers = self.world.create_entity()
        self.world.add_component(btn_servers, UIPosition(x=center_x - 96, y=servers_y + 4, width=192, height=42, z_index=2))
        self.world.add_component(btn_servers, UIButton(
            text="FIND SERVERS",
            on_click=self.goto_servers,
            color_normal=(0.3, 0.0, 0.0, 1.0),
            color_hover=(0.5, 0.0, 0.0, 1.0)
        ))
        
        # Ukončiť - border
        bg_quit = self.world.create_entity()
        quit_y = RENDER_HEIGHT * 0.75
        self.world.add_component(bg_quit, UIPosition(x=center_x - 100, y=quit_y, width=200, height=50, z_index=1))
        self.world.add_component(bg_quit, UISprite(color=(0.1, 0.1, 0.1, 1.0), use_texture=False))
        
        btn_quit = self.world.create_entity()
        self.world.add_component(btn_quit, UIPosition(x=center_x - 96, y=quit_y + 4, width=192, height=42, z_index=2))
        self.world.add_component(btn_quit, UIButton(
            text="QUIT",
            on_click=lambda: self.renderer.canvas.close(),
            color_normal=(0.3, 0.0, 0.0, 1.0),
            color_hover=(0.5, 0.0, 0.0, 1.0)
        ))

    def goto_servers(self):
        inp = self.world.get_component(self.name_input, UITextInput)
        name = inp.text.strip() if inp.text else "NoName"
        if len(name) < 3:
            name = (name + "xyz")[:3]
        elif len(name) > 13:
            name = name[:13]
        self.scene_manager.player_name = name
        self.scene_manager.switch_to("server_list")

    def update(self, delta_time: float):
        self.renderer.update_camera(0.0, 0.0, 0.0)

    def handle_key_down(self, key: str):
        pass

    def draw(self, encoder, target_view):
        self.renderer.update_text(self.world)
        self.renderer.update_ui_buffers(self.world)
        self.renderer.render_menu_scene(encoder, target_view)
