from AI import AIFramework
from Character import Character
import random
import numpy as np

class MyCustomAI(AIFramework):   # ← Rename this class

    def __init__(self, team):
        super().__init__(team)

    def reset(self):
        """
        Called at the start of each game.
        Use this to reset variables if needed.
        """
        super().reset()

    def calculate(self):
        """
        Called once at the beginning of each turn.

        Use this function to:
        - Analyze the board
        - Prepare strategy
        - Store data for later use
        """
        super().calculate()

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