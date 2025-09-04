import pygame, sys

WIDTH = 1280
HEIGHT = 720

# Colors
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
RED = (255, 0, 0)
GREEN = (0, 255, 0)
BLUE = (0, 0, 255)
YELLOW = (255, 255, 0)
SMOKE = (236, 223, 204)
GRAY = (100, 100, 100)
LIGHTYELLOW = (255, 255, 180)
OBJECTIVE_COLOR = (255, 200, 100)

TEAM1_COLOR = (0, 0, 150)
TEAM2_COLOR = (150, 0, 0)

# Frame rate for the game
MAX_FRAME_RATE = 120

# Template related
TEMPLATE_PATH = 'templates.json'
MAP_PATH = 'maps.json'
ENEMY_NAMES = ['enemy1', 'enemy2', 'enemy3']

# Delays
ROUND_DELAY = 1
# ACTION_DELAY = 0.8

# Map
GRID_ROWS = 8
GRID_COLS = 8

# Auto
AUTO_MATCH_LIMIT = 10

# Keyboard
MOVEMENTS = {
    pygame.K_UP: (-1, 0),
    pygame.K_DOWN: (1, 0),
    pygame.K_LEFT: (0, -1),
    pygame.K_RIGHT: (0, 1)
}
