import json
import logging
import os
import re
import sys
import fastmcp

from contextlib import ExitStack
from importlib import resources
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4
from pydantic import Field
from dotenv import load_dotenv
from fastmcp.server.providers.skills import SkillProvider
from starlette.requests import Request
from starlette.responses import JSONResponse

from ankify.anki.anki_deck_creator import AnkiDeckCreator
from ankify.llm.jinja2_prompt_formatter import PromptRenderer
from ankify.settings import (
    AWSProviderAccess,
    AzureProviderAccess,
    NoteType,
    ProviderAccessSettings,
    Text2SpeechSettings,
)
from ankify.tsv import read_from_string
from ankify.tts.tts_manager import TTSManager
from ankify.vocab_entry import VocabEntry


def _configure_logging_for_runtime(
    level: str | int = "INFO",
    logger: logging.Logger | None = None,
) -> None:
    # Rich terminal formatting is helpful locally but noisy in Lambda CloudWatch logs.
    fastmcp.settings.enable_rich_logging = not bool(
        os.environ.get("AWS_LAMBDA_FUNCTION_NAME")
    )
    fastmcp.utilities.logging.configure_logging(level=level, logger=logger)


logger = fastmcp.utilities.logging.get_logger(__name__)

# Configure the 'ankify' logger to use FastMCP's logging infrastructure
# so that logs from imported modules (tts_manager, anki_deck_creator, etc.) are visible
# fastmcp.utilities.logging.configure_logging(
#     level="INFO",
#     logger=logging.getLogger("ankify"),
# )

_configure_logging_for_runtime(
    level="INFO",
    logger=logging.getLogger("ankify"),
)

# Also apply to the main fastmcp logger
_configure_logging_for_runtime(
    level="INFO",
    logger=logging.getLogger("fastmcp"),
)

mcp = fastmcp.FastMCP(
    name="Ankify",
    instructions="Create Anki decks with TTS speech from arbitrary input",
    # website_url="https://github.com/AlexanderKazakov/ankify",
)

_resource_files = ExitStack()
_ankify_skill_path = _resource_files.enter_context(
    # Installed package resources are not guaranteed to already be filesystem paths.
    resources.as_file(
        resources.files("ankify.resources").joinpath(
            "skills",
            "anki-vocabulary-builder",
        )
    )
)
mcp.add_provider(
    SkillProvider(_ankify_skill_path, supporting_files="template"),
)

load_dotenv()

if os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):
    # Lambda: only /tmp is writable
    decks_directory = Path("/tmp/ankify")
else:
    # Local development
    decks_directory = Path("~/ankify").expanduser().resolve()
decks_directory.mkdir(parents=True, exist_ok=True)


def _upload_to_s3_if_lambda(local_path: Path) -> str:
    """Upload file to S3 if running in Lambda, otherwise return local file URI."""
    bucket = os.environ.get("ANKIFY_S3_BUCKET")
    if not bucket:
        return local_path.resolve().as_uri()

    import boto3

    region_name = os.environ.get("AWS_REGION", "eu-central-1")
    s3_client = boto3.client(
        "s3",
        # Important for presigned URLs to work
        # https://repost.aws/questions/QUbQp5wlMXTMOEdu8SZWzC7w/s3-presigned-url-doesn-t-work-from-newly-created-buckets
        region_name=region_name,
        endpoint_url=f"https://s3.{region_name}.amazonaws.com",
    )
    s3_key = f"decks/{local_path.name}"

    s3_client.upload_file(
        str(local_path),
        bucket,
        s3_key,
        ExtraArgs={"ContentType": "application/octet-stream"},
    )

    expiry = int(os.environ.get("ANKIFY_PRESIGNED_URL_EXPIRY", "86400"))
    presigned_url = s3_client.generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": s3_key},
        ExpiresIn=expiry,
    )

    logger.info("Uploaded deck to S3: %s", presigned_url)

    # Clean up local file after successful upload
    local_path.unlink(missing_ok=True)

    return presigned_url


def _get_azure_subscription_key() -> str | None:
    """Get Azure subscription key from Secrets Manager or environment variable."""
    # First check for Secrets Manager ARN (Lambda deployment)
    secret_arn = os.environ.get("ANKIFY_AZURE_SECRET_ARN")
    if secret_arn:
        import boto3

        client = boto3.client("secretsmanager")
        response = client.get_secret_value(SecretId=secret_arn)
        return response["SecretString"]
    # Fall back to direct environment variable (local execution)
    return os.getenv("ANKIFY__PROVIDERS__AZURE__SUBSCRIPTION_KEY")


azure_subscription_key = _get_azure_subscription_key()
if azure_subscription_key:
    tts_settings = Text2SpeechSettings(
        default_provider="azure",
    )
    provider_settings = ProviderAccessSettings(
        azure=AzureProviderAccess(
            subscription_key=azure_subscription_key,
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
        ),
    )
    logger.info("Using AWS TTS provider: %s", provider_settings.aws)
