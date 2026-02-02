import json
import logging
import os
import re
import fastmcp

from importlib import resources
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4
from typing import Any
from pydantic import Field
from pydantic.fields import FieldInfo
from dotenv import load_dotenv

from ankify.anki.anki_deck_creator import AnkiDeckCreator
from ankify.llm.jinja2_prompt_formatter import PromptRenderer
from ankify.settings import AWSProviderAccess, AzureProviderAccess, NoteType, ProviderAccessSettings, Text2SpeechSettings
from ankify.tsv import read_from_string
from ankify.tts.tts_manager import TTSManager
from ankify.vocab_entry import VocabEntry


logger = fastmcp.utilities.logging.get_logger(__name__)

# Configure the 'ankify' logger to use FastMCP's logging infrastructure
# so that logs from imported modules (tts_manager, anki_deck_creator, etc.) are visible
fastmcp.utilities.logging.configure_logging(
    level="INFO",
    logger=logging.getLogger("ankify"),
)

mcp = fastmcp.FastMCP(
    name="Ankify",
    instructions="Create Anki decks with TTS speech from arbitrary input",
    # website_url="https://github.com/AlexanderKazakov/ankify",
)

load_dotenv()

decks_directory = Path("~/ankify").expanduser().resolve()
decks_directory.mkdir(parents=True, exist_ok=True)

if os.getenv("ANKIFY__PROVIDERS__AZURE__SUBSCRIPTION_KEY"):
    tts_settings = Text2SpeechSettings(
        default_provider="azure",
    )
    provider_settings = ProviderAccessSettings(
        azure=AzureProviderAccess(
            subscription_key=os.getenv("ANKIFY__PROVIDERS__AZURE__SUBSCRIPTION_KEY"),
            region=os.getenv("ANKIFY__PROVIDERS__AZURE__REGION"),
        ),
    )
    logger.info("Using Azure TTS provider: %s", provider_settings.azure)
elif os.getenv("ANKIFY__PROVIDERS__AWS__ACCESS_KEY_ID"):
    tts_settings = Text2SpeechSettings(
        default_provider="aws",
    )
    provider_settings = ProviderAccessSettings(
        aws=AWSProviderAccess(
            access_key_id=os.getenv("ANKIFY__PROVIDERS__AWS__ACCESS_KEY_ID"),
            secret_access_key=os.getenv("ANKIFY__PROVIDERS__AWS__SECRET_ACCESS_KEY"),
            region=os.getenv("ANKIFY__PROVIDERS__AWS__REGION"),
        ),
    )
    logger.info("Using AWS TTS provider: %s", provider_settings.aws)
else:
    tts_settings = Text2SpeechSettings(
        default_provider="edge",
    )
    provider_settings = ProviderAccessSettings()
    logger.info("Using Edge TTS provider (as no AWS credentials found in env)")


def _fix_field_default_fastmcp_bug(value: Any) -> Any:
    if isinstance(value, FieldInfo):
        return value.default
    return value


def _deck_prompt(note_type: NoteType | str, deck_name: str) -> str:
    deck_name = _fix_field_default_fastmcp_bug(deck_name)
    return f"""
Create Anki deck from the vocabulary table with the note type: `{note_type}` and deck name: `{deck_name}`.
Use the MCP tool `convert_TSV_to_Anki_deck` for this.
If there are multiple vocabulary table versions in the chat, use the latest/actual/user-approved one.
Always put a full valid explicit clickable URI of the generated .apkg file in your answer, not just the file name or path, even if the file is local. That URI is returned to you by the MCP tool.
"""


@mcp.prompt(
        title="Create Anki Deck",
        description="Prompt to create Anki deck file from the vocabulary table. "
                "The note type is deduced by the LLM automatically. Use 'deck_fo' and 'deck_fb' prompts for explicit note type choices."
                "The table has to be already present in the chat at the time of the prompt.",
)
def deck(
        deck_name: str = Field(
            default="Ankify",
            description="Deck name (it's not the file name, it's the deck name within Anki)"
        ),
) -> str:
    basic_prompt = _deck_prompt(note_type='<choose it yourself intelligently>', deck_name=deck_name)
    note_type_instructions = f"""
Deduce the note type from the vocabulary table, the tool description, and the previous instructions.
If you are not sure, ask the user for the exact note type, and mention that there are explicit prompt shortcuts: 'deck_fo' and 'deck_fb'.
"""
    return f"{basic_prompt}\n{note_type_instructions}"


@mcp.prompt(
        title="Create Anki Deck with Forward-Only notes",
        description="Prompt to create Anki deck file with 'forward_only' notes from the vocabulary table. "
                "The table has to be already present in the chat at the time of the prompt.",
)
def deck_fo(
        deck_name: str = Field(
            default="Ankify",
            description="Deck name (it's not the file name, it's the deck name within Anki)",
        )
) -> str:
    return _deck_prompt(note_type="forward_only", deck_name=deck_name)


