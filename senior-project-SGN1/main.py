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
import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from datetime import datetime
import os

AI_SELECTION_LABELS = (
    'Player Input',
    'Perfect Play AI',
    'Random AI',
    'Personality Cores AI',
    'Disable AI'
)



# === Board placement (top-left of the 640x640 grid) ===
# Lower this to move the whole board (and its A-H / 1-8 labels) higher on screen.
BOARD_POS_X = WIDTH // 2 - 320
BOARD_POS_Y = 40

# === Game Log placement (anchored under the board) ===
LOG_W = WIDTH - 40              # full-ish width (tweak as you like)
LOG_H = 270                     # panel height (was 280)
LOG_X = 20                      # left margin
LOG_Y = BOARD_POS_Y + 700

# --- Cream UI colors for the bottom log panel (like your screenshot) ---
UI_PANEL  = (251, 247, 242)   # panel fill
UI_HEADER = (233, 226, 214)   # header strip
UI_BORDER = (30, 30, 30)      # dark border
UI_TEXT   = (20, 20, 20)      # text

LOG_COLOR_GAME    = (20, 20, 20)      # black
LOG_COLOR_ROUND   = (255, 165, 0)     # orange
LOG_COLOR_SUMMARY = (22, 138, 36)     # green
LOG_COLOR_P1      = (54, 92, 168)     # blue
LOG_COLOR_P2      = (178, 64, 64)     # red

# --- Scrollbar colors ---
SB_TRACK       = (220, 213, 200)
SB_THUMB       = (160, 150, 135)
SB_THUMB_HOVER = (145, 135, 120)
SB_THUMB_DRAG  = (130, 120, 105)

