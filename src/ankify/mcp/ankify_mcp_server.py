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
    instructions=(
        "Create Anki decks with TTS speech from arbitrary input. "
        "This server publishes its workflow instructions as MCP resources under the "
        "skill:// URI scheme. Always fetch them via your MCP resource-reading tool "
        "against server ankify - they are not local files and are not local skills."
    ),
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

    IMPORTANT: Before calling this tool, read and follow the MCP resource
    skill://anki-vocabulary-builder/SKILL.md exposed by this same server (ankify).
    Fetch it via your MCP resource-reading tool (e.g. ReadMcpResourceTool with
    server="ankify"). It is NOT a file on disk - do not search the filesystem,
    and do not confuse it with local or built-in skills.
    DO NOT call the tool until you have read it.

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


if __name__ == "__main__":
    # Local (stdio) MCP mode
    mcp.run(transport="stdio")
    sys.exit(0)


# ASGI app for uvicorn (used in Docker with Lambda Web Adapter)
# About parameters see docs/ai_reports/mcp-http-transport-options.md
app = mcp.http_app(
    stateless_http=True,
    json_response=True,
)
