# Note type: `basic`

The vocabulary is two-way, and you write each direction as its own row. Forward rows go from LANGUAGE_STUDIED to LANGUAGE_KNOWN; reverse rows go from LANGUAGE_KNOWN to LANGUAGE_STUDIED. Each row becomes exactly one Anki card (left column → right column).

Because the languages alternate from row to row, use `Front` and `Back` as the table headers, not the language names. List the forward row and its reverse row next to each other:


| Front                                | Back                               |
| ------------------------------------ | ---------------------------------- |
| a LANGUAGE_STUDIED word              | its LANGUAGE_KNOWN translation     |
| the same LANGUAGE_KNOWN translation  | the LANGUAGE_STUDIED word          |
| another LANGUAGE_STUDIED word        | another LANGUAGE_KNOWN translation |
| the other LANGUAGE_KNOWN translation | the other LANGUAGE_STUDIED word    |


In general, the reverse row just repeats the forward row with the two cells swapped, but not always. Think about it: consider when it is better to adjust, extend, or even split a row into several rows to make the Anki cards clearer. Imagine yourself learning this table in the following way: given the Front cell, you need to recall the Back cell. Sometimes one direction is good, but the opposite direction is awkward with a plain swap. Then you need to adjust or extend the Front cell, or even split the row into several rows. The goal is a meaningful set of cards for learning the Back given the Front, not just a copy of every row with the cells swapped.

## Examples

If we were building an English-Russian vocabulary:

### Example: straight reversal is fine


| Front | Back  |
| ----- | ----- |
| chair | стул  |
| стул  | chair |


Both directions are unambiguous. Do not invent synonyms just to make the reverse row "richer" — clean one-to-one pairs are the easiest cards to learn.

### Example: a fixed phrase stays a phrase


| Front         | Back                    |
| ------------- | ----------------------- |
| to take place | иметь место, состояться |
| иметь место   | to take place, to occur |


The Russian side keeps the phrase form; the reverse card does not collapse to a single verb. Pair a phrase with a phrase, a verb with a verb.

### Example: splitting when one word has several distinct meanings

Bad:


| Front            | Back             |
| ---------------- | ---------------- |
| bank             | банк; берег реки |
| банк; берег реки | bank             |


`банк` and `берег реки` are two different prompts; a combined reverse card is unanswerable.

Good:


| Front      | Back             |
| ---------- | ---------------- |
| bank       | банк; берег реки |
| банк       | bank             |
| берег реки | bank, riverbank  |


### Example: collocations for disambiguation

When a word's meaning shifts dramatically depending on what it is used with, the cleanest way to disambiguate is to embed a typical collocation in BOTH the Front and the Back cells. Each row then evokes a single, specific sense, and the prompt-answer pair is self-contained in both directions.


| Front              | Back               |
| ------------------ | ------------------ |
| to take a photo    | сделать фотографию |
| сделать фотографию | to take a photo    |
| to take a shower   | принять душ        |
| принять душ        | to take a shower   |
| to take a bus      | сесть на автобус   |
| сесть на автобус   | to take a bus      |


Listing "to take" alone would force an unnatural combined reverse translation like "сделать, принять, сесть на …", which no learner could naturally produce. Locking each row to one collocation — the same collocation on both sides — makes both directions answerable.

## Rule of thumb

For each forward (LANGUAGE_STUDIED → LANGUAGE_KNOWN) row, draft the reverse row and ask:

- Is the reverse prompt (the LANGUAGE_KNOWN cell) ambiguous? → split the reverse into separate rows or add collocations.
- Is the reverse direction phrased awkwardly with a straight swap? → adjust or extend the reverse cell or add collocations.
- Is everything unambiguous in both directions? → leave the reverse as a plain swap; do not over-engineer.

## Building the TSV

When the deck is built, each row becomes one TSV line: keep the two cells and append the two language labels for that row's direction. A forward row is LANGUAGE_STUDIED then LANGUAGE_KNOWN; a reverse row is LANGUAGE_KNOWN then LANGUAGE_STUDIED. See the "TSV format" section in `SKILL.md` for the exact format.

Example (English studied, Russian known):


| Front      | Back             |
| ---------- | ---------------- |
| bank       | банк; берег реки |
| банк       | bank             |
| берег реки | bank, riverbank  |


As TSV:

```
bank	банк; берег реки	English	Russian
банк	bank	Russian	English
берег реки	bank, riverbank	Russian	English
```

Never put more than one language in a single cell, so each cell maps to exactly one language label. Never put any headers into the TSV table.
