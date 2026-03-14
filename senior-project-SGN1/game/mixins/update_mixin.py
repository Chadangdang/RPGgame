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

AI_SELECTION_LABELS = (
    'Player Input',
    'Baseline AI',
    'Random AI',
    'Personality Cores AI',
    'Aggressive',
    'Strategic',
    'Survival',
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

class GameMainUpdateMixin:
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
                        self._toggle_resolution()

        elif self.game_screen == 0:       # AI select screen
            if not self._map_popup_open:
                self._map_popup_temp_selection = self._clamp_map_index(self.map_number)
                self._map_popup_hover_index = None

            # Keep cursor bounds in sync with model count
            total_rows = len(AI_SELECTION_LABELS)
            self.menu_cursor.bound = (total_rows, 2)
            self.p1_sel_cursor.bound = (total_rows, 1)
            self.p2_sel_cursor.bound = (total_rows, 1)

            # Geometry for hit-tests
            left_origin = self._model_column_origin(True)
            right_origin = self._model_column_origin(False)
            list_h = self._model_track_height()
            list_rect_left = pygame.Rect(left_origin[0], left_origin[1], self._model_box_w, list_h)
            list_rect_right = pygame.Rect(right_origin[0], right_origin[1], self._model_box_w, list_h)
            left_thumb = self._model_thumb_rect(True)
            right_thumb = self._model_thumb_rect(False)


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

                if self._settings_popup_open:
                    if event.type == pygame.KEYDOWN:
                        if event.key == pygame.K_ESCAPE:
                            self._settings_popup_open = False
                            self._settings_popup_page = 'main'
                            continue
                        if self._settings_popup_page == 'balance':
                            if event.key in (pygame.K_UP, pygame.K_DOWN):
                                if event.key == pygame.K_UP:
                                    self._balance_keyboard_index = (self._balance_keyboard_index - 1) % len(self._balance_option_row_rects)
                                else:
                                    self._balance_keyboard_index = (self._balance_keyboard_index + 1) % len(self._balance_option_row_rects)
                                continue
                            if event.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_z, pygame.K_x):
                                self._balance_option_states = [i == self._balance_keyboard_index for i in range(len(self._balance_option_states))]
                                self.settings.balance_mode = self._selected_balance_mode()
                                balance_controller.load_balance_mode(self.settings.balance_mode)
                                print("=== BALANCE MODE CHANGED ===")
                                print("Now using:", self.settings.balance_mode)
                                continue

                    if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                        if self._settings_close_rect.collidepoint(event.pos):
                            self._settings_popup_open = False
                            self._settings_popup_page = 'main'
                            continue
                        if not self._settings_popup_rect.collidepoint(event.pos):
                            self._settings_popup_open = False
                            self._settings_popup_page = 'main'
                            continue

                        if self._settings_popup_page == 'main':
                            if self._settings_main_balance_button_rect.collidepoint(event.pos):
                                self._settings_popup_page = 'balance'
                                continue
                            if self._settings_main_resolution_button_rect.collidepoint(event.pos):
                                self._toggle_resolution()
                                continue
                            continue

                        if self._settings_sub_back_rect.collidepoint(event.pos):
                            self._settings_popup_page = 'main'
                            continue

                        for idx, row_rect in enumerate(self._balance_option_row_rects):
                            if row_rect.collidepoint(event.pos):
                                self._balance_option_states = [i == idx for i in range(len(self._balance_option_states))]
                                self._balance_keyboard_index = idx
                                self.settings.balance_mode = self._selected_balance_mode()
                                balance_controller.load_balance_mode(self.settings.balance_mode)
                                print("=== BALANCE MODE CHANGED ===")
                                print("Now using:", self.settings.balance_mode)
                                break
                        continue
                    if event.type in (pygame.MOUSEBUTTONUP, pygame.MOUSEMOTION, pygame.MOUSEWHEEL):
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
                        # auto-scroll keyboard focus into view (per player column)
                        row, col = self.menu_cursor.grid
                        col_idx = 0 if col == 0 else 1
                        if row < self._model_scroll_offset[col_idx]:
                            self._model_scroll_offset[col_idx] = row
                        elif row >= self._model_scroll_offset[col_idx] + self._model_visible_rows:
                            self._model_scroll_offset[col_idx] = row - self._model_visible_rows + 1
                        self._model_scroll_offset[col_idx] = max(0, min(self._model_scroll_offset[col_idx], self._model_max_offset()))

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

                mouse_pos = pygame.mouse.get_pos()

                if event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == 1:
                        if self._start_button_rect.collidepoint(event.pos) and self.p1_sel_cursor.show and self.p2_sel_cursor.show:
                            self.screen1init()
                            continue
                        if self._settings_button_rect.collidepoint(event.pos):
                            self._settings_popup_open = not self._settings_popup_open
                            self._settings_popup_page = 'main'
                            # cancel any active dragging when opening settings
                            self._match_limit_slider_dragging = False
                            self._game_limit_slider_dragging = False
                            continue
                        if (self._map_select_button_rect.collidepoint(event.pos) or self._map_preview_thumb_rect.collidepoint(event.pos)):
                            self._map_popup_open = True
                            self._map_popup_temp_selection = self._clamp_map_index(self.map_number)
                            self._map_popup_hover_index = None
                            self._map_popup_select_hovered = False
                            # cancel any active dragging
                            self._match_limit_slider_dragging = False
                            self._game_limit_slider_dragging = False
                            continue
                        # Game slider (higher on UI)
                        if hasattr(self, "_game_limit_slider_rect") and self._game_limit_slider_rect.collidepoint(event.pos):
                            self._game_limit_slider_dragging = True
                            if hasattr(self, "_game_limit_value_from_pos"):
                                self.game_limit = self._game_limit_value_from_pos(event.pos[0])
                            continue
                        # Match slider
                        if hasattr(self, "_match_limit_slider_rect") and self._match_limit_slider_rect.collidepoint(event.pos):
                            self._match_limit_slider_dragging = True
                            if hasattr(self, "_match_limit_value_from_pos"):
                                self.match_limit = self._match_limit_value_from_pos(event.pos[0])
                            continue

                        # Scrollbar thumbs
                        if self._model_thumb_rect(True).collidepoint(mouse_pos):
                            self._model_sb_dragging_left = True

                        if self._model_thumb_rect(False).collidepoint(mouse_pos):
                            self._model_sb_dragging_right = True

                        # Scrollbar track clicks jump to position
                        elif self._model_track_rect(True).collidepoint(event.pos):
                            self._model_scroll_offset[0] = self._model_offset_from_thumb(event.pos[1], True)
                        elif self._model_track_rect(False).collidepoint(event.pos):
                            self._model_scroll_offset[1] = self._model_offset_from_thumb(event.pos[1], False)
                        self._model_scroll_offset[0] = max(0, min(self._model_scroll_offset[0], self._model_max_offset()))
                        self._model_scroll_offset[1] = max(0, min(self._model_scroll_offset[1], self._model_max_offset()))

                        # Clickable AI choices (both columns)
                        mx, my = event.pos
                        def _pick_from_list(is_left: bool) -> bool:
                            for real_idx, row_rect in self._model_row_rects(is_left):
                                if row_rect.collidepoint(mx, my):
                                    if is_left:
                                        self.p1_sel_cursor.moveTo((real_idx, 0))
                                        self.p1_sel_cursor.show = True
                                        self.menu_cursor.moveTo((real_idx, 0))
                                    else:
                                        self.p2_sel_cursor.moveTo((real_idx, 1))
                                        self.p2_sel_cursor.show = True
                                        self.menu_cursor.moveTo((real_idx, 1))
                                    return True
                            return False

                        if not _pick_from_list(True):
                            _pick_from_list(False)

                elif event.type == pygame.MOUSEBUTTONUP:
                    self._model_sb_dragging_left = False
                    self._model_sb_dragging_right = False
                    if event.button == 1:
                        self._model_scroll_dragging = [False, False]
                        if hasattr(self, "_match_limit_slider_dragging") and self._match_limit_slider_dragging:
                            self._match_limit_slider_dragging = False
                        if hasattr(self, "_game_limit_slider_dragging") and self._game_limit_slider_dragging:
                            self._game_limit_slider_dragging = False

                elif event.type == pygame.MOUSEMOTION:

                    if self._model_sb_dragging_left:
                        new_offset = self._model_offset_from_thumb(mouse_pos[1], True)
                        self._model_scroll_offset[0] = new_offset

                    if self._model_sb_dragging_right:
                        new_offset = self._model_offset_from_thumb(mouse_pos[1], False)
                        self._model_scroll_offset[1] = new_offset

                    if hasattr(self, "_game_limit_slider_dragging") and self._game_limit_slider_dragging:
                        if hasattr(self, "_game_limit_value_from_pos"):
                            self.game_limit = self._game_limit_value_from_pos(event.pos[0])
                    elif hasattr(self, "_match_limit_slider_dragging") and self._match_limit_slider_dragging:
                        if hasattr(self, "_match_limit_value_from_pos"):
                            self.match_limit = self._match_limit_value_from_pos(event.pos[0])
                    else:
                        for idx, dragging in enumerate(self._model_scroll_dragging):
                            if dragging:
                                center_y = event.pos[1] - self._model_scroll_drag_offset[idx]
                                self._model_scroll_offset[idx] = self._model_offset_from_thumb(center_y, idx == 0)
                    self._model_scroll_offset[0] = max(0, min(self._model_scroll_offset[0], self._model_max_offset()))
                    self._model_scroll_offset[1] = max(0, min(self._model_scroll_offset[1], self._model_max_offset()))

                if event.type == pygame.MOUSEWHEEL:
                    mx, my = pygame.mouse.get_pos()
                    if list_rect_left.collidepoint(mx, my):
                        self._model_scroll_offset[0] -= event.y
                        self._model_scroll_offset[0] = max(0, min(self._model_scroll_offset[0], self._model_max_offset()))
                    elif list_rect_right.collidepoint(mx, my):
                        self._model_scroll_offset[1] -= event.y
                        self._model_scroll_offset[1] = max(0, min(self._model_scroll_offset[1], self._model_max_offset()))


        elif self.game_screen == 1:
            self.cumulative_time += dt
            log_content_width = self._log_content_width()
            wrapped_log_lines = self._wrap_game_log_lines(log_content_width)
            geom = self._calc_log_geometry(total_log_lines=len(wrapped_log_lines))
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

            # Keep action-list scroll bounded and reset when focused unit changes
            action_chara = self._get_action_list_chara()
            action_chara_id = action_chara.id if action_chara is not None else None
            if action_chara_id != self._action_list_active_chara_id:
                self._action_list_active_chara_id = action_chara_id
                self._action_list_scroll = 0
            self._action_list_scroll = max(0, min(self._action_list_scroll, self._max_action_list_scroll(action_chara)))
            action_sb_geom = self._action_scrollbar_geometry(action_chara)

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

                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and self.GameMaster.isActiveAIHuman():
                    current_chara = self._get_action_list_chara()
                    is_wizard = (current_chara is not None and str(current_chara.template.get("display_name", "")).strip().lower() == "wizard")
                    if is_wizard and action_sb_geom is not None:
                        mx, my = event.pos
                        track_rect = action_sb_geom["track_rect"]
                        thumb_rect = action_sb_geom["thumb_rect"]
                        if thumb_rect.collidepoint(mx, my):
                            self._action_sb_dragging = True
                            self._action_sb_drag_offset_y = my - thumb_rect.y
                            continue
                        if track_rect.collidepoint(mx, my):
                            if my < thumb_rect.y:
                                self._action_list_scroll = max(0, self._action_list_scroll - self._action_list_scroll_step * 4)
                            elif my > thumb_rect.bottom:
                                self._action_list_scroll = min(action_sb_geom["max_scroll"], self._action_list_scroll + self._action_list_scroll_step * 4)
                            continue

                if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                    if self._action_sb_dragging:
                        self._action_sb_dragging = False
                        continue

                if event.type == pygame.MOUSEMOTION and self._action_sb_dragging and action_sb_geom is not None:
                    mx, my = event.pos
                    track_rect = action_sb_geom["track_rect"]
                    thumb_rect = action_sb_geom["thumb_rect"]
                    max_scroll = action_sb_geom["max_scroll"]
                    new_thumb_y = my - self._action_sb_drag_offset_y
                    min_y = track_rect.y
                    max_y = track_rect.bottom - thumb_rect.height
                    new_thumb_y = max(min_y, min(max_y, new_thumb_y))

                    if max_scroll == 0 or track_rect.height == thumb_rect.height:
                        self._action_list_scroll = 0
                    else:
                        ratio = (new_thumb_y - track_rect.y) / (track_rect.height - thumb_rect.height)
                        self._action_list_scroll = int(round(ratio * max_scroll))
                    continue

                if event.type == pygame.MOUSEWHEEL and self.GameMaster.isActiveAIHuman():
                    if self._action_panel_content_rect().collidepoint(pygame.mouse.get_pos()):
                        current_chara = self._get_action_list_chara()
                        if current_chara is not None and str(current_chara.template.get("display_name", "")).strip().lower() == "wizard":
                            max_scroll = self._max_action_list_scroll(current_chara)
                            self._action_list_scroll = max(
                                0,
                                min(max_scroll, self._action_list_scroll - (event.y * self._action_list_scroll_step))
                            )
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
                        self._sync_action_list_to_selection()
                    elif event.key == pygame.K_ESCAPE:
                        # Open pause only when human is active and not in endgame
                        if self.GameMaster.isActiveAIHuman() and not endgame_active:
                            self._pause_active = True
                            self._pause_selected_idx = None
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
                            self._pause_selected_idx = None
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
                                if self._action_panel_content_rect().collidepoint(event.pos):
                                    for idx, r in self._action_rects_for_chara(chara, self._action_list_scroll):
                                        if not self._action_panel_content_rect().colliderect(r):
                                            continue
                                        if r.collidepoint(event.pos):
                                                # Choose this action; if it's a heal, execute instantly
                                                Cursor.selected_action = idx
                                                action = chara.template["actions"][idx]
                                                if action.get("action_type", "").lower() == "heal" or action.get("heal") is not None:
                                                    # Execute healing immediately (pass caster as target)
                                                    self.GameMaster.activeAI.useCharaAction(chara, chara, idx, 0)
                                                    # Reset visuals and state
                                                    self.field.select_cursor.show = False
                                                    Cursor.selected_action = -1
                                                    for i in range(self.field.rows):
                                                        for j in range(self.field.cols):
                                                            self.field.boxes[i][j].selected_red = False
                                                    Cursor.state = 0
                                                    # Update end-of-turn check for human AI
                                                    self.GameMaster.activeAI.turnFinished = self.GameMaster.activeAI.checkCharaActed()
                                                    break
                                                else:
                                                    # Non-heal actions go to targeting as before
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
                                    if chara is not None:
                                        action = chara.template["actions"][Cursor.selected_action]
                                        # Heal actions (or actions with a 'heal' field)
                                        if action.get("action_type", "").lower() == "heal" or action.get("heal") is not None:
                                            # Only allow healing allies
                                            if target is not None and target in Character.team1_list:
                                                # Execute via the active human AI to keep logs/flags consistent
                                                self.GameMaster.activeAI.useCharaAction(chara, target, Cursor.selected_action, 0)
                                                # Reset visuals and state (match keyboard path)
                                                self.field.select_cursor.show = False
                                                Cursor.selected_action = -1
                                                for i in range(self.field.rows):
                                                    for j in range(self.field.cols):
                                                        self.field.boxes[i][j].selected_red = False
                                                Cursor.state = 0
                                                # Update end-of-turn check for human AI
                                                self.GameMaster.activeAI.turnFinished = self.GameMaster.activeAI.checkCharaActed()
                                        else:
                                            # Default: offensive actions targeting enemies
                                            if target is not None and target in Character.team2_list:
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
                            self.current_round = self.round
                            self.game_state = 'show round'
                            self.field.hover_cursor.show = True
                            self.log_event('round_begin', round=self.round)
                            self._init_character_snapshots()

                        if match_winner in (1, 2):
                            winner_label = 'P1' if match_winner == 1 else 'P2'
                            completed_match = self.current_match

                            self.last_match_duration = self.cumulative_time
                            self.log_event('match_end', game=self.current_game, match=self.current_match, winner=winner_label, p1_rounds=self.p1_round_wins, p2_rounds=self.p2_round_wins)
                            self.log_event('summary_match', game=self.current_game, match=self.current_match, map_label=self._current_map_label)
                            self.log_event('summary_result', winner=winner_label, p1_rounds=self.p1_round_wins, p2_rounds=self.p2_round_wins)

                            progress = self._handle_completed_match(winner_label)
                            self.log_event('summary_game', game=progress['completed_game'], p1_matches=progress['p1_matches_in_game'], p2_matches=progress['p2_matches_in_game'])

                            if progress['game_finished']:
                                completed_game = progress['completed_game']
                                self.log_event(
                                    'game_end',
                                    game=completed_game,
                                    winner=progress['game_winner'],
                                    p2_matches=progress['p2_matches_in_game'],
                                    p1_matches=progress['p1_matches_in_game'],
                                    time_elapsed=self.cumulative_time,
                                )

                            if progress['session_finished']:
                                self._log_session_summary()
                                if self.total_games_p1 > self.total_games_p2:
                                    self.game_state = 'win'
                                elif self.total_games_p2 > self.total_games_p1:
                                    self.game_state = 'lose'
                                else:
                                    self.game_state = 'win'
                                return

                            if self.isAuto:
                                print(f"Match {completed_match} result: Player {winner_label[-1]} wins")
                                self.startMatch()
                                return

                            self.game_state = 'win' if winner_label == 'P1' else 'lose'

                        self.number_action = -1
                        for chara in Character.team1_list + Character.team2_list:
                            chara.moved = False
                            chara.acted = False

                        self.GameMaster.startRound()

            prev_state = {cid: data.copy() for cid, data in self._char_snapshots.items()}
            current_state = self._capture_character_state()
            
            team1_on_obj = 0
            team2_on_obj = 0

            for char_id, data in current_state.items():
                r, c = data["grid"]
                terrain = self.field.boxes[r][c].terrain

                if terrain == 3:  # Objective tile
                    if data["team"] == 1:
                        team1_on_obj += 1
                    else:
                        team2_on_obj += 1

            # Count control ticks only if one team is actually winning the tile
            if team1_on_obj > team2_on_obj:
                self.obj_control_team1 += 1
            elif team2_on_obj > team1_on_obj:
                self.obj_control_team2 += 1
                
            if prev_state or current_state:
                self._process_character_movements(prev_state, current_state)
                self._process_ai_logs(prev_state, current_state)
                self._process_character_outcomes(prev_state, current_state)
            self._char_snapshots = current_state
