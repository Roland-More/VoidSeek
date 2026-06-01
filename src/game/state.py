from core.scene import Scene
from .input import InputState
from .ecs import World
from .components import Position, Rotation, Velocity, PlayerController, Sprite, Interactible, Vent, TextureAnimator, TextureAnimation, TextEntity, FPSCounter
from .systems import PlayerInputSystem, MovementSystem, AnimatorSystem, InteractSystem, VentSystem, FPSSystem
from .map import MapManager
from .definitions import VentOrientation, PlaybackState, PlaybackMode, VentAnim, VENT_OFFSET, PLAYER_RADIUS, TIME_TO_OPEN_VENT
import math

class GameplayScene(Scene):
    def __init__(self, renderer, scene_manager, init_data: dict, tcp_socket=None):
        super().__init__(renderer)
        self.scene_manager = scene_manager
        self.tcp_socket = tcp_socket
        self.input = InputState()
        
        config = init_data["config"]
        self.player_speed = config["player_speed"]
        self.player_reach = config["player_reach"]
        self.player_radius = config["player_radius"]
        self.vent_open_time = config["vent_open_time"]

        self.map_manager = MapManager()
        self.map_manager.load_from_layout(init_data["map"]["layout"])

        self.my_player_id = None
        self.player_entity = None

        # Vytvor hráčov
        for p in init_data["players"]:
            entity = self.world.create_entity()
            self.world.add_component(entity, Position(p["x"], p["y"]))
            self.world.add_component(entity, Rotation(angle=0.0))
            self.world.add_component(entity, Velocity(speed=self.player_speed))
            
            # TODO: self.my_player_id sa nastaví po vytvorení triedy (pred štartom)
            # a potom by sme mali priradiť PlayerController. Dočasne zatiaľ uložím všetky.
            # Spravíme to tak, že controller sa pridá neskôr alebo cez nejakú funkciu.
            self.world.add_component(entity, Sprite(z=0.0, scale=1.0, is_visible=True, atlas_index_front=1, atlas_index_back=3))
            
            # Pomocná premenná
            p["entity_id"] = entity
            
        self._temp_players = init_data["players"]

        for v in init_data["vents"]:
            self.create_vent(int(v["x"]), int(v["y"]), True, VentOrientation(v["orientation"]))

        self.fps_entity = self.world.create_entity()
        self.world.add_component(self.fps_entity, TextEntity("FPS: 0", 1.0, 1.0, 0.1, (0.0, 1.0, 0.0, 1.0)))
        self.world.add_component(self.fps_entity, FPSCounter(timer=0.0, time_to_update=1.0))

    def create_vent(self, x: int, y: int, is_active: bool, orientation: VentOrientation):
        vent_center_x, vent_center_y = float(x) + 0.5, float(y) + 0.5
        
        pos_1, pos_2 = None, None
        if orientation == VentOrientation.VERTICAL:
            pos_1 = Position(vent_center_x, vent_center_y - 0.5 - self.player_radius - VENT_OFFSET)
            pos_2 = Position(vent_center_x, vent_center_y + 0.5 + self.player_radius + VENT_OFFSET)
        elif orientation == VentOrientation.HORIZONTAL:
            pos_1 = Position(vent_center_x - 0.5 - self.player_radius - VENT_OFFSET, vent_center_y)
            pos_2 = Position(vent_center_x + 0.5 + self.player_radius + VENT_OFFSET, vent_center_y)
            
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

    def on_enter(self):
        # Nájdi môjho hráča a priraď mu ovládanie
        for p in getattr(self, "_temp_players", []):
            if p["id"] == self.my_player_id:
                self.player_entity = p["entity_id"]
                self.world.add_component(self.player_entity, PlayerController())
                
                sprite = self.world.get_component(self.player_entity, Sprite)
                if sprite:
                    sprite.is_visible = False
                    
        self.renderer.set_cursor_locked(True)

    def on_exit(self):
        self.renderer.set_cursor_locked(False)

    def update(self, delta_time: float):
        import glfw
        window = self.renderer.canvas._window
        
        # Uisti sa, že je myš uzamknutá
        if not getattr(self, "_mouse_unlocked", False):
            if glfw.get_input_mode(window, glfw.CURSOR) != glfw.CURSOR_DISABLED:
                glfw.set_input_mode(window, glfw.CURSOR, glfw.CURSOR_DISABLED)
                
            # Čítanie raw pohybu myši
            current_x, current_y = glfw.get_cursor_pos(window)
            if not hasattr(self, "_last_mouse_pos"):
                self._last_mouse_pos = (current_x, current_y)
                
            dx = current_x - self._last_mouse_pos[0]
            self._last_mouse_pos = (current_x, current_y)
            
            if dx != 0.0:
                self.input.mouse_dx += dx
        else:
            if glfw.get_input_mode(window, glfw.CURSOR) != glfw.CURSOR_NORMAL:
                glfw.set_input_mode(window, glfw.CURSOR, glfw.CURSOR_NORMAL)

        PlayerInputSystem.update(self.world, self.input)
        MovementSystem.update(self.world, delta_time, self.map_manager.walls, self.input, self.player_radius)
        AnimatorSystem.update(self.world, delta_time, self.map_manager)
        InteractSystem.update(self.world, self.input, self.player_entity, self.map_manager.walls, self.player_reach)
        VentSystem.update(self.world, delta_time, self.vent_open_time)
        FPSSystem.update(self.world, delta_time)

    def draw(self, encoder, target_view):
        # Synchronizácia mapy na GPU
        if self.map_manager.map_changed_flag:
            self.renderer.update_map(self.get_map_data())
            self.map_manager.map_changed_flag = False
            self.map_manager.dirty_tiles.clear()
        elif self.map_manager.dirty_tiles:
            for index, x, y, wall, floor, ceil in self.map_manager.dirty_tiles:
                self.renderer.update_map_tile(index, wall, floor, ceil)
            self.map_manager.dirty_tiles.clear()
        
        cam_x, cam_y, cam_angle = self.camera_pose()
        self.renderer.update_camera(cam_x, cam_y, cam_angle)

        self.renderer.update_sprites(self.world, cam_x, cam_y)
        
        self.renderer.update_text(self.world)
        self.renderer.update_ui_buffers(self.world)
        self.renderer.render_gameplay_scene(encoder, target_view)

    def handle_key_down(self, key: str):
        if key == "w":
            self.input.forward = True
        elif key == "s":
            self.input.backward = True
        elif key == "a":
            self.input.left = True
        elif key == "d":
            self.input.right = True
        elif key == "e":
            self.input.interact = True
            print("Interact key pressed")
        elif key == "Escape":
            self._mouse_unlocked = not getattr(self, "_mouse_unlocked", False)
            if not self._mouse_unlocked:
                import glfw
                window = self.renderer.canvas._window
                current_x, current_y = glfw.get_cursor_pos(window)
                self._last_mouse_pos = (current_x, current_y)

    def handle_key_up(self, key: str):
        if key == "w":
            self.input.forward = False
        elif key == "s":
            self.input.backward = False
        elif key == "a":
            self.input.left = False
        elif key == "d":
            self.input.right = False

    def camera_pose(self) -> tuple[float, float, float]:
        pos = self.world.get_component(self.player_entity, Position)
        rot = self.world.get_component(self.player_entity, Rotation)
        if pos and rot:
            return (pos.x, pos.y, rot.angle)
        return (0.0, 0.0, 0.0)

    def get_map_data(self) -> list[int]:
        return self.map_manager.get_map_data()