import json
import random


def generate_maze(width, height):
    # Initialize grid with walls
    grid = [['1' for _ in range(width)] for _ in range(height)]
    
    # Directions for maze carving (distance 2)
    dirs = [(0, -2), (0, 2), (-2, 0), (2, 0)]
    
    # Start at 1, 1
    stack = [(1, 1)]
    grid[1][1] = '.'
    
    while stack:
        # Randomized DFS
        current = stack[-1]
        x, y = current
        
        # Find valid unvisited neighbors
        unvisited = []
        for dx, dy in dirs:
            nx, ny = x + dx, y + dy
            if 0 < nx < width - 1 and 0 < ny < height - 1:
                if grid[ny][nx] == '1':
                    unvisited.append((nx, ny, dx, dy))
                    
        if unvisited:
            nx, ny, dx, dy = random.choice(unvisited)
            # Carve path and the wall between
            grid[ny][nx] = '.'
            grid[y + dy // 2][x + dx // 2] = '.'
            stack.append((nx, ny))
        else:
            stack.pop()

    return grid

def create_loops(grid, width, height):
    # Find dead ends and break through walls
    dead_ends = []
    for y in range(1, height - 1):
        for x in range(1, width - 1):
            if grid[y][x] == '.':
                walls = 0
                if grid[y-1][x] == '1': walls += 1
                if grid[y+1][x] == '1': walls += 1
                if grid[y][x-1] == '1': walls += 1
                if grid[y][x+1] == '1': walls += 1
                if walls == 3:
                    dead_ends.append((x, y))
                    
    # For dead ends, try to connect them to other paths
    for x, y in dead_ends:
        if random.random() < 0.8: # 80% chance to break a dead end
            neighbors = [(x, y-1, x, y-2), (x, y+1, x, y+2), (x-1, y, x-2, y), (x+1, y, x+2, y)]
            random.shuffle(neighbors)
            for nx, ny, nnx, nny in neighbors:
                if 0 < nnx < width - 1 and 0 < nny < height - 1:
                    if grid[ny][nx] == '1' and grid[nny][nnx] == '.':
                        grid[ny][nx] = '.'
                        break
                        
    # Add some random wall breaks to create more loops — scale count with map area
    loop_breaks = int(200 * (width * height) / (95 * 95))
    for _ in range(loop_breaks):
        x = random.randint(2, width - 3)
        y = random.randint(2, height - 3)
        if grid[y][x] == '1':
            # Check if breaking it connects two paths horizontally or vertically
            if grid[y-1][x] == '.' and grid[y+1][x] == '.' and grid[y][x-1] == '1' and grid[y][x+1] == '1':
                grid[y][x] = '.'
            elif grid[y][x-1] == '.' and grid[y][x+1] == '.' and grid[y-1][x] == '1' and grid[y+1][x] == '1':
                grid[y][x] = '.'

def create_rooms(grid, width, height):
    # Scale room count with area
    num_rooms = int(15 * (width * height) / (95 * 95))
    num_rooms = max(5, num_rooms)
    for _ in range(num_rooms):
        w = random.choice([3, 5, 7])
        h = random.choice([3, 5, 7])
        x = random.randint(2, width - w - 2)
        y = random.randint(2, height - h - 2)
        
        # Carve room
        for dy in range(h):
            for dx in range(w):
                grid[y + dy][x + dx] = '.'

def place_vents(grid, width, height):
    candidates = []
    for y in range(2, height - 2):
        for x in range(2, width - 2):
            if grid[y][x] == '1':
                # Vertical vent
                if grid[y-1][x] == '.' and grid[y+1][x] == '.' and grid[y][x-1] == '1' and grid[y][x+1] == '1':
                    candidates.append((x, y))
                # Horizontal vent
                elif grid[y][x-1] == '.' and grid[y][x+1] == '.' and grid[y-1][x] == '1' and grid[y+1][x] == '1':
                    candidates.append((x, y))
                    
    random.shuffle(candidates)
    # Scale vent count with area
    max_vents = int(20 * (width * height) / (95 * 95))
    max_vents = max(8, max_vents)
    vents_placed = 0
    for x, y in candidates:
        # Make sure no other vent is too close
        too_close = False
        for dy in range(-2, 3):
            for dx in range(-2, 3):
                if grid[y+dy][x+dx] == 'V':
                    too_close = True
        if not too_close:
            grid[y][x] = 'V'
            vents_placed += 1
            if vents_placed >= max_vents:
                break

def place_entities(grid, width, height):
    empty_cells = []
    for y in range(1, height - 1):
        for x in range(1, width - 1):
            if grid[y][x] == '.':
                empty_cells.append((x, y))
                
    random.shuffle(empty_cells)
    
    # Place Seekers
    seeker_cells = empty_cells[:3]
    for x, y in seeker_cells:
        grid[y][x] = 'S'
    empty_cells = empty_cells[3:]
    
    # Sort remaining cells by distance to nearest seeker
    def dist_to_seekers(cell):
        return min((cell[0]-sx)**2 + (cell[1]-sy)**2 for sx, sy in seeker_cells)
        
    empty_cells.sort(key=dist_to_seekers, reverse=True)
    
    # Take the top N furthest points, then shuffle them
    furthest_candidates = empty_cells[:100]
    random.shuffle(furthest_candidates)
    
    # Place Runners
    runner_cells = furthest_candidates[:10]
    for x, y in runner_cells:
        grid[y][x] = 'R'
        empty_cells.remove((x, y))
        
    random.shuffle(empty_cells)
    
    # Place Keys
    for _ in range(10):
        x, y = empty_cells.pop()
        grid[y][x] = 'K'
        
    # Place Portals
    for _ in range(10):
        x, y = empty_cells.pop()
        grid[y][x] = 'P'

def generate_full_map(target_size):
    """Generate a map of the given target_size (64 or 96).
    
    Maze generation requires odd dimensions, so we generate at (target_size - 1)
    and pad by 1 row/column of walls to reach the target_size.
    """
    # Maze needs odd dimensions
    maze_w = target_size - 1  # e.g. 63 or 95
    maze_h = target_size - 1

    # Make sure maze dimensions are odd
    if maze_w % 2 == 0:
        maze_w -= 1
    if maze_h % 2 == 0:
        maze_h -= 1

    grid = generate_maze(maze_w, maze_h)
    create_loops(grid, maze_w, maze_h)
    create_rooms(grid, maze_w, maze_h)
    place_vents(grid, maze_w, maze_h)
    place_entities(grid, maze_w, maze_h)
    
    # Pad to target_size x target_size
    pad_cols = target_size - maze_w
    pad_rows = target_size - maze_h

    for row in grid:
        for _ in range(pad_cols):
            row.append('1')
    for _ in range(pad_rows):
        grid.append(['1' for _ in range(target_size)])
    
    return [''.join(row) for row in grid]

if __name__ == "__main__":
    maps_32 = []
    for i in range(5):
        print(f"Generating 32x32 map {i+1}/5...")
        maps_32.append(generate_full_map(32))
        
    with open("maps_32.json", "w") as f:
        json.dump(maps_32, f)
    print("Successfully generated maps_32.json!")

    # Generate 5 maps of 64x64
    maps_64 = []
    for i in range(5):
        print(f"Generating 64x64 map {i+1}/5...")
        maps_64.append(generate_full_map(64))
        
    with open("maps_64.json", "w") as f:
        json.dump(maps_64, f)
    print("Successfully generated maps_64.json!")

    # Generate 5 maps of 96x96
    maps_96 = []
    for i in range(5):
        print(f"Generating 96x96 map {i+1}/5...")
        maps_96.append(generate_full_map(96))
        
    with open("maps_96.json", "w") as f:
        json.dump(maps_96, f)
    print("Successfully generated maps_96.json!")
