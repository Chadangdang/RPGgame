import pygame
from Constants import *
from Template import *

class Character:
    id = 0
    team1_list: list['Character'] = []
    team2_list: list['Character'] = []
    weakness_system_enabled = False
    fireball_burn_mode = 'default'

    @staticmethod
    def setWeaknessSystem(enabled: bool) -> None:
        Character.weakness_system_enabled = bool(enabled)

    @staticmethod
    def setFireballBurnMode(mode: str) -> None:
        allowed = {'default', 'new_stats_only', 'new_stats_weakness'}
        Character.fireball_burn_mode = mode if mode in allowed else 'default'

    @staticmethod
    def _damage_multiplier(attacker: 'Character', target: 'Character') -> float:
        if not Character.weakness_system_enabled:
            return 1.0

        atk = str(attacker.template.get('display_name', '')).strip().lower()
        dfn = str(target.template.get('display_name', '')).strip().lower()

        # Advantage cycle:
        # Fighter > Assassin > Wizard > Fighter
        advantage_pairs = {
            ('fighter', 'assassin'),
            ('assassin', 'wizard'),
            ('wizard', 'fighter'),
        }

        if (atk, dfn) in advantage_pairs:
            return 1.15
        if (dfn, atk) in advantage_pairs:
            return 0.85
        return 1.0

    @staticmethod
    def getCharacterByID(id) -> 'Character | None':
        for chara in Character.team1_list + Character.team2_list:
            if chara.id == id:
                return chara
        return None
    
    @staticmethod
    def getCharacterByGrid(grid: tuple[int, int]) -> 'Character | None':
        for chara in Character.team1_list + Character.team2_list:
            if chara.grid == grid:
                return chara
        return None

    @staticmethod
    def removeCharacter(chara) -> None:
        if chara in Character.team1_list:
            Character.team1_list.remove(chara)
        elif chara in Character.team2_list:
            Character.team2_list.remove(chara)

    @staticmethod
    def removeAllCharacters() -> None:
        Character.id = 0
        Character.team1_list = []
        Character.team2_list = []

    def __init__(self, screen: pygame.Surface, size: tuple[int, int], grid: tuple[int, int], name: str, team: int) -> None:
        self.screen = screen
        self.grid = grid
        self.id = Character.id
        Character.id += 1
        self.template = Template(name).data
        # per-instance mutable stats
        self.movement = self.template.get('movement', 0)
        self.status_effects: list[dict] = []
        self.movement_debuff_turns: int = 0
        self.moved = False
        self.acted = False
        self.alive = True

        if self.template and 'img' in self.template:
            # print(str(self.id) + "   " + self.template["img"])
            self.image = pygame.transform.scale(pygame.image.load(self.template["img"]), size)

        else:
            print(f"Failed to load template or image for character {name}")
            self.image = None
        Character.getCharacterByID(id)  # I forgot what this line is for so I'll keep it anyway
        # if self.type == "player":
        #     Character.team1_list.append(self)
        # elif self.type == "enemy":
        #     Character.team2_list.append(self)

        if team == 1:
            Character.team1_list.append(self)
        else:
            Character.team2_list.append(self)
        
    def moveTo(self, grid: tuple[int, int], update = True) -> None:
        self.grid = grid
        if update:
            self.moved = True

    def attack(self, target: 'Character', selected_action: int, modifier: int = 0, field=None) -> tuple[int, list[str]]:
        logs: list[str] = []
        action = self.template["actions"][selected_action]
        base = action.get("damage", 0) + modifier

        # If this action is a heal, apply healing and return
        if action.get("action_type", "").lower() == "heal" or action.get("heal") is not None:
            heal_amt = int(action.get("heal", 0))
            # apply caster heal bonus passives
            for passive in self.template.get('passives', []):
                if passive.get('type') == 'heal_bonus':
                    heal_amt += int(passive.get('value', 0))

            # Heal all allies (including self)
            allies = Character.team1_list if self in Character.team1_list else Character.team2_list
            for ally in allies:
                before = ally.template.get('curHP', 0)
                ally.template['curHP'] = min(ally.template.get('maxHP', 9999), before + heal_amt)
                healed = ally.template['curHP'] - before
                logs.append(f"{ally.template.get('display_name')} healed {healed} HP from {action.get('action_display_name','Heal')}")
            self.acted = True
            return 0, logs

        # Apply attacker passives that modify outgoing damage (terrain multipliers etc.)
        damage = base
        for passive in self.template.get('passives', []):
            ptype = passive.get('type', '')
            if 'terrain_multiplier' in ptype or 'terrain' in ptype:
                terrains = passive.get('terrain', [])
                if field is not None:
                    try:
                        row, col = self.grid
                        cur_terrain = field.boxes[row][col].terrain
                    except Exception:
                        cur_terrain = None
                    matched = False
                    for t in terrains:
                        tl = str(t).lower()
                        if 'tree' in tl or 'forest' in tl:
                            if cur_terrain == 1:
                                matched = True
                                break
                        if 'rock' in tl:
                            if cur_terrain == 2:
                                matched = True
                                break
                    if matched:
                        val = passive.get('value', 1)
                        try:
                            multiplier = float(val)
                        except Exception:
                            multiplier = 1.0
                        old = damage
                        damage = int(damage * multiplier)
                        logs.append(f"{self.template.get('display_name')} deals {multiplier}x damage due to {passive.get('passive_name','terrain passive')}")

        # Weakness system multiplier (if enabled)
        weakness_mult = Character._damage_multiplier(self, target)
        if weakness_mult != 1.0:
            old = damage
            damage = int(round(damage * weakness_mult))
            logs.append(
                f"{self.template.get('display_name')} deals {weakness_mult:.2f}x damage to {target.template.get('display_name')} (from {old} to {damage})"
            )

        # Damage reduction from target passives
        for passive in target.template.get('passives', []):
            ptype = passive.get('type', '')
            # flat reduction when below percent threshold
            if 'damage_reduction' in ptype:
                threshold = passive.get('threshold')
                apply_reduction = True
                if threshold is not None:
                    curpct = target.template.get('curHP', 0) / max(1, target.template.get('maxHP', 1))
                    apply_reduction = curpct < threshold
                if apply_reduction:
                    val = passive.get('value', 0)
                    if isinstance(val, float) and 0 < val < 1:
                        old = damage
                        damage = int(damage * (1 - val))
                        logs.append(f"{target.template.get('display_name')} reduces incoming damage by {int(old-damage)} ({int(val*100)}%) due to {passive.get('passive_name','passive')}")
                    else:
                        old = damage
                        damage = max(0, int(damage - val))
                        logs.append(f"{target.template.get('display_name')} reduces incoming damage by {int(old-damage)} (flat) due to {passive.get('passive_name','passive')}")

        # Apply damage
        damage = max(0, int(damage))
        target.template['curHP'] -= damage

        # Apply simple status effects based on action name
        action_name = self.template["actions"][selected_action].get("action_display_name", "").lower()
        # Fire actions apply burn
        if 'fire' in action_name or 'burn' in action_name:
            # Special-case Fireball: fixed burn of 3 per turn for 2 turns
            if 'fireball' in action_name:
                if Character.fireball_burn_mode == 'new_stats_only':
                    burn_dmg = 3
                elif Character.fireball_burn_mode == 'new_stats_weakness':
                    burn_base = 3
                    burn_mult = Character._damage_multiplier(self, target)
                    if burn_mult >= 1.0:
                        burn_dmg = max(1, int((burn_base * burn_mult) + 0.9999))
                    else:
                        burn_dmg = max(1, int(burn_base * burn_mult))
                else:
                    burn_dmg = 3
                burn_turns = 2
            else:
                burn_dmg = max(1, int(damage * 0.5))
                burn_turns = 2
            # check attacker passive to amplify burn
            for passive in self.template.get('passives', []):
                if passive.get('type') == 'burn_amplify':
                    burn_dmg += int(passive.get('value', 0))
            target.status_effects.append({'type': 'burn', 'turns': burn_turns, 'damage_per_turn': burn_dmg})
            logs.append(f"{target.template.get('display_name')} is Burned for {burn_turns} turns ({burn_dmg} dmg/turn)")

        # Ice actions reduce movement temporarily
        if 'ice' in action_name or 'iceshard' in action_name:
            # Iceshard reduces movement by 2 for 2 turns
            if target.movement > 2:
                target.movement = max(1, target.movement - 2)
            else:
                target.movement = 1
            target.movement_debuff_turns = 2
            logs.append(f"{target.template.get('display_name')}'s movement reduced by 2 for 2 turns")

        # Lifesteal on attacker passives
        for passive in self.template.get('passives', []):
            ptype = passive.get('type', '')
            if 'lifesteal' in ptype:
                threshold = passive.get('threshold')
                apply_ls = True
                if threshold is not None:
                    curpct = self.template.get('curHP', 0) / max(1, self.template.get('maxHP', 1))
                    apply_ls = curpct < threshold
                if apply_ls:
                    val = passive.get('value', 0)
                    # value may be fraction
                    heal_amt = int(damage * val) if 0 < val < 1 else int(val)
                    self.template['curHP'] = min(self.template.get('maxHP', 9999), self.template.get('curHP', 0) + heal_amt)
                    logs.append(f"{self.template.get('display_name')} heals {heal_amt} HP from {passive.get('passive_name','lifesteal')}")

        if target.template['curHP'] <= 0:
            target.alive = False
            Character.removeCharacter(target)
        self.acted = True
        return damage, logs

    def reset(self) -> None:
        self.moved = False
        self.acted = False


    def render(self, pos: tuple[float, float]) -> None:
        if self.image and self in Character.team1_list + Character.team2_list:
            self.screen.blit(self.image, pos)
