## Anki Note Structure

### Fields

Each Anki note contains:

- `Front` - Front side text
- `Back` - Back side text
- `Front language` - Language code for TTS
- `Back language` - Language code for TTS
- `Front sound` - Audio file
- `Back sound` - Audio file

### Note Types

| Config / tool value (`note_type`) | Anki model name           | MCP shorthand | Cards                  | Use Case                  |
| --------------------------------- | ------------------------- | ------------- | ---------------------- | ------------------------- |
| `basic_and_reversed`              | Ankify Basic & Reversed   | `br`          | 2 (Forward + Backward) | Remember both directions  |
| `basic`                           | Ankify Basic              | `ba`          | 1 (Forward only)       | Remember Back given Front |

See [Anki documentation](https://docs.ankiweb.net/getting-started.html#notes--fields) for Notes vs Cards explanation.

### TSV Format by Note Type

**`basic_and_reversed`** - LLM creates one-directional translations:

```tsv
jemanden abholen	to pick someone up	German	English
der Bahnsteig	train platform	German	English
```

**`basic`** - LLM creates bidirectional translations:

```tsv
jemanden abholen	to pick someone up	German	English
to pick someone up	jemanden abholen	English	German
der Bahnsteig	train platform	German	English
train platform	der Bahnsteig	English	German
```

The 3rd and 4th columns (language labels) are important for correct TTS pronunciation.

## Card Templates

HTML/CSS templates for card rendering are stored in [src/ankify/anki/templates](../src/ankify/anki/templates) and loaded on each run.
