from .input import InputState
from .ecs import World
from .components import Position, Rotation, Velocity, PlayerController, Sprite, Interactible, Vent, TextureAnimator, TextureAnimation
from .systems import PlayerInputSystem, MovementSystem, AnimatorSystem, InteractSystem, VentSystem
from .map import MapManager
from .definitions import VentOrientation, PlaybackState, PlaybackMode, VentAnim, VENT_OFFSET, PLAYER_RADIUS, TIME_TO_OPEN_VENT
import math

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
        self.world.add_component(self.barrel_entity, Rotation(angle=0.0))
        self.world.add_component(self.barrel_entity, Sprite(z=0.0, scale=1.0, is_visible=True, atlas_index_front=1, atlas_index_back=3))

        self.map_manager = MapManager()
        layout = [
            "11111111",
            "1.1....1",
            "1.1.11.1",
            "1.1V1..1",
            "1...V..1",
            "1.111..1",
            "1......1",
            "11111111",
        ]
        self.map_manager.load_from_layout(layout, self)

    def create_vent(self, x: int, y: int, is_active: bool, orientation: VentOrientation):
        vent_center_x, vent_center_y = float(x) + 0.5, float(y) + 0.5
        
        pos_1, pos_2 = None, None
        if orientation == VentOrientation.VERTICAL:
            pos_1 = Position(vent_center_x, vent_center_y - 0.5 - PLAYER_RADIUS - VENT_OFFSET)
            pos_2 = Position(vent_center_x, vent_center_y + 0.5 + PLAYER_RADIUS + VENT_OFFSET)
        elif orientation == VentOrientation.HORIZONTAL:
            pos_1 = Position(vent_center_x - 0.5 - PLAYER_RADIUS - VENT_OFFSET, vent_center_y)
            pos_2 = Position(vent_center_x + 0.5 + PLAYER_RADIUS + VENT_OFFSET, vent_center_y)
            
        vent_entity = self.world.create_entity()
        self.world.add_component(vent_entity, Position(float(x), float(y)))
        
        if pos_1 and pos_2:
            self.world.add_component(vent_entity, Vent(
                is_open=True, 
                timer=0.0, 
                time_to_open=TIME_TO_OPEN_VENT, 
                orientation=orientation, 
                destinations=(pos_1, pos_2)
            ))
            
            closing = {
                'frames': [13, 12, 11, 10, 9, 8, 7, 6, 5, 4],
                'frame_duration': 0.05,
                'playback_mode': PlaybackMode.ONCE
            }
            opening = {
                'frames': [4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
                'frame_duration': 0.05,
                'playback_mode': PlaybackMode.ONCE
            }
            
            self.world.add_component(vent_entity, TextureAnimator(
                animations={
                    ("Vent", VentAnim.OPENING): TextureAnimation(**opening),
                    ("Vent", VentAnim.CLOSING): TextureAnimation(**closing)
                },
                current_animation=None,
                current_frame=0,
                timer=0.0,
                playback_state=PlaybackState.STOPPED,
                direction=None
            ))
        
        self.world.add_component(vent_entity, Interactible(enabled=is_active, on_interact=self.vent_hit))

    def vent_hit(self, world: World, player: int, entity: int):
        vent = world.get_component(entity, Vent)
        if not vent or not vent.is_open:
            return
            
        player_pos = world.get_component(player, Position)
        if not player_pos:
            return
            
        first_dist = math.sqrt((player_pos.x - vent.destinations[0].x)**2 + (player_pos.y - vent.destinations[0].y)**2)
        second_dist = math.sqrt((player_pos.x - vent.destinations[1].x)**2 + (player_pos.y - vent.destinations[1].y)**2)
        
        if first_dist < second_dist:
            player_pos.x = vent.destinations[1].x
            player_pos.y = vent.destinations[1].y
        else:
            player_pos.x = vent.destinations[0].x
            player_pos.y = vent.destinations[0].y
            
        vent.is_open = False
        animator = world.get_component(entity, TextureAnimator)
        if animator:
            animator.current_animation = ("Vent", VentAnim.CLOSING)
            animator.playback_state = PlaybackState.PLAYING
            animator.current_frame = 0
            animator.timer = 0.0

    def start(self):
        PlayerInputSystem.update(self.world, self.input)

    def update(self, delta_time: float):
        PlayerInputSystem.update(self.world, self.input)
        MovementSystem.update(self.world, delta_time, self.map_manager.walls, self.input)
        AnimatorSystem.update(self.world, delta_time, self.map_manager)
        InteractSystem.update(self.world, self.input, self.player_entity, self.map_manager.walls)
        VentSystem.update(self.world, delta_time)

    def camera_pose(self) -> tuple[float, float, float]:
        pos = self.world.get_component(self.player_entity, Position)
        rot = self.world.get_component(self.player_entity, Rotation)
        if pos and rot:
            return (pos.x, pos.y, rot.angle)
        return (0.0, 0.0, 0.0)

    def get_map_data(self) -> list[int]:
        return self.map_manager.get_map_data()