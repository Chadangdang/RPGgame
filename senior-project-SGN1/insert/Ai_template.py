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
        Control one character's move + action for this activation.

        When it is called:
            - Once per activatable character in your team each turn.
        What to implement:
            1) Choose movement destination.
            2) Choose action/skill target.
            3) Execute exactly one final action path (act or pass).

        Args:
            activationNo: Index of the current character in `self.own_team`.
        """

        chara = self.own_team[activationNo]

        # -------------------------------------------------
        # STEP 1: CHOOSE MOVEMENT (implement your logic here)
        # -------------------------------------------------
        # Example (commented):
        # movement_map = self.field.getMovement(chara)
        # best_cell = ...  # choose a (row, col) from movement_map
        # self.moveCharaTo(chara, best_cell)

        # -------------------------------------------------
        # STEP 2: CHOOSE ACTION (implement your logic here)
        # -------------------------------------------------
        # Example (commented):
        # action_no = 0
        # target = ...
        # modifier = None
        # self.useCharaAction(chara, target, action_no, modifier)

        # -------------------------------------------------
        # DEFAULT SAFE BEHAVIOR
        # -------------------------------------------------
        # If you do not choose an action yet, pass this character's action.
        # This keeps the template runnable for beginners.
        self.passCharaAction(chara)

        # ===== HELPFUL FUNCTIONS =====
        # moveCharaTo(chara, (row, col))
        # useCharaAction(chara, target, actionNo, modifier)
        # passCharaAction(chara)
        # field.getMovement(chara)
        # field.getActionArea(chara, actionNo)

        # Additional useful references (optional):
        # enemies = self.enemy_team

        # allies = self.own_team

        # Character.getCharacterByGrid((row, col))
        # terrain_type = self.terrain[row][col]

       # Required final update: tells framework whether all allies acted.
        self.turnFinished = self.checkCharaActed()