struct Camera {
    position: vec2<f32>,
    direction: vec2<f32>,
    plane: vec2<f32>,
    resolution: vec2<f32>,
}

struct TextInstance {
    position: vec2<f32>,
    size: vec2<f32>,
    uv_min: vec2<f32>,
    uv_max: vec2<f32>,
    color: vec4<f32>,
}

@group(0) @binding(0) var<uniform> camera: Camera;
@group(1) @binding(0) var texture_atlas: texture_2d<f32>;
@group(1) @binding(1) var texture_sampler: sampler;
@group(2) @binding(0) var<storage, read> instances: array<TextInstance>;

struct VertexOutput {
    @builtin(position) position: vec4<f32>,
    @location(0) uv: vec2<f32>,
    @location(1) color: vec4<f32>,
}

@vertex
fn vs_main(
    @builtin(vertex_index) vertex_index: u32,
    @builtin(instance_index) instance_index: u32
) -> VertexOutput {
    let instance = instances[instance_index];
    
    // 6 vrcholov pre quad
    var pos_coords = array<vec2<f32>, 6>(
        vec2<f32>(0.0, 1.0), vec2<f32>(1.0, 1.0), vec2<f32>(0.0, 0.0),
        vec2<f32>(1.0, 1.0), vec2<f32>(1.0, 0.0), vec2<f32>(0.0, 0.0) 
    );
    
    let p = pos_coords[vertex_index];
    
    let pixel_x = instance.position.x + p.x * instance.size.x;
    let pixel_y = instance.position.y + p.y * instance.size.y;
    
    let ndc_x = (pixel_x / camera.resolution.x) * 2.0 - 1.0;
    let ndc_y = 1.0 - (pixel_y / camera.resolution.y) * 2.0;
    
    let uv_x = mix(instance.uv_min.x, instance.uv_max.x, p.x);
    let uv_y = mix(instance.uv_min.y, instance.uv_max.y, p.y);
    
    var out: VertexOutput;
    out.position = vec4<f32>(ndc_x, ndc_y, 0.0, 1.0);
    out.uv = vec2<f32>(uv_x, uv_y);
    out.color = instance.color;
    return out;
}

@fragment
fn fs_main(in: VertexOutput) -> @location(0) vec4<f32> {
    let tex_color = textureSample(texture_atlas, texture_sampler, in.uv);
    let final_color = tex_color * in.color;
    if (final_color.a < 0.1) {
        discard;
    }
    return final_color;
}
