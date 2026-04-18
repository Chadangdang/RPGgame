import random
import pygame
import sys
from Constants import *
from Field import Field
from Character import Character
from Cursor import *
import numpy as np
import AI
from GameMaster import GameMaster
import GameMaster as GM
from MapData import MapData
import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from datetime import datetime
import os
from tkinter import Tk, filedialog
from types import SimpleNamespace
from insert.Ai_insertion_instruction import AI_INSERTION_INSTRUCTION
from insert import ai_import_manager

from game.balance import balance_controller

def AI_SELECTION_LABELS() -> list[str]:
    return GM.get_ai_labels()



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

class GameMainInitMixin:
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

        ai_choice_count = len(AI_SELECTION_LABELS())
        self.menu_cursor = HoverMenuCursor(self.screen, (420, 60), (ai_choice_count, 2))
        self.p1_sel_cursor = SelectMenuCursor(self.screen, (420, 60), (ai_choice_count, 1))
        self.p2_sel_cursor = SelectMenuCursor(self.screen, (420, 60), (ai_choice_count, 1))

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
        # Model selector layout/state (AI selection page)
        self._model_box_w = 298
        self._model_box_h = 66
        self._model_box_gap = 89
        self._model_list_top = 259
        self._model_left_x = 154
        self._model_right_x = 756
        self._model_visible_rows = 5
        self._model_scroll_offset = [0, 0]
        self._model_scroll_dragging = [False, False]  # [left, right]
        self._model_scroll_drag_offset = [0, 0]
        self._model_sb_dragging_left = False
        self._model_sb_dragging_right = False
        # Buttons for model selection (under AI choices)
        self._model_btn_p1 = pygame.Rect(360, 590, 260, 40)
        self._model_btn_p2 = pygame.Rect(630, 590, 260, 40)
        self._start_button_rect = pygame.Rect(WIDTH // 2 - 130, 740, 260, 64)

        # Keyboard navigation focus: 'model_list' | 'settings' | 'start' | 'map_selection'
        self._kb_focus = 'model_list'

        # Settings popup (inside AI selection screen)
        self._settings_button_rect = pygame.Rect(WIDTH - 190, 22, 150, 52)
        self._settings_button_hovered = False
        self._settings_popup_open = False
        self._settings_popup_page = 'main'  # 'main' | 'balance'
        settings_popup_w, settings_popup_h = 1063, 907
        settings_popup_x = (WIDTH - settings_popup_w) // 2
        settings_popup_y = (HEIGHT - settings_popup_h) // 2
        self._settings_popup_rect = pygame.Rect(settings_popup_x, settings_popup_y, settings_popup_w, settings_popup_h)

        self._settings_main_balance_button_rect = pygame.Rect(
            self._settings_popup_rect.x + 140,
            self._settings_popup_rect.y + 210,
            self._settings_popup_rect.width - 280,
            92,
        )
        self._settings_main_resolution_button_rect = pygame.Rect(
            self._settings_popup_rect.x + 140,
            self._settings_popup_rect.y + 330,
            self._settings_popup_rect.width - 280,
            92,
        )
        self._settings_sub_back_rect = pygame.Rect(
            self._settings_popup_rect.x + 44,
            self._settings_popup_rect.y + 34,
            130,
            50,
        )
        self._settings_close_rect = pygame.Rect(
            self._settings_popup_rect.right - 92,
            self._settings_popup_rect.y + 24,
            48,
            48,
        )

        self._balance_option_labels = [
            'Baseline',
            'Passive-Enhanced',
            'Weakness-Based',
            'Combined Mode',
        ]
        self._balance_option_colors = [
            (0, 0, 0),
            (39, 174, 96),
            (66, 66, 245),
            (0, 0, 0),
        ]
        self._balance_option_states = [True, False, False, False]
        self._balance_option_row_rects = [
            pygame.Rect(self._settings_popup_rect.x + 140, self._settings_popup_rect.y + 205, self._settings_popup_rect.width - 280, 92),
            pygame.Rect(self._settings_popup_rect.x + 140, self._settings_popup_rect.y + 330, self._settings_popup_rect.width - 280, 92),
            pygame.Rect(self._settings_popup_rect.x + 140, self._settings_popup_rect.y + 455, self._settings_popup_rect.width - 280, 92),
            pygame.Rect(self._settings_popup_rect.x + 140, self._settings_popup_rect.y + 580, self._settings_popup_rect.width - 280, 92),
        ]
        self._balance_checkbox_rects = [
            pygame.Rect(self._balance_option_row_rects[0].x + 18, self._balance_option_row_rects[0].y + 31, 30, 30),
            pygame.Rect(self._balance_option_row_rects[1].x + 18, self._balance_option_row_rects[1].y + 31, 30, 30),
            pygame.Rect(self._balance_option_row_rects[2].x + 18, self._balance_option_row_rects[2].y + 31, 30, 30),
            pygame.Rect(self._balance_option_row_rects[3].x + 18, self._balance_option_row_rects[3].y + 31, 30, 30),
        ]
        self._balance_keyboard_index = 0

        self.settings = SimpleNamespace(balance_mode=balance_controller.BASELINE)
        balance_controller.load_balance_mode(self.settings.balance_mode)

        self.game_state = 'selecting start area'

        self.total_p1_win = 0
        self.total_p2_win = 0
        self.total_games_p1 = 0
        self.total_games_p2 = 0
        self.game_p1_match_wins = 0
        self.game_p2_match_wins = 0
        self.current_game = 1
        self.current_match = 0
        self.current_round = 1
        self.session_over = False
        self.p1_round_wins = 0
        self.p2_round_wins = 0
        self._current_map_label = ''

        # Fonts
        self.font_ss = pygame.font.Font('resource/font.ttf', 14)
        self.font_s = pygame.font.Font('resource/font.ttf', 24)
        self.font_sm = pygame.font.Font('resource/font.ttf', 30)
        self.font_model_select = pygame.font.Font('resource/font.ttf', 25)
        self.font_model_select_sub = pygame.font.Font('resource/font.ttf', 20)
        self.font_m = pygame.font.Font('resource/font.ttf', 48)
        self.font_l = pygame.font.Font('resource/font.ttf', 96)
        self.font_end_title = pygame.font.Font('resource/font.ttf', 74)
        self.font_end_button = pygame.font.Font('resource/font.ttf', 24)
        self.font_menu_label = pygame.font.Font('resource/font.ttf', 26)
        self.font_register_desc = pygame.font.Font('resource/font.ttf', 18)
        self._instr_text_font = pygame.font.Font('resource/font.ttf', 20)

        # --- Map selection UI geometry/state ---
        self._map_select_button_rect = pygame.Rect(995, 903, 220, 48)
        self._map_preview_thumb_rect = pygame.Rect(800, 853, 151, 150)

        # Import AI button (bottom-left on AI select screen)
        self._import_ai_button_rect = pygame.Rect(40, 903, 220, 48)
        self._import_ai_button_hovered = False
        self._import_popup_open = False
        self._import_modal_rect = pygame.Rect((WIDTH - 760) // 2, (HEIGHT - 340) // 2, 760, 340)
        self._import_modal_close_rect = pygame.Rect(self._import_modal_rect.right - 52, self._import_modal_rect.y + 16, 34, 34)
        import_modal_btn_w = 300
        import_modal_btn_h = 54
        import_modal_btn_gap = 40
        import_btn_total_w = import_modal_btn_w * 2 + import_modal_btn_gap
        import_btn_start_x = self._import_modal_rect.x + (self._import_modal_rect.width - import_btn_total_w) // 2
        import_btn_y = self._import_modal_rect.y + 198
        self._import_modal_download_rect = pygame.Rect(import_btn_start_x, import_btn_y, import_modal_btn_w, import_modal_btn_h)
        self._import_modal_upload_rect = pygame.Rect(import_btn_start_x + import_modal_btn_w + import_modal_btn_gap, import_btn_y, import_modal_btn_w, import_modal_btn_h)

        self._register_popup_open = False
        self._register_modal_rect = pygame.Rect((WIDTH - 760) // 2, (HEIGHT - 520) // 2, 760, 520)
        self._register_close_rect = pygame.Rect(self._register_modal_rect.right - 52, self._register_modal_rect.y + 16, 34, 34)
        self._register_name_rect = pygame.Rect(self._register_modal_rect.x + 48, self._register_modal_rect.y + 112, 664, 44)
        self._register_desc_rect = pygame.Rect(self._register_modal_rect.x + 48, self._register_modal_rect.y + 208, 664, 84)
        self._register_file_rect = pygame.Rect(self._register_modal_rect.x + 48, self._register_modal_rect.y + 328, 220, 48)
        self._register_submit_rect = pygame.Rect(self._register_modal_rect.right - 248, self._register_modal_rect.bottom - 72, 200, 48)
        self._register_active_field: str | None = None
        self._register_name_input = ''
        self._register_desc_input = ''
        self._register_file_path = ''
        # Circular Instructions button placed to the right of Import AI
        instr_x = self._import_ai_button_rect.right + 16
        instr_y = self._import_ai_button_rect.y
        self._instr_button_rect = pygame.Rect(instr_x, instr_y, 48, 48)  # square hitbox for circle
        self._instr_button_hovered = False
        # Instructions popup state + geometry
        self._instr_popup_open = False
        instr_w, instr_h = 1063, 907
        instr_x = (WIDTH - instr_w) // 2
        instr_y = (HEIGHT - instr_h) // 2
        self._instr_popup_rect = pygame.Rect(instr_x, instr_y, instr_w, instr_h)
        self._instr_popup_close_rect = pygame.Rect(self._instr_popup_rect.right - 56, self._instr_popup_rect.y + 16, 36, 36)
        # Load README/instructions into memory for display
        try:
            with open(os.path.join(os.getcwd(), 'README.md'), 'r', encoding='utf-8') as f:
                self._instr_lines = [ln.rstrip() for ln in f.readlines()]
        except Exception:
            self._instr_lines = [
                '',
                'AI Import Instructions.',
                '',
                '1. Click the "Import AI" button to open the AI selection dialog.',
                '2. Choose an AI model from the list.',
                '3. Click "Select" to apply the chosen AI model.',
            ]

        # Instruction popup supports three pages: 'game', 'import', and 'ai'
        self._instr_page = 'game'  # 'game' | 'import'
        # Import instructions come from a dedicated insertion guide.
        self._instr_import_lines = [ln.rstrip() for ln in AI_INSERTION_INSTRUCTION.strip('\n').splitlines()]
        # Basic game instructions (kept here so popup has two pages)
        self._instr_game_lines = [
            'GAME INSTRUCTION',
            '',
            'Controls:',
            ' - Arrow Keys : Navigate the game.',
            ' - Z / Left Click : Select',
            ' - X / Right Click : Cancel',
            ' - M : Change the map',
            ' - T : Toggle resolution',
            ' - Enter : Start the game',
            ' - Esc : Exit the game or pause during a match',
            '',
            'Pre-Game:',
            ' - Select player types, game mode, iteration, and map to start.',
            ' - Use the setting to change game mode and number of games and matches.',
            ' - You can change the number of games and matches by',
            '   typing the desired values in the text boxes ( >= 1 ).',
            '',
            '        Game Limit ( >= 1 )',
            '           - A game is a full set of matches',
            '           - The game limit sets how many games are played in the entire session..',
            '             Once the games have been completed, the session ends.',
            '',
            '        Match Limit ( >= 1 )',
            '           - A match is a single battle on the board, one fight to completion',
            '             (all enemies defeated or objective captured).',
            '           - The match limit sets how many matches make up one game.',
            '',
            'Gameplay:',
            ' - Select units, move and use actions to defeat the enemy.',
            ' - Capture the objective area to win the match.',
            ' - The exported session result will be stored on desktop',
            '   in the folder named "RPG Simulation Export".',
        ]
        # AI description page (brief descriptions for available AI types)
        self._instr_ai_lines_base = [
            'AI DESCRIPTION',
            '',
            'Player Input: Human control via mouse/keyboard.',
            '',
            'PerfectPlay (Baseline): Deterministic heatmap AI that evaluates every reachable tile and action combination to pick the highest-value option.',
            '  - Enemy Threat Map: Estimates how dangerous each tile is based on potential enemy damage; discourages risky tiles.',
            '  - Objective Map: Smooth gradient that rewards proximity to objective tiles, encouraging contesting control.',
            '  - Destination Map: Combines damage dealt, incoming threat, and objective proximity to rate reachable tiles; resolves conflicts by ordering unit claims.',
            '  - Turn Execution: Enumerates moves+actions and selects the best overall value; used as the performance baseline.',
            '',
            'Random: Stochastic model that selects valid moves and actions at random; serves as a lower-bound control.',
            '',
            'PersonalityCores: Baseline logic with dynamic weightings; selects a profile (Aggressive/Strategic/Survival) based on battlefield state to simulate varied playstyles.',
            '',
            '  Aggressive: High weight on Damage, moderate Objective, reduced Threat — prioritizes elimination and high-offense plays, accepts higher risk.',
            '',
            '  Strategic: Balanced weights across Damage/Objective/Threat — favors objective progress and positional stability for long-term advantage.',
            '',
            '  Survival: High weight on Threat, reduced Damage, moderate Objective — emphasizes safety, retreats on disadvantage, and prefers defensive/rescue actions.',
            '',
            'Kill One By One: Focus-fire strategy that uses threat assessment and projected HP tracking to secure kills efficiently without overkilling.',
            '',
            'Disable AI: Turns off AI control for a slot.',
        ]
        self._refresh_ai_description_lines()
        self._instr_scroll_by_page = {'game': 0, 'import': 0, 'ai': 0}
        self._instr_scroll_step = 28

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

        select_offset_x, select_offset_y = 420, 660
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

        # Match & Game limit numeric input geometry/state (inside Settings popup)
        self.match_limit = AUTO_MATCH_LIMIT
        self._match_limit_min = 1
        # position these relative to the settings popup so they render inside it
        base_x = self._settings_popup_rect.x + 140
        # place controls below the Toggle Resolution button for clearer grouping
        base_y = self._settings_main_resolution_button_rect.y + self._settings_main_resolution_button_rect.height + 24
        # label/value columns for neat alignment
        self._settings_label_x = base_x
        value_x = base_x + 260
        self._settings_value_x = value_x

        # Game limit (above match limit) — Auto row removed so controls start at base_y
        self.game_limit = AUTO_GAME_LIMIT
        self._game_limit_min = 1
        # number box inputs
        self._game_limit_box_rect = pygame.Rect(value_x, base_y, 170, 44)
        self._game_limit_input = str(self.game_limit)

        # Match limit (below game limit)
        self.match_limit = AUTO_MATCH_LIMIT
        self._match_limit_min = 1
        self._match_limit_box_rect = pygame.Rect(value_x, base_y + 78, 170, 44)
        self._match_limit_input = str(self.match_limit)
        self._active_limit_input: str | None = None
        self._start_alert_message = ''
        self._start_alert_until = 0

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
        self._pause_selected_idx = None  # 0=Resume, 1=Restart, 2=Menu; None until keyboard nav

        self.GameMaster = GameMaster()
        self.currentMatch = 0
        self._game_summary_logged = False

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
        # Action list scrolling (right panel, human player)
        self._action_list_scroll = 0
        self._action_list_scroll_step = 40
        self._action_list_active_chara_id: int | None = None
        self._action_sb_dragging = False
        self._action_sb_drag_offset_y = 0
        # Pause button
        self.pause_game_button_rect = pygame.Rect(40, 40, 260, 56)
        self.pause_game_button_hovered = False
        # --- Game Log store ---
        # store structured dict entries for reliable export + UI rendering metadata
        self.game_log: list[dict] = []
        # used to mirror newly-added lines from activeAI.action_log
        self._ai_log_len: dict[object, int] = {}
        self._ai_pending_lines: dict[int, list[str]] = {}
        self._char_snapshots: dict[int, dict] = {}
        self._ai_type_labels = AI_SELECTION_LABELS()
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
        
        self.obj_control_team1 = 0
        self.obj_control_team2 = 0

    def _open_file_picker(self) -> str:
        root = Tk()
        root.withdraw()
        root.attributes('-topmost', True)
        file_path = filedialog.askopenfilename(
            title='Select Python AI File',
            filetypes=[('Python files', '*.py')],
        )
        root.destroy()
        return file_path

    def _refresh_ai_selection_ui(self) -> None:
        labels = AI_SELECTION_LABELS()
        ai_choice_count = len(labels)
        self.menu_cursor = HoverMenuCursor(self.screen, (420, 60), (ai_choice_count, 2))
        self.p1_sel_cursor = SelectMenuCursor(self.screen, (420, 60), (ai_choice_count, 1))
        self.p2_sel_cursor = SelectMenuCursor(self.screen, (420, 60), (ai_choice_count, 1))
        self._ai_type_labels = labels
        self._refresh_ai_description_lines()

    def _refresh_ai_description_lines(self) -> None:
        lines = list(getattr(self, '_instr_ai_lines_base', []))
        custom_entries = [item for item in GM.get_ai_metadata() if item.get('name')]
        if custom_entries:
            lines.extend(['', 'TAP on first line'])
            for item in custom_entries:
                name = str(item.get('name', '')).strip()
                desc = str(item.get('description', '')).strip() or 'No description provided.'
                lines.append(f'{name} (custom AI): {desc}')
        self._instr_ai_lines = lines

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

    def _open_exports_folder(self) -> None:
        """Open the workspace 'exports' folder so the user can drop/import AI files."""
        exports_dir = os.path.join(os.getcwd(), 'exports')
        try:
            os.makedirs(exports_dir, exist_ok=True)
            if sys.platform.startswith('win'):
                os.startfile(exports_dir)
            else:
                # Fallback: try to open with default file manager
                import webbrowser
                webbrowser.open(exports_dir)
        except Exception:
            print('Could not open exports folder:', exports_dir)

    def _open_instructions(self) -> None:
        """Open the project's README (instructions) for the user."""
        readme = os.path.join(os.getcwd(), 'README.md')
        try:
            if os.path.exists(readme):
                if sys.platform.startswith('win'):
                    os.startfile(readme)
                else:
                    import webbrowser
                    webbrowser.open('file://' + readme)
            else:
                # Fallback to opening workspace root
                root = os.getcwd()
                if sys.platform.startswith('win'):
                    os.startfile(root)
                else:
                    import webbrowser
                    webbrowser.open(root)
        except Exception:
            print('Could not open instructions file or folder:', readme)

    def _scale_for_laptop(self) -> float:
        """Calculate a scale so the window is strictly smaller than 1280x1040."""
        max_w, max_h = 1280, 1040
        # Compute the largest scale that fits within the bounds
        s = min(max_w / float(WIDTH), max_h / float(HEIGHT), 1.0)
        # Nudge a tiny bit smaller to be strictly under the limits
        s = min(s, 0.75)
        return max(0.5, s)

    def _toggle_resolution(self) -> None:
        """Toggle between full size and laptop-friendly size."""
        if self.scale < 0.99:
            self._apply_scale(1.0)
        else:
            self._apply_scale(self._scale_for_laptop())

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
            if event.key == pygame.K_x:
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
            if event.key == pygame.K_t:
                self._toggle_resolution()
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
