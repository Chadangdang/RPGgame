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


class GameMainExportMixin:
    def export_game_log(self) -> None:
        """Export all played matches in one workbook with per-match Game Log + Match Summary sheets."""

        def safe_int(s, default=0):
            try:
                return int(s)
            except (ValueError, TypeError):
                return default

        def parse_match_number(message: str) -> int | None:
            if "Match " not in message:
                return None
            try:
                return int(message.split("Match ")[1].split()[0])
            except (ValueError, IndexError):
                return None

        def parse_round_number(message: str) -> int | None:
            if "Round " not in message:
                return None
            try:
                return int(message.split("Round ")[1].split()[0])
            except (ValueError, IndexError):
                return None

        def make_sheet_title(raw_title: str, used_titles: set[str]) -> str:
            # Excel/openpyxl constraints: max 31 chars and no []:*?/\
            invalid_chars = set('[]:*?/\\')
            cleaned = ''.join('_' if ch in invalid_chars else ch for ch in raw_title).strip()
            if not cleaned:
                cleaned = 'Sheet'
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

        try:
            wb = openpyxl.Workbook()
            wb.remove(wb.active)

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

            # Process oldest -> newest.
            ordered_logs = []
            for log_tuple in reversed(self.game_log):
                if len(log_tuple) == 3:
                    text, _color, time_elapsed = log_tuple
                else:
                    text, _color = log_tuple
                    time_elapsed = 0.0
                ordered_logs.append((text, float(time_elapsed)))

            matches_data: dict[int, dict] = {}
            current_match = 1
            current_round = 1

            def get_or_create_match(match_no: int) -> dict:
                if match_no not in matches_data:
                    matches_data[match_no] = {
                        "rows": [],
                        "winner": "Unknown",
                        "p1_rounds": 0,
                        "p2_rounds": 0,
                        "duration": 0.0,
                        "damage_t1": 0,
                        "damage_t2": 0,
                        "kills_t1": 0,
                        "kills_t2": 0,
                        "obj_t1": 0,
                        "obj_t2": 0,
                        "map_label": "Unknown",
                    }
                return matches_data[match_no]

            for log_entry, time_elapsed in ordered_logs:
                if "Match" in log_entry and "starts" in log_entry:
                    parsed_match = parse_match_number(log_entry)
                    if parsed_match is not None:
                        current_match = parsed_match
                    current_round = 1
                    match_data = get_or_create_match(current_match)
                    if "Map:" in log_entry:
                        try:
                            map_piece = log_entry.split("Map:", 1)[1]
                            map_label = map_piece.split("P1:", 1)[0].strip()
                            if map_label:
                                match_data["map_label"] = map_label
                        except Exception:
                            pass

                if "Round" in log_entry and "begins" in log_entry:
                    parsed_round = parse_round_number(log_entry)
                    if parsed_round is not None:
                        current_round = parsed_round

                if "Round" in log_entry and "ends" in log_entry:
                    parsed_round = parse_round_number(log_entry)
                    if parsed_round is not None:
                        current_round = parsed_round

                match_data = get_or_create_match(current_match)

                # Defaults for row columns
                scenario = log_entry
                team = 0
                health = 0
                position = ""
                event = "log"
                action_name = ""
                target_position = ""
                damage = 0
                heal = 0
                movement = ""
                target = ""
                target_health_before = ""
                target_health_after = ""
                target_team = ""

                # Track per-match objective control summary from game log lines
                if "SUMMARY : Team 1 Objective Control" in log_entry:
                    try:
                        match_data["obj_t1"] = safe_int(log_entry.split("=")[1].split("ticks")[0].strip())
                    except Exception:
                        pass
                elif "SUMMARY : Team 2 Objective Control" in log_entry:
                    try:
                        match_data["obj_t2"] = safe_int(log_entry.split("=")[1].split("ticks")[0].strip())
                    except Exception:
                        pass

                # Parse special summary lines
                if log_entry.startswith("SUMMARY : Result"):
                    event = "summary"
                    if "Winner: P1" in log_entry:
                        match_data["winner"] = "P1"
                    elif "Winner: P2" in log_entry:
                        match_data["winner"] = "P2"
                    try:
                        pieces = log_entry.split("P1 rounds = ", 1)[1]
                        p1_part, p2_part = pieces.split("P2 rounds = ", 1)
                        match_data["p1_rounds"] = safe_int(p1_part.strip())
                        match_data["p2_rounds"] = safe_int(p2_part.strip())
                    except Exception:
                        pass
                    match_data["duration"] = max(match_data["duration"], time_elapsed)

                elif "Match" in log_entry and "ends" in log_entry and "win" in log_entry:
                    event = "match_end"
                    parsed_match = parse_match_number(log_entry)
                    if parsed_match is not None:
                        current_match = parsed_match
                        match_data = get_or_create_match(current_match)
                    if "P1 win" in log_entry:
                        match_data["winner"] = "P1"
                    elif "P2 win" in log_entry:
                        match_data["winner"] = "P2"
                    match_data["duration"] = max(match_data["duration"], time_elapsed)

                elif " attacks " in log_entry and " with \"" in log_entry:
                    event = "attack"
                    attacker = log_entry.split(" attacks ")[0].strip()
                    scenario = log_entry
                    if "(T1)" in log_entry:
                        team = 1
                    elif "(T2)" in log_entry:
                        team = 2

                    if " attacks " in log_entry and " with \"" in log_entry:
                        left, right = log_entry.split(" attacks ", 1)
                        target = right.split(" with \"", 1)[0].strip()
                        action_name = right.split(" with \"", 1)[1].split("\"", 1)[0]

                    if "hit for" in log_entry:
                        try:
                            dmg_text = log_entry.split("hit for ", 1)[1].split(" ", 1)[0]
                            damage = safe_int(dmg_text)
                            if team == 1:
                                match_data["damage_t1"] += damage
                            elif team == 2:
                                match_data["damage_t2"] += damage
                        except Exception:
                            pass

                    if "(HP before:" in log_entry:
                        try:
                            hp_piece = log_entry.split("(HP before:", 1)[1].split(")", 1)[0]
                            hp_before_text, hp_after_text = hp_piece.split(", after:")
                            target_health_before = safe_int(hp_before_text.strip())
                            target_health_after = safe_int(hp_after_text.strip().split("/")[0])
                        except Exception:
                            pass

                    if " at " in log_entry:
                        target_position = log_entry.rsplit(" at ", 1)[1].strip()

                    unit_name = attacker.split(" (", 1)[0]
                    for chara in Character.team1_list + Character.team2_list:
                        if chara.template.get("display_name", "") == unit_name:
                            health = chara.template.get("curHP", 0)
                            position = f"{chara.grid[0]},{chara.grid[1]}"
                            break

                elif " uses \"" in log_entry and " - +" in log_entry:
                    event = "heal"
                    unit_name = log_entry.split(" uses \"", 1)[0]
                    if "(T1)" in log_entry:
                        team = 1
                    elif "(T2)" in log_entry:
                        team = 2
                    try:
                        action_name = log_entry.split(" uses \"", 1)[1].split("\"", 1)[0]
                        target = log_entry.split("\" on ", 1)[1].split(" - +", 1)[0].strip()
                        heal = safe_int(log_entry.split(" - +", 1)[1].split(" ", 1)[0])
                    except Exception:
                        pass

                    for chara in Character.team1_list + Character.team2_list:
                        if chara.template.get("display_name", "") == unit_name:
                            health = chara.template.get("curHP", 0)
                            position = f"{chara.grid[0]},{chara.grid[1]}"
                            break

                elif " is KO" in log_entry:
                    event = "kill"
                    target = log_entry.split(" is KO", 1)[0]
                    if "(T1)" in log_entry:
                        team = 1
                    elif "(T2)" in log_entry:
                        team = 2
                    if team == 1:
                        match_data["kills_t2"] += 1
                    elif team == 2:
                        match_data["kills_t1"] += 1

                elif "Pass turn" in log_entry:
                    event = "pass"
                    scenario = log_entry

                match_data["rows"].append({
                    "scenario": scenario,
                    "match": current_match,
                    "round": current_round,
                    "team": team,
                    "time_elapsed": time_elapsed,
                    "health": health,
                    "position": position,
                    "event": event,
                    "action_name": action_name,
                    "target_position": target_position,
                    "damage": damage,
                    "heal": heal,
                    "movement": movement,
                    "target": target,
                    "target_health_before": target_health_before,
                    "target_health_after": target_health_after,
                    "target_team": target_team,
                })

            if not matches_data:
                print("No game log data to export.")
                return

            # Create 2 sheets per match in order.
            column_widths = [5, 35, 8, 8, 6, 14, 10, 16, 12, 15, 12, 8, 8, 10, 18, 18, 18, 10]
            used_titles: set[str] = set()
            headers = [
                "No.", "Scenario", "Match", "Round", "Team", "Time (seconds)",
                "Health", "Position (Row, Col)", "Event", "Action name",
                "Target Position", "Damage", "Heal", "Movement",
                "Target", "Target Health before", "Target Health after", "Target Team"
            ]

            for match_no in sorted(matches_data.keys()):
                match_data = matches_data[match_no]

                # Mx: Game Log
                log_ws = wb.create_sheet(make_sheet_title(f"M{match_no}: Game Log", used_titles))
                for i, width in enumerate(column_widths, 1):
                    log_ws.column_dimensions[openpyxl.utils.get_column_letter(i)].width = width
                for col, header in enumerate(headers, 1):
                    cell = log_ws.cell(row=1, column=col, value=header)
                    cell.font = header_font
                    cell.fill = header_fill
                    cell.alignment = header_alignment
                    cell.border = thin_border

                for idx, row_data in enumerate(match_data["rows"], start=2):
                    log_ws.cell(row=idx, column=1, value=idx - 1).border = thin_border
                    log_ws.cell(row=idx, column=2, value=row_data["scenario"]).border = thin_border
                    log_ws.cell(row=idx, column=3, value=row_data["match"]).border = thin_border
                    log_ws.cell(row=idx, column=4, value=row_data["round"]).border = thin_border
                    log_ws.cell(row=idx, column=5, value=row_data["team"]).border = thin_border
                    log_ws.cell(row=idx, column=6, value=row_data["time_elapsed"]).border = thin_border
                    log_ws.cell(row=idx, column=7, value=row_data["health"]).border = thin_border
                    log_ws.cell(row=idx, column=8, value=row_data["position"]).border = thin_border
                    log_ws.cell(row=idx, column=9, value=row_data["event"]).border = thin_border
                    log_ws.cell(row=idx, column=10, value=row_data["action_name"]).border = thin_border
                    log_ws.cell(row=idx, column=11, value=row_data["target_position"]).border = thin_border
                    log_ws.cell(row=idx, column=12, value=row_data["damage"]).border = thin_border
                    log_ws.cell(row=idx, column=13, value=row_data["heal"]).border = thin_border
                    log_ws.cell(row=idx, column=14, value=row_data["movement"]).border = thin_border
                    log_ws.cell(row=idx, column=15, value=row_data["target"]).border = thin_border
                    log_ws.cell(row=idx, column=16, value=row_data["target_health_before"]).border = thin_border
                    log_ws.cell(row=idx, column=17, value=row_data["target_health_after"]).border = thin_border
                    log_ws.cell(row=idx, column=18, value=row_data["target_team"]).border = thin_border

                # Mx: Match Summary
                summary_ws = wb.create_sheet(make_sheet_title(f"M{match_no}: Match Summary", used_titles))
                summary_ws.column_dimensions['A'].width = 35
                summary_ws.column_dimensions['B'].width = 30
                title_cell = summary_ws.cell(1, 1, f"M{match_no} Match Summary")
                title_cell.font = summary_title_font
                title_cell.fill = summary_title_fill
                summary_ws.merge_cells('A1:B1')

                row = 2
                summary_ws.cell(row, 1, "Map").font = Font(bold=True)
                summary_ws.cell(row, 2, match_data["map_label"])
                row += 1
                summary_ws.cell(row, 1, "Winner").font = Font(bold=True)
                summary_ws.cell(row, 2, match_data["winner"])
                row += 1
                summary_ws.cell(row, 1, "Rounds (P1-P2)").font = Font(bold=True)
                summary_ws.cell(row, 2, f"{match_data['p1_rounds']}-{match_data['p2_rounds']}")
                row += 1
                summary_ws.cell(row, 1, "Duration (seconds)").font = Font(bold=True)
                summary_ws.cell(row, 2, f"{match_data['duration']:.2f}")
                row += 1
                summary_ws.cell(row, 1, "Damage Dealt Team 1").font = Font(bold=True)
                summary_ws.cell(row, 2, match_data["damage_t1"])
                row += 1
                summary_ws.cell(row, 1, "Damage Dealt Team 2").font = Font(bold=True)
                summary_ws.cell(row, 2, match_data["damage_t2"])
                row += 1
                summary_ws.cell(row, 1, "Kills by Team 1").font = Font(bold=True)
                summary_ws.cell(row, 2, match_data["kills_t1"])
                row += 1
                summary_ws.cell(row, 1, "Kills by Team 2").font = Font(bold=True)
                summary_ws.cell(row, 2, match_data["kills_t2"])
                row += 1

                total_obj = match_data["obj_t1"] + match_data["obj_t2"]
                t1_pct = (match_data["obj_t1"] / total_obj * 100) if total_obj else 0.0
                t2_pct = (match_data["obj_t2"] / total_obj * 100) if total_obj else 0.0
                summary_ws.cell(row, 1, "Objective Control Team 1").font = Font(bold=True)
                summary_ws.cell(row, 2, f"{match_data['obj_t1']} ({t1_pct:.2f}%)")
                row += 1
                summary_ws.cell(row, 1, "Objective Control Team 2").font = Font(bold=True)
                summary_ws.cell(row, 2, f"{match_data['obj_t2']} ({t2_pct:.2f}%)")

            # Save one workbook with all per-match sheets.
            export_dir = "exports"
            os.makedirs(export_dir, exist_ok=True)
            filename = f"{export_dir}/game_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            wb.save(filename)
            print(f"Game log exported to: {filename}")

        except Exception as e:
            print(f"Error exporting game log: {e}")
            import traceback
            traceback.print_exc()
