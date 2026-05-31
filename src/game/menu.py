from core.scene import Scene
from game.ecs import World
from game.components import TextEntity, UIPosition, UISprite, UIButton, UITextInput

class MenuScene(Scene):
    def __init__(self, renderer, scene_manager):
        super().__init__(renderer)
        self.scene_manager = scene_manager
        
        self.world.add_component(
            self.world.create_entity(),
            TextEntity("TEST UI WIDGETOV", x=120.0, y=20.0, size=0.4, color=(1.0, 1.0, 1.0, 1.0))
        )
        
        # Test Button
        btn_entity = self.world.create_entity()
        self.world.add_component(btn_entity, UIPosition(x=140, y=80, width=200, height=40, z_index=1))
        self.world.add_component(btn_entity, UIButton(
            text="KLIKNI SEM",
            on_click=lambda: print("Tlacitko bolo stlacene!"),
            font_size=0.3
        ))

        # Test Text Input
        input_entity = self.world.create_entity()
        self.world.add_component(input_entity, UIPosition(x=140, y=140, width=200, height=40, z_index=1))
        self.world.add_component(input_entity, UITextInput(
            placeholder="Napis daco...",
            font_size=0.3,
            on_submit=lambda txt: print(f"Zadany text: {txt}")
        ))

    def update(self, delta_time: float):
        self.renderer.update_camera(0.0, 0.0, 0.0)

    def handle_key_down(self, key: str):
        if key == "enter":
            if not self.renderer._is_mouse_locked:
                self.renderer.toggle_mouse_lock()
            self.scene_manager.switch_to("game")

    def draw(self, encoder, target_view):
        self.renderer.update_text(self.world)
        self.renderer.update_ui_buffers(self.world)
        self.renderer.render_menu_scene(encoder, target_view)
