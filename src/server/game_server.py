import socket
import threading
import json
import time
import math
import numpy as np
import random
from numba import njit
from game.ecs import World
from game.components import ServerConfig, NetworkPlayer, Position, Rotation, Velocity, NetworkIdentity
from shared.protocol import encode_message, decode_messages, encode_udp, decode_udp
from game.map import MapManager
from game.definitions import VentOrientation, VENT_OFFSET, PLAYER_RADIUS
from game.systems import _is_wall, _dda_raycast

try:
    from game.components import Position
except ImportError:
    from dataclasses import dataclass
    @dataclass
    class Position:
        x: float
        y: float

@njit(cache=True)
def _server_move_players(
    positions,
    angles,
    speeds,
    inputs,
    attack_frozen,
    is_dead,
    walls,
    map_w, map_h,
    player_radius,
    tick_duration
):
    n = positions.shape[0]
    for i in range(n):
        if attack_frozen[i] or is_dead[i]:
            continue

        angle = angles[i]
        speed = speeds[i]

        dx = 0.0
        dy = 0.0

        cos_a = math.cos(angle)
        sin_a = math.sin(angle)

        if inputs[i, 0]:
            dx += cos_a * speed
            dy += sin_a * speed
        if inputs[i, 1]:
            dx -= cos_a * speed
            dy -= sin_a * speed
        if inputs[i, 2]:
            dx += math.cos(angle - math.pi / 2.0) * speed
            dy += math.sin(angle - math.pi / 2.0) * speed
        if inputs[i, 3]:
            dx += math.cos(angle + math.pi / 2.0) * speed
            dy += math.sin(angle + math.pi / 2.0) * speed

        if dx == 0.0 and dy == 0.0:
            continue

        length = math.sqrt(dx * dx + dy * dy)
        dx = (dx / length) * speed * tick_duration
        dy = (dy / length) * speed * tick_duration

        new_x = positions[i, 0] + dx
        new_y = positions[i, 1] + dy

        if not _is_wall(new_x, positions[i, 1], walls, map_w, map_h, player_radius):
            positions[i, 0] = new_x
        if not _is_wall(positions[i, 0], new_y, walls, map_w, map_h, player_radius):
            positions[i, 1] = new_y

_warmup_walls = np.zeros(64, dtype=np.int32)
_warmup_pos = np.zeros((1, 2), dtype=np.float64)
_warmup_angles = np.zeros(1, dtype=np.float64)
_warmup_speeds = np.ones(1, dtype=np.float64)
_warmup_inputs = np.zeros((1, 4), dtype=np.int32)
_warmup_frozen = np.zeros(1, dtype=np.bool_)
_warmup_dead = np.zeros(1, dtype=np.bool_)
_server_move_players(
    _warmup_pos, _warmup_angles, _warmup_speeds, _warmup_inputs,
    _warmup_frozen, _warmup_dead, _warmup_walls, 8, 8, 0.15, 0.05
)

_single_pos = np.zeros((1, 2), dtype=np.float64)
_single_angle = np.zeros(1, dtype=np.float64)
_single_speed = np.zeros(1, dtype=np.float64)
_single_inputs = np.zeros((1, 4), dtype=np.int32)
_single_frozen = np.zeros(1, dtype=np.bool_)
_single_dead = np.zeros(1, dtype=np.bool_)

class ClientConnection:
    def __init__(self, sock: socket.socket, address: tuple, player_entity: int, name: str, client_id: int):
        self.socket = sock
        self.address = address
        self.player_entity = player_entity
        self.name = name
        self.client_id = client_id
        self.is_ready = False
        self.recv_buffer = b""
        self.input_state = {"forward": False, "backward": False, "left": False, "right": False, "angle": None}
        self.pending_requests = []
        self.udp_address = None

