from AI import *
import pygame


AI_list: list[type[AIFramework]] = [PlayerInput, PerfectPlay, Random, PersonalityCores, IndependentAction]

class GameMaster:
    def __init__(self) -> None:
        self.turn = 1   # Team 1 starts first
        self.roundFinished = False

    def setTeams(self, team1: int, team2: int) -> None:
        self.team1 = AI_list[team1](team=1)
        self.team2 = AI_list[team2](team=2)
        self.activeAI = self.team1

    def startRound(self) -> None:
        self.roundFinished = False

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