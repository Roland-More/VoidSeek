from .input import InputState
from .ecs import World
from .components import Position, Rotation, Velocity, PlayerController, Sprite, Interactible
from .systems import PlayerInputSystem, MovementSystem
from .map import MapManager
from .definitions import VentOrientation

class GameState:
    def __init__(self):
        self.world = World()
        self.input = InputState()  # Stály odkaz na globálny vstup kvôli renderer.py
        
        # Oživenie ENTITY cez ECS namiesto zviazanej triedy "Player"
        self.player_entity = self.world.create_entity()
        self.world.add_component(self.player_entity, Position(x=1.5, y=1.5))
        self.world.add_component(self.player_entity, Rotation(angle=0.0))
        self.world.add_component(self.player_entity, Velocity(speed=1.95))
        self.world.add_component(self.player_entity, PlayerController())

        # Príklad vytvorenia spritu v state.py
        self.barrel_entity = self.world.create_entity()
        # Súradnice spritu posielame v mapových jednotkách (napr. stred políčka 1.5, 6.5)
        self.world.add_component(self.barrel_entity, Position(x=1.5, y=6.5))
        self.world.add_component(self.barrel_entity, Sprite(z=0.0, scale=1.0, atlas_index=1))

        self.map_manager = MapManager()
        layout = [
            "11111111",
            "10100001",
            "10101101",
            "101V1001",
            "10001001",
            "10111001",
            "10000001",
            "11111111",
        ]
        self.map_manager.load_from_layout(layout, self)

    def create_vent(self, x: int, y: int, is_active: bool, orientation: VentOrientation):
        vent_entity = self.world.create_entity()
        self.world.add_component(vent_entity, Position(float(x), float(y)))
        
        callback = self.create_open_vent_callback(x, y, vent_entity)
        self.world.add_component(vent_entity, Interactible(enabled=is_active, on_interact=callback))

    def create_open_vent_callback(self, x: int, y: int, entity_id: int):
        def callback():
            print(f"Opening vent at {x}, {y}!")
        return callback

    def start(self):
        PlayerInputSystem.update(self.world, self.input)

    def update(self, delta_time: float):
        PlayerInputSystem.update(self.world, self.input)
        MovementSystem.update(self.world, delta_time, self.map_manager.walls, self.input)

    def camera_pose(self) -> tuple[float, float, float]:
        pos = self.world.get_component(self.player_entity, Position)
        rot = self.world.get_component(self.player_entity, Rotation)
        if pos and rot:
            return (pos.x, pos.y, rot.angle)
        return (0.0, 0.0, 0.0)

    def get_map_data(self) -> list[int]:
        return self.map_manager.get_map_data()