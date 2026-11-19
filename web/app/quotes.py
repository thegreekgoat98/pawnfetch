"""Short, widely attributed chess quotes for the home page."""

from __future__ import annotations

import random

QUOTES: tuple[tuple[str, str], ...] = (
    ("Tactics flow from a superior position.", "Bobby Fischer"),
    ("I don't believe in psychology. I believe in good moves.", "Bobby Fischer"),
    (
        (
            "You must take your opponent into a deep dark forest where 2+2=5, "
            "and the path leading out is only wide enough for one."
        ),
        "Mikhail Tal",
    ),
    (
        "In order to improve your game, you must study the endgame before everything else.",
        "José Raúl Capablanca",
    ),
    ("Help your pieces so they can help you.", "Paul Morphy"),
    ("The pawns are the soul of chess.", "François-André Danican Philidor"),
    ("When you see a good move, look for a better one.", "Emanuel Lasker"),
    ("The hardest game to win is a won game.", "Emanuel Lasker"),
    ("Every chess master was once a beginner.", "Irving Chernev"),
    (
        "The winner of the game is the player who makes the next-to-last mistake.",
        "Savielly Tartakower",
    ),
    ("Even a poor plan is better than no plan at all.", "Mikhail Chigorin"),
    ("Chess is everything: art, science and sport.", "Anatoly Karpov"),
    (
        (
            "Play the opening like a book, the middlegame like a magician, "
            "and the endgame like a machine."
        ),
        "Rudolf Spielmann",
    ),
    (
        (
            "Some people think that if their opponent plays a beautiful game, it's OK to lose. "
            "I don't. You have to be merciless."
        ),
        "Magnus Carlsen",
    ),
    ("Chess is a sea in which a gnat may drink and an elephant may bathe.", "Indian proverb"),
)


def random_quote() -> tuple[str, str]:
    return random.choice(QUOTES)
