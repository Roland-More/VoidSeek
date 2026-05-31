from core.scene import Scene
from game.ecs import World
from game.components import TextEntity, UIPosition, UISprite

class MenuScene(Scene):
    def __init__(self, renderer, scene_manager):
        super().__init__(renderer)
        self.scene_manager = scene_manager
        
        self.world.add_component(
            self.world.create_entity(),
            TextEntity("STLAC ENTER PRE START", x=0.3, y=0.5, size=0.15, color=(1.0, 1.0, 1.0, 1.0))
        )
        
        # Test UI obdĺžnik pre vizuálnu kontrolu (modré polopriehľadné pozadie)
        bg_entity = self.world.create_entity()
        self.world.add_component(bg_entity, UIPosition(x=100, y=100, width=600, height=400, z_index=-1))
        self.world.add_component(bg_entity, UISprite(color=(0.1, 0.2, 0.8, 0.5)))

    def update(self, delta_time: float):
        self.renderer.update_camera(0.0, 0.0, 0.0)

    def handle_key_down(self, key: str):
        if key == "enter":
            self.scene_manager.switch_to("game")

    def draw(self, encoder, target_view):
        self.renderer.update_text(self.world)
        self.renderer.update_ui_buffers(self.world)
        self.renderer.render_menu_scene(encoder, target_view)
