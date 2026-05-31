## New Card Order for Basic & Reversed Notes

A `basic_and_reversed` note has two cards (Forward and Backward). 

### How Anki orders new cards

The order is decided in two separate steps:

1. **Gather** - Anki walks new cards by their position (the card `due` value) and
  takes them up to the daily new-card limit, keeping a note's two cards together.
   This decides *which notes* are introduced today.
2. **Sort** - Anki reorders the gathered cards for display, using the deck setting
  "New card sort order". This decides whether you see all Forward cards first or
   each note's two cards one after the other.

#### What the `due` field means

`due` is a single integer column on the `cards` table, but its meaning depends on
the card state (`queue` / `type`):


| Card state           | `due` means                                     |
| -------------------- | ----------------------------------------------- |
| New (`queue=0`)      | **position** - the order to introduce new cards |
| Learning (`queue=1`) | **Unix timestamp in seconds** - next due moment |
| Review (`queue=2`)   | **day number** - days since collection creation |


A brand-new card has never been scheduled, so `due` holds its position. The first
time the card is studied, Anki overwrites `due` with a learning timestamp, then with
a review day number. The values never coexist; the position only orders the first
introduction.

### In genanki

The **gather** step (which notes per day, both sides together) is fixed by setting sequential `due` value to every note. It does not control the Forward/Backward display order, which is an app setting.

### The app setting (Forward/Backward order)

The display order is a per-deck preset, not part of the `.apkg`. To change it:

1. Main screen → click the gear icon next to the deck → **Options**.
2. Section **"Display Order"** → **"New card sort order"**.


| Value                                        | Day-1 order                                        |
| -------------------------------------------- | -------------------------------------------------- |
| **Card type, then order gathered** (default) | all Forward cards, then all Backward of same notes |
| **Order gathered**                           | each note's Forward then its own Backward          |


Leave these at their defaults so the fix above works:

- **"New card gather order"** = **Deck** (gathers by ascending position).
- **"Bury new siblings"** (section "Burying") = **off** (on shows only one side per
note per day).

