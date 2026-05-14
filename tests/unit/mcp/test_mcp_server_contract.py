import importlib
from pathlib import Path

import pytest
from fastmcp import Client


@pytest.fixture
def mcp_server(monkeypatch):
    # Keep tests from creating a local deck directory in the developer's home folder.
    monkeypatch.setenv("AWS_LAMBDA_FUNCTION_NAME", "pytest")
    return importlib.import_module("ankify.mcp.ankify_mcp_server")


def _prompt_text(result) -> str:
    content = result.messages[0].content
    if hasattr(content, "text"):
        return content.text
    return str(content)


@pytest.mark.asyncio
async def test_public_prompts_are_registered(mcp_server):
    async with Client(mcp_server.mcp) as client:
        prompts = await client.list_prompts()

    prompt_names = {prompt.name for prompt in prompts}

    assert "deck" in prompt_names
    assert "vocab" in prompt_names


@pytest.mark.asyncio
async def test_deck_prompt_uses_default_deck_name(mcp_server):
    async with Client(mcp_server.mcp) as client:
        result = await client.get_prompt("deck", {})

    text = _prompt_text(result)

    assert "`Ankify`" in text
    assert "FieldInfo" not in text
    assert "annotation=NoneType" not in text


@pytest.mark.asyncio
async def test_vocab_prompt_uses_real_default_values(mcp_server):
    async with Client(mcp_server.mcp) as client:
        result = await client.get_prompt("vocab", {})

    text = _prompt_text(result)

    assert "language_studied" in text
    assert "language_known" in text
    assert "The dictionary is one-way." in text
    assert "FieldInfo" not in text
    assert "annotation=NoneType" not in text


@pytest.mark.asyncio
async def test_public_tool_is_registered(mcp_server):
    async with Client(mcp_server.mcp) as client:
        tools = await client.list_tools()

    tool_names = {tool.name for tool in tools}

    assert "convert_TSV_to_Anki_deck" in tool_names


@pytest.mark.asyncio
async def test_convert_tool_returns_uploaded_deck_uri(mcp_server, monkeypatch, tmp_path):
    captured_vocab_count = 0
    captured_deck_name = ""
    captured_note_type = ""

    def fake_synthesize_audio(vocab_entries, audio_dir: Path) -> None:
        nonlocal captured_vocab_count
        captured_vocab_count = len(vocab_entries)
        assert audio_dir.exists()

    def fake_package_anki_deck(
        vocab_entries,
        decks_directory: Path,
        deck_name: str,
        note_type: str,
    ) -> Path:
        nonlocal captured_deck_name, captured_note_type
        captured_deck_name = deck_name
        captured_note_type = note_type
        assert len(vocab_entries) == captured_vocab_count
        assert decks_directory == tmp_path
        return tmp_path / "deck.apkg"

    def fake_upload_to_s3_if_lambda(local_path: Path) -> str:
        assert local_path == tmp_path / "deck.apkg"
        return "file:///tmp/deck.apkg"

    monkeypatch.setattr(mcp_server, "decks_directory", tmp_path)
    monkeypatch.setattr(mcp_server, "synthesize_audio", fake_synthesize_audio)
    monkeypatch.setattr(mcp_server, "package_anki_deck", fake_package_anki_deck)
    monkeypatch.setattr(
        mcp_server,
        "_upload_to_s3_if_lambda",
        fake_upload_to_s3_if_lambda,
    )

    async with Client(mcp_server.mcp) as client:
        result = await client.call_tool(
            "convert_TSV_to_Anki_deck",
            {
                "tsv_vocabulary": "Hello\tHallo\tEnglish\tGerman",
                "note_type": "basic",
                "deck_name": "Contract Test Deck",
            },
        )

    assert result.data == "file:///tmp/deck.apkg"
    assert captured_vocab_count == 1
    assert captured_deck_name == "Contract Test Deck"
    assert captured_note_type == "basic"
