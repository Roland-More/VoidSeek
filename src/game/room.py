import socket
import json
import wgpu
from core.scene import Scene
from .ecs import World
from .components import UIPosition, UIButton, TextEntity, UISprite
from shared.protocol import encode_message, decode_messages
from core.backend.definitions import RENDER_WIDTH, RENDER_HEIGHT

class RoomScene(Scene):
    def __init__(self, renderer, scene_manager):
        self.renderer = renderer
        self.scene_manager = scene_manager
        self.world = World()
        self.network_client = None
        self.is_ready = False
        self.recv_buffer = b""
        self.my_player_id = None
        self.players = []
        self.player_entities = []
        
        self.scroll_offset = 0
        
        # UI
        center_x = RENDER_WIDTH / 2
        title_entity = self.world.create_entity()
        self.world.add_component(title_entity, TextEntity(text="LOBBY", x=center_x, y=RENDER_HEIGHT * 0.1, size=0.8, color=(1.0, 1.0, 1.0, 1.0), alignment="center"))
        
        bottom_y = RENDER_HEIGHT * 0.85
        total_width = 100 + 10 + 100 # 210
        start_x = center_x - total_width / 2
        
        # Ready button border
        bg_ready = self.world.create_entity()
        self.world.add_component(bg_ready, UIPosition(x=start_x, y=bottom_y, width=100, height=40, z_index=1))
        self.world.add_component(bg_ready, UISprite(color=(0.1, 0.1, 0.1, 1.0), use_texture=False))
        
        self.ready_btn_entity = self.world.create_entity()
        self.world.add_component(self.ready_btn_entity, UIPosition(x=start_x + 2, y=bottom_y + 2, width=96, height=36, z_index=2))
        self.world.add_component(self.ready_btn_entity, UIButton(
            text="READY",
            on_click=self.toggle_ready
        ))
        
        # Disconnect button border
        bg_disc = self.world.create_entity()
        self.world.add_component(bg_disc, UIPosition(x=start_x + 110, y=bottom_y, width=100, height=40, z_index=1))
        self.world.add_component(bg_disc, UISprite(color=(0.1, 0.1, 0.1, 1.0), use_texture=False))
        
        disconnect_btn = self.world.create_entity()
        self.world.add_component(disconnect_btn, UIPosition(x=start_x + 112, y=bottom_y + 2, width=96, height=36, z_index=2))
        self.world.add_component(disconnect_btn, UIButton(
            text="DISCONNECT",
            on_click=self.disconnect,
            color_normal=(0.3, 0.0, 0.0, 1.0),
            color_hover=(0.5, 0.0, 0.0, 1.0)
        ))

    def on_enter(self):
        # Zavolané zo SceneManagera pri prepnutí scény
        self.network_client = getattr(self.scene_manager, 'network_client', None)
        self.is_ready = False
        self.players = []
        self.recv_buffer = b""
        self._update_ready_btn()
        
        # Odošleme úvodnú správu JOIN na server
        player_name = "Hrac"
        if hasattr(self.scene_manager, "player_name"):
            player_name = self.scene_manager.player_name
            
        if self.network_client:
            try:
                payload = {"type": "join", "name": player_name}
                self.network_client.sendall(encode_message(payload))
            except Exception as e:
                print(f"Nepodarilo sa poslať join: {e}")

    def disconnect(self):
        if self.network_client:
            self.network_client.close()
            self.network_client = None
            self.scene_manager.network_client = None
        self.scene_manager.switch_to("server_list")

    def toggle_ready(self):
        self.is_ready = not self.is_ready
        self._update_ready_btn()
        
        if self.network_client:
            try:
                payload = {"type": "ready", "value": self.is_ready}
                self.network_client.sendall(encode_message(payload))
            except Exception as e:
                print(f"Chyba pri odosielaní: {e}")
                self.disconnect()

    def _update_ready_btn(self):
        btn = self.world.get_component(self.ready_btn_entity, UIButton)
        if btn:
            if self.is_ready:
                btn.text = "UNREADY"
                btn.color_normal = (0.2, 0.8, 0.2, 1.0)
                btn.color_hover = (0.3, 0.9, 0.3, 1.0)
            else:
                btn.text = "READY"
                btn.color_normal = (0.2, 0.2, 0.3, 1.0)
                btn.color_hover = (0.3, 0.3, 0.5, 1.0)

    def update(self, delta_time: float):
        self.renderer.update_camera(0.0, 0.0, 0.0)
        if not self.network_client:
            return
            
        try:
            data = self.network_client.recv(4096)
            if not data:
                print("Server ukončil spojenie.")
                self.disconnect()
                return
                
            self.recv_buffer += data
        except BlockingIOError:
            pass
        except (ConnectionResetError, ConnectionAbortedError, OSError):
            print("Spojenie stratené.")
            self.disconnect()
            return
        
        messages, self.recv_buffer = decode_messages(self.recv_buffer)
        
        for i, payload in enumerate(messages):
            if payload.get("type") == "player_list":
                self.players = payload.get("players", [])
                self._refresh_player_list()
            elif payload.get("type") == "game_start":
                self.my_player_id = payload.get("your_id")
                print(f"Hra sa začína! Moje ID: {self.my_player_id}")
            elif payload.get("type") == "game_init":
                try:
                    from game.state import GameplayScene
                    pending_msgs = messages[i+1:]
                    gameplay = GameplayScene(
                        self.renderer, 
                        self.scene_manager, 
                        payload, 
                        self.network_client,
                        pending_messages=pending_msgs,
                        recv_buffer=self.recv_buffer
                    )
                    gameplay.my_player_id = self.my_player_id
                    self.scene_manager.register("game", gameplay)
                    self.scene_manager.switch_to("game")
                except Exception as e:
                    print(f"Chyba pri vytváraní hry: {e}")
                    import traceback
                    traceback.print_exc()
                break

    def _refresh_player_list(self):
        for ent in self.player_entities:
            self.world.destroy_entity(ent)
        self.player_entities.clear()
        
        max_scroll = max(0, len(self.players) - 5)
        self.scroll_offset = max(0, min(max_scroll, getattr(self, "scroll_offset", 0)))
        
        visible_players = self.players[self.scroll_offset : self.scroll_offset + 5]
        
        center_x = RENDER_WIDTH / 2
        list_start_y = RENDER_HEIGHT * 0.25
        
        for i, player in enumerate(visible_players):
            bg_w = 400
            bg_x = center_x - bg_w / 2
            
            bg = self.world.create_entity()
            self.world.add_component(bg, UIPosition(x=bg_x, y=list_start_y + i * 35, width=bg_w, height=30, z_index=1))
            self.world.add_component(bg, UISprite(color=(0.1, 0.1, 0.1, 1.0), use_texture=False))
            self.player_entities.append(bg)
            
            fg = self.world.create_entity()
            self.world.add_component(fg, UIPosition(x=bg_x + 2, y=list_start_y + i * 35 + 2, width=bg_w - 4, height=26, z_index=2))
            self.world.add_component(fg, UISprite(color=(0.3, 0.0, 0.0, 1.0), use_texture=False))
            self.player_entities.append(fg)
            
            ready_str = "READY" if player.get("ready") else "UNREADY"
            color = (0.0, 1.0, 0.0, 1.0) if player.get("ready") else (1.0, 0.0, 0.0, 1.0)
            
            # Name left
            name_ent = self.world.create_entity()
            self.world.add_component(name_ent, TextEntity(
                text=f"{player.get('name', 'Unknown')}",
                x=bg_x + 10, y=list_start_y + i * 35 + 8, size=0.4, color=(1.0, 1.0, 1.0, 1.0), alignment="left"
            ))
            self.player_entities.append(name_ent)
            
            # Status right
            status_ent = self.world.create_entity()
            self.world.add_component(status_ent, TextEntity(
                text=ready_str,
                x=bg_x + bg_w - 10, y=list_start_y + i * 35 + 8, size=0.4, color=color, alignment="right"
            ))
            self.player_entities.append(status_ent)

    def handle_mouse_wheel(self, dy: float):
        if dy > 0:
            self.scroll_offset += 1
        elif dy < 0:
            self.scroll_offset -= 1
        max_scroll = max(0, len(self.players) - 5)
        self.scroll_offset = max(0, min(max_scroll, getattr(self, "scroll_offset", 0)))
        self._refresh_player_list()

    def handle_key_down(self, key: str):
        pass

    def draw(self, encoder, target_view):
        self.renderer.update_text(self.world)
        self.renderer.update_ui_buffers(self.world)
        self.renderer.render_menu_scene(encoder, target_view)
