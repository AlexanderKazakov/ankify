# Note type: `basic`

The dictionary is two-way. The pairs "LANGUAGE_STUDIED -> LANGUAGE_KNOWN" are interleaved with "LANGUAGE_KNOWN -> LANGUAGE_STUDIED" pairs.
The output format is:
```
LANGUAGE_STUDIED word	its LANGUAGE_KNOWN translation	LANGUAGE_STUDIED	LANGUAGE_KNOWN
its LANGUAGE_KNOWN translation	LANGUAGE_STUDIED word	LANGUAGE_KNOWN	LANGUAGE_STUDIED
another LANGUAGE_STUDIED word	another LANGUAGE_KNOWN translation	LANGUAGE_STUDIED	LANGUAGE_KNOWN
another LANGUAGE_KNOWN translation	another LANGUAGE_STUDIED word	LANGUAGE_KNOWN	LANGUAGE_STUDIED
...
```

In general, "LANGUAGE_KNOWN -> LANGUAGE_STUDIED" pairs should just repeat the "LANGUAGE_STUDIED -> LANGUAGE_KNOWN" pairs in the reverse order, but not always. Think on it, consider when it's better to adjust, extend, or even split a row into several rows to make the Anki card clearer. Imagine yourself learning this table in the following way: given a word from the 1st column, you need to recall its translation from the 2nd column. And sometimes translation in one direction is good, but in the opposite direction, it is awkward. Then, you need to adjust or extend the first column, or even split the row into a couple of separate ones. The ultimate goal is to create a meaningful table for learning the 2nd column given the 1st column, not just duplicate every row swapping the cells. Keep that in mind when you decide on the translation and phrasing.

## Examples

If we were building an English-Russian vocabulary:

### Example: straight reversal is fine

```
chair	стул	English	Russian
стул	chair	Russian	English
```
Both directions are unambiguous. Do not invent synonyms just to make the reverse row "richer" — clean one-to-one pairs are the easiest cards to learn.

### Example: a fixed phrase stays a phrase

```
to take place	иметь место, состояться	English	Russian
иметь место	to take place, to occur	Russian	English
```
The Russian side keeps the phrase form; the reverse card does not collapse to a single verb. Pair a phrase with a phrase, a verb with a verb.

### Example: splitting when one word has several distinct meanings

Bad:
```
bank	банк; берег реки	English	Russian
банк; берег реки	bank	Russian	English
```
`банк` and `берег реки` are two different prompts; a combined reverse card is unanswerable.

Good:
```
bank	банк; берег реки	English	Russian
банк	bank	Russian	English
берег реки	bank, riverbank	Russian	English
```

### Example: collocations for disambiguation

When a word's meaning shifts dramatically depending on what it's used with, the cleanest way to disambiguate is to embed a typical collocation in BOTH the LANGUAGE_STUDIED and LANGUAGE_KNOWN cells. Each row then evokes a single, specific sense, and the prompt–answer pair is self-contained in both directions.

```
to take a photo	сделать фотографию	English	Russian
сделать фотографию	to take a photo	Russian	English
to take a shower	принять душ	English	Russian
принять душ	to take a shower	Russian	English
to take a bus	сесть на автобус	English	Russian
сесть на автобус	to take a bus	Russian	English
```

Listing "to take" alone would force a hodgepodge reverse translation like "сделать, принять, сесть на …", which no learner could naturally produce. Locking each row to one collocation — the same collocation on both sides — makes both directions answerable.

## Rule of thumb

For each LANGUAGE_STUDIED -> LANGUAGE_KNOWN row, draft the reverse row and ask:
- Is the LANGUAGE_KNOWN prompt ambiguous? → split the reverse into separate rows.
- Is the reverse direction phrased awkwardly with a straight swap? → adjust or extend the reverse cell.
- Is everything unambiguous in both directions? → leave the reverse as a plain swap; do not over-engineer.
