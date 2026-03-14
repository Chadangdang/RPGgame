from __future__ import annotations

from game.balance import baseline_mode, combined_mode, passive_mode, weakness_mode

BASELINE = "BASELINE"
PASSIVE = "PASSIVE"
WEAKNESS = "WEAKNESS"
COMBINED = "COMBINED"

_MODE_MAP = {
    BASELINE: baseline_mode,
    PASSIVE: passive_mode,
    WEAKNESS: weakness_mode,
    COMBINED: combined_mode,
}

_active_mode_name = BASELINE
_active_mode_module = baseline_mode


def _normalize_mode(mode: str | None) -> str:
    if mode is None:
        return BASELINE
    mode_name = str(mode).strip().upper()
    return mode_name if mode_name in _MODE_MAP else BASELINE


def load_balance_mode(mode: str | None):
    global _active_mode_name, _active_mode_module
    _active_mode_name = _normalize_mode(mode)
    _active_mode_module = _MODE_MAP[_active_mode_name]
    return _active_mode_module


def get_active_mode() -> str:
    return _active_mode_name


def adjust_template_stats(template: dict, **kwargs) -> dict:
    if hasattr(_active_mode_module, "adjust_template_stats"):
        return _active_mode_module.adjust_template_stats(template, **kwargs)
    return dict(template)


def calculate_damage(base_damage: float, attacker_class: str = "", defender_class: str = "", terrain_type: str | None = None, **kwargs) -> float:
    if hasattr(_active_mode_module, "calculate_damage"):
        return _active_mode_module.calculate_damage(base_damage, attacker_class, defender_class, terrain_type, **kwargs)
    return base_damage

def load_balance_mode(mode):
    global current_mode

    print("=== LOADING BALANCE MODE ===")
    print("Mode selected:", mode)

    if mode is None:
        mode = "BASELINE"

    print("Final mode used:", mode)
