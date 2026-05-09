import pygame
import random
import numpy as np
from Field import Field
from Character import Character
from Constants import *
from Personality import Personality
from Cursor import Cursor

def propagate_half(arr):
    arr = arr.copy()
    updated = True
    while updated:
        updated = False
        new_arr = arr.copy()
        rows, cols = arr.shape
        for i in range(rows):
            for j in range(cols):
                val = arr[i, j]
                if val == 0:
                    continue
                for dx, dy in [(-1,0), (1,0), (0,-1), (0,1)]:
                    ni, nj = i + dx, j + dy
                    if 0 <= ni < rows and 0 <= nj < cols:
                        half_val = val / 2
                        if new_arr[ni, nj] < half_val:
                            new_arr[ni, nj] = half_val
                            updated = True
        arr = new_arr
    return arr

class AIFramework:
    def __init__(self, team) -> None:
        self.terrain = np.zeros((GRID_ROWS, GRID_COLS))
        self.reset()
        self.team = team
        key:int = -1
        if team == 1:
            self.own_team = Character.team1_list
            self.enemy_team = Character.team2_list
            self.color = TEAM1_COLOR
        else:
            self.own_team = Character.team2_list
            self.enemy_team = Character.team1_list
            self.color = TEAM2_COLOR

    def loadField(self, field: Field) -> None:
        self.field = field
        self.terrain = np.array(self.field.getTerrain())

    def reset(self) -> None:
        self.action_log: list[str] = []
        self.ready = False
        self.turnFinished = False

    def calculate(self) -> None:
        self.ready = True

    def activate(self, activationNo: int) -> None:
        pass

    def moveCharaTo(self, chara: Character, grid: tuple[int, int]) -> bool:
        cols = "abcdefgh"
        charaName = chara.template["display_name"]
        gridName = cols[grid[1]] + str(GRID_ROWS - grid[0])

        occupant = Character.getCharacterByGrid(grid)
        if occupant is not None and occupant is not chara:
            occupant_name = occupant.template.get("display_name", "Unknown")
            self.action_log.append(
                f"{charaName} cannot move to grid {gridName} (occupied by {occupant_name})"
            )
            return False

        logs = [
            f"{charaName} moves to grid {gridName}"
        ]

        self.action_log.extend(logs)

        chara.moveTo(grid)
        chara.moved = True
        return True

    def useCharaAction(self, chara: Character, target: Character, actionNo: int, modifier: int) -> None:
        cols = "abcdefgh"
        charaName = chara.template["display_name"]
        action = chara.template["actions"][actionNo]
        actionName = chara.template["actions"][actionNo]["action_display_name"]
        actionHeal = action.get("heal")
        targetName = target.template["display_name"]
        gridName = cols[target.grid[1]] + str(GRID_ROWS - target.grid[0])

        # Attack once and capture calculated damage + passive/status messages.
        dealt_damage, extra_logs = chara.attack(target, actionNo, modifier, self.field)

        # Prepare target display info depending on action type
        if actionHeal is not None or action.get("action_type", "").lower() == "heal":
            target_display = "Allies"
            result_line = f"    Result: Healed {actionHeal} HP"
        else:
            targetName = target.template["display_name"] if target is not None else "Unknown"
            gridName = cols[target.grid[1]] + str(GRID_ROWS - target.grid[0]) if target is not None else ""
            target_display = f"{targetName} ({gridName})"
            result_line = f"    Result: {dealt_damage} damage"

        logs = [
            f"{charaName} uses {actionName}",
            f"    Target: {target_display}",
            result_line
        ]

        self.action_log.extend(logs)

        if extra_logs:
            # indent extra logs for readability
            for l in extra_logs:
                self.action_log.append(f"    {l}")

        chara.acted = True

    def passCharaAction(self, chara: Character) -> None:
        charaName = chara.template["display_name"]
        logs = [
            f"{charaName} passes."
        ]
        
        self.action_log.extend(logs)

        chara.acted = True

    def checkCharaActed(self) -> bool:
        for chara in self.own_team:
            if not chara.acted:
                return False
        return True


