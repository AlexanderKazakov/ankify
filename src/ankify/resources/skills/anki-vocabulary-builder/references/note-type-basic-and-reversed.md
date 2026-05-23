# Note type: `basic_and_reversed`

The dictionary is one-way. All the cells in the 1st column are in LANGUAGE_STUDIED, and all the cells in the 2nd column are in LANGUAGE_KNOWN. The 3rd column is always `LANGUAGE_STUDIED`, and the 4th column is always `LANGUAGE_KNOWN`.
The output format is:
```
LANGUAGE_STUDIED word	its LANGUAGE_KNOWN translation	LANGUAGE_STUDIED	LANGUAGE_KNOWN
another LANGUAGE_STUDIED word	another LANGUAGE_KNOWN translation	LANGUAGE_STUDIED	LANGUAGE_KNOWN
...
```

Imagine yourself learning this table in the following way: given a word from the 1st column, you need to recall its translation from the 2nd column, and vice versa: given a word from the 2nd column, you need to recall its translation from the 1st column. Keep that in mind when you decide on the translation and phrasing.

## Examples

If we were building an English-Russian vocabulary:

### Example: disambiguating an overly generic translation

Building English-Russian vocabulary for 'endeavor':
Bad:
```
endeavor	попытка	English	Russian
```
-- "попытка" most naturally reverses to "attempt", not "endeavor" specifically. The card is unanswerable in reverse.
Good:
```
endeavor	усилие, попытка; начинание	English	Russian
```
"начинание" carries the "undertaking / venture" sense that distinguishes "endeavor" from a plain "attempt".

### Example: when no extension is needed

Building English-Russian vocabulary for 'oak':
```
oak	дуб	English	Russian
```
Both directions are unambiguous, so no extension is needed. Do not pad rows with synonyms when the simple translation is already precise — extra synonyms add cognitive load without adding clarity.

### Example: a fixed phrase

Building English-Russian vocabulary for 'to take place':
```
to take place	состояться, иметь место	English	Russian
```
The phrase stays a phrase in both directions. Do not collapse the reverse direction onto a single verb — the learner should produce a phrase, not just "to happen".

## Rule of thumb

Before finalizing a row, mentally flip it: "given the 2nd-column cell as a prompt, would the 1st-column cell be a natural answer?" If not, extend or rephrase the 2nd column until it is. But stop as soon as the reverse direction is answerable — additional synonyms beyond that point hurt rather than help.
