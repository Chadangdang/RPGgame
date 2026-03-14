from __future__ import annotations

TRIANGLE_ADVANTAGE = {
    ("fighter", "assassin"),
    ("assassin", "wizard"),
    ("wizard", "fighter"),
}

STRONG_MULTIPLIER = 1.20
NEUTRAL_MULTIPLIER = 1.0
WEAK_MULTIPLIER = 0.8

TERRAIN_MODIFIERS = {
    "TreeTile": -2,
    "ObjectiveTile": 2,
    "EmptyTile": 0,
}


def weakness_multiplier(attacker_class: str, defender_class: str) -> float:
    attacker = attacker_class.strip().lower()
    defender = defender_class.strip().lower()

    if (attacker, defender) in TRIANGLE_ADVANTAGE:
        return STRONG_MULTIPLIER
    if (defender, attacker) in TRIANGLE_ADVANTAGE:
        return WEAK_MULTIPLIER
    return NEUTRAL_MULTIPLIER


def terrain_modifier(terrain_type: str | None) -> float:
    if terrain_type is None:
        return 0
    return TERRAIN_MODIFIERS.get(terrain_type, 0)


def calculate_damage(base_damage: float, attacker_class: str, defender_class: str, terrain_type: str | None = None) -> float:
    return (base_damage * weakness_multiplier(attacker_class, defender_class)) + terrain_modifier(terrain_type)


def adjust_template_stats(template: dict) -> dict:
    # Weakness mode does not alter base template stats.
    return dict(template)