class PlayerInput(AIFramework):
    def __init__(self, team) -> None:
        super().__init__(team)

    def reset(self) -> None:
        super().reset()
        Cursor.state = 0

    def calculate(self) -> None:
        super().calculate()

    def activate(self, activationNo: int) -> None:
        super().activate(activationNo)

    def receiveInput(self, key: int) -> None:

        KEYUP = 1073741906
        KEYDOWN = 1073741905
        KEYLEFT = 1073741904
        KEYRIGHT = 1073741903
        KEYZ = 122
        KEYX = 120

        if key in [KEYUP, KEYDOWN, KEYLEFT, KEYRIGHT] and Cursor.state != 2:  # 2 is the menu one
            self.field.hover_cursor.moveBy(key)
            key = -1
        else:
            match Cursor.state:
                case 0: # Default | Z: Select character, X: None
                    if key == KEYZ:
                        if self.field.select_cursor.getChara() is None:  # No Character is selected  (This happpens first)
                            # Only allow selecting own-team units when using keyboard input
                            for chara in self.own_team:
                                if self.field.hover_cursor.grid == chara.grid:
                                    if chara.acted:
                                        pass
                                    else:
                                        self.field.select_cursor.moveTo(self.field.hover_cursor.grid)
                                        self.field.select_cursor.show = True
                                        if chara.moved:
                                            Cursor.state = 2
                                            Cursor.selected_action = 0
                                            self.field.hover_cursor.show = False
                                        else:
                                            Cursor.state = 1
                                            self.field.getMovement(chara)
                                    break
                    elif key == KEYX:
                        pass
                case 1: # Select tile for movement | Z: Confirm, X: Cancel
                    if key == KEYZ:
                        if self.field.getHoveredBoxInfo().selected:
                                chara = self.field.select_cursor.getChara()
                                if chara is not None:
                                    chara.moveTo(self.field.hover_cursor.grid)
                                self.field.clearMovement()
                                Cursor.state = 0
                    elif key == KEYX:
                            self.field.clearMovement()
                            Cursor.state = 0
                case 2: # Select action from menu
                    chara = self.field.select_cursor.getChara()
                    if chara is not None:
                        actions = len(chara.template["actions"])
                        if key == KEYUP:
                            Cursor.selected_action -= 1
                            if Cursor.selected_action == -1:
                                Cursor.selected_action = actions
                        elif key == KEYDOWN:
                            Cursor.selected_action += 1
                            if Cursor.selected_action == actions + 1:
                                Cursor.selected_action = 0
                        elif key == KEYZ:
                            if Cursor.selected_action == actions:
                                self.passCharaAction(chara)
                                Cursor.state = 0
                                self.field.hover_cursor.show = True
                                self.field.select_cursor.show = False
                            else:
                                # If the selected action is a heal (or has a heal field), execute immediately
                                action = chara.template["actions"][Cursor.selected_action]
                                if action.get("action_type", "").lower() == "heal" or action.get("heal") is not None:
                                    # For heals we pass the caster as target (attack() ignores target for heals)
                                    self.useCharaAction(chara, chara, Cursor.selected_action, 0)
                                    # Reset visuals/state like other immediate actions
                                    self.field.select_cursor.show = False
                                    # Re-enable hover cursor and clear action highlights so player can continue
                                    self.field.hover_cursor.show = True
                                    self.field.clearMovement()
                                    Cursor.selected_action = -1
                                    for i in range(self.field.rows):
                                        for j in range(self.field.cols):
                                            self.field.boxes[i][j].selected_red = False
                                    Cursor.state = 0
                                else:
                                    Cursor.state = 4
                                    self.field.hover_cursor.show = True
                                    self.field.getActionArea(chara, Cursor.selected_action)
                        elif key == KEYX:
                            self.field.hover_cursor.show = True
                            self.field.select_cursor.show = False
                            Cursor.state = 0
                            Cursor.selected_action = -1
                case 3: # Showing enemy movement | Z: None, X: Cancel
                    if key == KEYZ:
                        pass
                    elif key == KEYX:
                        self.field.select_cursor.show = False
                        self.field.clearMovement()
                        Cursor.state = 0
                case 4: # Select target for chosen action
                    if key == KEYZ:
                        if self.field.getHoveredBoxInfo().selected_red:
                            chara = self.field.select_cursor.getChara()
                            target = self.field.hover_cursor.getChara()
                            if  (chara is not None and chara in self.own_team) and \
                                (target is not None and target in self.enemy_team):

                                if self.field.boxes[target.grid[0]][target.grid[1]].terrain == 1:
                                    modifier = -2
                                else:
                                    modifier = 0

                                self.useCharaAction(chara, target, Cursor.selected_action, modifier)
                                self.field.select_cursor.show = True
                                self.field.select_cursor.show = False
                                Cursor.selected_action = -1
                                for i in range(self.field.rows):
                                    for j in range(self.field.cols):
                                        self.field.boxes[i][j].selected_red = False
                                Cursor.state = 0
                    elif key == KEYX:
                        self.field.hover_cursor.show = False
                        Cursor.state = 2
                        for i in range(self.field.rows):
                            for j in range(self.field.cols):
                                self.field.boxes[i][j].selected_red = False

            key = -1     

        self.turnFinished = self.checkCharaActed()

        # charaName = self.own_team[activationNo].template["display_name"] # remove this line when AI is usable
        # self.action_log.extend([f'{charaName} pass'])  # remove this line when AI is usable


