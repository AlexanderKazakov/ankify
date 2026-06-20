# Ankify

Create Anki decks with text-to-speech audio from a vocabulary table.

Ankify runs as an MCP server. An MCP-compatible AI client builds the vocabulary
table by following the packaged skill, then calls a single tool that synthesizes
the audio and packages everything into an Anki `.apkg` file.

## Features

- **MCP Server**: Use with any MCP-compatible AI client, locally or in the cloud. No need for any API keys for local usage with free Edge TTS.
- **Agent Skill**: `src/ankify/resources/skills/anki-vocabulary-builder/` - a standard `SKILL.md`-format folder. It is exposed by the MCP server as a resource (`skill://anki-vocabulary-builder/SKILL.md`) and can also be copied directly into your agent's skills.
- **One tool**: `convert_TSV_to_Anki_deck` - converts a TSV vocabulary table into an Anki `.apkg` file with TTS audio.
- **Multi-language TTS**: Azure, AWS Polly, and free Edge TTS support.
- **Packed to Anki**: The resulting `.apkg` file is to be opened in Anki.

If the deck name is equal to the name of an existing deck in your Anki, it will be loaded directly into the existing deck. Clarification of possible note types: see [docs/Anki_note_types.md](docs/Anki_note_types.md). On the order of new cards, see [docs/Anki_new_card_order.md](docs/Anki_new_card_order.md).

## Installation

```bash
git clone https://github.com/AlexanderKazakov/ankify.git
cd ankify
uv venv --python 3.12
```

### Local MCP Server

For a local MCP server with free Edge TTS:

```bash
uv pip install -e .[local-mcp]
```

To also enable Azure and AWS Polly TTS providers (require API keys), add their extras:

```bash
uv pip install -e .[local-mcp,tts-azure,tts-aws]
```

### AWS Lambda Deployment

See [infra/README.md](infra/README.md) for deployment instructions. The AWS IAM
setup is documented in [docs/aws_iam_settings.md](docs/aws_iam_settings.md).

### Development

```bash
uv pip install -e .[local-mcp,tts-aws,tts-azure,dev]
```

#### Tests
Run all tests:
```bash
uv run pytest
```

Run the fast tests only (skip the TTS provider tests):
```bash
uv run pytest tests/ --ignore=tests/unit/tts/test_tts_providers.py
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

### Local MCP Server (stdio)

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

### AWS Deployment (HTTP)

Deploy to AWS Lambda for hosted MCP access. See [infra/README.md](infra/README.md) for instructions.

### Tools & Resources

**Resource:**

- `skill://anki-vocabulary-builder/SKILL.md` - the packaged Ankify skill, exposed through FastMCP's skill provider. The AI client reads and follows it to build the vocabulary table (it can also be copied and used as a normal `SKILL.md` skill).

**Tool:**

- `convert_TSV_to_Anki_deck` - convert a TSV vocabulary table to an `.apkg` file with TTS audio. The AI client should read the skill resource before calling this tool.

## TTS Providers

| Provider  | Package                            | Cost             | Notes                                                                              |
| --------- | ---------------------------------- | ---------------- | ---------------------------------------------------------------------------------- |
| Azure     | `azure-cognitiveservices-speech` | Paid (free tier) | The broadest language support. Good quality. "Neural" engines only.               |
| AWS Polly | `boto3`                          | Paid (free tier) | Good quality for "Neural" engine. Worse for languages with "Standard" engine only. |
| Edge      | `edge-tts`                       | Free             | Good quality, same to Azure. May rate-limit, but usually enough for local usage.   |

From my (limited to English, German, and Russian) experience, all "Neural" engines create good enough pronunciation in 99.9% cases and good for learning. "Standard" engines are a bit worse and OK for native speakers to understand, but not good enough to learn a foreign language pronunciation. But "Standard" engines are only on AWS, so it's quite unlikely you'll use them anyway, while all the default options use providers with "Neural" engines.

Install specific providers:

```bash
uv pip install -e .[tts-azure]
uv pip install -e .[tts-aws]
uv pip install -e .[tts-edge]
```

## Environment Variables

Provider credentials can be set via environment variables or `.env` file, see `.env.example`.

## License

MIT
