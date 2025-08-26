import json
from Constants import TEMPLATE_PATH

class Template:
    def __init__(self, name: str) -> None:
        self.data = self.load_template(name)

    def load_template(self, name: str) -> dict:
        try:
            with open(TEMPLATE_PATH, 'r') as f:
                data = json.load(f)

            for template in data["templates"]:
                if name == template["template_name"]:
                    return template

            print(f"Template {name} not found. Using the default one.")
            return data["templates"][0]

        except FileNotFoundError:
            raise RuntimeError(f"Error: The file {TEMPLATE_PATH} was not found.")

        except json.decoder.JSONDecodeError:
            raise RuntimeError(f"Error: Failed to decode the template {TEMPLATE_PATH} file.")
