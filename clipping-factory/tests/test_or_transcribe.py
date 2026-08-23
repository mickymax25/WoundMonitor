import json
import subprocess

import httpx
import pytest

from factory.llm import OpenRouterClient
from factory.transcribe import OpenRouterTranscriber


def make_audio(path, duration):
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
         "-i", f"sine=frequency=440:duration={duration}", str(path)],
        check=True,
    )
    return path


def test_split_offsets(tmp_path):
    audio = make_audio(tmp_path / "src.wav", 65)
    from types import SimpleNamespace

    tr = OpenRouterTranscriber(client=SimpleNamespace(model="stub"), chunk_s=30)
    chunks = tr._split(audio)
    assert len(chunks) == 3
    offsets = [o for _, o in chunks]
    assert offsets[0] == 0.0
    assert offsets[1] == pytest.approx(30.0, abs=1.0)
    assert offsets[2] == pytest.approx(60.0, abs=1.5)


def test_transcribe_offsets_and_multimodal_payload(tmp_path):
    audio = make_audio(tmp_path / "src.wav", 65)
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        calls.append(body)
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(
            {"segments": [{"start": 1.0, "end": 5.0, "text": f"chunk {len(calls)}"},
                          {"start": 6.0, "end": 9.0, "text": "  "}]}
        )}}]})

    client = OpenRouterClient(
        api_key="k", model="google/gemini-3.7-flash",
        transport=httpx.MockTransport(handler),
    )
    tr = OpenRouterTranscriber(client=client, chunk_s=30)
    segments = tr.transcribe(audio)

    assert len(calls) == 3
    parts = calls[0]["messages"][1]["content"]
    assert parts[1]["type"] == "input_audio"
    assert parts[1]["input_audio"]["format"] == "mp3"
    # segments vides filtrés, offsets appliqués par tranche
    assert [s.text for s in segments] == ["chunk 1", "chunk 2", "chunk 3"]
    assert segments[1].start == pytest.approx(31.0, abs=1.0)
    assert segments[2].start == pytest.approx(61.0, abs=1.5)
