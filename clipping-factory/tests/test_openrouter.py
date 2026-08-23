import json

import httpx
import pytest

from factory.llm import LLMUnavailable, OpenRouterClient, pick_scorer, pick_writer
from factory.moments import OpenRouterScorer
from factory.reaction import OpenRouterReactionWriter
from factory.transcribe import Segment

SEGMENTS = [
    Segment(100.0, 110.0, "Tu sais pourquoi 90% échouent ?"),
    Segment(110.0, 130.0, "Personne ne leur explique le modèle."),
    Segment(130.0, 141.0, "Voilà le secret."),
]


def make_client(reply: dict, captured: dict) -> OpenRouterClient:
    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        captured["auth"] = request.headers.get("authorization")
        return httpx.Response(200, json={
            "choices": [{"message": {"content": json.dumps(reply)}}]
        })

    return OpenRouterClient(
        api_key="sk-or-test", model="anthropic/claude-opus-5",
        transport=httpx.MockTransport(handler),
    )


def test_scorer_parses_and_postprocesses():
    captured = {}
    client = make_client({
        "moments": [
            {"start_s": 100.0, "end_s": 141.0, "title": "Le secret",
             "hook": 12.0, "emotion": 8.0, "autonomy": 8.5,
             "justification": "fort"},
            {"start_s": 0.0, "end_s": 4.0, "title": "trop court",
             "hook": 9, "emotion": 9, "autonomy": 9, "justification": "x"},
        ]
    }, captured)
    moments = OpenRouterScorer(client=client).find_moments(SEGMENTS, "fr", top_n=5)
    assert len(moments) == 1
    assert moments[0].hook == 10.0  # clampé /10
    body = captured["body"]
    assert body["model"] == "anthropic/claude-opus-5"
    assert body["response_format"]["json_schema"]["strict"] is True
    assert "[100.0–110.0]" in body["messages"][1]["content"]
    assert captured["auth"] == "Bearer sk-or-test"


def test_writer_builds_clamped_script():
    captured = {}
    client = make_client({
        "hook": " Écoute bien. ",
        "interruptions": [
            {"at_s": 500.0, "text": "clampée à la fin"},
            {"at_s": 10.0, "text": "première"},
            {"at_s": 20.0, "text": "au-delà de 2 → ignorée"},
        ],
        "outro": "Fin.",
    }, captured)
    script = OpenRouterReactionWriter(client=client).write(SEGMENTS, "fr", "Titre")
    assert script.hook == "Écoute bien."
    assert len(script.interruptions) == 2
    # triées, et la position clampée à la longueur du clip (41 s)
    assert script.interruptions[0].at_s == 10.0
    assert script.interruptions[1].at_s == pytest.approx(41.0)
    assert "Nova" in captured["body"]["messages"][0]["content"]


def test_client_requires_key(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    with pytest.raises(LLMUnavailable):
        OpenRouterClient(api_key=None).complete_json("s", "u", {})


def test_client_rejects_garbage_response():
    def handler(request):
        return httpx.Response(200, json={"choices": [{"message": {"content": "pas du json"}}]})

    client = OpenRouterClient(api_key="k", transport=httpx.MockTransport(handler))
    with pytest.raises(LLMUnavailable, match="inexploitable"):
        client.complete_json("s", "u", {})


def test_pick_prefers_anthropic_then_openrouter(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    with pytest.raises(LLMUnavailable):
        pick_scorer()
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-x")
    assert isinstance(pick_scorer(), OpenRouterScorer)
    assert isinstance(pick_writer(), OpenRouterReactionWriter)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-x")
    from factory.moments import ClaudeScorer

    assert isinstance(pick_scorer(), ClaudeScorer)
