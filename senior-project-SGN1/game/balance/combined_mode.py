from __future__ import annotations

from copy import deepcopy

from game.balance.baseline_mode import BALANCE_TARGET, average_damage
from game.balance.passive_mode import passive_score
from game.balance.weakness_mode import terrain_modifier, weakness_multiplier


def base_power(template: dict) -> float:
    return template.get("maxHP", 0) + (template.get("movement", 0) * 3) + average_damage(template.get("actions", []))


def final_power(
    template: dict,
    attacker_class: str,
    defender_class: str,
    base_damage: float,
    terrain_type: str | None = None,
) -> float:
    weak_score = base_damage * weakness_multiplier(attacker_class, defender_class)
    return base_power(template) + passive_score(template) + weak_score + terrain_modifier(terrain_type)


def balance_modifier(
    template: dict,
    attacker_class: str,
    defender_class: str,
    base_damage: float,
    terrain_type: str | None = None,
) -> float:
    power = final_power(template, attacker_class, defender_class, base_damage, terrain_type)
    if power <= 0:
        return 1.0
    return BALANCE_TARGET / power


def adjust_template_stats(
    template: dict,
    attacker_class: str | None = None,
    defender_class: str | None = None,
    base_damage: float | None = None,
    terrain_type: str | None = None,
) -> dict:
    adjusted = deepcopy(template)
    actor = attacker_class or str(template.get("display_name", "")).strip().lower()
    target = defender_class or actor
    raw_damage = base_damage
    if raw_damage is None:
        actions = template.get("actions", [])
        raw_damage = actions[0].get("damage", 0) if actions else 0

    modifier = balance_modifier(template, actor, target, raw_damage, terrain_type)
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


def calculate_damage(base_damage: float, attacker_class: str, defender_class: str, terrain_type: str | None = None) -> float:
    return (base_damage * weakness_multiplier(attacker_class, defender_class)) + terrain_modifier(terrain_type)
