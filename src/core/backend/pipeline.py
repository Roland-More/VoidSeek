import wgpu
import os

class Builder:
    def __init__(self, device: wgpu.GPUDevice):
        self.device = device
        self.shader_filename = ""
        self.vertex_entry = ""
        self.fragment_entry = ""
        self.pixel_format = wgpu.TextureFormat.rgba8unorm_srgb
        self.bind_group_layouts = []
        self.blend_state = {
            "color": {
                "src_factor": wgpu.BlendFactor.one,
                "dst_factor": wgpu.BlendFactor.zero,
                "operation": wgpu.BlendOperation.add,
            },
            "alpha": {
                "src_factor": wgpu.BlendFactor.one,
                "dst_factor": wgpu.BlendFactor.zero,
                "operation": wgpu.BlendOperation.add,
            }
        }

    def reset(self):
        self.bind_group_layouts.clear()

    def set_shader_module(self, shader_filename: str, vertex_entry: str, fragment_entry: str):
        self.shader_filename = shader_filename
        self.vertex_entry = vertex_entry
        self.fragment_entry = fragment_entry

    def add_bind_group_layout(self, layout: wgpu.GPUBindGroupLayout):
        self.bind_group_layouts.append(layout)

    def set_pixel_format(self, pixel_format: wgpu.TextureFormat):
        self.pixel_format = pixel_format

    def enable_alpha_blend(self):
        self.blend_state = {
            "color": {
                "src_factor": wgpu.BlendFactor.src_alpha,
                "dst_factor": wgpu.BlendFactor.one_minus_src_alpha,
                "operation": wgpu.BlendOperation.add,
            },
            "alpha": {
                "src_factor": wgpu.BlendFactor.one,
                "dst_factor": wgpu.BlendFactor.one_minus_src_alpha,
                "operation": wgpu.BlendOperation.add,
            }
        }

    def build(self, label: str) -> wgpu.GPURenderPipeline:
        filepath = os.path.join(os.getcwd(), "src", "shaders", self.shader_filename)
        with open(filepath, "r") as f:
            source_code = f.read()

        shader_module = self.device.create_shader_module(
            label="Shader Module",
            code=source_code
        )

        pipeline_layout = self.device.create_pipeline_layout(
            label="Render Pipeline Layout",
            bind_group_layouts=self.bind_group_layouts
        )

        pipeline = self.device.create_render_pipeline(
            label=label,
            layout=pipeline_layout,
            vertex={
                "module": shader_module,
                "entry_point": self.vertex_entry,
                "buffers": []
            },
            primitive={
                "topology": wgpu.PrimitiveTopology.triangle_list,
                "front_face": wgpu.FrontFace.ccw,
                "cull_mode": wgpu.CullMode.back,
            },
            fragment={
                "module": shader_module,
                "entry_point": self.fragment_entry,
                "targets": [
                    {
                        "format": self.pixel_format,
                        "blend": self.blend_state,
                        "write_mask": wgpu.ColorWrite.ALL,
                    }
                ]
            },
            multisample={
                "count": 1,
                "mask": 0xFFFFFFFF,
                "alpha_to_coverage_enabled": False,
            }
        )
        self.reset()
        return pipeline