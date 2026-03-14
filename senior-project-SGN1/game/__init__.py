"""Game package containing runtime wiring and controller composition."""

__all__ = ["GameMain", "run_game"]


def __getattr__(name):
    if name == "GameMain":
        from game.controller import GameMain
        return GameMain
    if name == "run_game":
        from game.runner import run_game
        return run_game
    raise AttributeError(name)
