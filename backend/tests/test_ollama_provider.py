"""OllamaProvider against a fake HTTP transport: checks the request and response mapping."""

import json

import httpx
import pytest

from app.config import Settings
from app.providers.ollama import OllamaProvider


def make_provider(handler: httpx.MockTransport) -> OllamaProvider:
    settings = Settings(_env_file=None, provider="ollama", embedding_dim=3)
    return OllamaProvider(settings, transport=handler)


async def test_embed_adds_task_prefixes_and_normalizes() -> None:
    seen: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content))
        return httpx.Response(200, json={"embeddings": [[3.0, 4.0, 0.0]], "prompt_eval_count": 7})

    provider = make_provider(httpx.MockTransport(handler))
    documents = await provider.embed(["battery"])
    await provider.embed(["battery"], for_query=True)

    assert documents.vectors == [[0.6, 0.8, 0.0]]
    assert documents.usage.input_tokens == 7
    assert seen[0]["input"] == ["search_document: battery"]
    assert seen[1]["input"] == ["search_query: battery"]


async def test_embed_rejects_a_model_with_the_wrong_dimension() -> None:
    transport = httpx.MockTransport(
        lambda _request: httpx.Response(200, json={"embeddings": [[1.0, 0.0]]})
    )
    with pytest.raises(RuntimeError, match="2 dimensions"):
        await make_provider(transport).embed(["x"])


async def test_generate_maps_text_and_usage() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["stream"] is False
        assert [m["role"] for m in body["messages"]] == ["system", "user"]
        return httpx.Response(
            200,
            json={"message": {"content": "hi"}, "prompt_eval_count": 12, "eval_count": 3},
        )

    completion = await make_provider(httpx.MockTransport(handler)).generate("sys", "prompt")
    assert completion.text == "hi"
    assert (completion.usage.input_tokens, completion.usage.output_tokens) == (12, 3)


async def test_stream_yields_text_then_usage_from_ndjson() -> None:
    lines = [
        {"message": {"content": "Flies "}, "done": False},
        {"message": {"content": "42 minutes [1]."}, "done": False},
        {"message": {"content": ""}, "done": True, "prompt_eval_count": 50, "eval_count": 9},
    ]
    payload = "\n".join(json.dumps(line) for line in lines) + "\n"
    transport = httpx.MockTransport(lambda _request: httpx.Response(200, text=payload))

    chunks = [chunk async for chunk in make_provider(transport).stream("sys", "prompt")]
    assert "".join(c.text for c in chunks) == "Flies 42 minutes [1]."
    assert chunks[-1].usage is not None
    assert chunks[-1].usage.output_tokens == 9


async def test_http_errors_are_raised_not_swallowed() -> None:
    transport = httpx.MockTransport(lambda _request: httpx.Response(404, json={"error": "nope"}))
    with pytest.raises(httpx.HTTPStatusError):
        await make_provider(transport).generate("sys", "prompt")
