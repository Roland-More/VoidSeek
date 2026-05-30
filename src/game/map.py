from core.backend.definitions import MAX_MAP_WIDTH, MAX_MAP_HEIGHT
from .definitions import *

class MapManager:
    def __init__(self):
        self.width = MAX_MAP_WIDTH
        self.height = MAX_MAP_HEIGHT
        
        self.walls = [0] * (self.width * self.height)
        self.floors = [0] * (self.width * self.height)
        self.ceilings = [0] * (self.width * self.height)
        
        self.dirty_tiles = []
        
    def load_from_layout(self, layout: list[str], game_state):
        vents_to_place = []

        for y, row in enumerate(layout):
            if y >= self.height: break
            for x, char in enumerate(row):
                if x >= self.width: break
                
                index = y * self.width + x
                
                # Základné podlahy a stropy
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
                self.walls[index] = 4
                game_state.create_vent(x, y, True, orientation)
            else:
                self.walls[index] = 1

        self.dirty_tiles.clear()
        self.mark_all_dirty()

    def check_vent_placement(self, x: int, y: int) -> tuple[bool, VentOrientation]:
        top = self.walls[(y - 1) * self.width + x] if y > 0 else 1
        bottom = self.walls[(y + 1) * self.width + x] if y < self.height - 1 else 1
        left = self.walls[y * self.width + (x - 1)] if x > 0 else 1
        right = self.walls[y * self.width + (x + 1)] if x < self.width - 1 else 1

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
            self.dirty_tiles.append((index, x, y, self.walls[index], self.floors[index], self.ceilings[index]))

    def set_floor(self, x: int, y: int, tex_id: int):
        if 0 <= x < self.width and 0 <= y < self.height:
            index = y * self.width + x
            self.floors[index] = tex_id
            self.dirty_tiles.append((index, x, y, self.walls[index], self.floors[index], self.ceilings[index]))

    def set_ceiling(self, x: int, y: int, tex_id: int):
        if 0 <= x < self.width and 0 <= y < self.height:
            index = y * self.width + x
            self.ceilings[index] = tex_id
            self.dirty_tiles.append((index, x, y, self.walls[index], self.floors[index], self.ceilings[index]))
            
    def mark_all_dirty(self):
        """Označí celú mapu za zmenenú, pre prvý načítavací krok."""
        pass

    def get_map_data(self) -> list[int]:
        """Vráti 1D pole celej mapy pre GPU (4 inty na tile: wall, floor, ceil, padding)"""
        map_data = []
        for i in range(self.width * self.height):
            map_data.append(self.walls[i])
            map_data.append(self.floors[i])
            map_data.append(self.ceilings[i])
            map_data.append(0) # padding
        return map_data
