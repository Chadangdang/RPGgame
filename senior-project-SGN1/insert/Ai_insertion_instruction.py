AI_INSERTION_INSTRUCTION = """

AI INSERTION INSTRUCTION

This feature allows you to develop and test your own AI in the game.
You can create custom strategies, experiment with decision-making models,
and integrate them directly into gameplay.

STEP 1: DOWNLOAD TEMPLATE
- Click "Download AI Template" to get the base file:
- AI_template.py
- This file contains the required structure for your AI.

STEP 2: IMPLEMENT YOUR AI
- Open the template file and modify it.
Requirements:
1. Rename the class
   Example:
   class MyCustomAI(AIFramework):
2. Implement the core functions:
   - calculate(self)
     Runs once per turn.
     Used for board analysis and planning.
   - activate(self, activationNo)
     Runs for each character.
     Used to decide movement and actions.

AVAILABLE FUNCTIONS
Movement:
    self.moveCharaTo(chara, (row, col))
Use Action:
    self.useCharaAction(chara, target, actionNo, modifier)
Pass Turn:
    self.passCharaAction(chara)

GAME INFORMATION
Your team:
    self.own_team
Enemy team:
    self.enemy_team
Movement range:
    self.field.getMovement(chara)
Action range:
    self.field.getActionArea(chara, actionNo)
Get character at position:
    Character.getCharacterByGrid((row, col))
Terrain map:
    self.terrain

STEP 3: UPLOAD YOUR AI
1. Click "Upload AI"
2. Select your .py file

STEP 4: REGISTER YOUR AI
After uploading, provide:
- AI Name (display name)
- Description (strategy explanation)

STEP 5: USE YOUR AI
- Your AI will appear in the selection list.
- Select it to run in the game.

MANAGING YOUR AI
You can:
- Use your AI
- Edit your AI
- Delete your AI from the system

IMPORTANT NOTES
- Your AI must inherit from AIFramework
- You must implement:
    calculate()
    activate()
- Invalid files will be rejected

TIPS
- Start simple (e.g., always attack or random behavior)
- Improve step by step
- Use logs to debug behavior
- Experiment with different strategies
"""
