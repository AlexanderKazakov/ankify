# Ankify

Create Anki decks with text-to-speech audio from arbitrary input using LLM and TTS services.

## Features

- **MCP Server**: Use with any MCP-compatible AI client, locally or in the cloud. No need for any API keys
- **Agent Skill**: `src/ankify/resources/skills/anki-vocabulary-builder/` - the standard `SKILL.md`-format folder you can copy to your agent's skills
- **CLI**: Standalone command-line tool, uses LLM through openai-compatible API
- **Multi-language TTS**: Azure, AWS Polly, and free Edge TTS support
- **Customizable prompts**: Curated vocabulary creation prompt templates for any language pair and note type with few-shot examples and custom instructions
- **Packed to Anki**: The resulting `.apkg` file is to be opened in Anki.

If the deck name in settings is equal to the name of an existing deck in your Anki, it will be loaded directly into the existing deck. Clarification of possible notes types: see [docs/Anki_note_types.md](docs/Anki_note_types.md).

## Installation

```bash
git clone https://github.com/AlexanderKazakov/ankify.git
cd ankify
uv venv --python 3.12
```

### Local MCP Server

For local MCP server with free Edge TTS:

```bash
uv pip install -e .[local-mcp]
```

### Local CLI Application (minimal installation)

For local CLI application with free Edge TTS:

```bash
uv pip install -e .[local-cli]
```

### Full Local (CLI + MCP + All TTS)

For all the features including CLI and all TTS providers:

```bash
uv pip install -e .[local-all]
```

### AWS Lambda Deployment

See [infra/README.md](infra/README.md) for deployment instructions.

### Development

```bash
uv pip install -e .[local-all,dev]
```

#### Tests
Run all tests:
```bash
uv run pytest
```

The full TTS provider test (`tests/unit/tts/test_tts_providers.py`) generates MP3
audio and asks Azure Speech-to-Text to transcribe it back. Azure Speech SDK needs
GStreamer at runtime to read compressed audio such as MP3. Microsoft documents
this compressed-audio GStreamer setup for Linux and Windows:
https://learn.microsoft.com/azure/ai-services/speech-service/how-to-use-codec-compressed-audio-input-streams

Install GStreamer before running those tests on Linux:

```bash
# Ubuntu/Debian
sudo apt-get install -y libgstreamer1.0-0 gstreamer1.0-plugins-base gstreamer1.0-plugins-good gstreamer1.0-plugins-bad gstreamer1.0-plugins-ugly
```

CI already installs GStreamer before running the full test suite. On macOS,
Homebrew GStreamer can be installed and still not be visible to Azure Speech SDK
for compressed MP3 input, so run the full TTS provider test in Linux/CI only,
TTS tests do not work on Mac for now.

Run a single test directory, file, or test:
```bash
uv run pytest tests/path/to/test_directory -v
uv run pytest tests/path/to/test_file.py -v
uv run pytest tests/path/to/test_file.py::test_name -v
```

#### Linter
```bash
uv run ruff check src/
```


## MCP Server

Ankify provides an MCP server for integration with LLM clients.

### Local MCP Server

Add to your MCP client (Claude Desktop, Cursor, etc.) configuration:

```json
{
  "mcpServers": {
    "ankify": {
      "command": "uv",
      "args": [
        "--directory",
        "/path/to/ankify",
        "run",
        "python",
        "-m",
        "ankify.mcp.ankify_mcp_server"
      ]
    }
  }
}
```

### AWS Deployment

Deploy to AWS Lambda for hosted MCP access. See [infra/README.md](infra/README.md) for instructions.

### MCP Tools & Prompts

**Prompts:**

- `vocab` - Create vocabulary table (universal template for any language pair, note type, custom instructions)
- `deck` - Create Anki deck from vocabulary table (instructs AI to use the conversion tool properly)

**Tools:**

- `convert_TSV_to_Anki_deck` - Convert TSV vocabulary to .apkg file

## TTS Providers

| Provider  | Package                            | Cost             | Notes                                                                              |
| --------- | ---------------------------------- | ---------------- | ---------------------------------------------------------------------------------- |
| Azure     | `azure-cognitiveservices-speech` | Paid (free tier) | The broadest language support. Good quality. "Neural" engines only.               |
| AWS Polly | `boto3`                          | Paid (free tier) | Good quality for "Neural" engine. Worse for languages with "Standard" engine only. |
| Edge      | `edge-tts`                       | Free             | Good quality, same to Azure. May rate-limit, but usually enough for local usage.   |

From my (limited to English, German, and Russian) experience, all "Neural" engines create good enough pronunciation in 99.9% cases and good for learning. "Standard" engines are a bit worse and OK for native speakers to understand, but not good enough to learn a foreign language pronunciation. But "Standard" engines are only on AWS, so it's quite unlikely you'll use them anyway, while all the default options use providers with "Neural" engines.

Install specific providers:

```bash
uv pip install -e .[tts-azure]
uv pip install -e .[tts-aws]
uv pip install -e .[tts-edge]
```

## CLI

For CLI usage documentation, see [docs/CLI.md](docs/CLI.md).

## Environment Variables

Provider credentials can be set via environment variables or `.env` file, see `.env.example`.

## License

MIT
