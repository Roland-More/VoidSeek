from core.scene import Scene
from .input import InputState
from .ecs import World
from .components import Position, Rotation, Velocity, PlayerController, Sprite, Interactible, Vent, TextureAnimator, TextureAnimation, TextEntity, FPSCounter, NetworkIdentity
from .systems import PlayerInputSystem, MovementSystem, AnimatorSystem, InteractSystem, VentSystem, FPSSystem
from .map import MapManager
from .definitions import VentOrientation, PlaybackState, PlaybackMode, VentAnim, VENT_OFFSET, PLAYER_RADIUS, TIME_TO_OPEN_VENT
import math
import socket
import numpy as np
from shared.protocol import encode_message, decode_messages, encode_udp, decode_udp
from core.backend.definitions import RENDER_WIDTH, RENDER_HEIGHT

class GameplayScene(Scene):
    def __init__(self, renderer, scene_manager, init_data: dict, tcp_socket=None, pending_messages=None, recv_buffer=b""):
        super().__init__(renderer)
        self.scene_manager = scene_manager
        self.tcp_socket = tcp_socket
        self.input = InputState()
        
        if self.tcp_socket:
            self.tcp_socket.setblocking(False)
        self.recv_buffer = recv_buffer
        self._pending_messages = pending_messages or []
        self.server_tick = 0
        self.my_role = None
        self.network_entities = {}
        self.attack_cooldown = 0.0
        self.is_dead = False
        self.has_key = False
        self.is_portal_open = False
        self.portal_entity = None
        self.portal_pos = None
        self.spectate_target_id = None
        self.attack_queue = []
        self.target_positions = {}
        self.target_angles = {}
        self._missing_ticks: dict[int, int] = {}  # pid -> počet tickov bez správy
        
        # Vytvor UDP socket
        self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_socket.bind(("0.0.0.0", 0))
        self.udp_socket.setblocking(False)
        self.udp_port = self.udp_socket.getsockname()[1]
        
        if self.tcp_socket:
            server_ip = self.tcp_socket.getpeername()[0]
            self.server_udp_address = (server_ip, init_data.get("game_udp_port", 5009))
            
            # Zaregistruj UDP port na serveri
            register_msg = {"type": "udp_register", "udp_port": self.udp_port}
            self.tcp_socket.sendall(encode_message(register_msg))
        else:
            self.server_udp_address = None
            
        config = init_data["config"]
        self.player_speed = config["player_speed"]
        self.player_reach = config["player_reach"]
        self.player_radius = config["player_radius"]
        self.vent_open_time = config["vent_open_time"]

        self.map_manager = MapManager()
        self.map_manager.width = init_data["map"].get("width", 64)
        self.map_manager.height = init_data["map"].get("height", 64)
        self.map_manager.load_from_layout(init_data["map"]["layout"])
        self.renderer.update_map_settings(self.map_manager.width, self.map_manager.height, 64, 5)

        self.my_player_id = None
        self.player_entity = None
        self.key_entities_3d: list = []  # Všetky 3D kľúče na scéne

        # Vytvor hráčov
        for p in init_data["players"]:
            entity = self.world.create_entity()
            self.world.add_component(entity, Position(p["x"], p["y"]))
            self.world.add_component(entity, Rotation(angle=math.pi / 2.0))
            vel_speed = self.player_speed * 1.25 if p.get("role") == "seeker" else self.player_speed
            self.world.add_component(entity, Velocity(speed=vel_speed))
            self.world.add_component(entity, NetworkIdentity(player_id=p["id"], role=p.get("role", "runner")))
            
            # TODO: self.my_player_id sa nastaví po vytvorení triedy (pred štartom)
            # a potom by sme mali priradiť PlayerController. Dočasne zatiaľ uložím všetky.
            # Spravíme to tak, že controller sa pridá neskôr alebo cez nejakú funkciu.
            self._setup_sprite(entity, p.get("role", "runner"))
            
            # Pomocná premenná a mapovanie
            p["entity_id"] = entity
            self.network_entities[p["id"]] = entity
            
        self._temp_players = init_data["players"]

        for v in init_data["vents"]:
            self.create_vent(int(v["x"]), int(v["y"]), True, VentOrientation(v["orientation"]))

        for y, row in enumerate(init_data["map"]["layout"]):
            for x, char in enumerate(row):
                if char == 'P':
                    self.portal_pos = (float(x) + 0.5, float(y) + 0.5)
                    portal_ent = self.world.create_entity()
                    self.world.add_component(portal_ent, Position(*self.portal_pos))
                    self.world.add_component(portal_ent, Rotation(angle=0.0))
                    self.world.add_component(portal_ent, Sprite(is_visible=True, atlas_index_front=48, atlas_index_back=48))
                    self.portal_entity = portal_ent
                elif char == 'K':
                    key_ent = self.world.create_entity()
                    self.world.add_component(key_ent, Position(float(x) + 0.5, float(y) + 0.5))
                    self.world.add_component(key_ent, Rotation(angle=0.0))
                    self.world.add_component(key_ent, Sprite(is_visible=True, atlas_index_front=50, atlas_index_back=50))
                    # Sledujeme všetky kľúče v zozname (nie len posledný)
                    if not hasattr(self, 'key_entities_3d'):
                        self.key_entities_3d = []
                    self.key_entities_3d.append(key_ent)

        self.fps_entity = self.world.create_entity()
        self.world.add_component(self.fps_entity, TextEntity("FPS: 0", 1.0, 1.0, 0.1, (0.0, 1.0, 0.0, 1.0)))
        self.world.add_component(self.fps_entity, FPSCounter(timer=0.0, time_to_update=1.0))
        
        self.role_entity = self.world.create_entity()
        self.world.add_component(self.role_entity, TextEntity(
            text="",
            x=RENDER_WIDTH / 2,
            y=10.0,
            size=0.5,
            color=(1.0, 1.0, 1.0, 1.0),
            alignment="center"
        ))

    def _setup_sprite(self, entity, role):
        from .components import SpriteAnimator, SpriteAnimation, Sprite
        if role == "seeker":
            idle_front, idle_back = 29, 12
            walk_front = [21, 22, 23, 24, 25, 26, 27, 28]
            walk_back = [4, 5, 6, 7, 8, 9, 10, 11]
            animations = {
                "walking": SpriteAnimation(frames_front=walk_front, frames_back=walk_back, frame_duration=0.1, playback_mode=PlaybackMode.LOOP),
                "attack": SpriteAnimation(frames_front=[13, 14, 15, 16, 17, 18, 19, 20, 29], frames_back=[12]*9, frame_duration=0.08, playback_mode=PlaybackMode.ONCE)
            }
        else:
            idle_front, idle_back = 30, 31
            walk_front = [32, 33, 34, 35, 36, 37, 38, 39]
            walk_back = [40, 41, 42, 43, 44, 45, 46, 47]
            animations = {
                "walking": SpriteAnimation(frames_front=walk_front, frames_back=walk_back, frame_duration=0.1, playback_mode=PlaybackMode.LOOP)
            }
        self.world.add_component(entity, Sprite(z=0.0, scale=1.0, is_visible=True, atlas_index_front=idle_front, atlas_index_back=idle_back))
        self.world.add_component(entity, SpriteAnimator(
            animations=animations,
            current_animation="walking",
            current_frame=0,
            timer=0.0,
            playback_state=PlaybackState.STOPPED
        ))

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
        if getattr(self, 'my_role', 'runner') == "seeker":
            return
            
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
                self.my_role = p.get("role")
                self.world.add_component(self.player_entity, PlayerController())
                
                sprite = self.world.get_component(self.player_entity, Sprite)
                if sprite:
                    sprite.is_visible = False
                    
        self._update_role_hud()
        self.renderer.set_cursor_locked(True)

    def on_exit(self):
        if getattr(self, "udp_socket", None):
            try:
                self.udp_socket.close()
            except:
                pass
        self.renderer.set_cursor_locked(False)

    def handle_pointer_down(self, event):
        if getattr(self, 'is_dead', False):
            if event.get("button", 1) == 1:
                self._switch_spectate_target(1)
            elif event.get("button", 1) == 2 or event.get("button", 1) == 3:
                self._switch_spectate_target(-1)
            return

        if event.get("button", 1) != 1:
            return
        if not getattr(self, 'is_paused', False):
            self.attack_queue.append(True)

    def handle_key_down(self, key: str):
        if key == "escape":
            self.is_paused = not getattr(self, 'is_paused', False)
            self.renderer.set_cursor_locked(not self.is_paused)
            if self.is_paused:
                self._show_pause_menu()
            else:
                self._hide_pause_menu()
            return True
            
        if getattr(self, 'is_paused', False):
            return
            
        if getattr(self, 'is_dead', False):
            if key == "a":
                self._switch_spectate_target(-1)
            elif key == "d":
                self._switch_spectate_target(1)
            return
            
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

    def _show_pause_menu(self):
        from core.backend.definitions import RENDER_WIDTH, RENDER_HEIGHT
        from game.components import UIPosition, UISprite, UIButton
        
        center_x = RENDER_WIDTH / 2
        center_y = RENDER_HEIGHT / 2
        self.pause_entities = []
        
        bg = self.world.create_entity()
        self.world.add_component(bg, UIPosition(x=center_x - 100, y=center_y - 100, width=200, height=200, z_index=10))
        self.world.add_component(bg, UISprite(color=(0.1, 0.1, 0.1, 0.9), use_texture=False))
        self.pause_entities.append(bg)
        
        btn_resume = self.world.create_entity()
        self.world.add_component(btn_resume, UIPosition(x=center_x - 90, y=center_y - 80, width=180, height=40, z_index=11))
        self.world.add_component(btn_resume, UIButton(
            text="RESUME",
            on_click=self._resume_game,
            color_normal=(0.3, 0.0, 0.0, 1.0),
            color_hover=(0.5, 0.0, 0.0, 1.0)
        ))
        self.pause_entities.append(btn_resume)
        
        btn_fs = self.world.create_entity()
        self.world.add_component(btn_fs, UIPosition(x=center_x - 90, y=center_y - 20, width=180, height=40, z_index=11))
        self.world.add_component(btn_fs, UIButton(
            text="FULLSCREEN",
            on_click=self.renderer.toggle_fullscreen,
            color_normal=(0.3, 0.0, 0.0, 1.0),
            color_hover=(0.5, 0.0, 0.0, 1.0)
        ))
        self.pause_entities.append(btn_fs)
        
        btn_quit = self.world.create_entity()
        self.world.add_component(btn_quit, UIPosition(x=center_x - 90, y=center_y + 40, width=180, height=40, z_index=11))
        self.world.add_component(btn_quit, UIButton(
            text="QUIT",
            on_click=self._handle_disconnect,
            color_normal=(0.3, 0.0, 0.0, 1.0),
            color_hover=(0.5, 0.0, 0.0, 1.0)
        ))
        self.pause_entities.append(btn_quit)

    def _resume_game(self):
        self.is_paused = False
        self.renderer.set_cursor_locked(True)
        self._hide_pause_menu()
        
    def _hide_pause_menu(self):
        if hasattr(self, 'pause_entities'):
            for e in self.pause_entities:
                self.world.destroy_entity(e)
            self.pause_entities.clear()

    def update(self, delta_time: float):
        # 1. PRIJMI správy zo servera
        self._recv_udp()
        self._recv_tcp()

        from .components import SpriteAnimator, Sprite
        animator = self.world.get_component(self.player_entity, SpriteAnimator) if self.player_entity else None
        
        if getattr(self, 'attack_cooldown', 0.0) > 0.0:
            self.attack_cooldown -= delta_time
            if self.attack_cooldown < 0.0:
                self.attack_cooldown = 0.0
                
        import copy
        input_to_system = copy.copy(self.input)
        
        if getattr(self, 'is_paused', False):
            input_to_system.forward = False
            input_to_system.backward = False
            input_to_system.left = False
            input_to_system.right = False
            input_to_system.mouse_dx = 0.0
            
        if self.attack_queue:
            if self.my_role == "seeker" and self.player_entity is not None:
                from .components import SpriteAnimator as _SpriteAnimator
                animator = self.world.get_component(self.player_entity, _SpriteAnimator)
                if animator and self.attack_cooldown <= 0.0:
                    self.attack_queue.clear()
                    animator.current_animation = "attack"
                    animator.playback_state = PlaybackState.PLAYING
                    animator.current_frame = 0
                    animator.timer = 0.0
                    self.attack_cooldown = 1.5
                    if self.tcp_socket:
                        try:
                            self.tcp_socket.sendall(encode_message({"type": "player_request", "action": "attack"}))
                        except OSError:
                            self._handle_disconnect()
            else:
                self.attack_queue.clear()
            
        is_attack_frozen = getattr(self, 'attack_cooldown', 0.0) > (1.5 - 0.72) # Prvých 0.72s sa nemoze hybat
            
        if is_attack_frozen:
            input_to_system.forward = False
            input_to_system.backward = False
            input_to_system.left = False
            input_to_system.right = False
            
        if animator and not is_attack_frozen:
            is_moving = input_to_system.forward or input_to_system.backward or input_to_system.left or input_to_system.right
            if is_moving:
                if animator.playback_state != PlaybackState.PLAYING or animator.current_animation != "walking":
                    animator.current_animation = "walking"
                    animator.playback_state = PlaybackState.PLAYING
                    animator.current_frame = 0
                    animator.timer = 0.0
            else:
                animator.playback_state = PlaybackState.STOPPED
                animator.current_frame = 0
                sprite = self.world.get_component(self.player_entity, Sprite)
                if sprite:
                    sprite.atlas_index_front = 29 if self.my_role == "seeker" else 30
                    sprite.atlas_index_back = 12 if self.my_role == "seeker" else 31

        if not getattr(self, 'is_dead', False):
            # 2. LOKÁLNA PREDIKCIA pohybu
            PlayerInputSystem.update(self.world, input_to_system)
            MovementSystem.update(self.world, delta_time, self.map_manager, input_to_system, self.player_radius)
            
            # 3. ODOŠLI input na server cez UDP
            self._send_input_udp(input_to_system)
            
            # UI pre vent / portal
            ui_text = ""  # vždy definovaná, aj pre seekera
            if getattr(self, 'my_role', 'runner') != "seeker":
                pos = self.world.get_component(self.player_entity, Position)
                rot = self.world.get_component(self.player_entity, Rotation)
                if pos and rot:
                    from game.systems import _dda_raycast
                    hit_mx, hit_my, hit_dist = _dda_raycast(
                        pos.x, pos.y, math.cos(rot.angle), math.sin(rot.angle),
                        self.map_manager.walls, self.map_manager.width, self.map_manager.height, self.player_reach
                    )
                    
                    portal_interact = False
                    
                    if self.portal_pos:
                        dist_to_portal = math.dist((pos.x, pos.y), self.portal_pos)
                        # Použij aj raycast – ak runner mieri priamo na portálový tile,
                        # detekuj ho aj keď stred tilu je mierne ďalej (napr. pri rohu).
                        portal_tile_x = int(self.portal_pos[0])
                        portal_tile_y = int(self.portal_pos[1])
                        portal_in_sight = (
                            hit_mx == portal_tile_x and hit_my == portal_tile_y
                        )
                        if dist_to_portal < 0.55 or portal_in_sight:
                            if not self.is_portal_open and self.has_key:
                                ui_text = "Press E to unlock door"
                                portal_interact = True
                            elif self.is_portal_open:
                                ui_text = "Press E to enter"
                                portal_interact = True
                    
                    if not portal_interact and hit_mx >= 0 and hit_my >= 0:
                        for entity, (v_pos, vent_comp) in self.world.get_components(Position, Vent):
                            if int(v_pos.x) == int(hit_mx) and int(v_pos.y) == int(hit_my):
                                if vent_comp.is_open:
                                    ui_text = "Press E to vent"
                                    self.last_hit_vent = (int(hit_mx), int(hit_my))
                                else:
                                    time_left = max(0, vent_comp.time_to_open - vent_comp.timer)
                                    ui_text = f"Wait {int(round(time_left))}s"
                                break
                                
                if not hasattr(self, 'interaction_text_entity'):
                    self.interaction_text_entity = self.world.create_entity()
                    self.world.add_component(self.interaction_text_entity, TextEntity(
                        text="", x=RENDER_WIDTH/2, y=RENDER_HEIGHT/2 + 50, size=0.4, color=(1.0, 1.0, 1.0, 1.0), alignment="center"
                    ))
                text_comp = self.world.get_component(self.interaction_text_entity, TextEntity)
                if text_comp:
                    text_comp.text = ui_text
                        
            # 4. Ak E stlačené → pošli player_request cez TCP
            if self.input.interact:
                if ui_text == "Press E to unlock door" or ui_text == "Press E to enter":
                    self._send_portal_request()
                elif ui_text == "Press E to vent" and hasattr(self, 'last_hit_vent'):
                    self._send_vent_request(self.last_hit_vent[0], self.last_hit_vent[1])
                self.input.interact = False
        else:
            # Ak sme dead, môžeme aspoň vypísať koho spectatujeme do stredu dole
            ui_text = ""
            if self.spectate_target_id is not None:
                ui_text = f"SPECTATING"
            
            if not hasattr(self, 'interaction_text_entity'):
                self.interaction_text_entity = self.world.create_entity()
                self.world.add_component(self.interaction_text_entity, TextEntity(
                    text="", x=RENDER_WIDTH/2, y=RENDER_HEIGHT/2 + 50, size=0.4, color=(1.0, 1.0, 1.0, 1.0), alignment="center"
                ))
            text_comp = self.world.get_component(self.interaction_text_entity, TextEntity)
            if text_comp:
                text_comp.text = ui_text

        # Interpolate remote players – plynulý pohyb medzi serverovými pozíciami
        interp_speed = 12.0
        for pid, (tx, ty) in getattr(self, 'target_positions', {}).items():
            if pid != self.my_player_id and pid in self.network_entities:
                ent = self.network_entities[pid]
                pos = self.world.get_component(ent, Position)
                rot = self.world.get_component(ent, Rotation)
                if pos:
                    dx = tx - pos.x
                    dy = ty - pos.y
                    dist_sq = dx * dx + dy * dy
                    if dist_sq > 9.0:  # > 3 bloky = teleport
                        pos.x = tx
                        pos.y = ty
                    else:
                        t = min(1.0, interp_speed * delta_time)
                        pos.x += dx * t
                        pos.y += dy * t
                # Interpolácia rotácie
                if rot and pid in self.target_angles:
                    target_a = self.target_angles[pid]
                    diff = target_a - rot.angle
                    # Normalizácia na [-pi, pi]
                    while diff > math.pi: diff -= 2.0 * math.pi
                    while diff < -math.pi: diff += 2.0 * math.pi
                    rot.angle += diff * min(1.0, interp_speed * delta_time)
        
        # 5. Ostatné systémy
        AnimatorSystem.update(self.world, delta_time, self.map_manager)
        VentSystem.update(self.world, delta_time, self.vent_open_time)
        FPSSystem.update(self.world, delta_time)
        
        self.input.mouse_dx = 0.0

    def _recv_udp(self):
        """Prijmi game_state pakety cez UDP. Spracuj len najnovší (podľa tick čísla)."""
        if not self.udp_socket:
            return
        latest_msg = None
        while True:
            try:
                data, addr = self.udp_socket.recvfrom(4096)
                msg = decode_udp(data)
                if msg and msg.get("type") == "game_state":
                    msg_tick = msg.get("tick", 0)
                    if msg_tick >= self.server_tick:
                        self.server_tick = msg_tick
                        latest_msg = msg
            except BlockingIOError:
                break
        if latest_msg:
            self._apply_game_state(latest_msg)

    def _recv_tcp(self):
        """Prijmi spoľahlivé správy cez TCP (vent_update, role_assign)."""
        if not self.tcp_socket:
            return
            
        messages = list(getattr(self, '_pending_messages', []))
        if messages:
            self._pending_messages = []
            
        try:
            data = self.tcp_socket.recv(4096)
            if not data:
                self._handle_disconnect()
                return
            self.recv_buffer += data
        except BlockingIOError:
            pass
        except (ConnectionResetError, OSError):
            self._handle_disconnect()
            return
            
        new_msgs, self.recv_buffer = decode_messages(self.recv_buffer)
        messages.extend(new_msgs)
        
        for msg in messages:
            msg_type = msg.get("type")
            if msg_type == "player_attack":
                pid = msg.get("player_id")
                if pid != self.my_player_id:
                    ent = self.network_entities.get(pid)
                    if ent:
                        from .components import SpriteAnimator
                        anim = self.world.get_component(ent, SpriteAnimator)
                        if anim and "attack" in anim.animations:
                            anim.current_animation = "attack"
                            anim.playback_state = PlaybackState.PLAYING
                            anim.current_frame = 0
                            anim.timer = 0.0
            elif msg_type == "player_killed":
                pid = msg.get("player_id")
                if pid == self.my_player_id:
                    self.is_dead = True
                    sprite = self.world.get_component(self.player_entity, Sprite)
                    if sprite: sprite.is_visible = False
                else:
                    ent = self.network_entities.get(pid)
                    if ent:
                        sprite = self.world.get_component(ent, Sprite)
                        if sprite: sprite.is_visible = False
            elif msg_type == "game_over":
                winner = msg.get("winner")
                self.renderer.set_cursor_locked(False)
                if self.tcp_socket:
                    self.tcp_socket.close()
                if self.udp_socket:
                    self.udp_socket.close()
                from .end_menu import EndMenuScene
                self.scene_manager.register("end_menu", EndMenuScene(self.renderer, self.scene_manager, init_data={"winner": winner, "my_role": getattr(self, 'my_role', 'runner')}))
                self.scene_manager.switch_to("end_menu")
            elif msg_type == "key_removed":
                rx, ry = msg.get("x"), msg.get("y")
                if rx is not None and ry is not None:
                    for ent in list(self.key_entities_3d):
                        kpos = self.world.get_component(ent, Position)
                        if kpos and abs(kpos.x - rx) < 0.1 and abs(kpos.y - ry) < 0.1:
                            self.key_entities_3d.remove(ent)
                            try:
                                self.world.destroy_entity(ent)
                            except:
                                pass
                            break
                elif self.key_entities_3d:
                    ent = self.key_entities_3d.pop(0)
                    try:
                        self.world.destroy_entity(ent)
                    except:
                        pass
            elif msg_type == "key_picked":
                self.has_key = True
                rx, ry = msg.get("x"), msg.get("y")
                if rx is not None and ry is not None:
                    for ent in list(self.key_entities_3d):
                        kpos = self.world.get_component(ent, Position)
                        if kpos and abs(kpos.x - rx) < 0.1 and abs(kpos.y - ry) < 0.1:
                            self.key_entities_3d.remove(ent)
                            try:
                                self.world.destroy_entity(ent)
                            except:
                                pass
                            break
                elif self.key_entities_3d:
                    ent = self.key_entities_3d.pop(0)
                    try:
                        self.world.destroy_entity(ent)
                    except:
                        pass
                from game.components import UIPosition, UISprite
                self.key_ui_entity = self.world.create_entity()
                # Zobrazíme klúč vpravo hore
                self.world.add_component(self.key_ui_entity, UIPosition(x=RENDER_WIDTH - 80, y=20, width=64, height=64, z_index=10))
                self.world.add_component(self.key_ui_entity, UISprite(use_texture=True, atlas_index=50))
            elif msg_type == "portal_opened":
                self.is_portal_open = True
                if self.portal_entity:
                    sprite = self.world.get_component(self.portal_entity, Sprite)
                    if sprite:
                        sprite.atlas_index_front = 49
                        sprite.atlas_index_back = 49
            elif msg_type == "player_escaped":
                pid = msg.get("player_id")
                if pid == self.my_player_id:
                    self.is_dead = True # Znefunkční pohyb
                    sprite = self.world.get_component(self.player_entity, Sprite)
                    if sprite: sprite.is_visible = False
                else:
                    ent = self.network_entities.get(pid)
                    if ent:
                        sprite = self.world.get_component(ent, Sprite)
                        if sprite: sprite.is_visible = False
            elif msg_type == "role_assign":
                self.my_role = msg.get("role")
                self._update_role_hud()
            elif msg_type == "vent_update":
                vent_x = msg.get("vent_x")
                vent_y = msg.get("vent_y")
                is_open = msg.get("is_open")
                
                for entity, (pos, vent_comp) in self.world.get_components(Position, Vent):
                    if abs(pos.x + 0.5 - vent_x) < 0.1 and abs(pos.y + 0.5 - vent_y) < 0.1:
                        vent_comp.is_open = is_open
                        vent_comp.timer = 0.0
                        animator = self.world.get_component(entity, TextureAnimator)
                        if animator:
                            if is_open:
                                animator.current_animation = ("Vent", VentAnim.OPENING)
                            else:
                                animator.current_animation = ("Vent", VentAnim.CLOSING)
                            animator.playback_state = PlaybackState.PLAYING
                            animator.current_frame = 0
                            animator.timer = 0.0
                        break

    def _send_input_udp(self, inp=None):
        """Odošli aktuálny input na server cez UDP."""
        if not self.udp_socket or not self.server_udp_address:
            return
        if inp is None: inp = self.input
        rot = self.world.get_component(self.player_entity, Rotation)
        input_msg = {
            "type": "player_input",
            "id": self.my_player_id,
            "forward": inp.forward,
            "backward": inp.backward,
            "left": inp.left,
            "right": inp.right,
            "angle": rot.angle if rot else 0.0
        }
        try:
            raw = encode_udp(input_msg)
            self.udp_socket.sendto(raw, self.server_udp_address)
        except OSError:
            pass

    def _apply_game_state(self, msg):
        """Aplikuj server game_state – aktualizuj pozície, rotácie a existenciu hráčov."""
        players_in_msg = set()
        
        for p in msg.get("players", []):
            pid = p["id"]
            players_in_msg.add(pid)
            entity = self.network_entities.get(pid)
            
            if entity is None:
                # Nový hráč (pripojil sa počas hry)
                entity = self.world.create_entity()
                self.world.add_component(entity, Position(p["x"], p["y"]))
                self.world.add_component(entity, Rotation(angle=p.get("angle", math.pi / 2.0)))
                # Vzdialený hráč je vždy viditeľný
                self._setup_sprite(entity, p.get("role", "runner"))
                self.world.add_component(entity, NetworkIdentity(player_id=pid, role=p.get("role", "runner")))
                self.network_entities[pid] = entity
            else:
                # Aktualizuj existujúceho hráča
                pos = self.world.get_component(entity, Position)
                rot = self.world.get_component(entity, Rotation)
                if pos and rot:
                    if pid == self.my_player_id:
                        # Server je autorita – priamo nastav pozíciu bez predikcie
                        pos.x = p["x"]
                        pos.y = p["y"]
                    else:
                        from .components import SpriteAnimator
                        
                        target_x, target_y = p["x"], p["y"]
                        old_target = self.target_positions.get(pid)
                        self.target_positions[pid] = (target_x, target_y)
                        self.target_angles[pid] = p["angle"]
                        
                        # Animácia na základe pohybu
                        if old_target:
                            move_dist_sq = (target_x - old_target[0])**2 + (target_y - old_target[1])**2
                        else:
                            move_dist_sq = (pos.x - target_x)**2 + (pos.y - target_y)**2
                        
                        remote_animator = self.world.get_component(entity, SpriteAnimator)
                        if remote_animator and (remote_animator.current_animation != "attack" or remote_animator.playback_state != PlaybackState.PLAYING):
                            if move_dist_sq > 0.0001:
                                if remote_animator.current_animation != "walking" or remote_animator.playback_state != PlaybackState.PLAYING:
                                    remote_animator.current_animation = "walking"
                                    remote_animator.playback_state = PlaybackState.PLAYING
                            else:
                                remote_animator.playback_state = PlaybackState.STOPPED
                                remote_animator.current_frame = 0
                                remote_sprite = self.world.get_component(entity, Sprite)
                                if remote_sprite:
                                    remote_sprite.atlas_index_front = 29 if p.get("role") == "seeker" else 30
                                    remote_sprite.atlas_index_back = 12 if p.get("role") == "seeker" else 31
                    
        # Detekcia odpojených hráčov – tolerancia voči výpadku UDP paketu
        # Hráč sa zmaže až po MISSING_TICKS_THRESHOLD po sebe idúcich chýbajúcich tickoch
        MISSING_TICKS_THRESHOLD = 5
        for pid in list(self.network_entities):
            if pid == self.my_player_id:
                continue
            if pid not in players_in_msg:
                self._missing_ticks[pid] = self._missing_ticks.get(pid, 0) + 1
                if self._missing_ticks[pid] >= MISSING_TICKS_THRESHOLD:
                    entity = self.network_entities[pid]
                    self.world.destroy_entity(entity)
                    del self.network_entities[pid]
                    self._missing_ticks.pop(pid, None)
                    self.target_positions.pop(pid, None)
                    self.target_angles.pop(pid, None)
            else:
                self._missing_ticks.pop(pid, None)

    def _handle_disconnect(self):
        """Ošetrenie odpojenia od servera."""
        if self.tcp_socket:
            try: self.tcp_socket.close()
            except: pass
            self.tcp_socket = None
        if self.udp_socket:
            try: self.udp_socket.close()
            except: pass
            self.udp_socket = None
            
        if "game" in self.scene_manager.scenes:
            del self.scene_manager.scenes["game"]
            
        self.scene_manager.switch_to("server_list")

    def _send_vent_request(self, vent_x, vent_y):
        if getattr(self, 'my_role', 'runner') == "seeker":
            return
        if not self.tcp_socket:
            return

        pos = self.world.get_component(self.player_entity, Position)
        rot = self.world.get_component(self.player_entity, Rotation)
        if pos and rot:
            request = {
                "type": "player_request",
                "action": "vent_use",
                "vent_x": vent_x,
                "vent_y": vent_y,
                "px": pos.x, "py": pos.y,
                "angle": rot.angle
            }
            try:
                self.tcp_socket.sendall(encode_message(request))
            except OSError:
                self._handle_disconnect()
                
    def _send_portal_request(self):
        if not self.tcp_socket: return
        msg = {"type": "player_request", "id": self.my_player_id, "action": "interact_portal"}
        try:
            self.tcp_socket.sendall(encode_message(msg))
        except OSError:
            self._handle_disconnect()
                
    def _update_role_hud(self):
        text_comp = self.world.get_component(self.role_entity, TextEntity)
        if text_comp and self.my_role:
            if self.my_role == "seeker":
                text_comp.text = "SEEKER"
                text_comp.color = (1.0, 0.2, 0.2, 1.0)  # červená
            else:
                text_comp.text = "RUNNER"
                text_comp.color = (0.2, 1.0, 0.2, 1.0)  # zelená

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
            
    def handle_mouse_move(self, dx: float):
        if not getattr(self, 'is_paused', False):
            self.input.mouse_dx += dx

    def handle_key_up(self, key: str):
        if key == "w":
            self.input.forward = False
        elif key == "s":
            self.input.backward = False
        elif key == "a":
            self.input.left = False
        elif key == "d":
            self.input.right = False

    def _switch_spectate_target(self, direction: int):
        alive_pids = []
        for pid, ent in self.network_entities.items():
            if pid == self.my_player_id: continue
            sprite = self.world.get_component(ent, Sprite)
            if sprite and sprite.is_visible:
                alive_pids.append(pid)
                
        if not alive_pids:
            return
            
        alive_pids.sort()
        if self.spectate_target_id in alive_pids:
            idx = alive_pids.index(self.spectate_target_id)
            idx = (idx + direction) % len(alive_pids)
            self.spectate_target_id = alive_pids[idx]
        else:
            self.spectate_target_id = alive_pids[0]

    def camera_pose(self) -> tuple[float, float, float]:
        if getattr(self, 'is_dead', False):
            alive_pids = []
            for pid, ent in self.network_entities.items():
                if pid == self.my_player_id: continue
                sprite = self.world.get_component(ent, Sprite)
                if sprite and sprite.is_visible:
                    alive_pids.append(pid)
                    
            if alive_pids:
                alive_pids.sort()
                if self.spectate_target_id not in alive_pids:
                    self.spectate_target_id = alive_pids[0]
                    
                target_ent = self.network_entities.get(self.spectate_target_id)
                if target_ent:
                    t_pos = self.world.get_component(target_ent, Position)
                    t_rot = self.world.get_component(target_ent, Rotation)
                    if t_pos and t_rot:
                        return (t_pos.x, t_pos.y, t_rot.angle)
            else:
                self.spectate_target_id = None
                
        pos = self.world.get_component(self.player_entity, Position)
        rot = self.world.get_component(self.player_entity, Rotation)
        if pos and rot:
            return (pos.x, pos.y, rot.angle)
        return (0.0, 0.0, 0.0)

    def get_map_data(self) -> list[int]:
        return self.map_manager.get_map_data()