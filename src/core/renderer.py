import glfw
import wgpu
import time
import ctypes
import struct  # Potrebné pre serializáciu dát spritov do buffra
from rendercanvas.auto import RenderCanvas
from core.backend.pipeline import Builder as RenderPipelineBuilder
from core.backend.compute_pipeline import Builder as ComputePipelineBuilder
from core.backend.bind_group_layout import Builder as BindGroupLayoutBuilder
from core.backend.atlas import Builder as AtlasBuilder
from core.backend.texture import new_offscreen_texture
from core.backend.definitions import *
from game.state import GameState
from game.components import Position, Sprite  # Import ECS komponentov pre dopytovanie
from game.systems import SpriteSystem

class Renderer:
    def __init__(self, title="VoidSeek", width=800, height=600):
        self._is_fullscreen = False
        self._is_mouse_locked = False
        self._last_mouse_x = None

        self.game_state = GameState()
        self.game_state.start()
        self.last_time = time.perf_counter()

        self.size = (width, height)
        self.canvas = RenderCanvas(title=title, size=(width, height))
        self.toggle_mouse_lock()
        self.toggle_fullscreen()

        self.device = wgpu.utils.get_default_device()
        self.queue = self.device.queue
        self.present_context = self.canvas.get_wgpu_context()
        self.render_texture_format = self.present_context.get_preferred_format(self.device.adapter)
        self.present_context.configure(device=self.device, format=self.render_texture_format)
        
        offscreen_format = wgpu.TextureFormat.rgba8unorm
        
        self.bind_group_layouts = self._build_bind_groups_layouts(self.device)
        self.render_pipelines = self._build_render_pipelines(self.device, self.render_texture_format, offscreen_format, self.bind_group_layouts)
        self.compute_pipelines = self._build_compute_pipelines(self.device, self.bind_group_layouts)

        # Offscreen textúra a Blit
        offscreen_view, offscreen_sampler = new_offscreen_texture(self.device, RENDER_HEIGHT, RENDER_WIDTH, offscreen_format)
        blit_bind_group = self.device.create_bind_group(
            label="Blit Bind Group",
            layout=self.bind_group_layouts[BindScope.BlitTexture],
            entries=[
                {"binding": 0, "resource": offscreen_view},
                {"binding": 1, "resource": offscreen_sampler},
            ]
        )
        self.blit_resources = BlitResources(offscreen_view, blit_bind_group)

        # Atlas textúr pre prostredie (Steny, Podlahy, Stropy)
        atlas_texture = self._create_atlas_texture(self.device, self.queue, wgpu.TextureFormat.rgba8unorm_srgb)
        atlas_view = atlas_texture.create_view(
            label="Texture Array View",
            dimension=wgpu.TextureViewDimension.d2_array
        )
        atlas_sampler = self.device.create_sampler(
            label="Retro Sampler",
            address_mode_u=wgpu.AddressMode.clamp_to_edge,
            address_mode_v=wgpu.AddressMode.clamp_to_edge,
            address_mode_w=wgpu.AddressMode.clamp_to_edge,
            mag_filter=wgpu.FilterMode.nearest,
            min_filter=wgpu.FilterMode.nearest,
            mipmap_filter=wgpu.MipmapFilterMode.nearest,
        )
        atlas_bind_group = self.device.create_bind_group(
            label="Texture Array Bind Group",
            layout=self.bind_group_layouts[BindScope.AtlasTexture],
            entries=[
                {"binding": 0, "resource": atlas_view},
                {"binding": 1, "resource": atlas_sampler},
            ]
        )
        self.atlas_resources = AtlasResources(atlas_bind_group, atlas_view)

        # =====================================================================
        # Inicializácia Atlasu pre Sprity
        # =====================================================================
        atlas_sprite_texture = self._create_atlas_texture(
            self.device, self.queue, wgpu.TextureFormat.rgba8unorm_srgb, 
            ["Sprite-bg.png", "Sprite-no-bg.png"]
        )
        atlas_sprite_view = atlas_sprite_texture.create_view(
            label="Sprite Texture Array View",
            dimension=wgpu.TextureViewDimension.d2_array
        )
        atlas_sprite_sampler = self.device.create_sampler(
            label="Sprite Retro Sampler",
            address_mode_u=wgpu.AddressMode.clamp_to_edge,
            address_mode_v=wgpu.AddressMode.clamp_to_edge,
            address_mode_w=wgpu.AddressMode.clamp_to_edge,
            mag_filter=wgpu.FilterMode.nearest,
            min_filter=wgpu.FilterMode.nearest,
            mipmap_filter=wgpu.MipmapFilterMode.nearest,
        )
        self.atlas_sprite_bind_group = self.device.create_bind_group(
            label="Sprite Texture Array Bind Group",
            layout=self.bind_group_layouts[BindScope.AtlasTexture],
            entries=[
                {"binding": 0, "resource": atlas_sprite_view},
                {"binding": 1, "resource": atlas_sprite_sampler},
            ]
        )

        # Buffer pre Ray Hits (1D Z-Buffer pre orezávanie spritov za stenami)
        self.ray_hits_buffer = self.device.create_buffer(
            label="Ray Hits Buffer",
            size=RENDER_WIDTH * 16,
            usage=wgpu.BufferUsage.STORAGE
        )
        self.ray_hits_bind_group = self.device.create_bind_group(
            label="Ray Hits Bind Group",
            layout=self.bind_group_layouts[BindScope.RayHits],
            entries=[{"binding": 0, "resource": {"buffer": self.ray_hits_buffer, "offset": 0, "size": self.ray_hits_buffer.size}}]
        )

        # =====================================================================
        # Buffer pre Inštancie Spritov (ECS dáta posielané na GPU)
        # =====================================================================
        # Štruktúra jedného spritu má 32 bajtov: position(vec3=12b) + scale(4b) + atlas_index(4b) + _padding(12b)
        self.sprites_buffer = self.device.create_buffer(
            label="Sprite Instances Buffer",
            size=MAX_SPRITES * 32,
            usage=wgpu.BufferUsage.STORAGE | wgpu.BufferUsage.COPY_DST
        )
        self.sprites_bind_group = self.device.create_bind_group(
            label="Sprite Instances Bind Group",
            layout=self.bind_group_layouts[BindScope.SpriteInstances],
            entries=[{"binding": 0, "resource": {"buffer": self.sprites_buffer, "offset": 0, "size": self.sprites_buffer.size}}]
        )
        self.sprite_count = 0

        # Inicializácia kamery s defaultnými hodnotami
        camera_data = (ctypes.c_float * 8)(*([0.0]*8))
        self.camera_buffer = self.device.create_buffer_with_data(
            data=camera_data,
            usage=wgpu.BufferUsage.UNIFORM | wgpu.BufferUsage.COPY_DST
        )
        camera_bind_group = self.device.create_bind_group(
            label="Camera Bind Group",
            layout=self.bind_group_layouts[BindScope.Camera],
            entries=[{"binding": 0, "resource": {"buffer": self.camera_buffer, "offset": 0, "size": self.camera_buffer.size}}]
        )
        self.camera_resources = CameraResources(camera_bind_group, self.camera_buffer)

        # Inicializácia mapy s defaultnými hodnotami
        map_settings_data = (ctypes.c_uint32 * 4)(MAX_MAP_WIDTH, MAX_MAP_HEIGHT, TILE_SIZE, 5)
        self.map_settings_buffer = self.device.create_buffer_with_data(
            data=map_settings_data,
            usage=wgpu.BufferUsage.UNIFORM | wgpu.BufferUsage.COPY_DST
        )
        
        map_data_init = (ctypes.c_uint32 * (MAX_MAP_TILES * 4))(*([0] * (MAX_MAP_TILES * 4)))
        self.map_buffer = self.device.create_buffer_with_data(
            data=map_data_init,
            usage=wgpu.BufferUsage.STORAGE | wgpu.BufferUsage.COPY_DST
        )
        map_bind_group = self.device.create_bind_group(
            label="Map Bind Group",
            layout=self.bind_group_layouts[BindScope.Map],
            entries=[
                {"binding": 0, "resource": {"buffer": self.map_buffer, "offset": 0, "size": self.map_buffer.size}},
                {"binding": 1, "resource": {"buffer": self.map_settings_buffer, "offset": 0, "size": self.map_settings_buffer.size}},
            ]
        )
        self.map_resources = MapResources(map_bind_group, self.map_buffer, self.map_settings_buffer)

        self.compute_bind_group = self.device.create_bind_group(
            label="Compute Bind Group",
            layout=self.bind_group_layouts[BindScope.ComputeRayHits],
            entries=[
                {"binding": 0, "resource": {"buffer": self.camera_resources.buffer, "offset": 0, "size": self.camera_resources.buffer.size}},
                {"binding": 1, "resource": {"buffer": self.map_resources.settings_buffer, "offset": 0, "size": self.map_resources.settings_buffer.size}},
                {"binding": 2, "resource": {"buffer": self.map_resources.data_buffer, "offset": 0, "size": self.map_resources.data_buffer.size}},
                {"binding": 3, "resource": {"buffer": self.ray_hits_buffer, "offset": 0, "size": self.ray_hits_buffer.size}},
            ]
        )

        self.update_map(self.game_state.get_map_data())

        self.canvas.request_draw(self.draw_frame)
        self.canvas.add_event_handler(self.on_key_down, "key_down")
        self.canvas.add_event_handler(self.on_key_up, "key_up")
        self.canvas.add_event_handler(self.on_pointer_move, "pointer_move")

    def _build_bind_groups_layouts(self, device):
        layouts = {}
        builder = BindGroupLayoutBuilder(device)

        builder.add_entry({
            "binding": 0,
            "visibility": wgpu.ShaderStage.VERTEX | wgpu.ShaderStage.FRAGMENT,
            "buffer": {"type": wgpu.BufferBindingType.uniform}
        })
        layouts[BindScope.Camera] = builder.build("Camera Bind Group Layout")

        builder.add_entry({
            "binding": 0,
            "visibility": wgpu.ShaderStage.FRAGMENT,
            "buffer": {"type": wgpu.BufferBindingType.read_only_storage}
        })
        builder.add_entry({
            "binding": 1,
            "visibility": wgpu.ShaderStage.VERTEX | wgpu.ShaderStage.FRAGMENT,
            "buffer": {"type": wgpu.BufferBindingType.uniform}
        })
        layouts[BindScope.Map] = builder.build("Map Bind Group Layout")

        builder.add_entry({
            "binding": 0,
            "visibility": wgpu.ShaderStage.FRAGMENT,
            "texture": {"sample_type": wgpu.TextureSampleType.float, "view_dimension": wgpu.TextureViewDimension.d2_array}
        })
        builder.add_entry({
            "binding": 1,
            "visibility": wgpu.ShaderStage.FRAGMENT,
            "sampler": {"type": wgpu.SamplerBindingType.filtering}
        })
        layouts[BindScope.AtlasTexture] = builder.build("Atlas Bind Group Layout")

        builder.add_entry({
            "binding": 0,
            "visibility": wgpu.ShaderStage.FRAGMENT,
            "texture": {"sample_type": wgpu.TextureSampleType.float, "view_dimension": wgpu.TextureViewDimension.d2}
        })
        builder.add_entry({
            "binding": 1,
            "visibility": wgpu.ShaderStage.FRAGMENT,
            "sampler": {"type": wgpu.SamplerBindingType.filtering}
        })
        layouts[BindScope.BlitTexture] = builder.build("Blit Bind Group Layout")

        builder.add_entry({
            "binding": 0,
            "visibility": wgpu.ShaderStage.FRAGMENT,
            "buffer": {"type": wgpu.BufferBindingType.read_only_storage}
        })
        layouts[BindScope.RayHits] = builder.build("Ray Hits Fragment Layout")

        builder.add_entry({
            "binding": 0,
            "visibility": wgpu.ShaderStage.VERTEX,
            "buffer": {"type": wgpu.BufferBindingType.read_only_storage}
        })
        layouts[BindScope.SpriteInstances] = builder.build("Sprite Instances Layout")

        builder.add_entry({
            "binding": 0,
            "visibility": wgpu.ShaderStage.COMPUTE,
            "buffer": {"type": wgpu.BufferBindingType.uniform}
        })
        builder.add_entry({
            "binding": 1,
            "visibility": wgpu.ShaderStage.COMPUTE,
            "buffer": {"type": wgpu.BufferBindingType.uniform}
        })
        builder.add_entry({
            "binding": 2,
            "visibility": wgpu.ShaderStage.COMPUTE,
            "buffer": {"type": wgpu.BufferBindingType.read_only_storage}
        })
        builder.add_entry({
            "binding": 3,
            "visibility": wgpu.ShaderStage.COMPUTE,
            "buffer": {"type": wgpu.BufferBindingType.storage}
        })
        layouts[BindScope.ComputeRayHits] = builder.build("Compute Ray Hits Layout")

        return layouts

    def _build_render_pipelines(self, device, surface_format, offscreen_format, layouts):
        pipelines = {}
        
        # Raycast
        raycast_builder = RenderPipelineBuilder(device)
        raycast_builder.set_shader_module("raycast_retro.wgsl", "vs_main", "fs_main")
        raycast_builder.set_pixel_format(offscreen_format)
        raycast_builder.add_bind_group_layout(layouts[BindScope.Camera])
        raycast_builder.add_bind_group_layout(layouts[BindScope.Map])
        raycast_builder.add_bind_group_layout(layouts[BindScope.AtlasTexture])
        raycast_builder.add_bind_group_layout(layouts[BindScope.RayHits])
        pipelines[RenderPipelineType.Raycast] = raycast_builder.build("Raycast Pipeline")

        #Sprite
        sprite_builder = RenderPipelineBuilder(device)
        sprite_builder.set_shader_module("sprite.wgsl", "vs_main", "fs_main")
        sprite_builder.set_pixel_format(offscreen_format)
        sprite_builder.add_bind_group_layout(layouts[BindScope.Camera])
        sprite_builder.add_bind_group_layout(layouts[BindScope.RayHits])
        sprite_builder.add_bind_group_layout(layouts[BindScope.AtlasTexture])
        sprite_builder.add_bind_group_layout(layouts[BindScope.SpriteInstances])
        sprite_builder.add_bind_group_layout(layouts[BindScope.Map])
        pipelines[RenderPipelineType.Sprite] = sprite_builder.build("Sprite Pipeline")

        # Blit
        blit_builder = RenderPipelineBuilder(device)
        blit_builder.set_shader_module("blit.wgsl", "vs_main", "fs_main")
        blit_builder.set_pixel_format(surface_format)
        blit_builder.add_bind_group_layout(layouts[BindScope.BlitTexture])
        pipelines[RenderPipelineType.Blit] = blit_builder.build("Blit Pipeline")

        return pipelines

    def _create_atlas_texture(self, device, queue, format, textures_list=None):
        if textures_list is None:
            textures_list = ["Wall-Texture.png", "Floor-Texture.png", "Ceiling-Texture.png"]
        builder = AtlasBuilder(device, queue)
        builder.set_pixel_format(format)
        try:
            builder.add_textures(textures_list)
        except Exception as e:
            print(f"Varovanie: Textúry atlasu sa nepodarilo načítať. Chyba: {e}")
        return builder.build("Atlas Texture")

    def _build_compute_pipelines(self, device, layouts):
        pipelines = {}
        builder = ComputePipelineBuilder(device)
        builder.set_shader_module("raycast_compute.wgsl", "cs_main")
        builder.add_bind_group_layout(layouts[BindScope.ComputeRayHits])
        pipelines[ComputePipelineType.Raycast] = builder.build("Raycast Compute Pipeline")
        return pipelines

    def update_camera(self, cam_x, cam_y, cam_angle):
        import math
        dir_x = math.cos(cam_angle)
        dir_y = math.sin(cam_angle)

        fov_scale = 0.66
        plane_x = -dir_y * fov_scale
        plane_y = dir_x * fov_scale

        camera_data = (ctypes.c_float * 8)(
            cam_x, cam_y,
            dir_x, dir_y,
            plane_x, plane_y,
            float(RENDER_WIDTH), float(RENDER_HEIGHT)
        )
        self.queue.write_buffer(self.camera_resources.buffer, 0, camera_data)

    def update_map(self, map_data):
        c_map_data = (ctypes.c_uint32 * len(map_data))(*map_data)
        self.queue.write_buffer(self.map_resources.data_buffer, 0, c_map_data)

    def update_map_settings(self, width, height, tile_size, render_distance):
        data = (ctypes.c_uint32 * 4)(width, height, tile_size, render_distance)
        self.queue.write_buffer(self.map_resources.settings_buffer, 0, data)

    def _on_key_down(self, event):
        key = event.get("key").lower()
        if key == "escape":
            self.canvas.close()
        elif key == "p":
            self.toggle_fullscreen()
        elif key == "l":
            self.toggle_mouse_lock()
        elif key == "w":
            self.game_state.input.forward = True
        elif key == "s":
            self.game_state.input.backward = True
        elif key == "a":
            self.game_state.input.left = True
        elif key == "d":
            self.game_state.input.right = True

    def _on_key_up(self, event):
        key = event.get("key").lower()
        if key == "w":
            self.game_state.input.forward = False
        elif key == "s":
            self.game_state.input.backward = False
        elif key == "a":
            self.game_state.input.left = False
        elif key == "d":
            self.game_state.input.right = False

    def _on_pointer_move(self, event):
        if self._is_mouse_locked:
            x = event.get("x")
            if self._last_mouse_x is not None:
                dx = x - self._last_mouse_x
                self.game_state.input.mouse_dx += dx
            self._last_mouse_x = x
        else:
            self._last_mouse_x = None

    def toggle_mouse_lock(self):
        if self._is_mouse_locked:
            glfw.set_input_mode(self.canvas._window, glfw.CURSOR, glfw.CURSOR_NORMAL)
            self._is_mouse_locked = False
            self._last_mouse_x = None
        else:
            glfw.set_input_mode(self.canvas._window, glfw.CURSOR, glfw.CURSOR_DISABLED)
            self._is_mouse_locked = True
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
        self._last_mouse_x = None

    def update_sprites(self, cam_x, cam_y):
        sprites_with_dist = SpriteSystem.update(self.game_state.world, cam_x, cam_y)
        self.sprite_count = min(len(sprites_with_dist), 4096)
        
        if self.sprite_count > 0:
            sprite_bytes = bytearray()
            for i in range(self.sprite_count):
                _, pos, sprite_comp = sprites_with_dist[i]
                sprite_bytes.extend(struct.pack(
                    "<ffffI3I",
                    pos.x, pos.y, sprite_comp.z,
                    sprite_comp.scale,
                    sprite_comp.atlas_index,
                    0, 0, 0
                ))
            self.queue.write_buffer(self.sprites_buffer, 0, sprite_bytes)

    def draw_frame(self):
        current_time = time.perf_counter()
        delta_time = current_time - self.last_time
        self.last_time = current_time
        
        self.game_state.update(delta_time)
        
        cam_x, cam_y, cam_angle = self.game_state.camera_pose()
        self.update_camera(cam_x, cam_y, cam_angle)

        self.update_sprites(cam_x, cam_y)

        command_encoder = self.device.create_command_encoder(label="Render Encoder")

        # 1. Compute Pass
        compute_pass = command_encoder.begin_compute_pass(label="Raycast Compute Pass")
        compute_pass.set_pipeline(self.compute_pipelines[ComputePipelineType.Raycast])
        compute_pass.set_bind_group(0, self.compute_bind_group, [])
        dispatch_count = (RENDER_WIDTH + 63) // 64
        compute_pass.dispatch_workgroups(dispatch_count, 1, 1)
        compute_pass.end()

        # 2. Render Pass (do offscreen texture)
        render_pass = command_encoder.begin_render_pass(
            label="Raycast & Sprite Pass",
            color_attachments=[
                {
                    "view": self.blit_resources.offscreen_texture,
                    "resolve_target": None,
                    "clear_value": (0.0, 0.0, 0.0, 1.0),
                    "load_op": wgpu.LoadOp.clear,
                    "store_op": wgpu.StoreOp.store,
                }
            ],
        )
        # Vykreslenie 3D stien pomocou Raycastu
        render_pass.set_pipeline(self.render_pipelines[RenderPipelineType.Raycast])
        render_pass.set_bind_group(0, self.camera_resources.bind_group, [])
        render_pass.set_bind_group(1, self.map_resources.bind_group, [])
        render_pass.set_bind_group(2, self.atlas_resources.bind_group, [])
        render_pass.set_bind_group(3, self.ray_hits_bind_group, [])
        render_pass.draw(3, 1, 0, 0)

        #Vykreslenie všetkých inštancií spritov v rovnakom render passe
        if self.sprite_count > 0:
            render_pass.set_pipeline(self.render_pipelines[RenderPipelineType.Sprite])
            render_pass.set_bind_group(0, self.camera_resources.bind_group, [])
            render_pass.set_bind_group(1, self.ray_hits_bind_group, [])
            render_pass.set_bind_group(2, self.atlas_sprite_bind_group, [])
            render_pass.set_bind_group(3, self.sprites_bind_group, [])
            render_pass.set_bind_group(4, self.map_resources.bind_group, [])
            render_pass.draw(6, self.sprite_count, 0, 0)

        render_pass.end()
        
        # 3. Blit Pass (kreslí na okno)
        current_texture = self.present_context.get_current_texture()
        current_texture_view = current_texture.create_view()

        blit_pass = command_encoder.begin_render_pass(
            label="Blit Pass",
            color_attachments=[
                {
                    "view": current_texture_view,
                    "resolve_target": None,
                    "clear_value": (0.0, 0.0, 0.0, 1.0),
                    "load_op": wgpu.LoadOp.clear,
                    "store_op": wgpu.StoreOp.store,
                }
            ],
        )
        blit_pass.set_pipeline(self.render_pipelines[RenderPipelineType.Blit])
        blit_pass.set_bind_group(0, self.blit_resources.bind_group, [])
        blit_pass.draw(3, 1, 0, 0)
        blit_pass.end()

        self.device.queue.submit([command_encoder.finish()])
        self.canvas.request_draw(self.draw_frame)