import math
import numpy as np
from numba import njit
from .ecs import World
from .components import Position, Rotation, Velocity, PlayerController, Sprite, Interactible
from .input import InputState

TILE_SIZE = 64
MAX_MAP_WIDTH = 8
MAX_MAP_HEIGHT = 8
PLAYER_RADIUS = 0.15

# =============================================================================
# Numba-optimalizované matematické funkcie
# =============================================================================

@njit(cache=True)
def _is_wall(check_x: float, check_y: float, map_walls, max_w: int, max_h: int, player_rad: float) -> bool:
    min_x = int(math.floor(check_x - player_rad))
    max_x = int(math.floor(check_x + player_rad))
    min_y = int(math.floor(check_y - player_rad))
    max_y = int(math.floor(check_y + player_rad))

    for map_x in range(min_x, max_x + 1):
        for map_y in range(min_y, max_y + 1):
            if map_x < 0 or map_x >= max_w or map_y < 0 or map_y >= max_h:
                return True
            map_index = map_y * max_w + map_x
            if map_index < len(map_walls) and map_walls[map_index] != 0:
                return True
    return False

@njit(cache=True)
def _dda_raycast(player_x: float, player_y: float, dir_x: float, dir_y: float, 
                 map_walls, max_w: int, max_h: int, max_dist: float):
    map_x = int(math.floor(player_x))
    map_y = int(math.floor(player_y))

    if dir_x != 0.0:
        delta_dist_x = abs(1.0 / dir_x)
    else:
        delta_dist_x = 1e30
    if dir_y != 0.0:
        delta_dist_y = abs(1.0 / dir_y)
    else:
        delta_dist_y = 1e30

    if dir_x < 0.0:
        step_x = -1
        side_dist_x = (player_x - map_x) * delta_dist_x
    else:
        step_x = 1
        side_dist_x = ((map_x + 1.0) - player_x) * delta_dist_x

    if dir_y < 0.0:
        step_y = -1
        side_dist_y = (player_y - map_y) * delta_dist_y
    else:
        step_y = 1
        side_dist_y = ((map_y + 1.0) - player_y) * delta_dist_y

    hit_distance = 0.0

    while hit_distance <= max_dist:
        if side_dist_x < side_dist_y:
            hit_distance = side_dist_x
            side_dist_x += delta_dist_x
            map_x += step_x
        else:
            hit_distance = side_dist_y
            side_dist_y += delta_dist_y
            map_y += step_y

        if hit_distance > max_dist:
            break

        if 0 <= map_x < max_w and 0 <= map_y < max_h:
            map_index = map_y * max_w + map_x
            if map_walls[map_index] != 0:
                return map_x, map_y, hit_distance

    return -1, -1, max_dist

class PlayerInputSystem:
    @staticmethod
    def update(world: World, inp: InputState):
        for entity_id, (rot, vel, ctrl) in world.get_components(Rotation, Velocity, PlayerController):
            # Rotácia
            if inp.mouse_dx != 0.0:
                rot.angle += inp.mouse_dx * ctrl.sensitivity
                if rot.angle < 0.0:
                    rot.angle += 2.0 * math.pi
                elif rot.angle >= 2.0 * math.pi:
                    rot.angle -= 2.0 * math.pi
                inp.mouse_dx = 0.0
            
            # Smerové vektory vypočítané z uhla
            vel.dx = math.cos(rot.angle)
            vel.dy = math.sin(rot.angle)

class MovementSystem:
    @staticmethod
    def update(world: World, delta_time: float, map_walls: list[int], inp: InputState):
        walls_arr = np.array(map_walls, dtype=np.int32)
        for entity_id, (pos, rot, vel) in world.get_components(Position, Rotation, Velocity):
            move_x = 0.0
            move_y = 0.0

            if inp.forward:
                move_x += vel.dx
                move_y += vel.dy

            if inp.backward:
                move_x -= vel.dx
                move_y -= vel.dy

            strafe_x = math.cos(rot.angle + math.pi / 2.0)
            strafe_y = math.sin(rot.angle + math.pi / 2.0)

            if inp.right:
                move_x += strafe_x
                move_y += strafe_y

            if inp.left:
                move_x -= strafe_x
                move_y -= strafe_y

            magnitude = math.sqrt(move_x * move_x + move_y * move_y)
            
            if magnitude > 0.0:
                move_x = (move_x / magnitude) * vel.speed * delta_time
                move_y = (move_y / magnitude) * vel.speed * delta_time

                if not _is_wall(pos.x + move_x, pos.y, walls_arr, MAX_MAP_WIDTH, MAX_MAP_HEIGHT, PLAYER_RADIUS):
                    pos.x += move_x
                
                if not _is_wall(pos.x, pos.y + move_y, walls_arr, MAX_MAP_WIDTH, MAX_MAP_HEIGHT, PLAYER_RADIUS):
                    pos.y += move_y

class SpriteSystem:
    @staticmethod
    def update(world: World, cam_x: float, cam_y: float):
        sprite_entities = world.get_components(Position, Rotation, Sprite)
        
        sprites_with_dist = []
        for entity_id, (pos, rot, sprite_comp) in sprite_entities:
            dist_sq = (pos.x - cam_x)**2 + (pos.y - cam_y)**2
            sprites_with_dist.append((dist_sq, pos, rot, sprite_comp))
        
        sprites_with_dist.sort(key=lambda s: s[0], reverse=True)
        return sprites_with_dist

