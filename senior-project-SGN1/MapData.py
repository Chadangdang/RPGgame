import json
from Constants import MAP_PATH

class MapData:
    def __init__(self) -> None:
        self.data = self.load_map()

    def load_map(self) -> dict:
        try:
            with open(MAP_PATH, 'r') as f:
                data = json.load(f)

            return data["map"]


        except FileNotFoundError:
            raise RuntimeError(f"Error: The file {MAP_PATH} was not found.")

        except json.decoder.JSONDecodeError:
            raise RuntimeError(f"Error: Failed to decode the template {MAP_PATH} file.")