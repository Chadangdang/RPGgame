class Objective:
    def __init__(self, id):
        self.id = id
        match id:
            case 0: # Attack Point
                self.size = 2 # 2x2             
                self.name = "Attack Point"
                self.location = "corner"
                self.enemy_count = 5