@mcp.prompt(
        title="Create Anki Deck with Forward-and-Backward notes",
        description="Prompt to create Anki deck file with 'forward_and_backward' notes from the vocabulary table. "
                "The table has to be already present in the chat at the time of the prompt.",
)
def deck_fb(
        deck_name: str = Field(
            default="Ankify",
            description="Deck name (it's not the file name, it's the deck name within Anki)",
        )
) -> str:
    return _deck_prompt(note_type="forward_and_backward", deck_name=deck_name)


def _resolve_language_alias(language: str) -> str:
    language = language.lower()
    # todo - all these configs (and tts manager) should be kept as singletons
    aliases_content = resources.files("ankify.resources").joinpath("language_aliases.json").read_text(encoding="utf-8")
    aliases: dict[str, str] = json.loads(aliases_content)
    if language in aliases:
        return aliases[language]
    return language


def _resolve_instructions_for_language(language: str) -> str:
    instructions_path = resources.files("ankify.resources.prompts.language_specific").joinpath(f"{language.lower()}.md")
    if instructions_path.is_file():
        return instructions_path.read_text(encoding="utf-8")
    return ""


def _vocab_prompt(
        language_a: str,
        language_b: str,
        note_type: str,
        custom_instructions: str = "",
) -> str:
    language_a = _fix_field_default_fastmcp_bug(language_a)
    language_b = _fix_field_default_fastmcp_bug(language_b)
    note_type = _fix_field_default_fastmcp_bug(note_type)
    custom_instructions = _fix_field_default_fastmcp_bug(custom_instructions)

    if note_type == "fo":
        note_type = "forward_only"
    elif note_type == "fb":
        note_type = "forward_and_backward"
    else:
        note_type = note_type.lower().strip().replace(" ", "_").replace("-", "_")

    if note_type not in ["forward_only", "forward_and_backward"]:
        raise ValueError("Invalid note type")
    
    template_content = resources.files("ankify.resources.prompts").joinpath("mcp_prompt_template.md.j2").read_text(encoding="utf-8")
    language_a = _resolve_language_alias(language_a)
    language_b = _resolve_language_alias(language_b)
    language_a_instructions = _resolve_instructions_for_language(language_a)
    language_b_instructions = _resolve_instructions_for_language(language_b)

    return PromptRenderer.render(
        template_content=template_content,
        context={
            "language_a": language_a,
            "language_b": language_b,
            "note_type": note_type,
            "language_a_instructions": language_a_instructions,
            "language_b_instructions": language_b_instructions,
            "custom_instructions": custom_instructions,
        }
    )


@mcp.prompt(
        title="Create Vocabulary Table (universal parametrizable template)",
        description="""
Prompt to create vocabulary table in TSV format from the user input. 
The universal template, to be parametrized with languages, note type, and additional custom instructions. 
'language_a' is the language being studied, 'language_b' is the known language, any language is supported.

Languages can be specified quite flexibly like "English", "en", "ENG", "GE", "ger", "Rus", "russian", "Turkish", etc.

Note type can be specified quite flexibly like "fo" (forward only), "fb" (forward and backward), "forward only", "Forward and backward", "forward-only", "forward-and-backward", "forward_only", "forward_and_backward".
""",
)
def vocab(
        language_a: str = Field(
            default="language_a",
            description="The language being studied (front side). Accepts flexible formats: 'English', 'en', 'ENG', 'GE', 'ger', 'Rus', 'russian', 'Turkish', etc.",
        ),
        language_b: str = Field(
            default="language_b",
            description="The known language (back side). Accepts flexible formats: 'English', 'en', 'ENG', 'GE', 'ger', 'Rus', 'russian', 'Turkish', etc.",
        ),
        note_type: str = Field(
            default="fb",
            description="Type of Anki notes: 'forward_only' (fo) for one card per note, 'forward_and_backward' (fb) for two cards per note. Accepts flexible formats: 'fo', 'fb', 'forward_only', 'forward_and_backward', 'Forward only', 'Forward and backward', 'forward-only', 'forward-and-backward', 'forward_only', 'forward_and_backward'.",
        ),
        custom_instructions: str = Field(
            default="",
            description="Optional additional instructions to customize vocabulary generation (e.g., focus on specific topics, style preferences).",
        ),
) -> str:
    return _vocab_prompt(language_a=language_a, language_b=language_b, note_type=note_type, custom_instructions=custom_instructions)


@mcp.prompt(
        title="Create Vocabulary Table (English-Russian, forward-only notes)",
        description="Shortcut for 'vocab' with language_a='English', language_b='Russian', note_type='forward_only'",
)
def vocab_en_ru_fo() -> str:
    return _vocab_prompt(language_a="English", language_b="Russian", note_type="forward_only")


@mcp.prompt(
        title="Create Vocabulary Table (German-English, forward-and-backward notes)",
        description="Shortcut for 'vocab' with language_a='German', language_b='English', note_type='forward_and_backward'",
)
def vocab_ge_en_fb() -> str:
    return _vocab_prompt(language_a="German", language_b="English", note_type="forward_and_backward")


