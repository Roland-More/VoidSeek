from PIL import Image, ImageFont, ImageDraw
import wgpu
import ctypes

class FontAtlas:
    def __init__(self, device: wgpu.GPUDevice, font_path: str, font_size: int = 64):
        self.device = device
        self.font_size = font_size
        self.glyphs = {}
        
        chars = [chr(i) for i in range(32, 127)]
        
        try:
            font = ImageFont.truetype(font_path, font_size)
        except Exception as e:
            print(f"Error loading font {font_path}: {e}")
            font = ImageFont.load_default()
        

        cols = 10
        rows = (len(chars) + cols - 1) // cols
        
        cell_w = font_size * 2
        cell_h = font_size * 2
        
        atlas_w = cols * cell_w
        atlas_h = rows * cell_h
        
        img = Image.new("RGBA", (atlas_w, atlas_h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        
        for i, char in enumerate(chars):
            col = i % cols
            row = i // cols
            x = col * cell_w
            y = row * cell_h
            
            bbox = font.getbbox(char)
            left, top, right, bottom = bbox
            width = right - left
            height = bottom - top
            advance = font.getlength(char)
            
            draw.text((x - left, y - top), char, font=font, fill=(255, 255, 255, 255))
            
            u_min = x / atlas_w
            v_min = y / atlas_h
            u_max = (x + width) / atlas_w
            v_max = (y + height) / atlas_h
            
            self.glyphs[char] = {
                "u_min": u_min,
                "v_min": v_min,
                "u_max": u_max,
                "v_max": v_max,
                "width": width,
                "height": height,
                "advance": advance
            }
            
        # img.save("font_atlas_debug.png")
        img_data = img.tobytes()
        
        self.texture = self.device.create_texture(
            size=(atlas_w, atlas_h, 1),
            format=wgpu.TextureFormat.rgba8unorm_srgb,
            usage=wgpu.TextureUsage.TEXTURE_BINDING | wgpu.TextureUsage.COPY_DST,
        )
        
        self.device.queue.write_texture(
            {"texture": self.texture},
            img_data,
            {"bytes_per_row": atlas_w * 4, "rows_per_image": atlas_h},
            (atlas_w, atlas_h, 1),
        )
        
        self.texture_view = self.texture.create_view()
