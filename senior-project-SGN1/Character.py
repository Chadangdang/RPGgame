import pygame
from Constants import *
from Template import *

class Character:
    id = 0
    team1_list: list['Character'] = []
    team2_list: list['Character'] = []

    @staticmethod
    def getCharacterByID(id) -> 'Character | None':
        for chara in Character.team1_list + Character.team2_list:
            if chara.id == id:
                return chara
        return None
    
    @staticmethod
    def getCharacterByGrid(grid: tuple[int, int]) -> 'Character | None':
        for chara in Character.team1_list + Character.team2_list:
            if chara.grid == grid:
                return chara
        return None

    @staticmethod
    def removeCharacter(chara) -> None:
        if chara in Character.team1_list:
            Character.team1_list.remove(chara)
        elif chara in Character.team2_list:
            Character.team2_list.remove(chara)

    @staticmethod
    def removeAllCharacters() -> None:
        Character.id = 0
        Character.team1_list = []
        Character.team2_list = []

    def __init__(self, screen: pygame.Surface, size: tuple[int, int], grid: tuple[int, int], name: str, team: int) -> None:
        self.screen = screen
        self.grid = grid
        self.id = Character.id
        Character.id += 1
        self.template = Template(name).data
        self.moved = False
        self.acted = False
        self.alive = True

        if self.template and 'img' in self.template:
            # print(str(self.id) + "   " + self.template["img"])
            self.image = pygame.transform.scale(pygame.image.load(self.template["img"]), size)

        else:
            print(f"Failed to load template or image for character {name}")
            self.image = None
        Character.getCharacterByID(id)  # I forgot what this line is for so I'll keep it anyway
        # if self.type == "player":
        #     Character.team1_list.append(self)
        # elif self.type == "enemy":
        #     Character.team2_list.append(self)

        if team == 1:
            Character.team1_list.append(self)
        else:
            Character.team2_list.append(self)
        
    def moveTo(self, grid: tuple[int, int], update = True) -> None:
        self.grid = grid
        if update:
            self.moved = True

    def attack(self, target: 'Character', selected_action: int, modifier: int = 0) -> None:
        target.template['curHP'] -= max(0, self.template["actions"][selected_action]["damage"] + modifier)
        if target.template['curHP'] <= 0:
            target.alive = False
            Character.removeCharacter(target)
        self.acted = True

    def reset(self) -> None:
        self.moved = False
        self.acted = False


    def render(self, pos: tuple[float, float]) -> None:
        if self.image and self in Character.team1_list + Character.team2_list:
            self.screen.blit(self.image, pos)
