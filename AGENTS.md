# Ankify - AI Coding Agent Guide


## Project Overview

Ankify converts arbitrary text into Anki vocabulary decks with text-to-speech audio. It operates as both a CLI tool and an MCP (both local and http on AWS) server.

**Data flow:** Input Text → LLM → Vocabulary Table (TSV) → TTS → Audio Files → Anki Deck (.apkg)

### Components

- **MCP Server** (`src/ankify/mcp/`) - FastMCP server exposing prompts and tools to AI clients
- **TTS** (`src/ankify/tts/`) - `TTSManager` orchestrating Azure, AWS Polly, and Edge TTS providers
- **Anki** (`src/ankify/anki/`) - Deck creation with `genanki`
- **Pipeline** (`src/ankify/pipeline.py`) - Main CLI orchestrator coordinating LLM vocabulary generation, TTS, and Anki packaging
- **Settings** (`src/ankify/settings.py`) - Pydantic configuration
- **LLM** (`src/ankify/llm/`) - `OpenAIClient` implementation (for CLI only); Jinja2 prompt templating
- **Deployment** (`infra/`) - CDK infrastructure as code for AWS deployment

## Development Commands

**All Python tools must be run through `uv run` to ensure the virtual environment is properly activated.** Never invoke `python`, `pytest`, `ruff`, `pip`, or anything like that without uv.

```bash
# Install for development
uv pip install -e ".[local-all,dev]"

# Sync dependencies from lockfile
uv sync --all-extras

# Linting and formatting
uv run ruff check src/
uv run ruff format src/

# All Tests (you most probably don't need to run all tests, see below)
uv run pytest

## Fast Tests (if you haven't touched TTS code, skip the TTS tests)
uv run python -m pytest tests/ --ignore=tests/unit/tts/test_tts_providers.py
```

## Rules

### Permissions & Automation

- **Python, pip, tests, etc. execution:** Only through `uv run` or `uv pip`. Direct `python`, `pip`, `pytest`, `ruff`, etc. calls are denied.
- **File operations:** No `rm`, `mv`, `rmdir`, `chmod`, `chown`. Use `mkdir`, `cp`, `touch` freely. Use the `Edit`/`Write` / `MultiEdit` / etc. tools for file content changes.
- **Git:** Read-only. No commits, pushes, checkouts, merges, rebases, or any state-changing operations.
- **AWS/CDK:** Read-only. Inspect with `aws ... list-*`, `aws ... get-*`, `aws ... describe-*`, etc. Use `cdk synth` and `cdk diff` for validation. No `cdk deploy`, no S3 writes, no Lambda updates, etc.
- **Docker:** Build and inspect only. No `docker run`, `docker push`, or container/image management.

### Environment Variables

Only use environment variable with prefix and style: `ANKIFY__` (double underscore for nesting, see `.env.example`). Do not use any other conventional environment variables like `OPENAI_API_KEY`, `AWS_SECRET_ACCESS_KEY`, `AZURE_SUBSCRIPTION_KEY`, `AWS_REGION` etc. Do not invent your own environment variable names.

Default AWS region is `eu-central-1`. Default Azure region is `westeurope`. Better avoid specifying defaults where possible.

### Key Patterns

- Lazy loading of provider libraries (allows partial installations)
- Use modern Python typing: `list[str]` not `List[str]`
- Use relative imports: `from ..logging import get_logger`
- All files you read and write must use UTF-8 encoding
- No `from __future__ import ...`
- Handle errors gracefully; use `tenacity` for connection retries, when appropriate
- Respect library choices in `pyproject.toml`

## Workflow

Always when you substantially change the code:

- mind the existing tests (and adjust them if you change behavior)
- write new tests covering new functionality
- run all relevant tests to check everything works as expected
- do not stop until all the tests pass and you're sure about what you've done
