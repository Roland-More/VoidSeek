import socket
import threading
import json
import time
from game.ecs import World
from game.components import ServerConfig, NetworkPlayer
from shared.protocol import encode_message, decode_messages

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
    def __init__(self, sock: socket.socket, address: tuple, player_entity: int, name: str):
        self.socket = sock
        self.address = address
        self.player_entity = player_entity
        self.name = name
        self.is_ready = False
        self.recv_buffer = b""

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
        
        # UDP Setup
        self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        self.clients: list[ClientConnection] = []
        self.state = "lobby"
        self._running = False
        
        # Determine local IP
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            self.local_ip = s.getsockname()[0]
            s.close()
        except Exception:
            self.local_ip = socket.gethostbyname(socket.gethostname())

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
                        self.udp_socket.sendto(message, ("<broadcast>", self.udp_port))
                        self.udp_socket.sendto(message, ("127.0.0.1", self.udp_port))
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
                    
                    connection = ClientConnection(client_sock, address, entity, player_name)
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

    def start_game(self):
        # Tu sa neskôr doplní logika na spustenie hry (inicializácia mapy, spawn pointov atď.)
        pass

    def _disconnect_client(self, client: ClientConnection):
        if client in self.clients:
            print(f"[TCP] Klient {client.name} sa odpojil.")
            client.socket.close()
            self.clients.remove(client)
            self.world.destroy_entity(client.player_entity)
            
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
                
                # Zatiaľ prázdna herná slučka
                
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
