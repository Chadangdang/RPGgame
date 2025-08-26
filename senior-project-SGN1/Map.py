import random
from Objective import Objective
from MapData import MapData

class Map:
    def __init__(self, grid: tuple[int, int]) -> None:
        self.map_list = MapData().data
        self.map_name = ''
        self.terrain = [[0] * grid[1] for _ in range(grid[0])]
        # Terrain numbering:
        #   0 - Nothing
        #   1 - Tree
        #   2 - Rock
        #   3 - Objective
        #   4 - Player Spawn
        #   5 - Enemy Spawn
        self.objective = Objective(random.randint(0, 0))  # Because there is only one programmed right now

    def generateTerrain(self, randomMap: bool = True, mapID: int = 0) -> None:
        if randomMap:
            self.map_name, self.terrain = random.choice(list(self.map_list.items())[1:])
        else:
            self.map_name, self.terrain = str(mapID), self.map_list['map ' + str(mapID)]
        # print(self.map_name)

    # def generateTerrain(self):
    #     # Place the objective
    #     match self.objective.location:
    #         case "corner": # Puts Objective in one corner, then Player Spawn on the opposite corner
    #             m = random.choice(("left", "right"))
    #             n = random.choice((-1, 1))
    #             for i in range(self.objective.size):
    #                 match m:
    #                     case "left":
    #                         self.terrain[n-i][0:self.objective.size] = [3, 3]
    #                         self.terrain[-n-i][-self.objective.size:] = [4, 4]
    #                     case "right":
    #                         self.terrain[n-i][-self.objective.size:] = [3, 3]
    #                         self.terrain[-n-i][0:self.objective.size] = [4, 4]
    #
    #     # Generate terrain features clusters
    #     for i in range(random.randint(4,6)):   # Number of clusters
    #         while True:
    #             tiles = []
    #             tiles.append((random.randint(0, self.rows - 1), random.randint(0, self.cols - 1)))   # The origin tile of the cluster
    #             if self.terrain[tiles[0][0]][tiles[0][1]] == 0:
    #                 break
    #         type = random.randint(1,2)
    #         amount = random.randint(4-type,7-type)
    #         while len(tiles) < amount:
    #             candidates = []
    #             for tile in tiles:
    #                 if tile[0] != self.rows - 1 and (tile[0]+1,tile[1]) not in tiles and self.terrain[tile[0]+1][tile[1]] == 0:
    #                     candidates.append((tile[0]+1,tile[1]))
    #                 if tile[0] != 0 and (tile[0]-1,tile[1]) not in tiles and self.terrain[tile[0]-1][tile[1]] == 0:
    #                     candidates.append((tile[0]-1,tile[1]))
    #                 if tile[1] != self.cols - 1 and (tile[0],tile[1]+1) not in tiles and self.terrain[tile[0]][tile[1]+1] == 0:
    #                     candidates.append((tile[0],tile[1]+1))
    #                 if tile[1] != 0 and (tile[0],tile[1]+1) not in tiles and self.terrain[tile[0]][tile[1]-1] == 0:
    #                     candidates.append((tile[0],tile[1]-1))
    #             if candidates:
    #                 tiles.append(random.choice(candidates))
    #         for tile in tiles:
    #             self.terrain[tile[0]][tile[1]] = type
