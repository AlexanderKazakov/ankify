# Note type: `basic`

The vocabulary is two-way, and you write each direction as its own row. Forward rows go from LANGUAGE_STUDIED to LANGUAGE_KNOWN; reverse rows go from LANGUAGE_KNOWN to LANGUAGE_STUDIED. Each row becomes exactly one Anki card (left column → right column).

Because the languages alternate from row to row, use `Front` and `Back` as the table headers, not the language names. List the forward row and its reverse row next to each other:


| Front                                | Back                               |
| ------------------------------------ | ---------------------------------- |
| a LANGUAGE_STUDIED word              | its LANGUAGE_KNOWN translation     |
| the same LANGUAGE_KNOWN translation  | the LANGUAGE_STUDIED word          |
| another LANGUAGE_STUDIED word        | another LANGUAGE_KNOWN translation |
| the other LANGUAGE_KNOWN translation | the other LANGUAGE_STUDIED word    |


The default is simple: the reverse row is the forward row with the two cells swapped **verbatim**, synonyms and all. For the large majority of rows this plain mirror is exactly right, so do it by default and do not look for ways to "improve" it. Deviate only in specific situations, described below.

## Examples

If we were building an English-Russian vocabulary:

### Example: straight reversal is fine


| Front | Back  |
| ----- | ----- |
| chair | стул  |
| стул  | chair |


Both directions are unambiguous. Do not **invent** new synonyms just to make the reverse row "richer" — clean one-to-one pairs are the easiest cards to learn. This means do not fabricate extra synonyms that were not there. It does NOT mean dropping synonyms the forward row already has: those are kept on both sides (see the "synonyms are mirrored" example below).

### Example: a fixed phrase stays a phrase


| Front                   | Back                    |
| ----------------------- | ----------------------- |
| to take place, to occur | иметь место, состояться |
| иметь место, состояться | to take place, to occur |


Both sides keep the phrase form — the reverse does not collapse to a single verb. Note that both synonyms appear on both sides: the reverse prompt keeps `состояться`, it is not trimmed. Pair a phrase with a phrase, a verb with a verb.

### Example: comma-separated synonyms are mirrored on both sides


| Front                                    | Back                                     |
| ---------------------------------------- | ---------------------------------------- |
| bereavement                              | тяжёлая утрата, потеря близкого человека |
| тяжёлая утрата, потеря близкого человека | bereavement                              |


The two Russian phrases are synonyms for ONE meaning — they are comma-separated, not semicolon-separated. Keep all of them on BOTH sides. Do not drop one to make the reverse prompt look "cleaner": a prompt made of synonyms is fine, and it reinforces both. The reverse row here is simply the forward row with the cells swapped verbatim, which is exactly what it should be. Contrast this with the next example, where the items are DIFFERENT meanings and the reverse must be split instead.

### Example: splitting when one word has several distinct meanings

Bad:


| Front            | Back             |
| ---------------- | ---------------- |
| bank             | банк; берег реки |
| банк; берег реки | bank             |


`банк` and `берег реки` are two different unrelated things; a combined reverse card is extremely awkward. The semicolon is the signal: it separates different meanings, not synonyms.

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


Listing "to take" alone would force an unnatural combined reverse translation like "сделать, принять, сесть на …", which no learner could naturally produce. Locking each row to one collocation — the same collocation on both sides — makes both directions answerable. Do not hesitate to add collocations if that makes things cleaner and simpler.

## Rule of thumb

The default reverse row is the forward row with the two cells swapped **verbatim**, including every comma-separated synonym. This plain mirror is the correct answer for most rows. Start there, and deviate only for one of the two specific reasons below. The number of synonyms in a cell is NEVER a reason to deviate — a prompt made of comma-synonyms is good, not noise.

Deviate only when:

- **The cell holds several DIFFERENT meanings (semicolon-separated).** Then the reverse prompt would be unanswerable, so split the reverse into separate rows, one per meaning, and add a collocation where a bare word is still ambiguous. (See the `bank` example.) Comma-separated synonyms do NOT trigger this — they are one meaning, so mirror them.
- **A straight swap is grammatically awkward or unnatural in the reverse direction.** Then adjust or extend the wording so the reverse reads naturally, or add a collocation to both sides.

If neither applies — and for the large majority of rows neither does — leave the reverse as the verbatim mirror. Do not trim synonyms, do not reorder, do not "improve" it.

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
