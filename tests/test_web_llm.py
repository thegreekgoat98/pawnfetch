import json
from datetime import timedelta

import httpx
import pytest
import respx

pytest.importorskip("fastapi")

from test_web_roast import game

from pawnfetch.chesscom.client import ChessComClient
from web.app.llm import API_URL, DEFAULT_MODELS, GeminiWriter, RoastText
from web.app.roast import build_roast
from web.app.service import GameInsights, PlayerService
from web.app.store import AppStore

URL = API_URL.format(model=DEFAULT_MODELS[0])
BACKUP_URL = API_URL.format(model=DEFAULT_MODELS[1])
GOOD = {
    "persona": "Caffeinated Bullet Goblin",
    "lines": [
        "100% bullet. Thinking is a luxury they can't afford.",
        "Starts a new game within 2 minutes of every loss. Healthy.",
        "Win rate drops right after a loss. Tilt? Never heard of it.",
    ],
}


def sample_roast():
    pattern = ["win", "win", "win", "loss", "loss", "loss"]
    games = [game(i, pattern[i % 6], time_class="bullet", gap=timedelta(seconds=30)) for i in range(60)]
    return build_roast("me", games)


def gemini_reply(payload, *, thought=False) -> httpx.Response:
    parts = [{"text": "thinking...", "thought": True}] if thought else []
    parts.append({"text": payload if isinstance(payload, str) else json.dumps(payload)})
    body = {"candidates": [{"content": {"parts": parts}}], "usageMetadata": {"promptTokenCount": 300}}
    return httpx.Response(200, json=body)


def test_roast_facts_are_plain_numbers_without_jokes():
    roast = sample_roast()
    assert "100% of their games are bullet" in roast.facts
    assert not any("Thinking is clearly optional" in fact for fact in roast.facts)


@respx.mock
def test_writer_sends_only_facts_and_returns_checked_text():
    route = respx.post(URL).mock(return_value=gemini_reply(GOOD, thought=True))
    text = GeminiWriter("secret-key").write("me", sample_roast())

    assert text == RoastText(**GOOD)
    request = route.calls.last.request
    assert request.headers["x-goog-api-key"] == "secret-key"
    assert "secret-key" not in str(request.url)
    prompt = json.loads(request.content)["contents"][0]["parts"][0]["text"]
    assert "Player: me" in prompt and "- 100% of their games are bullet" in prompt


@pytest.mark.parametrize(
    "reply",
    [
        gemini_reply({**GOOD, "lines": [*GOOD["lines"][:2], "Lost 47 games in a row, a world record."]}),
        gemini_reply("not json"),
        gemini_reply({"persona": "x", "lines": []}),
        httpx.Response(500),
        httpx.ReadTimeout("slow"),
    ],
    ids=["invented-number", "bad-json", "wrong-shape", "server-error", "timeout"],
)
@respx.mock
def test_writer_returns_none_for_anything_unusable(reply):
    for url in (URL, BACKUP_URL):  # overload errors are retried on the backup model
        route = respx.post(url)
        if isinstance(reply, Exception):
            route.mock(side_effect=reply)
        else:
            route.mock(return_value=reply)
    assert GeminiWriter("key").write("me", sample_roast()) is None