class Random(AIFramework):
    def __init__(self, team) -> None:
        super().__init__(team)

    def calculate(self) -> None:
        super().calculate()
        
        # No calculation needed
        # Random movement and action done at runtime


    def activate(self, activationNo: int) -> None:
        chara = self.own_team[activationNo]

        # Move to a random tile within range
        movementMap = self.field.getMovement(chara, show=False)
        movementTiles = np.argwhere(movementMap > 0)
        if movementTiles.size > 0:
            self.moveCharaTo(chara, tuple(random.choice(movementTiles.tolist())))

        # List of all actions unit can use
        availableActions = list(range(len(chara.template["actions"])))
        random.shuffle(availableActions)

        if not availableActions:    # Empty
            # If no targets for all available actions, pass
            self.passCharaAction(chara)
        else:        
            acted = False
            while availableActions:
                # Choose one action from the list and get its tiles
                chosenAction = availableActions.pop()        
                actionMap = self.field.getActionArea(chara, chosenAction, show=False)
                actionTiles = np.argwhere(actionMap)
                target_list = []
                
                # Check all enemy units within range
                for coords in actionTiles.tolist():
                    char = Character.getCharacterByGrid(tuple(coords))
                    if char is not None and char in self.enemy_team:
                        target_list.append(char)

                # If not empty, attack one at random
                if target_list:
                    target = random.choice(target_list)
                    if self.terrain[target.grid[0]][target.grid[1]] == 1:   # Target standing in a Tree tile
                        modifier = -2
                    elif self.terrain[target.grid[0]][target.grid[1]] == 3:
                        modifier = 2
                    else:
                        modifier = 0
                    self.useCharaAction(chara, target, chosenAction, modifier)
                    acted = True
                    break

            if not acted:
                self.passCharaAction(chara)

        self.turnFinished = self.checkCharaActed()


class DisableAI(AIFramework):
    def __init__(self, team) -> None:
        super().__init__(team)

    def calculate(self) -> None:
        super().calculate()

    def activate(self, activationNo: int) -> None:
        chara = self.own_team[activationNo]
        self.passCharaAction(chara)
        self.turnFinished = self.checkCharaActed()



