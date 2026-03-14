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
from pathlib import Path

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


class GameMainExportMixin:
    def export_game_log(self) -> None:
        """Export all played games into one workbook with per-game log + summary sheets."""

        def convert_to_board_position(row, col) -> str:
            try:
                row_int = int(row)
                col_int = int(col)
            except (TypeError, ValueError):
                return ""
            if col_int < 0:
                return ""
            column_letter = chr(ord('A') + col_int)
            return f"{column_letter}{row_int}"

        def normalize_position(value) -> str:
            if value is None:
                return ""
            value_str = str(value).strip()
            if not value_str:
                return ""

            upper_value = value_str.upper()
            if len(upper_value) >= 2 and upper_value[0].isalpha() and upper_value[1:].isdigit():
                return upper_value

            if "," in value_str:
                parts = [part.strip() for part in value_str.split(",", 1)]
                if len(parts) == 2:
                    return convert_to_board_position(parts[0], parts[1])

            return value_str

        def make_sheet_title(raw_title: str, used_titles: set[str]) -> str:
            invalid_chars = set('[]:*?/\\')
            cleaned = ''.join('_' if ch in invalid_chars else ch for ch in raw_title).strip() or 'Sheet'
            cleaned = cleaned[:31]
            if cleaned not in used_titles:
                used_titles.add(cleaned)
                return cleaned

            suffix = 2
            while True:
                suffix_text = f"_{suffix}"
                base = cleaned[:31 - len(suffix_text)]
                candidate = f"{base}{suffix_text}"
                if candidate not in used_titles:
                    used_titles.add(candidate)
                    return candidate
                suffix += 1

        def as_int(value, default=0) -> int:
            try:
                return int(value)
            except (TypeError, ValueError):
                return default

        def as_float(value, default=0.0) -> float:
            try:
                return float(value)
            except (TypeError, ValueError):
                return default

        try:
            if not self.game_log:
                print("No game log data to export.")
                return

            wb = openpyxl.Workbook()
            wb.remove(wb.active)

            header_font = Font(bold=True, color="FFFFFF")
            header_fill = PatternFill(start_color="FFA500", end_color="FFA500", fill_type="solid")
            header_alignment = Alignment(horizontal="center", vertical="center")
            thin_border = Border(
                left=Side(style='thin'), right=Side(style='thin'), top=Side(style='thin'), bottom=Side(style='thin')
            )
            summary_title_font = Font(bold=True, color="FFFFFF", size=13)
            summary_title_fill = PatternFill(start_color="FF0000", end_color="FF0000", fill_type="solid")
            summary_metric_font = Font(bold=True)
            summary_metric_fill = PatternFill(start_color="00B050", end_color="00B050", fill_type="solid")
            summary_value_font = Font(bold=False, color="000000")
            summary_value_fill = PatternFill(fill_type=None)

            # Oldest -> newest already preserved by structured append order.
            ordered_logs = [entry for entry in self.game_log if isinstance(entry, dict)]
            if not ordered_logs:
                print("No structured game log data to export.")
                return

            games_data: dict[int, dict] = {}

            def get_or_create_game(game_no: int) -> dict:
                if game_no not in games_data:
                    games_data[game_no] = {
                        "rows": [],
                        "match": 0,
                        "map": "",
                        "winner": "",
                        "duration": 0.0,
                        "damage_p1": 0,
                        "damage_p2": 0,
                        "kills_p1": 0,
                        "kills_p2": 0,
                        "obj_p1": 0,
                        "obj_p2": 0,
                        "p1_model": "",
                        "p2_model": "",
                        "duration_sum": 0.0,
                    }
                return games_data[game_no]

            for entry in ordered_logs:
                game_no = as_int(entry.get("game", 1), 1)
                game_data = get_or_create_game(game_no)
                game_data["rows"].append(entry)

                game_data["match"] = max(game_data["match"], as_int(entry.get("match", 0), 0))
                game_data["duration"] = max(game_data["duration"], as_float(entry.get("duration", entry.get("time", 0.0)), 0.0))
                game_data["duration_sum"] += as_float(entry.get("time", 0.0), 0.0)

                if not game_data["map"] and entry.get("map"):
                    game_data["map"] = str(entry.get("map", ""))
                if entry.get("winner"):
                    game_data["winner"] = str(entry.get("winner", ""))
                if not game_data["p1_model"] and entry.get("p1_model"):
                    game_data["p1_model"] = str(entry.get("p1_model", ""))
                if not game_data["p2_model"] and entry.get("p2_model"):
                    game_data["p2_model"] = str(entry.get("p2_model", ""))

                team = as_int(entry.get("team", 0), 0)
                damage = as_int(entry.get("damage", 0), 0)
                if team == 1:
                    game_data["damage_p1"] += damage
                elif team == 2:
                    game_data["damage_p2"] += damage

                if str(entry.get("action_type", "")).lower() == "ko":
                    if team == 1:
                        game_data["kills_p2"] += 1
                    elif team == 2:
                        game_data["kills_p1"] += 1

                game_data["obj_p1"] = max(game_data["obj_p1"], as_int(entry.get("objective_control_p1", 0), 0))
                game_data["obj_p2"] = max(game_data["obj_p2"], as_int(entry.get("objective_control_p2", 0), 0))

            total_games = len(games_data)
            if total_games == 0:
                print("No game log data to export.")
                return

            p1_wins = sum(1 for data in games_data.values() if data.get("winner") == "P1")
            p2_wins = sum(1 for data in games_data.values() if data.get("winner") == "P2")
            winrate_p1 = (p1_wins / total_games * 100.0) if total_games else 0.0
            winrate_p2 = (p2_wins / total_games * 100.0) if total_games else 0.0

            headers = [
                "No.", "Log", "Match", "Round", "Team", "Time (seconds)", "Class", "Health",
                "Position", "Action type", "Action name", "Target Class", "Target Position",
                "Damage", "Heal", "Target Health before", "Target Health after"
            ]
            column_widths = [6, 48, 8, 8, 6, 14, 18, 10, 18, 14, 18, 18, 18, 10, 10, 20, 20]
            used_titles: set[str] = set()

            for game_no in sorted(games_data.keys()):
                game_data = games_data[game_no]

                log_ws = wb.create_sheet(make_sheet_title(f"G{game_no}_game_log", used_titles))
                for i, width in enumerate(column_widths, 1):
                    log_ws.column_dimensions[openpyxl.utils.get_column_letter(i)].width = width

                for col, header in enumerate(headers, 1):
                    cell = log_ws.cell(row=1, column=col, value=header)
                    cell.font = header_font
                    cell.fill = header_fill
                    cell.alignment = header_alignment
                    cell.border = thin_border

                for index, entry in enumerate(game_data["rows"], start=1):
                    position = normalize_position(entry.get("position", ""))
                    target_position = normalize_position(entry.get("target_position", ""))
                    row_values = [
                        index,
                        str(entry.get("log", "")),
                        as_int(entry.get("match", 0), 0),
                        as_int(entry.get("round", 0), 0),
                        as_int(entry.get("team", 0), 0),
                        as_float(entry.get("time", 0.0), 0.0),
                        str(entry.get("class", "")),
                        as_int(entry.get("health", 0), 0),
                        position,
                        str(entry.get("action_type", "")),
                        str(entry.get("action_name", "")),
                        str(entry.get("target_class", "")),
                        target_position,
                        as_int(entry.get("damage", 0), 0),
                        as_int(entry.get("heal", 0), 0),
                        as_int(entry.get("target_hp_before", 0), 0),
                        as_int(entry.get("target_hp_after", 0), 0),
                    ]
                    log_ws.append(row_values)
                    for col in range(1, len(row_values) + 1):
                        log_ws.cell(row=index + 1, column=col).border = thin_border

                summary_ws = wb.create_sheet(make_sheet_title(f"G{game_no}_summary", used_titles))
                summary_ws.column_dimensions['A'].width = 28
                summary_ws.column_dimensions['B'].width = 32

                title_cell = summary_ws.cell(row=1, column=1, value=f"Game {game_no} Summary")
                title_cell.font = summary_title_font
                title_cell.fill = summary_title_fill
                title_cell.alignment = header_alignment
                title_cell.border = thin_border
                summary_ws.merge_cells('A1:B1')
                summary_ws.cell(row=1, column=2).border = thin_border

                total_obj = game_data["obj_p1"] + game_data["obj_p2"]
                obj_p1_pct = (game_data["obj_p1"] / total_obj * 100.0) if total_obj else 0.0
                obj_p2_pct = (game_data["obj_p2"] / total_obj * 100.0) if total_obj else 0.0

                summary_data = [
                    ("P1 Model", game_data["p1_model"] or "Unknown"),
                    ("P2 Model", game_data["p2_model"] or "Unknown"),
                    ("Match", game_data["match"]),
                    ("Map", game_data["map"] or "Unknown"),
                    ("Winner", game_data["winner"] or "Unknown"),
                    ("Duration (seconds)", round(game_data["duration_sum"], 2)),
                    ("Damage Dealt P1", game_data["damage_p1"]),
                    ("Damage Dealt P2", game_data["damage_p2"]),
                    ("Kills by P1", game_data["kills_p1"]),
                    ("Kills by P2", game_data["kills_p2"]),
                    ("Objective Control P1", f"{game_data['obj_p1']} ({obj_p1_pct:.2f}%)"),
                    ("Objective Control P2", f"{game_data['obj_p2']} ({obj_p2_pct:.2f}%)"),
                    ("Win rate P1", f"{winrate_p1:.2f}%"),
                    ("Win rate P2", f"{winrate_p2:.2f}%"),
                ]

                for row_idx, (metric, value) in enumerate(summary_data, start=2):
                    metric_cell = summary_ws.cell(row=row_idx, column=1, value=metric)
                    metric_cell.font = summary_metric_font
                    metric_cell.fill = summary_metric_fill
                    metric_cell.alignment = Alignment(horizontal="left", vertical="center")
                    metric_cell.border = thin_border

                    value_cell = summary_ws.cell(row=row_idx, column=2, value=value)
                    value_cell.font = summary_value_font
                    value_cell.fill = summary_value_fill
                    value_cell.alignment = Alignment(horizontal="left", vertical="center")
                    value_cell.border = thin_border

            desktop = Path.home() / "Desktop"
            export_dir = desktop / "RPG Simulation Export"
            export_dir.mkdir(parents=True, exist_ok=True)

            filename = f"game_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            filepath = export_dir / filename
            wb.save(filepath)
            print(f"Game log exported to: {filepath}")

        except Exception as e:
            print(f"Error exporting game log: {e}")
            import traceback
            traceback.print_exc()
