import json
import random

WIDTH = 95
HEIGHT = 95

def generate_maze():
    # Initialize grid with walls
    grid = [['1' for _ in range(WIDTH)] for _ in range(HEIGHT)]
    
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
            if 0 < nx < WIDTH - 1 and 0 < ny < HEIGHT - 1:
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

def create_loops(grid):
    # Find dead ends and break through walls
    dead_ends = []
    for y in range(1, HEIGHT - 1):
        for x in range(1, WIDTH - 1):
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
                if 0 < nnx < WIDTH - 1 and 0 < nny < HEIGHT - 1:
                    if grid[ny][nx] == '1' and grid[nny][nnx] == '.':
                        grid[ny][nx] = '.'
                        break
                        
    # Add some random random wall breaks to create more loops
    for _ in range(200):
        x = random.randint(2, WIDTH - 3)
        y = random.randint(2, HEIGHT - 3)
        if grid[y][x] == '1':
            # Check if breaking it connects two paths horizontally or vertically
            if grid[y-1][x] == '.' and grid[y+1][x] == '.' and grid[y][x-1] == '1' and grid[y][x+1] == '1':
                grid[y][x] = '.'
            elif grid[y][x-1] == '.' and grid[y][x+1] == '.' and grid[y-1][x] == '1' and grid[y+1][x] == '1':
                grid[y][x] = '.'

def create_rooms(grid):
    for _ in range(15):
        w = random.choice([3, 5, 7])
        h = random.choice([3, 5, 7])
        x = random.randint(2, WIDTH - w - 2)
        y = random.randint(2, HEIGHT - h - 2)
        
        # Carve room
        for dy in range(h):
            for dx in range(w):
                grid[y + dy][x + dx] = '.'

def place_vents(grid):
    candidates = []
    for y in range(2, HEIGHT - 2):
        for x in range(2, WIDTH - 2):
            if grid[y][x] == '1':
                # Vertical vent
                if grid[y-1][x] == '.' and grid[y+1][x] == '.' and grid[y][x-1] == '1' and grid[y][x+1] == '1':
                    candidates.append((x, y))
                # Horizontal vent
                elif grid[y][x-1] == '.' and grid[y][x+1] == '.' and grid[y-1][x] == '1' and grid[y+1][x] == '1':
                    candidates.append((x, y))
                    
    random.shuffle(candidates)
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
            if vents_placed >= 20:
                break

def place_entities(grid):
    empty_cells = []
    for y in range(1, HEIGHT - 1):
        for x in range(1, WIDTH - 1):
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
    
    # Take the top N furthest points, then shuffle them so they are not perfectly deterministically the absolute furthest
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

def generate_full_map():
    grid = generate_maze()
    create_loops(grid)
    create_rooms(grid)
    place_vents(grid)
    place_entities(grid)
    
    # Pad to 96x96
    for row in grid:
        row.append('1')
    grid.append(['1' for _ in range(WIDTH + 1)])
    
    return [''.join(row) for row in grid]

if __name__ == "__main__":
    maps = []
    for i in range(5):
        print(f"Generating map {i+1}/5...")
        maps.append(generate_full_map())
        
    with open("maps.json", "w") as f:
        json.dump(maps, f)
        
    print("Successfully generated professional maze maps.json!")
