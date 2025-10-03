# Bandage until main.py is refactored
import random
import pygame
import sys
from Constants import *
from Field import Field
from Character import Character
from Cursor import *
import numpy as np    # we doing math now :(
import AI
from GameMaster import GameMaster
from MapData import MapData

# === Board placement (top-left of the 640x640 grid) ===
# Lower this to move the whole board (and its A–H / 1–8 labels) higher on screen.
BOARD_POS_X = WIDTH // 2 - 320
BOARD_POS_Y = 40

# === Game Log placement (anchored under the board) ===
LOG_W = WIDTH - 40              # full-ish width (tweak as you like)
LOG_H = 240                     # panel height (was 280)
LOG_X = 20                      # left margin
LOG_Y = BOARD_POS_Y + 700 + 12  # 12px below the 640x640 board

# --- Cream UI colors for the bottom log panel (like your screenshot) ---
UI_PANEL  = (245, 238, 228)   # panel fill
UI_HEADER = (233, 226, 214)   # header strip
UI_BORDER = (30, 30, 30)      # dark border
UI_TEXT   = (20, 20, 20)      # text

# --- Scrollbar colors ---
SB_TRACK       = (220, 213, 200)
SB_THUMB       = (160, 150, 135)
SB_THUMB_HOVER = (145, 135, 120)
SB_THUMB_DRAG  = (130, 120, 105)

# --- Team-colored highlight colors by status ---
# Team 1 (Blue)
HL1_MOVED = (90, 170, 255)   # moved only (still can act)
HL1_ACTED = (30, 120, 220)   # moved + acted (done)
# Team 2 (Red)
HL2_MOVED = (255, 140, 140)  # moved only
HL2_ACTED = (230, 60, 60)    # moved + acted

