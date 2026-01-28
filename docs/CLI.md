# Ankify CLI

A command-line application for creating Anki decks with text-to-speech audio.

## Overview

The CLI takes arbitrary text (a book fragment, a foreign language lesson chat export, etc.) and:

- Converts it to a vocabulary table using an LLM
- Generates text-to-speech audio for all entries
- Packages everything into an Anki deck file (.apkg)
- Supports manual adjustment of the vocabulary table before TTS generation
- Includes few-shot LLM prompting with automatic collection of validated examples

## Installation

```bash
pip install ankify[local-all]
```

Or for development:

```bash
git clone https://github.com/AlexanderKazakov/ankify.git
cd ankify
uv venv --python 3.12
uv pip install -e .[local-all,dev]
```

## Usage

```bash
ankify --config config.yaml [--options]
```

Or with uv:

```bash
uv run ankify --config config.yaml [--options]
```

See config examples in the `settings` directory.

## Configuration

All options can be set via:

- YAML config file (`--config`)
- Command-line options
- Environment variables (prefix: `ANKIFY__`)
- `.env` file

**Priority (high to low):** CLI > env > dotenv > YAML

### Required Settings

- `language_a` - Target language being studied (e.g., German)
- `language_b` - Known/native language (e.g., English)

### Provider Credentials

You need LLM provider access keys. Any OpenAI-compatible provider is supported (tested with OpenAI and Helicone).

TTS defaults to Edge (no key required, free), but it may rate-limit. AWS Polly and Azure TTS are also supported.

Credentials can be set via environment variables or `.env` file, see `.env.example` for examples.

Copy `.env.example` to `.env` and fill in your keys. Run the application **from the same directory** where `.env` is located.

## How It Works

1. **Text to Vocabulary:** The provided text is converted to a `.tsv` (tab-separated values) vocabulary table using an LLM (according to the rules stated in the prompt and the few-shot examples)
2. **Manual Review (optional):** If `confirm_steps` is enabled, you can review and edit the TSV file before proceeding
3. **Speech Generation:** TTS audio is generated for all vocabulary entries
4. **Vocabulary to Anki:** Everything is packaged into an Anki deck file (`.apkg`)
5. **Import to Anki:** Open the resulting file in Anki. If the deck name in settings is equal to the name of an existing deck, it will be loaded directly into the existing deck.

## LLM Prompt Customization

The LLM prompt is built from:

- `prompt_template` - default: `settings/prompts/prompt_template.md.j2`
- `custom_instructions` - optional language/level/format-specific instructions
- `few_shot_examples` - optional directory of validated input/output pairs
- Language and note type settings

### Few-Shot Examples

Few-shot examples directory structure: pairs of `{stem}.txt` and `{stem}.tsv` files.

The application will:

1. Load all pairs from the specified directory
2. Embed them into the prompt
3. After a successful run, ask whether to save the new result as a new example

These additional steps take time initially but significantly improve output quality.

## Interactive Mode

By default, `confirm_steps` is `true`, which allows you to:

- Review the intermediate vocabulary table
- Edit it manually (e.g., in a spreadsheet editor, saving back as TSV)
- Confirm before generating speech and the Anki deck

To run non-interactively: `--no-confirm-steps`

**Tip:** It's usually better to review the vocabulary table. The time spent is negligible compared to learning time in Anki, and precise vocabulary is worth it.

## File Handling

If output files already exist:

| File                   | Default Behavior |
| ---------------------- | ---------------- |
| `table_output` (TSV) | Reuse existing   |
| `anki_output` (APKG) | Overwrite        |

With `confirm_steps` enabled, you'll be asked for each file.