class PerfectPlay(AIFramework):

    def __init__(self, team) -> None:
        super().__init__(team)

    def reset(self) -> None:
        super().reset()
        self.optimalMap = np.ones(
            (3, GRID_ROWS, GRID_COLS)) * -1  # The map used to determine optimal movement tiles for each characters

    def calculate(self) -> None:
        # PART 1
        # GOAL: Evaluate the danger of each tile as a heat map
        enemyThreatMap = np.zeros(
            (GRID_ROWS, GRID_COLS))  # Theroetical maximum damage the enemy team can deal to a tile
        for enemy_unit in self.enemy_team:
            movementMap = np.array(
                self.field.getMovement(enemy_unit, False))  # Get list of coordinates that the enemy character can move to

            movementTiles = np.argwhere(movementMap > 0)  # Note: Does not consider the fact that characters may not stack on the same tile
            actionMap = np.zeros((GRID_ROWS, GRID_COLS))  # Theoretical maximum damage for that single enemy character
            for tile in movementTiles:
                for actionNo in range(len(enemy_unit.template["actions"])):  # Get the damage map of each specific action
                    tempMap = self.field.getActionArea(enemy_unit, actionNo, False, (tile[0], tile[1]))
                    actionMap = np.maximum(actionMap, tempMap)  # Only keep the highest damage value for each tile
            enemyThreatMap = enemyThreatMap + actionMap  # Add that character's maximum damage to the total

        # print("ENEMY THREAT MAP:")
        # print(enemyThreatMap)
        # print()

        # PART 1.5
        # GOAL: Encourage the AI to move its units into the objective squares

        OBJECTIVE_WEIGHT = 8

        #

        objectiveMap = np.zeros((GRID_ROWS, GRID_COLS))
        objectiveMap[np.nonzero(self.terrain == 3)] = OBJECTIVE_WEIGHT
        objectiveMap = propagate_half(objectiveMap)
        # print(objectiveMap)

        # PART 2
        # GOAL: Evaluate the damage

        THREAT_WEIGHT = 0.1  # Arbitrary multiplier for weighing between damage dealt and damage received

        # * Enemies do not focus on a single character
        # * No fallback if a character's optimal tiles are all overwritten -> will just stay still
        optimalIndicesList = []  # List of list of indices
        for own_unit in self.own_team:
            movementMap = np.array(self.field.getMovement(own_unit, False))  # Same system as part 1

        ### Some logic here to remove tiles with enemy_team on them
        #
            enemy_pos = [enemy.grid for enemy in self.enemy_team]   # Get list of enemy team's grid coordinates
            if enemy_pos:
                rows, cols = np.transpose(enemy_pos)    # There is probably a better way to do this
                enemy_pos_full = np.zeros((GRID_ROWS, GRID_COLS))
                enemy_pos_full[(rows, cols)] = 1
                movementMap = np.logical_and(movementMap, np.logical_not(enemy_pos_full))   # Remove occupied tiles from consideration
            else:
                # No enemies present; nothing to remove from movementMap
                pass
        #
        ###

            movementTiles = np.argwhere(movementMap > 0)
            destinationMap = np.ones((GRID_ROWS, GRID_COLS)) * -999
            bestActionMap = np.zeros((GRID_ROWS, GRID_COLS), dtype=int)
            bestTargetMap = np.full((GRID_ROWS, GRID_COLS), 999, dtype=int)
            for tile in movementTiles:
                damageMap = np.zeros((GRID_ROWS, GRID_COLS))  # Instead of keeping potential damage on other tiles,
                tileActionNo = 0
                tileTargetPlayerID = 999
                for actionNo in range(len(own_unit.template["actions"])):
                    tempMap = self.field.getActionArea(own_unit, actionNo, False, (tile[0], tile[1]))
                    if np.array_equal(tempMap, np.maximum(damageMap, tempMap)):
                        tileActionNo = actionNo
                        tileTargetPlayerID = 999
                        for enemy_unit in self.enemy_team:
                            if tempMap[enemy_unit.grid[0]][enemy_unit.grid[1]] > 0:         # Player can be targeted
                                tileTargetPlayerID = enemy_unit.id
                        damageMap = np.copy(tempMap)
                destinationMap[tile[0]][tile[1]] = np.max(
                    damageMap)  # The maximum damage is registered to the movement tile instead
                bestActionMap[tile[0]][tile[1]] = tileActionNo
                bestTargetMap[tile[0]][tile[1]] = tileTargetPlayerID
            destinationMap = destinationMap + objectiveMap - (THREAT_WEIGHT * enemyThreatMap)
            # print(destinationMap)
            optimalIndices = np.argwhere(destinationMap == np.max(destinationMap))
            optimalIndicesList.append([own_unit.id, bestActionMap, bestTargetMap, optimalIndices])
            # print(optimalIndicesList)
            # print(destinationMap)
        optimalIndicesList = sorted(optimalIndicesList, key=lambda s: -len(
            s[3]))  # Sorts the list to let the character with the most optimal tiles "place" first
        for data in optimalIndicesList:  # Insanity
            for index in data[3]:
                self.optimalMap[0][index[0]][index[1]] = data[0]        # Own ID
                self.optimalMap[1][index[0]][index[1]] = data[1][index[0]][index[1]]        # Action to use
                self.optimalMap[2][index[0]][index[1]] = data[2][index[0]][index[1]]        # Target ID

        print("ENEMY OPTIMAL MAP:")
        print(self.optimalMap)
        print()

        # Initalize a timer state variable.
        # last_action_time = 0
        # action_delay = 500

        # print("---- ACTION LOG ----")

        super().calculate()

    def activate(self, activationNo: int) -> None:

        chara = self.own_team[activationNo]

        tiles = np.argwhere(self.optimalMap[0] == chara.id)
        if tiles.size > 0:
            available_tiles = []
            for tile in tiles.tolist():
                tile_choice = (int(tile[0]), int(tile[1]))
                occupant = Character.getCharacterByGrid(tile_choice)
                if occupant is None or occupant is chara:
                    available_tiles.append(tile_choice)

            if not available_tiles:
                self.passCharaAction(chara)
                self.turnFinished = self.checkCharaActed()
                return

            tile_choice = random.choice(available_tiles)

            row = tile_choice[0]
            col = tile_choice[1]
            optimalActionNo = int(self.optimalMap[1][row][col])
            targetPlayerID = int(self.optimalMap[2][row][col])

            if not self.moveCharaTo(chara, tile_choice):
                self.passCharaAction(chara)
                self.turnFinished = self.checkCharaActed()
                return

            # Perform attack.

            target = Character.getCharacterByID(targetPlayerID)
            if target is not None:
                if chara.acted == False:
                    if self.terrain[target.grid[0]][target.grid[1]] == 1:   # Target standing in a Tree tile
                        modifier = -2
                    elif self.terrain[target.grid[0]][target.grid[1]] == 3:
                        modifier = 2
                    else:
                        modifier = 0
                    self.useCharaAction(chara, target, optimalActionNo, modifier)
                
            else:
                # print(f"Warning: Target with ID {targetPlayerID} is not found!")
                self.passCharaAction(chara)
                pass
        else:
            self.passCharaAction(chara)
        
        self.turnFinished = self.checkCharaActed()