else:
    tts_settings = Text2SpeechSettings(
        default_provider="edge",
    )
    provider_settings = ProviderAccessSettings()
    logger.info("Using Edge TTS provider (as no AWS credentials found in env)")


@mcp.prompt(
    name="ankify",
    title="Create Ankify Vocabulary Table or Deck",
    description="Prompt to read and follow the packaged Ankify skill.",
)
def ankify() -> str:
    logger.info("Received PROMPT request: ankify")
    return """
Read and follow the Ankify skill at `skill://anki-vocabulary-builder/SKILL.md`.
"""


@mcp.prompt(
    title="Create Anki Deck",
    description="Prompt to create Anki deck file from the vocabulary table. "
    "The note type is deduced by the LLM automatically."
    "The table has to be already present in the chat at the time of the prompting.",
)
def deck(
    deck_name: str = Field(
        default="Ankify",
        description="Deck name (it's not the file name, it's the deck name within Anki)",
    ),
) -> str:
    logger.info(
        "Received PROMPT request: deck: deck_name '%s'",
        deck_name,
    )
    return f"""
Create Anki deck from the vocabulary table with the deck name: `{deck_name}`.
Use the MCP tool `convert_TSV_to_Anki_deck` for this.

If there are multiple vocabulary table versions in the chat, use the latest/actual/user-approved one.

Deduce the note type from the vocabulary table, the tool description, and the previous instructions.
If you are not sure, ask the user for the exact note type.

Always put a full valid explicit clickable URI of the generated .apkg file in your answer, 
not just the file name or path, even if the file is local. That URI is returned to you by the MCP tool.
"""


def _resolve_language_alias(language: str) -> str:
    language = language.lower()
    # todo - all these configs (and tts manager) should be kept as singletons
    aliases_content = (
        resources.files("ankify.resources")
        .joinpath("language_aliases.json")
        .read_text(encoding="utf-8")
    )
    aliases: dict[str, str] = json.loads(aliases_content)
    if language in aliases:
        return aliases[language]
    return language


def _resolve_instructions_for_language(language: str) -> str:
    instructions_path = resources.files(
        "ankify.resources.prompts.language_specific"
    ).joinpath(f"{language.lower()}.md")
    if instructions_path.is_file():
        return instructions_path.read_text(encoding="utf-8")
    return ""


@mcp.prompt(
    title="Create Vocabulary Table (universal parametrizable template)",
    description="""
Prompt to create vocabulary table in TSV format from the user input. 
The universal template, to be parametrized with languages, note type, and additional custom instructions. 

Languages can be specified quite flexibly like "English", "en", "ENG", "GE", "ger", "Rus", "russian", "Turkish", etc.

Note type can be specified quite flexibly like "ba" (Basic), "br" (Basic & Reversed), "basic", "basic_and_reversed", "basic and reversed", "basic & reversed", "Basic & Reversed", etc.
""",
)
def vocab(
    language_studied: str = Field(
        default="language_studied",
        description="The language being studied (front side). Accepts flexible formats: 'English', 'en', 'ENG', 'GE', 'ger', 'Rus', 'russian', 'Turkish', etc.",
    ),
    language_known: str = Field(
        default="language_known",
        description="The known language (back side). Accepts flexible formats: 'English', 'en', 'ENG', 'GE', 'ger', 'Rus', 'russian', 'Turkish', etc.",
    ),
    note_type: str = Field(
        default="br",
        description="Type of Anki notes: 'basic' (ba) for one card per note, 'basic_and_reversed' (br) for two cards per note. Accepts flexible formats including 'basic', 'basic_and_reversed', 'basic and reversed', 'basic & reversed', 'ba', 'br'.",
    ),
    custom_instructions: str = Field(
        default="",
        description="Optional additional instructions to customize vocabulary generation (e.g., focus on specific topics, style preferences).",
    ),
) -> str:
    logger.info(
        "Received PROMPT request: vocab: language_studied '%s', language_known '%s', note_type '%s'",
        language_studied,
        language_known,
        note_type,
    )

    note_type_raw = note_type.lower().strip()
    if note_type_raw == "ba":
        note_type = "basic"
    elif note_type_raw == "br":
        note_type = "basic_and_reversed"
    else:
        s = note_type_raw.replace("&", " and ")
        s = re.sub(r"[\s\-]+", "_", s)
        note_type = re.sub(r"_+", "_", s).strip("_")

    if note_type not in ("basic", "basic_and_reversed"):
        raise ValueError("Invalid note type")

    template_content = (
        resources.files("ankify.resources.prompts")
        .joinpath("mcp_prompt_template.md.j2")
        .read_text(encoding="utf-8")
    )
    language_studied = _resolve_language_alias(language_studied)
    language_known = _resolve_language_alias(language_known)
    language_studied_instructions = _resolve_instructions_for_language(language_studied)
    language_known_instructions = _resolve_instructions_for_language(language_known)

    return PromptRenderer.render(
        template_content=template_content,
        context={
            "language_studied": language_studied,
            "language_known": language_known,
            "note_type": note_type,
            "language_studied_instructions": language_studied_instructions,
            "language_known_instructions": language_known_instructions,
            "custom_instructions": custom_instructions,
        },
    )


