# Note type: `basic_and_reversed`

The vocabulary is one-way. The left column is always LANGUAGE_STUDIED and the right column is always LANGUAGE_KNOWN. Use the two language names as the table headers. You list each entry only once, in a single row, and Anki creates two cards from it: a forward card (left → right) and a reverse card (right → left).

The table looks like this (the headers are the real language names):


| LANGUAGE_STUDIED              | LANGUAGE_KNOWN                     |
| ----------------------------- | ---------------------------------- |
| a LANGUAGE_STUDIED word       | its LANGUAGE_KNOWN translation     |
| another LANGUAGE_STUDIED word | another LANGUAGE_KNOWN translation |


Imagine yourself learning this table in the following way: given a word from the left column, you need to recall its translation from the right column, and the other way around: given a word from the right column, you need to recall the word from the left column. Keep that in mind when you decide on the translation and phrasing.

## Examples

If we were building an English-Russian vocabulary:

### Example: disambiguating an overly generic translation

Building English-Russian vocabulary for 'endeavor':

Bad:


| English  | Russian |
| -------- | ------- |
| endeavor | попытка |


-- "попытка" most naturally reverses to "attempt", not "endeavor" specifically. The card is unanswerable in reverse.

Good:


| English  | Russian                    |
| -------- | -------------------------- |
| endeavor | усилие, попытка; начинание |


"начинание" carries the "undertaking / venture" sense that distinguishes "endeavor" from a plain "attempt".

### Example: when no extension is needed

Building English-Russian vocabulary for 'oak':


| English | Russian |
| ------- | ------- |
| oak     | дуб     |


Both directions are unambiguous, so no extension is needed. Do not pad rows with synonyms when the simple translation is already precise — extra synonyms add cognitive load without adding clarity.

### Example: a fixed phrase

Building English-Russian vocabulary for 'to take place':


| English       | Russian                 |
| ------------- | ----------------------- |
| to take place | состояться, иметь место |


The phrase stays a phrase in both directions. Do not collapse the reverse direction onto a single verb — the learner should produce a phrase, not just "to happen".

## Rule of thumb

Before finalizing a row, mentally flip it: "given the right-column cell as a prompt, would the left-column cell be a natural answer?" If not, extend or rephrase or add collocation until it is. But stop as soon as the reverse direction is answerable — additional synonyms beyond that point hurt rather than help.

## Building the TSV

When the deck is being built, each row becomes one TSV line: keep the two cells and append the two language labels. Every row goes from LANGUAGE_STUDIED to LANGUAGE_KNOWN, so `front_language` is always LANGUAGE_STUDIED and `back_language` is always LANGUAGE_KNOWN. See the "TSV format" section in `SKILL.md` for the exact format.

Example (English studied, Russian known):


| English       | Russian                 |
| ------------- | ----------------------- |
| oak           | дуб                     |
| to take place | состояться, иметь место |


As TSV:

```
oak	дуб	English	Russian
to take place	состояться, иметь место	English	Russian
```

Never put more than one language in a single cell, so each cell maps to exactly one language label. Never put any headers into the TSV table.
