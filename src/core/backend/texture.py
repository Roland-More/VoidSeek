import wgpu

def new_offscreen_texture(
    device: wgpu.GPUDevice, 
    height: int, 
    width: int, 
    format: wgpu.TextureFormat
) -> tuple[wgpu.GPUTextureView, wgpu.GPUSampler]:
    
    offscreen_texture = device.create_texture(
        label="Offscreen Texture",
        size=[width, height, 1],
        mip_level_count=1,
        sample_count=1,
        dimension=wgpu.TextureDimension.d2,
        format=format,
        usage=wgpu.TextureUsage.RENDER_ATTACHMENT | wgpu.TextureUsage.TEXTURE_BINDING,
    )

    offscreen_view = offscreen_texture.create_view(
        label="Offscreen Texture View"
    )

    offscreen_sampler = device.create_sampler(
        label="Offscreen Sampler",
        address_mode_u=wgpu.AddressMode.clamp_to_edge,
        address_mode_v=wgpu.AddressMode.clamp_to_edge,
        address_mode_w=wgpu.AddressMode.clamp_to_edge,
        mag_filter=wgpu.FilterMode.nearest,
        min_filter=wgpu.FilterMode.nearest,
        mipmap_filter=wgpu.MipmapFilterMode.nearest,
    )

    return offscreen_view, offscreen_sampler