class PersonalityCores(AIFramework):
    def __init__(self, team) -> None:
        super().__init__(team)

        # Just put numbers that seem sensible idk
        # DAMAGE | OBJECTIVE | THREAT
        self.personalities = [
            Personality('Strategic', (0.8, 2.0, 0.6)),
            Personality('Survival', (0.6, 0.6, 1.6)),
            Personality('Aggressive', (1.7, 0.9, 0.3))
        ]

    def reset(self) -> None:
        super().reset()
        self.optimalMap = np.ones(
            (3, GRID_ROWS, GRID_COLS)) * -1  # The map used to determine optimal movement tiles for each characters

    def calculate(self) -> None:
        # PART 0
        # GOAL: Determine personality type to use

        own_team_HP = 0
        for i in self.own_team:
            own_team_HP += i.template['curHP']
        enemy_team_HP = 0
        for i in self.enemy_team:
            enemy_team_HP += i.template['curHP']
        enemy_team_max_HP = 0
        for i in self.enemy_team:
            enemy_team_max_HP += i.template['maxHP']

        p_weights = [1.0] * len(self.personalities)     # Initialize a list of equal weights for randomization (will be normalized later)

        # SOME CONDITION FOR STRATEGIC
        # p_weights[0] += 1

        n = (own_team_HP / (enemy_team_HP + 0.000000000000001))
        n = min(n, 10)
        p_weights[0] = (1.5 ** n) - 0.5

        # SOME CONDITION FOR SURVIVAL
        # p_weights[1] += 1

        # EXAMPLE FORMULA FOR SURVIVAL:

        n = 0
        c = 0
        for own_unit in self.own_team:
            c += 1
            if own_unit.template['curHP'] <= own_unit.template['maxHP'] * 0.75:
                n += 1
        n += 2 * (3 - c)
        n = min(n, 10)
        p_weights[1] = (1.5 ** n) - 0.5         # Arbitrary formula. <1 at n=0, 1 at n=1, >1 at n>1

        # SOME CONDITION FOR AGGRESSIVE
        # p_weights[2] += 1

        n = 0
        c = 0
        for enemy_unit in self.enemy_team:
            c += 1
            if enemy_unit.template['curHP'] <= enemy_unit.template['maxHP'] * 0.5:
                n += 1
        n += 2 * (3 - c)
        n = min(n, 10)
        p_weights[2] = (1.5 ** n) - 0.5

        # print('Board analyzed - Displaying personality weights' + f' - team {self.team}')
        for index, personality in enumerate(self.personalities):
            name = personality.name
            p_weight = p_weights[index]
            percentage = round(p_weight * 100 / sum(p_weights), 2)
            # print(f'{name}: {p_weight} ({percentage}%)')

        # print('\nChoosing personality...')
        self.chosen_personality = random.choices(self.personalities, weights=p_weights)[0]
        # print(f'Team {self.team} choose --> ' + str(self.chosen_personality.name) + '\n')
        

        # PART 1
        # GOAL: Evaluate the danger of each tile as a heat map
        enemyThreatMap = np.zeros(
            (GRID_ROWS, GRID_COLS))  # Theroetical maximum damage the enemy team can deal to a tile
        for enemy_unit in self.enemy_team:
            movementMap = np.array(
                self.field.getMovement(enemy_unit,
                                    False))  # Get list of coordinates that the enemy character can move to

            movementTiles = np.argwhere(
                movementMap > 0)  # Note: Does not consider the fact that characters may not stack on the same tile
            actionMap = np.zeros((GRID_ROWS, GRID_COLS))  # Theoretical maximum damage for that single enemy character
            for tile in movementTiles:
                for actionNo in range(
                        len(enemy_unit.template["actions"])):  # Get the damage map of each specific action
                    tempMap = self.field.getActionArea(enemy_unit, actionNo, False, (tile[0], tile[1]))
                    actionMap = np.maximum(actionMap, tempMap)  # Only keep the highest damage value for each tile
            enemyThreatMap = enemyThreatMap + actionMap  # Add that character's maximum damage to the total

        # print("ENEMY THREAT MAP:")
        # print(enemyThreatMap)
        # print()

        # PART 1.5
        # GOAL: Encourage the AI to move its units into the objective squares

        OBJECTIVE_WEIGHT = 8 * (own_team_HP / (enemy_team_HP + 0.000000000000001))  # for avoiding div by zero
        # print(f'OBJECTIVE_WEIGHT = {OBJECTIVE_WEIGHT}')

        # PART 2
        # GOAL: Evaluate the damage

        THREAT_WEIGHT = 0.1 * (enemy_team_HP / (own_team_HP + 0.000000000000001))

        DAMAGE_WEIGHT = 1.5 - 0.5 * (enemy_team_HP / (enemy_team_max_HP + 0.000000000000001))

        # print(f'THREAT_WEIGHT = {THREAT_WEIGHT}')
        # print(f'DAMAGE_WEIGHT = {DAMAGE_WEIGHT}')

        # * Enemies do not focus on a single character
        # * No fallback if a character's optimal tiles are all overwritten -> will just stay still
        optimalIndicesList = []  # List of list of indices
        for own_unit in self.own_team:
            movementMap = np.array(self.field.getMovement(own_unit, False))  # Same system as part 1

            ### Some logic here to remove tiles with enemy_team on them
            #
            enemy_pos = [enemy.grid for enemy in self.enemy_team]  # Get list of enemy team's grid coordinates
            if enemy_pos:
                rows, cols = np.transpose(enemy_pos)  # There is probably a better way to do this
                enemy_pos_full = np.zeros((GRID_ROWS, GRID_COLS))
                enemy_pos_full[(rows, cols)] = 1
                movementMap = np.logical_and(movementMap,
                                            np.logical_not(enemy_pos_full))  # Remove occupied tiles from consideration
            #
            ###

            movementTiles = np.argwhere(movementMap > 0)
            destinationMap = np.ones((GRID_ROWS, GRID_COLS)) * -999
            bestActionMap = np.zeros((GRID_ROWS, GRID_COLS), dtype=int)
            bestTargetMap = np.full((GRID_ROWS, GRID_COLS), 999, dtype=int)
            for tile in movementTiles:
                damageMap = np.zeros((GRID_ROWS, GRID_COLS))  # Instead of keeping potential damage on other tiles,
                tileActionNo = 0
                tileTargetPlayerID = 999
                for actionNo in range(len(own_unit.template["actions"])):
                    tempMap = self.field.getActionArea(own_unit, actionNo, False, (tile[0], tile[1]))
                    if np.array_equal(tempMap, np.maximum(damageMap, tempMap)):
                        tileActionNo = actionNo
                        tileTargetPlayerID = 999
                        for enemy_unit in self.enemy_team:
                            if tempMap[enemy_unit.grid[0]][enemy_unit.grid[1]] > 0:  # Player can be targeted
                                tileTargetPlayerID = enemy_unit.id
                        damageMap = np.copy(tempMap)
                destinationMap[tile[0]][tile[1]] = np.max(
                    damageMap)  # The maximum damage is registered to the movement tile instead
                bestActionMap[tile[0]][tile[1]] = tileActionNo
                bestTargetMap[tile[0]][tile[1]] = tileTargetPlayerID
                
            ########
            # APPLY ADJUSTMENTS FROM PERSONALITY
            #
            c_weights = [DAMAGE_WEIGHT, OBJECTIVE_WEIGHT, THREAT_WEIGHT]
            DAMAGE_WEIGHT, OBJECTIVE_WEIGHT, THREAT_WEIGHT = [c_weight * mult for c_weight, mult in zip(c_weights, self.chosen_personality.c_weights_mult)]
            #
            #
            ########
            
            objectiveMap = np.zeros((GRID_ROWS, GRID_COLS))
            objectiveMap[np.nonzero(self.terrain == 3)] = OBJECTIVE_WEIGHT
            objectiveMap = propagate_half(objectiveMap)
            # print(objectiveMap)

            destinationMap = (DAMAGE_WEIGHT * destinationMap) + objectiveMap - (THREAT_WEIGHT * enemyThreatMap)
            optimalIndices = np.argwhere(destinationMap == np.max(destinationMap))
            optimalIndicesList.append([own_unit.id, bestActionMap, bestTargetMap, optimalIndices])
            # print(optimalIndicesList)
            # print(destinationMap)
        optimalIndicesList = sorted(optimalIndicesList, key=lambda s: -len(
            s[3]))  # Sorts the list to let the character with the most optimal tiles "place" first
        for data in optimalIndicesList:  # Insanity
            for index in data[3]:
                self.optimalMap[0][index[0]][index[1]] = data[0]  # Own ID
                self.optimalMap[1][index[0]][index[1]] = data[1][index[0]][index[1]]  # Action to use
                self.optimalMap[2][index[0]][index[1]] = data[2][index[0]][index[1]]  # Target ID

        # print("ENEMY OPTIMAL MAP:")
        # print(optimalMap)
        # print()

        # Initalize a timer state variable.
        # last_action_time = 0
        # action_delay = 500

        # print("---- ACTION LOG ----")

        super().calculate()

    def activate(self, activationNo: int) -> None:

        chara = self.own_team[activationNo]

        tiles = np.argwhere(self.optimalMap[0] == chara.id)
        if tiles.size > 0:
            available_tiles = []
            for tile in tiles.tolist():
                tile_choice = (int(tile[0]), int(tile[1]))
                occupant = Character.getCharacterByGrid(tile_choice)
                if occupant is None or occupant is chara:
                    available_tiles.append(tile_choice)

            if not available_tiles:
                self.passCharaAction(chara)
                self.turnFinished = self.checkCharaActed()
                return

            tile_choice = random.choice(available_tiles)

            row = tile_choice[0]
            col = tile_choice[1]
            optimalActionNo = int(self.optimalMap[1][row][col])
            targetPlayerID = int(self.optimalMap[2][row][col])

            if not self.moveCharaTo(chara, tile_choice):
                self.passCharaAction(chara)
                self.turnFinished = self.checkCharaActed()
                return

            # Perform attack.

            target = Character.getCharacterByID(targetPlayerID)
            if target is not None:
                if chara.acted == False:
                    if self.terrain[target.grid[0]][target.grid[1]] == 1:  # Target standing in a Tree tile
                        modifier = -2
                    elif self.terrain[target.grid[0]][target.grid[1]] == 3:
                        modifier = 2
                    else:
                        modifier = 0
                    self.useCharaAction(chara, target, optimalActionNo, modifier)

            else:
                # print(f"Warning: Target with ID {targetPlayerID} is not found!")
                self.passCharaAction(chara)
                pass
        else:
            self.passCharaAction(chara)
        
        self.turnFinished = self.checkCharaActed()



