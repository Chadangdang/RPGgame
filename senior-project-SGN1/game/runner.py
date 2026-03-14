import pygame

from Constants import MAX_FRAME_RATE
from game.controller import GameMain


def run_game() -> None:
    """Run the main pygame loop using GameMain as the orchestrator."""
    main = GameMain()
    clock = pygame.time.Clock()

    while True:
        pygame.display.set_caption(f"Turn-based game : {int(clock.get_fps())} FPS")

        dt = clock.tick(MAX_FRAME_RATE) / 1000.0
        events = pygame.event.get()

        main.update(dt, events)
        main.render(dt)

        pygame.display.update()