class AnimatorSystem:
    @staticmethod
    def update(world: World, delta_time: float, map_manager):
        from .components import SpriteAnimator, Sprite, TextureAnimator, Position
        from .definitions import PlaybackState, PlaybackMode
        
        # SpriteAnimator
        for entity_id, (pos, animator, sprite) in world.get_components(Position, SpriteAnimator, Sprite):
            if animator.playback_state != PlaybackState.PLAYING:
                continue

            animation = animator.animations.get(animator.current_animation)
            if animation:
                sprite.atlas_index_front = animation.frames_front[animator.current_frame]
                sprite.atlas_index_back = animation.frames_back[animator.current_frame]

                animator.timer += delta_time
                if animator.timer >= animation.frame_duration:
                    animator.timer -= animation.frame_duration
                    next_frame = animator.current_frame + 1

                    if next_frame >= len(animation.frames_front):
                        if animation.playback_mode != PlaybackMode.LOOP:
                            animator.playback_state = PlaybackState.STOPPED
                            animator.current_frame = len(animation.frames_front) - 1
                        else:
                            animator.current_frame = 0
                    else:
                        animator.current_frame = next_frame

        # TextureAnimator
        for entity_id, (pos, animator) in world.get_components(Position, TextureAnimator):
            if animator.playback_state != PlaybackState.PLAYING:
                continue
            
            animation = animator.animations.get(animator.current_animation)
            if animation:
                map_manager.set_wall(int(pos.x), int(pos.y), animation.frames[animator.current_frame])

                animator.timer += delta_time
                if animator.timer >= animation.frame_duration:
                    animator.timer -= animation.frame_duration
                    next_frame = animator.current_frame + 1

                    if next_frame >= len(animation.frames):
                        if animation.playback_mode != PlaybackMode.LOOP:
                            animator.playback_state = PlaybackState.STOPPED
                            animator.current_frame = len(animation.frames) - 1
                        else:
                            animator.current_frame = 0
                    else:
                        animator.current_frame = next_frame

class InteractSystem:
    @staticmethod
    def update(world: World, input_state: InputState, player_entity, map_walls: list[int]):
        from .definitions import INTERACT_DISTANCE

        if not input_state.interact or player_entity is None:
            return
        input_state.interact = False

        pos = world.get_component(player_entity, Position)
        rot = world.get_component(player_entity, Rotation)
        if not pos or not rot:
            return

        player_x, player_y = pos.x, pos.y
        dir_x = math.cos(rot.angle)
        dir_y = math.sin(rot.angle)

        walls_arr = np.array(map_walls, dtype=np.int32)
        hit_mx, hit_my, hit_dist = _dda_raycast(
            player_x, player_y, dir_x, dir_y,
            walls_arr, MAX_MAP_WIDTH, MAX_MAP_HEIGHT, INTERACT_DISTANCE
        )

        entity_hit = None
        if hit_mx >= 0 and hit_my >= 0:
            entity_hit = InteractSystem.find_interactable_at_position(world, float(hit_mx), float(hit_my))

        if entity_hit is not None:
            interactible = world.get_component(entity_hit, Interactible)
            if interactible and interactible.enabled and interactible.on_interact:
                interactible.on_interact(world, player_entity, entity_hit)

    @staticmethod
    def find_interactable_at_position(world: World, x: float, y: float):
        for entity_id, (pos, interact) in world.get_components(Position, Interactible):
            if int(pos.x) == int(x) and int(pos.y) == int(y):
                return entity_id
        return None

class VentSystem:
    @staticmethod
    def update(world: World, delta_time: float):
        from .components import Vent, TextureAnimator
        from .definitions import PlaybackState, VentAnim
        
        for entity_id, (vent, texture_animator) in world.get_components(Vent, TextureAnimator):
            if vent.is_open:
                continue
            vent.timer += delta_time
            if vent.timer >= vent.time_to_open:
                vent.is_open = True
                vent.timer = 0.0
                texture_animator.current_animation = ("Vent", VentAnim.OPENING)
                texture_animator.playback_state = PlaybackState.PLAYING
                texture_animator.current_frame = 0
                texture_animator.timer = 0.0

class FPSSystem:
    @staticmethod
    def update(world: World, delta_time: float):
        from .components import FPSCounter, TextEntity
        
        for entity_id, (counter, text) in world.get_components(FPSCounter, TextEntity):
            counter.timer += delta_time
            counter.frame_count += 1
            if counter.timer >= counter.time_to_update:
                avg_fps = int(counter.frame_count / counter.timer)
                counter.timer = 0.0
                counter.frame_count = 0
                text.text = f"FPS: {avg_fps}"

# =============================================================================
# Numba warmup – kompilácia prebehne pri importe modulu, nie počas hrania
# =============================================================================
_warmup_walls = np.zeros(64, dtype=np.int32)
_is_wall(1.5, 1.5, _warmup_walls, 8, 8, 0.15)
_dda_raycast(1.5, 1.5, 1.0, 0.0, _warmup_walls, 8, 8, 2.0)
