"""Game package containing runtime wiring and controller composition."""

from game.controller import GameMain
from game.runner import run_game

__all__ = ["GameMain", "run_game"]
