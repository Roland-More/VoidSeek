struct Camera {
    position: vec2<f32>,
    direction: vec2<f32>,
    plane: vec2<f32>,
    resolution: vec2<f32>,
}
struct MapSettings {
    width: u32,
    height: u32,
    tile_size: u32,
    render_distance: u32, 
}
struct Tile {
    wall_texture_id: u32,
    floor_texture_id: u32,
    ceiling_texture_id: u32,
    _padding: u32,
}
struct RayHit {
    distance:    f32,
    line_height: f32,
    wall_x:      f32,
    packed:      u32,
}

const BIT_HIT:    u32 = 0u;
const BIT_TEX_ID: u32 = 1u;
const BIT_SIDE:   u32 = 17u;
const MASK_HIT:    u32 = 0x1u;
const MASK_TEX_ID: u32 = 0xFFFFu;
const MASK_SIDE:   u32 = 0x1u;

@group(0) @binding(0) var<uniform> camera: Camera;
@group(1) @binding(0) var<storage, read> map_data: array<Tile>;
@group(1) @binding(1) var<uniform> map_settings: MapSettings;
@group(2) @binding(0) var texture_atlas: texture_2d_array<f32>;
@group(2) @binding(1) var texture_sampler: sampler;
@group(3) @binding(0) var<storage, read> ray_hits: array<RayHit>;

struct VertexPayload {
    @builtin(position) position: vec4<f32>,
    @location(0) uv: vec2<f32>, 
}

@vertex
fn vs_main(@builtin(vertex_index) i: u32) -> VertexPayload {
    let positions = array<vec2<f32>, 3>(
        vec2<f32>(-1.0, -1.0),
        vec2<f32>( 3.0, -1.0),
        vec2<f32>(-1.0,  3.0)
    );
    var out: VertexPayload;
    let pos = positions[i];
    out.position = vec4<f32>(pos, 0.0, 1.0);
    out.uv = vec2<f32>(pos.x * 0.5 + 0.5, 1.0 - (pos.y * 0.5 + 0.5));
    return out;
}

