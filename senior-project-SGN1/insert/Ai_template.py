"""
AI TEMPLATE FOR RESEARCHERS
===========================

This file is a starter template for creating a custom AI.

Please note:
- You can safely modify the inside of methods such as `calculate()` and `activate()`.
- Keep required method names (`__init__`, `reset`, `calculate`, `activate`) unchanged.
- Keep the class inheriting from `AIFramework` so it remains compatible with the game system.
"""

from AI import AIFramework
from Character import Character
import random
import numpy as np

class MyCustomAI(AIFramework):  # Optional: rename class if your loader supports it.
    """Beginner-friendly custom AI skeleton.

    Inherit from `AIFramework` and implement your own decision logic.
    The game engine calls this class automatically during a match.
    """

    def __init__(self, team):
        """Create AI instance for one team.

        When it is called:
            - Once when the AI object is created.

        What to implement:
            - Initialize custom variables (memory, parameters, counters, etc.).

        Important:
            - Always call `super().__init__(team)` to keep engine compatibility.
        """
        super().__init__(team)

        # Example placeholders for your own state:
        # self.turn_index = 0
        # self.custom_memory = {}

    def reset(self):
        """Reset AI state at the start of a new game.

        When it is called:
            - At the beginning of every new game session.

        What to implement:
            - Clear or reinitialize anything stored across turns/games.
        """
        super().reset()

        # Example reset logic:
        # self.turn_index = 0
        # self.custom_memory.clear()

    def calculate(self):
        """
        Prepare turn-level strategy before character activations.

        When it is called:
            - Once at the beginning of your team's turn.

        What to implement:
            - Analyze board state.
            - Build priorities/targets.
            - Save data used later in `activate()`.
        """
        super().calculate()

        # Example planning steps:
        # 1) Scan enemies and allies.
        # 2) Score threats/opportunities.
        # 3) Store selected targets in self variables.

    def activate(self, activationNo: int):
        """
        Called once for each character in your team.

        This is the MOST IMPORTANT function.
        You must decide:
        - Where the character moves
        - What action the character uses
        """

        chara = self.own_team[activationNo]

        # =========================
        # 🔰 BASIC EXAMPLE (PASS)
        # =========================
        self.passCharaAction(chara)

        # =========================
        # 💡 USEFUL FUNCTIONS
        # =========================

        # Move character:
        # self.moveCharaTo(chara, (row, col))

        # Use action:
        # self.useCharaAction(chara, target, actionNo, modifier)

        # Get movement range:
        # movementMap = self.field.getMovement(chara)

        # Get attack range:
        # actionMap = self.field.getActionArea(chara, actionNo)

        # Get enemy units:
        # enemies = self.enemy_team

        # Get ally units:
        # allies = self.own_team

        # Find character at position:
        # Character.getCharacterByGrid((row, col))

        # Terrain info:
        # self.terrain[row][col]

        # =========================

        self.turnFinished = self.checkCharaActed()