@mcp.tool()
def convert_TSV_to_Anki_deck(
    tsv_vocabulary: str = Field(description="String with vocabulary table in TSV format"),
    note_type: NoteType = Field(description="Type of Anki notes to create, exactly one of: forward_and_backward or forward_only"),
    deck_name: str = Field(description="Name of the Anki deck (it's not the file name, it's the deck name within Anki)"),
) -> str:
    """
    Creates Anki deck (.apkg) from TSV vocabulary (string).

    Important:
    - `tsv_vocabulary` - it supports only correctly formatted TSV strings!
    - `note_type` - attention should be paid to the proper choice of it!
    
    Args:

        tsv_vocabulary: string with vocabulary in TSV format: 
            `front_text<tab>back_text<tab>front_language<tab>back_language<newline>...`
        
        note_type: type of Anki notes to create, exactly one of: 
            - `forward_and_backward` - two cards per note: forward and backward
            - `forward_only` - one card per note: forward only
        
        deck_name: name of the Anki deck (it's not the file name, it's the deck name within Anki)
    
    Returns:
        URI of the generated .apkg file
    """
    logger.info("Received request to create deck '%s' with note_type '%s'", deck_name, note_type)
    
    try:
        vocab_entries: list[VocabEntry] = read_from_string(tsv_vocabulary)
    except Exception as e:
        msg = f"Failed to parse vocabulary TSV: {e}"
        logger.error(msg)
        raise ValueError(msg)

    with TemporaryDirectory(dir=decks_directory, prefix="media_") as audio_dir:
        synthesize_audio(vocab_entries, Path(audio_dir))
        output_file = package_anki_deck(vocab_entries, decks_directory, deck_name, note_type)
        
    return output_file.resolve().as_uri()


def synthesize_audio(vocab_entries: list[VocabEntry], audio_dir: Path) -> None:
    logger.info("Synthesizing audio to %s", audio_dir)
    try:
        tts_manager = TTSManager(
            tts_settings=tts_settings,
            provider_settings=provider_settings,
        )
        tts_manager.synthesize(vocab_entries, audio_dir)
    except Exception as e:
        msg = f"TTS synthesis failed: {e}"
        logger.error(msg)
        raise RuntimeError(msg)


def package_anki_deck(
    vocab_entries: list[VocabEntry], 
    decks_directory: Path, 
    deck_name: str, 
    note_type: NoteType,
) -> Path:
    safe_deck_name = re.sub(r"\s+", "_", deck_name)
    safe_deck_name = re.sub(r"[^a-zA-Z0-9_-]", "", safe_deck_name)
    if not safe_deck_name:
        safe_deck_name = "Ankify"
    output_file = decks_directory / f"{safe_deck_name}-{uuid4()}.apkg"
    logger.info("Packaging Anki deck to %s", output_file)
    try:
        creator = AnkiDeckCreator(output_file=output_file, deck_name=deck_name, note_type=note_type)
        creator.write_anki_deck(vocab_entries)
    except Exception as e:
        msg = f"Anki deck packaging failed: {e}"
        logger.error(msg)
        raise RuntimeError(msg)
    return output_file


async def _test_vocab() -> None:
    with open("tmp/vocab_en_ru_fo.md", "w", encoding="utf-8") as f:
        f.write((await vocab_en_ru_fo.render())[0].content.text)
    with open("tmp/vocab_en_ru_fb.md", "w", encoding="utf-8") as f:
        f.write((await vocab.render({"language_a": "en", "language_b": "ru", "note_type": "forward and backward", "custom_instructions": "Some custom instructions..."}))[0].content.text)
    with open("tmp/vocab_ge_en_fb.md", "w", encoding="utf-8") as f:
        f.write((await vocab_ge_en_fb.render())[0].content.text)
    with open("tmp/vocab_ge_en_fo.md", "w", encoding="utf-8") as f:
        f.write((await vocab.render({"language_a": "de", "language_b": "eng", "note_type": "fo"}))[0].content.text)
    with open("tmp/vocab_ar_tr_fb.md", "w", encoding="utf-8") as f:
        f.write((await vocab.render({"language_a": "ar", "language_b": "tr", "note_type": "fb"}))[0].content.text)


async def _test_convert_TSV_to_Anki_deck() -> None:
    result = await convert_TSV_to_Anki_deck.run({
        "tsv_vocabulary": """Hello World!\tHallo Welt!\tEng\tGe
Как дела?\t¿Cómo estás?\tRus\tSpanish
كم تبلغ من العمر؟\t你今年多大\tArabic\tChinese""",
        "note_type": "forward_and_backward",
        "deck_name": "Ankify Test Deck",
    })
    logger.info("Ankify Test Deck: %s", result.content[0].text)


async def _test_all() -> None:
    await _test_vocab()
    await _test_convert_TSV_to_Anki_deck()


if __name__ == "__main__":
    # import asyncio
    # asyncio.run(_test_all())

    mcp.run(transport="stdio")

