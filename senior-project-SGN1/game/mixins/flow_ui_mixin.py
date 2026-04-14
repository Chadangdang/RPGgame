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

from game.balance import balance_controller
from game.session_limits import SessionProgress, apply_match_result

AI_SELECTION_LABELS = (
    'Player Input',
    'Baseline AI',
    'Random AI',
    'Personality Cores AI',
    'Aggressive Personality Cores AI',
    'Strategic Personality Cores AI',
    'Survival Personality Cores AI',
    'Kill One By One AI',
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

class GameMainFlowUiMixin:
    def _set_start_alert(self, message: str, duration_ms: int = 3600) -> None:
        self._start_alert_message = message
        self._start_alert_until = pygame.time.get_ticks() + duration_ms

    def _parse_limit_input(self, raw_value: str) -> int | None:
        text = str(raw_value).strip()
        if not text:
            return None
        try:
            return int(text)
        except (TypeError, ValueError):
            return None

    def _sync_limit_values_from_inputs(self) -> tuple[int | None, int | None]:
        game_input = self._parse_limit_input(self._game_limit_input)
        match_input = self._parse_limit_input(self._match_limit_input)
        if game_input is not None:
            self.game_limit = game_input
        if match_input is not None:
            self.match_limit = match_input
        return game_input, match_input

    def _attempt_start_session(self) -> bool:
        game_input, match_input = self._sync_limit_values_from_inputs()
        if game_input is None or match_input is None or self.game_limit < 1 or self.match_limit < 1:
            self._set_start_alert(
                "Game Limit, Match limit have to be number and >=1 user have to edit it first"
            )
            return False
        self._start_alert_message = ''
        self.screen1init()
        return True

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
        self.current_match = 0
        self.current_game = 1
        self.current_round = 1
        self.game_p1_match_wins = 0
        self.game_p2_match_wins = 0
        self.total_games_p1 = 0
        self.total_games_p2 = 0
        self.session_over = False
        self.total_p1_win = 0
        self.total_p2_win = 0
        self.p1_round_wins = 0
        self.p2_round_wins = 0
        self._current_map_label = ''
        self._char_snapshots = {}
        self._sb_dragging = False
        self._game_summary_logged = False

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
        self.current_match = 0
        self.current_game = 1
        self.current_round = 1
        self.game_p1_match_wins = 0
        self.game_p2_match_wins = 0
        self.total_games_p1 = 0
        self.total_games_p2 = 0
        self.session_over = False
        self.total_p1_win = 0
        self.total_p2_win = 0
        self.p1_round_wins = 0
        self.p2_round_wins = 0
        self._current_map_label = ''
        self._game_summary_logged = False
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
                if self._pause_selected_idx is None:
                    self._pause_selected_idx = 0
                self._pause_selected_idx = (self._pause_selected_idx - 1) % 3
            elif event.key == pygame.K_RIGHT:
                if self._pause_selected_idx is None:
                    self._pause_selected_idx = 0
                self._pause_selected_idx = (self._pause_selected_idx + 1) % 3
            elif event.key == pygame.K_z:
                if self._pause_selected_idx is None:
                    self._pause_selected_idx = 0
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

        # Yellow highlight for pause button (keyboard selection only)
        if self._pause_selected_idx is not None:
            selected_rect = [
                self.pause_resume_button_rect,
                self.pause_restart_button_rect,
                self.pause_menu_button_rect,
            ][self._pause_selected_idx]
            pygame.draw.rect(self.screen, YELLOW, selected_rect, 4)

    def _selected_balance_mode(self) -> str:
        if self._balance_option_states[1]:
            return balance_controller.PASSIVE
        if self._balance_option_states[2]:
            return balance_controller.WEAKNESS
        if self._balance_option_states[3]:
            return balance_controller.COMBINED
        return balance_controller.BASELINE

    def _is_weakness_system_enabled(self) -> bool:
        return self.settings.balance_mode in (balance_controller.WEAKNESS, balance_controller.COMBINED)

    def _fireball_burn_mode(self) -> str:
        if self.settings.balance_mode == balance_controller.COMBINED:
            return 'new_stats_weakness'
        if self.settings.balance_mode == balance_controller.PASSIVE:
            return 'new_stats_only'
        return 'default'

    def _apply_new_stats_balance(self) -> None:
        for chara in Character.team1_list + Character.team2_list:
            chara.template = balance_controller.adjust_template_stats(chara.template)
            chara.movement = chara.template.get('movement', chara.movement)

    def _handle_completed_match(self, winner_label: str) -> dict:
        """Update match/game/session counters and return transition flags."""
        try:
            safe_match_limit = max(1, int(self.match_limit))
        except (TypeError, ValueError):
            safe_match_limit = 1
        try:
            safe_game_limit = max(1, int(self.game_limit))
        except (TypeError, ValueError):
            safe_game_limit = 1
        state = SessionProgress(
            current_game=self.current_game,
            current_match=self.current_match,
            match_limit=safe_match_limit,
            game_limit=safe_game_limit,
            game_p1_match_wins=self.game_p1_match_wins,
            game_p2_match_wins=self.game_p2_match_wins,
            total_games_p1=self.total_games_p1,
            total_games_p2=self.total_games_p2,
            total_p1_win=self.total_p1_win,
            total_p2_win=self.total_p2_win,
        )
        result = apply_match_result(state, winner_label)

        self.current_game = state.current_game
        self.current_match = state.current_match
        self.currentMatch = state.current_match
        self.game_p1_match_wins = state.game_p1_match_wins
        self.game_p2_match_wins = state.game_p2_match_wins
        self.total_games_p1 = state.total_games_p1
        self.total_games_p2 = state.total_games_p2
        self.total_p1_win = state.total_p1_win
        self.total_p2_win = state.total_p2_win
        if result['session_finished']:
            self.session_over = True

        return result

    def _selection_row_to_team_id(self, row_index: int) -> int:
        row_to_team = {
            0: 0,  # Player Input
            1: 1,  # Baseline AI
            2: 2,  # Random AI
            3: 3,  # Personality Cores AI
            4: 4,  # Aggressive Personality Cores AI
            5: 5,  # Strategic Personality Cores AI
            6: 6,  # Survival Personality Cores AI
            7: 7,  # Kill One By One AI (Hard)
            8: 8,  # Disable AI
        }
        return row_to_team.get(int(row_index), 0)

    def screen1init(self):
        self.game_limit = max(self._game_limit_min, self.game_limit)
        self.match_limit = max(self._match_limit_min, self.match_limit)

        p1_row = self.p1_sel_cursor.grid[0]
        p2_row = self.p2_sel_cursor.grid[0]
        self.team1_ID = self._selection_row_to_team_id(p1_row)
        self.team2_ID = self._selection_row_to_team_id(p2_row)
        p1_label = self._ai_type_labels[p1_row] if 0 <= p1_row < len(self._ai_type_labels) else 'Unknown'
        p2_label = self._ai_type_labels[p2_row] if 0 <= p2_row < len(self._ai_type_labels) else 'Unknown'
        print(f'{p1_label} vs {p2_label}')

        self.currentMatch = 0
        self.current_match = 0
        self.current_game = 1
        self.current_round = 1
        self.game_p1_match_wins = 0
        self.game_p2_match_wins = 0
        self.total_games_p1 = 0
        self.total_games_p2 = 0
        self.session_over = False
        self.total_p1_win = 0
        self.total_p2_win = 0
        self._game_summary_logged = False

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
        if self.session_over:
            return

        if self.current_match == 0:
            self.log_event("game_start", game=self.current_game, time_elapsed=self.cumulative_time)

        self.current_match += 1
        self.currentMatch = self.current_match
        self.cumulative_time = 0.0

        self.settings.balance_mode = self._selected_balance_mode()
        balance_controller.load_balance_mode(self.settings.balance_mode)

        Character.setWeaknessSystem(self._is_weakness_system_enabled())
        Character.setFireballBurnMode(self._fireball_burn_mode())

        self._ai_log_len = {}
        self._ai_pending_lines.clear()
        self._pending_ko_sources = {}
        self._pending_ko_sources_by_name = {}
        self.p1_round_wins = 0
        self.p2_round_wins = 0

        self.obj_control_team1 = 0
        self.obj_control_team2 = 0

        ai1_name = self._get_ai_label(self.team1_ID)
        ai2_name = self._get_ai_label(self.team2_ID)

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

        self._apply_new_stats_balance()

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
        try:
            print(f"Debug: AI_list length={len(GM.AI_list)}; AI names={[c.__name__ for c in GM.AI_list]}")
        except Exception:
            print("Debug: could not read GM.AI_list")
        print(f"Debug: selected team1_ID={self.team1_ID}, team2_ID={self.team2_ID}")

        try:
            ai_count = len(GM.AI_list)
        except Exception:
            ai_count = 0

        if not isinstance(self.team1_ID, int) or self.team1_ID < 0 or self.team1_ID >= ai_count:
            print(f"Warning: team1_ID {self.team1_ID} out of range, defaulting to 0")
            self.team1_ID = 0
        if not isinstance(self.team2_ID, int) or self.team2_ID < 0 or self.team2_ID >= ai_count:
            print(f"Warning: team2_ID {self.team2_ID} out of range, defaulting to 0")
        try:
            self.GameMaster.setTeams(self.team1_ID, self.team2_ID)
            self.GameMaster.team1.loadField(self.field)
            self.GameMaster.team2.loadField(self.field)
        except Exception as e:
            print(f"Error setting up AIs: {e}")
            print("Falling back to human players (Player Input)")
            try:
                self.team1_ID = 0
                self.team2_ID = 0
                self.GameMaster.setTeams(0, 0)
                self.GameMaster.team1.loadField(self.field)
                self.GameMaster.team2.loadField(self.field)
            except Exception as e2:
                print(f"Fallback also failed: {e2}")

        Cursor.state = 0 if self.GameMaster.isActiveAIHuman() else 6
        Cursor.state = 5
        Cursor.selected_action = -1

        self.round = 1
        self.current_round = 1
        self.round_title_timer = 0
        self.number_action = -1
        self.action_timer = 0
        self.p1_dom_count = 0
        self.p2_dom_count = 0

        self.action_delay = 0 if self.isAuto else 0.8

        map_label = str(getattr(getattr(self.field, 'map', None), 'map_name', ''))
        if not map_label:
            map_label = 'Unknown'
        self._current_map_label = map_label

        self.log_event('match_start',
                       game=self.current_game,
                       match=self.current_match,
                       map_label=map_label,
                       ai1=ai1_name,
                       ai2=ai2_name,
                       time_elapsed=self.cumulative_time)

        self.log_event('round_begin',
                       round=self.round,
                       time_elapsed=self.cumulative_time)

        self._init_character_snapshots()
        self.log_scroll = 0
