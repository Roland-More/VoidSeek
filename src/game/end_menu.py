import wgpu
from core.scene import Scene
from game.ecs import World
from game.components import UIPosition, UIButton, TextEntity, UISprite
from core.backend.definitions import RENDER_WIDTH, RENDER_HEIGHT

class EndMenuScene(Scene):
    def __init__(self, renderer, scene_manager, init_data=None):
        super().__init__(renderer)
        self.scene_manager = scene_manager
        self.world = World()
        
        center_x = RENDER_WIDTH / 2
        
        winner = init_data.get("winner", "runner") if init_data else "runner"
        my_role = init_data.get("my_role", "runner") if init_data else "runner"
        
        if winner == "terminated":
            result_text = "MATCH TERMINATED"
            color = (1.0, 0.8, 0.2, 1.0)
        elif my_role == winner:
            result_text = "YOU WON!"
            color = (0.2, 1.0, 0.2, 1.0)
        else:
            result_text = "YOU LOST!"
            color = (1.0, 0.2, 0.2, 1.0)
            
        self.world.add_component(self.world.create_entity(), TextEntity(
            text=result_text, x=center_x, y=RENDER_HEIGHT * 0.3, size=1.0, color=color, alignment="center"
        ))
        
        # Návrat do menu - border
        bg_quit = self.world.create_entity()
        quit_y = RENDER_HEIGHT * 0.6
        self.world.add_component(bg_quit, UIPosition(x=center_x - 100, y=quit_y, width=200, height=50, z_index=1))
        self.world.add_component(bg_quit, UISprite(color=(0.1, 0.1, 0.1, 1.0), use_texture=False))
        
        btn_quit = self.world.create_entity()
        self.world.add_component(btn_quit, UIPosition(x=center_x - 96, y=quit_y + 4, width=192, height=42, z_index=2))
        self.world.add_component(btn_quit, UIButton(
            text="RETURN TO MENU",
            on_click=lambda: self.scene_manager.switch_to("menu"),
            color_normal=(0.3, 0.0, 0.0, 1.0),
            color_hover=(0.5, 0.0, 0.0, 1.0)
        ))

    def update(self, delta_time: float):
        self.renderer.update_camera(0.0, 0.0, 0.0)

    def handle_key_down(self, key: str):
        pass

    def handle_key_up(self, key: str):
        pass

    def draw(self, encoder, target_view):
        self.renderer.update_text(self.world)
        self.renderer.update_ui_buffers(self.world)
        self.renderer.render_menu_scene(encoder, target_view)
