import math
from .ecs import World
from .components import Position, Rotation, Velocity, PlayerController, Sprite, Interactible
from .input import InputState

TILE_SIZE = 64
MAX_MAP_WIDTH = 8
MAX_MAP_HEIGHT = 8
PLAYER_RADIUS = 0.15

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

                if not MovementSystem.is_wall(pos.x + move_x, pos.y, map_walls):
                    pos.x += move_x
                
                if not MovementSystem.is_wall(pos.x, pos.y + move_y, map_walls):
                    pos.y += move_y
                    
            # Vypísanie do konzoly
            # print(f"Player position: ({pos.x:.2f}, {pos.y:.2f}), angle: {math.degrees(rot.angle):.2f}°")

    @staticmethod
    def is_wall(check_x: float, check_y: float, map_walls: list[int]) -> bool:
        player_rad = PLAYER_RADIUS

        min_x = int(math.floor(check_x - player_rad))
        max_x = int(math.floor(check_x + player_rad))
        min_y = int(math.floor(check_y - player_rad))
        max_y = int(math.floor(check_y + player_rad))

        for map_x in range(min_x, max_x + 1):
            for map_y in range(min_y, max_y + 1):
                if map_x < 0 or map_x >= MAX_MAP_WIDTH or map_y < 0 or map_y >= MAX_MAP_HEIGHT:
                    return True
                
                map_index = map_y * MAX_MAP_WIDTH + map_x
                if map_index < len(map_walls) and map_walls[map_index] != 0:
                    return True
        return False

class SpriteSystem:
    @staticmethod
    def update(world: World, cam_x: float, cam_y: float):
        sprite_entities = world.get_components(Position, Sprite)
        
        sprites_with_dist = []
        for entity_id, (pos, sprite_comp) in sprite_entities:
            dist_sq = (pos.x - cam_x)**2 + (pos.y - cam_y)**2
            sprites_with_dist.append((dist_sq, pos, sprite_comp))
        
        sprites_with_dist.sort(key=lambda s: s[0], reverse=True)
        return sprites_with_dist
