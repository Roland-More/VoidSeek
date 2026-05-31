import socket
import json
import time
import wgpu
from core.scene import Scene
from .ecs import World
from .components import UIPosition, UIButton, UITextInput, TextEntity

class ServerListScene(Scene):
    def __init__(self, renderer, scene_manager):
        self.renderer = renderer
        self.scene_manager = scene_manager
        self.world = World()
        
        # UDP Setup
        self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.udp_socket.bind(("", 7778))
        self.udp_socket.setblocking(False)
        
        self.servers = []
        self.server_entities = []
        
        # Static UI
        title_entity = self.world.create_entity()
        self.world.add_component(title_entity, TextEntity(text="ZOZNAM SERVEROV", x=240, y=30, size=0.5, color=(1.0, 1.0, 1.0, 1.0), alignment="center"))
        
        # Input for direct IP
        self.input_entity = self.world.create_entity()
        self.world.add_component(self.input_entity, UIPosition(x=50, y=210, width=200, height=40, z_index=1))
        text_input = UITextInput(placeholder="Zadaj IP:PORT")
        text_input.on_submit = self.connect_manual
        self.world.add_component(self.input_entity, text_input)
        
        # Connect button
        connect_btn = self.world.create_entity()
        self.world.add_component(connect_btn, UIPosition(x=260, y=210, width=100, height=40, z_index=1))
        self.world.add_component(connect_btn, UIButton(
            text="PRIPOJIT",
            on_click=lambda: self.connect_manual(self.world.get_component(self.input_entity, UITextInput).text)
        ))
        
        # Back button
        back_btn = self.world.create_entity()
        self.world.add_component(back_btn, UIPosition(x=370, y=210, width=60, height=40, z_index=1))
        self.world.add_component(back_btn, UIButton(
            text="SPAT",
            on_click=lambda: self.scene_manager.switch_to("menu")
        ))

    def connect_to(self, host, port):
        print(f"Pripájanie na {host}:{port}...")
        try:
            tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            tcp_socket.connect((host, port))
            tcp_socket.setblocking(False)
            self.scene_manager.network_client = tcp_socket
            self.scene_manager.switch_to("room")
        except Exception as e:
            print(f"Nepodarilo sa pripojiť: {e}")

    def connect_manual(self, address_string=None):
        if not address_string:
            address_string = self.world.get_component(self.input_entity, UITextInput).text
        try:
            host, port = address_string.split(":")
            self.connect_to(host, int(port))
        except ValueError:
            print("Neplatný formát IP:PORT")

    def update(self, delta_time: float):
        self.renderer.update_camera(0.0, 0.0, 0.0)
        # Read UDP packets
        try:
            while True:
                data, addr = self.udp_socket.recvfrom(1024)
                payload = json.loads(data.decode("utf-8"))
                
                # Check if server exists
                existing = next((s for s in self.servers if s["tcp_host"] == payload["tcp_host"] and s["tcp_port"] == payload["tcp_port"]), None)
                if existing:
                    existing.update(payload)
                    existing["last_seen"] = time.time()
                else:
                    payload["last_seen"] = time.time()
                    self.servers.append(payload)
        except BlockingIOError:
            pass
        except json.JSONDecodeError:
            pass
            
        # Clean old servers
        current_time = time.time()
        self.servers = [s for s in self.servers if current_time - s["last_seen"] < 15.0]
        
        # Refresh UI if needed (simple way: clear and recreate server entities every frame)
        for ent in self.server_entities:
            self.world.destroy_entity(ent)
        self.server_entities.clear()
        
        for i, s in enumerate(self.servers):
            ent = self.world.create_entity()
            self.world.add_component(ent, UIPosition(x=90, y=130 + i * 40, width=300, height=30, z_index=1))
            self.world.add_component(ent, UIButton(
                text=f"{s['name']} ({s['players']}/{s['max_players']})",
                on_click=lambda s=s: self.connect_to(s["tcp_host"], s["tcp_port"])
            ))
            self.server_entities.append(ent)

    def draw(self, encoder, target_view):
        self.renderer.update_text(self.world)
        self.renderer.update_ui_buffers(self.world)
        self.renderer.render_menu_scene(encoder, target_view)
