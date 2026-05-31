import wgpu
from core.scene import Scene
from .ecs import World
from .components import UIPosition, UIButton, UITextInput, TextEntity

class MenuScene(Scene):
    def __init__(self, renderer, scene_manager):
        self.renderer = renderer
        self.scene_manager = scene_manager
        self.world = World()
        
        # Názov hry
        title_entity = self.world.create_entity()
        self.world.add_component(title_entity, TextEntity(text="VOIDSEEK", x=240, y=50, size=1.0, color=(1.0, 1.0, 1.0, 1.0), alignment="center"))
        
        # Hľadať servery
        btn_servers = self.world.create_entity()
        self.world.add_component(btn_servers, UIPosition(x=140, y=100, width=200, height=60, z_index=1))
        self.world.add_component(btn_servers, UIButton(
            text="HLADAT SERVERY",
            on_click=lambda: self.scene_manager.switch_to("server_list")
        ))
        
        # Ukončiť
        btn_quit = self.world.create_entity()
        self.world.add_component(btn_quit, UIPosition(x=140, y=170, width=200, height=60, z_index=1))
        self.world.add_component(btn_quit, UIButton(
            text="UKONCIT",
            on_click=lambda: self.renderer.canvas.close()
        ))

    def update(self, delta_time: float):
        self.renderer.update_camera(0.0, 0.0, 0.0)

    def handle_key_down(self, key: str):
        pass

    def draw(self, encoder, target_view):
        self.renderer.update_text(self.world)
        self.renderer.update_ui_buffers(self.world)
        self.renderer.render_menu_scene(encoder, target_view)
