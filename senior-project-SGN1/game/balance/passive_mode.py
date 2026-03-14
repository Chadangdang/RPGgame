from __future__ import annotations

from copy import deepcopy

from game.balance.baseline_mode import BALANCE_TARGET, average_damage

PASSIVE_SPECS = {
    "fighter": [
        {"effect": 3, "trigger_weight": 0.6, "type_multiplier": 1.6},
        {"effect": 0.5, "trigger_weight": 0.6, "type_multiplier": 1.8},
    ],
    "wizard": [
        {"effect": 1, "trigger_weight": 1.0, "type_multiplier": 2.0},
        {"effect": 2, "trigger_weight": 1.0, "type_multiplier": 1.4},
    ],
    "assassin": [
        {"effect": 1.5, "trigger_weight": 0.8, "type_multiplier": 1.5},
        {"effect": 1.5, "trigger_weight": 0.7, "type_multiplier": 2.0},
    ],
}


def base_power(template: dict) -> float:
    return template.get("maxHP", 0) + (template.get("movement", 0) * 3) + average_damage(template.get("actions", []))


def passive_score(template: dict) -> float:
    class_name = str(template.get("display_name", "")).strip().lower()
    specs = PASSIVE_SPECS.get(class_name, [])
    return sum(item["effect"] * item["trigger_weight"] * item["type_multiplier"] for item in specs)


def enhanced_power(template: dict) -> float:
    return base_power(template) + passive_score(template)


def balance_modifier(template: dict) -> float:
    power = enhanced_power(template)
    if power <= 0:
        return 1.0
    return BALANCE_TARGET / power


def adjust_template_stats(template: dict) -> dict:
    adjusted = deepcopy(template)
    modifier = balance_modifier(template)

    adjusted["maxHP"] = int(round(template.get("maxHP", 0) * modifier))
    adjusted["curHP"] = adjusted["maxHP"]
    adjusted["movement"] = template.get("movement", 0)

    adjusted_actions = []
    for action in template.get("actions", []):
        new_action = dict(action)
        if "damage" in new_action:
            new_action["damage"] = int(round(new_action["damage"] * modifier))
        adjusted_actions.append(new_action)
    adjusted["actions"] = adjusted_actions
    return adjusted


def calculate_damage(base_damage: float, *_args, **_kwargs) -> float:
    return base_damage
