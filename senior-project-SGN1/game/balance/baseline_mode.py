from __future__ import annotations

from copy import deepcopy

BALANCE_TARGET = 41.5


def average_damage(actions: list[dict]) -> float:
    if not actions:
        return 0.0
    values = [action.get("damage", 0) for action in actions]
    return sum(values) / len(values)


def base_power(template: dict) -> float:
    return template.get("maxHP", 0) + (template.get("movement", 0) * 3) + average_damage(template.get("actions", []))


def balance_modifier(template: dict) -> float:
    power = base_power(template)
    if power <= 0:
        return 1.0
    return BALANCE_TARGET / power


def adjust_template_stats(template: dict) -> dict:
    adjusted = deepcopy(template)
    modifier = balance_modifier(template)

    adjusted["maxHP"] = int(round(template.get("maxHP", 0) * modifier))
    adjusted["curHP"] = adjusted["maxHP"]

    adjusted_actions = []
    for action in template.get("actions", []):
        new_action = dict(action)
        if "damage" in new_action:
            new_action["damage"] = int(round(new_action["damage"] * modifier))
        adjusted_actions.append(new_action)

    adjusted["actions"] = adjusted_actions
    # movement stays unchanged by design
    adjusted["movement"] = template.get("movement", 0)
    return adjusted


def calculate_damage(base_damage: float, *_args, **_kwargs) -> float:
    return base_damage