def test_writer_from_env(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert GeminiWriter.from_env() is None
    monkeypatch.setenv("GEMINI_API_KEY", " k ")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-a, gemini-b")
    assert GeminiWriter.from_env() == GeminiWriter("k", ("gemini-a", "gemini-b"))


@respx.mock
def test_writer_tries_the_next_model_when_one_is_overloaded():
    respx.post(URL).mock(return_value=httpx.Response(503, json={"error": {"message": "high demand"}}))
    backup = respx.post(BACKUP_URL).mock(return_value=gemini_reply(GOOD))
    assert GeminiWriter("key").write("me", sample_roast()) == RoastText(**GOOD)
    assert backup.called


@respx.mock
def test_writer_does_not_retry_a_bad_request():
    respx.post(URL).mock(return_value=httpx.Response(400, json={"error": {"message": "bad"}}))
    backup = respx.post(BACKUP_URL).mock(return_value=gemini_reply(GOOD))
    assert GeminiWriter("key").write("me", sample_roast()) is None
    assert not backup.called


class Clock:
    def __init__(self):
        self.now = 1_800_000_000.0

    def __call__(self) -> float:
        return self.now


class FakeWriter:
    def __init__(self, text=GOOD):
        self.text = text
        self.calls = []

    def write(self, username, roast):
        self.calls.append(username)
        return RoastText(**self.text) if self.text else None


@pytest.fixture
def make_service(tmp_path):
    def make(writer=None, cap=10):
        clock = Clock()
        service = PlayerService(ChessComClient(), store=AppStore(tmp_path / "app.sqlite", clock), writer=writer, ai_daily_cap=cap)
        roast = sample_roast()
        service._insights = lambda name: GameInsights(openings=None, roast=roast, meetings={})
        return service, clock

    return make


def test_store_round_trip(tmp_path):
    store = AppStore(tmp_path / "sub" / "app.sqlite", Clock())
    saved = store.save_roast("me", sample_roast())
    loaded = store.load_roast("me")
    assert loaded == saved
    assert loaded.first is not None and loaded.facts == []


def test_ai_roast_is_stored_and_reused_for_a_day(make_service):
    writer = FakeWriter()
    service, clock = make_service(writer)

    first = service.get_roast("Me")
    assert (first.source, first.persona) == ("ai", GOOD["persona"])
    assert first.games == 60  # numbers still come from Python
    assert service.get_roast("me") == first
    assert writer.calls == ["me"]

    clock.now += 24 * 60 * 60
    service.get_roast("me")
    assert writer.calls == ["me", "me"]


def test_failed_ai_roast_falls_back_and_is_retried_after_an_hour(make_service):
    writer = FakeWriter(text=None)
    service, clock = make_service(writer)

    roast = service.get_roast("me")
    assert roast.source == "rules"
    assert roast.persona == sample_roast().persona
    service.get_roast("me")
    assert len(writer.calls) == 1

    clock.now += 60 * 60
    service.get_roast("me")
    assert len(writer.calls) == 2


def test_daily_cap_limits_ai_calls(make_service):
    writer = FakeWriter()
    service, _ = make_service(writer, cap=1)
    assert service.get_roast("alice").source == "ai"
    assert service.get_roast("bob").source == "rules"
    assert writer.calls == ["alice"]


def test_without_a_key_roasts_are_rule_based(make_service, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    service, _ = make_service()
    assert service.get_roast("me").source == "rules"


def test_when_every_ai_slot_is_busy_the_classic_roast_is_shown_but_not_stored(tmp_path):
    writer = FakeWriter()
    store = AppStore(tmp_path / "app.sqlite", Clock())
    service = PlayerService(ChessComClient(), store=store, writer=writer, ai_concurrency=1, ai_wait=0.01)
    roast = sample_roast()
    service._insights = lambda name: GameInsights(openings=None, roast=roast, meetings={})

    service._llm.acquire()  # someone else's AI roast is being written
    try:
        assert service.get_roast("me").source == "rules"
    finally:
        service._llm.release()
    assert writer.calls == []
    assert store.load_roast("me") is None
    assert service.get_roast("me").source == "ai"  # the next visit gets the AI roast


@respx.mock
def test_lines_with_invented_numbers_are_dropped_not_the_whole_roast():
    reply = {**GOOD, "lines": [*GOOD["lines"], "Tilts hardest after 11 PM, like clockwork."]}
    respx.post(URL).mock(return_value=gemini_reply(reply))
    assert GeminiWriter("key").write("me", sample_roast()) == RoastText(**GOOD)