class AggressivePersonalityCoresAI(PersonalityCores):
    def __init__(self, team) -> None:
        super().__init__(team)
        # Keep 3 entries for parent calculate() compatibility.
        # Every entry still uses only DAMAGE_WEIGHT.
        self.personalities = [
            Personality('Aggressive', (1.5, 0.9, 0.3)),
            Personality('Aggressive', (1.5, 0.9, 0.3)),
            Personality('Aggressive', (1.5, 0.9, 0.3))
        ]


class StrategicPersonalityCoresAI(PersonalityCores):
    def __init__(self, team) -> None:
        super().__init__(team)
        # Keep 3 entries for parent calculate() compatibility.
        # Every entry still uses only OBJECTIVE_WEIGHT.
        self.personalities = [
            Personality('Strategic', (0.3, 1.3, 0.9)),
            Personality('Strategic', (0.3, 1.3, 0.9)),
            Personality('Strategic', (0.3, 1.3, 0.9))
        ]


class SurvivalPersonalityCoresAI(PersonalityCores):
    def __init__(self, team) -> None:
        super().__init__(team)
        # Keep 3 entries for parent calculate() compatibility.
        # Every entry still uses only THREAT_WEIGHT.
        self.personalities = [
            Personality('Survival', (0.2, 0.5, 1.5)),
            Personality('Survival', (0.2, 0.5, 1.5)),
            Personality('Survival', (0.2, 0.5, 1.5))
        ]


