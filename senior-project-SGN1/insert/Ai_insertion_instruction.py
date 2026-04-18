AI_INSERTION_INSTRUCTION = """
AI INSERTION GUIDE

This feature allows you to develop, customize, and test your own AI within the game.
You can design strategies, experiment with decision-making logic, and integrate your AI directly into gameplay.

--------------------------------------------------

STEP 1: DOWNLOAD TEMPLATE

Click "Download AI Template" to obtain the base file:
AI_template.py

This template provides the required structure and functions for your AI implementation.

--------------------------------------------------

STEP 2: IMPLEMENT YOUR AI

Open the template file and modify it according to your strategy.

Requirements:

1. Rename the class
   Example:
   class MyCustomAI(AIFramework):

2. Implement the core functions:

   - calculate(self)
     - Executes once per turn
     - Use for analyzing the board and planning decisions

   - activate(self, activationNo)
     - Executes for each character
     - Define movement and action behavior

--------------------------------------------------

AVAILABLE FUNCTIONS

Movement:
    self.moveCharaTo(chara, (row, col))

Use Action:
    self.useCharaAction(chara, target, actionNo, modifier)

Pass Turn:
    self.passCharaAction(chara)

--------------------------------------------------

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

--------------------------------------------------

STEP 3: UPLOAD YOUR AI

Click "Import AI"

--------------------------------------------------

STEP 4: REGISTER YOUR AI

After uploading, provide:

- AI Name (display name)
- Description (optional explanation of your strategy)
- Select your .py file then upload the file

--------------------------------------------------

STEP 5: USE YOUR AI

Your AI will appear in the selection list for both players.
You can select and run it during gameplay.

--------------------------------------------------

MANAGING YOUR AI

You can manage your custom AI directly from the interface:

- Click the "Edit" button next to the selection list to modify its details
- Delete your AI from the system if no longer needed

--------------------------------------------------

IMPORTANT NOTES

- Your AI must inherit from AIFramework
- The following functions are required:
    • calculate()
    • activate()
- Invalid or improperly structured files will be rejected

--------------------------------------------------

TIPS

- Start with a simple strategy (e.g., basic attack or random behavior)
- Improve your AI incrementally
- Use logging to debug and understand behavior
- Experiment with different approaches to optimize performance

--------------------------------------------------
"""