from AI import *
import pygame
from insert import ai_import_manager


AI_list: list[type[AIFramework]] = ai_import_manager.get_ai_list()


class PerCharacterTeamAI(AIFramework):
    def __init__(self, team: int, char_ai_ids: list[int]) -> None:
        super().__init__(team)
        max_index = max(0, len(AI_list) - 1)
        self.char_ai_ids = [max(0, min(int(ai_id), max_index)) for ai_id in char_ai_ids[:3]]
        self.per_char_ais = [AI_list[ai_id](team=team) for ai_id in self.char_ai_ids]
        self.color = TEAM1_COLOR if team == 1 else TEAM2_COLOR

    def loadField(self, field: Field) -> None:
        super().loadField(field)
        for ai in self.per_char_ais:
            ai.field = self.field
            ai.terrain = self.terrain
            ai.own_team = self.own_team
            ai.enemy_team = self.enemy_team

    def reset(self) -> None:
        super().reset()
        for ai in self.per_char_ais:
            ai.reset()

    def calculate(self) -> None:
        for ai in self.per_char_ais:
            ai.own_team = self.own_team
            ai.enemy_team = self.enemy_team
            ai.field = self.field
            ai.terrain = self.terrain
            ai.calculate()
        self.ready = True

    def activate(self, activationNo: int) -> None:
        if activationNo < 0 or activationNo >= len(self.per_char_ais):
            return
        ai = self.per_char_ais[activationNo]
        ai.own_team = self.own_team
        ai.enemy_team = self.enemy_team
        ai.field = self.field
        ai.terrain = self.terrain
        ai.activate(activationNo)
        self.turnFinished = self.checkCharaActed()


def refresh_ai_pool() -> None:
    global AI_list
    ai_import_manager.refresh_ai_registry()
    AI_list = ai_import_manager.get_ai_list()


def get_ai_labels() -> list[str]:
    refresh_ai_pool()
    return ai_import_manager.get_ai_labels()


def get_ai_metadata() -> list[dict]:
    refresh_ai_pool()
    return ai_import_manager.get_ai_metadata()

class GameMaster:
    def __init__(self) -> None:
        self.turn = 1   # Team 1 starts first
        self.roundFinished = False

    def setTeams(
        self,
        team1: int,
        team2: int,
        team1_char_ai_ids: list[int] | None = None,
        team2_char_ai_ids: list[int] | None = None,
    ) -> None:
        refresh_ai_pool()
        if team1 == 0:
            self.team1 = AI_list[0](team=1)
        elif team1_char_ai_ids is not None and len(team1_char_ai_ids) > 0:
            self.team1 = PerCharacterTeamAI(team=1, char_ai_ids=team1_char_ai_ids)
        else:
            self.team1 = AI_list[team1](team=1)

        if team2 == 0:
            self.team2 = AI_list[0](team=2)
        elif team2_char_ai_ids is not None and len(team2_char_ai_ids) > 0:
            self.team2 = PerCharacterTeamAI(team=2, char_ai_ids=team2_char_ai_ids)
        else:
            self.team2 = AI_list[team2](team=2)

        self.activeAI = self.team1

    def startRound(self) -> None:
        self.roundFinished = False
        # Process per-round status effects (burn, movement debuffs)
        for chara in Character.team1_list + Character.team2_list:
            # process burns
            new_effects = []
            for eff in getattr(chara, 'status_effects', []):
                if eff.get('type') == 'burn':
                    dmg = eff.get('damage_per_turn', 0)
                    chara.template['curHP'] -= dmg
                eff['turns'] -= 1
                if eff['turns'] > 0:
                    new_effects.append(eff)
            chara.status_effects = new_effects

            # check movement debuff expiration
            if getattr(chara, 'movement_debuff_turns', 0) > 0:
                chara.movement_debuff_turns -= 1
                if chara.movement_debuff_turns == 0:
                    # restore movement to template default
                    chara.movement = chara.template.get('movement', chara.movement)

            # remove dead characters
            if chara.template.get('curHP', 0) <= 0:
                chara.alive = False
                Character.removeCharacter(chara)

    def calculate(self) -> None:        
        self.activeAI.calculate()

    def switchTurn(self) -> None:
        if self.turn == 1:
            self.turn = 2
            self.activeAI = self.team2
        else:
            self.endRound()

    def isActiveAIHuman(self) -> bool:
        return isinstance(self.activeAI, PlayerInput)

    def activateAI(self, activationNo: int) -> None:
        self.activeAI.activate(activationNo)
        # print("activating: " + str(activationNo))

    def endRound(self) -> None:
        self.team1.reset()
        self.team2.reset()
        self.turn = 1
        self.activeAI = self.team1
        self.roundFinished = True

    def keyInput(self, key:int):
        if isinstance(self.activeAI, PlayerInput):
            self.activeAI.receiveInput(key)