@mcp.custom_route("/health", methods=["GET"])
async def health_check(request: Request):
    """Health check endpoint for Lambda Web Adapter."""
    return JSONResponse({"status": "healthy"})


@mcp.tool()
def convert_TSV_to_Anki_deck(
    tsv_vocabulary: str = Field(
        description="String with vocabulary table in TSV format"
    ),
    note_type: NoteType = Field(
        description="Type of Anki notes to create, exactly one of: basic_and_reversed or basic"
    ),
    deck_name: str = Field(
        description="Name of the Anki deck (it's not the file name, it's the deck name within Anki)"
    ),
) -> str:
    """
    Creates Anki deck (.apkg) from TSV vocabulary (string).

    IMPORTANT: Before calling this tool, read and follow skill://anki-vocabulary-builder/SKILL.md.
    DO NOT call the tool until you have read the skill!

    Important:
    - `tsv_vocabulary` - it supports only correctly formatted TSV strings!
    - `note_type` - attention should be paid to the proper choice of it!

    Args:

        tsv_vocabulary: string with vocabulary in TSV format:
            `front_text<tab>back_text<tab>front_language<tab>back_language<newline>...`

        note_type: type of Anki notes to create, exactly one of:
            - `basic_and_reversed` - two cards per note: forward and reversed
            - `basic` - one card per note: forward only

        deck_name: name of the Anki deck (it's not the file name, it's the deck name within Anki)

    Returns:
        URI of the generated .apkg file
    """
    logger.info(
        "Received TOOL request: convert_TSV_to_Anki_deck: note_type '%s', deck_name '%s'",
        note_type,
        deck_name,
    )

    try:
        vocab_entries: list[VocabEntry] = read_from_string(tsv_vocabulary)
    except Exception as e:
        msg = f"Failed to parse vocabulary TSV: {e}"
        logger.error(msg)
        raise ValueError(msg)

    with TemporaryDirectory(dir=decks_directory, prefix="media_") as audio_dir:
        synthesize_audio(vocab_entries, Path(audio_dir))
        output_file = package_anki_deck(
            vocab_entries, decks_directory, deck_name, note_type
        )

    return _upload_to_s3_if_lambda(output_file)


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
        creator = AnkiDeckCreator(
            output_file=output_file, deck_name=deck_name, note_type=note_type
        )
        creator.write_anki_deck(vocab_entries)
    except Exception as e:
        msg = f"Anki deck packaging failed: {e}"
        logger.error(msg)
        raise RuntimeError(msg)
    return output_file


def _prompt_result_text(result) -> str:
    # MCP prompt content can be a typed text block or a plain string, depending on client API.
    content = result.messages[0].content
    if hasattr(content, "text"):
        return content.text
    return str(content)


async def _test_vocab() -> None:
    prompts_to_render = {
        "vocab_en_ru_ba.md": {
            "language_studied": "English",
            "language_known": "Russian",
            "note_type": "basic",
        },
        "vocab_en_ru_br.md": {
            "language_studied": "eng",
            "language_known": "ru",
            "note_type": "basic and reversed",
            "custom_instructions": "Some custom instructions...",
        },
        "vocab_ge_en_br.md": {
            "language_studied": "ger",
            "language_known": "en",
            "note_type": "basic_and_reversed",
        },
        "vocab_ge_en_ba.md": {
            "language_studied": "de",
            "language_known": "eng",
            "note_type": "ba",
        },
        "vocab_ar_tr_br.md": {
            "language_studied": "ar",
            "language_known": "tr",
            "note_type": "br",
        },
    }

    async with fastmcp.Client(mcp) as client:
        for output_name, arguments in prompts_to_render.items():
            result = await client.get_prompt("vocab", arguments)
            Path("tmp", output_name).write_text(
                _prompt_result_text(result),
                encoding="utf-8",
            )


async def _test_convert_TSV_to_Anki_deck() -> None:
    async with fastmcp.Client(mcp) as client:
        result = await client.call_tool(
            "convert_TSV_to_Anki_deck",
            {
                "tsv_vocabulary": """Hello World!\tHallo Welt!\tEng\tGe
Как дела?\t¿Cómo estás?\tRus\tSpanish
كم تبلغ من العمر؟\t你今年多大\tArabic\tChinese""",
                "note_type": "basic_and_reversed",
                "deck_name": "Ankify Test Deck",
            },
        )
    logger.info("Ankify Test Deck: %s", result.data or result.content[0].text)


async def _test_all() -> None:
    await _test_vocab()
    await _test_convert_TSV_to_Anki_deck()


if __name__ == "__main__":
    # import asyncio
    # asyncio.run(_test_all())

    # Local (stdio) MCP mode
    mcp.run(transport="stdio")
    sys.exit(0)


# ASGI app for uvicorn (used in Docker with Lambda Web Adapter)
# About parameters see docs/mcp-http-transport-options.md
app = mcp.http_app(
    stateless_http=True,
    json_response=True,
)
