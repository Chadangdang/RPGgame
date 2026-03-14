from __future__ import annotations

from game.balance import balance_controller


def calculate_damage(base_damage: float, attacker_class: str, defender_class: str, terrain_type: str | None = None) -> float:
    return balance_controller.calculate_damage(
        base_damage=base_damage,
        attacker_class=attacker_class,
        defender_class=defender_class,
        terrain_type=terrain_type,
    )
