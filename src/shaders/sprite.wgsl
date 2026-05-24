struct Camera {
    position: vec2<f32>,
    direction: vec2<f32>,
    plane: vec2<f32>,
    resolution: vec2<f32>,
}

struct RayHit {
    distance:    f32,
    line_height: f32,
    wall_x:      f32,
    packed:      u32,
}

struct SpriteInstance {
    position: vec3<f32>,
    scale: f32,
    atlas_index: u32,
    _padding: array<u32, 3>,
}

struct MapSettings {
    width: u32,
    height: u32,
    tile_size: u32,
    render_distance: u32, 
}

@group(0) @binding(0) var<uniform> camera: Camera;
@group(1) @binding(0) var<storage, read> ray_hits: array<RayHit>;
@group(2) @binding(0) var texture_atlas: texture_2d_array<f32>;
@group(2) @binding(1) var texture_sampler: sampler;
@group(3) @binding(0) var<storage, read> sprites: array<SpriteInstance>;
@group(4) @binding(1) var<uniform> map_settings: MapSettings;

struct VertexOutput {
    @builtin(position) position: vec4<f32>,
    @location(0) uv: vec2<f32>,
    @location(1) atlas_index: f32,
    @location(2) sprite_distance: f32,
    @location(3) logical_x: f32, 
}

@vertex
fn vs_main(
    @builtin(vertex_index) vertex_index: u32,
    @builtin(instance_index) instance_index: u32
) -> VertexOutput {
    let sprite = sprites[instance_index];
    
    // Transformovať sprite pozíciu vzhľadom ku kamere (Kamera je v (0,0) a my počítame rozdiel)
    let sprite_pos = sprite.position.xy - (camera.position / f32(map_settings.tile_size));
    let sprite_z = sprite.position.z;

    // Transformácia do kamerového priestoru (Násobenie inverznou kamerovou maticou)
    let inv_det = 1.0 / (camera.plane.x * camera.direction.y - camera.direction.x * camera.plane.y);

    let transform_x = inv_det * (camera.direction.y * sprite_pos.x - camera.direction.x * sprite_pos.y);
    let transform_y = inv_det * (-camera.plane.y * sprite_pos.x + camera.plane.x * sprite_pos.y); // Toto je hĺbka!

    // Ak je sprite za nami (transform_y <= 0), posunieme ho preč (bude orezaný GPU)
    if (transform_y <= 0.0) {
        var out: VertexOutput;
        out.position = vec4<f32>(0.0, 0.0, -1000.0, 1.0); 
        return out; 
    }

    // Projekcia na obrazovku (kamera resolution x)
    let sprite_screen_x = i32((camera.resolution.x / 2.0) * (1.0 + transform_x / transform_y));

    // Vypočítame veľkosť spritu (šírku a výšku) na základe vzdialenosti
    let sprite_scale = abs((camera.resolution.y * 1.3333) / transform_y) * sprite.scale;
    
    // Tvorba billboarovaného štvorca zo 6 vrcholov
    var uv_coords = array<vec2<f32>, 6>(
        vec2<f32>(0.0, 1.0), vec2<f32>(1.0, 1.0), vec2<f32>(0.0, 0.0),
        vec2<f32>(1.0, 1.0), vec2<f32>(1.0, 0.0), vec2<f32>(0.0, 0.0) 
    );
    let uv = uv_coords[vertex_index];
    
    // Zistíme presné X a Y na pixelovej mriežke obrazovky (Posun a Roztiahnutie)
    let pixel_x = f32(sprite_screen_x) + (uv.x - 0.5) * sprite_scale;
    let pixel_y = (camera.resolution.y / 2.0) + (uv.y - 0.5) * sprite_scale - sprite_z * sprite_scale; 

    // Konvertujeme pixelové súradnice do NDC (Normalized Device Coordinates: -1 až 1)
    let ndc_x = (pixel_x / camera.resolution.x) * 2.0 - 1.0;
    let ndc_y = 1.0 - (pixel_y / camera.resolution.y) * 2.0;

    var out: VertexOutput;
    out.position = vec4<f32>(ndc_x, ndc_y, 0.5, 1.0);
    out.uv = uv;
    out.atlas_index = f32(sprite.atlas_index);
    out.sprite_distance = transform_y;
    out.logical_x = pixel_x;

    return out;
}

@fragment
fn fs_main(in: VertexOutput) -> @location(0) vec4<f32> {
    // 1. Získame náš logický herný stĺpec a prehodíme ho na celé číslo. 
    let screen_x = i32(in.logical_x);
    
    // 2. Prečítame dáta iba ak sme presne v našom hernom okne
    if (screen_x >= 0 && screen_x < i32(camera.resolution.x)) {
        let hit_data = ray_hits[screen_x];
        let hit = (hit_data.packed) & 0x1u; 
        
        // 3. Odrezanie spritu, ak je hlbšie ako stena (1D Z-Buffer)
        if (hit == 1u && in.sprite_distance > hit_data.distance) {
            discard; 
        }
    }

    let color = textureSampleLevel(
        texture_atlas, 
        texture_sampler,
        in.uv,
        i32(in.atlas_index), 
        0.0
    );

    if (color.a < 0.1) {
        discard;
    }

    // Prepočítame smer lúča pre toto konkrétne logické X na obrazovke
    let camera_x = 2.0 * f32(screen_x) / camera.resolution.x - 1.0;
    let ray_dir = camera.direction + camera.plane * camera_x;
    
    // Vynásobíme kolmú vzdialenosť spritu dĺžkou tohto konkrétneho lúča
    let per_pixel_distance = in.sprite_distance * length(ray_dir);

    let render_dist = f32(map_settings.render_distance);
    let intensity = clamp(1.0 - (per_pixel_distance / render_dist), 0.0, 1.0);

    return vec4<f32>(color.rgb * intensity, color.a);
}