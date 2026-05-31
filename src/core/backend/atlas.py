import os
import wgpu
from PIL import Image

class Builder:
    def __init__(self, device: wgpu.GPUDevice, queue: wgpu.GPUQueue):
        self.device = device
        self.queue = queue
        self.rgba_data = bytearray()
        self.texture_width = 0
        self.texture_height = 0
        self.layers = 0
        self.pixel_format = wgpu.TextureFormat.rgba8unorm_srgb

    def add_textures(self, names: list[str]):
        self.layers = len(names)
        for i, name in enumerate(names):
            src_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            filepath = os.path.join(src_dir, "assets", name)
            try:
                img = Image.open(filepath).convert("RGBA")
            except Exception as e:
                raise RuntimeError(f"Failed to open image: {e}")
            
            w, h = img.size
            if i == 0:
                # Prvý obrázok nastaví referenčné rozmery
                self.texture_width = w
                self.texture_height = h
            else:
                assert w == self.texture_width and h == self.texture_height, f"Image {name} má zlé rozmery!"
            
            self.rgba_data.extend(img.tobytes())

    def set_pixel_format(self, pixel_format: wgpu.TextureFormat):
        self.pixel_format = pixel_format

    def build(self, label: str) -> wgpu.GPUTexture:
        texture_size = [self.texture_width, self.texture_height, self.layers]

        texture = self.device.create_texture(
            label=label,
            size=texture_size,
            mip_level_count=1,
            sample_count=1,
            dimension=wgpu.TextureDimension.d2,
            format=self.pixel_format,
            usage=wgpu.TextureUsage.TEXTURE_BINDING | wgpu.TextureUsage.COPY_DST,
        )

        self.queue.write_texture(
            {
                "texture": texture,
                "mip_level": 0,
                "origin": (0, 0, 0),
                "aspect": wgpu.TextureAspect.all,
            },
            self.rgba_data,
            {
                "offset": 0,
                "bytes_per_row": 4 * self.texture_width,
                "rows_per_image": self.texture_height,
            },
            texture_size
        )

        self.rgba_data.clear()
        return texture
