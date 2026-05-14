import wgpu
import os

class Builder:
    def __init__(self, device: wgpu.GPUDevice):
        self.device = device
        self.shader_filename = ""
        self.entry = ""
        self.bind_group_layouts = []

    def reset(self):
        self.bind_group_layouts.clear()

    def set_shader_module(self, shader_filename: str, entry: str):
        self.shader_filename = shader_filename
        self.entry = entry

    def add_bind_group_layout(self, layout: wgpu.GPUBindGroupLayout):
        self.bind_group_layouts.append(layout)

    def build(self, label: str) -> wgpu.GPUComputePipeline:
        filepath = os.path.join(os.getcwd(), "src", "shaders", self.shader_filename)
        with open(filepath, "r") as f:
            source_code = f.read()

        shader_module = self.device.create_shader_module(
            label="Compute Shader Module",
            code=source_code
        )

        pipeline_layout = self.device.create_pipeline_layout(
            label="Compute Pipeline Layout",
            bind_group_layouts=self.bind_group_layouts
        )

        pipeline = self.device.create_compute_pipeline(
            label=label,
            layout=pipeline_layout,
            compute={
                "module": shader_module,
                "entry_point": self.entry
            }
        )
        self.reset()
        return pipeline