class GameMain:
    game_screen: int

    def __init__(self) -> None:
        pygame.init()
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))

        self.game_screen = 0
        # 0 = AI Selection Screen
        # 1 = Game Screen

        self.menu_cursor = HoverMenuCursor(self.screen, (420, 60), (5, 2))
        self.p1_sel_cursor = SelectMenuCursor(self.screen, (420, 60), (5, 1))
        self.p2_sel_cursor = SelectMenuCursor(self.screen, (420, 60), (5, 1))

        self.isAuto = True  # if True, auto repeat and skip delays
        self.map_list = list(MapData().data)
        self.map_number = 0

        self.game_state = 'selecting start area'

        self.total_p1_win = 0
        self.total_p2_win = 0

        # Fonts
        self.font_ss = pygame.font.Font('resource/font.ttf', 14)
        self.font_s = pygame.font.Font('resource/font.ttf', 24)
        self.font_sm = pygame.font.Font('resource/font.ttf', 30)
        self.font_m = pygame.font.Font('resource/font.ttf', 48)
        self.font_l = pygame.font.Font('resource/font.ttf', 96)

        self.GameMaster = GameMaster()
        self.currentMatch = 0

        # --- Game Log store ---
        # store tuples: (text, color)
        self.game_log: list[tuple[str, tuple[int, int, int]]] = []
        # used to mirror newly-added lines from activeAI.action_log
        self._ai_log_len = 0

        # --- Log panel style (header height kept) ---
        self._log_header_h = 28
        self._log_line_h = 22
        self._log_scroll_step = 1   # lines per wheel tick
        self._log_page_step = 8     # lines per page jump

        # --- Log scrolling state ---
        # Now: 0 means show from the very first line (oldest) at top.
        # Increase this to scroll down to newer content.
        self.log_scroll = 0

        # --- Scrollbar interaction state ---
        self._sb_dragging = False
        self._sb_drag_offset_y = 0  # mouse offset inside thumb while dragging
        self._sb_last_geometry = None  # cached geometry for hit tests

    # --------- logging helper ----------
    def log(self, text: str, color=(0, 0, 0)) -> None:
        """Append a line to the game log."""
        self.game_log.append((text, color))
        if len(self.game_log) > 500:  # prevent unbounded growth
            self.game_log.pop(0)

    # --------- geometry helper used by render & input ----------
    def _calc_log_geometry(self):
        """Return a dict with log panel & scrollbar geometry and paging info."""
        header_h = self._log_header_h
        line_h = self._log_line_h

        log_rect = pygame.Rect(LOG_X, LOG_Y, LOG_W, LOG_H)
        header_rect = pygame.Rect(log_rect.x, log_rect.y, log_rect.w, header_h)

        # Content area (lines) inside the panel below header, with small padding
        content_x = log_rect.x + 8
        content_y = header_rect.bottom + 6
        content_h = log_rect.bottom - content_y - 6
        max_lines = max(0, content_h // line_h)

        # Scrollbar track on far right inside panel
        sb_margin = 6
        sb_width = 10
        track_rect = pygame.Rect(
            log_rect.right - sb_margin - sb_width,
            header_rect.bottom + 6,
            sb_width,
            log_rect.bottom - (header_rect.bottom + 6) - 6
        )

        # Compute scroll bounds
        max_scroll = max(0, len(self.game_log) - max_lines)

        # Thumb size proportional to visible fraction; enforce a minimum
        if max_scroll == 0:
            thumb_h = track_rect.height
        else:
            visible_fraction = max_lines / max(len(self.game_log), 1)
            thumb_h = max(24, int(track_rect.height * visible_fraction))
            thumb_h = min(thumb_h, track_rect.height)

        # Thumb position maps log_scroll in [0, max_scroll]
        if max_scroll == 0:
            thumb_y = track_rect.y
        else:
            t = 0 if max_scroll == 0 else (self.log_scroll / max_scroll)
            thumb_y = int(track_rect.y + t * (track_rect.height - thumb_h))

        thumb_rect = pygame.Rect(track_rect.x, thumb_y, track_rect.width, thumb_h)

        return {
            "log_rect": log_rect,
            "header_rect": header_rect,
            "content_origin": (content_x, content_y),
            "content_max_lines": max_lines,
            "max_scroll": max_scroll,
            "track_rect": track_rect,
            "thumb_rect": thumb_rect,
            "line_h": line_h
        }

    def screen1init(self):
        self.match_limit = AUTO_MATCH_LIMIT  # should be changed to input at some point

        AI_types = ('Player Input', 'Perfect Play AI', 'Random AI', 'Personality Cores AI', 'Disable AI')
        self.team1_ID = self.p1_sel_cursor.grid[0]
        self.team2_ID = self.p2_sel_cursor.grid[0]
        print(f'{AI_types[self.team1_ID]} vs {AI_types[self.team2_ID]}')

        self.currentMatch = 0
        self.total_p1_win = 0
        self.total_p2_win = 0
        self.startMatch()

        # add a headline in the log when a game starts
        self.log(f"Game {self.currentMatch} started", UI_TEXT)

        self.game_screen = 1

    def startMatch(self) -> None:
        self.currentMatch += 1
        if self.isAuto and self.currentMatch > self.match_limit:
            print("Auto mode completed after " + str(self.match_limit) + " matches.")
            print("Player 1: " + str(self.total_p1_win) + " wins")
            print("Player 2: " + str(self.total_p2_win) + " wins")
            if self.total_p1_win > self.total_p2_win:
                self.game_state = 'win'
            elif self.total_p2_win > self.total_p1_win:
                self.game_state = 'lose'
            else:
                print("-Tie breaking Match-")
            return

        # ======= Board created at the NEW (X, Y) so it sits higher =======
        if self.map_number == len(self.map_list):
            self.field = Field(self.screen,
                               (BOARD_POS_X, BOARD_POS_Y),
                               (8, 8),
                               (640, 640),
                               rand_map=True)
        else:
            self.field = Field(self.screen,
                               (BOARD_POS_X, BOARD_POS_Y),
                               (8, 8),
                               (640, 640),
                               rand_map=False,
                               map_id=self.map_number)
        # =================================================================

        Character.removeAllCharacters()

        for i, pos in enumerate(self.field.team1_spawns[:3]):
            Character(self.screen,
                      (self.field.boxes_width, self.field.boxes_height),
                      (pos[0], pos[1]),
                      "player" + str(i + 1), team=1)
        for i, pos in enumerate(self.field.team2_spawns[:3]):
            Character(self.screen,
                      (self.field.boxes_width, self.field.boxes_height),
                      (pos[0], pos[1]),
                      "player" + str(i + 1), team=2)

        self.GameMaster.setTeams(self.team1_ID, self.team2_ID)
        self.GameMaster.team1.loadField(self.field)
        self.GameMaster.team2.loadField(self.field)
        if self.GameMaster.isActiveAIHuman():
            Cursor.state = 0
        else:
            Cursor.state = 6

        Cursor.state = 5
        Cursor.selected_action = -1

        self.round = 1
        self.round_title_timer = 0

        self.number_action = -1
        self.action_timer = 0

        self.p1_dom_count = 0
        self.p2_dom_count = 0

        self.action_delay = 0 if self.isAuto else 0.8

        # new round headline
        self.log(f"Round {self.round} begins", UI_TEXT)
        self._ai_log_len = 0  # reset mirror of AI log this match
        # Start at very top (oldest first visible)
        self.log_scroll = 0

    def _log_rect(self) -> pygame.Rect:
        """Helper: current log panel rect (same as in render)."""
        return pygame.Rect(LOG_X, LOG_Y, LOG_W, LOG_H)

    # --- helper: get exact tile rect from Field/boxes if available ---
    def _tile_rect(self, gx: int, gy: int) -> pygame.Rect:
        """
        Try to fetch the real pixel-rect of the tile from Field.boxes[gx][gy].
        If not available, fall back to computing from the field origin + tile size.
        """
        try:
            box = self.field.boxes[gx][gy]
            if hasattr(box, "rect"):
                r = box.rect
                return pygame.Rect(r.x, r.y, r.w, r.h) if hasattr(r, "x") else pygame.Rect(r)
            if hasattr(box, "pos"):
                px, py = box.pos
                return pygame.Rect(px, py, self.field.boxes_width, self.field.boxes_height)
            if hasattr(box, "x") and hasattr(box, "y"):
                return pygame.Rect(box.x, box.y, self.field.boxes_width, self.field.boxes_height)
        except Exception:
            pass

        tile_w = self.field.boxes_width
        tile_h = self.field.boxes_height
        origin = (
            getattr(self.field, "position", None)
            or getattr(self.field, "pos", None)
            or (getattr(self.field, "x", None), getattr(self.field, "y", None))
        )
        if origin and origin[0] is not None and origin[1] is not None:
            ox, oy = origin
        else:
            ox, oy = BOARD_POS_X, BOARD_POS_Y

        return pygame.Rect(ox + gx * tile_w, oy + gy * tile_h, tile_w, tile_h)

    def update(self, dt: float, events: list[pygame.event.Event]) -> None:
        if self.game_screen == 0:       # AI select screen
            for event in events:
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:  # ESC exits
                        pygame.quit()
                        sys.exit()
                    if event.key == pygame.K_RETURN or event.key == pygame.K_x:
                        if self.p1_sel_cursor.show and self.p2_sel_cursor.show:
                            self.screen1init()
                    if event.key == pygame.K_UP:
                        self.menu_cursor.moveBy(event.key)
                    if event.key == pygame.K_DOWN:
                        self.menu_cursor.moveBy(event.key)
                    if event.key == pygame.K_LEFT:
                        self.menu_cursor.moveBy(event.key)
                    if event.key == pygame.K_RIGHT:
                        self.menu_cursor.moveBy(event.key)
                    if event.key == pygame.K_z:
                        if self.menu_cursor.grid[1] == 0:
                            self.p1_sel_cursor.moveTo(self.menu_cursor.grid)
                            self.p1_sel_cursor.show = True
                        elif self.menu_cursor.grid[1] == 1:
                            self.p2_sel_cursor.moveTo(self.menu_cursor.grid)
                            self.p2_sel_cursor.show = True
                    if event.key == pygame.K_a:
                        self.isAuto = not self.isAuto
                    if event.key == pygame.K_m:
                        self.map_number += 1
                        if self.map_number > len(self.map_list):
                            self.map_number = 0

        elif self.game_screen == 1:
            # cache geometry for this frame
            geom = self._calc_log_geometry()
            self._sb_last_geometry = geom

            for event in events:
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()

                # --- Mouse wheel scrolling for the log (only when pointer over the log) ---
                if event.type == pygame.MOUSEWHEEL:
                    if geom["log_rect"].collidepoint(pygame.mouse.get_pos()):
                        if event.y > 0:
                            self.log_scroll = max(0, self.log_scroll - self._log_scroll_step * abs(event.y))
                        elif event.y < 0:
                            self.log_scroll = min(geom["max_scroll"],
                                                  self.log_scroll + self._log_scroll_step * abs(event.y))

                # --- Scrollbar mouse interactions ---
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    mx, my = event.pos
                    if geom["thumb_rect"].collidepoint(mx, my):
                        self._sb_dragging = True
                        self._sb_drag_offset_y = my - geom["thumb_rect"].y
                    elif geom["track_rect"].collidepoint(mx, my):
                        if my < geom["thumb_rect"].y:
                            self.log_scroll = max(0, self.log_scroll - self._log_page_step)
                        elif my > geom["thumb_rect"].bottom:
                            self.log_scroll = min(geom["max_scroll"], self.log_scroll + self._log_page_step)

                if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                    self._sb_dragging = False

                if event.type == pygame.MOUSEMOTION and self._sb_dragging:
                    mx, my = event.pos
                    track = geom["track_rect"]
                    max_scroll = geom["max_scroll"]
                    thumb_h = geom["thumb_rect"].height
                    new_thumb_y = my - self._sb_drag_offset_y
                    min_y = track.y
                    max_y = track.bottom - thumb_h
                    new_thumb_y = max(min_y, min(max_y, new_thumb_y))
                    if max_scroll == 0:
                        self.log_scroll = 0
                    else:
                        t = (new_thumb_y - track.y) / (track.height - thumb_h)
                        self.log_scroll = int(round(t * max_scroll))

                # Existing game controls (arrows NOT used for the log)
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:  # ESC exits
                        pygame.quit()
                        sys.exit()
                    if event.key == pygame.K_1:
                        self.action_delay = 0.1
                    if event.key == pygame.K_2:
                        self.action_delay = 0.4
                    if event.key == pygame.K_3:
                        self.action_delay = 0.8
                    if event.key == pygame.K_r:
                        if self.game_state == 'win' or self.game_state == 'lose':
                            self.startMatch()
                    if event.key in [pygame.K_UP, pygame.K_DOWN, pygame.K_LEFT, pygame.K_RIGHT, pygame.K_z, pygame.K_x]:
                        self.GameMaster.keyInput(event.key)
                    if event.key == pygame.K_p:
                        if self.game_state == 'win' or self.game_state == 'lose':
                            self.game_screen = 0

            # update by state
            if Cursor.state == 0:
                pass
            elif Cursor.state == 1:
                pass
            elif Cursor.state == 2:
                pass
            elif Cursor.state == 3:
                pass
            elif Cursor.state == 4:
                pass
            elif Cursor.state == 5:
                Cursor.state = 0
                self.game_state = 'enemy action'
            else:
                pass

            if self.isAuto:
                self.action_delay = 0

            if self.game_state != 'win' and self.game_state != 'lose':
                if not self.GameMaster.activeAI.ready:
                    self.GameMaster.calculate()
                else:
                    if not self.GameMaster.roundFinished:
                        if not self.GameMaster.isActiveAIHuman():
                            self.action_timer += dt
                            if self.action_timer >= self.action_delay:
                                self.action_timer = 0
                                self.number_action += 1
                                if self.number_action < len(self.GameMaster.activeAI.own_team):
                                    self.GameMaster.activateAI(self.number_action)
                                elif self.number_action > len(self.GameMaster.activeAI.own_team) + 2:  # Extra delay
                                    # End of round
                                    self.number_action = -1
                                    self.GameMaster.switchTurn()
                                    if self.GameMaster.isActiveAIHuman():
                                        Cursor.state = 0
                                    else:
                                        Cursor.state = 6
                        else:
                            self.action_timer += dt
                            if self.action_timer >= self.action_delay:
                                self.action_timer = 0
                                if self.GameMaster.activeAI.turnFinished:
                                    self.number_action = -1
                                    self.GameMaster.switchTurn()
                                    if self.GameMaster.isActiveAIHuman():
                                        Cursor.state = 0
                                    else:
                                        Cursor.state = 6

                    if self.GameMaster.roundFinished:
                        # Check win condition
                        team1_win_count = 0
                        team2_win_count = 0
                        for chara in Character.team1_list:
                            if self.field.boxes[chara.grid[0]][chara.grid[1]].terrain == 3:
                                team1_win_count += 1
                        for enemy in Character.team2_list:
                            if self.field.boxes[enemy.grid[0]][enemy.grid[1]].terrain == 3:
                                team2_win_count += 1
                        if team1_win_count > team2_win_count:
                            if self.p1_dom_count == 0:
                                self.p1_dom_count = 1
                                self.p2_dom_count = 0
                            elif self.p1_dom_count == 1:
                                if not self.isAuto:
                                    self.game_state = 'win'
                                else:
                                    self.total_p1_win += 1
                                    print("Match " + str(self.currentMatch) + " result: Player 1 wins")
                                    self.startMatch()
                            else:
                                print('There is a problem with dominance check')
                        elif team2_win_count > team1_win_count:
                            if self.p2_dom_count == 0:
                                self.p2_dom_count = 1
                                self.p1_dom_count = 0
                            elif self.p2_dom_count == 1:
                                if not self.isAuto:
                                    self.game_state = 'lose'
                                else:
                                    self.total_p2_win += 1
                                    print("Match " + str(self.currentMatch) + " result: Player 2 wins")
                                    self.startMatch()
                            else:
                                print('There is a problem with dominance check')
                        else:
                            self.round += 1
                            self.game_state = 'show round'
                            self.field.hover_cursor.show = True
                            self.p1_dom_count = 0
                            self.p2_dom_count = 0
                            self.log(f"Round {self.round} begins", UI_TEXT)

                        self.number_action = -1
                        for chara in Character.team1_list + Character.team2_list:
                            chara.moved = False
                            chara.acted = False

                        self.GameMaster.startRound()

            # --- Mirror any NEW lines from activeAI.action_log to the Game Log ---
            if hasattr(self.GameMaster, "activeAI") and self.GameMaster.activeAI is not None:
                log = getattr(self.GameMaster.activeAI, "action_log", None)
                if isinstance(log, list):
                    if len(log) > self._ai_log_len:
                        for line in log[self._ai_log_len:]:
                            self.log(line, getattr(self.GameMaster.activeAI, "color", (0,0,0)))
                        self._ai_log_len = len(log)

    def render(self) -> None:
        if self.game_screen == 0:
            self.screen.fill(SMOKE)

            p1_text = self.font_l.render(f"Player 1", False, (0, 0, 0))
            text_rect = p1_text.get_rect(midtop=(WIDTH // 4, 40))
            self.screen.blit(p1_text, text_rect)

            p2_text = self.font_l.render(f"Player 2", False, (0, 0, 0))
            text_rect = p2_text.get_rect(midtop=(WIDTH // 2 + WIDTH // 4, 40))
            self.screen.blit(p2_text, text_rect)

            AI_types = ('Player Input', 'Perfect Play AI', 'Random AI', 'Personality Cores AI', 'Disable AI')
            available1 = ('', '', '', '', '')
            available2 = ('', '', '', '', '')

            for i in range(len(AI_types)):
                pygame.draw.rect(self.screen, (0, 0, 0), pygame.Rect(WIDTH // 4 - 210, 200 + i*90, 420, 60), 2)
                text = self.font_sm.render(f'{AI_types[i]} {available1[i]}', False, (0, 0, 0))
                text_rect = text.get_rect(center=(WIDTH // 4, 200 + i*90 + 30))
                self.screen.blit(text, text_rect)

            for i in range(len(AI_types)):
                pygame.draw.rect(self.screen, (0, 0, 0), pygame.Rect(WIDTH // 2 + WIDTH // 4 - 210, 200 + i*90, 420, 60), 2)
                text = self.font_sm.render(f'{AI_types[i]} {available2[i]}', False, (0, 0, 0))
                text_rect = text.get_rect(center=(WIDTH // 2 + WIDTH // 4, 200 + i*90 + 30))
                self.screen.blit(text, text_rect)

            text = self.font_sm.render(f'Press X or ENTER to start', False, (0, 0, 0))
            text_rect = text.get_rect(center=(WIDTH // 2, 690))
            self.screen.blit(text, text_rect)

            mcx = WIDTH // 4 - 210
            mcy = 200 + self.p1_sel_cursor.grid[0] * 90
            self.p1_sel_cursor.render((mcx, mcy))

            mcx = WIDTH // 4 - 210 + WIDTH // 2
            mcy = 200 + self.p2_sel_cursor.grid[0] * 90
            self.p2_sel_cursor.render((mcx, mcy))

            mcx = WIDTH // 4 - 210 + self.menu_cursor.grid[1] * WIDTH // 2
            mcy = 200 + self.menu_cursor.grid[0] * 90
            self.menu_cursor.render((mcx, mcy))

            auto_text = self.font_s.render(f"Auto : {self.isAuto}", False, (0, 0, 0))
            text_rect = auto_text.get_rect(bottomleft=(40, 700))
            self.screen.blit(auto_text, text_rect)

            if self.map_number == len(self.map_list):
                map_text = self.font_s.render(f"Map : Random", False, (0, 0, 0))
                text_rect = map_text.get_rect(bottomright=(WIDTH - 40, 700))
                self.screen.blit(map_text, text_rect)
            else:
                map_text = self.font_s.render(f"Map : {str(self.map_list[self.map_number])}", False, (0, 0, 0))
                text_rect = map_text.get_rect(bottomright=(WIDTH - 40, 700))
                self.screen.blit(map_text, text_rect)

        elif self.game_screen == 1:
            self.screen.fill(SMOKE)

            # Draw board & units
            self.field.render()

            # === Finished-Action Highlights with team-specific colors ===
            # Team 1 (blue theme)
            for chara in Character.team1_list:
                rect = self._tile_rect(chara.grid[0], chara.grid[1])
                if getattr(chara, "acted", False):
                    pygame.draw.rect(self.screen, HL1_ACTED, rect, 4)
                elif getattr(chara, "moved", False):
                    pygame.draw.rect(self.screen, HL1_MOVED, rect, 4)

            # Team 2 (red theme)
            for chara in Character.team2_list:
                rect = self._tile_rect(chara.grid[0], chara.grid[1])
                if getattr(chara, "acted", False):
                    pygame.draw.rect(self.screen, HL2_ACTED, rect, 4)
                elif getattr(chara, "moved", False):
                    pygame.draw.rect(self.screen, HL2_MOVED, rect, 4)

            # Render Page
            # Unit Info
            pygame.draw.rect(self.screen, (0, 0, 0), pygame.Rect(40, 40, 260, 180), 2)
            unit_menu_text = self.font_s.render("Unit Info", False, (0, 0, 0))
            text_rect = unit_menu_text.get_rect(topleft=(50, 50))
            self.screen.blit(unit_menu_text, text_rect)
            if (chara := self.field.hover_cursor.getChara()) is not None:
                unit_info = self.font_s.render(chara.template['display_name'], False, (0, 0, 0))
                text_rect = unit_info.get_rect(topleft=(55, 80))
                self.screen.blit(unit_info, text_rect)
                unit_info = self.font_s.render(
                    f"HP : {chara.template['curHP']}/{chara.template['maxHP']}", False,
                    (0, 0, 0))
                text_rect = unit_info.get_rect(topleft=(55, 105))
                self.screen.blit(unit_info, text_rect)
                unit_info = self.font_s.render(f"Movement : {chara.template['movement']}", False, (0, 0, 0))
                text_rect = unit_info.get_rect(topleft=(55, 130))
                self.screen.blit(unit_info, text_rect)
                if chara in Character.team1_list:
                    if not chara.moved:
                        text = "Movement available"
                    elif not chara.acted:
                        text = "Action available"
                    else:
                        text = "Turn completed"
                    unit_info = self.font_s.render(text, False, (0, 0, 0))
                    text_rect = unit_info.get_rect(topleft=(55, 155))
                    self.screen.blit(unit_info, text_rect)

            # Terrain Info
            pygame.draw.rect(self.screen, (0, 0, 0), pygame.Rect(40, 240, 260, 180), 2)
            terrain_menu_text = self.font_s.render("Terrain Info", False, (0, 0, 0))
            text_rect = terrain_menu_text.get_rect(topleft=(50, 250))
            self.screen.blit(terrain_menu_text, text_rect)

            box = self.field.getHoveredBoxInfo()

            terrain_name = self.font_s.render(box.terrain_name, False, (0, 0, 0))
            terrain_desc = self.font_s.render(box.terrain_desc, False, (0, 0, 0))

            self.screen.blit(terrain_name, terrain_name.get_rect(topleft=(55, 280)))
            self.screen.blit(terrain_desc, terrain_desc.get_rect(topleft=(55, 310)))

            # Objective Info
            pygame.draw.rect(self.screen, (0, 0, 0), pygame.Rect(40, 440, 260, 240), 2)
            objective_menu_text = self.font_s.render("Objective Info", False, (0, 0, 0))
            text_rect = objective_menu_text.get_rect(topleft=(50, 450))
            self.screen.blit(objective_menu_text, text_rect)
            text = self.font_s.render(f'Have units stand', False, (0, 0, 0))
            text_rect = text.get_rect(topleft=(55, 480))
            self.screen.blit(text, text_rect)
            text = self.font_s.render(f'in objective area', False, (0, 0, 0))
            text_rect = text.get_rect(topleft=(55, 505))
            self.screen.blit(text, text_rect)
            text = self.font_s.render(f'more than enemy.', False, (0, 0, 0))
            text_rect = text.get_rect(topleft=(55, 530))
            self.screen.blit(text, text_rect)

            # Game State Indicator (Will be hide for now)
            game_state_text = self.font_s.render(f'{self.game_state}', False, (0, 0, 0))
            text_rect = game_state_text.get_rect(bottomright=(1230, 30))
            self.screen.blit(game_state_text, text_rect)

            # AI Type vs AI Type (May hide later)
            AI_types = ('Player Input', 'Perfect Play AI', 'Random AI', 'Personality Cores AI', 'Independent Action AI')
            text = self.font_ss.render(f'{AI_types[self.p1_sel_cursor.grid[0]]} vs {AI_types[self.p2_sel_cursor.grid[0]]}', False, (0, 0, 0))
            text_rect = text.get_rect(bottomleft=(50, 30))
            self.screen.blit(text, text_rect)

            # Actions Menu
            if not self.GameMaster.isActiveAIHuman():
                pygame.draw.rect(self.screen, (0, 0, 0), pygame.Rect(980, 40, 260, 640), 2)
                objective_menu_text = self.font_s.render("Actions Log", False, (0, 0, 0))
                text_rect = objective_menu_text.get_rect(topleft=(990, 50))
                self.screen.blit(objective_menu_text, text_rect)
                i = 0
                for t in self.GameMaster.activeAI.action_log:
                    text = self.font_ss.render(f'{t}', False, self.GameMaster.activeAI.color)
                    text_rect = text.get_rect(topleft=(995, 80 + i))
                    self.screen.blit(text, text_rect)
                    i += 20
            else:
                pygame.draw.rect(self.screen, (0, 0, 0), pygame.Rect(980, 40, 260, 640), 2)
                objective_menu_text = self.font_s.render("Actions List", False, (0, 0, 0))
                text_rect = objective_menu_text.get_rect(topleft=(990, 50))
                self.screen.blit(objective_menu_text, text_rect)
                i = 0
                if self.field.hover_cursor.getChara() or self.field.select_cursor.getChara():
                    if Cursor.state != 4:
                        chara = self.field.hover_cursor.getChara() if self.field.hover_cursor.getChara() else self.field.select_cursor.getChara()
                    else:
                        chara = self.field.select_cursor.getChara()
                    for index, action in enumerate(chara.template["actions"]):
                        pygame.draw.rect(self.screen, (0, 0, 0), pygame.Rect(1000, 80 + i, 220, 150), 1)
                        if Cursor.selected_action == index:
                            pygame.draw.rect(self.screen, YELLOW, pygame.Rect(1000, 80 + i, 220, 150), 4)
                        objective_menu_text = self.font_s.render(action["action_display_name"], False, (0, 0, 0))
                        text_rect = objective_menu_text.get_rect(topleft=(1010, 90 + i))
                        self.screen.blit(objective_menu_text, text_rect)
                        objective_menu_text = self.font_s.render(f'Type : {action["action_type"]}', False, (0, 0, 0))
                        text_rect = objective_menu_text.get_rect(topleft=(1015, 120 + i))
                        self.screen.blit(objective_menu_text, text_rect)
                        objective_menu_text = self.font_s.render(f'Area : {action["target"]}', False, (0, 0, 0))
                        text_rect = objective_menu_text.get_rect(topleft=(1015, 145 + i))
                        self.screen.blit(objective_menu_text, text_rect)
                        objective_menu_text = self.font_s.render(f'Range : {action["range"]}', False, (0, 0, 0))
                        text_rect = objective_menu_text.get_rect(topleft=(1015, 170 + i))
                        self.screen.blit(objective_menu_text, text_rect)
                        objective_menu_text = self.font_s.render(f'Damage : {action["damage"]}', False, (0, 0, 0))
                        text_rect = objective_menu_text.get_rect(topleft=(1015, 195 + i))
                        self.screen.blit(objective_menu_text, text_rect)
                        i += 180
                    pygame.draw.rect(self.screen, (0, 0, 0), pygame.Rect(1000, 620, 220, 40), 1)
                    if Cursor.selected_action == len(chara.template['actions']):       # Pass button
                        pygame.draw.rect(self.screen, YELLOW, pygame.Rect(1000, 620, 220, 40), 4)
                    objective_menu_text = self.font_s.render('Pass', False, (0, 0, 0))
                    text_rect = objective_menu_text.get_rect(topleft=(1010, 630))
                    self.screen.blit(objective_menu_text, text_rect)

            # info text
            if Cursor.state == 0:
                action_text = self.font_s.render("Z : Move Unit / Perform Action    X : Does Nothing    P : Pass All", False, (0, 0, 0))
                text_rect = action_text.get_rect(topleft=(50, 690))
                self.screen.blit(action_text, text_rect)
            elif Cursor.state == 1:
                action_text = self.font_s.render("Z : Move Unit    X : Cancel    P : Pass All", False, (0, 0, 0))
                text_rect = action_text.get_rect(topleft=(50, 690))
                self.screen.blit(action_text, text_rect)
            elif Cursor.state == 2:
                action_text = self.font_s.render("Z : Confirm Option    X : Cancel    P : Pass All", False, (0, 0, 0))
                text_rect = action_text.get_rect(topleft=(50, 690))
                self.screen.blit(action_text, text_rect)
            elif Cursor.state == 3:
                action_text = self.font_s.render("Z : Does Nothing    X : Cancel    P : Pass All", False, (0, 0, 0))
                text_rect = action_text.get_rect(topleft=(50, 690))
                self.screen.blit(action_text, text_rect)
            elif Cursor.state == 4:
                action_text = self.font_s.render("Z : Perform Action    X : Cancel    P : Pass All", False, (0, 0, 0))
                text_rect = action_text.get_rect(topleft=(50, 690))
                self.screen.blit(action_text, text_rect)
            elif Cursor.state == 5:
                action_text = self.font_s.render("Z : Select / Move Unit    X : Confirm position", False, (0, 0, 0))
                text_rect = action_text.get_rect(topleft=(50, 690))
                self.screen.blit(action_text, text_rect)

            # Round Indicator at corner
            round_text = self.font_s.render(f"Round : {self.round}", False, (0, 0, 0))
            text_rect = round_text.get_rect(topright=(1230, 690))
            self.screen.blit(round_text, text_rect)

            # Round Indicator at center
            if self.game_state == 'show round':
                pygame.draw.rect(self.screen, WHITE, pygame.Rect(WIDTH // 2 - 300, HEIGHT // 2 - 90, 600, 180))
                pygame.draw.rect(self.screen, BLACK, pygame.Rect(WIDTH // 2 - 300, HEIGHT // 2 - 90, 600, 180), 4)
                round_text = self.font_l.render(f"Round : {self.round}", False, (0, 0, 0))
                text_rect = round_text.get_rect(center=(WIDTH // 2, HEIGHT // 2))
                self.screen.blit(round_text, text_rect)

                # Set Delay
                self.round_title_timer += dt
                if self.round_title_timer >= ROUND_DELAY:
                    self.round_title_timer = 0
                    self.game_state = 'enemy action'

            # Delay text
            delay_text = self.font_ss.render(f'Delay = {self.action_delay}', False, (0, 0, 0))
            text_rect = delay_text.get_rect(bottomleft=(50, 670))
            self.screen.blit(delay_text, text_rect)

            if self.game_state == 'win':
                pygame.draw.rect(self.screen, WHITE, pygame.Rect(WIDTH // 2 - 300, HEIGHT // 2 - 90, 600, 180))
                pygame.draw.rect(self.screen, BLACK, pygame.Rect(WIDTH // 2 - 300, HEIGHT // 2 - 90, 600, 180), 4)
                round_text = self.font_l.render(f"P1 Win!!", False, (0, 0, 0))
                text_rect = round_text.get_rect(center=(WIDTH // 2, HEIGHT // 2))
                self.screen.blit(round_text, text_rect)

            if self.game_state == 'lose':
                pygame.draw.rect(self.screen, WHITE, pygame.Rect(WIDTH // 2 - 300, HEIGHT // 2 - 90, 600, 180))
                pygame.draw.rect(self.screen, BLACK, pygame.Rect(WIDTH // 2 - 300, HEIGHT // 2 - 90, 600, 180), 4)
                round_text = self.font_l.render(f"P2 Win!!", False, (0, 0, 0))
                text_rect = round_text.get_rect(center=(WIDTH // 2, HEIGHT // 2))
                self.screen.blit(round_text, text_rect)

            # ----------------- Game Log Panel (with SCROLLBAR) -----------------
            geom = self._calc_log_geometry()

            # panel fill + border
            pygame.draw.rect(self.screen, UI_PANEL, geom["log_rect"])
            pygame.draw.rect(self.screen, UI_BORDER, geom["log_rect"], 2)

            # header strip
            pygame.draw.rect(self.screen, UI_HEADER, geom["header_rect"])
            pygame.draw.rect(self.screen, UI_BORDER, geom["header_rect"], 2)

            title = self.font_s.render("Game Log", False, UI_TEXT)
            self.screen.blit(title, title.get_rect(topleft=(geom["header_rect"].x + 8, geom["header_rect"].y + 4)))

            # log lines (chronological: oldest at top)
            x, y = geom["content_origin"]
            line_h = geom["line_h"]
            max_lines = geom["content_max_lines"]

            # clamp scroll to what can actually scroll right now
            max_scroll = geom["max_scroll"]
            if self.log_scroll > max_scroll:
                self.log_scroll = max_scroll
            if self.log_scroll < 0:
                self.log_scroll = 0

            start = self.log_scroll
            end   = min(len(self.game_log), start + max_lines)

            for text, color in self.game_log[start:end]:
                img = self.font_s.render(text, False, color)
                self.screen.blit(img, (x, y))
                y += line_h

            # Scrollbar track
            pygame.draw.rect(self.screen, SB_TRACK, geom["track_rect"], border_radius=5)

            # Thumb (hover / drag colors)
            mouse_pos = pygame.mouse.get_pos()
            if self._sb_dragging:
                thumb_color = SB_THUMB_DRAG
            elif geom["thumb_rect"].collidepoint(mouse_pos):
                thumb_color = SB_THUMB_HOVER
            else:
                thumb_color = SB_THUMB

            pygame.draw.rect(self.screen, thumb_color, geom["thumb_rect"], border_radius=5)
            pygame.draw.rect(self.screen, UI_BORDER, geom["thumb_rect"], 1, border_radius=5)
            # -----------------------------------------------------------------------

if __name__ == '__main__':
    main = GameMain()
    clock = pygame.time.Clock()

    while True:
        pygame.display.set_caption("Turn-based game : {:d} FPS".format(int(clock.get_fps())))

        # elapsed time from the last call
        dt = clock.tick(MAX_FRAME_RATE) / 1000.0

        events = pygame.event.get()
        main.update(dt, events)
        main.render()

        pygame.display.update()
