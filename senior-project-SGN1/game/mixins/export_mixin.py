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
            # Total Matches Played
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
                    
            # ------------------------------------------------
            # ⭐ ADD OBJECTIVE CONTROL BELOW KILL DETAILS ⭐
            # ------------------------------------------------
            row += 1  # One empty line for spacing

            summary_ws.cell(row, 1, "Objective Control:").font = Font(bold=True)
            row += 1

            team1_obj = self.obj_control_team1
            team2_obj = self.obj_control_team2
            total_obj = team1_obj + team2_obj

            team1_obj_pct = (team1_obj / total_obj * 100) if total_obj > 0 else 0
            team2_obj_pct = (team2_obj / total_obj * 100) if total_obj > 0 else 0

            summary_ws.cell(row, 1, f"- Team 1 control ticks: {team1_obj}")
            row += 1
            summary_ws.cell(row, 1, f"- Team 2 control ticks: {team2_obj}")
            row += 1
            summary_ws.cell(row, 1, f"- Team 1 Control %: {team1_obj_pct:.2f}%")
            row += 1
            summary_ws.cell(row, 1, f"- Team 2 Control %: {team2_obj_pct:.2f}%")
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