class GameServer:
    def __init__(self, name: str, tcp_port: int, udp_port: int, max_players: int, map_size: int = 96):
        self.name = name
        self.tcp_port = tcp_port
        self.udp_port = udp_port
        self.max_players = max_players
        self.map_size = map_size

        self.world = World()
        self.config_entity = self.world.create_entity()
        self.world.add_component(self.config_entity, ServerConfig(
            name=name,
            max_players=max_players,
            player_speed=1.95,
            player_reach=1.5,
            player_radius=0.15,
            vent_open_time=45.0,
            tick_rate=20
        ))

        self.tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.tcp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.tcp_socket.bind(("0.0.0.0", self.tcp_port))
        self.tcp_socket.listen()

        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            self.local_ip = s.getsockname()[0]
            s.close()
        except Exception:
            self.local_ip = socket.gethostbyname(socket.gethostname())

        self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        ttl = 1
        self.udp_socket.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, ttl)
        self.udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self.udp_socket.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF, socket.inet_aton(self.local_ip))
        except Exception as e:
            print(f"[UDP] Nepodarilo sa nastaviť IP_MULTICAST_IF: {e}")

        self.game_udp_port = self.udp_port + 1
        self.game_udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.game_udp_socket.bind(("0.0.0.0", self.game_udp_port))
        self.game_udp_socket.setblocking(False)

        self.clients: list[ClientConnection] = []
        self._udp_client_map: dict[tuple, ClientConnection] = {}
        self._next_client_id = 0
        self.state = "lobby"
        self._running = False
        self.current_tick = 0
        self.vents = []
        self._tick_lock = threading.Lock()

    def _find_client_by_udp(self, addr):
        return self._udp_client_map.get(addr)

    def _process_player_instant(self, client, input_msg):
        if getattr(client, 'escaped', False) or getattr(client, 'is_dead', False):
            return

        pos = self.world.get_component(client.player_entity, Position)
        rot = self.world.get_component(client.player_entity, Rotation)
        vel = self.world.get_component(client.player_entity, Velocity)
        if not pos or not rot or not vel:
            return

        angle = input_msg.get("angle")
        if angle is not None:
            rot.angle = angle

        now = time.perf_counter()
        last = getattr(client, '_last_move_time', now)
        dt = now - last
        client._last_move_time = now

        if dt > 0.1:
            dt = 0.1
        if dt < 0.001:
            dt = 0.001

        if getattr(client, 'attack_timer', 0.0) > 0.0:
            client.attack_timer -= dt

        frozen = getattr(client, 'attack_timer', 0.0) > 0.0

        _single_pos[0, 0] = pos.x
        _single_pos[0, 1] = pos.y
        _single_angle[0] = rot.angle
        _single_speed[0] = vel.speed
        _single_inputs[0, 0] = int(input_msg.get("forward", False))
        _single_inputs[0, 1] = int(input_msg.get("backward", False))
        _single_inputs[0, 2] = int(input_msg.get("left", False))
        _single_inputs[0, 3] = int(input_msg.get("right", False))
        _single_frozen[0] = frozen
        _single_dead[0] = getattr(client, 'is_dead', False)

        walls_arr = self.map_manager.walls
        _server_move_players(
            _single_pos, _single_angle, _single_speed, _single_inputs,
            _single_frozen, _single_dead,
            walls_arr, self.map_manager.width, self.map_manager.height,
            self.world.get_component(self.config_entity, ServerConfig).player_radius, dt
        )

        pos.x = _single_pos[0, 0]
        pos.y = _single_pos[0, 1]

    def start_udp_broadcast(self):
        def broadcast_loop():
            while self._running:
                if self.state == "lobby":
                    payload = {
                        "name": self.name,
                        "tcp_host": self.local_ip,
                        "tcp_port": self.tcp_port,
                        "players": len(self.clients),
                        "max_players": self.max_players,
                        "map_size": self.map_size,
                        "state": self.state
                    }
                    message = json.dumps(payload).encode("utf-8")
                    try:
                        self.udp_socket.sendto(message, ("224.1.1.1", 5007))
                    except Exception as e:
                        pass

                time.sleep(2.0 if self.state == "lobby" else 5.0)

        thread = threading.Thread(target=broadcast_loop, daemon=True)
        thread.start()

    def start_tcp_listener(self):
        def listener_loop():
            while self._running:
                try:
                    client_sock, address = self.tcp_socket.accept()
                    print(f"[TCP] Nové pripojenie z {address}")

                    if len(self.clients) >= self.max_players or self.state != "lobby":
                        client_sock.close()
                        continue

                    client_id = self._next_client_id
                    self._next_client_id += 1
                    player_name = f"Player{client_id+1}"

                    entity = self.world.create_entity()
                    self.world.add_component(entity, NetworkPlayer(client_id, player_name))
                    self.world.add_component(entity, Position(x=0.0, y=0.0))

                    connection = ClientConnection(client_sock, address, entity, player_name, client_id)
                    self.clients.append(connection)

                    client_thread = threading.Thread(target=self._handle_client, args=(connection,), daemon=True)
                    client_thread.start()

                except Exception as e:
                    if self._running:
                        print(f"[TCP] Listener error: {e}")

        thread = threading.Thread(target=listener_loop, daemon=True)
        thread.start()

    def broadcast(self, msg: dict):
        data = encode_message(msg)
        for client in list(self.clients):
            try:
                client.socket.sendall(data)
            except Exception:
                self._disconnect_client(client)

    def build_player_list(self) -> dict:
        return {
            "type": "player_list",
            "players": [{"name": c.name, "ready": c.is_ready, "id": c.client_id} for c in self.clients]
        }

    def _handle_client_message(self, client: ClientConnection, msg: dict):
        msg_type = msg.get("type")
        if msg_type == "join":
            client.name = msg.get("name", client.name)
            player_comp = self.world.get_component(client.player_entity, NetworkPlayer)
            if player_comp:
                player_comp.name = client.name
            self.broadcast(self.build_player_list())

        elif msg_type == "ready":
            client.is_ready = msg.get("value", False)
            self.broadcast(self.build_player_list())

            if len(self.clients) >= 2 and all(c.is_ready for c in self.clients):
                print("[TCP] Všetci hráči pripravení! Štartujem hru...")
                self.state = "game"
                for i, c in enumerate(self.clients):
                    try:
                        c.socket.sendall(encode_message({"type": "game_start", "your_id": c.client_id}))
                    except Exception:
                        pass
                self.start_game()

        elif msg_type == "udp_register":
            udp_addr = (client.address[0], msg.get("udp_port"))
            client.udp_address = udp_addr
            self._udp_client_map[udp_addr] = client

        elif msg_type == "player_request":
            with self._tick_lock:
                client.pending_requests.append(msg)

    def _check_game_over(self):
        all_done = True
        has_runner = False
        any_escaped = False

        for c in self.clients:
            c_net = self.world.get_component(c.player_entity, NetworkIdentity)
            if c_net and c_net.role == "runner":
                has_runner = True
                if getattr(c, 'escaped', False):
                    any_escaped = True
                elif not getattr(c, 'is_dead', False):
                    all_done = False

        if has_runner and all_done:
            winner = "runner" if any_escaped else "seeker"
            self.broadcast({"type": "game_over", "winner": winner})
            self.state = "lobby"
            for c in self.clients:
                c.is_ready = False
            self.broadcast(self.build_player_list())

    def _handle_interact_portal(self, client):
        if getattr(client, 'assigned_role', 'runner') == "seeker":
            return
        if getattr(client, 'is_dead', False) or getattr(client, 'escaped', False):
            return

        pos = self.world.get_component(client.player_entity, Position)
        if not pos:
            return

        from game.components import Portal
        for portal_ent, (p_pos, portal) in self.world.get_components(Position, Portal):
            # Zväčšený threshold – pozícia sa môže mierne líšiť kvôli latencie TCP vs UDP
            if math.dist((pos.x, pos.y), (p_pos.x, p_pos.y)) < 0.55:
                if not portal.is_open:
                    if getattr(client, 'has_key', False):
                        portal.is_open = True
                        self.broadcast({"type": "portal_opened", "portal_x": p_pos.x, "portal_y": p_pos.y})
                else:
                    client.escaped = True
                    self.broadcast({"type": "player_escaped", "player_id": client.client_id})
                    self._check_game_over()

    def _handle_attack(self, attacker: ClientConnection):
        pos = self.world.get_component(attacker.player_entity, Position)
        rot = self.world.get_component(attacker.player_entity, Rotation)
        if not pos or not rot:
            return

        attacker_net = self.world.get_component(attacker.player_entity, NetworkIdentity)
        if not attacker_net or attacker_net.role != "seeker":
            return

        dir_x = math.cos(rot.angle)
        dir_y = math.sin(rot.angle)

        config = self.world.get_component(self.config_entity, ServerConfig)
        attack_dist = config.player_reach if config else 1.5
        attack_radius = 0.4

        walls_arr = self.map_manager.walls

        for victim in self.clients:
            if victim == attacker:
                continue
            v_net = self.world.get_component(victim.player_entity, NetworkIdentity)
            v_pos = self.world.get_component(victim.player_entity, Position)
            if v_net and v_net.role == "runner" and not getattr(victim, 'is_dead', False) and not getattr(victim, 'escaped', False):
                dx = v_pos.x - pos.x
                dy = v_pos.y - pos.y
                dist = math.sqrt(dx*dx + dy*dy)

                if dist <= 0.5:
                    if dist > 0.0:
                        hit_mx, hit_my, hit_dist = _dda_raycast(pos.x, pos.y, dx/dist, dy/dist, walls_arr, self.map_manager.width, self.map_manager.height, dist)
                        if hit_dist >= dist - 0.5:
                            victim.is_dead = True
                            self.broadcast({"type": "player_killed", "player_id": victim.client_id})
                    else:
                        victim.is_dead = True
                        self.broadcast({"type": "player_killed", "player_id": victim.client_id})

        self._check_game_over()

    def start_game(self):
        self.map_manager = MapManager()

        import os
        maps_filename = f"maps_{self.map_size}.json"
        maps_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), maps_filename)
        try:
            with open(maps_path, "r") as f:
                all_maps = json.load(f)
            original_layout = random.choice(all_maps)
            print(f"[Game] Na\u010d\u00edtan\u00e1 mapa {self.map_size}x{self.map_size} z {maps_filename}")
        except Exception as e:
            print(f"Chyba pri načítaní máp: {e}")
            original_layout = [
                "11111111",
                "1R1.KS.1",
                "1.1.11.1",
                "1P1V1..1",
                "1...V..1",
                "1.111..1",
                "1R....R1",
                "11111111"
            ]

        runner_spawns = []
        seeker_spawns = []
        key_spawns = []
        portal_spawns = []
        empty_spaces = []

        for y, row in enumerate(original_layout):
            for x, char in enumerate(row):
                if char == 'R':
                    runner_spawns.append((float(x) + 0.5, float(y) + 0.5))
                elif char == 'S':
                    seeker_spawns.append((float(x) + 0.5, float(y) + 0.5))
                elif char == 'K':
                    key_spawns.append((x, y))
                elif char == 'P':
                    portal_spawns.append((x, y))
                elif char == '.':
                    empty_spaces.append((x, y))

        if not runner_spawns: runner_spawns = [(1.5, 1.5)]
        if not seeker_spawns: seeker_spawns = [(6.5, 1.5)]

        random.shuffle(runner_spawns)
        random.shuffle(seeker_spawns)
        random.shuffle(key_spawns)
        random.shuffle(portal_spawns)
        random.shuffle(empty_spaces)

        seeker_idx = random.randint(0, len(self.clients) - 1) if self.clients else 0
        total_players = max(1, len(self.clients))
        num_runners = max(1, total_players - 1) if total_players > 1 else 1
        if len(self.clients) == 1 and seeker_idx == 0:
            num_runners = 0
            
        while len(runner_spawns) < num_runners and empty_spaces:
            ex, ey = empty_spaces.pop()
            runner_spawns.append((float(ex) + 0.5, float(ey) + 0.5))

        num_items = num_runners + 1
        
        # Zozbieraj použité pozície aby sa spawny neprekrývali
        used_positions = set()
        for sx, sy in runner_spawns:
            used_positions.add((int(sx - 0.5), int(sy - 0.5)))
        for sx, sy in seeker_spawns:
            used_positions.add((int(sx - 0.5), int(sy - 0.5)))
        
        # Vyber kľúče z dostupných, ktoré nie sú obsadené
        available_keys = [pos for pos in key_spawns if pos not in used_positions]
        selected_keys = []
        for pos in available_keys[:num_items]:
            selected_keys.append(pos)
            used_positions.add(pos)
        needed_keys = num_items - len(selected_keys)
        for _ in range(needed_keys):
            while empty_spaces:
                candidate = empty_spaces.pop()
                if candidate not in used_positions:
                    selected_keys.append(candidate)
                    used_positions.add(candidate)
                    break
                
        # Vyber portály z dostupných, ktoré nie sú obsadené
        available_portals = [pos for pos in portal_spawns if pos not in used_positions]
        selected_portals = []
        for pos in available_portals[:num_items]:
            selected_portals.append(pos)
            used_positions.add(pos)
        needed_portals = num_items - len(selected_portals)
        for _ in range(needed_portals):
            while empty_spaces:
                candidate = empty_spaces.pop()
                if candidate not in used_positions:
                    selected_portals.append(candidate)
                    used_positions.add(candidate)
                    break

        layout = []
        for y, row in enumerate(original_layout):
            new_row = ""
            for x, char in enumerate(row):
                if char in ['R', 'S']:
                    new_row += '.'
                elif char == 'K':
                    if (x, y) in selected_keys:
                        new_row += 'K'
                    else:
                        new_row += '.'
                elif char == 'P':
                    if (x, y) in selected_portals:
                        new_row += 'P'
                    else:
                        new_row += '.'
                else:
                    new_row += char
            layout.append(new_row)

        self.map_manager.load_from_layout(layout)

        for (x, y) in selected_keys:
            key_ent = self.world.create_entity()
            self.world.add_component(key_ent, Position(float(x) + 0.5, float(y) + 0.5))
            from game.components import Key
            self.world.add_component(key_ent, Key())

        for (x, y) in selected_portals:
            portal_ent = self.world.create_entity()
            self.world.add_component(portal_ent, Position(float(x) + 0.5, float(y) + 0.5))
            from game.components import Portal
            self.world.add_component(portal_ent, Portal(is_open=False))

        players_data = []
        runner_count = 0
        seeker_count = 0
        for i, client in enumerate(self.clients):
            role = "seeker" if i == seeker_idx else "runner"

            if role == "seeker":
                spawn_x, spawn_y = seeker_spawns[seeker_count % len(seeker_spawns)]
                seeker_count += 1
            else:
                spawn_x, spawn_y = runner_spawns[runner_count % len(runner_spawns)]
                runner_count += 1

            pos = self.world.get_component(client.player_entity, Position)
            if pos:
                pos.x = spawn_x
                pos.y = spawn_y

            from game.components import SphereCollider
            vel_speed = 1.95 * 1.25 if role == "seeker" else 1.95
            self.world.add_component(client.player_entity, Rotation(angle=math.pi/2.0))
            self.world.add_component(client.player_entity, Velocity(speed=vel_speed))
            self.world.add_component(client.player_entity, NetworkIdentity(player_id=client.client_id, role=role))
            self.world.add_component(client.player_entity, SphereCollider(radius=0.15))

            client.assigned_role = role
            client.is_dead = False
            client.escaped = False
            client.has_key = False
            client.attack_timer = 0.0
            client._last_move_time = time.perf_counter()

            players_data.append({
                "id": client.client_id,
                "name": client.name,
                "x": spawn_x,
                "y": spawn_y,
                "role": role
            })

        vents_data = []
        self.vents = []
        for y, row in enumerate(layout):
            for x, char in enumerate(row):
                if char == 'V':
                    valid, orientation = self.map_manager.check_vent_placement(x, y)
                    if valid:
                        vents_data.append({
                            "x": float(x) + 0.5,
                            "y": float(y) + 0.5,
                            "orientation": orientation.value
                        })

                        vx, vy = float(x) + 0.5, float(y) + 0.5
                        dest1, dest2 = None, None
                        if orientation == VentOrientation.VERTICAL:
                            dest1 = (vx, vy - 0.5 - PLAYER_RADIUS - VENT_OFFSET)
                            dest2 = (vx, vy + 0.5 + PLAYER_RADIUS + VENT_OFFSET)
                        elif orientation == VentOrientation.HORIZONTAL:
                            dest1 = (vx - 0.5 - PLAYER_RADIUS - VENT_OFFSET, vy)
                            dest2 = (vx + 0.5 + PLAYER_RADIUS + VENT_OFFSET, vy)

                        self.vents.append({
                            "x": vx, "y": vy,
                            "is_open": True, "timer": 0.0,
                            "orientation": orientation,
                            "destinations": (dest1, dest2)
                        })

        init_data = {
            "type": "game_init",
            "game_udp_port": self.game_udp_port,
            "config": {
                "player_speed": 1.95,
                "player_reach": 1.5,
                "player_radius": 0.15,
                "vent_open_time": 45.0
            },
            "map": {
                "width": self.map_manager.width,
                "height": self.map_manager.height,
                "layout": layout
            },
            "players": players_data,
            "vents": vents_data
        }

        self.broadcast(init_data)

        for client in self.clients:
            try:
                client.socket.sendall(encode_message({"type": "role_assign", "role": client.assigned_role}))
            except Exception:
                pass

    def _handle_vent_request(self, client, req):
        if getattr(client, 'assigned_role', 'runner') == "seeker":
            return
        pos = self.world.get_component(client.player_entity, Position)
        if not pos:
            return

        vent_x = req.get("vent_x")
        vent_y = req.get("vent_y")
        
        if vent_x is None or vent_y is None:
            return

        for vent in self.vents:
            vx_tile = int(vent["x"] - 0.5)
            vy_tile = int(vent["y"] - 0.5)
            if vx_tile == vent_x and vy_tile == vent_y and vent["is_open"]:
                dist_to_vent = math.sqrt((pos.x - vent["x"])**2 + (pos.y - vent["y"])**2)
                if dist_to_vent > 1.5:
                    continue
                    
                d1, d2 = vent["destinations"]
                dist1 = math.sqrt((pos.x - d1[0])**2 + (pos.y - d1[1])**2)
                dist2 = math.sqrt((pos.x - d2[0])**2 + (pos.y - d2[1])**2)
                if dist1 < dist2:
                    pos.x, pos.y = d2[0], d2[1]
                else:
                    pos.x, pos.y = d1[0], d1[1]

                vent["is_open"] = False
                vent["timer"] = 0.0

                self.broadcast({"type": "vent_update", "vent_x": vent["x"], "vent_y": vent["y"], "is_open": False})
                break

    def _reset_server(self):
        self.state = "lobby"
        self.current_tick = 0
        self.clients.clear()
        self._udp_client_map.clear()

        self.world = World()
        self.config_entity = self.world.create_entity()
        self.world.add_component(self.config_entity, ServerConfig(
            name=self.name,
            max_players=self.max_players,
            player_speed=1.95,
            player_reach=1.5,
            player_radius=0.15,
            vent_open_time=45.0,
            tick_rate=20
        ))
        if hasattr(self, 'vents'):
            self.vents.clear()
        if hasattr(self, 'map_manager'):
            del self.map_manager

    def _disconnect_client(self, client: ClientConnection):
        if client in self.clients:
            print(f"[TCP] Klient {client.name} sa odpojil.")
            client.socket.close()
            self.clients.remove(client)
            if client.udp_address and client.udp_address in self._udp_client_map:
                del self._udp_client_map[client.udp_address]
            self.world.destroy_entity(client.player_entity)

            if self.state == "game":
                runners_alive = sum(1 for c in self.clients if getattr(c, 'assigned_role', '') == 'runner' and not getattr(c, 'is_dead', False) and not getattr(c, 'escaped', False))
                seekers = sum(1 for c in self.clients if getattr(c, 'assigned_role', '') == 'seeker')
                
                if runners_alive >= 1 and seekers >= 1:
                    print(f"[TCP] Hráč {client.name} sa odpojil, ale hra pokračuje.")
                else:
                    print("[TCP] Hráč sa odpojil a hra nemôže pokračovať. Ukončujem hru.")
                    self.state = "lobby"
                    for c in self.clients:
                        c.is_ready = False
                    self.broadcast({"type": "game_over", "winner": "terminated"})

            if len(self.clients) == 0:
                print("[Server] Všetci hráči sa odpojili, resetujem server...")
                self._reset_server()
            elif self.state == "lobby":
                self.broadcast(self.build_player_list())
                if len(self.clients) >= 2 and all(c.is_ready for c in self.clients):
                    print("[TCP] Všetci hráči pripravení! Štartujem hru...")
                    self.state = "game"
                    for i, c in enumerate(self.clients):
                        try:
                            c.socket.sendall(encode_message({"type": "game_start", "your_id": c.client_id}))
                        except Exception:
                            pass
                    self.start_game()

    def _handle_client(self, client: ClientConnection):
        try:
            while self._running:
                data = client.socket.recv(4096)
                if not data:
                    break
                client.recv_buffer += data
                messages, client.recv_buffer = decode_messages(client.recv_buffer)
                for msg in messages:
                    self._handle_client_message(client, msg)
        except ConnectionResetError:
            pass
        except Exception as e:
            print(f"[TCP] Klient {client.name} error: {e}")
        finally:
            self._disconnect_client(client)

    def _process_pending_requests(self, tick_duration):
        for client in list(self.clients):
            with self._tick_lock:
                requests = list(client.pending_requests)
                client.pending_requests.clear()

            for req in requests:
                action = req.get("action")
                if action == "attack":
                    print(f"Attack request from client {client.name}")
                    client.attack_timer = 0.72
                    self.broadcast({"type": "player_attack", "player_id": client.client_id})
                    self._handle_attack(client)
                elif action == "vent_use":
                    self._handle_vent_request(client, req)
                elif action == "interact_portal":
                    self._handle_interact_portal(client)

    def run(self):
        self._running = True
        self.start_udp_broadcast()
        self.start_tcp_listener()

        print(f"Server '{self.name}' beží.")
        print(f" -> TCP Port: {self.tcp_port}")
        print(f" -> UDP Broadcast Port: {self.udp_port}")
        print(f" -> Lokálna IP: {self.local_ip}")
        print(f" -> Veľkosť mapy: {self.map_size}x{self.map_size}")

        config = self.world.get_component(self.config_entity, ServerConfig)
        tick_duration = 1.0 / config.tick_rate

        try:
            while self._running:
                start_time = time.perf_counter()

                if self.state == "game":
                    while True:
                        try:
                            data, addr = self.game_udp_socket.recvfrom(1024)
                            msg = decode_udp(data)
                            if msg and msg.get("type") == "player_input":
                                client = self._find_client_by_udp(addr)
                                if client:
                                    client.input_state = {
                                        "forward": msg.get("forward", False),
                                        "backward": msg.get("backward", False),
                                        "left": msg.get("left", False),
                                        "right": msg.get("right", False),
                                        "angle": msg.get("angle")
                                    }
                                    self._process_player_instant(client, msg)
                        except BlockingIOError:
                            break

                    self._process_pending_requests(tick_duration)

                    picked_key_entities: set[int] = set()
                    for client in self.clients:
                        if not getattr(client, 'is_dead', False) and not getattr(client, 'escaped', False) and getattr(client, 'assigned_role', '') == 'runner' and not getattr(client, 'has_key', False):
                            pos = self.world.get_component(client.player_entity, Position)
                            if pos:
                                from game.components import Key
                                for key_ent, (k_pos, key_comp) in self.world.get_components(Position, Key):
                                    # Preskočíme kľúče, ktoré boli zdvihnuté iným hráčom v tomto tiku
                                    if key_ent in picked_key_entities:
                                        continue
                                    if math.dist((pos.x, pos.y), (k_pos.x, k_pos.y)) < 0.45:
                                        client.has_key = True
                                        picked_key_entities.add(key_ent)
                                        self.world.destroy_entity(key_ent)
                                        try:
                                            client.socket.sendall(encode_message({"type": "key_picked"}))
                                        except:
                                            pass
                                        self.broadcast({"type": "key_removed"})
                                        break

                    player_data = []
                    for client in self.clients:
                        if not getattr(client, 'is_dead', False) and not getattr(client, 'escaped', False):
                            pos = self.world.get_component(client.player_entity, Position)
                            rot = self.world.get_component(client.player_entity, Rotation)
                            net_id = self.world.get_component(client.player_entity, NetworkIdentity)
                            if pos and rot and net_id:
                                player_data.append((client.client_id, pos, rot, net_id.role))

                    state_msg = {
                        "type": "game_state",
                        "tick": self.current_tick,
                        "players": [
                            {"id": cid, "x": p.x, "y": p.y, "angle": r.angle, "role": role_str}
                            for cid, p, r, role_str in player_data
                        ]
                    }
                    raw = encode_udp(state_msg)
                    for client in self.clients:
                        if client.udp_address:
                            try:
                                self.game_udp_socket.sendto(raw, client.udp_address)
                            except BlockingIOError:
                                pass

                    for vent in self.vents:
                        if not vent["is_open"]:
                            vent["timer"] += tick_duration
                            if vent["timer"] >= config.vent_open_time:
                                vent["is_open"] = True
                                vent["timer"] = 0.0
                                self.broadcast({"type": "vent_update", "vent_x": vent["x"], "vent_y": vent["y"], "is_open": True})

                    self.current_tick += 1

                elapsed = time.perf_counter() - start_time
                sleep_time = tick_duration - elapsed
                if sleep_time > 0:
                    time.sleep(sleep_time)
        except KeyboardInterrupt:
            self.shutdown()

    def shutdown(self):
        print("Vypínam server...")
        self._running = False
        try:
            self.tcp_socket.close()
            self.udp_socket.close()
            if hasattr(self, 'game_udp_socket'):
                self.game_udp_socket.close()
            for client in self.clients:
                client.socket.close()
        except Exception:
            pass