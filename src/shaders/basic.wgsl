struct VertexOutput {
    @builtin(position) position: vec4<f32>,
    @location(0) color: vec4<f32>,
};

@vertex
fn vs_main(@builtin(vertex_index) in_vertex_index: u32) -> VertexOutput {
    // 3 vrcholy pre trojuholník
    var positions = array<vec2<f32>, 3>(
        vec2<f32>( 0.0,  0.5), // hore
        vec2<f32>(-0.5, -0.5), // vľavo dole
        vec2<f32>( 0.5, -0.5)  // vpravo dole
    );

    // Farby pre trojuholník
    var colors = array<vec3<f32>, 3>(
        vec3<f32>(1.0, 0.0, 0.0), // červená
        vec3<f32>(0.0, 1.0, 0.0), // zelená
        vec3<f32>(0.0, 0.0, 1.0)  // modrá
    );

    var out: VertexOutput;
    out.position = vec4<f32>(positions[in_vertex_index], 0.0, 1.0);
    out.color = vec4<f32>(colors[in_vertex_index], 1.0);
    return out;
}

@fragment
fn fs_main(in: VertexOutput) -> @location(0) vec4<f32> {
    return in.color;
}