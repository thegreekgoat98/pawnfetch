from importlib.metadata import version

import httpx
import respx
from typer.testing import CliRunner

from pawnfetch.cli import app

runner = CliRunner()


def test_version_option():
    result = runner.invoke(app, ["--version"])

    assert result.exit_code == 0
    assert result.stdout == f"pawnfetch {version('pawnfetch')}\n"


@respx.mock
def test_profile_command_renders_profile():
    respx.get("https://api.chess.com/pub/player/hikaru").mock(
        return_value=httpx.Response(
            200,
            json={"username": "hikaru", "player_id": 1, "status": "premium"},
        )
    )

    result = runner.invoke(app, ["profile", "hikaru"])

    assert result.exit_code == 0
    assert "chess.com/hikaru" in result.stdout
    assert "premium" in result.stdout


@respx.mock
def test_profile_command_writes_errors_to_stderr():
    respx.get("https://api.chess.com/pub/player/missing").mock(
        return_value=httpx.Response(404, json={})
    )

    result = runner.invoke(app, ["profile", "missing"])

    assert result.exit_code == 1
    assert result.stdout == ""
    assert "No chess.com player found" in result.stderr


@respx.mock
def test_stats_command_renders_stats():
    respx.get("https://api.chess.com/pub/player/hikaru/stats").mock(
        return_value=httpx.Response(
            200,
            json={"chess_blitz": {"last": {"rating": 3000}, "record": {"win": 1}}},
        )
    )

    result = runner.invoke(app, ["stats", "hikaru"])

    assert result.exit_code == 0
    assert "Blitz" in result.stdout
    assert "3000" in result.stdout
    assert "chess.com/hikaru" in result.stdout
    assert "escape(" not in result.stdout


@respx.mock
def test_compare_command_fetches_both_players_and_renders_ratings():
    for username, rating in (("hikaru", 2800), ("magnus", 2900)):
        profile = {"username": username, "player_id": rating, "status": "premium"}
        stats = {"chess_blitz": {"last": {"rating": rating}, "record": {}}}
        respx.get(f"https://api.chess.com/pub/player/{username}").mock(
            return_value=httpx.Response(200, json=profile)
        )
        respx.get(f"https://api.chess.com/pub/player/{username}/stats").mock(
            return_value=httpx.Response(200, json=stats)
        )

    result = runner.invoke(app, ["compare", "hikaru", "magnus"])

    assert result.exit_code == 0
    assert "hikaru vs magnus" in result.stdout
    assert "2800" in result.stdout
    assert "2900" in result.stdout


@respx.mock
def test_profile_command_prints_bracketed_text_literally():
    respx.route(host="api.chess.com").mock(
        return_value=httpx.Response(
            200,
            json={
                "username": "[b]x",
                "player_id": 1,
                "status": "basic",
                "name": "Ann [/x]",
                "location": "Bangalore [/x]",
            },
        )
    )

    result = runner.invoke(app, ["profile", "x"])

    assert result.exit_code == 0
    assert "chess.com/[b]x" in result.stdout
    assert "Ann [/x]" in result.stdout
    assert "Bangalore [/x]" in result.stdout


@respx.mock
def test_stats_command_prints_bracketed_username_literally():
    respx.route(host="api.chess.com").mock(
        return_value=httpx.Response(
            200, json={"chess_blitz": {"last": {"rating": 3000}, "record": {}}}
        )
    )

    result = runner.invoke(app, ["stats", "[b]x"])

    assert result.exit_code == 0
    assert "chess.com/[b]x" in result.stdout


@respx.mock
def test_compare_command_prints_bracketed_usernames_literally():
    respx.route(host="api.chess.com").mock(
        return_value=httpx.Response(
            200, json={"username": "[b]x", "player_id": 1, "status": "basic"}
        )
    )

    result = runner.invoke(app, ["compare", "a", "b"])

    assert result.exit_code == 0
    assert "[b]x vs [b]x" in result.stdout


@respx.mock
def test_error_message_prints_bracketed_username_literally():
    respx.route(host="api.chess.com").mock(return_value=httpx.Response(404, json={}))

    result = runner.invoke(app, ["profile", "[b]x"])

    assert result.exit_code == 1
    assert "'[b]x'" in result.stderr