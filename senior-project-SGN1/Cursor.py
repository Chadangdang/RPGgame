import pygame
from Constants import *
from Character import Character

class Cursor:
    state = 0
    selected_action = -1

    image1 = pygame.image.load('./resource/cursor/cursor1p20.png')
    image2 = pygame.image.load('./resource/cursor/cursor2p20.png')
    image3 = pygame.image.load('./resource/cursor/cursor-1sp20-p5.png')
    image4 = pygame.image.load('./resource/cursor/cursor-2sp20-p5.png')

    @staticmethod
    def gridBounding(grid: tuple[int, int], bound: tuple[int, int]) -> tuple[int, int]:
        row, col = grid

        if row < 0:
            row = 0
        elif row >= bound[0]:
            row = bound[0] - 1

        if col < 0:
            col = 0
        elif col >= bound[1]:
            col = bound[1] - 1

        return (row, col)

    def __init__(self, screen: pygame.Surface, size: tuple[int, int], bound: tuple[int, int], grid: tuple[int, int], show: bool) -> None:
        self.screen = screen
        self.size = size
        self._show = show
        self.image: pygame.Surface
        self.grid: tuple[int, int]
        self.bound = bound
        self.moveTo(grid)

    @property
    def show(self) -> bool:
        return getattr(self, '_show', False)

    @show.setter
    def show(self, val: bool) -> None:
        # If attempting to show, enforce that select cursor may only show when the
        # selected character (if any) belongs to the active player's team.
        try:
            if val:
                from Character import Character as _Character
                import game.state as _state
                main = getattr(_state, 'main', None)
                if main is not None:
                    gm = getattr(main, 'GameMaster', None)
                    active_own = getattr(getattr(gm, 'activeAI', None), 'own_team', None)
                    char = _Character.getCharacterByGrid(self.grid)
                    if char is not None and active_own is not None and char not in active_own:
                        # Block showing select cursor for non-active team's unit
                        self._show = False
                        return
            self._show = bool(val)
        except Exception:
            # On any error, fall back to basic behavior
            self._show = bool(val)

    def moveTo(self, grid: tuple[int, int]) -> None:
        self.grid = Cursor.gridBounding(grid, self.bound)
    
    def moveBy(self, key: int) -> None:
        mod = MOVEMENTS[key]
        self.grid = Cursor.gridBounding((self.grid[0] + mod[0], self.grid[1] + mod[1]), self.bound)

    def getChara(self) -> Character | None:
        if self.show:
            return Character.getCharacterByGrid(self.grid)
        else:
            return None

    def render(self, pos: tuple[float, float]) -> None:
        if self.show and Cursor.state != 6:
            self.screen.blit(pygame.transform.scale(self.image, self.size), pos)

class SelectCursor(Cursor):
    def __init__(self, screen: pygame.Surface, size: tuple[int, int], bound: tuple[int, int], grid: tuple[int, int] = (0, 0)) -> None:
        self.image = Cursor.image1
        super().__init__(screen, size, bound, grid, show=False)

class HoverCursor(Cursor):
    def __init__(self, screen: pygame.Surface, size: tuple[int, int], bound: tuple[int, int], grid: tuple[int, int] = (0, 0)) -> None:
        self.image = Cursor.image2
        super().__init__(screen, size, bound, grid, show=True)

class SelectMenuCursor(Cursor):
    def __init__(self, screen: pygame.Surface, size: tuple[int, int], bound: tuple[int, int], grid: tuple[int, int] = (0, 0)) -> None:
        self.image = Cursor.image3
        super().__init__(screen, size, bound, grid, show=False)

class HoverMenuCursor(Cursor):
    def __init__(self, screen: pygame.Surface, size: tuple[int, int], bound: tuple[int, int], grid: tuple[int, int] = (0, 0)) -> None:
        self.image = Cursor.image4
        super().__init__(screen, size, bound, grid, show=True)



