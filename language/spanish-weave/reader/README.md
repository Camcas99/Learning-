# Reader (preview)

A phone web page that shows message threads with a few words in Spanish inside the bubbles. Tap a word for its meaning
and sound hint, or tap English to see the messages as they were written. It only reads: replies go through the real
app, and it never sends anything.

For now it shows made-up threads (`demo.js`). Real threads need a read-only helper on the Mac, which isn't built yet.

## How words are chosen

`extension/src/chatweave.js` picks the words, with no AI model, no network and no key, so a friend's message stays on
the device it's read on. `extension/src/chatrules.js` says where each word in the list may stand in for English: a word
swaps only where the English keeps the one meaning the list gives it, and anything unsure stays English. Words that
change with the speaker's gender are left out, since a text doesn't say who wrote it.

- Words in use (learning, shaky or known) can appear. Words not introduced yet never do.
- About one swap per ten words, at most two a sentence, each word once, learning words first.
- Messages with a one-time code, about health, money, legal trouble, emergencies, driving or a death, or over 4,000
  characters stay in English.
- Links, email addresses, handles, hyphenated words, names and all-caps words stay as written.
- Nothing here counts toward known: chat Spanish sends no sightings.

## Try it

From the plugin folder:

```bash
python3 -m http.server 8765 --bind 127.0.0.1
```

Then open http://127.0.0.1:8765/reader/ in a browser.

## Tests

`extension/test/chatweave.test.js` checks every rule against the word's meaning in `data/lexicon.csv`, plus sentences
that must change and sentences that must stay English. `extension/test/reader.test.js` checks the page, including that
message text never becomes markup. Both run with `bun test` in `extension/`.
