# Ankify

Create Anki decks with text-to-speech audio from arbitrary text using LLM and TTS services.

## Features

- **MCP Server**: Use with any MCP-compatible AI client, locally or in the cloud. No need for any API keys
- **CLI**: Standalone command-line tool, uses LLM through openai-compatible API
- **Multi-language TTS**: Azure, AWS Polly, and free Edge TTS support
- **Customizable prompts**: Curated vocabulary creation prompt templates for any language pair and note type with few-shot examples and custom instructions
- **Packed to Anki**: The resulting `.apkg` file is to be opened in Anki.

If the deck name in settings is equal to the name of an existing deck in your Anki, it will be loaded directly into the existing deck. Clarification of possible notes types: see [docs/Anki_note_types.md](docs/Anki_note_types.md).

## Installation

### Local MCP Server

For local MCP server with free Edge TTS:

```bash
pip install ankify[local-mcp]
```

### Full Local (CLI + All TTS)

For all the features including CLI and all TTS providers:

```bash
pip install ankify[local-all]
```

### FastMCP Cloud

You need this only when deploying to FastMCP Cloud. This is the default installation option just because that's how it works with FastMCP Cloud. So most probably you don't need it.

```bash
pip install ankify
```

### Development

```bash
git clone https://github.com/AlexanderKazakov/ankify.git
cd ankify
uv venv --python 3.12
uv pip install -e .[local-all,dev]
```

## MCP Server

Ankify provides an MCP server for integration with LLM clients

### Cloud Deployment (FastMCP)

Deploy to FastMCP Cloud for hosted MCP access. The server uses Azure TTS by default.

### Local MCP Server

Add to your MCP client configuration:

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

### MCP Tools & Prompts

**Prompts:**

- `vocab` - Create vocabulary table (universal template for any language pair, note type, custom instructions)
- `vocab_en_ru_fo` - shortcut for English-Russian, forward-only not
- `vocab_ge_en_fb` - shortcut for German-English, forward-and-backward
- `deck` / `deck_fo` / `deck_fb` - Create Anki deck from vocabulary table (instructs AI to use the conversion tool properly)

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
pip install ankify[tts-azure]
pip install ankify[tts-aws]
pip install ankify[tts-edge]
```

## CLI

For CLI usage documentation, see [docs/CLI.md](docs/CLI.md).

## Environment Variables

Provider credentials can be set via environment variables or `.env` file, see `.env.example` for examples.

## License

MIT