@fragment
fn fs_main(in: VertexPayload) -> @location(0) vec4<f32> {
    let frag_y_pixels = in.uv.y * camera.resolution.y;

    let x = u32(in.uv.x * camera.resolution.x);
    let hit_data = ray_hits[x];

    let hit    = (hit_data.packed >> BIT_HIT)    & MASK_HIT;
    let tex_id = (hit_data.packed >> BIT_TEX_ID) & MASK_TEX_ID;
    let side   = (hit_data.packed >> BIT_SIDE)   & MASK_SIDE;

    let line_height = hit_data.line_height;
    
    // Potrebujeme nezaokrúhlený štart pre plynulé mapovanie textúry steny
    let raw_draw_start = -line_height / 2.0 + camera.resolution.y / 2.0;
    
    let draw_start  = floor(raw_draw_start);
    let draw_end    = ceil(line_height / 2.0 + camera.resolution.y / 2.0);

    let camera_x = 2.0 * f32(x) / camera.resolution.x - 1.0;
    
    let ray_dir  = camera.direction + camera.plane * camera_x;
    let ray_pos  = camera.position / f32(map_settings.tile_size);
    let aspect_fix = 1.3333;

    // --- PRIDANÉ: Ukladanie výsledkov pre neskoršiu úpravu svetla ---
    var final_color = vec4<f32>(0.0, 0.0, 0.0, 1.0); // Predvolená farba (čierna)
    var pixel_distance: f32 = 0.0;                   // Vzdialenosť konkrétneho pixelu

    if (frag_y_pixels < draw_start) {
        // --- STROP ---
        let p = (camera.resolution.y / 2.0) - frag_y_pixels;
        var row_dist = (camera.resolution.y * aspect_fix / 2.0) / p;

        if (hit == 1u) {
            row_dist = min(row_dist, hit_data.distance - 0.001);
        }
        
        pixel_distance = row_dist; // Uložíme vzdialenosť stropu
        
        let floor_pos = ray_pos + row_dist * ray_dir;
        let map_x = i32(floor(floor_pos.x));
        let map_y = i32(floor(floor_pos.y));

        if (map_x >= 0 && map_x < i32(map_settings.width) &&
            map_y >= 0 && map_y < i32(map_settings.height)) {

            let map_index = u32(map_y) * map_settings.width + u32(map_x);
            let tile = map_data[map_index];

            if (tile.ceiling_texture_id > 0u) {
                let tex_x = 1.0 - fract(floor_pos.x);
                let tex_y = 1.0 - fract(floor_pos.y);
                let atlas_layer = i32(tile.ceiling_texture_id) - 1;
                let color = textureSampleLevel(texture_atlas, texture_sampler,
                    vec2<f32>(tex_x, tex_y), atlas_layer, 0.0);
                final_color = vec4<f32>(color.rgb * 0.5, 1.0);
            } else {
                final_color = vec4<f32>(0.1, 0.1, 0.1, 1.0);
            }
        } else {
            final_color = vec4<f32>(0.1, 0.1, 0.1, 1.0);
        }

    } else if (frag_y_pixels > draw_end) {
        // --- PODLAHA ---
        let p = frag_y_pixels - (camera.resolution.y / 2.0);
        var row_dist = (camera.resolution.y * aspect_fix / 2.0) / p;

        if (hit == 1u) {
            row_dist = min(row_dist, hit_data.distance - 0.001);
        }

        pixel_distance = row_dist; // Uložíme vzdialenosť podlahy
        
        let floor_pos = ray_pos + row_dist * ray_dir;
        let map_x = i32(floor(floor_pos.x));
        let map_y = i32(floor(floor_pos.y));

        if (map_x >= 0 && map_x < i32(map_settings.width) &&
            map_y >= 0 && map_y < i32(map_settings.height)) {

            let map_index = u32(map_y) * map_settings.width + u32(map_x);
            let tile = map_data[map_index];

            if (tile.floor_texture_id > 0u) {
                let tex_x = fract(floor_pos.x);
                let tex_y = 1.0 - fract(floor_pos.y);
                let atlas_layer = i32(tile.floor_texture_id) - 1;
                let color = textureSampleLevel(texture_atlas, texture_sampler,
                    vec2<f32>(tex_x, tex_y), atlas_layer, 0.0);
                final_color = vec4<f32>(color.rgb * 0.7, 1.0);
            } else {
                final_color = vec4<f32>(0.2, 0.2, 0.2, 1.0);
            }
        } else {
            final_color = vec4<f32>(0.2, 0.2, 0.2, 1.0);
        }

    } else {
        // --- STENA ---
        pixel_distance = hit_data.distance; // Uložíme vzdialenosť steny

        if (hit == 1u) { 
            let tex_x = hit_data.wall_x;
            let tex_y = clamp((frag_y_pixels - raw_draw_start) / line_height, 0.0, 1.0);
            let atlas_layer = i32(tex_id) - 1;

            var color = textureSampleLevel(texture_atlas, texture_sampler,
                vec2<f32>(tex_x, tex_y), atlas_layer, 0.0);

            if (side == 1u) {
                color = vec4<f32>(color.rgb * 0.35, color.a);
            }
            final_color = color;
        }
    }

    // --- VÝPOČET TMY (FADE TO BLACK) ---
    let render_dist = f32(map_settings.render_distance);
    
    // Týmto dosiahneme kruhový fog, ktorý sa na okrajoch obrazovky nevzďaľuje
    let true_distance = pixel_distance * length(ray_dir);
    
    // Intenzita stmavovania: 1.0 = sme pri kamere, 0.0 = sme za hranicou vykresľovania
    let intensity = clamp(1.0 - (true_distance / render_dist), 0.0, 1.0);

    // Výsledná farba sa vynásobí intenzitou. 
    return vec4<f32>(final_color.rgb * intensity, final_color.a);
}