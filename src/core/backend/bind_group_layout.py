import wgpu

class Builder:
    def __init__(self, device: wgpu.GPUDevice):
        self.device = device
        self.entries = []

    def reset(self):
        self.entries.clear()

    def add_entry(self, entry: dict):
        self.entries.append(entry)

    def build(self, label: str) -> wgpu.GPUBindGroupLayout:
        layout = self.device.create_bind_group_layout(
            label=label,
            entries=self.entries
        )
        self.reset()
        return layout