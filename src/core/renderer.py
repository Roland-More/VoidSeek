import glfw
import wgpu
from rendercanvas.auto import RenderCanvas


class Renderer:
    def __init__(self, title="VoidSeek", width=800, height=600):
        self._is_fullscreen = False
        self._is_mouse_locked = False

        # 1. Vytvorenie plátna (canvas) automaticky cez rendercanvas, ktorý podporuje GLFW
        self.canvas = RenderCanvas(title=title, size=(width, height))

        self.toggle_fullscreen()
        self.toggle_mouse_lock()

        # 2. Získanie predvoleného adaptéra a zariadenia (synchrónne volanie)
        self.device = wgpu.utils.get_default_device()
        self.present_context = self.canvas.get_wgpu_context()
        self.render_texture_format = self.present_context.get_preferred_format(self.device.adapter)

        # 3. Konfigurácia kontextu renderovania
        self.present_context.configure(device=self.device, format=self.render_texture_format)

        # 4. Registrácia funkcie pre vykresľovanie snímky
        self.canvas.request_draw(self.draw_frame)

        # 5. Registrácia globálnych eventov okna
        self.canvas.add_event_handler(self.on_key_down, "key_down")

    def on_key_down(self, event):
        key = event.get("key")
        if key == "Escape":
            self.canvas.close()
        elif key in ("p", "P"):
            self.toggle_fullscreen()
        elif key in ("l", "L"):
            self.toggle_mouse_lock()

    def toggle_mouse_lock(self):
        if self._is_mouse_locked:
            glfw.set_input_mode(self.canvas._window, glfw.CURSOR, glfw.CURSOR_NORMAL)
            self._is_mouse_locked = False
        else:
            glfw.set_input_mode(self.canvas._window, glfw.CURSOR, glfw.CURSOR_DISABLED)
            self._is_mouse_locked = True

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

    def draw_frame(self):
        # Zapíše príkazy do command_encoder
        command_encoder = self.device.create_command_encoder()
        current_texture = self.present_context.get_current_texture()
        current_texture_view = current_texture.create_view()

        # Kreslenie zelenej farby (R=0.0, G=1.0, B=0.0, A=1.0)
        render_pass = command_encoder.begin_render_pass(
            color_attachments=[
                {
                    "view": current_texture_view,
                    "resolve_target": None,
                    "clear_value": (0.0, 1.0, 0.0, 1.0),
                    "load_op": wgpu.LoadOp.clear,
                    "store_op": wgpu.StoreOp.store,
                }
            ],
        )

        render_pass.end()
        self.device.queue.submit([command_encoder.finish()])