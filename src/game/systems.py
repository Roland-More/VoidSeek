import math
from .ecs import World
from .components import Position, Rotation, Velocity, PlayerController, InputState

TILE_SIZE = 64
MAX_MAP_WIDTH = 8
MAX_MAP_HEIGHT = 8
PLAYER_RADIUS = 10.0

class PlayerInputSystem:
    @staticmethod
    def update(world: World):
        for entity_id, (rot, vel, ctrl, inp) in world.get_components(Rotation, Velocity, PlayerController, InputState):
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
    def update(world: World, delta_time: float, map_walls: list[int]):
        for entity_id, (pos, rot, vel, inp) in world.get_components(Position, Rotation, Velocity, InputState):
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
        inverted_size = 1.0 / float(TILE_SIZE)
        player_rad = PLAYER_RADIUS * inverted_size

        x_scaled = check_x * inverted_size
        y_scaled = check_y * inverted_size

        min_x = int(math.floor(x_scaled - player_rad))
        max_x = int(math.floor(x_scaled + player_rad))
        min_y = int(math.floor(y_scaled - player_rad))
        max_y = int(math.floor(y_scaled + player_rad))

        for map_x in range(min_x, max_x + 1):
            for map_y in range(min_y, max_y + 1):
                if map_x < 0 or map_x >= MAX_MAP_WIDTH or map_y < 0 or map_y >= MAX_MAP_HEIGHT:
                    return True
                
                map_index = map_y * MAX_MAP_WIDTH + map_x
                if map_index < len(map_walls) and map_walls[map_index] != 0:
                    return True
        return False
