from datetime import datetime, timedelta, timezone

from pawnfetch.chesscom.models import Game, GamePlayer
from web.app.rivals import head_to_head, index_meetings
from web.app.roast import DEFAULT_PERSONA, MIN_GAMES, build_roast

START = datetime(2026, 9, 1, tzinfo=timezone.utc)
LOSS_CODES = {"loss": "resigned", "timeout": "timeout", "draw": "agreed"}


def game(i, result="win", *, white=True, time_class="blitz", first_move=None, gap=timedelta(minutes=30), opponent=None):
    """Game number i for "me". `result` is from my side: "win", "loss", "timeout" or "draw"."""
    mine = "win" if result == "win" else LOSS_CODES[result]
    theirs = {"win": "resigned", "draw": "agreed"}.get(result, "win")
    me = GamePlayer("Me", 1500 + i, mine)
    opp = GamePlayer(opponent or f"opp{i}", 1500, theirs)
    end = START + i * timedelta(hours=1)
    return Game(
        url=f"https://www.chess.com/game/live/{i}",
        white=me if white else opp,
        black=opp if white else me,
        end_time=end,
        time_class=time_class,
        first_move=first_move,
        moves=40,
        start_time=end - timedelta(hours=1) + gap,
    )


def test_too_few_games_is_not_roasted():
    assert build_roast("me", [game(i) for i in range(MIN_GAMES - 1)]) is None


def test_bullet_addict_gets_the_bullet_persona():
    games = [game(i, "win" if i % 2 else "loss", time_class="bullet") for i in range(40)]
    roast = build_roast("Me", games)
    assert roast.persona == "Caffeinated Bullet Goblin"
    assert roast.main_mode == "Bullet"
    assert any("100% of games are bullet" in line for line in roast.lines)


def test_one_first_move_player_is_called_out():
    games = [game(i, "win" if i % 2 else "loss", first_move="e4") for i in range(40)]
    assert any(line.startswith("1.e4 in 100% of White games") for line in build_roast("me", games).lines)


def test_tilt_compares_results_after_losses_and_wins():
    # W W W L L L repeated: after a win, two in three next games are won; after a loss, one.
    pattern = ["win", "win", "win", "loss", "loss", "loss"]
    games = [game(i, pattern[i % 6]) for i in range(60)]
    lines = build_roast("me", games).lines
    assert any(line.startswith("Win rate drops from 67% to 3") for line in lines)


def test_quick_requeue_after_losses_counts_as_revenge():
    games = [game(i, "win" if i % 2 else "loss", gap=timedelta(seconds=30)) for i in range(40)]
    assert any("within 2 minutes of 100% of losses" in line for line in build_roast("me", games).lines)


def test_bland_player_gets_default_persona_and_three_lines():
    pattern = ["win", "loss"]
    games = [game(i, pattern[i % 2], white=i % 4 < 2) for i in range(30)]
    for g in games:
        g.white.rating = g.black.rating = 1500  # no rating trend
    roast = build_roast("me", games)
    assert roast.persona == DEFAULT_PERSONA
    assert len(roast.lines) == 3


def test_head_to_head_counts_games_against_one_opponent():
    games = [
        game(1, "win", opponent="Rival"),
        game(2, "draw", opponent="rival"),
        game(3, "loss", opponent="someone"),
        game(4, "loss", white=False, opponent="RIVAL"),
    ]
    meetings = index_meetings("me", games)
    record = head_to_head(meetings["rival"])
    assert (record.wins, record.draws, record.losses) == (1, 1, 1)
    assert record.recent[0].url.endswith("/4")  # newest first
    assert "someone" in meetings
