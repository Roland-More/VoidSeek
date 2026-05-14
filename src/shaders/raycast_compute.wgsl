struct Camera {
    position:   vec2<f32>,
    direction:  vec2<f32>,
    plane:      vec2<f32>,
    resolution: vec2<f32>,
}

struct MapSettings {
    width:             u32,
    height:            u32,
    tile_size:         u32,
    render_distance:   u32, 
}

struct Tile {
    wall_texture_id:    u32,
    floor_texture_id:   u32,
    ceiling_texture_id: u32,
    
    _padding:           u32,
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

@group(0) @binding(0) var<uniform>             camera:       Camera;

@group(0) @binding(1) var<uniform>             map_settings: MapSettings;
@group(0) @binding(2) var<storage, read>       map_data:     array<Tile>;

@group(0) @binding(3) var<storage, read_write> ray_hits:     array<RayHit>;


@compute @workgroup_size(64)
fn cs_main(@builtin(global_invocation_id) global_id: vec3<u32>) {
    let x = global_id.x;
    if (x >= u32(camera.resolution.x)) { return; }

    let max_steps = u32(f32(map_settings.render_distance) * 1.4143) + 2u;

    let camera_x = 2.0 * f32(x) / camera.resolution.x - 1.0; // Zisti kde sa nachádza x pixel v zornom poli (-1 až 1)
    let ray_dir = camera.direction + camera.plane * camera_x; // Zisti smer lúča pre tento pixel

    let ray_pos = camera.position / f32(map_settings.tile_size); // Ziskame ray poziciu v mapových jednotkách (napr. ak je tile_size 64, a kamera je na pozícii (128, 128), ray_pos bude (2, 2))
    var map_pos = vec2<i32>(floor(ray_pos)); // Ziskame aktuálnu mapovú pozíciu (napr. (2, 2))

    let delta_dist = vec2<f32>(
        abs(1.0 / ray_dir.x),
        abs(1.0 / ray_dir.y)
    ); // Vypočítame vzdialenosť, ktorú musí lúč prejsť, aby sa posunul o jednu mapovú jednotku v X alebo Y smere

    var step_dir = vec2<i32>(0, 0); // Určíme krok smeru (1 alebo -1)
    var side_dist = vec2<f32>(0.0, 0.0); // Vzdialenosť k najbližšiej tile hranici

    if (ray_dir.x < 0.0) {
        step_dir.x = -1;
        side_dist.x = (ray_pos.x - f32(map_pos.x)) * delta_dist.x;
    } else {
        step_dir.x = 1;
        side_dist.x = (f32(map_pos.x) + 1.0 - ray_pos.x) * delta_dist.x;
    }

    if (ray_dir.y < 0.0) {
        step_dir.y = -1;
        side_dist.y = (ray_pos.y - f32(map_pos.y)) * delta_dist.y;
    } else {
        step_dir.y = 1;
        side_dist.y = (f32(map_pos.y) + 1.0 - ray_pos.y) * delta_dist.y;
    }

    var hit = false;
    var side = 0;
    var hit_wall_tex_id = 0u;

    for (var i: u32 = 0; i < max_steps; i++) {
        if (side_dist.x < side_dist.y) { // Posuneme sa na dalsiu tile podla toho ktora je bližšie
            side_dist.x += delta_dist.x;
            map_pos.x += step_dir.x;
            side = 0;
        } else {
            side_dist.y += delta_dist.y;
            map_pos.y += step_dir.y;
            side = 1;
        }

        if (map_pos.x >= 0 && map_pos.x < i32(map_settings.width) &&
            map_pos.y >= 0 && map_pos.y < i32(map_settings.height)) { // Zkontrolujeme, či nie sme mimo mapy
            
            let map_index = u32(map_pos.y) * map_settings.width + u32(map_pos.x);
            let tile = map_data[map_index];
            
            if (tile.wall_texture_id > 0u) { // Ak narazime na stenu, zaznamenáme hit a uložíme ID textúry steny
                hit = true;
                hit_wall_tex_id = tile.wall_texture_id;
                break;
            }
        }
    }

    if (!hit) { // Ak nie vratíme nič
    ray_hits[x] = RayHit(0.0, 0.0, 0.0, 0u);
        return;
    }

    var perp_wall_dist: f32;
    if (side == 0) {
        perp_wall_dist = (f32(map_pos.x) - ray_pos.x + (1.0 - f32(step_dir.x)) / 2.0) / ray_dir.x;
    } else {
        perp_wall_dist = (f32(map_pos.y) - ray_pos.y + (1.0 - f32(step_dir.y)) / 2.0) / ray_dir.y;
    }

    var wall_x: f32;
    if (side == 0) { 
        wall_x = ray_pos.y + perp_wall_dist * ray_dir.y;
    } else { 
        wall_x = ray_pos.x + perp_wall_dist * ray_dir.x;
    }
    wall_x = fract(wall_x);

    if (side == 0 && ray_dir.x < 0.0) { wall_x = 1.0 - wall_x; }
    if (side == 1 && ray_dir.y > 0.0) { wall_x = 1.0 - wall_x; }

    let aspect_fix = 1.3333; 
    let line_height = (camera.resolution.y * aspect_fix) / perp_wall_dist;

    var packed: u32 = 0u;
    packed |= u32(hit);
    packed |= (hit_wall_tex_id & MASK_TEX_ID) << BIT_TEX_ID;
    packed |= (u32(side) << BIT_SIDE);

    ray_hits[x] = RayHit(perp_wall_dist, line_height, wall_x, packed);
}