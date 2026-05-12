import wgpu
from rendercanvas.auto import RenderCanvas

class Renderer:
    def __init__(self, title="VoidSeek", width=800, height=600):
        # 1. Vytvorenie plátna (canvas) automaticky cez rendercanvas, ktorý podporuje GLFW
        self.canvas = RenderCanvas(title=title, size=(width, height))
        
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
        if event.get("key") == "Escape":
            self.canvas.close()

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