class GameMain:
    game_screen: int

    def __init__(self) -> None:
        pygame.init()
        # --- Scaling/display setup ---
        self.scale: float = 1.0  # 1.0 = desktop/default, <1.0 for laptops/macbooks
        # Center window on screen before creating it
        os.environ['SDL_VIDEO_CENTERED'] = '1'
        self.display = pygame.display.set_mode((WIDTH, HEIGHT))  # actual OS window
        # Render everything to a base canvas at the logical/original resolution,
        # then scale to the window size when presenting.
        self.screen = pygame.Surface((WIDTH, HEIGHT))
        # Save original mouse func and install a patch that returns base-space coords
        self._orig_mouse_get_pos = pygame.mouse.get_pos
        self._install_mouse_patch()

        self.game_screen = -1
        # -1 = Start Screen
        # 0 = AI Selection Screen
        # 1 = Game Screen

        # Load background image
        self.background = pygame.image.load('resource/background/background_1.png')
        self.background = pygame.transform.scale(self.background, (WIDTH, HEIGHT))

        # Play button properties
        self.play_button_rect = pygame.Rect(510, 405, 250, 100)
        self.play_button_hovered = False
        # Laptop/Macbook button to scale window down for smaller screens
        self.laptop_button_rect = pygame.Rect(220, 405, 250, 55)
        self.laptop_button_hovered = False

        self.menu_cursor = HoverMenuCursor(self.screen, (420, 60), (5, 2))
        self.p1_sel_cursor = SelectMenuCursor(self.screen, (420, 60), (5, 1))
        self.p2_sel_cursor = SelectMenuCursor(self.screen, (420, 60), (5, 1))

        self.isAuto = True  # if True, auto repeat and skip delays
        self.map_list = list(MapData().data)
        # to change the defaults, change this
        self.map_number = 0
        # self.mapNumber = len(self.map_list)  # default is set to random

        # --- Model picker (AI select page) ---
        self.p1_model_index = 0
        self.p2_model_index = 0
        self._show_model_modal = False
        self._model_modal_for = 1      # 1 = selecting for P1, 2 = P2
        self._model_hover = -1

    # Buttons for model selection (under AI choices)
        self._model_btn_p1 = pygame.Rect(360, 590, 260, 40)
        self._model_btn_p2 = pygame.Rect(630, 590, 260, 40)


        self.game_state = 'selecting start area'

        self.total_p1_win = 0
        self.total_p2_win = 0
        self.p1_round_wins = 0
        self.p2_round_wins = 0
        self._current_map_label = ''

        # Fonts
        self.font_ss = pygame.font.Font('resource/font.ttf', 14)
        self.font_s = pygame.font.Font('resource/font.ttf', 24)
        self.font_sm = pygame.font.Font('resource/font.ttf', 30)
        self.font_m = pygame.font.Font('resource/font.ttf', 48)
        self.font_l = pygame.font.Font('resource/font.ttf', 96)
        self.font_end_title = pygame.font.Font('resource/font.ttf', 74)
        self.font_end_button = pygame.font.Font('resource/font.ttf', 24)
        self.font_menu_label = pygame.font.Font('resource/font.ttf', 26)

        # --- Map selection UI geometry/state ---
        self._map_select_button_rect = pygame.Rect(995, 903, 220, 48)
        self._map_preview_thumb_rect = pygame.Rect(800, 853, 151, 150)

        popup_width, popup_height = 1063, 907
        popup_x = (WIDTH - popup_width) // 2
        popup_y = (HEIGHT - popup_height) // 2
        self._map_popup_rect = pygame.Rect(popup_x, popup_y, popup_width, popup_height)

        preview_offset_x, preview_offset_y = 545, 55
        self._map_popup_preview_rect = pygame.Rect(
            self._map_popup_rect.x + preview_offset_x,
            self._map_popup_rect.y + preview_offset_y,
            461,
            459,
        )

        select_offset_x, select_offset_y = 681, 597
        self._map_popup_select_rect = pygame.Rect(
            self._map_popup_rect.x + select_offset_x,
            self._map_popup_rect.y + select_offset_y,
            219,
            53,
        )
        self._map_popup_option_rects = self._build_map_option_rects()
        self._map_popup_open = False
        self._map_popup_hover_index: int | None = None
        self._map_popup_temp_selection = self._clamp_map_index(self.map_number)
        self._map_button_hovered = False
        self._map_popup_select_hovered = False
        self._map_option_labels = [self._map_label_from_key(name) for name in self.map_list] + ['Random']
        self._map_preview_large, self._map_preview_small = self._load_map_previews()

        # Match limit slider geometry/state
        self.match_limit = AUTO_MATCH_LIMIT  # default slider value (1..10)
        self._match_limit_min = 1
        self._match_limit_max = 10
        self._match_limit_box_rect = pygame.Rect(224, 945, 58, 25)
        self._match_limit_slider_rect = pygame.Rect(292, 945, 220, 25)
        self._match_limit_knob_width = 16
        self._match_limit_knob_height = 16
        self._match_limit_slider_dragging = False

        # Game limit slider geometry/state (another slider shown above Match limit)
        self.game_limit = AUTO_GAME_LIMIT
        self._game_limit_min = 1
        self._game_limit_max = 10
        self._game_limit_box_rect = pygame.Rect(224, 915, 58, 25)
        self._game_limit_slider_rect = pygame.Rect(292, 915, 220, 25)
        self._game_limit_knob_width = 16
        self._game_limit_knob_height = 16
        self._game_limit_slider_dragging = False

        # --- Endgame popup geometry ---
        self.endgame_popup_rect = pygame.Rect(243, 151, 794, 420)
        self.endgame_menu_button_rect = pygame.Rect(342, 416, 166, 56)
        self.endgame_restart_button_rect = pygame.Rect(558, 416, 166, 56)
        self.endgame_export_button_rect = pygame.Rect(774, 416, 166, 56)
        self._endgame_overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        self.endgame_menu_hovered = False
        self.endgame_restart_hovered = False
        self.endgame_export_hovered = False
        # Keyboard selection for endgame buttons; None means no button highlighted yet.
        self._endgame_selected_idx: int | None = None
        self._prev_endgame_active = False

        # --- Pause popup (for human player) ---
        self._pause_active = False
        self.pause_popup_rect = pygame.Rect(243, 151, 794, 420)
        self.pause_resume_button_rect = pygame.Rect(342, 416, 166, 56)
        self.pause_restart_button_rect = pygame.Rect(558, 416, 166, 56)
        self.pause_menu_button_rect = pygame.Rect(774, 416, 166, 56)
        self.pause_resume_hovered = False
        self.pause_restart_hovered = False
        self.pause_menu_hovered = False
        self._pause_selected_idx = 0  # 0=Resume, 1=Restart, 2=Menu

        self.GameMaster = GameMaster()
        self.currentMatch = 0
        self._series_summary_logged = False

        # --- Match selection history (for restart functionality) ---
        self.last_team1_ID: int | None = None
        self.last_team2_ID: int | None = None
        self.last_map_selection_value: int | None = None
        self.last_map_generated_id: int | None = None
        self.last_map_was_random = False
        self._next_map_id_override: int | None = None

        # Pass player turn button
        self.pass_turn_button_rect = pygame.Rect(987, 620, 245, 45)
        self.pass_turn_button_hovered = False
        # Pause button
        self.pause_game_button_rect = pygame.Rect(40, 40, 260, 56)
        self.pause_game_button_hovered = False
        # --- Game Log store ---
        # store tuples: (text, color)
        self.game_log: list[tuple[str, tuple[int, int, int]]] = []
        # used to mirror newly-added lines from activeAI.action_log
        self._ai_log_len: dict[object, int] = {}
        self._ai_pending_lines: dict[int, list[str]] = {}
        self._char_snapshots: dict[int, dict] = {}
        self._ai_type_labels = AI_SELECTION_LABELS
        self._pending_ko_sources: dict[int, dict] = {}
        self._pending_ko_sources_by_name: dict[tuple[str, int], dict] = {}

        # --- Log panel style (header height kept) ---
        self._log_header_h = 28
        self._log_line_h = 22
        self._log_scroll_step = 1   # lines per wheel tick
        self._log_page_step = 8     # lines per page jump

        # --- Log scrolling state ---
        # 0 shows the newest entry at the top.
        # Increase this to scroll down to older content.
        self.log_scroll = 0

        # --- Scrollbar interaction state ---
        self._sb_dragging = False
        self._sb_drag_offset_y = 0  # mouse offset inside thumb while dragging
        self._sb_last_geometry = None  # cached geometry for hit tests
        
        self.cumulative_time = 0.0
        self.match_start_time = 0.0
        self.last_match_duration = 0.0       

    # ---- scaling helpers ----
    def _install_mouse_patch(self) -> None:
        """Patch pygame.mouse.get_pos to return base-space coords (divide by scale)."""
        orig = self._orig_mouse_get_pos
        def _get_pos():
            x, y = orig()
            s = self.scale if self.scale != 0 else 1.0
            return int(x / s), int(y / s)
        pygame.mouse.get_pos = _get_pos

    def _apply_scale(self, scale: float) -> None:
        """Apply a new scale: resize the OS window; game still renders to base surface."""
        self.scale = max(0.6, min(1.0, float(scale)))  # clamp between 0.6 and 1.0
        new_size = (int(WIDTH * self.scale), int(HEIGHT * self.scale))
        # Re-center the window whenever we recreate it
        os.environ['SDL_VIDEO_CENTERED'] = '1'
        self.display = pygame.display.set_mode(new_size)
        self._install_mouse_patch()

    def _scale_for_laptop(self) -> float:
        """Calculate a scale so the window is strictly smaller than 1280x1040."""
        max_w, max_h = 1280, 1040
        # Compute the largest scale that fits within the bounds
        s = min(max_w / float(WIDTH), max_h / float(HEIGHT), 1.0)
        # Nudge a tiny bit smaller to be strictly under the limits
        s = min(s, 0.75)
        return max(0.5, s)

    def _scale_events_to_base(self, events: list[pygame.event.Event]) -> list[pygame.event.Event]:
        """Return a copy of events with .pos mapped into base-space (divide by scale)."""
        out: list[pygame.event.Event] = []
        for e in events:
            d = getattr(e, 'dict', {}).copy()
            if 'pos' in d and isinstance(d['pos'], (tuple, list)):
                x, y = d['pos']
                s = self.scale if self.scale != 0 else 1.0
                d['pos'] = (int(x / s), int(y / s))
                e2 = pygame.event.Event(e.type, d)
                out.append(e2)
            else:
                out.append(e)
        return out

    def _build_map_option_rects(self) -> list[pygame.Rect]:
        base_offsets = [
            (89, 96),
            (89, 181),
            (89, 266),
            (89, 351),
            (89, 436),
            (305, 96),
            (305, 181),
            (305, 266),
            (305, 351),
            (305, 436),
        ]
        total_options = len(self.map_list) + 1  # include Random option
        rects: list[pygame.Rect] = []
        self._map_option_positions: list[tuple[int, int]] = []
        for idx in range(total_options):
            coord_index = min(idx, len(base_offsets) - 2)
            offset_x, offset_y = base_offsets[coord_index]
            x = self._map_popup_rect.x + offset_x
            y = self._map_popup_rect.y + offset_y
            rects.append(pygame.Rect(x, y, 128, 50))
            col = 0 if offset_x < 200 else 1
            row = round((offset_y - base_offsets[0][1]) / 85)
            self._map_option_positions.append((row, col))
        return rects

    def _map_label_from_key(self, key: str) -> str:
        if not key:
            return key
        if ' ' in key:
            return key.split(' ', 1)[1]
        return key

    def _load_map_previews(self) -> tuple[list[pygame.Surface], list[pygame.Surface]]:
        large_size = self._map_popup_preview_rect.size
        thumb_size = self._map_preview_thumb_rect.size
        large_surfaces: list[pygame.Surface] = []
        small_surfaces: list[pygame.Surface] = []
        for idx in range(len(self.map_list)):
            path = os.path.join('resource', 'map', f'map{idx}.jpg')
            try:
                image = pygame.image.load(path).convert()
            except (pygame.error, FileNotFoundError):
                image = pygame.Surface(large_size)
                image.fill((210, 210, 210))
            large_surface = pygame.transform.smoothscale(image, large_size)
            small_surface = pygame.transform.smoothscale(image, thumb_size)
            large_surfaces.append(large_surface)
            small_surfaces.append(small_surface)

        random_large = self._create_random_preview(large_size, self.font_end_title)
        random_small = self._create_random_preview(thumb_size, self.font_m)
        large_surfaces.append(random_large)
        small_surfaces.append(random_small)
        return large_surfaces, small_surfaces

    def _create_random_preview(self, size: tuple[int, int], font: pygame.font.Font) -> pygame.Surface:
        surface = pygame.Surface(size)
        surface.fill((220, 220, 220))
        border_rect = surface.get_rect()
        pygame.draw.rect(surface, (180, 180, 180), border_rect, 4)
        text = font.render('?', False, (80, 80, 80))
        text_rect = text.get_rect(center=border_rect.center)
        surface.blit(text, text_rect)
        return surface

    def _clamp_map_index(self, index: int) -> int:
        max_index = len(self.map_list)
        if index < 0:
            return 0
        if index > max_index:
            return max_index
        return index

    def _handle_map_popup_event(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self._map_popup_open = False
                self._map_popup_select_hovered = False
                self._map_popup_temp_selection = self._clamp_map_index(self.map_number)
                self._map_popup_hover_index = None
                return True
            if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                self.map_number = self._map_popup_temp_selection
                self._map_popup_open = False
                self._map_popup_select_hovered = False
                self._map_popup_hover_index = None
                return True
            if event.key in (pygame.K_UP, pygame.K_DOWN, pygame.K_LEFT, pygame.K_RIGHT):
                self._move_map_popup_selection(event.key)
                return True
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self._map_popup_select_rect.collidepoint(event.pos):
                self.map_number = self._map_popup_temp_selection
                self._map_popup_open = False
                self._map_popup_select_hovered = False
                self._map_popup_hover_index = None
                return True
            for idx, rect in enumerate(self._map_popup_option_rects):
                if rect.collidepoint(event.pos):
                    self._map_popup_temp_selection = idx
                    return True
            if not self._map_popup_rect.collidepoint(event.pos):
                self._map_popup_open = False
                self._map_popup_select_hovered = False
                self._map_popup_temp_selection = self._clamp_map_index(self.map_number)
                self._map_popup_hover_index = None
                return True
        elif event.type == pygame.MOUSEMOTION:
            if self._map_popup_rect.collidepoint(event.pos):
                for idx, rect in enumerate(self._map_popup_option_rects):
                    if rect.collidepoint(event.pos):
                        self._map_popup_hover_index = idx
                        break
                else:
                    self._map_popup_hover_index = None
            else:
                self._map_popup_hover_index = None
            return True
        return False

    def _move_map_popup_selection(self, key: int) -> None:
        if not self._map_popup_option_rects:
            return
        current_idx = self._clamp_map_index(self._map_popup_temp_selection)
        current_row, current_col = self._map_option_positions[current_idx]

        def best_candidate(predicate) -> int | None:
            best: tuple[int, int] | None = None
            best_idx: int | None = None
            for idx, (row, col) in enumerate(self._map_option_positions):
                if idx == current_idx:
                    continue
                if predicate(row, col):
                    diff_row = abs(row - current_row)
                    diff_col = abs(col - current_col)
                    weight = diff_row * 10 + diff_col
                    if best is None or (weight, row, col) < best:
                        best = (weight, row, col)
                        best_idx = idx
            return best_idx

        next_idx: int | None = None
        if key == pygame.K_UP:
            next_idx = best_candidate(lambda r, c: c == current_col and r < current_row)
        elif key == pygame.K_DOWN:
            next_idx = best_candidate(lambda r, c: c == current_col and r > current_row)
        elif key == pygame.K_LEFT:
            next_idx = best_candidate(lambda r, c: c < current_col)
        elif key == pygame.K_RIGHT:
            next_idx = best_candidate(lambda r, c: c > current_col)

        if next_idx is not None:
            self._map_popup_temp_selection = next_idx

    # --------- logging helper ----------
    def log(self, text: str, color=(0, 0, 0), time_elapsed=0.0) -> None:
        """Append a line to the game log."""
        # Store tuple: (text, color, time_elapsed)
        self.game_log.insert(0, (text, color, time_elapsed))
        if len(self.game_log) > 500:  # prevent unbounded growth
            self.game_log.pop()
        # We do NOT auto-jump to bottom; view stays where the user left it.

    def log_event(self, event: str, **kwargs) -> None:
        """Build and append a formatted log entry for a structured event."""
        tag_labels = {
            "GAME": "GAME : ",
            "ROUND": "ROUND : ",
            "P1": "P1 : ",
            "P2": "P2 : ",
            "SUMMARY": "SUMMARY : "
        }
        def tag_color(tag: str) -> tuple[int, int, int]:
            return {
                "GAME": LOG_COLOR_GAME,
                "ROUND": LOG_COLOR_ROUND,
                "SUMMARY": LOG_COLOR_SUMMARY,
                "P1": LOG_COLOR_P1,
                "P2": LOG_COLOR_P2,
            }.get(tag, UI_TEXT)
        def board_label(grid: tuple[int, int] | None) -> str:
            if grid is None:
                return ""
            row, col = grid
            return f"{chr(ord('A') + col)}{GRID_ROWS - row}"
        tag = "GAME"
        message = ""
        actor_health = 0  # Initialize actor's health
        if event == "match_start":
            tag = "GAME"
            message = ("Match {match} starts   Map: {map_label}   P1: {ai1}   P2: {ai2}".format(
                match=kwargs.get("match"),
                map_label=kwargs.get("map_label", ""),
                ai1=kwargs.get("ai1", ""),
                ai2=kwargs.get("ai2", "")
            ))
        elif event == "round_begin":
            tag = "ROUND"
            message = f"Round {kwargs.get('round')} begins"
        elif event == "round_end":
            tag = "ROUND"
            message = f"Round {kwargs.get('round')} ends"
        elif event == "move":
            team = kwargs.get("team")
            tag = "P1" if team == 1 else "P2"
            actor = kwargs.get("actor", "")
            start = board_label(kwargs.get("start"))
            end = board_label(kwargs.get("end"))
            distance = kwargs.get("distance", 0)
            message = f"{actor} moves {start} -> {end} ({distance} tiles)"
            # --- GET ACTOR'S HEALTH FOR MOVE EVENT ---
            for chara in Character.team1_list + Character.team2_list:
                if chara.template.get("display_name", "") == actor:
                    actor_health = chara.template.get("curHP", 0)
                    break
        elif event == "attack":
            team = kwargs.get("team")
            tag = "P1" if team == 1 else "P2"
            actor = kwargs.get("actor", "")
            target = kwargs.get("target", "")
            action = kwargs.get("action", "")
            amount = kwargs.get("amount", 0)
            hp_before = kwargs.get("hp_before", 0)
            hp_cur = kwargs.get("hp_cur", 0)
            hp_max = kwargs.get("hp_max", 0)
            target_position = kwargs.get("target_position", "")  # ✅ Add this line
            message = (f"{actor} attacks {target} with \"{action}\" - hit for {amount} "
                    f"(HP before: {hp_before}, after: {hp_cur}/{hp_max})")
            if target_position:
                message += f" at {target_position}"  # ✅ Append position to message
            # --- GET ACTOR'S HEALTH FOR ATTACK EVENT ---
            for chara in Character.team1_list + Character.team2_list:
                if chara.template.get("display_name", "") == actor:
                    actor_health = chara.template.get("curHP", 0)
                    break
        elif event == "heal":
            team = kwargs.get("team")
            tag = "P1" if team == 1 else "P2"
            actor = kwargs.get("actor", "")
            target = kwargs.get("target", "")
            action = kwargs.get("action", "")
            amount = kwargs.get("amount", 0)
            cur = kwargs.get("hp_cur", 0)
            max_hp = kwargs.get("hp_max", 0)
            message = (f"{actor} uses \"{action}\" on {target} - +{amount}"
                       f" (HP {cur}/{max_hp})")
            # --- GET ACTOR'S HEALTH FOR HEAL EVENT ---
            for chara in Character.team1_list + Character.team2_list:
                if chara.template.get("display_name", "") == actor:
                    actor_health = chara.template.get("curHP", 0)
                    break
        elif event == "pass":
            team = kwargs.get("team")
            tag = "P1" if team == 1 else "P2"
            message = "Pass turn"
            # For pass events, we don't have a specific unit name, so we leave actor_health as 0.
            actor_health = 0
        elif event == "ko":
            team = kwargs.get("team")
            tag = "P1" if team == 1 else "P2"
            actor = kwargs.get("actor", "")
            location = board_label(kwargs.get("location"))
            hp_max = kwargs.get("hp_max", 0)
            by_actor = kwargs.get("by_actor")
            by_action = kwargs.get("by_action")
            message_parts = [f"{actor} is KO"]
            if location:
                message_parts[-1] += f" at {location}"
            detail_parts: list[str] = []
            if by_actor and by_action:
                detail_parts.append(f"by {by_actor} using \"{by_action}\"")
            elif by_actor:
                detail_parts.append(f"by {by_actor}")
            elif by_action:
                detail_parts.append(f"by \"{by_action}\"")
            if detail_parts:
                message_parts.append(" ".join(detail_parts))
            if hp_max:
                message_parts.append(f"(HP 0/{hp_max})")
            message = " ".join(part for part in message_parts if part)
            # --- SET ACTOR'S HEALTH TO 0 FOR KO EVENT ---
            actor_health = 0
        elif event == "match_over":
            tag = "GAME"
            match_number = kwargs.get("match")
            if match_number is not None:
                match_label = f"Match {match_number} over"
            else:
                match_label = "Match over"
            message = ("{match_label} - {winner} win ({p1}-{p2})".format(
                match_label=match_label,
                winner=kwargs.get("winner", ""),
                p1=kwargs.get("p1_rounds", 0),
                p2=kwargs.get("p2_rounds", 0)
            ))
        elif event == "summary_match":
            tag = "SUMMARY"
            message = ("Match {match}   Map: {map_label}".format(
                match=kwargs.get("match"),
                map_label=kwargs.get("map_label", "")
            ))
        elif event == "summary_result":
            tag = "SUMMARY"
            message = ("Result - P{winner} win ({p1}-{p2})".format(
                winner=kwargs.get("winner", ""),
                p1=kwargs.get("p1_rounds", 0),
                p2=kwargs.get("p2_rounds", 0)
            ))
        elif event == "summary_series":
            tag = "SUMMARY"
            message = ("Series - P1 matches = {p1}   P2 matches = {p2}".format(
                p1=kwargs.get("p1_matches", 0),
                p2=kwargs.get("p2_matches", 0)
            ))
        else:
            message = kwargs.get("message", "")
        label = tag_labels.get(tag, "")
        # --- NEW: Include actor's health in the log entry ---
        # We'll modify the message to include the actor's health.
        # This is a temporary fix; ideally, we would store this data separately.
        if actor_health > 0 and event in ["move", "attack", "heal"]:
            message = f"{message} (Actor HP: {actor_health})"
        time_elapsed = kwargs.get("time_elapsed", 0.0)
        self.log(f"{label}{message}", tag_color(tag), time_elapsed=time_elapsed)

    def _get_ai_label(self, team_id: int) -> str:
        if 0 <= team_id < len(self._ai_type_labels):
            return self._ai_type_labels[team_id]
        return 'Unknown'

    def _log_series_summary(self, total_matches_played: int | None = None) -> None:
        """Append a formatted summary of the overall series to the game log."""
        if self._series_summary_logged:
            return

        calculated_total = self.total_p1_win + self.total_p2_win
        if total_matches_played is None:
            total_matches_played = self.currentMatch
        total_matches_played = max(total_matches_played, calculated_total)

        ai1_name = self._get_ai_label(self.team1_ID)
        ai2_name = self._get_ai_label(self.team2_ID)

        if self.total_p1_win > self.total_p2_win:
            winner = "P1"
        elif self.total_p2_win > self.total_p1_win:
            winner = "P2"
        else:
            winner = "TIE"

        lines = [
            f"GAME : WINNER = {winner}",
            f"GAME : P1 total matches = {self.total_p1_win}   P2 total matches = {self.total_p2_win}",
            f"GAME : Total matches played = {total_matches_played}",
            f"GAME : P1 = {ai1_name}   P2 = {ai2_name}",
            "GAME : SERIES OVER - FINAL RESULT",
            "-------------------------------------"
        ]

        for line in reversed(lines):
            self.log(line, LOG_COLOR_GAME)

        self._series_summary_logged = True

    def _init_character_snapshots(self) -> None:
        self._char_snapshots: dict[int, dict] = {}
        for chara in Character.team1_list + Character.team2_list:
            self._char_snapshots[chara.id] = {
                "grid": chara.grid,
                "hp": chara.template.get("curHP", 0),
                "max_hp": chara.template.get("maxHP", 0),
                "name": chara.template.get("display_name", ""),
                "team": 1 if chara in Character.team1_list else 2
            }

    def _capture_character_state(self) -> dict[int, dict]:
        state: dict[int, dict] = {}
        for chara in Character.team1_list + Character.team2_list:
            state[chara.id] = {
                "grid": chara.grid,
                "hp": chara.template.get("curHP", 0),
                "max_hp": chara.template.get("maxHP", 0),
                "name": chara.template.get("display_name", ""),
                "team": 1 if chara in Character.team1_list else 2
            }
        return state

    def _process_character_movements(self, prev: dict[int, dict], current: dict[int, dict]) -> None:
        for char_id, data in current.items():
            if char_id in prev:
                prev_data = prev[char_id]
                if prev_data["grid"] != data["grid"]:
                    distance = abs(prev_data["grid"][0] - data["grid"][0]) + \
                               abs(prev_data["grid"][1] - data["grid"][1])
                    self.log_event(
                        "move",
                        team=prev_data["team"],
                        actor=data["name"],
                        start=prev_data["grid"],
                        end=data["grid"],
                        distance=distance,
                        actor_hp=prev_data["hp"],
                        time_elapsed=self.cumulative_time
                    )

    def _process_ai_logs(self, prev_state: dict[int, dict], current_state: dict[int, dict]) -> None:
        ai_objects = []
        if hasattr(self.GameMaster, "team1"):
            ai_objects.append(self.GameMaster.team1)
        if hasattr(self.GameMaster, "team2"):
            ai_objects.append(self.GameMaster.team2)
        for ai in ai_objects:
            log = getattr(ai, "action_log", None)
            if not isinstance(log, list):
                continue
            prev_len = self._ai_log_len.get(ai, 0)
            if len(log) > prev_len:
                new_lines = log[prev_len:]
                self._ai_log_len[ai] = len(log)
                # --- FIX: Use object identity to get team ID ---
                if ai is self.GameMaster.team1:
                    team_id = 1
                elif ai is self.GameMaster.team2:
                    team_id = 2
                else:
                    team_id = 0  # fallback
                queue = self._ai_pending_lines.setdefault(team_id, [])
                queue.extend(new_lines)
        # ... rest of the method remains the same ...

        def parse_grid(label: str) -> tuple[int, int] | None:
            if not label:
                return None
            col_char = label[0].lower()
            if not ('a' <= col_char <= 'z'):
                return None
            try:
                row_num = int(label[1:])
            except ValueError:
                return None
            col_idx = ord(col_char) - ord('a')
            row_idx = GRID_ROWS - row_num
            if 0 <= row_idx < GRID_ROWS and 0 <= col_idx < GRID_COLS:
                return (row_idx, col_idx)
            return None

        for team, queue in self._ai_pending_lines.items():
            idx = 0
            while idx < len(queue):
                line = queue[idx]
                if "moves to grid" in line:
                    queue.pop(idx)
                    continue
                if "passes" in line:
                    queue.pop(idx)
                    self.log_event("pass", team=team, time_elapsed=self.cumulative_time)
                    continue
                if "uses" in line:
                    if len(queue) - idx < 3:
                        break
                    first = queue.pop(idx)
                    second = queue.pop(idx)
                    third = queue.pop(idx)
                    actor, _, action_name = first.partition(" uses ")
                    action_name = action_name.strip()
                    target_info = second.replace("Target:", "").strip()
                    grid_label = ''
                    if '(' in target_info and target_info.endswith(')'):
                        grid_label = target_info[target_info.rfind('(') + 1:-1]
                    target_name = target_info.split(" (", 1)[0].strip()
                    amount_str = third.replace("Result:", "").replace("damage", "").strip()
                    try:
                        amount = int(float(amount_str))
                    except ValueError:
                        amount = 0

                    target_id = None
                    target_team = None
                    grid_coords = parse_grid(grid_label)
                    if grid_coords is not None:
                        for cid, data in current_state.items():
                            if data["grid"] == grid_coords:
                                target_id = cid
                                target_team = data.get("team")
                                break
                        if target_id is None:
                            for cid, data in prev_state.items():
                                if data["grid"] == grid_coords:
                                    target_id = cid
                                    target_team = data.get("team")
                                    break
                    if target_id is None:
                        for cid, data in current_state.items():
                            if data["name"] == target_name:
                                target_id = cid
                                target_team = data.get("team")
                                break
                    hp_cur = 0
                    hp_max = 0
                    if target_id is not None:
                        combined = current_state.get(target_id, prev_state.get(target_id, {}))
                        hp_cur = combined.get("hp", 0)
                        hp_max = combined.get("max_hp", 0)
                        target_team = combined.get("team", target_team)
                    else:
                        for cid, data in prev_state.items():
                            if data["name"] == target_name:
                                hp_cur = max(0, data["hp"] - amount)
                                hp_max = data["max_hp"]
                                target_team = data.get("team")
                                break

                    if amount >= 0:
                        hp_before = 0
                        if target_id is not None:
                            # Use previous state's HP as "before"
                            hp_before = prev_state.get(target_id, {}).get("hp", hp_max)
                        else:
                            # Fallback: current HP + damage
                            hp_before = hp_cur + amount

                        self.log_event(
                            "attack",
                            team=team,
                            actor=actor,
                            target=target_name,
                            action=action_name,
                            amount=amount,
                            hp_before=hp_before,
                            hp_cur=hp_cur,
                            hp_max=hp_max,
                            target_position=grid_label,
                            time_elapsed=self.cumulative_time  
                        )
                        if target_id is not None:
                            self._pending_ko_sources[target_id] = {
                                "by_actor": actor,
                                "by_action": action_name
                            }
                        elif target_team is not None:
                            self._pending_ko_sources_by_name[(target_name, target_team)] = {
                                "by_actor": actor,
                                "by_action": action_name
                            }
                    else:
                        self.log_event(
                            "heal",
                            team=team,
                            actor=actor,
                            target=target_name,
                            action=action_name,
                            amount=abs(amount),
                            hp_cur=hp_cur,
                            hp_max=hp_max,
                            time_elapsed=self.cumulative_time
                        )
                    continue
                idx += 1

        # Remove consumed queues to avoid growth
        for team in list(self._ai_pending_lines.keys()):
            if not self._ai_pending_lines[team]:
                del self._ai_pending_lines[team]

    def _process_character_outcomes(self, prev: dict[int, dict], current: dict[int, dict]) -> None:
        for char_id, prev_data in prev.items():
            prev_hp = prev_data.get("hp", 0)
            if prev_hp <= 0:
                continue
            current_data = current.get(char_id)
            ko_detected = False
            location = prev_data.get("grid")
            hp_max = prev_data.get("max_hp", 0)
            if current_data is None:
                ko_detected = True
            else:
                cur_hp = current_data.get("hp", 0)
                if cur_hp <= 0:
                    ko_detected = True
                    location = current_data.get("grid") or location
                    hp_max = current_data.get("max_hp", hp_max)
            if not ko_detected:
                continue
            source = self._pending_ko_sources.pop(char_id, None)
            if source is None:
                key = (prev_data.get("name", ""), prev_data.get("team"))
                source = self._pending_ko_sources_by_name.pop(key, None)
            self.log_event(
                "ko",
                team=prev_data.get("team"),
                actor=prev_data.get("name", ""),
                location=location,
                hp_max=hp_max,
                **(source or {}),
                time_elapsed=self.cumulative_time 
            )
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
        # With chronological order, max_scroll is last possible start index
        max_scroll = max(0, len(self.game_log) - max_lines)

        # Thumb size proportional to visible fraction; enforce a minimum
        if max_scroll == 0:
            thumb_h = track_rect.height
        else:
            visible_fraction = max_lines / max(len(self.game_log), 1)
            thumb_h = max(24, int(track_rect.height * visible_fraction))
            thumb_h = min(thumb_h, track_rect.height)

        # Thumb position maps log_scroll in [0, max_scroll] to y in [track.y, track.bottom - thumb_h]
        if max_scroll == 0:
            thumb_y = track_rect.y
        else:
            t = 0 if max_scroll == 0 else (self.log_scroll / max_scroll)  # 0..1  (0 = top/oldest, 1 = bottom/newest)
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

    def _log_rect(self) -> pygame.Rect:
        """Helper: current log panel rect (same as in render)."""
        return pygame.Rect(LOG_X, LOG_Y, LOG_W, LOG_H)

    # UI hit-test helpers
    def _grid_from_mouse_pos(self, pos: tuple[int, int]) -> tuple[int, int] | None:
        # Translate a mouse position to a (row, col) on the 8x8 board, or None if outside
        if not hasattr(self, 'field'):
            return None
        x, y = pos
        rect = self.field.rect
        if not rect.collidepoint(x, y):
            return None
        row = int((y - rect.y) // self.field.boxes_height)
        col = int((x - rect.x) // self.field.boxes_width)
        # clamp just in case
        row = max(0, min(self.field.rows - 1, row))
        col = max(0, min(self.field.cols - 1, col))
        return (row, col)

    def _action_rects_for_chara(self, chara) -> list[tuple[int, pygame.Rect]]:
        # Return list of (action_index, rect) for the Actions List UI of a character.
        rects: list[tuple[int, pygame.Rect]] = []
        i = 0
        for idx, _ in enumerate(chara.template.get("actions", [])):
            rects.append((idx, pygame.Rect(1000, 88 + i, 220, 150)))
            i += 170
        return rects

    def _extract_field_map_id(self) -> int | None:
        """Return the numeric map id from the current field, if available."""
        if not hasattr(self, 'field') or self.field is None:
            return None

        map_name = getattr(getattr(self.field, 'map', None), 'map_name', '')
        if not map_name:
            return None

        digits = ''.join(ch for ch in str(map_name) if ch.isdigit())
        if digits:
            try:
                return int(digits)
            except ValueError:
                return None
        return None

    def _handle_log_event(self, event: pygame.event.Event, geom: dict) -> bool:
        """Process scroll events for the game log. Returns True if consumed."""
        if event.type == pygame.MOUSEWHEEL:
            if geom["log_rect"].collidepoint(pygame.mouse.get_pos()):
                if event.y > 0:
                    self.log_scroll = max(0, self.log_scroll - self._log_scroll_step * abs(event.y))
                elif event.y < 0:
                    self.log_scroll = min(geom["max_scroll"],
                                          self.log_scroll + self._log_scroll_step * abs(event.y))
                return True

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mx, my = event.pos
            if geom["thumb_rect"].collidepoint(mx, my):
                self._sb_dragging = True
                self._sb_drag_offset_y = my - geom["thumb_rect"].y
                return True
            if geom["track_rect"].collidepoint(mx, my):
                if my < geom["thumb_rect"].y:
                    self.log_scroll = max(0, self.log_scroll - self._log_page_step)
                elif my > geom["thumb_rect"].bottom:
                    self.log_scroll = min(geom["max_scroll"], self.log_scroll + self._log_page_step)
                return True

        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self._sb_dragging:
                self._sb_dragging = False
                return True

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
            return True

        return False

    def _is_endgame_popup_active(self) -> bool:
        return self.game_state in ('win', 'lose')

    def _reset_endgame_hover_states(self) -> None:
        self.endgame_menu_hovered = False
        self.endgame_restart_hovered = False
        self.endgame_export_hovered = False

    def _handle_endgame_event(self, event: pygame.event.Event, geom: dict) -> None:
        if self._handle_log_event(event, geom):
            return

        if event.type == pygame.KEYDOWN:
            # Left/Right to change selection, Z to confirm
            if event.key == pygame.K_LEFT:
                if self._endgame_selected_idx is None:
                    self._endgame_selected_idx = 0
                self._endgame_selected_idx = (self._endgame_selected_idx - 1) % 3
                return
            if event.key == pygame.K_RIGHT:
                if self._endgame_selected_idx is None:
                    self._endgame_selected_idx = 0
                self._endgame_selected_idx = (self._endgame_selected_idx + 1) % 3
                return
            if event.key == pygame.K_z:
                if self._endgame_selected_idx is None:
                    self._endgame_selected_idx = 0
                if self._endgame_selected_idx == 0:
                    self._return_to_menu()
                elif self._endgame_selected_idx == 1:
                    self._restart_match_from_popup()
                else:
                    # Export log not implemented yet
                    pass
                return

            if event.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_r):
                self._restart_match_from_popup()
            elif event.key in (pygame.K_ESCAPE, pygame.K_p):
                self._return_to_menu()
            return

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.endgame_menu_button_rect.collidepoint(event.pos):
                self._return_to_menu()
            elif self.endgame_restart_button_rect.collidepoint(event.pos):
                self._restart_match_from_popup()
            elif self.endgame_export_button_rect.collidepoint(event.pos):
                # Placeholder: export log not implemented yet
                self.export_game_log()

    def _restart_match_from_popup(self) -> None:
        if self.last_team1_ID is None or self.last_team2_ID is None:
            return

        self.team1_ID = self.last_team1_ID
        self.team2_ID = self.last_team2_ID

        if self.last_map_selection_value is not None:
            self.map_number = self.last_map_selection_value

        if self.last_map_was_random and self.last_map_generated_id is not None:
            self._next_map_id_override = self.last_map_generated_id
        else:
            self._next_map_id_override = None

        self.game_state = 'selecting start area'
        self.game_log.clear()
        self._ai_log_len = {}
        self._ai_pending_lines.clear()
        self._pending_ko_sources = {}
        self._pending_ko_sources_by_name = {}
        self.log_scroll = 0
        self.currentMatch = 0
        self.total_p1_win = 0
        self.total_p2_win = 0
        self.p1_round_wins = 0
        self.p2_round_wins = 0
        self._current_map_label = ''
        self._char_snapshots = {}
        self._sb_dragging = False
        self._series_summary_logged = False

        self.startMatch()

    def _return_to_menu(self) -> None:
        self.game_screen = 0
        self.game_state = 'selecting start area'
        self._sb_dragging = False
        self._reset_endgame_hover_states()
        self.pass_turn_button_hovered = False
        self.game_log.clear()
        self._ai_log_len = {}
        self._ai_pending_lines.clear()
        self._pending_ko_sources = {}
        self._pending_ko_sources_by_name = {}
        self.log_scroll = 0
        self.currentMatch = 0
        self.total_p1_win = 0
        self.total_p2_win = 0
        self.p1_round_wins = 0
        self.p2_round_wins = 0
        self._current_map_label = ''
        self._series_summary_logged = False
        self._char_snapshots = {}
        self._next_map_id_override = None
        Cursor.state = 5
        Cursor.selected_action = -1
        if hasattr(self, 'field'):
            Character.removeAllCharacters()

    def _render_endgame_popup(self, geom: dict) -> None:
        overlay = self._endgame_overlay
        overlay.fill((0, 0, 0, 140))
        overlay.fill((0, 0, 0, 0), geom["log_rect"])
        self.screen.blit(overlay, (0, 0))

        pygame.draw.rect(self.screen, (217, 217, 217), self.endgame_popup_rect)
        pygame.draw.rect(self.screen, (0, 0, 0), self.endgame_popup_rect, 2)

        title_text = 'P1 WIN!!' if self.game_state == 'win' else 'P2 WIN!!'
        title_surface = self.font_end_title.render(title_text, False, (0, 0, 0))
        title_rect = title_surface.get_rect(center=(self.endgame_popup_rect.centerx,
                                                   self.endgame_popup_rect.y + 100))
        self.screen.blit(title_surface, title_rect)

        self._draw_endgame_button(self.endgame_menu_button_rect, 'MENU', self.endgame_menu_hovered)
        self._draw_endgame_button(self.endgame_restart_button_rect, 'RESTART', self.endgame_restart_hovered)
        self._draw_endgame_button(self.endgame_export_button_rect, 'EXPORT LOG', self.endgame_export_hovered)

        # Yellow highlight for endgame button
        if self._endgame_selected_idx is not None:
            selected_rect = [
                self.endgame_menu_button_rect,
                self.endgame_restart_button_rect,
                self.endgame_export_button_rect,
            ][self._endgame_selected_idx]
            pygame.draw.rect(self.screen, YELLOW, selected_rect, 4)

    def _model_modal_geometry(self):
        """Rects used by the Model Select popup."""
        modal_rect = pygame.Rect(220, 140, 800, 460)
        list_rect  = pygame.Rect(modal_rect.x + 40, modal_rect.y + 80, 380, 300)
        confirm_btn = pygame.Rect(modal_rect.right - 200, modal_rect.bottom - 70, 160, 40)
        return modal_rect, list_rect, confirm_btn

    def _render_model_modal(self):
        """Draw the Model Select popup."""
        mask = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        mask.fill((0, 0, 0, 120))
        self.screen.blit(mask, (0, 0))

        modal_rect, list_rect, confirm_btn = self._model_modal_geometry()
        pygame.draw.rect(self.screen, (245, 238, 228), modal_rect, border_radius=10)
        pygame.draw.rect(self.screen, (30, 30, 30), modal_rect, 3, border_radius=10)

        title = self.font_m.render(f"Select Model for P{self._model_modal_for}", False, (0, 0, 0))
        self.screen.blit(title, title.get_rect(midtop=(modal_rect.centerx, modal_rect.y + 12)))

        mouse_pos = pygame.mouse.get_pos()
        self._model_hover = -1
        item_h = 44
        gap = 10
        top_y = list_rect.y
        for i, name in enumerate(AI_SELECTION_LABELS):
            r = pygame.Rect(list_rect.x, top_y + i*(item_h + gap), list_rect.w, item_h)
            hovered = r.collidepoint(mouse_pos)
            if self._model_modal_for == 1:
                selected = (self.p1_model_index == i)
            else:
                selected = (self.p2_model_index == i)
            if hovered:
                self._model_hover = i
            self._draw_button(r, name, hovered, selected)

        hovered = confirm_btn.collidepoint(mouse_pos)
        self._draw_button(confirm_btn, "SELECT", hovered, ok=True)
         

    def _draw_endgame_button(self, rect: pygame.Rect, text: str, hovered: bool) -> None:
        fill_color = (255, 255, 255)
        border_color = (0, 0, 0)
        if hovered:
            fill_color = (245, 245, 245)
            border_color = (60, 60, 60)

        pygame.draw.rect(self.screen, fill_color, rect)
        pygame.draw.rect(self.screen, border_color, rect, 2)

        label = self.font_end_button.render(text, False, (0, 0, 0))
        label_rect = label.get_rect(center=rect.center)
        self.screen.blit(label, label_rect)

    # Pause button available when one side is player input
    def _is_pause_button_available(self) -> bool:
        p1_human = self.team1_ID == 0
        p2_human = self.team2_ID == 0
        return p1_human or p2_human

    def _is_pause_popup_active(self) -> bool:
        return self._pause_active and not self._is_endgame_popup_active()

    def _reset_pause_hover_states(self) -> None:
        self.pause_resume_hovered = False
        self.pause_restart_hovered = False
        self.pause_menu_hovered = False

    def _handle_pause_event(self, event: pygame.event.Event, geom: dict) -> None:
        # Allow scrolling the log while paused
        if self._handle_log_event(event, geom):
            return

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                # Resume game
                self._pause_active = False
                self._reset_pause_hover_states()
            elif event.key == pygame.K_LEFT:
                self._pause_selected_idx = (self._pause_selected_idx - 1) % 3
            elif event.key == pygame.K_RIGHT:
                self._pause_selected_idx = (self._pause_selected_idx + 1) % 3
            elif event.key == pygame.K_z:
                if self._pause_selected_idx == 0:  # Resume
                    self._pause_active = False
                    self._reset_pause_hover_states()
                elif self._pause_selected_idx == 1:  # Restart
                    self._pause_active = False
                    self._reset_pause_hover_states()
                    self._restart_match_from_popup()
                elif self._pause_selected_idx == 2:  # Menu
                    self._pause_active = False
                    self._reset_pause_hover_states()
                    self._return_to_menu()
            return

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.pause_resume_button_rect.collidepoint(event.pos):
                self._pause_active = False
                self._reset_pause_hover_states()
            elif self.pause_restart_button_rect.collidepoint(event.pos):
                self._pause_active = False
                self._reset_pause_hover_states()
                self._restart_match_from_popup()
            elif self.pause_menu_button_rect.collidepoint(event.pos):
                self._pause_active = False
                self._reset_pause_hover_states()
                self._return_to_menu()

    def _render_pause_popup(self, geom: dict) -> None:
        # Dim background, same as endgame, but keep log area transparent
        overlay = self._endgame_overlay
        overlay.fill((0, 0, 0, 140))
        overlay.fill((0, 0, 0, 0), geom["log_rect"])
        self.screen.blit(overlay, (0, 0))

        pygame.draw.rect(self.screen, (217, 217, 217), self.pause_popup_rect)
        pygame.draw.rect(self.screen, (0, 0, 0), self.pause_popup_rect, 2)

        title_surface = self.font_end_title.render('PAUSED', False, (0, 0, 0))
        title_rect = title_surface.get_rect(center=(self.pause_popup_rect.centerx,
                                                   self.pause_popup_rect.y + 100))
        self.screen.blit(title_surface, title_rect)

        self._draw_endgame_button(self.pause_resume_button_rect, 'RESUME', self.pause_resume_hovered)
        self._draw_endgame_button(self.pause_restart_button_rect, 'RESTART', self.pause_restart_hovered)
        self._draw_endgame_button(self.pause_menu_button_rect, 'MENU', self.pause_menu_hovered)

        # Yellow highlight for endgame button
        selected_rect = [
            self.pause_resume_button_rect,
            self.pause_restart_button_rect,
            self.pause_menu_button_rect,
        ][self._pause_selected_idx]
        pygame.draw.rect(self.screen, YELLOW, selected_rect, 4)
    def screen1init(self):

        self.match_limit = max(self._match_limit_min, min(self._match_limit_max, self.match_limit))

        AI_types = ('Player Input', 'Perfect Play AI', 'Random AI', 'Personality Cores AI', 'Disable AI') # not 'Independent Action AI' anymore
        self.team1_ID = self.p1_sel_cursor.grid[0]
        self.team2_ID = self.p2_sel_cursor.grid[0]
        print(f'{AI_types[self.team1_ID]} vs {AI_types[self.team2_ID]}')

        self.currentMatch = 0
        self.total_p1_win = 0
        self.total_p2_win = 0
        self._series_summary_logged = False

        self.startMatch()
        

        # if self.p2_sel_cursor.grid[0] == 0:
        #     self.AI = AI.Random(team=2)
        #     print('Random AI!')
        # else:
        #     self.AI = AI.PerfectPlay(team=1)
        #     print('Perfect AI!')

        ### CHOOSE AI TYPE HERE
        # self.AI = AI.Random()
        # self.AI = AI.PerfectPlay()
        ###

        self.game_screen = 1

    def startMatch(self) -> None:
        self.currentMatch += 1
        self.cumulative_time = 0.0  

        self._ai_log_len = {}
        self._ai_pending_lines.clear()
        self._pending_ko_sources = {}
        self._pending_ko_sources_by_name = {}
        self.p1_round_wins = 0
        self.p2_round_wins = 0

        ai1_name = self._get_ai_label(self.team1_ID)
        ai2_name = self._get_ai_label(self.team2_ID)

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
            self._log_series_summary(total_matches_played=self.total_p1_win + self.total_p2_win)
            return

        map_override = self._next_map_id_override
        self._next_map_id_override = None

        if map_override is not None:
            self.field = Field(self.screen,
                               (BOARD_POS_X, BOARD_POS_Y),
                               (8, 8),
                               (640, 640),
                               rand_map=False,
                               map_id=map_override)
        elif self.map_number == len(self.map_list):
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

        self.last_team1_ID = self.team1_ID
        self.last_team2_ID = self.team2_ID
        self.last_map_selection_value = self.map_number

        if map_override is not None:
            actual_map_id = map_override
            map_was_random = True
        elif self.map_number == len(self.map_list):
            actual_map_id = self._extract_field_map_id()
            map_was_random = True
        else:
            actual_map_id = self.map_number
            map_was_random = False

        self.last_map_generated_id = actual_map_id
        self.last_map_was_random = map_was_random

        self.field.positionCursorOnTeam1Character()
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

        if self.isAuto:
            self.action_delay = 0
        else:
            self.action_delay = 0.8

        map_label = str(getattr(getattr(self.field, 'map', None), 'map_name', ''))
        if not map_label:
            map_label = 'Unknown'
        self._current_map_label = map_label

        # ✅ Log match start with time_elapsed = 0.0 (since match just began)
        self.log_event('match_start',
                       match=self.currentMatch,
                       map_label=map_label,
                       ai1=ai1_name,
                       ai2=ai2_name,
                       time_elapsed=self.cumulative_time)

        # ✅ Log round begin with time_elapsed = 0.0
        self.log_event('round_begin',
                       round=self.round,
                       time_elapsed=self.cumulative_time)

        self._init_character_snapshots()
        self.log_scroll = 0


    def update(self, dt: float, events: list[pygame.event.Event]) -> None:
        # Normalize event coordinates to base space so hit-tests still work when scaled
        events = self._scale_events_to_base(list(events))
        if self.game_screen == -1:      # Start screen
            # Reposition Laptop/Macbook button to be under the "X / Right Click : Cancel" text
            cancel_text_h = self.font_s.size("X / Right Click : Cancel")[1]
            self.laptop_button_rect.topleft = (290, 667 + cancel_text_h + 30)
            mouse_pos = pygame.mouse.get_pos()
            self.play_button_hovered = self.play_button_rect.collidepoint(mouse_pos)
            self.laptop_button_hovered = self.laptop_button_rect.collidepoint(mouse_pos)

            for event in events:
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_RETURN or event.key == pygame.K_SPACE:
                        self.game_screen = 0  # Go to AI selection screen
                                # --- ESC quits only on start menu ---
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        pygame.quit()
                        sys.exit()
                if event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == 1 and self.play_button_hovered:  # Left click on play button
                        self.game_screen = 0  # Go to AI selection screen
                    # Apply laptop scaling when clicking the Laptop/Macbook button
                    if event.button == 1 and self.laptop_button_rect.collidepoint(event.pos):
                        # Toggle: if currently scaled down, restore to 1.0; otherwise scale for laptop
                        if self.scale < 0.99:
                            self._apply_scale(1.0)
                        else:
                            self._apply_scale(self._scale_for_laptop())

        elif self.game_screen == 0:       # AI select screen
            if not self._map_popup_open:
                self._map_popup_temp_selection = self._clamp_map_index(self.map_number)
                self._map_popup_hover_index = None

            for event in events:
                # --- Window close ---
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                if self._map_popup_open:
                    if self._handle_map_popup_event(event):
                        continue
                    if event.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP, pygame.MOUSEMOTION, pygame.KEYDOWN):
                        continue
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_RETURN:
                        if self.p1_sel_cursor.show and self.p2_sel_cursor.show:
                            self.screen1init()
            # ESC exits the app on AI-select page
                    if event.key == pygame.K_ESCAPE:
                        pygame.quit()
                        sys.exit()
            

                    # Arrow keys move the hover menu cursor
                    elif event.key in (pygame.K_UP, pygame.K_DOWN, pygame.K_LEFT, pygame.K_RIGHT):
                        self.menu_cursor.moveBy(event.key)

                    # Z to confirm selection into the column you're on
                    elif event.key == pygame.K_z:
                        # menu_cursor.grid == (row_index, col_index) where col 0 = P1, col 1 = P2
                        row, col = self.menu_cursor.grid
                        if col == 0:
                            self.p1_sel_cursor.moveTo((row, 0))
                            self.p1_sel_cursor.show = True
                        elif col == 1:
                            self.p2_sel_cursor.moveTo((row, 1))
                            self.p2_sel_cursor.show = True

                    # A toggles auto mode
                    elif event.key == pygame.K_a:
                        self.isAuto = not self.isAuto

                    # M cycles map index
                    elif event.key == pygame.K_m:
                        self.map_number += 1
                        if self.map_number > len(self.map_list):
                            self.map_number = 0
                if event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == 1 and (self._map_select_button_rect.collidepoint(event.pos) or self._map_preview_thumb_rect.collidepoint(event.pos)):
                        self._map_popup_open = True
                        self._map_popup_temp_selection = self._clamp_map_index(self.map_number)
                        self._map_popup_hover_index = None
                        self._map_popup_select_hovered = False
                        # cancel any active dragging
                        self._match_limit_slider_dragging = False
                        self._game_limit_slider_dragging = False
                        continue
                    # Game slider (higher on UI)
                    if event.button == 1 and hasattr(self, "_game_limit_slider_rect") and self._game_limit_slider_rect.collidepoint(event.pos):
                        self._game_limit_slider_dragging = True
                        if hasattr(self, "_game_limit_value_from_pos"):
                            self.game_limit = self._game_limit_value_from_pos(event.pos[0])
                        continue
                    # Match slider
                    if event.button == 1 and hasattr(self, "_match_limit_slider_rect") and self._match_limit_slider_rect.collidepoint(event.pos):
                        self._match_limit_slider_dragging = True
                        if hasattr(self, "_match_limit_value_from_pos"):
                            self.match_limit = self._match_limit_value_from_pos(event.pos[0])
                if event.type == pygame.MOUSEBUTTONUP:
                    if event.button == 1:
                        if hasattr(self, "_match_limit_slider_dragging") and self._match_limit_slider_dragging:
                            self._match_limit_slider_dragging = False
                        if hasattr(self, "_game_limit_slider_dragging") and self._game_limit_slider_dragging:
                            self._game_limit_slider_dragging = False
                if event.type == pygame.MOUSEMOTION:
                    if hasattr(self, "_game_limit_slider_dragging") and self._game_limit_slider_dragging:
                        if hasattr(self, "_game_limit_value_from_pos"):
                            self.game_limit = self._game_limit_value_from_pos(event.pos[0])
                    elif hasattr(self, "_match_limit_slider_dragging") and self._match_limit_slider_dragging:
                        if hasattr(self, "_match_limit_value_from_pos"):
                            self.match_limit = self._match_limit_value_from_pos(event.pos[0])

                # Mouse: make all 10 AI type buttons clickable
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    mx, my = event.pos
                    # Left column (Player 1)
                    left_x = WIDTH // 4 - 210
                    for i in range(5):
                        rect = pygame.Rect(left_x, 200 + i * 90, 420, 60)
                        if rect.collidepoint(mx, my):
                            # Select AI for Player 1
                            self.p1_sel_cursor.moveTo((i, 0))
                            self.p1_sel_cursor.show = True
                            # Move the yellow menu cursor to the clicked button (left column)
                            self.menu_cursor.moveTo((i, 0))
                            break

                # --- Mouse: left button down (slider OR AI buttons) ---
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    mx, my = event.pos

                    # 1) Match-limit slider grab (guarded so it won't crash if rect/helper missing)
                    if hasattr(self, "_match_limit_slider_rect") and self._match_limit_slider_rect.collidepoint(mx, my):
                        self._match_limit_slider_dragging = True
                        if hasattr(self, "_match_limit_value_from_pos"):
                            self.match_limit = self._match_limit_value_from_pos(mx)

                    else:
                        # 2) Clickable AI choices (both columns)
                        y0, h_gap = 200, 90
                        btn_w, btn_h = 420, 60

                        # Left column (Player 1)
                        left_x = WIDTH // 4 - 210
                        for i in range(5):
                            rect = pygame.Rect(left_x, y0 + i * h_gap, btn_w, btn_h)
                            if rect.collidepoint(mx, my):
                                self.p1_sel_cursor.moveTo((i, 0))
                                self.p1_sel_cursor.show = True
                                self.menu_cursor.moveTo((i, 0))
                                break
                        else:
                            # Right column (Player 2) — only checked if left column wasn't clicked
                            right_x = WIDTH // 2 + WIDTH // 4 - 210
                            for i in range(5):
                                rect = pygame.Rect(right_x, y0 + i * h_gap, btn_w, btn_h)
                                if rect.collidepoint(mx, my):
                                    self.p2_sel_cursor.moveTo((i, 1))
                                    self.p2_sel_cursor.show = True
                                    self.menu_cursor.moveTo((i, 1))
                                    break
                
                # --- Model Select Button ---
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    mx, my = event.pos                    
                    # Model select buttons (below AI choices)
                    p1_model_rect = pygame.Rect(WIDTH // 4 - 125, 650, 250, 50)
                    p2_model_rect = pygame.Rect(WIDTH * 3 // 4 - 125, 650, 250, 50)
                    # Player 1 Model Button
                    if p1_model_rect.collidepoint(mx, my):
                        self._model_modal_for = 1
                        self._show_model_modal = True   # ✅ use your existing variable name
                    # Player 2 Model Button
                    elif p2_model_rect.collidepoint(mx, my):
                        self._model_modal_for = 2
                        self._show_model_modal = True   # ✅ use the same variable
    

                # --- Mouse: left button up (release slider) ---
                elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                    if hasattr(self, "_match_limit_slider_dragging") and self._match_limit_slider_dragging:
                        self._match_limit_slider_dragging = False

                # --- Mouse: move (while dragging slider) ---
                elif event.type == pygame.MOUSEMOTION:
                    if hasattr(self, "_match_limit_slider_dragging") and self._match_limit_slider_dragging:
                        if hasattr(self, "_match_limit_value_from_pos"):
                            self.match_limit = self._match_limit_value_from_pos(event.pos[0])


        elif self.game_screen == 1:
            self.cumulative_time += dt
            geom = self._calc_log_geometry()
            self._sb_last_geometry = geom

            endgame_active = self._is_endgame_popup_active()
            pause_active = self._is_pause_popup_active()
            # Initialize endgame selection the frame it becomes active
            if endgame_active and not self._prev_endgame_active:
                self._endgame_selected_idx = None
            self._prev_endgame_active = endgame_active

            mouse_pos = pygame.mouse.get_pos()
            show_pause_button = self._is_pause_button_available()
            if endgame_active:
                self.pass_turn_button_hovered = False
                self.pause_game_button_hovered = False
                self.endgame_menu_hovered = self.endgame_menu_button_rect.collidepoint(mouse_pos)
                self.endgame_restart_hovered = self.endgame_restart_button_rect.collidepoint(mouse_pos)
                self.endgame_export_hovered = self.endgame_export_button_rect.collidepoint(mouse_pos)
                self._reset_pause_hover_states()
            elif pause_active:
                self.pass_turn_button_hovered = False
                self.pause_game_button_hovered = False
                self.pause_resume_hovered = self.pause_resume_button_rect.collidepoint(mouse_pos)
                self.pause_restart_hovered = self.pause_restart_button_rect.collidepoint(mouse_pos)
                self.pause_menu_hovered = self.pause_menu_button_rect.collidepoint(mouse_pos)
                self._reset_endgame_hover_states()
            else:
                self.pass_turn_button_hovered = self.pass_turn_button_rect.collidepoint(mouse_pos)
                self.pause_game_button_hovered = (show_pause_button and self.pause_game_button_rect.collidepoint(mouse_pos))
                self._reset_endgame_hover_states()
                self._reset_pause_hover_states()

            for event in events:
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()

                if endgame_active:
                    self._handle_endgame_event(event, geom)
                    continue

                if pause_active:
                    self._handle_pause_event(event, geom)
                    continue

                if self._handle_log_event(event, geom):
                    continue

                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_1:
                        self.action_delay = 0.1
                    elif event.key == pygame.K_2:
                        self.action_delay = 0.4
                    elif event.key == pygame.K_3:
                        self.action_delay = 0.8
                    elif event.key in [pygame.K_UP, pygame.K_DOWN, pygame.K_LEFT, pygame.K_RIGHT, pygame.K_z, pygame.K_x]:
                        self.GameMaster.keyInput(event.key)
                    elif event.key == pygame.K_ESCAPE:
                        # Open pause only when human is active and not in endgame
                        if self.GameMaster.isActiveAIHuman() and not endgame_active:
                            self._pause_active = True
                            self._pause_selected_idx = 0
                    elif event.key == pygame.K_p:
                        if self.GameMaster.isActiveAIHuman():
                            self.GameMaster.activeAI.turnFinished = True
                            self.log_event('pass', team=getattr(self.GameMaster.activeAI, 'team', 1), time_elapsed=self.cumulative_time)
                            Cursor.state = 0
                            self.field.select_cursor.show = False
                            self.field.hover_cursor.show = True
                    continue

                if event.type == pygame.MOUSEBUTTONDOWN:
                    # Right-click (cancel) for human player, mirrors X key behavior
                    if event.button == 3 and self.GameMaster.isActiveAIHuman():
                        if Cursor.state == 1:
                            # Cancel movement selection
                            self.field.clearMovement()
                            Cursor.state = 0
                            continue
                        elif Cursor.state == 2:
                            # Close action menu
                            self.field.hover_cursor.show = True
                            Cursor.selected_action = -1
                            self.field.select_cursor.show = False
                            Cursor.state = 0
                            continue
                        elif Cursor.state == 3:
                            # Close enemy movement preview
                            self.field.select_cursor.show = False
                            self.field.clearMovement()
                            Cursor.state = 0
                            continue
                        elif Cursor.state == 4:
                            # Exit targeting, back to action menu
                            self.field.hover_cursor.show = False
                            Cursor.state = 2
                            for i in range(self.field.rows):
                                for j in range(self.field.cols):
                                    self.field.boxes[i][j].selected_red = False
                            continue

                    if event.button == 1 and self.GameMaster.isActiveAIHuman():
                        # 0) Pause button
                        if self._is_pause_button_available() and self.pause_game_button_rect.collidepoint(event.pos):
                            self._pause_active = True
                            self._pause_selected_idx = 0
                            continue
                        # 1) Pass-turn button
                        if self.pass_turn_button_rect.collidepoint(event.pos):
                            self.GameMaster.activeAI.turnFinished = True
                            self.log_event('pass', team=getattr(self.GameMaster.activeAI, 'team', 1), time_elapsed=self.cumulative_time)
                            Cursor.state = 0
                            self.field.select_cursor.show = False
                            self.field.hover_cursor.show = True
                            continue

                        # 2) Actions panel click (only when in action menu state and a unit is selected)
                        if Cursor.state == 2:
                            chara = self.field.select_cursor.getChara()
                            if chara is not None:
                                for idx, r in self._action_rects_for_chara(chara):
                                    if r.collidepoint(event.pos):
                                        # Choose this action and go to targeting
                                        Cursor.selected_action = idx
                                        Cursor.state = 4
                                        self.field.hover_cursor.show = True
                                        self.field.getActionArea(chara, idx)
                                        break

                        # 3) Board click: move hover to tile and act based on current state
                        grid = self._grid_from_mouse_pos(event.pos)
                        if grid is not None:
                            # Move hover cursor to the clicked tile first
                            self.field.hover_cursor.moveTo(grid)

                            # State machine similar to PlayerInput.receiveInput for KEYZ
                            if Cursor.state == 0:
                                # Try selecting a character at this tile
                                chara = Character.getCharacterByGrid(grid)
                                if chara is not None and not chara.acted:
                                    self.field.select_cursor.moveTo(grid)
                                    self.field.select_cursor.show = True
                                    if chara in Character.team1_list:
                                        if chara.moved:
                                            Cursor.state = 2
                                            Cursor.selected_action = 0
                                            self.field.hover_cursor.show = False
                                        else:
                                            Cursor.state = 1
                                            self.field.getMovement(chara)
                                    else:
                                        # enemy unit: show its movement preview and block actions
                                        Cursor.state = 3
                                        self.field.getMovement(chara)

                            elif Cursor.state == 1:
                                # Confirm movement if tile is allowed
                                box = self.field.boxes[grid[0]][grid[1]]
                                if getattr(box, 'selected', False):
                                    chara = self.field.select_cursor.getChara()
                                    if chara is not None:
                                        chara.moveTo(grid)
                                    self.field.clearMovement()
                                    Cursor.state = 0

                            elif Cursor.state == 4:
                                # Choose target for the selected action
                                box = self.field.boxes[grid[0]][grid[1]]
                                if getattr(box, 'selected_red', False):
                                    chara = self.field.select_cursor.getChara()
                                    target = self.field.hover_cursor.getChara()
                                    if (chara is not None and chara in Character.team1_list) and \
                                       (target is not None and target in Character.team2_list):
                                        if self.field.boxes[target.grid[0]][target.grid[1]].terrain == 1:
                                            modifier = -2
                                        else:
                                            modifier = 0
                                        # Execute via the active human AI to keep logs/flags consistent
                                        self.GameMaster.activeAI.useCharaAction(chara, target, Cursor.selected_action, modifier)
                                        # Reset visuals and state (match keyboard path)
                                        self.field.select_cursor.show = False
                                        Cursor.selected_action = -1
                                        for i in range(self.field.rows):
                                            for j in range(self.field.cols):
                                                self.field.boxes[i][j].selected_red = False
                                        Cursor.state = 0
                                        # Update end-of-turn check for human AI
                                        self.GameMaster.activeAI.turnFinished = self.GameMaster.activeAI.checkCharaActed()
                
                # if event.type == pygame.KEYDOWN:
                #     if event.key == pygame.K_p and Cursor.state != 5 and Cursor.state != 6 and self.game_state == 'attacking phase':
                #         for chara in Character.team1_list:
                #             chara.moved = True
                #             chara.acted = True
                #     # if Cursor.state != 2 and self.game_state != 'enemy action' and self.game_state != 'win':
                #     #     if event.key == pygame.K_UP:
                #     #         self.field.hover_cursor.sel_row -= 1
                #     #     if event.key == pygame.K_DOWN:
                #     #         self.field.hover_cursor.sel_row += 1
                #     #     if event.key == pygame.K_LEFT:
                #     #         self.field.hover_cursor.sel_col -= 1
                #     #     if event.key == pygame.K_RIGHT:
                #     #         self.field.hover_cursor.sel_col += 1

                #     # if self.field.hover_cursor.sel_col < 0:
                #     #     self.field.hover_cursor.sel_col = self.field.cols - 1
                #     # if self.field.hover_cursor.sel_row < 0:
                #     #     self.field.hover_cursor.sel_row = self.field.rows - 1
                #     # if self.field.hover_cursor.sel_col == self.field.cols:
                #     #     self.field.hover_cursor.sel_col = 0
                #     # if self.field.hover_cursor.sel_row == self.field.rows:
                #     #     self.field.hover_cursor.sel_row = 0

                #     if Cursor.state == 0:  # Cursor state 0 start here
                #         if event.key == pygame.K_z:
                #             if self.field.select_cursor.getChara() is None:  # No Character is selected  (This happpens first)
                #                 for chara in Character.team1_list + Character.team2_list:
                #                     if self.field.hover_cursor.grid == chara.grid:
                #                         if chara.acted:
                #                             pass
                #                         else:
                #                             self.field.select_cursor.moveTo(self.field.hover_cursor.grid)
                #                             self.field.select_cursor.show = True
                #                             if self.field.select_cursor.getChara() in Character.team1_list:
                #                                 if chara.moved:
                #                                     Cursor.state = 2
                #                                     Cursor.selected_action = 0
                #                                     self.field.hover_cursor.show = False
                #                                 else:
                #                                     Cursor.state = 1
                #                                     self.field.getMovement(chara)

                #                             else:  # Enemy
                #                                 Cursor.state = 3
                #                                 self.field.getMovement(chara)
                #                             break
                #     elif Cursor.state == 1:  # Cursor state 1 start here -- MOVEMENT
                #         if event.key == pygame.K_z:
                #             if self.field.boxes[self.field.hover_cursor.grid[0]][self.field.hover_cursor.grid[1]].selected:
                #                 chara = self.field.select_cursor.getChara()
                #                 if chara is not None:
                #                     chara.moveTo(self.field.hover_cursor.grid)
                #                 self.field.clearMovement()
                #                 Cursor.state = 0

                #             # if self.field.hover_cursor.getChara() is not None:
                #             #     if self.field.hover_cursor.getChara() == self.field.select_cursor.getChara():
                #             #         self.field.select_cursor.getChara().moved = True
                #             #         self.field.clearMovement()
                #             #         Cursor.state = 0
                #             # else:
                #             #     if self.field.boxes[self.field.hover_cursor.grid[0]][self.field.hover_cursor.grid[1]].selected:
                #             #         chara = self.field.select_cursor.getChara()
                #             #         chara.moveTo((self.field.hover_cursor.sel_row, self.field.hover_cursor.sel_col))
                #             #         # chara.row = self.field.hover_cursor.sel_row
                #             #         # chara.col = self.field.hover_cursor.sel_col
                #             #         chara.moved = True
                #             #         self.field.clearMovement()
                #             #         Cursor.state = 0
                #         if event.key == pygame.K_x:
                #             self.field.clearMovement()
                #             Cursor.state = 0
                #     elif Cursor.state == 2:  # Cursor state 2 start here
                #         if event.key == pygame.K_UP:
                #             Cursor.selected_action -= 1
                #         if event.key == pygame.K_DOWN:
                #             Cursor.selected_action += 1
                #         if Cursor.selected_action > len(self.field.select_cursor.getChara().template['actions']):
                #             Cursor.selected_action = 0
                #         if Cursor.selected_action < 0:
                #             Cursor.selected_action = len(self.field.select_cursor.getChara().template['actions'])

                #         if event.key == pygame.K_z:
                #             self.field.hover_cursor.moveTo(self.field.select_cursor.grid)
                #             self.field.hover_cursor.show = True
                #             chara = self.field.select_cursor.getChara()
                #             if Cursor.selected_action == len(chara.template['actions']):
                #                 chara.acted = True
                #                 Cursor.selected_action = -1
                #                 self.field.hover_cursor.show = True
                #                 self.field.select_cursor.show = False
                #                 Cursor.state = 0
                #             else:
                #                 Cursor.state = 4
                #                 self.field.getActionArea(chara, Cursor.selected_action)
                #         if event.key == pygame.K_x:
                #             self.field.hover_cursor.moveTo(self.field.select_cursor.grid)
                #             Cursor.selected_action = -1
                #             self.field.hover_cursor.show = True
                #             self.field.select_cursor.show = False
                #             Cursor.state = 0
                #     elif Cursor.state == 3:  # Cursor state 3 start here
                #         if event.key == pygame.K_x:
                #             self.field.select_cursor.show = False
                #             self.field.clearMovement()
                #             Cursor.state = 0
                #     elif Cursor.state == 4:  # Cursor state 4 start here
                #         if event.key == pygame.K_z:
                #             if self.field.boxes[self.field.hover_cursor.grid[0]][self.field.hover_cursor.grid[1]].selected_red:
                #                 chara = self.field.select_cursor.getChara()
                #                 if chara is not None:
                #                     match chara.template["actions"][Cursor.selected_action]["action_type"]:
                #                         case "Attack":
                #                             target = self.field.hover_cursor.getChara()
                #                             if target in Character.team2_list:
                #                                 if self.field.boxes[target.grid[0]][target.grid[1]].terrain == 1:
                #                                     chara.attack(target, Cursor.selected_action, -2)
                #                                 else:
                #                                     chara.attack(target, Cursor.selected_action)
                #                                 # if self.field.boxes[target.row][target.col].terrain == 1:
                #                                 #     target.template['curHP'] -= max(0, chara.template["actions"][
                #                                 #         Cursor.selected_action]["damage"] - 2)
                #                                 # else:
                #                                 #     target.template['curHP'] -= chara.template["actions"][Cursor.selected_action][
                #                                 #         "damage"]
                #                                 # if target.template['curHP'] <= 0:
                #                                 #     target.alive = False
                #                                 #     Character.enemy_list.remove(target)
                #                                 chara.acted = True
                #                                 self.field.select_cursor.show = False
                #                                 Cursor.selected_action = -1
                #                                 for i in range(self.field.rows):
                #                                     for j in range(self.field.cols):
                #                                         self.field.boxes[i][j].selected_red = False
                #                                 Cursor.state = 0
                #                         case "Heal":
                #                             # TODO: May add healing in the future
                #                             target = self.field.hover_cursor.getChara()
                #                             if target in Character.team1_list:
                #                                 heal_amount = random.randint(5, 10)
                #                                 target.template['curHP'] = min(target.template['curHP'] + heal_amount, target.template['maxHP'])

                #                                 chara.acted = True
                #                                 self.field.select_cursor.show = False
                #                                 Cursor.selected_action = -1

                #                                 for i in range(self.field.rows):
                #                                     for j in range(self.field.cols):
                #                                         self.field.boxes[i][j].selected_red = False
                #                                 Cursor.state = 0
                #         if event.key == pygame.K_x:
                #             self.field.hover_cursor.show = False
                #             Cursor.state = 2
                #             for i in range(self.field.rows):
                #                 for j in range(self.field.cols):
                #                     self.field.boxes[i][j].selected_red = False
                #     elif Cursor.state == 5:  # Cursor state 5 start here
                #         if event.key == pygame.K_z:
                #             if not self.field.select_cursor.getChara():  # No Character is selected  (This happpens first)
                #                 if self.field.hover_cursor.getChara() is not None:
                #                     self.field.select_cursor.moveTo(self.field.hover_cursor.grid)
                #                     self.field.select_cursor.show = True
                #                     # self.showMovement(self.field.select_cursor.getChara())
                #                     if self.field.select_cursor.getChara() in Character.team2_list:
                #                         Cursor.state = 6
                #                     break
                #             else:  # There is already a Character selected earlier
                #                 if self.field.select_cursor.getChara() in Character.team1_list and self.field.hover_cursor.grid in self.field.player_spawns:
                #                     selectedChara = self.field.select_cursor.getChara()
                #                     hoveredChara = self.field.hover_cursor.getChara()
                #                     if hoveredChara is not None:
                #                         hoveredChara.moveTo(self.field.select_cursor.getChara().grid, update=False)
                #                     selectedChara.moveTo(self.field.hover_cursor.grid, update=False)
                #                     self.field.select_cursor.show = False
                #                     self.field.clearMovement()
                #         if event.key == pygame.K_x:
                #             if self.field.select_cursor.getChara():
                #                 self.field.clearMovement()
                #             else:
                #                 Cursor.state = 0
                #                 self.field.select_cursor.show = False
                #                 self.field.clearSpawns()
                #                 self.game_state = 'show round'
                #     elif Cursor.state == 6:  # Cursor state 6 start here
                #         if event.key == pygame.K_x:
                #             Cursor.state = 5
                #             self.field.clearMovement()
                #     else:
                #         # For Debugging
                #         if event.key == pygame.K_z:
                #             self.field.select_cursor.show = True
                #             self.field.select_cursor.moveTo(self.field.hover_cursor.grid)
                #         if event.key == pygame.K_x:
                #             self.field.select_cursor.show = False

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
                # if self.game_state == 'selecting start area':;
                # for i, pos in enumerate(self.field.player_spawns[:3]):
                #     Character(self.screen,
                #                 (self.field.boxes_width, self.field.boxes_height),
                #                 (pos[0], pos[1]),
                #                 "player" + str(i + 1), type="player")
                # # Incomprehensible Horror
                # for i, pos in enumerate(self.field.enemy_spawns):
                #     Character(self.screen,
                #                 (self.field.boxes_width, self.field.boxes_height),
                #                 (pos[0], pos[1]),
                #                 random.choice(ENEMY_NAMES), type="enemy")

                    # self.game_state = 'selecting start position'

                Cursor.state = 0
                self.game_state = 'enemy action'
            else:
                pass


            # player_acted = [chara.acted for chara in Character.team1_list]
            # # enemy_acted = [enemy.acted for enemy in Character.enemy_list]
            # if all(player_acted) and not self.AI.ready:
            #     self.AI.calculate()
            #     self.game_state = 'enemy action'
            #     Cursor.state = 0
            #     self.field.hover_cursor.show = False
            #     # if all(enemy_acted) or self.enemy_number_action > len(Character.enemy_list) + 1:


            # if self.game_state == 'enemy action' and self.AI.ready:

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
                    # self.game_state = 'finish enemy action'

                    if self.GameMaster.roundFinished:
                        self.log_event('round_end', round=self.round, time_elapsed=self.cumulative_time)
                        # Check win condition
                        team1_win_count = 0
                        team2_win_count = 0
                        for chara in Character.team1_list:
                            if self.field.boxes[chara.grid[0]][chara.grid[1]].terrain == 3:
                                team1_win_count += 1
                        for enemy in Character.team2_list:
                            if self.field.boxes[enemy.grid[0]][enemy.grid[1]].terrain == 3:
                                team2_win_count += 1

                        match_winner = 0
                        next_round = False

                        if team1_win_count > team2_win_count:
                            self.p1_round_wins += 1
                            if self.p1_dom_count == 0:
                                self.p1_dom_count = 1
                                self.p2_dom_count = 0
                                next_round = True
                            elif self.p1_dom_count == 1:
                                match_winner = 1
                            else:
                                print('There is a problem with dominance check')
                        elif team2_win_count > team1_win_count:
                            self.p2_round_wins += 1
                            if self.p2_dom_count == 0:
                                self.p2_dom_count = 1
                                self.p1_dom_count = 0
                                next_round = True
                            elif self.p2_dom_count == 1:
                                match_winner = 2
                            else:
                                print('There is a problem with dominance check')
                        else:
                            next_round = True
                            self.p1_dom_count = 0  # remove these 2 lines may cause a bug
                            self.p2_dom_count = 0  # but it may be a good feature

                        if match_winner == 0 and next_round:
                            self.round += 1
                            self.game_state = 'show round'
                            self.field.hover_cursor.show = True
                            self.log_event('round_begin', round=self.round)
                            self._init_character_snapshots()

                        if match_winner == 1:
                            self.total_p1_win += 1
                            self.last_match_duration = self.cumulative_time
                            self.log_event('match_over', match=self.currentMatch, winner='P1', p1_rounds=self.p1_round_wins, p2_rounds=self.p2_round_wins)
                            self.log_event('summary_match', match=self.currentMatch, map_label=self._current_map_label)
                            self.log_event('summary_result', winner=1, p1_rounds=self.p1_round_wins, p2_rounds=self.p2_round_wins)
                            self.log_event('summary_series', p1_matches=self.total_p1_win, p2_matches=self.total_p2_win)
                            if self.isAuto:
                                print("Match " + str(self.currentMatch) + " result: Player 1 wins")
                                self.startMatch()
                                return
                            self.game_state = 'win'
                            self._log_series_summary()
                        elif match_winner == 2:
                            self.total_p2_win += 1
                            self.last_match_duration = self.cumulative_time
                            self.log_event('match_over', match=self.currentMatch, winner='P2', p1_rounds=self.p1_round_wins, p2_rounds=self.p2_round_wins)
                            self.log_event('summary_match', match=self.currentMatch, map_label=self._current_map_label)
                            self.log_event('summary_result', winner=2, p1_rounds=self.p1_round_wins, p2_rounds=self.p2_round_wins)
                            self.log_event('summary_series', p1_matches=self.total_p1_win, p2_matches=self.total_p2_win)
                            if self.isAuto:
                                print("Match " + str(self.currentMatch) + " result: Player 2 wins")
                                self.startMatch()
                                return
                            self.game_state = 'lose'
                            self._log_series_summary()

                        self.number_action = -1
                        for chara in Character.team1_list + Character.team2_list:
                            chara.moved = False
                            chara.acted = False

                        self.GameMaster.startRound()

            prev_state = {cid: data.copy() for cid, data in self._char_snapshots.items()}
            current_state = self._capture_character_state()
            if prev_state or current_state:
                self._process_character_movements(prev_state, current_state)
                self._process_ai_logs(prev_state, current_state)
                self._process_character_outcomes(prev_state, current_state)
            self._char_snapshots = current_state

            # Cursor.state = self.field.update(dt, events, Cursor.state)

    def _match_limit_position_from_value(self, value: int) -> int:
        value = max(self._match_limit_min, min(self._match_limit_max, value))
        span = self._match_limit_slider_rect.width - self._match_limit_knob_width
        if span <= 0 or self._match_limit_max == self._match_limit_min:
            return 0
        ratio = (value - self._match_limit_min) / (self._match_limit_max - self._match_limit_min)
        return int(round(ratio * span))

    def _match_limit_value_from_pos(self, pos_x: float) -> int:
        span = self._match_limit_slider_rect.width - self._match_limit_knob_width
        if span <= 0 or self._match_limit_max == self._match_limit_min:
            return self._match_limit_min
        ratio = (pos_x - self._match_limit_slider_rect.x - self._match_limit_knob_width / 2) / span
        ratio = max(0.0, min(1.0, ratio))
        value = round(ratio * (self._match_limit_max - self._match_limit_min)) + self._match_limit_min
        return int(max(self._match_limit_min, min(self._match_limit_max, value)))

    def _game_limit_position_from_value(self, value: int) -> int:
        value = max(self._game_limit_min, min(self._game_limit_max, value))
        span = self._game_limit_slider_rect.width - self._game_limit_knob_width
        if span <= 0 or self._game_limit_max == self._game_limit_min:
            return 0
        ratio = (value - self._game_limit_min) / (self._game_limit_max - self._game_limit_min)
        return int(round(ratio * span))

    def _game_limit_value_from_pos(self, pos_x: float) -> int:
        span = self._game_limit_slider_rect.width - self._game_limit_knob_width
        if span <= 0 or self._game_limit_max == self._game_limit_min:
            return self._game_limit_min
        ratio = (pos_x - self._game_limit_slider_rect.x - self._game_limit_knob_width / 2) / span
        ratio = max(0.0, min(1.0, ratio))
        value = round(ratio * (self._game_limit_max - self._game_limit_min)) + self._game_limit_min
        return int(max(self._game_limit_min, min(self._game_limit_max, value)))

    def render(self) -> None:
        if self.game_screen == -1:      # Start screen
            # Draw background
            self.screen.blit(self.background, (0, 0))
            
            # Draw play button
            button_color = (255, 255, 255) if self.play_button_hovered else (235, 235, 235)
            pygame.draw.rect(self.screen, button_color, self.play_button_rect)
            pygame.draw.rect(self.screen, BLACK, self.play_button_rect, 2)
            
            # Draw play button text
            play_text = self.font_m.render("PLAY", False, (50, 50, 50))
            text_rect = play_text.get_rect(center=(self.play_button_rect.centerx, self.play_button_rect.centery + 5))
            self.screen.blit(play_text, text_rect)
        
            # Draw Laptop/Macbook button to scale the window smaller
            lb_color = (255, 255, 255) if self.laptop_button_hovered else (235, 235, 235)
            pygame.draw.rect(self.screen, lb_color, self.laptop_button_rect)
            pygame.draw.rect(self.screen, BLACK, self.laptop_button_rect, 2)
            lb_text = self.font_s.render("Toggle Resolution", False, (50, 50, 50))
            lb_rect = lb_text.get_rect(center=self.laptop_button_rect.center)
            self.screen.blit(lb_text, lb_rect)
        
            # Show current resolution under the toggle button, left-aligned with the button
            cur_w, cur_h = self.display.get_size()
            res_text = self.font_s.render(f"Resolution: {cur_w}x{cur_h}", False, (0, 0, 0))
            res_rect = res_text.get_rect(topleft=(self.laptop_button_rect.left, self.laptop_button_rect.bottom + 15))
            self.screen.blit(res_text, res_rect)
            
            # "Control :"
            Control_text = self.font_s.render("Control :", False, WHITE)
            Control_rect = Control_text.get_rect(topleft=(290, 580))
            shadow0 = self.font_s.render("Control :", False, BLACK)
            shadow0_rect = shadow0.get_rect(topleft=(292, 582))
            self.screen.blit(shadow0, shadow0_rect)
            self.screen.blit(Control_text, Control_rect)

            # Control select
            control1_text = self.font_s.render("Z / Left Click : Select", False, WHITE)
            control1_rect = control1_text.get_rect(topleft=(290, 630))
            shadow1 = self.font_s.render("Z / Left Click : Select", False, BLACK)
            shadow1_rect = shadow1.get_rect(topleft=(292, 632))
            self.screen.blit(shadow1, shadow1_rect)
            self.screen.blit(control1_text, control1_rect)
            
            # Control cancel
            control2_text = self.font_s.render("X / Right Click : Cancel", False, WHITE)
            control2_rect = control2_text.get_rect(topleft=(290, 667))
            shadow2 = self.font_s.render("X / Right Click : Cancel", False, BLACK)
            shadow2_rect = shadow2.get_rect(topleft=(292, 669))
            self.screen.blit(shadow2, shadow2_rect)
            self.screen.blit(control2_text, control2_rect)
            
            # Control auto
            control3_text = self.font_s.render("A : Auto setting", False, WHITE)
            control3_rect = control3_text.get_rect(topleft=(690, 630))
            shadow3 = self.font_s.render("A : Auto setting", False, BLACK)
            shadow3_rect = shadow3.get_rect(topleft=(692, 632))
            self.screen.blit(shadow3, shadow3_rect)
            self.screen.blit(control3_text, control3_rect)
            
            # Control start
            control4_text = self.font_s.render("Enter : Start the game", False, WHITE)
            control4_rect = control4_text.get_rect(topleft=(690, 667))
            shadow4 = self.font_s.render("Enter : Start the game", False, BLACK)
            shadow4_rect = shadow4.get_rect(topleft=(692, 669))
            self.screen.blit(shadow4, shadow4_rect)
            self.screen.blit(control4_text, control4_rect)
            
        elif self.game_screen == 0:
            # AI selection screen — layout styled to match the provided screenshot
            self.screen.fill(SMOKE)

            # Header banners
            banner_w, banner_h = 260, 48
            p1_banner = pygame.Rect(WIDTH // 4 - banner_w // 2, 24, banner_w, banner_h)
            p2_banner = pygame.Rect(WIDTH * 3 // 4 - banner_w // 2, 24, banner_w, banner_h)
            pygame.draw.rect(self.screen, (158, 219, 247), p1_banner)
            pygame.draw.rect(self.screen, (255, 153, 153), p2_banner)
            pygame.draw.rect(self.screen, (0, 0, 0), p1_banner, 2)
            pygame.draw.rect(self.screen, (0, 0, 0), p2_banner, 2)

            p1_title = self.font_s.render('PLAYER 1', False, (0, 0, 0))
            p2_title = self.font_s.render('PLAYER 2', False, (0, 0, 0))
            self.screen.blit(p1_title, p1_title.get_rect(center=p1_banner.center))
            self.screen.blit(p2_title, p2_title.get_rect(center=p2_banner.center))

            # Build display labels: first is Player Input, then AI_1..AI_4 with the existing model names appended
            model_names = AI_SELECTION_LABELS
            labels = [model_names[0]] + [f'AI_{i}' for i in range(1, len(model_names))]
            # We'll display the model name beside each AI_i in smaller text

            left_center_x = WIDTH // 4
            right_center_x = WIDTH * 3 // 4
            start_y = 160
            slot_h = 56
            gap = 22
            box_w = 360

            for col_x in (left_center_x, right_center_x):
                for i, main_label in enumerate(labels):
                    y = start_y + i * (slot_h + gap)
                    box_rect = pygame.Rect(col_x - box_w // 2, y, box_w, slot_h)
                    pygame.draw.rect(self.screen, (255, 255, 255), box_rect)
                    pygame.draw.rect(self.screen, (0, 0, 0), box_rect, 2)

                    # Main label (AI_1 etc or Player Input)
                    lbl = self.font_sm.render(main_label, False, (0, 0, 0))
                    lbl_rect = lbl.get_rect(midleft=(box_rect.left + 18, box_rect.centery))
                    self.screen.blit(lbl, lbl_rect)

                    # If not the Player Input row, draw the model name to the right
                    if i > 0:
                        model_name = model_names[i]
                        mdl = self.font_ss.render(model_name, False, (0, 0, 0))
                        mdl_rect = mdl.get_rect(midright=(box_rect.right - 18, box_rect.centery))
                        self.screen.blit(mdl, mdl_rect)

                    # Decorative dropdown arrow for the second row (like screenshot)
                    if i == 2:
                        arrow = self.font_sm.render('\u25BE', False, (0, 0, 0))
                        arrow_rect = arrow.get_rect(midright=(box_rect.right - 40, box_rect.centery))
                        self.screen.blit(arrow, arrow_rect)

            # Small scrollbars beside columns (cosmetic)
            sb_x_off = box_w // 2 + 18
            sb_h = (slot_h + gap) * len(labels) - gap
            for cx in (left_center_x, right_center_x):
                track_rect = pygame.Rect(cx + sb_x_off, start_y, 12, sb_h)
                pygame.draw.rect(self.screen, SB_TRACK, track_rect)
                thumb_rect = pygame.Rect(track_rect.x + 1, start_y + 8, 10, 44)
                pygame.draw.rect(self.screen, SB_THUMB, thumb_rect)

            # Center message
            enter_text = self.font_l.render('Enter to start', False, (0, 0, 0))
            self.screen.blit(enter_text, enter_text.get_rect(center=(WIDTH // 2, 680)))

            # Draw selection cursors (positions are aligned to the left column coordinates)
            p1_cursor_x = left_center_x - box_w // 2
            p2_cursor_x = right_center_x - box_w // 2
            self.p1_sel_cursor.render((p1_cursor_x, start_y + self.p1_sel_cursor.grid[0] * (slot_h + gap)))
            self.p2_sel_cursor.render((p2_cursor_x, start_y + self.p2_sel_cursor.grid[0] * (slot_h + gap)))
            self.menu_cursor.render((p1_cursor_x + self.menu_cursor.grid[1] * (box_w + 48), start_y + self.menu_cursor.grid[0] * (slot_h + gap)))

            # Bottom-left: Auto and match limit widgets (reuse existing controls)
            auto_label_surface = self.font_menu_label.render("Auto:", False, (0, 0, 0))
            auto_label_rect = auto_label_surface.get_rect(topleft=(64, 880))
            self.screen.blit(auto_label_surface, auto_label_rect)
            auto_value_text = "True" if self.isAuto else "False"
            auto_value_surface = self.font_menu_label.render(auto_value_text, False, (0, 197, 7) if self.isAuto else (200, 0, 0))
            auto_value_rect = auto_value_surface.get_rect()
            auto_value_rect.topleft = (auto_label_rect.right + 8, 880)
            self.screen.blit(auto_value_surface, auto_value_rect)

            # Game limit (above match limit)
            game_label = self.font_menu_label.render("Game limit:", False, (0, 0, 0))
            self.screen.blit(game_label, (64, 915))
            pygame.draw.rect(self.screen, (245, 245, 245), self._game_limit_box_rect)
            pygame.draw.rect(self.screen, (0, 0, 0), self._game_limit_box_rect, 1)
            game_value_surface = self.font_s.render(str(self.game_limit), False, (0, 0, 0))
            game_value_rect = game_value_surface.get_rect(center=self._game_limit_box_rect.center)
            self.screen.blit(game_value_surface, game_value_rect)

            # Draw game limit slider track + knob
            pygame.draw.rect(self.screen, (235, 235, 235), self._game_limit_slider_rect)
            pygame.draw.rect(self.screen, (0, 0, 0), self._game_limit_slider_rect, 1)
            # knob position
            knob_x = self._game_limit_slider_rect.x + self._game_limit_position_from_value(self.game_limit)
            knob_rect = pygame.Rect(knob_x, self._game_limit_slider_rect.y - (self._game_limit_knob_height - self._game_limit_slider_rect.height) // 2, self._game_limit_knob_width, self._game_limit_knob_height)
            pygame.draw.rect(self.screen, (180, 180, 180), knob_rect)
            pygame.draw.rect(self.screen, (0, 0, 0), knob_rect, 1)

            # Match limit
            match_label = self.font_menu_label.render("Match limit:", False, (0, 0, 0))
            self.screen.blit(match_label, (64, 945))
            pygame.draw.rect(self.screen, (245, 245, 245), self._match_limit_box_rect)
            pygame.draw.rect(self.screen, (0, 0, 0), self._match_limit_box_rect, 1)
            match_value_surface = self.font_s.render(str(self.match_limit), False, (0, 0, 0))
            value_rect = match_value_surface.get_rect(center=self._match_limit_box_rect.center)
            self.screen.blit(match_value_surface, value_rect)

            # Draw match limit slider track + knob
            pygame.draw.rect(self.screen, (235, 235, 235), self._match_limit_slider_rect)
            pygame.draw.rect(self.screen, (0, 0, 0), self._match_limit_slider_rect, 1)
            mknob_x = self._match_limit_slider_rect.x + self._match_limit_position_from_value(self.match_limit)
            mknob_rect = pygame.Rect(mknob_x, self._match_limit_slider_rect.y - (self._match_limit_knob_height - self._match_limit_slider_rect.height) // 2, self._match_limit_knob_width, self._match_limit_knob_height)
            pygame.draw.rect(self.screen, (180, 180, 180), mknob_rect)
            pygame.draw.rect(self.screen, (0, 0, 0), mknob_rect, 1)

            # Map preview and selection button
            mouse_pos = pygame.mouse.get_pos()
            self._map_button_hovered = self._map_select_button_rect.collidepoint(mouse_pos)
            preview_index = self._clamp_map_index(self.map_number)
            preview_surface = self._map_preview_small[preview_index]
            self.screen.blit(preview_surface, self._map_preview_thumb_rect)
            pygame.draw.rect(self.screen, (0, 0, 0), self._map_preview_thumb_rect, 1)
            button_color = (217, 217, 217) if not self._map_button_hovered else (200, 200, 200)
            pygame.draw.rect(self.screen, button_color, self._map_select_button_rect)
            pygame.draw.rect(self.screen, (0, 0, 0), self._map_select_button_rect, 1)
            map_button_text = self.font_s.render("Map Selection", False, (0, 0, 0))
            self.screen.blit(map_button_text, map_button_text.get_rect(center=self._map_select_button_rect.center))

            # Map popup (reuse existing implementation)
            if self._map_popup_open:
                self._map_popup_select_hovered = self._map_popup_select_rect.collidepoint(mouse_pos)
                self._map_popup_hover_index = None
                for idx, rect in enumerate(self._map_popup_option_rects):
                    if rect.collidepoint(mouse_pos):
                        self._map_popup_hover_index = idx
                        break

                overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
                overlay.fill((0, 0, 0, 100))
                self.screen.blit(overlay, (0, 0))

                pygame.draw.rect(self.screen, (255, 255, 255), self._map_popup_rect)
                pygame.draw.rect(self.screen, (0, 0, 0), self._map_popup_rect, 3)

                preview_surface_large = self._map_preview_large[self._map_popup_temp_selection]
                self.screen.blit(preview_surface_large, self._map_popup_preview_rect)
                pygame.draw.rect(self.screen, (0, 0, 0), self._map_popup_preview_rect, 2)

                preview_label = self._map_option_labels[self._map_popup_temp_selection]
                if preview_label.lower() != 'random':
                    preview_label = f"Map {preview_label}"
                preview_text = self.font_sm.render(preview_label, False, (0, 0, 0))
                preview_text_rect = preview_text.get_rect(midtop=(self._map_popup_preview_rect.centerx, self._map_popup_preview_rect.bottom + 12))
                self.screen.blit(preview_text, preview_text_rect)

                for idx, rect in enumerate(self._map_popup_option_rects):
                    is_selected = idx == self._map_popup_temp_selection
                    is_hovered = idx == self._map_popup_hover_index and not is_selected
                    fill_color = (226, 226, 226)
                    if is_hovered:
                        fill_color = (210, 210, 210)
                    pygame.draw.rect(self.screen, fill_color, rect)
                    border_color = (19, 189, 0) if is_selected else (0, 0, 0)
                    border_width = 4 if is_selected else 2
                    pygame.draw.rect(self.screen, border_color, rect, border_width)

                    label = self._map_option_labels[idx]
                    text_surface = self.font_menu_label.render(label, False, (0, 0, 0))
                    text_rect = text_surface.get_rect(center=rect.center)
                    self.screen.blit(text_surface, text_rect)

                select_color = (199, 255, 178) if not self._map_popup_select_hovered else (182, 235, 160)
                pygame.draw.rect(self.screen, select_color, self._map_popup_select_rect)
                pygame.draw.rect(self.screen, (0, 0, 0), self._map_popup_select_rect, 2)
                select_text = self.font_sm.render("SELECT", False, (0, 0, 0))
                self.screen.blit(select_text, select_text.get_rect(center=self._map_popup_select_rect.center))


        elif self.game_screen == 1:
            self.screen.fill(SMOKE)

            self.field.render()

            # Left column UI: optional Pause button + compact info panels
            left_x, left_w = 40, 260
            show_pause_button = self._is_pause_button_available()
            # Draw Pause button
            if show_pause_button:
                pygame.draw.rect(self.screen, (235, 235, 235), self.pause_game_button_rect)
                pygame.draw.rect(self.screen, (0, 0, 0), self.pause_game_button_rect, 1)
                if self.pause_game_button_hovered:
                    pygame.draw.rect(self.screen, YELLOW, self.pause_game_button_rect, 3)
                pause_text = self.font_s.render('Pause', False, (0, 0, 0))
                self.screen.blit(pause_text, pause_text.get_rect(center=self.pause_game_button_rect.center))

            # Panel positions/heights
            base_y = self.pause_game_button_rect.bottom + 10 if show_pause_button else 40
            unit_rect = pygame.Rect(left_x, base_y, left_w, 140)
            terrain_rect = pygame.Rect(left_x, unit_rect.bottom + 10, left_w, 140)
            objective_rect = pygame.Rect(left_x, terrain_rect.bottom + 10, left_w, 220)

            # Unit Info
            pygame.draw.rect(self.screen, (0, 0, 0), unit_rect, 2)
            unit_menu_text = self.font_s.render("Unit Info", False, (0, 0, 0))
            self.screen.blit(unit_menu_text, unit_menu_text.get_rect(topleft=(unit_rect.x + 10, unit_rect.y + 10)))
            if (chara := self.field.hover_cursor.getChara()) is not None:
                unit_info = self.font_s.render(chara.template['display_name'], False, (0, 0, 0))
                self.screen.blit(unit_info, unit_info.get_rect(topleft=(unit_rect.x + 10, unit_rect.y + 40)))
                unit_info = self.font_s.render(
                    f"HP : {chara.template['curHP']}/{chara.template['maxHP']}", False, (0, 0, 0))
                self.screen.blit(unit_info, unit_info.get_rect(topleft=(unit_rect.x + 10, unit_rect.y + 65)))
                unit_info = self.font_s.render(f"Movement : {chara.template['movement']}", False, (0, 0, 0))
                self.screen.blit(unit_info, unit_info.get_rect(topleft=(unit_rect.x + 10, unit_rect.y + 90)))
                if chara in Character.team1_list:
                    if not chara.moved:
                        text = "Movement available"
                    elif not chara.acted:
                        text = "Action available"
                    else:
                        text = "Turn completed"
                    unit_info = self.font_s.render(text, False, (0, 0, 0))
                    self.screen.blit(unit_info, unit_info.get_rect(topleft=(unit_rect.x + 10, unit_rect.y + 115)))

            # Terrain Info
            pygame.draw.rect(self.screen, (0, 0, 0), terrain_rect, 2)
            terrain_menu_text = self.font_s.render("Terrain Info", False, (0, 0, 0))
            self.screen.blit(terrain_menu_text, terrain_menu_text.get_rect(topleft=(terrain_rect.x + 10, terrain_rect.y + 10)))

            box = self.field.getHoveredBoxInfo()
            terrain_name = self.font_s.render(box.terrain_name, False, (0, 0, 0))
            terrain_desc = self.font_s.render(box.terrain_desc, False, (0, 0, 0))
            self.screen.blit(terrain_name, terrain_name.get_rect(topleft=(terrain_rect.x + 10, terrain_rect.y + 40)))
            self.screen.blit(terrain_desc, terrain_desc.get_rect(topleft=(terrain_rect.x + 10, terrain_rect.y + 70)))

            # Objective Info
            pygame.draw.rect(self.screen, (0, 0, 0), objective_rect, 2)
            objective_menu_text = self.font_s.render("Objective Info", False, (0, 0, 0))
            self.screen.blit(objective_menu_text, objective_menu_text.get_rect(topleft=(objective_rect.x + 10, objective_rect.y + 10)))
            text = self.font_s.render(f'Have units stand', False, (0, 0, 0))
            self.screen.blit(text, text.get_rect(topleft=(objective_rect.x + 10, objective_rect.y + 40)))
            text = self.font_s.render(f'in objective area', False, (0, 0, 0))
            self.screen.blit(text, text.get_rect(topleft=(objective_rect.x + 10, objective_rect.y + 65)))
            text = self.font_s.render(f'more than enemy.', False, (0, 0, 0))
            self.screen.blit(text, text.get_rect(topleft=(objective_rect.x + 10, objective_rect.y + 90)))

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
            # if self.game_state == 'enemy action':
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
                pygame.draw.rect(self.screen, (0, 0, 0), pygame.Rect(980, 40, 260, 560), 2)
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
                        pygame.draw.rect(self.screen, (0, 0, 0), pygame.Rect(1000, 88 + i, 220, 150), 1)
                        if Cursor.selected_action == index:
                            pygame.draw.rect(self.screen, YELLOW, pygame.Rect(1000, 88 + i, 220, 150), 4)
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
                        i += 170
                # Pass player turn button (mouse only)
                # Draw button with hover highlight
                pygame.draw.rect(self.screen, (235, 235, 235), self.pass_turn_button_rect)
                pygame.draw.rect(self.screen, (0, 0, 0), self.pass_turn_button_rect, 1)
                if self.pass_turn_button_hovered:
                    pygame.draw.rect(self.screen, YELLOW, self.pass_turn_button_rect, 3)
                pass_turn_text = self.font_s.render('Pass player turn', False, (0, 0, 0))
                text_rect = pass_turn_text.get_rect(center=self.pass_turn_button_rect.center)
                self.screen.blit(pass_turn_text, text_rect)

            # info text
            if Cursor.state == 0:
                action_text = self.font_s.render("Z : Move Unit / Perform Action    X : Does Nothing    P : Pass player turn", False, (0, 0, 0))
                text_rect = action_text.get_rect(topleft=(40, 697))
                self.screen.blit(action_text, text_rect)
            elif Cursor.state == 1:
                action_text = self.font_s.render("Z : Move Unit    X : Cancel    P : Pass player turn", False, (0, 0, 0))
                text_rect = action_text.get_rect(topleft=(40, 697))
                self.screen.blit(action_text, text_rect)
            elif Cursor.state == 2:
                action_text = self.font_s.render("Z : Confirm Option    X : Cancel    P : Pass player turn", False, (0, 0, 0))
                text_rect = action_text.get_rect(topleft=(40, 697))
                self.screen.blit(action_text, text_rect)
            elif Cursor.state == 3:
                action_text = self.font_s.render("Z : Does Nothing    X : Cancel    P : Pass player turn", False, (0, 0, 0))
                text_rect = action_text.get_rect(topleft=(40, 697))
                self.screen.blit(action_text, text_rect)
            elif Cursor.state == 4:
                action_text = self.font_s.render("Z : Perform Action    X : Cancel    P : Pass player turn", False, (0, 0, 0))
                text_rect = action_text.get_rect(topleft=(40, 697))
                self.screen.blit(action_text, text_rect)
            elif Cursor.state == 5:
                action_text = self.font_s.render("Z : Select / Move Unit    X : Confirm position", False, (0, 0, 0))
                text_rect = action_text.get_rect(topleft=(40, 697))
                self.screen.blit(action_text, text_rect)
            # elif Cursor.state == 6:
            #     action_text = self.font_s.render("Z : Does Nothing   X : Cancel", False, (0, 0, 0))
            #     text_rect = action_text.get_rect(topleft=(50, 690))
            #     self.screen.blit(action_text, text_rect)
            else:
                pass

            # Round Indicator at corner
            round_text = self.font_s.render(f"Round : {self.round}", False, (0, 0, 0))
            text_rect = round_text.get_rect(topright=(1230, 697))
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
                    # self.game_state = 'attacking phase'
                    self.game_state = 'enemy action'

            # Delay text
            delay_text = self.font_ss.render(f'Delay = {self.action_delay}', False, (0, 0, 0))
            text_rect = delay_text.get_rect(bottomleft=(50, 670))
            self.screen.blit(delay_text, text_rect)

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

            for log_tuple in self.game_log[start:end]:
                # Handle both old (text, color) and new (text, color, time) formats
                if len(log_tuple) == 3:
                    text, color, _ = log_tuple
                else:
                    text, color = log_tuple
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

            if self._is_endgame_popup_active():
                self._render_endgame_popup(geom)
            elif self._is_pause_popup_active():
                self._render_pause_popup(geom)
        
        # --- Present base canvas to the OS window (scaled if needed) ---
        scaled_surface = pygame.transform.smoothscale(self.screen, self.display.get_size())
        self.display.blit(scaled_surface, (0, 0))
                
    def export_game_log(self) -> None:
        """Export the game log to an Excel file with 'Game Log' and 'Match Summary' sheets."""
        def safe_int(s, default=0):
            try:
                return int(s)
            except (ValueError, TypeError):
                return default

        try:
            import openpyxl
            from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
            from datetime import datetime
            import os

            wb = openpyxl.Workbook()
            wb.remove(wb.active)
            log_ws = wb.create_sheet("Game Log")
            summary_ws = wb.create_sheet("Match Summary")

            # Styles
            header_font = Font(bold=True, color="FFFFFF")
            header_fill = PatternFill(start_color="FFA500", end_color="FFA500", fill_type="solid")
            header_alignment = Alignment(horizontal="center", vertical="center")
            thin_border = Border(
                left=Side(style='thin'),
                right=Side(style='thin'),
                top=Side(style='thin'),
                bottom=Side(style='thin')
            )
            summary_title_font = Font(bold=True, size=14, color="FFFFFF")
            summary_title_fill = PatternFill(start_color="FF0000", end_color="FF0000", fill_type="solid")

            # === GAME LOG SHEET ===
            column_widths = [5, 25, 8, 8, 6, 10, 10, 12, 10, 15, 12, 8, 8, 10, 15, 12, 12, 10]
            for i, width in enumerate(column_widths, 1):
                log_ws.column_dimensions[openpyxl.utils.get_column_letter(i)].width = width

            headers = [
                "No.", "Scenario", "Match", "Round", "Team", "Time (seconds)",
                "Health", "Position (Row, Col)", "Event", "Action name",
                "Target Position", "Damage", "Heal", "Movement",
                "Target", "Target Health before", "Target Health after", "Target Team"
            ]
            for col, header in enumerate(headers, 1):
                cell = log_ws.cell(row=1, column=col, value=header)
                cell.font = header_font
                cell.fill = header_fill
                cell.alignment = header_alignment
                cell.border = thin_border

            # Initialize tracking
            current_match = 1
            current_round = 1
            team1_damage_given = 0
            team2_damage_given = 0
            team1_kills = 0
            team2_kills = 0
            kill_details = []
            row = 2
            step = 1

            # --- NEW: Find the last match number and its final round ---
            last_match_num = 0
            last_round_num = 0
            for log_tuple in reversed(self.game_log):
                if len(log_tuple) == 3:
                    log_entry, color, time_elapsed = log_tuple
                else:
                    log_entry, color = log_tuple
                    time_elapsed = 0.0 # Process oldest first
                if "Match" in log_entry and "starts" in log_entry:
                    try:
                        match_num = int(log_entry.split("Match ")[1].split()[0])
                        last_match_num = max(last_match_num, match_num)
                    except:
                        pass
                elif "Round" in log_entry and "begins" in log_entry:
                    try:
                        round_num = int(log_entry.split("Round ")[1].split()[0])
                        # Only update if this round belongs to the last match
                        if last_match_num > 0: # Ensure we have a valid last match
                            last_round_num = max(last_round_num, round_num)
                    except:
                        pass

            # --- NEW: Flag to indicate we've passed the end of the last match's final round ---
            reached_final_round_end = False

            # Process log from OLDEST to NEWEST (reverse because log is newest-first)
            for log_tuple in reversed(self.game_log):
                # Unpack: (text, color, time_elapsed)
                if len(log_tuple) == 3:
                    log_entry, color, time_elapsed = log_tuple
                else:
                    # Fallback for old-style logs (if any)
                    log_entry, color = log_tuple
                    time_elapsed = 0.0
                # --- NEW: Check if we've already passed the final round end ---
                if reached_final_round_end:
                    # Skip this entry for the Game Log sheet
                    continue

                if "Match" in log_entry and "starts" in log_entry:
                    try:
                        current_match = int(log_entry.split("Match ")[1].split()[0])
                    except:
                        pass
                    continue
                elif "Round" in log_entry and "begins" in log_entry:
                    try:
                        current_round = int(log_entry.split("Round ")[1].split()[0])
                    except:
                        pass
                    continue
                # --- NEW: Also skip summary events ---
                elif "Match over" in log_entry or "SUMMARY" in log_entry or \
                     "SERIES OVER" in log_entry or "WINNER" in log_entry or \
                     "Total matches played" in log_entry:
                    # We'll handle the "round_end" for the final round separately.
                    continue

                parts = log_entry.split(" : ", 1)
                if len(parts) < 2:
                    continue
                tag = parts[0]
                message = parts[1]
                team = 1 if tag == "P1" else (2 if tag == "P2" else "")
                event = ""
                action_name = ""
                unit_name = ""
                target = ""
                position = ""
                target_position = ""
                damage = ""
                heal = ""
                movement = ""
                health = "" # Initialize to empty
                target_health_before = ""
                target_health_after = ""
                target_team = ""
                scenario = message

                # --- Parse events ---
                if "moves" in message:
                    event = "move"
                    if " moves " in message:
                        a, b = message.split(" moves ", 1)
                        unit_name = a
                        if " -> " in b and " (" in b:
                            pos_part, dist_part = b.rsplit(" (", 1)
                            start_pos, end_pos = pos_part.split(" -> ", 1)
                            movement = safe_int(dist_part.replace(" tiles)", ""))
                            position = end_pos
                            scenario = f"{unit_name} moves ({start_pos} -> {end_pos})"
                    # --- GET HEALTH FOR MOVE EVENT FROM PREV STATE ---
                    # Use the _char_snapshots (prev_state) to get health at start of turn
                    for chara in Character.team1_list + Character.team2_list:
                        if chara.template.get("display_name", "") == unit_name:
                            # Try to find the character's state at the beginning of the turn
                            prev_char_data = self._char_snapshots.get(chara.id)
                            if prev_char_data:
                                health = prev_char_data.get("hp", 0)
                            else:
                                # Fallback: use current health if snapshot not available
                                health = chara.template.get("curHP", 0)
                            break
                elif "attacks" in message and "(HP before:" in message:
                    event = "attack"
                    if " attacks " in message and " with \"" in message and " - hit for " in message:
                        a, rest = message.split(" attacks ", 1)
                        unit_name = a
                        if " with \"" in rest:
                            target_part, action_rest = rest.split(" with \"", 1)
                            target = target_part
                            if "\" - hit for " in action_rest:
                                action_name, result = action_rest.split("\" - hit for ", 1)
                                if "(HP before: " in result:
                                    # Parse: "6 (HP before: 4, after: 4/22) at E5"
                                    parts = result.split(" at ")
                                    main_part = parts[0]
                                    target_position = parts[1] if len(parts) > 1 else ""  # Extract target position
                                    # Now parse the main part for damage and HP
                                    dmg_str = main_part.split(" (HP before: ")[0]
                                    hp_part = main_part.split("(HP before: ")[1].split(")")[0]  # "4, after: 4/22"
                                    hp_before_str, hp_after_str = hp_part.split(", after: ")
                                    damage = safe_int(dmg_str)
                                    target_health_before = safe_int(hp_before_str)
                                    # Calculate actual HP after damage (clamp to 0)
                                    target_health_after = max(0, target_health_before - damage)
                                    if team == 1:
                                        team1_damage_given += damage
                                    elif team == 2:
                                        team2_damage_given += damage
                                    scenario = f"{unit_name} attacks {target} with {action_name}"
                                    target_team = 2 if team == 1 else 1
                    # --- GET HEALTH FOR ATTACK EVENT FROM PREV STATE ---
                    for chara in Character.team1_list + Character.team2_list:
                        if chara.template.get("display_name", "") == unit_name:
                            prev_char_data = self._char_snapshots.get(chara.id)
                            if prev_char_data:
                                health = prev_char_data.get("hp", 0)
                            else:
                                health = chara.template.get("curHP", 0)
                            break
                elif "uses" in message and "heal" in message:
                    event = "heal"
                    if " uses \"" in message and " on " in message and " - +" in message:
                        a, rest = message.split(" uses \"", 1)
                        unit_name = a
                        if "\" on " in rest:
                            action_part, target_rest = rest.split("\" on ", 1)
                            action_name = action_part
                            if " - +" in target_rest:
                                target_part, hp_part = target_rest.split(" - +", 1)
                                target = target_part
                                if " (HP " in hp_part:
                                    heal_str, hp_str = hp_part.split(" (HP ", 1)
                                    heal = safe_int(heal_str)
                                    hp_cur, hp_max = hp_str.replace(")", "").split("/", 1)
                                    target_health_after = safe_int(hp_cur)
                                    target_health_before = target_health_after - heal
                                    target_team = team
                                    scenario = f"{unit_name} heals {target} with {action_name}"
                    # --- GET HEALTH FOR HEAL EVENT FROM PREV STATE ---
                    for chara in Character.team1_list + Character.team2_list:
                        if chara.template.get("display_name", "") == unit_name:
                            prev_char_data = self._char_snapshots.get(chara.id)
                            if prev_char_data:
                                health = prev_char_data.get("hp", 0)
                            else:
                                health = chara.template.get("curHP", 0)
                            break
                elif "is KO" in message:
                    event = "kill"
                    unit_name = message.split(" is KO")[0]
                    if "(HP 0/" in message:
                        hp_max = safe_int(message.split("(HP 0/")[1].split(")")[0])
                        target_health_before = hp_max
                        target_health_after = 0
                        damage = hp_max
                        if team == 1:
                            team1_damage_given += damage
                            team1_kills += 1
                        elif team == 2:
                            team2_damage_given += damage
                            team2_kills += 1
                        # Extract killer if possible
                        if "by " in message:
                            killer = message.split("by ")[1].split(" using")[0]
                            kill_details.append(f"In Match {current_match} - Round {current_round}, {killer} killed {unit_name}")
                    target = unit_name
                    target_team = team
                    scenario = f"{unit_name} is KO"
                    # --- SET HEALTH TO 0 FOR KO EVENT ---
                    health = 0
                elif "Pass turn" in message:
                    event = "pass"
                    unit_name = f"T{team}"
                    scenario = f"{unit_name} passes turn"
                    # --- GET HEALTH FOR PASS EVENT FROM PREV STATE ---
                    # For pass events, we don't have a specific unit name, so we leave health as 0.
                    # You could enhance this by tracking the last active unit per team.
                    health = 0

                # --- NEW: Check for "round_end" event for the last match and round ---
                if "Round" in log_entry and "ends" in log_entry:
                    try:
                        round_num = int(log_entry.split("Round ")[1].split()[0])
                        # Check if this is the end of the final round of the last match
                        if current_match == last_match_num and round_num == last_round_num:
                            # This is the end of the last match's final round.
                            # Mark that we've reached it.
                            reached_final_round_end = True
                            # We still want to include this "round_end" line in the log.
                            # So, we don't continue here; we process it.
                    except:
                        pass

                # Write row
                log_ws.cell(row=row, column=1, value=step).border = thin_border
                log_ws.cell(row=row, column=2, value=scenario).border = thin_border
                log_ws.cell(row=row, column=3, value=current_match).border = thin_border
                log_ws.cell(row=row, column=4, value=current_round).border = thin_border
                log_ws.cell(row=row, column=5, value=team).border = thin_border
                log_ws.cell(row=row, column=6, value=time_elapsed).border = thin_border    # Time placeholder
                log_ws.cell(row=row, column=7, value=health).border = thin_border  # ✅ This will now have the correct value
                log_ws.cell(row=row, column=8, value=position).border = thin_border
                log_ws.cell(row=row, column=9, value=event).border = thin_border
                log_ws.cell(row=row, column=10, value=action_name).border = thin_border
                log_ws.cell(row=row, column=11, value=target_position).border = thin_border
                log_ws.cell(row=row, column=12, value=damage).border = thin_border
                log_ws.cell(row=row, column=13, value=heal).border = thin_border
                log_ws.cell(row=row, column=14, value=movement).border = thin_border
                log_ws.cell(row=row, column=15, value=target).border = thin_border
                log_ws.cell(row=row, column=16, value=target_health_before).border = thin_border
                log_ws.cell(row=row, column=17, value=target_health_after).border = thin_border
                log_ws.cell(row=row, column=18, value=target_team).border = thin_border
                step += 1
                row += 1

            # === MATCH SUMMARY SHEET ===
            summary_ws.column_dimensions['A'].width = 25
            summary_ws.column_dimensions['B'].width = 35
            title_cell = summary_ws.cell(1, 1, "Match Summary")
            title_cell.font = summary_title_font
            title_cell.fill = summary_title_fill
            summary_ws.merge_cells('A1:B1')
            row = 2
            winner = "Team 1" if self.total_p1_win > self.total_p2_win else "Team 2"
            summary_ws.cell(row, 1, f"Winner: {winner}").font = Font(bold=True)
            row += 1
            # FIX: Total Matches Played = completed matches
            total_matches_played = max(0, self.currentMatch - 1)
            summary_ws.cell(row, 1, f"Total Matches Played: {total_matches_played}").font = Font(bold=True)
            row += 1
            # Add Total Match Time
            summary_ws.cell(row, 1, f"Total Match Time (seconds): {self.last_match_duration:.2f}").font = Font(bold=True)
            row += 1
            # Add Win Rates
            team1_win_rate = (self.total_p1_win / total_matches_played * 100) if total_matches_played > 0 else 0.0
            team2_win_rate = (self.total_p2_win / total_matches_played * 100) if total_matches_played > 0 else 0.0
            summary_ws.cell(row, 1, f"Team 1 Win Rate: {team1_win_rate:.2f}%").font = Font(bold=True)
            row += 1
            summary_ws.cell(row, 1, f"Team 2 Win Rate: {team2_win_rate:.2f}%").font = Font(bold=True)
            row += 1
            summary_ws.cell(row, 1, f"Team 1 Wins: {self.total_p1_win}").font = Font(bold=True)
            row += 1
            summary_ws.cell(row, 1, f"Team 2 Wins: {self.total_p2_win}").font = Font(bold=True)
            row += 1
            summary_ws.cell(row, 1, "Damage Dealt:").font = Font(bold=True)
            row += 1
            summary_ws.cell(row, 1, "- Team 1:"); summary_ws.cell(row, 2, f"{team1_damage_given}")
            row += 1
            summary_ws.cell(row, 1, "- Team 2:"); summary_ws.cell(row, 2, f"{team2_damage_given}")
            row += 1
            summary_ws.cell(row, 1, "Kills:").font = Font(bold=True)
            row += 1
            summary_ws.cell(row, 1, "- Team 1:"); summary_ws.cell(row, 2, f"{team1_kills}")
            row += 1
            summary_ws.cell(row, 1, "- Team 2:"); summary_ws.cell(row, 2, f"{team2_kills}")
            row += 1
            if kill_details:
                summary_ws.cell(row, 1, "Kill Details:").font = Font(bold=True)
                row += 1
                for detail in kill_details:
                    summary_ws.cell(row, 1, detail)
                    row += 1

            # Save
            export_dir = "exports"
            os.makedirs(export_dir, exist_ok=True)
            filename = f"{export_dir}/game_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            wb.save(filename)
            print(f"Game log exported to: {filename}")

        except Exception as e:
            print(f"Error exporting game log: {e}")
            import traceback
            traceback.print_exc()
                
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
