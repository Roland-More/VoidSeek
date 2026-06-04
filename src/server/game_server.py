import socket
import threading
import json
import time
import math
import random
from game.ecs import World
from game.components import ServerConfig, NetworkPlayer, Position, Rotation, Velocity, NetworkIdentity
from shared.protocol import encode_message, decode_messages, encode_udp, decode_udp
from game.map import MapManager
from game.definitions import VentOrientation
from game.systems import _is_wall

# Ak by bolo potrebné Position z components
try:
    from game.components import Position
except ImportError:
    from dataclasses import dataclass
    @dataclass
    class Position:
        x: float
        y: float

class ClientConnection:
    def __init__(self, sock: socket.socket, address: tuple, player_entity: int, name: str, client_id: int):
        self.socket = sock
        self.address = address
        self.player_entity = player_entity
        self.name = name
        self.client_id = client_id
        self.is_ready = False
        self.recv_buffer = b""
        self.input_state = {"forward": False, "backward": False, "left": False, "right": False, "mouse_dx": 0.0}
        self.pending_requests = []
        self.udp_address = None

class GameServer:
    def __init__(self, name: str, tcp_port: int, udp_port: int, max_players: int):
        self.name = name
        self.tcp_port = tcp_port
        self.udp_port = udp_port
        self.max_players = max_players
        
        self.world = World()
        self.config_entity = self.world.create_entity()
        self.world.add_component(self.config_entity, ServerConfig(
            name=name,
            max_players=max_players,
            player_speed=1.95,
            player_reach=1.5,       # INTERACT_DISTANCE
            player_radius=0.15,     # PLAYER_RADIUS
            vent_open_time=10.0,    # TIME_TO_OPEN_VENT
            tick_rate=20             # serverových updatov za sekundu
        ))
        
        # TCP Setup
        self.tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.tcp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.tcp_socket.bind(("0.0.0.0", self.tcp_port))
        self.tcp_socket.listen()
        
        # Determine local IP
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            self.local_ip = s.getsockname()[0]
            s.close()
        except Exception:
            self.local_ip = socket.gethostbyname(socket.gethostname())
            
        # UDP Setup
        self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        ttl = 1
        self.udp_socket.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, ttl)
        self.udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self.udp_socket.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF, socket.inet_aton(self.local_ip))
        except Exception as e:
            print(f"[UDP] Nepodarilo sa nastaviť IP_MULTICAST_IF: {e}")
            
        # UDP Game Socket
        self.game_udp_port = self.udp_port + 1
        self.game_udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.game_udp_socket.bind(("0.0.0.0", self.game_udp_port))
        self.game_udp_socket.setblocking(False)
        
        self.clients: list[ClientConnection] = []
        self.state = "lobby"
        self._running = False
        self.current_tick = 0
        
    def _find_client_by_udp(self, addr):
        for client in self.clients:
            if client.udp_address == addr:
                return client
        return None

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
                        "state": self.state
                    }
                    message = json.dumps(payload).encode("utf-8")
                    try:
                        self.udp_socket.sendto(message, ("224.1.1.1", 5007))
                        print(f"[UDP] Odoslané: {payload}")
                    except Exception as e:
                        print(f"[UDP] Broadcast error: {e}")
                time.sleep(5.0)
                
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
                        
                    client_id = len(self.clients)
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
            "players": [{"name": c.name, "ready": c.is_ready, "id": i} for i, c in enumerate(self.clients)]
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
            
            # Skontroluj či sú všetci ready a aspoň 2 hráči
            if len(self.clients) >= 2 and all(c.is_ready for c in self.clients):
                print("[TCP] Všetci hráči pripravení! Štartujem hru...")
                self.state = "game"
                for i, c in enumerate(self.clients):
                    try:
                        c.socket.sendall(encode_message({"type": "game_start", "your_id": i}))
                    except Exception:
                        pass
                self.start_game()
                
        elif msg_type == "udp_register":
            client.udp_address = (client.address[0], msg.get("udp_port"))
            
        elif msg_type == "player_request":
            client.pending_requests.append(msg)

    def start_game(self):
        # 1. Inicializácia mapy na strane servera
        self.map_manager = MapManager()
        layout = [
            "11111111",
            "1.1....1",
            "1.1.11.1",
            "1.1V1..1",
            "1...V..1",
            "1.111..1",
            "1......1",
            "11111111"
        ]
        self.map_manager.load_from_layout(layout)
        
        seeker_idx = random.randint(0, len(self.clients) - 1) if self.clients else 0
        
        # 2. Nastavenie spawn pointov hráčom
        spawn_points = [(1.5, 1.5), (6.5, 1.5), (1.5, 6.5), (6.5, 6.5)]
        players_data = []
        for i, client in enumerate(self.clients):
            spawn_x, spawn_y = spawn_points[i % len(spawn_points)]
            role = "seeker" if i == seeker_idx else "runner"
            
            # Aktualizácia pozície na serveri
            pos = self.world.get_component(client.player_entity, Position)
            if pos:
                pos.x = spawn_x
                pos.y = spawn_y
                
            self.world.add_component(client.player_entity, Rotation(angle=math.pi/2.0))
            self.world.add_component(client.player_entity, Velocity(speed=1.95))
            self.world.add_component(client.player_entity, NetworkIdentity(player_id=client.client_id, role=role))
                
            players_data.append({
                "id": client.client_id,
                "name": client.name,
                "x": spawn_x,
                "y": spawn_y,
                "role": role
            })
            
        # 3. Zozbieranie dát o ventoch
        vents_data = []
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

        # 4. Zostavenie inicializačného balíčka a rozposlanie
        init_data = {
            "type": "game_init",
            "game_udp_port": self.game_udp_port,
            "config": {
                "player_speed": 1.95,
                "player_reach": 1.5,
                "player_radius": 0.15,
                "vent_open_time": 10.0
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
            role = "seeker" if client.client_id == seeker_idx else "runner"
            try:
                client.socket.sendall(encode_message({"type": "role_assign", "role": role}))
            except Exception:
                pass

    def _disconnect_client(self, client: ClientConnection):
        if client in self.clients:
            print(f"[TCP] Klient {client.name} sa odpojil.")
            client.socket.close()
            self.clients.remove(client)
            self.world.destroy_entity(client.player_entity)
            
            if self.state == "game" and len(self.clients) < 2:
                print("[TCP] Nedostatok hráčov. Návrat do lobby.")
                self.state = "lobby"
                for c in self.clients:
                    c.is_ready = False
            
            # Zruš ready ak klesol počet pod 2 alebo iný dôvod
            if self.state == "lobby":
                self.broadcast(self.build_player_list())

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

    def run(self):
        self._running = True
        self.start_udp_broadcast()
        self.start_tcp_listener()
        
        print(f"Server '{self.name}' beží.")
        print(f" -> TCP Port: {self.tcp_port}")
        print(f" -> UDP Broadcast Port: {self.udp_port}")
        print(f" -> Lokálna IP: {self.local_ip}")
        
        config = self.world.get_component(self.config_entity, ServerConfig)
        tick_duration = 1.0 / config.tick_rate
        
        try:
            while self._running:
                start_time = time.perf_counter()
                
                if self.state == "game":
                    # Prijmi všetky čakajúce UDP pakety
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
                                        "mouse_dx": msg.get("mouse_dx", 0.0)
                                    }
                        except BlockingIOError:
                            break
                            
                    # Update physics and collect state
                    player_data = []
                    for client in self.clients:
                        pos = self.world.get_component(client.player_entity, Position)
                        rot = self.world.get_component(client.player_entity, Rotation)
                        vel = self.world.get_component(client.player_entity, Velocity)
                        net_id = self.world.get_component(client.player_entity, NetworkIdentity)
                        
                        if pos and rot and vel and net_id:
                            # Rotation
                            rot.angle += client.input_state["mouse_dx"] * 0.0015
                            client.input_state["mouse_dx"] = 0.0
                            
                            # Movement
                            dx, dy = 0.0, 0.0
                            if client.input_state["forward"]:
                                dx += math.cos(rot.angle) * vel.speed
                                dy += math.sin(rot.angle) * vel.speed
                            if client.input_state["backward"]:
                                dx -= math.cos(rot.angle) * vel.speed
                                dy -= math.sin(rot.angle) * vel.speed
                            if client.input_state["left"]:
                                dx += math.cos(rot.angle - math.pi/2) * vel.speed
                                dy += math.sin(rot.angle - math.pi/2) * vel.speed
                            if client.input_state["right"]:
                                dx += math.cos(rot.angle + math.pi/2) * vel.speed
                                dy += math.sin(rot.angle + math.pi/2) * vel.speed
                                
                            # Apply movement with collision
                            if dx != 0.0 or dy != 0.0:
                                length = math.sqrt(dx*dx + dy*dy)
                                dx = (dx / length) * vel.speed * tick_duration
                                dy = (dy / length) * vel.speed * tick_duration
                                
                                new_x = pos.x + dx
                                new_y = pos.y + dy
                                
                                # X kolízia
                                if not _is_wall(new_x, pos.y, self.map_manager.walls, 8, 8, 0.15):
                                    pos.x = new_x
                                # Y kolízia
                                if not _is_wall(pos.x, new_y, self.map_manager.walls, 8, 8, 0.15):
                                    pos.y = new_y
                            
                            player_data.append((client.client_id, pos, rot, net_id.role))
                    
                    # Broadcast game state
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
            for client in self.clients:
                client.socket.close()
        except Exception:
            pass
