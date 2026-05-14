from .input import InputState
from .ecs import World
from .components import Position, Rotation, Velocity, PlayerController
from .systems import PlayerInputSystem, MovementSystem

class GameState:
    def __init__(self):
        self.world = World()
        self.input = InputState()  # Stály odkaz na globálny vstup kvôli renderer.py
        
        # Oživenie ENTITY cez ECS namiesto zviazanej triedy "Player"
        self.player_entity = self.world.create_entity()
        self.world.add_component(self.player_entity, Position(x=96.0, y=96.0))
        self.world.add_component(self.player_entity, Rotation(angle=0.0))
        self.world.add_component(self.player_entity, Velocity(speed=125.0))
        self.world.add_component(self.player_entity, PlayerController())
        self.world.add_component(self.player_entity, self.input)
        
        self.map_walls = [
            1,1,1,1,1,1,1,1,
            1,0,1,0,0,0,0,1,
            1,0,1,0,1,1,0,1,
            1,0,1,0,1,0,0,1,
            1,0,0,0,1,0,0,1,
            1,0,1,1,1,0,0,1,
            1,0,0,0,0,0,0,1,
            1,1,1,1,1,1,1,1,
        ]
        self.map_floor = [
            0,0,0,0,0,0,0,0,
            0,2,0,2,2,2,2,0,
            0,2,0,2,0,0,2,0,
            0,2,0,2,0,2,2,0,
            0,2,2,2,0,2,2,0,
            0,2,0,0,0,2,2,0,
            0,2,2,2,2,2,2,2,
            0,0,0,0,0,0,0,0,
        ]
        self.map_ceiling = [
            0,0,0,0,0,0,0,0,
            0,3,0,3,3,3,3,0,
            0,3,0,3,0,0,3,0,
            0,3,0,3,0,3,3,0,
            0,3,3,3,0,3,3,0,
            0,3,0,0,0,3,3,0,
            0,3,3,3,3,3,3,3,
            0,0,0,0,0,0,0,0,
        ]

    def start(self):
        PlayerInputSystem.update(self.world)

    def update(self, delta_time: float):
        PlayerInputSystem.update(self.world)
        MovementSystem.update(self.world, delta_time, self.map_walls)

    def camera_pose(self) -> tuple[float, float, float]:
        pos = self.world.get_component(self.player_entity, Position)
        rot = self.world.get_component(self.player_entity, Rotation)
        if pos and rot:
            return (pos.x, pos.y, rot.angle)
        return (0.0, 0.0, 0.0)

    def get_map_data(self) -> list[int]:
        map_data = []
        for i in range(len(self.map_walls)):
            map_data.append(self.map_walls[i])
            map_data.append(self.map_floor[i])
            map_data.append(self.map_ceiling[i])
            map_data.append(0)
        return map_data