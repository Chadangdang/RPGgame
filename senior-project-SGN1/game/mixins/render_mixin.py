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

def AI_SELECTION_LABELS() -> list[str]:
    return GM.get_ai_labels()


def _format_ai_selection_label(label: str) -> str:
    """Shorten personality-core variant names for AI select screen display only."""
    mapping = {
        'Aggressive Personality Cores AI': 'Aggressive',
        'Strategic Personality Cores AI': 'Strategic',
        'Survival Personality Cores AI': 'Survival',
    }
    return mapping.get(label, label)



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
    def _draw_start_alert_overlay(self) -> None:
        """Render startup alert as a top-most responsive banner."""
        alert_msg = getattr(self, '_start_alert_message', '')
        if not alert_msg or pygame.time.get_ticks() >= getattr(self, '_start_alert_until', 0):
            return

        text = str(alert_msg).strip()
        if not text:
            return

        max_lines = 3
        base_padding_x = 40
        line_spacing = 5
        min_banner_width = 260
        max_banner_width = min(WIDTH - 32, 1120)
        line_height = self.font_s.get_height()

        words = text.split()
        lines: list[str] = []

        if not words:
            words = [text]

        current_line = ""
        for word in words:
            candidate = word if not current_line else f"{current_line} {word}"
            candidate_w = self.font_s.size(candidate)[0]
            if candidate_w <= (max_banner_width - (base_padding_x * 2)):
                current_line = candidate
            else:
                if current_line:
                    lines.append(current_line)
                current_line = word

        if current_line:
            lines.append(current_line)

        if len(lines) > max_lines:
            visible_lines = lines[:max_lines]
            while visible_lines[-1] and self.font_s.size(f"{visible_lines[-1]}...")[0] > (max_banner_width - (base_padding_x * 2)):
                visible_lines[-1] = visible_lines[-1][:-1]
            visible_lines[-1] = f"{visible_lines[-1].rstrip()}..."
            lines = visible_lines

        text_width = max(self.font_s.size(line)[0] for line in lines)
        alert_width = max(min_banner_width, min(max_banner_width, text_width + (base_padding_x * 2)))
        alert_height = 22 + (len(lines) * line_height) + (max(0, len(lines) - 1) * line_spacing)
        alert_bg = pygame.Rect(0, 0, alert_width, alert_height)
        alert_bg.midtop = (WIDTH // 2, 28)

        pygame.draw.rect(self.screen, (247, 207, 111), alert_bg, border_radius=8)
        pygame.draw.rect(self.screen, (64, 36, 0), alert_bg, 2, border_radius=8)

        y = alert_bg.y + 11
        for line in lines:
            alert_text = self.font_s.render(line, False, (30, 18, 0))
            self.screen.blit(alert_text, alert_text.get_rect(centerx=alert_bg.centerx, y=y))
            y += line_height + line_spacing

    def _model_track_height(self) -> int:
        left_rows = self._model_row_rects(True)
        right_rows = self._model_row_rects(False)

        def _rows_height(rows: list[tuple[int, pygame.Rect]]) -> int:
            if not rows:
                return self._model_box_h
            return rows[-1][1].bottom - rows[0][1].top

        return max(_rows_height(left_rows), _rows_height(right_rows))

    def _model_max_offset(self) -> int:
        return max(0, len(AI_SELECTION_LABELS()) - self._model_visible_rows)

    def _model_column_origin(self, is_left: bool) -> tuple[int, int]:
        return (self._model_left_x if is_left else self._model_right_x, self._model_list_top)

    def _model_is_personality_subrow(self, idx: int) -> bool:
        return idx in {4, 5, 6}

    def _model_row_height(self, idx: int) -> int:
        if self._model_is_personality_subrow(idx):
            return int(self._model_box_h * 0.72)
        return self._model_box_h

    def _model_row_gap(self, prev_idx: int | None, idx: int) -> int:
        if prev_idx is None:
            return 0

        normal_gap = max(0, self._model_box_gap - self._model_box_h)
        if (prev_idx == 3 and self._model_is_personality_subrow(idx)) or (
            self._model_is_personality_subrow(prev_idx) and self._model_is_personality_subrow(idx)
        ):
            return 0
        return normal_gap

    def _model_row_rects(self, is_left: bool) -> list[tuple[int, pygame.Rect]]:
        col_idx = 0 if is_left else 1
        start = self._model_scroll_offset[col_idx]
        end = min(len(AI_SELECTION_LABELS()), start + self._model_visible_rows)
        origin_x, origin_y = self._model_column_origin(is_left)

        rows: list[tuple[int, pygame.Rect]] = []
        cursor_y = origin_y
        prev_idx: int | None = None
        for idx in range(start, end):
            cursor_y += self._model_row_gap(prev_idx, idx)
            row_h = self._model_row_height(idx)
            if self._model_is_personality_subrow(idx):
                inset_x = 10
                row_rect = pygame.Rect(origin_x + inset_x, cursor_y, self._model_box_w - (inset_x * 2), row_h)
            else:
                row_rect = pygame.Rect(origin_x, cursor_y, self._model_box_w, row_h)
            rows.append((idx, row_rect))
            cursor_y += row_h
            prev_idx = idx

        return rows

    def _model_track_rect(self, is_left: bool) -> pygame.Rect:
        x, y = self._model_column_origin(is_left)
        track_x = x + self._model_box_w + 57
        return pygame.Rect(track_x, y, 15, self._model_track_height())

    def _model_thumb_rect(self, is_left: bool) -> pygame.Rect:
        track = self._model_track_rect(is_left)
        max_offset = self._model_max_offset()
        col_idx = 0 if is_left else 1
        col_offset = self._model_scroll_offset[col_idx]
        if max_offset == 0:
            thumb_h = track.height
            thumb_y = track.y
        else:
            thumb_h = max(32, int(track.height * (self._model_visible_rows / len(AI_SELECTION_LABELS()))))
            thumb_span = track.height - thumb_h
            ratio = (col_offset / max_offset) if max_offset else 0
            thumb_y = track.y + int(ratio * thumb_span)
        return pygame.Rect(track.x + 1, thumb_y, track.width - 4, thumb_h)

    def _model_offset_from_thumb(self, thumb_center_y: float, is_left: bool) -> int:
        max_offset = self._model_max_offset()
        if max_offset == 0:
            return 0
        track = self._model_track_rect(is_left)
        thumb_h = max(32, int(track.height * (self._model_visible_rows / len(AI_SELECTION_LABELS()))))
        thumb_span = max(1, track.height - thumb_h)
        ratio = (thumb_center_y - track.y - thumb_h / 2) / thumb_span
        ratio = max(0.0, min(1.0, ratio))
        return int(round(ratio * max_offset))

    def render(self, dt: float = 0.0) -> None:
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

            ai_labels = AI_SELECTION_LABELS()
            model_names = [_format_ai_selection_label(name) for name in ai_labels]
            custom_map = {str(item.get('name', '')).strip(): item for item in GM.get_ai_metadata() if str(item.get('name', '')).strip()}
            self._custom_ai_dot_buttons = []

            def draw_column(is_left: bool) -> None:
                mouse_pos = pygame.mouse.get_pos()
                highlight_color = (255, 255, 94)

                for idx, rect in self._model_row_rects(is_left):
                    model_label = ai_labels[idx]
                    is_custom_ai = model_label in custom_map
                    hovered = rect.collidepoint(mouse_pos)
                    pygame.draw.rect(self.screen, (255, 255, 255) if not hovered else (245, 245, 245), rect)
                    pygame.draw.rect(self.screen, BLACK, rect, 2)

                    text_font = self.font_model_select_sub if self._model_is_personality_subrow(idx) else self.font_model_select
                    lbl_surface = text_font.render(model_names[idx], False, (0, 0, 0))
                    label_center = rect.center
                    if is_custom_ai:
                        label_center = (rect.centerx - 18, rect.centery)
                    self.screen.blit(lbl_surface, lbl_surface.get_rect(center=label_center))

                    if is_custom_ai:
                        dot_rect = pygame.Rect(rect.right + 14, rect.y + (rect.height - 34) // 2, 34, 34)
                        dot_hovered = dot_rect.collidepoint(mouse_pos)
                        pygame.draw.rect(self.screen, (248, 248, 248) if not dot_hovered else (235, 235, 235), dot_rect, border_radius=8)
                        pygame.draw.rect(self.screen, (0, 0, 0), dot_rect, 2, border_radius=8)
                        if self._custom_ai_menu_icon is not None:
                            icon_size = max(18, dot_rect.width - 10)
                            icon_surface = pygame.transform.smoothscale(self._custom_ai_menu_icon, (icon_size, icon_size))
                            self.screen.blit(icon_surface, icon_surface.get_rect(center=dot_rect.center))
                        else:
                            dots_text = self.font_s.render('⋯', False, (0, 0, 0))
                            self.screen.blit(dots_text, dots_text.get_rect(center=(dot_rect.centerx, dot_rect.centery - 1)))
                        self._custom_ai_dot_buttons.append((model_label, dot_rect))

                    # Selection highlight (neon yellow inspired by map popup)
                    sel_cursor = self.p1_sel_cursor if is_left else self.p2_sel_cursor
                    if sel_cursor.show and sel_cursor.grid[0] == idx:
                        pygame.draw.rect(self.screen, highlight_color, rect, 6)

                    # Keyboard focus glow
                    if getattr(self, '_kb_focus', 'model_list') == 'model_list' and self.menu_cursor.grid == (idx, 0 if is_left else 1):
                        glow = pygame.Surface((rect.width + 8, rect.height + 8), pygame.SRCALPHA)
                        glow.fill((255, 255, 94, 80))
                        self.screen.blit(glow, (rect.x - 4, rect.y - 4))
                        pygame.draw.rect(self.screen, highlight_color, rect, 3)

                # Scrollbar
                track = self._model_track_rect(is_left)
                thumb = self._model_thumb_rect(is_left)
                pygame.draw.rect(self.screen, (254, 254, 254), track)
                pygame.draw.rect(self.screen, BLACK, track, 2)
                if thumb.collidepoint(mouse_pos):
                    thumb_color = (200, 200, 200)
                else:
                    thumb_color = (217, 217, 217)
                pygame.draw.rect(self.screen, thumb_color, thumb)
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
            if getattr(self, '_kb_focus', 'model_list') == 'start':
                glow = pygame.Surface((self._start_button_rect.width + 8, self._start_button_rect.height + 8), pygame.SRCALPHA)
                glow.fill((255, 255, 94, 80))
                self.screen.blit(glow, (self._start_button_rect.x - 4, self._start_button_rect.y - 4))
                pygame.draw.rect(self.screen, (255, 255, 94), self._start_button_rect, 3)

            # (Auto, Game/Match limits now rendered inside Settings popup)

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
            if getattr(self, '_kb_focus', 'model_list') == 'map_selection':
                glow = pygame.Surface((self._map_select_button_rect.width + 8, self._map_select_button_rect.height + 8), pygame.SRCALPHA)
                glow.fill((255, 255, 94, 80))
                self.screen.blit(glow, (self._map_select_button_rect.x - 4, self._map_select_button_rect.y - 4))
                pygame.draw.rect(self.screen, (255, 255, 94), self._map_select_button_rect, 3)
            # Import AI button (bottom-left)
            try:
                import_hover = self._import_ai_button_rect.collidepoint(mouse_pos)
            except Exception:
                import_hover = False
            self._import_ai_button_hovered = import_hover
            import_fill = (217, 217, 217) if not import_hover else (200, 200, 200)
            pygame.draw.rect(self.screen, import_fill, self._import_ai_button_rect)
            pygame.draw.rect(self.screen, (0, 0, 0), self._import_ai_button_rect, 1)
            import_text = self.font_s.render("Import AI", False, (0, 0, 0))
            self.screen.blit(import_text, import_text.get_rect(center=self._import_ai_button_rect.center))
            if getattr(self, '_kb_focus', 'model_list') == 'import_ai':
                glow = pygame.Surface((self._import_ai_button_rect.width + 8, self._import_ai_button_rect.height + 8), pygame.SRCALPHA)
                glow.fill((255, 255, 94, 80))
                self.screen.blit(glow, (self._import_ai_button_rect.x - 4, self._import_ai_button_rect.y - 4))
                pygame.draw.rect(self.screen, (255, 255, 94), self._import_ai_button_rect, 3)

            # Instructions circular button (to the right of Import AI)
            try:
                instr_hover = self._instr_button_rect.collidepoint(mouse_pos)
            except Exception:
                instr_hover = False
            self._instr_button_hovered = instr_hover
            instr_center = self._instr_button_rect.center
            instr_radius = min(self._instr_button_rect.width, self._instr_button_rect.height) // 2
            instr_fill = (234, 234, 200) if not instr_hover else (220, 220, 170)
            pygame.draw.circle(self.screen, instr_fill, instr_center, instr_radius)
            pygame.draw.circle(self.screen, (0, 0, 0), instr_center, instr_radius, 2)
            i_text = self.font_sm.render('i', False, (0, 0, 0))
            self.screen.blit(i_text, i_text.get_rect(center=instr_center))
            if getattr(self, '_kb_focus', 'model_list') == 'info':
                glow_surface = pygame.Surface((self._instr_button_rect.width + 8, self._instr_button_rect.height + 8), pygame.SRCALPHA)
                glow_center = (glow_surface.get_width() // 2, glow_surface.get_height() // 2)
                pygame.draw.circle(glow_surface, (255, 255, 94, 80), glow_center, instr_radius + 4)
                self.screen.blit(glow_surface, (self._instr_button_rect.x - 4, self._instr_button_rect.y - 4))
                pygame.draw.circle(self.screen, (255, 255, 94), instr_center, instr_radius, 3)
            # Settings button (top-right)
            self._settings_button_hovered = self._settings_button_rect.collidepoint(mouse_pos)
            settings_fill = (245, 245, 245) if not self._settings_button_hovered else (230, 230, 230)
            pygame.draw.rect(self.screen, settings_fill, self._settings_button_rect)
            pygame.draw.rect(self.screen, (0, 0, 0), self._settings_button_rect, 2)
            setting_text = self.font_s.render('Setting', False, (0, 0, 0))
            self.screen.blit(setting_text, setting_text.get_rect(center=self._settings_button_rect.center))
            if getattr(self, '_kb_focus', 'model_list') == 'settings':
                glow = pygame.Surface((self._settings_button_rect.width + 8, self._settings_button_rect.height + 8), pygame.SRCALPHA)
                glow.fill((255, 255, 94, 80))
                self.screen.blit(glow, (self._settings_button_rect.x - 4, self._settings_button_rect.y - 4))
                pygame.draw.rect(self.screen, (255, 255, 94), self._settings_button_rect, 3)

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
                    balance_btn_text = self.font_sm.render('Balance Tweaking >', False, (0, 0, 0))
                    self.screen.blit(balance_btn_text, balance_btn_text.get_rect(center=self._settings_main_balance_button_rect.center))

                    resolution_btn_hovered = self._settings_main_resolution_button_rect.collidepoint(mouse_pos)
                    resolution_btn_fill = (236, 228, 215) if not resolution_btn_hovered else (226, 216, 199)
                    pygame.draw.rect(self.screen, resolution_btn_fill, self._settings_main_resolution_button_rect, border_radius=10)
                    pygame.draw.rect(self.screen, (90, 80, 66), self._settings_main_resolution_button_rect, 2, border_radius=10)
                    resolution_btn_text = self.font_sm.render('Toggle Resolution', False, (0, 0, 0))
                    self.screen.blit(resolution_btn_text, resolution_btn_text.get_rect(center=self._settings_main_resolution_button_rect.center))

                    # --- Auto toggle + Game/Match limit controls inside the Settings popup ---
                    label_x = getattr(self, '_settings_label_x', self._settings_popup_rect.x + 140)
                    value_x = getattr(self, '_settings_value_x', label_x + 260)

                    # Auto control removed; controls begin here

                    # Game limit
                    game_label = self.font_sm.render("Game Limit:", False, (0, 0, 0))
                    game_label_rect = game_label.get_rect(midleft=(label_x, self._game_limit_box_rect.centery))
                    self.screen.blit(game_label, game_label_rect)
                    game_active = getattr(self, '_active_limit_input', None) == 'game'
                    pygame.draw.rect(self.screen, (255, 255, 255), self._game_limit_box_rect, border_radius=6)
                    pygame.draw.rect(self.screen, (255, 220, 120) if game_active else (0, 0, 0), self._game_limit_box_rect, 2, border_radius=6)
                    game_value_surface = self.font_sm.render(str(getattr(self, '_game_limit_input', self.game_limit)), False, (0, 0, 0))
                    game_value_rect = game_value_surface.get_rect(midleft=(self._game_limit_box_rect.x + 12, self._game_limit_box_rect.centery))
                    self.screen.blit(game_value_surface, game_value_rect)

                    # Match limit
                    match_label = self.font_sm.render("Match Limit:", False, (0, 0, 0))
                    match_label_rect = match_label.get_rect(midleft=(label_x, self._match_limit_box_rect.centery))
                    self.screen.blit(match_label, match_label_rect)
                    match_active = getattr(self, '_active_limit_input', None) == 'match'
                    pygame.draw.rect(self.screen, (255, 255, 255), self._match_limit_box_rect, border_radius=6)
                    pygame.draw.rect(self.screen, (255, 220, 120) if match_active else (0, 0, 0), self._match_limit_box_rect, 2, border_radius=6)
                    match_value_surface = self.font_sm.render(str(getattr(self, '_match_limit_input', self.match_limit)), False, (0, 0, 0))
                    value_rect = match_value_surface.get_rect(midleft=(self._match_limit_box_rect.x + 12, self._match_limit_box_rect.centery))
                    self.screen.blit(match_value_surface, value_rect)
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
                        if idx == 3:
                            mode = self.font_s.render('Combined Mode', False, (0, 0, 0))
                            lparen = self.font_s.render(' (', False, (0, 0, 0))
                            left = self.font_s.render('Passive-Enhanced', False, (39, 174, 96))
                            plus = self.font_s.render(' + ', False, (0, 0, 0))
                            right = self.font_s.render('Weakness-Based', False, (66, 66, 245))
                            rparen = self.font_s.render(')', False, (0, 0, 0))
                            mode_rect = mode.get_rect(midleft=(label_x, label_y))
                            self.screen.blit(mode, mode_rect)
                            lparen_rect = lparen.get_rect(midleft=(mode_rect.right, label_y))
                            self.screen.blit(lparen, lparen_rect)
                            left_rect = left.get_rect(midleft=(lparen_rect.right, label_y))
                            self.screen.blit(left, left_rect)
                            plus_rect = plus.get_rect(midleft=(left_rect.right, label_y))
                            self.screen.blit(plus, plus_rect)
                            right_rect = right.get_rect(midleft=(plus_rect.right, label_y))
                            self.screen.blit(right, right_rect)
                            rparen_rect = rparen.get_rect(midleft=(right_rect.right, label_y))
                            self.screen.blit(rparen, rparen_rect)
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

                    # Render map option label (e.g., map number or Random) centered in each box.
                    option_label = self._map_option_labels[idx]
                    if option_label.lower() != 'random':
                        option_label = str(option_label)
                    label_font = self.font_sm
                    if label_font.size(option_label)[0] > rect.width - 12:
                        label_font = self.font_s
                    if label_font.size(option_label)[0] > rect.width - 12:
                        label_font = self.font_ss
                    label_surface = label_font.render(option_label, False, (0, 0, 0))
                    self.screen.blit(label_surface, label_surface.get_rect(center=rect.center))

            # Instructions popup (in-game)
            if getattr(self, '_instr_popup_open', False):
                overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
                overlay.fill((0, 0, 0, 150))
                self.screen.blit(overlay, (0, 0))

                pygame.draw.rect(self.screen, (255, 255, 255), self._instr_popup_rect)
                pygame.draw.rect(self.screen, (0, 0, 0), self._instr_popup_rect, 3)

                # Close button
                close_text = self.font_s.render('X', False, (0, 0, 0))
                self.screen.blit(close_text, close_text.get_rect(center=self._instr_popup_close_rect.center))

                # Title icon: match appearance of the circular 'i' button next to Import AI
                icon_center = (self._instr_popup_rect.centerx, self._instr_popup_rect.y + 48)
                icon_radius = 24
                icon_fill = (234, 234, 200)
                pygame.draw.circle(self.screen, icon_fill, icon_center, icon_radius)
                pygame.draw.circle(self.screen, (0, 0, 0), icon_center, icon_radius, 2)
                i_surf = self.font_sm.render('i', False, (0, 0, 0))
                self.screen.blit(i_surf, i_surf.get_rect(center=icon_center))

                # Tabs for pages — compute widths so three tabs perfectly fit & center inside popup
                tab_y = self._instr_popup_rect.y + 80
                tab_h = 42
                gap = 24
                side_padding = 48
                tab_w = int((self._instr_popup_rect.width - side_padding * 2 - gap * 2) / 3)
                start_x = self._instr_popup_rect.x + (self._instr_popup_rect.width - (tab_w * 3 + gap * 2)) // 2
                game_tab_rect = pygame.Rect(start_x, tab_y, tab_w, tab_h)
                import_tab_rect = pygame.Rect(start_x + tab_w + gap, tab_y, tab_w, tab_h)
                ai_tab_rect = pygame.Rect(start_x + (tab_w + gap) * 2, tab_y, tab_w, tab_h)
                mouse_pos = pygame.mouse.get_pos()
                # draw tabs
                game_active = getattr(self, '_instr_page', 'game') == 'game'
                import_active = getattr(self, '_instr_page', 'game') == 'import'
                ai_active = getattr(self, '_instr_page', 'game') == 'ai'
                g_fill = (246, 242, 234) if game_active else (235, 235, 235)
                i_fill = (246, 242, 234) if import_active else (235, 235, 235)
                a_fill = (246, 242, 234) if ai_active else (235, 235, 235)
                pygame.draw.rect(self.screen, g_fill, game_tab_rect, border_radius=8)
                pygame.draw.rect(self.screen, (0, 0, 0), game_tab_rect, 2, border_radius=8)
                pygame.draw.rect(self.screen, i_fill, import_tab_rect, border_radius=8)
                pygame.draw.rect(self.screen, (0, 0, 0), import_tab_rect, 2, border_radius=8)
                pygame.draw.rect(self.screen, a_fill, ai_tab_rect, border_radius=8)
                pygame.draw.rect(self.screen, (0, 0, 0), ai_tab_rect, 2, border_radius=8)
                # Render tab labels, shrinking font if necessary to fit inside each tab
                def render_tab_text(text: str, rect: pygame.Rect, bold: bool = False):
                    padding_inside = 12
                    max_text_w = max(8, rect.width - padding_inside * 2)
                    # try sizes starting from font_s size down to 10
                    base_size = 30 if hasattr(self, 'font_s') else 24
                    for size in range(base_size, 9, -1):
                        tmp_font = pygame.font.Font('resource/font.ttf', size)
                        if bold:
                            try:
                                tmp_font.set_bold(True)
                            except Exception:
                                pass
                        if tmp_font.size(text)[0] <= max_text_w:
                            surf = tmp_font.render(text, False, (0, 0, 0))
                            self.screen.blit(surf, surf.get_rect(center=rect.center))
                            return
                    # fallback: render with smallest size
                    tmp_font = pygame.font.Font('resource/font.ttf', 10)
                    if bold:
                        try:
                            tmp_font.set_bold(True)
                        except Exception:
                            pass
                    surf = tmp_font.render(text, False, (0, 0, 0))
                    self.screen.blit(surf, surf.get_rect(center=rect.center))

                render_tab_text('Game Instruction', game_tab_rect)
                render_tab_text('AI Insertion', import_tab_rect)
                render_tab_text('AI Description', ai_tab_rect)

                # Render selected page lines with simple wrapping + vertical scrolling.
                padding = 28
                text_x = self._instr_popup_rect.x + padding
                text_y = self._instr_popup_rect.y + 140
                max_w = self._instr_popup_rect.width - padding * 2
                available_h = self._instr_popup_rect.bottom - padding - text_y
                if getattr(self, '_instr_page', 'game') == 'game':
                    source_lines = getattr(self, '_instr_game_lines', [])
                elif getattr(self, '_instr_page', 'game') == 'import':
                    source_lines = getattr(self, '_instr_import_lines', [])
                else:
                    source_lines = getattr(self, '_instr_ai_lines', [])
                chosen_font = getattr(self, '_instr_text_font', self.font_ss)
                line_h = chosen_font.get_height() + 6

                wrapped_lines = []
                for raw_line in source_lines:
                    raw_text = str(raw_line)
                    if raw_text.strip() == '':
                        wrapped_lines.append('')
                        continue
                    # Preserve leading whitespace (indentation)
                    stripped = raw_text.lstrip(' ')
                    indent = raw_text[:len(raw_text) - len(stripped)]
                    words = stripped.split(' ')
                    cur = indent
                    for w in words:
                        test = cur + (' ' if cur.strip() else '') + w
                        if chosen_font.size(test)[0] <= max_w:
                            cur = test
                        else:
                            if cur.strip():
                                wrapped_lines.append(cur)
                            # Handle very long tokens (no spaces) by splitting them
                            # across multiple lines so text never overflows popup width.
                            if chosen_font.size(indent + w)[0] <= max_w:
                                cur = indent + w
                            else:
                                segment = indent
                                for ch in w:
                                    candidate = segment + ch
                                    if chosen_font.size(candidate)[0] <= max_w:
                                        segment = candidate
                                    else:
                                        if segment.strip():
                                            wrapped_lines.append(segment)
                                        segment = indent + ch
                                cur = segment
                    if cur.strip():
                        wrapped_lines.append(cur)

                total_h = len(wrapped_lines) * line_h
                max_scroll = max(0, total_h - available_h)
                page = getattr(self, '_instr_page', 'game')
                if not hasattr(self, '_instr_scroll_by_page'):
                    self._instr_scroll_by_page = {'game': 0, 'import': 0, 'ai': 0}
                current_scroll = max(0, min(self._instr_scroll_by_page.get(page, 0), max_scroll))
                self._instr_scroll_by_page[page] = current_scroll

                clip_rect = pygame.Rect(text_x, text_y, max_w, available_h)
                prev_clip = self.screen.get_clip()
                self.screen.set_clip(clip_rect)

                y = text_y - current_scroll
                for line in wrapped_lines:
                    if y + line_h < text_y:
                        y += line_h
                        continue
                    if y > text_y + available_h:
                        break
                    if line:
                        surf = chosen_font.render(line, False, (10, 10, 10))
                        self.screen.blit(surf, (text_x, y))
                    y += line_h

                self.screen.set_clip(prev_clip)

                if max_scroll > 0:
                    bar_w = 8
                    bar_x = self._instr_popup_rect.right - padding + 4
                    bar_rect = pygame.Rect(bar_x, text_y, bar_w, available_h)
                    pygame.draw.rect(self.screen, (220, 220, 220), bar_rect)
                    thumb_h = max(36, int(available_h * (available_h / total_h)))
                    thumb_y = text_y + int((available_h - thumb_h) * (current_scroll / max_scroll))
                    pygame.draw.rect(self.screen, (120, 120, 120), pygame.Rect(bar_x, thumb_y, bar_w, thumb_h))

            if getattr(self, '_import_popup_open', False):
                overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
                overlay.fill((0, 0, 0, 145))
                self.screen.blit(overlay, (0, 0))

                pygame.draw.rect(self.screen, (247, 242, 234), self._import_modal_rect, border_radius=8)
                pygame.draw.rect(self.screen, (0, 0, 0), self._import_modal_rect, 3, border_radius=8)
                close_text = self.font_s.render('X', False, (0, 0, 0))
                self.screen.blit(close_text, close_text.get_rect(center=self._import_modal_close_rect.center))

                title = self.font_m.render('AI Import', False, (0, 0, 0))
                self.screen.blit(title, title.get_rect(midtop=(self._import_modal_rect.centerx, self._import_modal_rect.y + 22)))
                info = self.font_s.render('Choose one action to continue.', False, (40, 40, 40))
                self.screen.blit(info, info.get_rect(midtop=(self._import_modal_rect.centerx, self._import_modal_rect.y + 92)))

                mouse_pos = pygame.mouse.get_pos()
                dl_hover = self._import_modal_download_rect.collidepoint(mouse_pos)
                up_hover = self._import_modal_upload_rect.collidepoint(mouse_pos)
                pygame.draw.rect(self.screen, (220, 220, 220) if dl_hover else (235, 235, 235), self._import_modal_download_rect, border_radius=6)
                pygame.draw.rect(self.screen, (0, 0, 0), self._import_modal_download_rect, 2, border_radius=6)
                pygame.draw.rect(self.screen, (220, 220, 220) if up_hover else (235, 235, 235), self._import_modal_upload_rect, border_radius=6)
                pygame.draw.rect(self.screen, (0, 0, 0), self._import_modal_upload_rect, 2, border_radius=6)

                dl_text = self.font_s.render('Download AI Template', False, (0, 0, 0))
                up_text = self.font_s.render('Import AI', False, (0, 0, 0))
                self.screen.blit(dl_text, dl_text.get_rect(center=self._import_modal_download_rect.center))
                self.screen.blit(up_text, up_text.get_rect(center=self._import_modal_upload_rect.center))

            if getattr(self, '_register_popup_open', False):
                overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
                overlay.fill((0, 0, 0, 155))
                self.screen.blit(overlay, (0, 0))

                pygame.draw.rect(self.screen, (247, 242, 234), self._register_modal_rect, border_radius=8)
                pygame.draw.rect(self.screen, (0, 0, 0), self._register_modal_rect, 3, border_radius=8)
                close_text = self.font_s.render('X', False, (0, 0, 0))
                self.screen.blit(close_text, close_text.get_rect(center=self._register_close_rect.center))

                is_edit_mode = getattr(self, '_register_mode', 'create') == 'edit'
                title_label = 'Edit Custom AI' if is_edit_mode else 'Register Custom AI'
                title = self.font_m.render(title_label, False, (0, 0, 0))
                self.screen.blit(title, title.get_rect(midtop=(self._register_modal_rect.centerx, self._register_modal_rect.y + 18)))

                name_label = self.font_s.render('AI Name (required, max 20)', False, (0, 0, 0))
                desc_label = self.font_s.render('Description (optional, max 1000)', False, (0, 0, 0))
                file_prompt = 'Upload File (optional replacement, .py only)' if is_edit_mode else 'Upload File (required, .py only)'
                file_label = self.font_s.render(file_prompt, False, (0, 0, 0))
                self.screen.blit(name_label, (self._register_name_rect.x, self._register_name_rect.y - 28))
                self.screen.blit(desc_label, (self._register_desc_rect.x, self._register_desc_rect.y - 28))
                self.screen.blit(file_label, (self._register_file_rect.x, self._register_file_rect.y - 28))

                name_active = self._register_active_field == 'name'
                desc_active = self._register_active_field == 'description'
                pygame.draw.rect(self.screen, (255, 255, 255), self._register_name_rect)
                pygame.draw.rect(self.screen, (32, 32, 32), self._register_name_rect, 2 if not name_active else 3)
                pygame.draw.rect(self.screen, (255, 255, 255), self._register_desc_rect)
                pygame.draw.rect(self.screen, (32, 32, 32), self._register_desc_rect, 2 if not desc_active else 3)

                name_value = self.font_s.render(getattr(self, '_register_name_input', ''), False, (0, 0, 0))
                self.screen.blit(name_value, (self._register_name_rect.x + 10, self._register_name_rect.y + 10))
                desc_input = getattr(self, '_register_desc_input', '')
                line_h = self.font_register_desc.get_height() + 4
                visible_width = self._register_desc_rect.width - 28
                visible_height = self._register_desc_rect.height - 20

                wrapped_lines = []
                for raw_line in desc_input.split('\n'):
                    if raw_line == '':
                        wrapped_lines.append('')
                        continue
                    current_line = ''
                    for ch in raw_line:
                        test_line = current_line + ch
                        if self.font_register_desc.size(test_line)[0] <= visible_width:
                            current_line = test_line
                        else:
                            if current_line:
                                wrapped_lines.append(current_line)
                            current_line = ch
                    wrapped_lines.append(current_line)
                if not wrapped_lines:
                    wrapped_lines.append('')

                content_height = max(line_h, len(wrapped_lines) * line_h)
                max_scroll = max(0, content_height - visible_height)
                self._register_desc_scroll_y = max(0, min(getattr(self, '_register_desc_scroll_y', 0), max_scroll))

                clip_rect = pygame.Rect(
                    self._register_desc_rect.x + 8,
                    self._register_desc_rect.y + 6,
                    self._register_desc_rect.width - 20,
                    self._register_desc_rect.height - 12,
                )
                previous_clip = self.screen.get_clip()
                self.screen.set_clip(clip_rect)
                draw_y = self._register_desc_rect.y + 10 - self._register_desc_scroll_y
                for line in wrapped_lines:
                    if draw_y + line_h < self._register_desc_rect.y + 4:
                        draw_y += line_h
                        continue
                    if draw_y > self._register_desc_rect.bottom - 6:
                        break
                    if line:
                        line_surface = self.font_register_desc.render(line, False, (0, 0, 0))
                        self.screen.blit(line_surface, (self._register_desc_rect.x + 10, draw_y))
                    draw_y += line_h
                self.screen.set_clip(previous_clip)

                self._register_desc_scrollbar_rect = pygame.Rect(
                    self._register_desc_rect.right - 12,
                    self._register_desc_rect.y + 10,
                    6,
                    self._register_desc_rect.height - 20,
                )
                pygame.draw.rect(self.screen, (210, 210, 210), self._register_desc_scrollbar_rect, border_radius=3)
                thumb_height = self._register_desc_scrollbar_rect.height if max_scroll == 0 else max(36, int(self._register_desc_scrollbar_rect.height * (visible_height / max(content_height, 1))))
                track_range = max(0, self._register_desc_scrollbar_rect.height - thumb_height)
                thumb_y = self._register_desc_scrollbar_rect.y if max_scroll == 0 else self._register_desc_scrollbar_rect.y + int((self._register_desc_scroll_y / max_scroll) * track_range)
                self._register_desc_thumb_rect = pygame.Rect(
                    self._register_desc_scrollbar_rect.x,
                    thumb_y,
                    self._register_desc_scrollbar_rect.width,
                    thumb_height,
                )
                thumb_color = (150, 150, 150) if getattr(self, '_register_desc_scroll_dragging', False) else (170, 170, 170)
                pygame.draw.rect(self.screen, thumb_color, self._register_desc_thumb_rect, border_radius=3)

                upload_hover = self._register_file_rect.collidepoint(pygame.mouse.get_pos())
                pygame.draw.rect(self.screen, (220, 220, 220) if upload_hover else (236, 236, 236), self._register_file_rect, border_radius=5)
                pygame.draw.rect(self.screen, (0, 0, 0), self._register_file_rect, 2, border_radius=5)
                upload_text = self.font_s.render('Choose .py File', False, (0, 0, 0))
                self.screen.blit(upload_text, upload_text.get_rect(center=self._register_file_rect.center))

                selected_file_path = getattr(self, '_register_file_path', '')
                existing_file_path = getattr(self, '_register_existing_file_path', '')
                if selected_file_path:
                    selected_name = os.path.basename(selected_file_path)
                elif is_edit_mode and existing_file_path:
                    selected_name = f'Current: {os.path.basename(existing_file_path)}'
                else:
                    selected_name = 'No file selected'
                file_text = self.font_ss.render(selected_name, False, (30, 30, 30))
                self.screen.blit(file_text, (self._register_file_rect.right + 16, self._register_file_rect.y + 14))

                submit_hover = self._register_submit_rect.collidepoint(pygame.mouse.get_pos())
                pygame.draw.rect(self.screen, (202, 242, 184) if submit_hover else (214, 250, 196), self._register_submit_rect, border_radius=6)
                pygame.draw.rect(self.screen, (0, 0, 0), self._register_submit_rect, 2, border_radius=6)
                submit_label = 'Save' if getattr(self, '_register_mode', 'create') == 'edit' else 'Submit'
                submit_text = self.font_s.render(submit_label, False, (0, 0, 0))
                self.screen.blit(submit_text, submit_text.get_rect(center=self._register_submit_rect.center))

            if getattr(self, '_custom_ai_menu_open', False):
                menu_rect = self._custom_ai_menu_rect
                pygame.draw.rect(self.screen, (247, 242, 234), menu_rect, border_radius=8)
                pygame.draw.rect(self.screen, (0, 0, 0), menu_rect, 2, border_radius=8)

                title = self.font_s.render('Edit Custom AI', False, (0, 0, 0))
                self.screen.blit(title, title.get_rect(midtop=(menu_rect.centerx, menu_rect.y + 14)))

                edit_rect = self._custom_ai_menu_edit_rect
                delete_rect = self._custom_ai_menu_delete_rect
                mouse_pos = pygame.mouse.get_pos()

                edit_hovered = edit_rect.collidepoint(mouse_pos)
                pygame.draw.rect(self.screen, (238, 244, 255) if edit_hovered else (248, 250, 255), edit_rect, border_radius=6)
                pygame.draw.rect(self.screen, (0, 0, 0), edit_rect, 2, border_radius=6)
                edit_text = self.font_s.render('Edit', False, (0, 0, 0))
                self.screen.blit(edit_text, edit_text.get_rect(center=edit_rect.center))

                delete_hovered = delete_rect.collidepoint(mouse_pos)
                pygame.draw.rect(self.screen, (255, 238, 238) if delete_hovered else (255, 246, 246), delete_rect, border_radius=6)
                pygame.draw.rect(self.screen, (0, 0, 0), delete_rect, 2, border_radius=6)
                delete_text = self.font_s.render('Delete', False, (120, 0, 0))
                self.screen.blit(delete_text, delete_text.get_rect(center=delete_rect.center))

            if getattr(self, '_custom_ai_delete_popup_open', False):
                modal = self._custom_ai_delete_modal_rect
                overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
                overlay.fill((0, 0, 0, 120))
                self.screen.blit(overlay, (0, 0))

                pygame.draw.rect(self.screen, (247, 242, 234), modal, border_radius=8)
                pygame.draw.rect(self.screen, (0, 0, 0), modal, 3, border_radius=8)

                ai_name = getattr(self, '_custom_ai_delete_target_name', '')
                line1 = self.font_sm.render('Are you sure you want to delete', False, (0, 0, 0))
                line2 = self.font_s.render(f'custom ai: {ai_name} ?', False, (0, 0, 0))
                self.screen.blit(line1, line1.get_rect(center=(modal.centerx, modal.y + 98)))
                self.screen.blit(line2, line2.get_rect(center=(modal.centerx, modal.y + 142)))

                cancel_rect = self._custom_ai_delete_cancel_rect
                delete_rect = self._custom_ai_delete_confirm_rect
                mouse_pos = pygame.mouse.get_pos()
                cancel_hovered = cancel_rect.collidepoint(mouse_pos)
                delete_hovered = delete_rect.collidepoint(mouse_pos)

                pygame.draw.rect(self.screen, (232, 232, 232) if cancel_hovered else (240, 240, 240), cancel_rect, border_radius=6)
                pygame.draw.rect(self.screen, (0, 0, 0), cancel_rect, 2, border_radius=6)
                cancel_text = self.font_s.render('Cancel', False, (0, 0, 0))
                self.screen.blit(cancel_text, cancel_text.get_rect(center=cancel_rect.center))

                pygame.draw.rect(self.screen, (255, 214, 214) if delete_hovered else (255, 224, 224), delete_rect, border_radius=6)
                pygame.draw.rect(self.screen, (0, 0, 0), delete_rect, 2, border_radius=6)
                confirm_text = self.font_s.render('Delete', False, (120, 0, 0))
                self.screen.blit(confirm_text, confirm_text.get_rect(center=delete_rect.center))

            # Draw the map 'SELECT' box only when the map popup is active
            if getattr(self, '_map_popup_open', False) and not getattr(self, '_instr_popup_open', False):
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
            # Reduce height so the active-player banner (positioned below) doesn't overlap bottom UI
            objective_rect = pygame.Rect(left_x, terrain_rect.bottom + 10, left_w, 160)

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
                # Show status regardless of hard-coded team checks; interpret moved/acted flags for any hovered unit
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
            p1_row = self.p1_sel_cursor.grid[0]
            p2_row = self.p2_sel_cursor.grid[0]
            labels = AI_SELECTION_LABELS()
            p1_label = labels[p1_row] if 0 <= p1_row < len(labels) else 'Unknown'
            p2_label = labels[p2_row] if 0 <= p2_row < len(labels) else 'Unknown'
            text = self.font_ss.render(f'{p1_label} vs {p2_label}', False, (0, 0, 0))
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
            # Active player banner (top-right)
            try:
                active_team = getattr(self.GameMaster.activeAI, 'team', getattr(self.GameMaster, 'turn', 1))
                banner_text = f'P{active_team} Turn'
                banner_color = getattr(self.GameMaster.activeAI, 'color', LOG_COLOR_P1 if active_team == 1 else LOG_COLOR_P2)
                # Position banner below the Objective Info panel on the left column
                banner_rect = pygame.Rect(left_x, objective_rect.bottom + 8, left_w, 36)
                pygame.draw.rect(self.screen, banner_color, banner_rect)
                pygame.draw.rect(self.screen, (0, 0, 0), banner_rect, 2)
                bt = self.font_s.render(banner_text, False, (255, 255, 255))
                self.screen.blit(bt, bt.get_rect(center=banner_rect.center))
            except Exception:
                pass
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
            total_log_lines = self._get_total_wrapped_line_count(log_content_width)
            geom = self._calc_log_geometry(total_log_lines=total_log_lines)

            # panel fill + border
            pygame.draw.rect(self.screen, UI_PANEL, geom["log_rect"])
            pygame.draw.rect(self.screen, UI_BORDER, geom["log_rect"], 2)

            # header strip
            pygame.draw.rect(self.screen, UI_HEADER, geom["header_rect"])
            pygame.draw.rect(self.screen, UI_BORDER, geom["header_rect"], 2)

            title = self.font_s.render("Game Log", False, UI_TEXT)
            self.screen.blit(title, title.get_rect(topleft=(geom["header_rect"].x + 8, geom["header_rect"].y + 4)))

            # log lines (newest pinned at top; older lines below)
            x, y = geom["content_origin"]
            line_h = geom["line_h"]
            max_lines = geom["content_max_lines"]

            # clamp scroll to what can actually scroll right now
            max_scroll = geom["max_scroll"]
            if self.log_scroll > max_scroll:
                self.log_scroll = max_scroll
            if self.log_scroll < 0:
                self.log_scroll = 0

            start = max(0, self.log_scroll)
            visible_log_lines, _ = self._get_log_window_lines(log_content_width, start, max_lines)

            for log_tuple in visible_log_lines:
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

        # Keep transient alerts above every other UI layer.
        self._draw_start_alert_overlay()
        
        # --- Present base canvas to the OS window (scaled if needed) ---
        scaled_surface = pygame.transform.smoothscale(self.screen, self.display.get_size())
        self.display.blit(scaled_surface, (0, 0))
