from dataclasses import dataclass


@dataclass
class SessionProgress:
    current_game: int
    current_match: int
    match_limit: int
    game_limit: int
    game_p1_match_wins: int
    game_p2_match_wins: int
    total_games_p1: int
    total_games_p2: int
    total_p1_win: int
    total_p2_win: int


def apply_match_result(state: SessionProgress, winner_label: str) -> dict:
    if winner_label == 'P1':
        state.total_p1_win += 1
        state.game_p1_match_wins += 1
    else:
        state.total_p2_win += 1
        state.game_p2_match_wins += 1

    result = {
        'game_finished': False,
        'session_finished': False,
        'game_winner': 'Draw',
        'completed_game': state.current_game,
        'p1_matches_in_game': state.game_p1_match_wins,
        'p2_matches_in_game': state.game_p2_match_wins,
    }

    if state.current_match >= state.match_limit:
        result['game_finished'] = True
        if state.game_p1_match_wins > state.game_p2_match_wins:
            result['game_winner'] = 'P1'
            state.total_games_p1 += 1
        elif state.game_p2_match_wins > state.game_p1_match_wins:
            result['game_winner'] = 'P2'
            state.total_games_p2 += 1

        state.current_game += 1
        state.current_match = 0
        state.game_p1_match_wins = 0
        state.game_p2_match_wins = 0

        if state.current_game > state.game_limit:
            result['session_finished'] = True

    return result
