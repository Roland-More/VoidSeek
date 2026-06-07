import socket
import json
import time
import wgpu
from core.scene import Scene
from .ecs import World
from .components import UIPosition, UIButton, UITextInput, TextEntity, UISprite
from core.backend.definitions import RENDER_WIDTH, RENDER_HEIGHT

class ServerListScene(Scene):
    def __init__(self, renderer, scene_manager):
        self.renderer = renderer
        self.scene_manager = scene_manager
        self.world = World()
        
        # UDP Setup
        import struct
        self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.udp_socket.bind(("", 5007))
        group = socket.inet_aton("224.1.1.1")
        # Get local IP
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
        except Exception:
            local_ip = socket.gethostbyname(socket.gethostname())

        mreq = struct.pack("4s4s", group, socket.inet_aton(local_ip))
        try:
            self.udp_socket.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
        except Exception as e:
            print(f"[UDP] Nepodarilo sa pridať do multicast skupiny s {local_ip}: {e}")
            # Fallback
            mreq = struct.pack("4s4s", group, socket.inet_aton("0.0.0.0"))
            self.udp_socket.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
        self.udp_socket.setblocking(False)
        
        self.servers = []
        self.server_entities = []
        
        self.scroll_offset = 0
        
        center_x = RENDER_WIDTH / 2
        
        # Static UI
        title_entity = self.world.create_entity()
        self.world.add_component(title_entity, TextEntity(text="SERVER LIST", x=center_x, y=RENDER_HEIGHT * 0.1, size=0.5, color=(1.0, 1.0, 1.0, 1.0), alignment="center"))
        
        bottom_y = RENDER_HEIGHT * 0.85
        total_width = 190 + 10 + 100 + 10 + 80  # 390
        start_x = center_x - total_width / 2
        
        # Input for direct IP (border)
        bg_inp = self.world.create_entity()
        self.world.add_component(bg_inp, UIPosition(x=start_x, y=bottom_y, width=190, height=40, z_index=1))
        self.world.add_component(bg_inp, UISprite(color=(0.1, 0.1, 0.1, 1.0), use_texture=False))
        
        self.input_entity = self.world.create_entity()
        self.world.add_component(self.input_entity, UIPosition(x=start_x + 2, y=bottom_y + 2, width=186, height=36, z_index=2))
        text_input = UITextInput(placeholder="IP:PORT", color_normal=(0.2, 0.0, 0.0, 1.0), color_active=(0.4, 0.0, 0.0, 1.0))
        text_input.on_submit = self.connect_manual
        self.world.add_component(self.input_entity, text_input)
        
        # Connect button
        bg_conn = self.world.create_entity()
        self.world.add_component(bg_conn, UIPosition(x=start_x + 200, y=bottom_y, width=100, height=40, z_index=1))
        self.world.add_component(bg_conn, UISprite(color=(0.1, 0.1, 0.1, 1.0), use_texture=False))
        
        connect_btn = self.world.create_entity()
        self.world.add_component(connect_btn, UIPosition(x=start_x + 202, y=bottom_y + 2, width=96, height=36, z_index=2))
        self.world.add_component(connect_btn, UIButton(
            text="CONNECT",
            on_click=lambda: self.connect_manual(self.world.get_component(self.input_entity, UITextInput).text),
            color_normal=(0.3, 0.0, 0.0, 1.0),
            color_hover=(0.5, 0.0, 0.0, 1.0)
        ))
        
        # Back button
        bg_back = self.world.create_entity()
        self.world.add_component(bg_back, UIPosition(x=start_x + 310, y=bottom_y, width=80, height=40, z_index=1))
        self.world.add_component(bg_back, UISprite(color=(0.1, 0.1, 0.1, 1.0), use_texture=False))
        
        back_btn = self.world.create_entity()
        self.world.add_component(back_btn, UIPosition(x=start_x + 312, y=bottom_y + 2, width=76, height=36, z_index=2))
        self.world.add_component(back_btn, UIButton(
            text="BACK",
            on_click=lambda: self.scene_manager.switch_to("menu"),
            color_normal=(0.3, 0.0, 0.0, 1.0),
            color_hover=(0.5, 0.0, 0.0, 1.0)
        ))

    def handle_mouse_wheel(self, dy: float):
        if dy > 0:
            self.scroll_offset += 1
        elif dy < 0:
            self.scroll_offset -= 1
        max_scroll = max(0, len(self.servers) - 5)
        self.scroll_offset = max(0, min(max_scroll, self.scroll_offset))

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
                print(f"[UDP] Prijaté od {addr}: {payload}")
                
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
        self.servers = [s for s in self.servers if current_time - s["last_seen"] < 6.0 and s.get("state", "lobby") == "lobby"]
        
        max_scroll = max(0, len(self.servers) - 5)
        self.scroll_offset = max(0, min(max_scroll, self.scroll_offset))
        
        # Refresh UI
        for ent in self.server_entities:
            self.world.destroy_entity(ent)
        self.server_entities.clear()
        
        visible_servers = self.servers[self.scroll_offset : self.scroll_offset + 5]
        
        center_x = RENDER_WIDTH / 2
        list_start_y = RENDER_HEIGHT * 0.25
        
        for i, s in enumerate(visible_servers):
            bg_w = 400
            bg_x = center_x - bg_w / 2
            
            # Border
            bg = self.world.create_entity()
            self.world.add_component(bg, UIPosition(x=bg_x, y=list_start_y + i * 35, width=bg_w, height=30, z_index=1))
            self.world.add_component(bg, UISprite(color=(0.1, 0.1, 0.1, 1.0), use_texture=False))
            self.server_entities.append(bg)
            
            ent = self.world.create_entity()
            self.world.add_component(ent, UIPosition(x=bg_x + 2, y=list_start_y + i * 35 + 2, width=bg_w - 4, height=26, z_index=2))
            self.world.add_component(ent, UIButton(
                text="",
                on_click=lambda s=s: self.connect_to(s["tcp_host"], s["tcp_port"]),
                color_normal=(0.4, 0.0, 0.0, 1.0),
                color_hover=(0.6, 0.0, 0.0, 1.0)
            ))
            self.server_entities.append(ent)
            
            # Name left
            name_ent = self.world.create_entity()
            self.world.add_component(name_ent, TextEntity(
                text=s['name'],
                x=bg_x + 10, y=list_start_y + i * 35 + 8, size=0.35, color=(1.0, 1.0, 1.0, 1.0), alignment="left"
            ))
            self.server_entities.append(name_ent)

            # Status right
            status_ent = self.world.create_entity()
            self.world.add_component(status_ent, TextEntity(
                text=f"{s['players']}/{s['max_players']}",
                x=bg_x + bg_w - 10, y=list_start_y + i * 35 + 8, size=0.35, color=(1.0, 1.0, 1.0, 1.0), alignment="right"
            ))
            self.server_entities.append(status_ent)

    def draw(self, encoder, target_view):
        self.renderer.update_text(self.world)
        self.renderer.update_ui_buffers(self.world)
        self.renderer.render_menu_scene(encoder, target_view)
