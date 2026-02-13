import pygame
import random
import numpy as np
from Constants import *
from Box import Box
from Cursor import *
from Map import Map
from Character import Character
from string import ascii_lowercase as alc

class Field:
    def __init__(self, screen: pygame.Surface, coords: tuple[float, float], grid: tuple[int, int], size: tuple[int, int], rand_map: bool, map_id: int = 0):
        self.screen = screen
        self.rows, self.cols = grid
        self.rect = pygame.Rect(coords, size)

        self.map = Map(grid)
        self.generateTerrain(rand_map, map_id)
        
        self.team1_spawns: list[tuple[int, int]] = [(i, j) for i in range(self.rows) for j in range(self.cols) if self.map.terrain[i][j] == 4]
        self.team2_spawns: list[tuple[int, int]] = [(i, j) for i in range(self.rows) for j in range(self.cols) if self.map.terrain[i][j] == 5]
        # print(self.player_spawns)

        self.boxes_width = int(size[0] / grid[1])
        self.boxes_height = int(size[1] / grid[0])
        self.boxes: list[list[Box]] = [[Box(self.screen, 
                                        (coords[0] + (j * self.boxes_width), coords[1] + (i * self.boxes_height)),
                                        (self.boxes_width, self.boxes_height),
                                        self.map.terrain[i][j])
                                        for j in range(grid[1])] 
                                        for i in range(grid[0])]

        self.hover_cursor = HoverCursor(self.screen, (self.boxes_width, self.boxes_height), (GRID_ROWS, GRID_COLS))
        self.select_cursor = SelectCursor(self.screen, (self.boxes_width, self.boxes_height), (GRID_ROWS, GRID_COLS))

        self.starting_area_row = 0
        self.starting_area_col = 0
        # self.starting_area = [[None, None, None],
        #                       [None, None, None],
        #                       [None, None, None]]
        # self.enemy_starting_area_row = 0
        # self.enemy_starting_area_col = 0
        # self.enemy_starting_area = [[None, None, None],
        #                             [None, None, None],
        #                             [None, None, None]]

        self.font_ss = pygame.font.Font('resource/font.ttf', 18)

    # Get the first team1 np.character's position
    def positionCursorOnTeam1Character(self) -> None:
        if Character.team1_list:
            first_character = Character.team1_list[0]
            self.hover_cursor.moveTo(first_character.grid)

    def generateTerrain(self, rand_map, map_id) -> None:
        if rand_map:
            self.map.generateTerrain(randomMap=True)  # Generate map terrain
        else:
            self.map.generateTerrain(randomMap=False, mapID=map_id)
        
    def getTerrain(self) -> list[list[int]]:
        return self.map.terrain

    def clearSpawns(self) -> None:
        for pos in self.team1_spawns:
            self.boxes[pos[0]][pos[1]].terrain = 0

    def getCoordsAtGrid(self, grid: tuple[int, int]) -> tuple[float, float]:
        box = self.boxes[grid[0]][grid[1]]
        return (box.rect.x, box.rect.y)
    
    def getHoveredBoxInfo(self) -> Box:
        box = self.boxes[self.hover_cursor.grid[0]][self.hover_cursor.grid[1]]
        # return (box.terrain_name, box.terrain_desc)
        return box


    # def selecting_start_area(self, method='random'):
    #     if method == 'corner':
    #         pass
    #     elif method == 'center':
    #         pass
    #     else:
    #         self.starting_area_row = random.randint(0, self.rows - 3)
    #         self.starting_area_col = random.randint(0, self.cols - 3)
    #         for i in range(0, 3):
    #             for j in range(0, 3):
    #                 self.starting_area[i][j] = self.get_box(self.starting_area_col+j, self.starting_area_row+i)
    #         self.enemy_starting_area_row = random.randint(0, self.rows - 3)
    #         self.enemy_starting_area_col = random.randint(0, self.cols - 3)
    #         while self.starting_area_row - 2 <= self.enemy_starting_area_row <= self.starting_area_row + 2 and self.starting_area_col - 2 <= self.enemy_starting_area_col <= self.starting_area_col + 2:
    #             self.enemy_starting_area_row = random.randint(0, self.rows - 3)
    #             self.enemy_starting_area_col = random.randint(0, self.cols - 3)
    #         for i in range(0, 3):
    #             for j in range(0, 3):
    #                 self.enemy_starting_area[i][j] = self.get_box(self.enemy_starting_area_col + j, self.enemy_starting_area_row + i)

    def getMovement(self, chara: Character, show: bool = True) -> np.ndarray: 
        movementMap = np.zeros((GRID_ROWS, GRID_COLS))
        movement_value = getattr(chara, 'movement', chara.template.get('movement', 0))
        for route_number in range(4 ** movement_value):
            # route = '{0:x}'.format(route).zfill(movement_value)
            route = ''
            if route_number == 0:
                route = '0'.zfill(movement_value)
            while route_number:
                route = route + str(route_number % 4)
                route_number //= 4
            cur_row, cur_col = chara.grid
            if route.find('10') >= 0 or route.find('01') >= 0 or route.find('23') >= 0 or route.find('32') >= 0:
                continue
            for direction in route:
                if direction == '0':
                    cur_row += 1
                elif direction == '1':
                    cur_row -= 1
                elif direction == '2':
                    cur_col += 1
                elif direction == '3':
                    cur_col -= 1

                if 0 <= cur_row < self.rows and 0 <= cur_col < self.cols:
                    if self.boxes[cur_row][cur_col].terrain == 2 or (cur_row, cur_col) in [unit.grid for unit in Character.team2_list]:
                        break
                    if (cur_row, cur_col) not in [unit.grid for unit in Character.team1_list]:
                        # if show:
                        #     self.field.boxes[cur_row][cur_col].selected = True
                        movementMap[cur_row][cur_col] = 1
                else:
                    break
        if show:
            movementTiles = np.argwhere(movementMap > 0)
            self.boxes[chara.grid[0]][chara.grid[1]].selected = True
            for tile in movementTiles:
                self.boxes[tile[0]][tile[1]].selected = True
            # for i in range(len(movementMap)):
            #     for j in range(len(movementMap[i])):
            #         if movementMap[i][j]:
            #             self.field.boxes[i][j].selected = True
        return movementMap  # Used for AI
    
    def getActionArea(self, chara: Character, actionNo: int, show=True, coords=None) -> np.ndarray:
        if coords is None:
            row, col = chara.grid
        else:
            row, col = coords
        actionMap = np.zeros((GRID_ROWS, GRID_COLS))
        action = chara.template["actions"][actionNo]
        action_range = action.get("range", 0)
        action_target = action.get("target", "")
        action_damage = action.get("damage", 0)
        match action_target:
            case "Line":
                for i in range(max(0, row - action_range), min(GRID_ROWS, row + action_range + 1)):
                    actionMap[i][col] = action_damage
                    # self.field.boxes[i][col].selected_red = show
                for j in range(max(0, col - action_range), min(GRID_COLS, col + action_range + 1)):
                    actionMap[row][j] = action_damage
                    # self.field.boxes[row][j].selected_red = show
            case "Cross":
                actionMap[row][col] = action_damage
                # self.field.boxes[row][col].selected_red = show                
                # The reason I make 4 separate for loops is for checking is there is an obstacle in between
                # (may break out of loop or something better) (May use this method for line selection too)
                # please don't delete yet
                for i in range(action_range + 1):
                    if 0 <= row + i < GRID_ROWS and 0 <= col + i < GRID_COLS:
                        actionMap[row + i][col + i] = action_damage
                        # self.field.boxes[row + i][col + i].selected_red = show
                for i in range(action_range + 1):
                    if 0 <= row + i < GRID_ROWS and 0 <= col - i < GRID_COLS:
                        actionMap[row + i][col - i] = action_damage
                        # self.field.boxes[row + i][col - i].selected_red = show
                for i in range(action_range + 1):
                    if 0 <= row - i < GRID_ROWS and 0 <= col + i < GRID_COLS:
                        actionMap[row - i][col + i] = action_damage
                        # self.field.boxes[row - i][col + i].selected_red = show
                for i in range(action_range + 1):
                    if 0 <= row - i < GRID_ROWS and 0 <= col - i < GRID_COLS:
                        actionMap[row - i][col - i] = action_damage
                        # self.field.boxes[row - i][col - i].selected_red = show
            case "Asterisk":
                for i in range(max(0, row - action_range), min(GRID_ROWS, row + action_range + 1)):
                    actionMap[i][col] = action_damage
                    # self.field.boxes[i][col].selected_red = show
                for j in range(max(0, col - action_range), min(GRID_COLS, col + action_range + 1)):
                    actionMap[row][j] = action_damage
                    # self.field.boxes[row][j].selected_red = show

                for i in range(action_range + 1):
                    if 0 <= row + i < GRID_ROWS and 0 <= col + i < GRID_COLS:
                        actionMap[row + i][col + i] = action_damage
                        # self.field.boxes[row + i][col + i].selected_red = show
                for i in range(action_range + 1):
                    if 0 <= row + i < GRID_ROWS and 0 <= col - i < GRID_COLS:
                        actionMap[row + i][col - i] = action_damage
                        # self.field.boxes[row + i][col - i].selected_red = show
                for i in range(action_range + 1):
                    if 0 <= row - i < GRID_ROWS and 0 <= col + i < GRID_COLS:
                        actionMap[row - i][col + i] = action_damage
                        # self.field.boxes[row - i][col + i].selected_red = show
                for i in range(action_range + 1):
                    if 0 <= row - i < GRID_ROWS and 0 <= col - i < GRID_COLS:
                        actionMap[row - i][col - i] = action_damage
                        # self.field.boxes[row - i][col - i].selected_red = show
            case "Box":
                for i in range(max(0, row - action_range), min(GRID_ROWS, row + action_range + 1)):
                    for j in range(max(0, col - action_range),
                                   min(GRID_COLS, col + action_range + 1)):
                        actionMap[i][j] = action_damage
                        # self.field.boxes[i][j].selected_red = show
        if show:
            actionTiles = np.argwhere(actionMap > 0)
            for tile in actionTiles:
                self.boxes[tile[0]][tile[1]].selected_red = True
        return actionMap
    
    def clearMovement(self) -> None:
        for i in range(GRID_ROWS):
            for j in range(GRID_COLS):
                self.boxes[i][j].selected = False
                self.boxes[i][j].selected_red = False
        self.select_cursor.show = False

    def update(self, dt: float, events: list[pygame.event.Event], cursor_state: int) -> int:
        new_cursor_state = cursor_state
        events = [event for event in events if event.type == pygame.KEYDOWN]
        for event in events:
            match event.key:
                case pygame.K_z:
                    break
                case pygame.K_x:
                    break
                case pygame.K_p:
                    break
                case pygame.K_UP | pygame.K_DOWN | pygame.K_LEFT | pygame.K_RIGHT:
                    if cursor_state != 2:
                        self.hover_cursor.moveBy(event.key)
        
        return new_cursor_state

    def render(self) -> None:
        # render the white background
        pygame.draw.rect(self.screen, (255, 255, 255), self.rect)
        # render the map itself
        for i in range(self.rows):
            for j in range(self.cols):
                self.boxes[i][j].render()

        # render the grid
        for i in range(self.rows + 1):
            pygame.draw.line(self.screen, BLACK,
                             (self.rect.x, self.rect.y + (i * self.boxes_width)),
                             (self.rect.x + self.rect.width, self.rect.y + (i * self.boxes_width)), 1)
        for i in range(self.cols + 1):
            pygame.draw.line(self.screen, BLACK,
                             (self.rect.x + (i * self.boxes_height), self.rect.y),
                             (self.rect.x + (i * self.boxes_height), self.rect.y + self.rect.height), 1)

        for i in range(self.rows):
            x = self.rect.x - 9
            y = self.rect.y + self.boxes_height/2 + (i * self.boxes_height)
            text = self.font_ss.render(f'{8 - i}', False, (0, 0, 0))
            text_rect = text.get_rect(center=(x, y))
            self.screen.blit(text, text_rect)
        for i in range(self.cols):
            x = self.rect.x + self.boxes_width/2 + (i * self.boxes_width)
            y = self.rect.y - 9
            text = self.font_ss.render(f'{alc[i]}', False, (0, 0, 0))
            text_rect = text.get_rect(center=(x, y))
            self.screen.blit(text, text_rect)

                # character renders (with proper highlights)
        for character in Character.team1_list:
            # Draw the character sprite
            character.render(self.getCoordsAtGrid(character.grid))

            # Position rectangle around the bot
            gx, gy = character.grid
            x, y = self.getCoordsAtGrid((gx, gy))
            rect = pygame.Rect(x, y, self.boxes_width, self.boxes_height)

            # Blue team highlights
            if character.moved and not character.acted:
                pygame.draw.rect(self.screen, (90, 170, 255), rect, 3)   # light blue = moved
            elif character.acted:
                pygame.draw.rect(self.screen, (30, 110, 220), rect, 3)   # dark blue = acted
            else:
                pygame.draw.rect(self.screen, (0, 100, 255), rect, 2)    # idle blue outline

        for character in Character.team2_list:
            # Draw the character sprite
            character.render(self.getCoordsAtGrid(character.grid))

            # Position rectangle around the bot
            gx, gy = character.grid
            x, y = self.getCoordsAtGrid((gx, gy))
            rect = pygame.Rect(x, y, self.boxes_width, self.boxes_height)

            # Red team highlights
            if character.moved and not character.acted:
                pygame.draw.rect(self.screen, (255, 160, 160), rect, 3)  # light red = moved
            elif character.acted:
                pygame.draw.rect(self.screen, (200, 40, 40), rect, 3)    # dark red = acted
            else:
                pygame.draw.rect(self.screen, (255, 0, 0), rect, 2)      # idle red outline



        # Cursors
        self.hover_cursor.render(self.getCoordsAtGrid((self.hover_cursor.grid)))
        self.select_cursor.render(self.getCoordsAtGrid(self.select_cursor.grid))
