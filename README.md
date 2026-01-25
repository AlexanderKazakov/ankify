# Ankify: MCP and CLI for Anki decks with TTS speech

## MCP
Local stdio MCP -- automatic creation of .apkg Anki decks with added TTS speech + carefully tweaked prompt templates for vocabulary creation for any pair of languages.
```
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

## CLI

A Python command-line application that

- takes arbitrary text (a book fragment, a foreign language lesson chat export, ...)
- translates it into an [Anki](https://apps.ankiweb.net/) deck file with all the words and phrases
- or with any other vocabulary, depending on the instructions you give to the LLM
- **text-to-speech audio** is generated for all the vocabulary entities
- you can manually adjust the vocabulary table before the text-to-speech step if needed
- few-shot LLM prompting with automatic collection of validated examples

### How It Works

- **Text to Vocabulary:** The provided text is converted to a `.tsv` (tab-separated values) vocabulary table using an LLM (according to the rules stated in the prompt and the few-shot examples)
- **Speech is generated** for all vocabulary entries via a TTS service
- **Vocabulary to Anki:** All of it is packaged into a new Anki deck file (`.apkg`)
- **Manually import the resulting deck into Anki** and move all notes from it into a permanent deck (decks created by the application are intended to be temporary and to be used just for importing into Anki)

## Installation

```bash
git clone https://github.com/AlexanderKazakov/ankify.git
cd ankify
uv venv --python 3.12
uv pip install -e .[dev]
uv run ankify --help
```

## Usage

```bash
uv run ankify --config config.yaml [--options]
```

See config examples in the `settings` directory.

All options from the config can be overridden by command-line options, environment variables, or dotenv (priority (high > low): CLI > env > dotenv > YAML), but it's better to copy one of the existing config files and set your options there for reuse next time.

You need LLM provider access keys. Any OpenAI-compatible provider is supported (tested with OpenAI and Helicone). 

TTS defaults to Edge (no key required, free), but it may rate-limit. AWS Polly is supported too, but it requires AWS key and is not free after free tier expiration.

You may subclass and implement any additional provider if needed.

Provider access keys are set the same way as all the other settings, but since they are secret, you may prefer using dotenv or environment variables, see `.env.example`. To use dotenv, you need to copy it to `.env`, set your keys, and run the application **from the same directory** where `.env` is located.

### Instructions for the LLM about how to generate the vocabulary table

LLM prompt is built from:

- `prompt_template`, default is `settings/prompts/prompt_template.md.j2`
- optional language- or level- or format-specific `custom_instructions`
- optional `few_shot_examples` loaded from a directory of saved validated inputs/outputs
- languages and note type settings

Few-shot examples directory structure is simple: pairs of `{stem}.txt` and `{stem}.tsv` files. The application will look for all pairs in the specified directory and embed them into the prompt. After a successful run, the application will ask you whether it should save the new result as a new few-shot example.

These additional steps (own config, custom instructions, few-shot examples validation) take a bit of time initially but pay off quickly in output quality.

By default, the application will ask you to confirm each step before it is executed (`confirm_steps` is `true`). This allows you to manually adjust the intermediate vocabulary table before generating the speech and the Anki deck (e.g., in OpenOffice, saving it back in the same TSV format).

If you want to do everything in one run, you can disable confirmation with `--no-confirm-steps`. However, note that it's usually better to skim the intermediate vocabulary table and adjust it manually. It's a negligible amount of time compared to the time you are going to spend learning it in Anki later, so making the vocabulary precise in the beginning is worth it.

### If some output files already exist

If the TSV vocabulary file `table_output` or the Anki deck file `anki_output` already exists, the application can either rewrite them or reuse them. If `confirm_steps` is `true`, it will ask for instructions, otherwise it will make the default choice. By default, `table_output` will be reused, while `anki_output` will be rewritten by default.

## Anki Note & Card Structure

### The Note

The resulting Anki note consists of these fields:

- `Front`
- `Back`
- `Front language`
- `Back language`
- `Front sound`
- `Back sound`

### Note Types

See [this page](https://docs.ankiweb.net/getting-started.html#notes--fields) for the 'Note' vs 'Card' explanation

The application can generate two different types of notes:

- A note with two cards: the 'Forward Card' and the 'Backward Card' — `forward_and_backward` in config — **default** — to remember 'Back' given 'Front' and vice versa
- A note with a single 'Forward Card' — `forward_only` in config — just to remember 'Back' given 'Front'

The HTML/CSS templates used to render the cards are stored in [separate files within the package](src/ankify/anki/templates). They are loaded from there on every application run.

### Consistency between the LLM prompt and the note type

The prompt template is already conditioned on the note type and languages.

If you use the `forward_and_backward` note type, the LLM will be prompted to create a table with translations in one direction, like this:

```tsv
jemanden abholen    to pick someone up  German  English
der Bahnsteig   train platform  German  English
```

If you use the `forward_only` note type, the LLM will be prompted to create a table with translations in both directions, like this:

```tsv
jemanden abholen    to pick someone up  German  English
to pick someone up  jemanden abholen    English German
der Bahnsteig   train platform  German  English
train platform  der Bahnsteig   English German
```

The 3rd and 4th columns (language labels) are important for text-to-speech in both cases.
