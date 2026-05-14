import glfw
import wgpu
import time
from rendercanvas.auto import RenderCanvas
from core.backend.pipeline import Builder
from game.state import GameState


class Renderer:
    def __init__(self, title="VoidSeek", width=800, height=600):
        self._is_fullscreen = False
        self._is_mouse_locked = False
        self._last_mouse_x = None

        self.game_state = GameState()
        self.game_state.start()
        self.last_time = time.perf_counter()

        # 1. Vytvorenie plátna (canvas) automaticky cez rendercanvas, ktorý podporuje GLFW
        self.canvas = RenderCanvas(title=title, size=(width, height))

        # self.toggle_fullscreen()
        self.toggle_mouse_lock()

        # 2. Získanie predvoleného adaptéra a zariadenia (synchrónne volanie)
        self.device = wgpu.utils.get_default_device()
        self.present_context = self.canvas.get_wgpu_context()
        self.render_texture_format = self.present_context.get_preferred_format(self.device.adapter)

        # 3. Konfigurácia kontextu renderovania
        self.present_context.configure(device=self.device, format=self.render_texture_format)
        
        # Vytvorenie render pipeline
        builder = Builder(self.device)
        builder.set_shader_module("basic.wgsl", "vs_main", "fs_main")
        builder.set_pixel_format(self.render_texture_format)
        self.render_pipeline = builder.build("Basic Pipeline")

        # 4. Registrácia funkcie pre vykresľovanie snímky
        self.canvas.request_draw(self.draw_frame)

        # 5. Registrácia globálnych eventov okna (len pre prepínacie klávesy)
        self.canvas.add_event_handler(self.on_key_down, "key_down")

    def on_key_down(self, event):
        key = event.get("key").lower()
        if key == "escape":
            self.canvas.close()
        elif key == "p":
            self.toggle_fullscreen()
        elif key == "l":
            self.toggle_mouse_lock()

    def toggle_mouse_lock(self):
        if self._is_mouse_locked:
            glfw.set_input_mode(self.canvas._window, glfw.CURSOR, glfw.CURSOR_NORMAL)
            self._is_mouse_locked = False
            self._last_mouse_x = None
        else:
            glfw.set_input_mode(self.canvas._window, glfw.CURSOR, glfw.CURSOR_DISABLED)
            self._is_mouse_locked = True
            # Aby pri locknuti neskocila mys, ziskame jej prvu poziciu az pri dalsom evente
            if self.canvas._window:
                x, _ = glfw.get_cursor_pos(self.canvas._window)
                self._last_mouse_x = x

    def toggle_fullscreen(self):
        if self._is_fullscreen:
            glfw.set_window_monitor(self.canvas._window, None, 100, 100, 800, 600, glfw.DONT_CARE)
            self._is_fullscreen = False
        else:
            monitor = glfw.get_primary_monitor()
            mode = glfw.get_video_mode(monitor)
            glfw.set_window_monitor(
                self.canvas._window,
                monitor,
                0,
                0,
                mode.size.width,
                mode.size.height,
                mode.refresh_rate,
            )
            self._is_fullscreen = True
            
        # Ochrana proti nechcenému trhnutiu kamery po prestavení okna
        # Namiesto rátania starej pozície ju po zmene resetneme
        self._last_mouse_x = None

    def draw_frame(self):
        current_time = time.perf_counter()
        delta_time = current_time - self.last_time
        self.last_time = current_time
        
        # --- ZÍSKAVANIE KONTINUÁLNYCH VSTUPOV PRIAMO Z GLFW ---
        window = self.canvas._window
        if window:
            # WASD pohyb
            self.game_state.input.forward = glfw.get_key(window, glfw.KEY_W) == glfw.PRESS
            self.game_state.input.backward = glfw.get_key(window, glfw.KEY_S) == glfw.PRESS
            self.game_state.input.left = glfw.get_key(window, glfw.KEY_A) == glfw.PRESS
            self.game_state.input.right = glfw.get_key(window, glfw.KEY_D) == glfw.PRESS

            # Myš rotácia
            if self._is_mouse_locked:
                x, _ = glfw.get_cursor_pos(window)
                if self._last_mouse_x is not None:
                    dx = x - self._last_mouse_x
                    self.game_state.input.mouse_dx += dx
                self._last_mouse_x = x
            else:
                self._last_mouse_x = None

        # Odošle spracovaný vstup a časový rozdiel do hry
        self.game_state.update(delta_time)

        # Zapíše príkazy do command_encoder
        command_encoder = self.device.create_command_encoder()
        current_texture = self.present_context.get_current_texture()
        current_texture_view = current_texture.create_view()

        # Telová farba pre pozadie (jemne oranžovo/ružovo-béžová)
        render_pass = command_encoder.begin_render_pass(
            color_attachments=[
                {
                    "view": current_texture_view,
                    "resolve_target": None,
                    "clear_value": (1.0, 0.8, 0.6, 1.0),
                    "load_op": wgpu.LoadOp.clear,
                    "store_op": wgpu.StoreOp.store,
                }
            ],
        )

        render_pass.set_pipeline(self.render_pipeline)
        render_pass.draw(3, 1, 0, 0)
        render_pass.end()
        self.device.queue.submit([command_encoder.finish()])
        
        # Požadovať ďalší frame pre neustálu slučku
        self.canvas.request_draw(self.draw_frame)