class KillOneByOneAI(AIFramework):
    """Hard tactical AI focused on kill confirms with strict threat discipline."""

    def __init__(self, team) -> None:
        super().__init__(team)

    def reset(self) -> None:
        super().reset()
        self.enemy_threat_map = np.zeros((GRID_ROWS, GRID_COLS))
        self.objective_map = np.zeros((GRID_ROWS, GRID_COLS))
        self.projected_enemy_hp: dict[int, float] = {}

    def _build_enemy_threat_map(self) -> np.ndarray:
        enemy_threat_map = np.zeros((GRID_ROWS, GRID_COLS))
        for enemy_unit in self.enemy_team:
            movement_map = np.array(self.field.getMovement(enemy_unit, False))
            movement_tiles = np.argwhere(movement_map > 0)
            action_map = np.zeros((GRID_ROWS, GRID_COLS))
            for tile in movement_tiles:
                for action_no in range(len(enemy_unit.template["actions"])):
                    temp_map = self.field.getActionArea(enemy_unit, action_no, False, (tile[0], tile[1]))
                    action_map = np.maximum(action_map, temp_map)
            enemy_threat_map = enemy_threat_map + action_map
        return enemy_threat_map

    def _build_objective_map(self) -> np.ndarray:
        objective_map = np.zeros((GRID_ROWS, GRID_COLS))
        objective_map[np.nonzero(self.terrain == 3)] = 8
        return propagate_half(objective_map)

    def _remove_occupied_enemy_tiles(self, movement_map: np.ndarray) -> np.ndarray:
        enemy_pos = [enemy.grid for enemy in self.enemy_team]
        if not enemy_pos:
            return movement_map
        enemy_pos_full = np.zeros((GRID_ROWS, GRID_COLS))
        for row, col in enemy_pos:
            enemy_pos_full[row][col] = 1
        return np.logical_and(movement_map, np.logical_not(enemy_pos_full))

    def calculate(self) -> None:
        self.enemy_threat_map = self._build_enemy_threat_map()
        self.objective_map = self._build_objective_map()
        self.projected_enemy_hp = {
            enemy.id: float(enemy.template['curHP'])
            for enemy in self.enemy_team
        }
        super().calculate()

    def activate(self, activationNo: int) -> None:
        chara = self.own_team[activationNo]

        movement_map = np.array(self.field.getMovement(chara, False))
        movement_map = self._remove_occupied_enemy_tiles(movement_map)
        movement_tiles = np.argwhere(movement_map > 0)

        if movement_tiles.size == 0:
            self.passCharaAction(chara)
            self.turnFinished = self.checkCharaActed()
            return

        threat_limit = max(1.0, float(chara.template['curHP']) * 0.65)
        best_candidate = None
        best_score = -10**18

        for tile in movement_tiles:
            row, col = int(tile[0]), int(tile[1])
            tile_threat = float(self.enemy_threat_map[row][col])
            threat_over = max(0.0, tile_threat - threat_limit)
            objective_bonus = float(self.objective_map[row][col]) * 6.0
            base_threat_penalty = tile_threat * 10.0
            strict_threat_penalty = threat_over * 40.0 + (600.0 if threat_over > 0 else 0.0)

            for action_no in range(len(chara.template["actions"])):
                temp_map = self.field.getActionArea(chara, action_no, False, (row, col))
                for enemy_unit in self.enemy_team:
                    erow, ecol = enemy_unit.grid
                    damage = float(temp_map[erow][ecol])
                    if damage <= 0:
                        continue

                    predicted_hp = float(self.projected_enemy_hp.get(enemy_unit.id, enemy_unit.template['curHP']))
                    kill_bonus = 5000.0 if damage >= predicted_hp else 0.0
                    focus_bonus = (300.0 / (predicted_hp + 1.0)) + ((enemy_unit.template['maxHP'] - predicted_hp) * 8.0)
                    damage_score = damage * 12.0
                    overkill_penalty = max(0.0, damage - predicted_hp) * 5.0

                    score = (
                        kill_bonus
                        + focus_bonus
                        + damage_score
                        + objective_bonus
                        - base_threat_penalty
                        - strict_threat_penalty
                        - overkill_penalty
                    )

                    if score > best_score:
                        best_score = score
                        best_candidate = (row, col, action_no, enemy_unit.id, damage)

        if best_candidate is not None:
            row, col, action_no, target_id, planned_damage = best_candidate
            if not self.moveCharaTo(chara, (row, col)):
                self.passCharaAction(chara)
                self.turnFinished = self.checkCharaActed()
                return
            target = Character.getCharacterByID(int(target_id))
            if target is not None and not chara.acted:
                if self.terrain[target.grid[0]][target.grid[1]] == 1:
                    modifier = -2
                elif self.terrain[target.grid[0]][target.grid[1]] == 3:
                    modifier = 2
                else:
                    modifier = 0
                self.useCharaAction(chara, target, int(action_no), modifier)
                if target.id in self.projected_enemy_hp:
                    self.projected_enemy_hp[target.id] = max(0.0, self.projected_enemy_hp[target.id] - float(planned_damage))
            else:
                self.passCharaAction(chara)
        else:
            # No legal attacks: reposition to safest objective-forward tile, then pass.
            best_tile = None
            best_tile_score = -10**18
            for tile in movement_tiles:
                row, col = int(tile[0]), int(tile[1])
                tile_threat = float(self.enemy_threat_map[row][col])
                tile_objective = float(self.objective_map[row][col])
                tile_score = (tile_objective * 8.0) - (tile_threat * 12.0)
                if tile_score > best_tile_score:
                    best_tile_score = tile_score
                    best_tile = (row, col)
            if best_tile is not None:
                self.moveCharaTo(chara, best_tile)
            self.passCharaAction(chara)

        self.turnFinished = self.checkCharaActed()
