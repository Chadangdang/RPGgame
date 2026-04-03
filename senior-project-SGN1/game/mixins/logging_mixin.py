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
    'Aggressive Personality Cores AI',
    'Strategic Personality Cores AI',
    'Survival Personality Cores AI',
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
LOG_COLOR_MATCH   = (60, 60, 60)      # dark gray
LOG_COLOR_ROUND   = (255, 165, 0)     # orange
LOG_COLOR_P1      = (54, 92, 168)     # blue
LOG_COLOR_P2      = (178, 64, 64)     # red
LOG_COLOR_SYSTEM  = (120, 120, 120)   # medium gray
LOG_COLOR_SUMMARY = (22, 138, 36)     # green
LOG_COLOR_SESSION_SUMMARY = (75, 0, 130)  # indigo (#4B0082)

GAME_BAR = "=" * 50
MATCH_BAR = "-" * 30

# --- Scrollbar colors ---
SB_TRACK       = (220, 213, 200)
SB_THUMB       = (160, 150, 135)
SB_THUMB_HOVER = (145, 135, 120)
SB_THUMB_DRAG  = (130, 120, 105)

class GameMainLoggingMixin:
    def get_balance_mode(self) -> str:
        """Return the selected balance mode, defaulting to BASELINE."""
        settings = getattr(self, "settings", None)
        mode = getattr(settings, "balance_mode", balance_controller.BASELINE)
        mode_name = str(mode).strip().upper()
        valid_modes = {
            balance_controller.BASELINE,
            balance_controller.PASSIVE,
            balance_controller.WEAKNESS,
            balance_controller.COMBINED,
        }
        return mode_name if mode_name in valid_modes else balance_controller.BASELINE

    def _is_passive_logging_mode(self) -> bool:
        return self.get_balance_mode() in {balance_controller.PASSIVE, balance_controller.COMBINED}

    def _is_weakness_logging_mode(self) -> bool:
        return self.get_balance_mode() in {balance_controller.WEAKNESS, balance_controller.COMBINED}

    def _ensure_balance_counters(self) -> None:
        if not hasattr(self, "passive_trigger_count"):
            self.passive_trigger_count = 0
        if not hasattr(self, "weakness_trigger_count"):
            self.weakness_trigger_count = 0

    def _log_balance_summary(self, time_elapsed: float = 0.0) -> None:
        self._ensure_balance_counters()
        mode = self.get_balance_mode()
        if mode == balance_controller.BASELINE:
            return
        if mode in {balance_controller.PASSIVE, balance_controller.COMBINED}:
            self.log(
                f"SUMMARY : Passive triggers -> {self.passive_trigger_count}",
                LOG_COLOR_SUMMARY,
                time_elapsed=time_elapsed,
            )
        if mode in {balance_controller.WEAKNESS, balance_controller.COMBINED}:
            self.log(
                f"SUMMARY : Weakness bonuses -> {self.weakness_trigger_count}",
                LOG_COLOR_SUMMARY,
                time_elapsed=time_elapsed,
            )

    def _find_character_by_name(self, display_name: str):
        for chara in Character.team1_list + Character.team2_list:
            if chara.template.get("display_name", "") == display_name:
                return chara
        return None

    def _log_weakness_multiplier_for_attack(self, team: int, actor: str, target: str, time_elapsed: float = 0.0) -> None:
        if not self._is_weakness_logging_mode():
            return
        self._ensure_balance_counters()
        actor_chara = self._find_character_by_name(actor)
        target_chara = self._find_character_by_name(target)
        if not actor_chara or not target_chara:
            return

        multiplier = balance_controller.weakness_mode.weakness_multiplier(
            actor_chara.template.get("display_name", ""),
            target_chara.template.get("display_name", ""),
        )
        if multiplier > 1.0:
            self.log(
                f"SYSTEM : Weakness multiplier applied ({multiplier:.1f}x)",
                LOG_COLOR_SYSTEM,
                time_elapsed=time_elapsed,
            )
            self.weakness_trigger_count += 1
        elif multiplier < 1.0:
            self.log(
                f"SYSTEM : Resistance applied ({multiplier:.1f}x)",
                LOG_COLOR_SYSTEM,
                time_elapsed=time_elapsed,
            )
            self.weakness_trigger_count += 1

    def _format_system_message(self, message: str, team: int) -> str:
        trimmed = str(message).strip()
        if not trimmed:
            return "System event"
        return f"{trimmed} (P{team})"

    def _snapshot_actor_state(self, actor_name: str) -> tuple[int, str]:
        for chara in Character.team1_list + Character.team2_list:
            if chara.template.get("display_name", "") == actor_name:
                hp = int(chara.template.get("curHP", 0) or 0)
                row, col = chara.grid
                return hp, f"{row},{col}"
        return 0, ""

    def _log_default_entry(self, text: str, color: tuple[int, int, int], time_elapsed: float) -> dict:
        return {
            "log": text,
            "match": int(getattr(self, "current_match", 0) or 0),
            "round": int(getattr(self, "current_round", 0) or 0),
            "team": 0,
            "time": float(time_elapsed or 0.0),
            "class": "",
            "health": 0,
            "position": "",
            "action_type": "",
            "action_name": "",
            "target_class": "",
            "target_position": "",
            "damage": 0,
            "heal": 0,
            "target_hp_before": 0,
            "target_hp_after": 0,
            "game": int(getattr(self, "current_game", 1) or 1),
            "map": str(getattr(self, "_current_map_label", "") or ""),
            "winner": "",
            "duration": 0.0,
            "objective_control_p1": 0,
            "objective_control_p2": 0,
            "p1_rounds": 0,
            "p2_rounds": 0,
            "p1_model": "",
            "p2_model": "",
            "_color": color,
        }

    def log(self, text: str, color=(0, 0, 0), time_elapsed=0.0, **fields) -> None:
        """Append a structured line to the game log."""
        pinned_to_top = getattr(self, "log_scroll", 0) == 0
        entry = self._log_default_entry(text=text, color=color, time_elapsed=float(time_elapsed or 0.0))
        entry.update(fields)
        self.game_log.insert(0, entry)
        if len(self.game_log) > 500:  # prevent unbounded growth
            self.game_log.pop()

        # Keep auto-follow on the newest line only when the user was already pinned there.
        if pinned_to_top:
            self.log_scroll = 0

    def log_event(self, event: str, **kwargs) -> None:
        """Build and append a formatted structured log entry for a game event."""
        tag_labels = {
            "GAME": "GAME : ",
            "MATCH": "MATCH : ",
            "ROUND": "ROUND : ",
            "P1": "P1 : ",
            "P2": "P2 : ",
            "SYSTEM": "SYSTEM : ",
            "SUMMARY": "SUMMARY : "
        }

        def tag_color(tag: str) -> tuple[int, int, int]:
            return {
                "GAME": LOG_COLOR_GAME,
                "MATCH": LOG_COLOR_MATCH,
                "ROUND": LOG_COLOR_ROUND,
                "P1": LOG_COLOR_P1,
                "P2": LOG_COLOR_P2,
                "SYSTEM": LOG_COLOR_SYSTEM,
                "SUMMARY": LOG_COLOR_SUMMARY,
            }.get(tag, UI_TEXT)

        def board_label(grid: tuple[int, int] | None) -> str:
            if grid is None:
                return ""
            row, col = grid
            return f"{chr(ord('A') + col)}{GRID_ROWS - row}"

        tag = "GAME"
        message = ""
        event_fields: dict = {}

        if event == "game_start":
            time_elapsed = kwargs.get("time_elapsed", 0.0)
            self.log(f"GAME : {GAME_BAR}", tag_color("GAME"), time_elapsed=time_elapsed)
            self.log(f"GAME : Game {kwargs.get('game')} begins", tag_color("GAME"), time_elapsed=time_elapsed, game=int(kwargs.get('game', getattr(self, 'current_game', 1))))
            return
        elif event == "match_start":
            self._ensure_balance_counters()
            self.passive_trigger_count = 0
            self.weakness_trigger_count = 0
            match_number = kwargs.get("match")
            message = f"{MATCH_BAR[:8]} Match {match_number} {MATCH_BAR[:8]}"
            time_elapsed = kwargs.get("time_elapsed", 0.0)
            if match_number == 1:
                self.log(
                    "GAME : Map: {map_label} | P1: {ai1} vs P2: {ai2}".format(
                        map_label=kwargs.get("map_label", ""),
                        ai1=kwargs.get("ai1", ""),
                        ai2=kwargs.get("ai2", ""),
                    ),
                    tag_color("GAME"),
                    time_elapsed=time_elapsed,
                    game=int(kwargs.get('game', getattr(self, 'current_game', 1))),
                    map=str(kwargs.get("map_label", "") or ""),
                    p1_model=str(kwargs.get("ai1", "") or ""),
                    p2_model=str(kwargs.get("ai2", "") or ""),
                )
                self.log(
                    f"GAME : Balance Mode -> {self.get_balance_mode()}",
                    tag_color("GAME"),
                    time_elapsed=time_elapsed,
                    game=int(kwargs.get('game', getattr(self, 'current_game', 1))),
                )
            return self.log(
                f"MATCH : {message}",
                tag_color("MATCH"),
                time_elapsed=time_elapsed,
                match=int(match_number or getattr(self, "current_match", 0) or 0),
                game=int(kwargs.get('game', getattr(self, 'current_game', 1))),
            )
        elif event == "round_begin":
            tag = "ROUND"
            message = f"Round {kwargs.get('round')} begins"
        elif event == "round_end":
            tag = "ROUND"
            message = f"Round {kwargs.get('round')} ends"
        elif event == "game_end":
            time_elapsed = kwargs.get("time_elapsed", 0.0)
            game_number = kwargs.get("game")
            winner = kwargs.get("winner", "")
            p1_matches = kwargs.get("p1_matches", 0)
            p2_matches = kwargs.get("p2_matches", 0)
            # Ensure numeric `game` field matches the message text (avoid mismatch after increment)
            self.log(f"GAME : Game {game_number} ends", tag_color("GAME"), time_elapsed=time_elapsed, game=int(game_number or getattr(self, 'current_game', 1)))
            self.log(f"SUMMARY : Game winner -> {winner}", tag_color("SUMMARY"), time_elapsed=time_elapsed, game=int(game_number or getattr(self, 'current_game', 1)), winner=winner)
            self.log(f"SUMMARY : P1 won {p1_matches} matches", tag_color("SUMMARY"), time_elapsed=time_elapsed, game=int(game_number or getattr(self, 'current_game', 1)))
            self.log(f"SUMMARY : P2 won {p2_matches} matches", tag_color("SUMMARY"), time_elapsed=time_elapsed, game=int(game_number or getattr(self, 'current_game', 1)))
            self.log(f"SUMMARY : Game {game_number} finished", tag_color("SUMMARY"), time_elapsed=time_elapsed, game=int(game_number or getattr(self, 'current_game', 1)))
            self.log(f"GAME : {GAME_BAR}", tag_color("GAME"), time_elapsed=time_elapsed, game=int(game_number or getattr(self, 'current_game', 1)))
            return
        elif event == "move":
            team = int(kwargs.get("team") or 0)
            tag = "P1" if team == 1 else "P2"
            actor = kwargs.get("actor", "")
            start = board_label(kwargs.get("start"))
            end = board_label(kwargs.get("end"))
            distance = int(kwargs.get("distance", 0) or 0)
            tile_word = "tile" if distance == 1 else "tiles"
            message = f"{actor} moves {start} -> {end} ({distance} {tile_word})"
            health, position = self._snapshot_actor_state(actor)
            event_fields.update({
                "team": team,
                "class": actor,
                "health": health,
                "position": position,
                "action_type": "move",
                "action_name": "Move",
                "target_position": end,
            })
        elif event == "attack":
            team = int(kwargs.get("team") or 0)
            tag = "P1" if team == 1 else "P2"
            actor = kwargs.get("actor", "")
            target = kwargs.get("target", "")
            action = kwargs.get("action", "")
            amount = int(kwargs.get("amount", 0) or 0)
            message = f"{actor} uses \"{action}\" on {target} -> {amount} dmg"
            self._log_weakness_multiplier_for_attack(
                team=team,
                actor=actor,
                target=target,
                time_elapsed=kwargs.get("time_elapsed", 0.0),
            )
            health, position = self._snapshot_actor_state(actor)
            event_fields.update({
                "team": team,
                "class": actor,
                "health": health,
                "position": position,
                "action_type": "attack",
                "action_name": action,
                "target_class": target,
                "target_position": kwargs.get("target_position", "") or "",
                "damage": amount,
                "heal": 0,
                "target_hp_before": int(kwargs.get("hp_before", 0) or 0),
                "target_hp_after": int(kwargs.get("hp_cur", 0) or 0),
            })
        elif event == "heal":
            team = int(kwargs.get("team") or 0)
            tag = "P1" if team == 1 else "P2"
            actor = kwargs.get("actor", "")
            target = kwargs.get("target", "")
            action = kwargs.get("action", "")
            amount = int(kwargs.get("amount", 0) or 0)
            cur = int(kwargs.get("hp_cur", 0) or 0)
            max_hp = int(kwargs.get("hp_max", 0) or 0)
            message = f"{actor} heals {target} with \"{action}\" -> +{amount} HP ({cur}/{max_hp})"
            health, position = self._snapshot_actor_state(actor)
            event_fields.update({
                "team": team,
                "class": actor,
                "health": health,
                "position": position,
                "action_type": "heal",
                "action_name": action,
                "target_class": target,
                "damage": 0,
                "heal": amount,
                "target_hp_before": max(0, cur - amount),
                "target_hp_after": cur,
            })
        elif event == "pass":
            team = int(kwargs.get("team") or 0)
            tag = "P1" if team == 1 else "P2"
            message = "Pass turn"
            event_fields.update({"team": team, "action_type": "pass", "action_name": "Pass"})
        elif event == "ko":
            team = int(kwargs.get("team") or 0)
            tag = "P1" if team == 1 else "P2"
            actor = kwargs.get("actor", "")
            location = board_label(kwargs.get("location"))
            by_actor = kwargs.get("by_actor")
            by_action = kwargs.get("by_action")
            source = by_actor or "Unknown"
            if by_action:
                source = f"{source} ({by_action})"
            message = f"{actor} KO'd by {source}"
            if location:
                message += f" at {location}"
            event_fields.update({"team": team, "class": actor, "position": location, "action_type": "ko", "target_class": actor})
        elif event == "match_end":
            tag = "SUMMARY"
            event_fields.update({
                "action_type": "match_end",
                "winner": kwargs.get("winner", ""),
                "duration": float(kwargs.get("time_elapsed", 0.0) or 0.0),
                "p1_rounds": int(kwargs.get("p1_rounds", 0) or 0),
                "p2_rounds": int(kwargs.get("p2_rounds", 0) or 0),
                "objective_control_p1": int(getattr(self, "obj_control_team1", 0) or 0),
                "objective_control_p2": int(getattr(self, "obj_control_team2", 0) or 0),
            })
        elif event == "summary_match":
            tag = "SUMMARY"
            message = f"Match {kwargs.get('match')} ends"
            event_fields.update({"action_type": "summary_match", "map": str(kwargs.get("map_label", "") or "")})
        elif event == "summary_result":
            tag = "SUMMARY"
            message = ("Match result -> {winner} wins ({p1}-{p2} rounds)".format(
                winner=kwargs.get("winner", ""),
                p1=kwargs.get("p1_rounds", 0),
                p2=kwargs.get("p2_rounds", 0)
            ))
            event_fields.update({"action_type": "summary_result"})
        elif event == "summary":
            tag = "SUMMARY"
            message = kwargs.get("message", "")
            event_fields.update({"action_type": "summary"})
        elif event == "summary_game":
            tag = "SUMMARY"
            p1_matches = int(kwargs.get("p1_matches", 0) or 0)
            p2_matches = int(kwargs.get("p2_matches", 0) or 0)
            winner = "P1" if p1_matches > p2_matches else "P2" if p2_matches > p1_matches else "Draw"
            message = f"Game result -> {winner} wins ({p1_matches}-{p2_matches} matches)"
            event_fields.update({"action_type": "summary_game", "winner": winner})
        else:
            message = kwargs.get("message", "")

        label = tag_labels.get(tag, "")
        time_elapsed = float(kwargs.get("time_elapsed", 0.0) or 0.0)
        if message:
            self.log(f"{label}{message}", tag_color(tag), time_elapsed=time_elapsed, **event_fields)
        if event in {"round_end", "match_end"}:
            self._log_balance_summary(time_elapsed=time_elapsed)

    def _get_ai_label(self, team_id: int) -> str:
        if 0 <= team_id < len(self._ai_type_labels):
            return self._ai_type_labels[team_id]
        return 'Unknown'

    def _log_session_summary(self) -> None:
        """Append a formatted summary of the completed session to the game log."""
        if self._game_summary_logged:
            return

        if self.total_games_p1 > self.total_games_p2:
            winner = "P1"
        elif self.total_games_p2 > self.total_games_p1:
            winner = "P2"
        else:
            winner = "Draw"

        self.log(f"SUMMARY : P1 won {self.total_games_p1} games", LOG_COLOR_SESSION_SUMMARY)
        self.log(f"SUMMARY : P2 won {self.total_games_p2} games", LOG_COLOR_SESSION_SUMMARY)
        self.log(f"SUMMARY : Overall winner -> {winner}", LOG_COLOR_SESSION_SUMMARY)
        self.log("SUMMARY : Session finished", LOG_COLOR_SESSION_SUMMARY)

        self._game_summary_logged = True

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
                stripped = line.strip()
                if "moves to grid" in line:
                    queue.pop(idx)
                    continue
                if "passes" in line:
                    queue.pop(idx)
                    self.log_event("pass", team=team, time_elapsed=self.cumulative_time)
                    continue
                # Passive / status messages created by Character.attack() are added
                # as extra lines (indented). Detect common passive keywords and
                # convert them directly into colored log entries.
                passive_detected = False
                passive_message = stripped
                if stripped:
                    low = stripped.lower()
                    passive_keywords = (
                        "lifesteal",
                        "burn",
                        "poison",
                        "shield",
                        "regen",
                        "damage reduction",
                    )
                    passive_detected = any(keyword in low for keyword in passive_keywords)
                    if not passive_detected:
                        passive_detected = (
                            "movement reduced" in low
                            or "healed" in low and "from" in low
                            or "heals" in low and "from" in low
                            or "reduces incoming" in low
                        )
                if passive_detected:
                    queue.pop(idx)
                    if not self._is_passive_logging_mode():
                        continue
                    self._ensure_balance_counters()
                    self.passive_trigger_count += 1
                    system_message = self._format_system_message(passive_message, team)
                    self.log(f"SYSTEM : {system_message}", LOG_COLOR_SYSTEM, time_elapsed=self.cumulative_time)
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

    def _log_content_width(self) -> int:
        """Return the usable text width inside the log panel."""
        log_rect = self._log_rect()
        content_x = log_rect.x + 8

        sb_margin = 6
        sb_width = 10
        track_x = log_rect.right - sb_margin - sb_width

        # Small padding before the scrollbar
        return max(0, track_x - content_x - 4)

    def _wrap_text_to_width(self, text: str, max_width: int) -> list[str]:
        """Wrap a string into a list of lines that fit within max_width."""
        if max_width <= 0:
            return [text]

        if not text:
            return [""]

        words = text.split(" ")
        lines: list[str] = []
        current = ""

        for word in words:
            candidate = word if current == "" else f"{current} {word}"
            if self.font_s.size(candidate)[0] <= max_width:
                current = candidate
                continue

            if current:
                lines.append(current)
                current = ""

            if self.font_s.size(word)[0] <= max_width:
                current = word
            else:
                partial = ""
                for ch in word:
                    candidate_partial = partial + ch
                    if self.font_s.size(candidate_partial)[0] <= max_width:
                        partial = candidate_partial
                    else:
                        if partial:
                            lines.append(partial)
                        partial = ch
                current = partial

        if current:
            lines.append(current)

        return lines or [""]

    def _wrap_game_log_lines(self, max_width: int) -> list[tuple[str, tuple[int, int, int], int | None]]:
        """Expand game_log entries into individually wrapped display lines."""
        wrapped: list[tuple[str, tuple[int, int, int], int | None]] = []
        for entry in self.game_log:
            text = entry.get("log", "") if isinstance(entry, dict) else str(entry)
            color = entry.get("_color", UI_TEXT) if isinstance(entry, dict) else UI_TEXT
            timestamp = entry.get("time") if isinstance(entry, dict) else None
            for line in self._wrap_text_to_width(str(text), max_width):
                wrapped.append((line, color, timestamp))

        # Keep list order as-is so index 0 (newest) renders at the top.
        return wrapped

    def _calc_log_geometry(self, total_log_lines: int | None = None):
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

        content_width = max(0, track_rect.x - content_x - 4)
        total_lines = total_log_lines if total_log_lines is not None else len(self.game_log)

        # Compute scroll bounds (0 = newest/top, max_scroll = oldest reachable start)
        max_scroll = max(0, total_lines - max_lines)

        # Thumb size proportional to visible fraction; enforce a minimum
        if max_scroll == 0:
            thumb_h = track_rect.height
        else:
            visible_fraction = max_lines / max(total_lines, 1)
            thumb_h = max(24, int(track_rect.height * visible_fraction))
            thumb_h = min(thumb_h, track_rect.height)

        # Thumb position maps log_scroll in [0, max_scroll] to y in [top, bottom].
        if max_scroll == 0:
            thumb_y = track_rect.y
        else:
            t = self.log_scroll / max_scroll  # 0..1 (0 = newest/top, 1 = oldest/bottom)
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
            "line_h": line_h,
            "content_width": content_width
        }

    def _log_rect(self) -> pygame.Rect:
        """Helper: current log panel rect (same as in render)."""
        return pygame.Rect(LOG_X, LOG_Y, LOG_W, LOG_H)

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

    def _action_panel_content_rect(self) -> pygame.Rect:
        # Visible content area inside the right-side Actions List panel
        # Header at y=50, first card starts at y=88, panel bottom is y=600.
        return pygame.Rect(1000, 88, 220, 512)

    def _action_rects_for_chara(self, chara, scroll_offset: int = 0) -> list[tuple[int, pygame.Rect]]:
        # Return list of (action_index, rect) for the Actions List UI of a character.
        rects: list[tuple[int, pygame.Rect]] = []
        i = 0
        for idx, _ in enumerate(chara.template.get("actions", [])):
            rects.append((idx, pygame.Rect(1000, 88 + i - scroll_offset, 220, 150)))
            i += 170
        return rects

    def _get_action_list_chara(self):
        if not hasattr(self, 'field'):
            return None
        if Cursor.state != 4:
            return self.field.hover_cursor.getChara() if self.field.hover_cursor.getChara() else self.field.select_cursor.getChara()
        return self.field.select_cursor.getChara()

    def _max_action_list_scroll(self, chara) -> int:
        if chara is None:
            return 0
        actions_count = len(chara.template.get("actions", []))
        if actions_count <= 0:
            return 0
        total_height = 170 + max(0, actions_count - 1) * 170
        visible_h = self._action_panel_content_rect().height
        return max(0, total_height - visible_h)

    def _action_scrollbar_geometry(self, chara):
        # Reuse game-log scrollbar style, but with a shorter track for the action panel.
        if chara is None:
            return None
        max_scroll = self._max_action_list_scroll(chara)
        if max_scroll <= 0:
            return None

        panel = self._action_panel_content_rect()
        track_h = 380
        # Place scrollbar slightly more to the right and start a bit higher.
        track_y = panel.y + 12
        track_rect = pygame.Rect(panel.right + 10, track_y, 8, track_h)

        total_height = 150 + max(0, len(chara.template.get("actions", [])) - 1) * 170
        visible_fraction = panel.height / max(1, total_height)
        thumb_h = max(24, int(track_rect.height * visible_fraction))
        thumb_h = min(thumb_h, track_rect.height)

        if max_scroll == 0:
            thumb_y = track_rect.y
        else:
            ratio = self._action_list_scroll / max_scroll
            thumb_y = int(track_rect.y + ratio * (track_rect.height - thumb_h))

        thumb_rect = pygame.Rect(track_rect.x, thumb_y, track_rect.width, thumb_h)
        return {
            "track_rect": track_rect,
            "thumb_rect": thumb_rect,
            "max_scroll": max_scroll,
        }

    def _sync_action_list_to_selection(self) -> None:
        """When using keyboard in action menu, keep selected action card visible."""
        if Cursor.state != 2:
            return

        chara = self._get_action_list_chara()
        if chara is None:
            return
        if str(chara.template.get("display_name", "")).strip().lower() != "wizard":
            return

        actions_count = len(chara.template.get("actions", []))
        selected_idx = Cursor.selected_action
        if selected_idx < 0 or selected_idx >= actions_count:
            return

        content_rect = self._action_panel_content_rect()
        card_top = 88 + (selected_idx * 170) - self._action_list_scroll
        card_bottom = card_top + 150

        if card_top < content_rect.top:
            self._action_list_scroll += card_top - content_rect.top
        elif card_bottom > content_rect.bottom:
            self._action_list_scroll += card_bottom - content_rect.bottom

        max_scroll = self._max_action_list_scroll(chara)
        self._action_list_scroll = max(0, min(self._action_list_scroll, max_scroll))

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
                    # Wheel up -> move toward newest/top.
                    self.log_scroll = max(0, self.log_scroll - self._log_scroll_step * abs(event.y))
                elif event.y < 0:
                    # Wheel down -> move toward older/bottom.
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
