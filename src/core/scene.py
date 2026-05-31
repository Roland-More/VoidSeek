from game.ecs import World

class Scene:
    def __init__(self, renderer):
        self.renderer = renderer
        self.world = World()

    def update(self, delta_time: float):
        pass

    def draw(self, encoder, target_view):
        pass

    def handle_key_down(self, key: str):
        pass

    def handle_key_up(self, key: str):
        pass

    def handle_mouse_move(self, dx: float):
        pass


class SceneManager:
    def __init__(self):
        self.scenes: dict[str, Scene] = {}
        self.current_scene: Scene | None = None

    def register(self, name: str, scene: Scene):
        self.scenes[name] = scene

    def switch_to(self, name: str):
        self.current_scene = self.scenes.get(name)
