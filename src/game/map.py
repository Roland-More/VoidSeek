import numpy as np
from core.backend.definitions import MAX_MAP_WIDTH, MAX_MAP_HEIGHT
from .definitions import *

class MapManager:
    def __init__(self):
        self.width = MAX_MAP_WIDTH
        self.height = MAX_MAP_HEIGHT
        
        # Numpy arrays namiesto Python listov – eliminuje per-frame np.array() konverziu
        self.walls = np.zeros(self.width * self.height, dtype=np.int32)
        self.floors = np.zeros(self.width * self.height, dtype=np.int32)
        self.ceilings = np.zeros(self.width * self.height, dtype=np.int32)
        
        self.dirty_tiles = []
        self.map_changed_flag = False
        
    def load_from_layout(self, layout: list[str], game_state=None):
        vents_to_place = []

        for y, row in enumerate(layout):
            if y >= self.height: break
            for x, char in enumerate(row):
                if x >= self.width: break
                
                index = y * self.width + x
                
                self.floors[index] = 2
                self.ceilings[index] = 3
                self.walls[index] = 0
                
                if char == '1':
                    self.walls[index] = 1
                elif char == 'V':
                    vents_to_place.append((x, y))
                    
        for x, y in vents_to_place:
            valid, orientation = self.check_vent_placement(x, y)
            index = y * self.width + x
            if valid:
                self.walls[index] = 13
                if game_state:
                    game_state.create_vent(x, y, True, orientation)
            else:
                self.walls[index] = 1

        self.dirty_tiles.clear()
        self.mark_all_dirty()

    def check_vent_placement(self, x: int, y: int) -> tuple[bool, VentOrientation]:
        top = int(self.walls[(y - 1) * self.width + x]) if y > 0 else 1
        bottom = int(self.walls[(y + 1) * self.width + x]) if y < self.height - 1 else 1
        left = int(self.walls[y * self.width + (x - 1)]) if x > 0 else 1
        right = int(self.walls[y * self.width + (x + 1)]) if x < self.width - 1 else 1

        orientation = VentOrientation.NONE
        valid_placement = False

        if top == 0 and bottom == 0 and left != 0 and right != 0:
            orientation = VentOrientation.VERTICAL
            valid_placement = True
        elif left == 0 and right == 0 and top != 0 and bottom != 0:
            orientation = VentOrientation.HORIZONTAL
            valid_placement = True

        return valid_placement, orientation
                    
    def set_wall(self, x: int, y: int, tex_id: int):
        if 0 <= x < self.width and 0 <= y < self.height:
            index = y * self.width + x
            self.walls[index] = tex_id
            self.dirty_tiles.append((index, x, y, int(self.walls[index]), int(self.floors[index]), int(self.ceilings[index])))

    def set_floor(self, x: int, y: int, tex_id: int):
        if 0 <= x < self.width and 0 <= y < self.height:
            index = y * self.width + x
            self.floors[index] = tex_id
            self.dirty_tiles.append((index, x, y, int(self.walls[index]), int(self.floors[index]), int(self.ceilings[index])))

    def set_ceiling(self, x: int, y: int, tex_id: int):
        if 0 <= x < self.width and 0 <= y < self.height:
            index = y * self.width + x
            self.ceilings[index] = tex_id
            self.dirty_tiles.append((index, x, y, int(self.walls[index]), int(self.floors[index]), int(self.ceilings[index])))
            
    def mark_all_dirty(self):
        self.map_changed_flag = True

    def get_map_data(self) -> list[int]:
        map_data = []
        for i in range(self.width * self.height):
            map_data.append(int(self.walls[i]))
            map_data.append(int(self.floors[i]))
            map_data.append(int(self.ceilings[i]))
            map_data.append(0)
        return map_data
