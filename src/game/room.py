import socket
import json
import wgpu
from core.scene import Scene
from .ecs import World
from .components import UIPosition, UIButton, TextEntity

class RoomScene(Scene):
    def __init__(self, renderer, scene_manager):
        self.renderer = renderer
        self.scene_manager = scene_manager
        self.world = World()
        self.network_client = None
        self.is_ready = False
        
        self.players = []
        self.player_entities = []
        
        # UI
        title_entity = self.world.create_entity()
        self.world.add_component(title_entity, TextEntity(text="LOBBY", x=240, y=30, size=0.8, color=(1.0, 1.0, 1.0, 1.0), alignment="center"))
        
        # Ready button
        self.ready_btn_entity = self.world.create_entity()
        self.world.add_component(self.ready_btn_entity, UIPosition(x=130, y=150, width=100, height=30, z_index=1))
        self.world.add_component(self.ready_btn_entity, UIButton(
            text="READY",
            on_click=self.toggle_ready
        ))
        
        # Disconnect button
        disconnect_btn = self.world.create_entity()
        self.world.add_component(disconnect_btn, UIPosition(x=250, y=150, width=100, height=30, z_index=1))
        self.world.add_component(disconnect_btn, UIButton(
            text="ODPOJIT",
            on_click=self.disconnect
        ))

    def on_enter(self):
        # Zavolané zo SceneManagera pri prepnutí scény
        self.network_client = getattr(self.scene_manager, 'network_client', None)
        self.is_ready = False
        self.players = []
        self._update_ready_btn()

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
                self.network_client.sendall((json.dumps(payload) + "\n").encode("utf-8"))
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
                
            messages = data.decode("utf-8").strip().split('\n')
            for msg in messages:
                if not msg:
                    continue
                payload = json.loads(msg)
                if payload.get("type") == "player_list":
                    self.players = payload.get("players", [])
                    self._refresh_player_list()
                elif payload.get("type") == "game_start":
                    self.scene_manager.switch_to("game")
                    
        except BlockingIOError:
            pass
        except Exception as e:
            print(f"Spojenie stratené: {e}")
            self.disconnect()

    def _refresh_player_list(self):
        for ent in self.player_entities:
            self.world.remove_entity(ent)
        self.player_entities.clear()
        
        for i, player in enumerate(self.players):
            ent = self.world.create_entity()
            ready_str = "[READY]" if player.get("ready") else "[WAITING]"
            self.world.add_component(ent, TextEntity(
                text=f"{player.get('name', 'Unknown')} {ready_str}",
                x=140, y=80 + i * 20, size=0.3, color=(1.0, 1.0, 1.0, 1.0)
            ))
            self.player_entities.append(ent)

    def handle_key_down(self, key: str):
        pass

    def draw(self, encoder, target_view):
        self.renderer.update_text(self.world)
        self.renderer.update_ui_buffers(self.world)
        self.renderer.render_menu_scene(encoder, target_view)
