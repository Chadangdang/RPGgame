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

class GameMainRenderMixin:
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

    def _model_track_height(self) -> int:
        return self._model_box_h + self._model_box_gap * (self._model_visible_rows - 1)

    def _model_max_offset(self) -> int:
        return max(0, len(AI_SELECTION_LABELS) - self._model_visible_rows)

    def _model_column_origin(self, is_left: bool) -> tuple[int, int]:
        return (self._model_left_x if is_left else self._model_right_x, self._model_list_top)

    def _model_track_rect(self, is_left: bool) -> pygame.Rect:
        x, y = self._model_column_origin(is_left)
        track_x = x + self._model_box_w + 57
        return pygame.Rect(track_x, y, 15, self._model_track_height())

    def _model_thumb_rect(self, is_left: bool) -> pygame.Rect:
        track = self._model_track_rect(is_left)
        max_offset = self._model_max_offset()
        if max_offset == 0:
            thumb_h = track.height
            thumb_y = track.y
        else:
            thumb_h = max(32, int(track.height * (self._model_visible_rows / len(AI_SELECTION_LABELS))))
            thumb_span = track.height - thumb_h
            ratio = (self._model_scroll_offset / max_offset) if max_offset else 0
            thumb_y = track.y + int(ratio * thumb_span)
        return pygame.Rect(track.x + 1, thumb_y, track.width - 4, thumb_h)

    def _model_offset_from_thumb(self, thumb_center_y: float, is_left: bool) -> int:
        max_offset = self._model_max_offset()
        if max_offset == 0:
            return 0
        track = self._model_track_rect(is_left)
        thumb_h = max(32, int(track.height * (self._model_visible_rows / len(AI_SELECTION_LABELS))))
        thumb_span = max(1, track.height - thumb_h)
        ratio = (thumb_center_y - track.y - thumb_h / 2) / thumb_span
        ratio = max(0.0, min(1.0, ratio))
        return int(round(ratio * max_offset))

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
            # Header banners anchored to provided coordinates
            p1_banner = pygame.Rect(181, 122, 249, 71)
            p2_banner = pygame.Rect(782, 127, 249, 71)
            pygame.draw.rect(self.screen, (140, 215, 255), p1_banner)
            pygame.draw.rect(self.screen, (255, 108, 108), p2_banner)
            pygame.draw.rect(self.screen, BLACK, p1_banner, 2)
            pygame.draw.rect(self.screen, BLACK, p2_banner, 2)

            p1_title = self.font_m.render('PLAYER 1', False, (0, 0, 0))
            p2_title = self.font_m.render('PLAYER 2', False, (0, 0, 0))
            self.screen.blit(p1_title, p1_title.get_rect(center=p1_banner.center))
            self.screen.blit(p2_title, p2_title.get_rect(center=p2_banner.center))

            # Build display labels: first is Player Input, then AI_1..AI_4 with the existing model names appended
            model_names = AI_SELECTION_LABELS
            labels = [model_names[0]] + [f'AI_{i}' for i in range(1, len(model_names))]

            def draw_column(is_left: bool) -> None:
                origin_x, origin_y = self._model_column_origin(is_left)
                mouse_pos = pygame.mouse.get_pos()
                start = self._model_scroll_offset
                end = min(len(labels), start + self._model_visible_rows)
                highlight_color = (255, 255, 94)

                for idx in range(start, end):
                    local_idx = idx - start
                    y = origin_y + local_idx * self._model_box_gap
                    rect = pygame.Rect(origin_x, y, self._model_box_w, self._model_box_h)
                    hovered = rect.collidepoint(mouse_pos)
                    pygame.draw.rect(self.screen, (255, 255, 255) if not hovered else (245, 245, 245), rect)
                    pygame.draw.rect(self.screen, BLACK, rect, 2)

                    lbl_surface = self.font_sm.render(labels[idx], False, (0, 0, 0))
                    self.screen.blit(lbl_surface, lbl_surface.get_rect(midleft=(rect.left + 18, rect.centery)))
                    if idx > 0:
                        mdl_surface = self.font_ss.render(model_names[idx], False, (0, 0, 0))
                        self.screen.blit(mdl_surface, mdl_surface.get_rect(midright=(rect.right - 18, rect.centery)))

                    # Selection highlight (neon yellow inspired by map popup)
                    sel_cursor = self.p1_sel_cursor if is_left else self.p2_sel_cursor
                    if sel_cursor.show and sel_cursor.grid[0] == idx:
                        pygame.draw.rect(self.screen, highlight_color, rect, 6)

                    # Keyboard focus glow
                    if self.menu_cursor.grid == (idx, 0 if is_left else 1):
                        glow = pygame.Surface((rect.width + 8, rect.height + 8), pygame.SRCALPHA)
                        glow.fill((255, 255, 94, 80))
                        self.screen.blit(glow, (rect.x - 4, rect.y - 4))
                        pygame.draw.rect(self.screen, highlight_color, rect, 3)

                # Scrollbar
                track = self._model_track_rect(is_left)
                thumb = self._model_thumb_rect(is_left)
                pygame.draw.rect(self.screen, (254, 254, 254), track)
                pygame.draw.rect(self.screen, BLACK, track, 2)
                pygame.draw.rect(self.screen, (217, 217, 217), thumb)
                pygame.draw.rect(self.screen, BLACK, thumb, 1)

            draw_column(True)
            draw_column(False)

            # Start button
            start_hovered = self._start_button_rect.collidepoint(pygame.mouse.get_pos())
            start_fill = (255, 255, 255) if not start_hovered else (240, 240, 240)
            pygame.draw.rect(self.screen, start_fill, self._start_button_rect)
            pygame.draw.rect(self.screen, BLACK, self._start_button_rect, 2)
            start_text = self.font_sm.render('START', False, (0, 0, 0))
            self.screen.blit(start_text, start_text.get_rect(center=self._start_button_rect.center))

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
            # Settings button (top-right)
            self._settings_button_hovered = self._settings_button_rect.collidepoint(mouse_pos)
            settings_fill = (245, 245, 245) if not self._settings_button_hovered else (230, 230, 230)
            pygame.draw.rect(self.screen, settings_fill, self._settings_button_rect, border_radius=10)
            pygame.draw.rect(self.screen, (0, 0, 0), self._settings_button_rect, 2, border_radius=10)
            setting_text = self.font_s.render('Setting', False, (0, 0, 0))
            self.screen.blit(setting_text, setting_text.get_rect(center=self._settings_button_rect.center))

            if self._settings_popup_open:
                overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
                overlay.fill((0, 0, 0, 110))
                self.screen.blit(overlay, (0, 0))

                pygame.draw.rect(self.screen, (247, 242, 234), self._settings_popup_rect)
                pygame.draw.rect(self.screen, (0, 0, 0), self._settings_popup_rect, 3)

                close_text = self.font_s.render('X', False, (0, 0, 0))
                self.screen.blit(close_text, close_text.get_rect(center=self._settings_close_rect.center))

                if self._settings_popup_page == 'main':
                    settings_title = self.font_m.render('Settings', False, (0, 0, 0))
                    self.screen.blit(settings_title, settings_title.get_rect(center=(self._settings_popup_rect.centerx, self._settings_popup_rect.y + 120)))

                    main_btn_hovered = self._settings_main_balance_button_rect.collidepoint(mouse_pos)
                    btn_fill = (236, 228, 215) if not main_btn_hovered else (226, 216, 199)
                    pygame.draw.rect(self.screen, btn_fill, self._settings_main_balance_button_rect, border_radius=10)
                    pygame.draw.rect(self.screen, (90, 80, 66), self._settings_main_balance_button_rect, 2, border_radius=10)
                    balance_btn_text = self.font_sm.render('Balance Tweaking', False, (0, 0, 0))
                    self.screen.blit(balance_btn_text, balance_btn_text.get_rect(center=self._settings_main_balance_button_rect.center))
                else:
                    back_hovered = self._settings_sub_back_rect.collidepoint(mouse_pos)
                    back_fill = (236, 236, 236) if not back_hovered else (223, 223, 223)
                    pygame.draw.rect(self.screen, back_fill, self._settings_sub_back_rect, border_radius=8)
                    pygame.draw.rect(self.screen, (60, 60, 60), self._settings_sub_back_rect, 2, border_radius=8)
                    back_text = self.font_s.render('< Back', False, (0, 0, 0))
                    self.screen.blit(back_text, back_text.get_rect(center=self._settings_sub_back_rect.center))

                    title = self.font_sm.render('Balance Tweaking', False, (0, 0, 0))
                    self.screen.blit(title, title.get_rect(center=(self._settings_popup_rect.centerx, self._settings_popup_rect.y + 120)))

                    for idx, row_rect in enumerate(self._balance_option_row_rects):
                        row_fill = (252, 249, 244)
                        if idx == self._balance_keyboard_index:
                            row_fill = (255, 252, 232)
                        pygame.draw.rect(self.screen, row_fill, row_rect, border_radius=10)
                        pygame.draw.rect(self.screen, (130, 120, 104), row_rect, 2, border_radius=10)

                        checkbox_rect = self._balance_checkbox_rects[idx]
                        pygame.draw.rect(self.screen, (250, 250, 250), checkbox_rect, border_radius=4)
                        pygame.draw.rect(self.screen, (80, 80, 80), checkbox_rect, 2, border_radius=4)
                        if self._balance_option_states[idx]:
                            pygame.draw.line(self.screen, (24, 24, 24), (checkbox_rect.left + 6, checkbox_rect.centery), (checkbox_rect.centerx - 1, checkbox_rect.bottom - 6), 4)
                            pygame.draw.line(self.screen, (24, 24, 24), (checkbox_rect.centerx - 1, checkbox_rect.bottom - 6), (checkbox_rect.right - 6, checkbox_rect.top + 6), 4)

                        label_x = checkbox_rect.right + 16
                        label_y = row_rect.centery
                        if idx == 1:
                            left = self.font_s.render('Passive and skill after effect', False, (39, 174, 96))
                            plus = self.font_s.render(' + ', False, (0, 0, 0))
                            right = self.font_s.render('Weakness system', False, (66, 66, 245))
                            left_rect = left.get_rect(midleft=(label_x, label_y))
                            self.screen.blit(left, left_rect)
                            plus_rect = plus.get_rect(midleft=(left_rect.right, label_y))
                            self.screen.blit(plus, plus_rect)
                            right_rect = right.get_rect(midleft=(plus_rect.right, label_y))
                            self.screen.blit(right, right_rect)
                        else:
                            label_surface = self.font_s.render(self._balance_option_labels[idx], False, self._balance_option_colors[idx])
                            self.screen.blit(label_surface, label_surface.get_rect(midleft=(label_x, label_y)))

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
                pygame.draw.rect(self.screen, (0, 0, 0), pygame.Rect(980, 40, 280, 560), 2)
                objective_menu_text = self.font_s.render("Actions List", False, (0, 0, 0))
                text_rect = objective_menu_text.get_rect(topleft=(990, 50))
                self.screen.blit(objective_menu_text, text_rect)
                action_content_rect = self._action_panel_content_rect()
                if (chara := self._get_action_list_chara()) is not None:
                    old_clip = self.screen.get_clip()
                    self.screen.set_clip(action_content_rect)
                    for index, action in enumerate(chara.template.get("actions", [])):
                        card_rect = pygame.Rect(1000, 88 + (index * 170) - self._action_list_scroll, 220, 150)
                        if not action_content_rect.colliderect(card_rect):
                            continue

                        pygame.draw.rect(self.screen, (0, 0, 0), card_rect, 1)
                        if Cursor.selected_action == index:
                            pygame.draw.rect(self.screen, YELLOW, card_rect, 4)
                        name = action.get("action_display_name", "")
                        atype = action.get("action_type", "")
                        atarget = action.get("target", "")
                        arange = action.get("range", "")
                        adamage = action.get("damage", "")
                        aheal = action.get("heal", "")
                        objective_menu_text = self.font_s.render(name, False, (0, 0, 0))
                        text_rect = objective_menu_text.get_rect(topleft=(card_rect.x + 10, card_rect.y + 2))
                        self.screen.blit(objective_menu_text, text_rect)
                        objective_menu_text = self.font_s.render(f'Type : {atype}', False, (0, 0, 0))
                        text_rect = objective_menu_text.get_rect(topleft=(card_rect.x + 15, card_rect.y + 32))
                        self.screen.blit(objective_menu_text, text_rect)
                        objective_menu_text = self.font_s.render(f'Area : {atarget}', False, (0, 0, 0))
                        text_rect = objective_menu_text.get_rect(topleft=(card_rect.x + 15, card_rect.y + 57))
                        self.screen.blit(objective_menu_text, text_rect)
                        objective_menu_text = self.font_s.render(f'Range : {arange}', False, (0, 0, 0))
                        text_rect = objective_menu_text.get_rect(topleft=(card_rect.x + 15, card_rect.y + 82))
                        self.screen.blit(objective_menu_text, text_rect)
                        if str(atype).lower() == "heal" or action.get("heal") is not None:
                            value_text = f'Heal : {aheal}'
                        else:
                            value_text = f'Damage : {adamage}'
                        objective_menu_text = self.font_s.render(value_text, False, (0, 0, 0))
                        text_rect = objective_menu_text.get_rect(topleft=(card_rect.x + 15, card_rect.y + 107))
                        self.screen.blit(objective_menu_text, text_rect)
                    self.screen.set_clip(old_clip)

                    # Show short scrollbar (same style as game log) when wizard has more actions.
                    is_wizard = str(chara.template.get("display_name", "")).strip().lower() == "wizard"
                    if is_wizard:
                        sb_geom = self._action_scrollbar_geometry(chara)
                        if sb_geom is not None:
                            pygame.draw.rect(self.screen, SB_TRACK, sb_geom["track_rect"], border_radius=5)
                            mouse_pos = pygame.mouse.get_pos()
                            if self._action_sb_dragging:
                                thumb_color = SB_THUMB_DRAG
                            elif sb_geom["thumb_rect"].collidepoint(mouse_pos):
                                thumb_color = SB_THUMB_HOVER
                            else:
                                thumb_color = SB_THUMB
                            pygame.draw.rect(self.screen, thumb_color, sb_geom["thumb_rect"], border_radius=5)
                            pygame.draw.rect(self.screen, UI_BORDER, sb_geom["thumb_rect"], 1, border_radius=5)
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
            log_content_width = self._log_content_width()
            wrapped_log_lines = self._wrap_game_log_lines(log_content_width)
            geom = self._calc_log_geometry(total_log_lines=len(wrapped_log_lines))

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
            end   = min(len(wrapped_log_lines), start + max_lines)

            for log_tuple in wrapped_log_lines[start:end]:
                text, color, _ = log_tuple
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
