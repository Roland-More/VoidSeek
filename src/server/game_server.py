import socket
import threading
import json
import time
from game.ecs import World
from game.components import ServerConfig, NetworkPlayer

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
        
    def _handle_client(self, client: ClientConnection):
        try:
            while self._running:
                data = client.socket.recv(1024)
                if not data:
                    break
                # TODO: Spracovanie prijatých dát od klienta
        except ConnectionResetError:
            pass
        except Exception as e:
            print(f"[TCP] Klient {client.name} error: {e}")
        finally:
            print(f"[TCP] Klient {client.name} sa odpojil.")
            client.socket.close()
            if client in self.clients:
                self.clients.remove(client)

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
