import pygame
from Constants import *


class Box:
    def __init__(self, screen: pygame.Surface, coords: tuple[float, float], size: tuple[int, int], terrain: int) -> None:
        self.screen = screen
        self.rect = pygame.Rect(coords, size)
        self.selected = False
        self.selected_red = False
        self.terrain = terrain 
        self.terrain_name = ""
        self.terrain_desc = ""
        self.color = WHITE
        self.img = None

    def render(self) -> None:
        match self.terrain:
            case 0:  # Nothing
                self.color = WHITE
                self.terrain_name = ""
                self.terrain_desc = ""
            case 1:  # Tree
                self.color = GREEN
                self.img = "./resource/terrain/tree.png"
                self.terrain_name = "Tree"
                self.terrain_desc = "-2 Damage Taken"
            case 2:  # Rock
                self.color = GRAY
                self.img = "./resource/terrain/rock.png"
                self.terrain_name = "Rock"
                self.terrain_desc = "Impassable"
            case 3:  # Objective
                self.color = OBJECTIVE_COLOR
                self.terrain_name = "Objective"
                self.terrain_desc = "Control to win"
            case 4:  # Player Spawn
                self.color = BLUE
                self.terrain_name = "Player Spawn"
                self.terrain_desc = "Position your units"
            case 5:  # Enemy Spawn
                self.color = RED
                self.terrain_name = "Enemy Spawn"
                self.terrain_desc = "Position enemy units"

        pygame.draw.rect(self.screen, self.color, self.rect)

        if self.img is not None:
            self.image = pygame.transform.scale(pygame.image.load(self.img), (self.rect.width, self.rect.height))
            self.screen.blit(self.image, (self.rect.x, self.rect.y))


        if self.selected:
            pygame.draw.rect(self.screen, YELLOW, self.rect, 4)
        if self.selected_red:
            pygame.draw.rect(self.screen, RED, self.rect, 4)
            #kuy