# Spanish Weave on your iPhone

Three ways to use Spanish Weave on an iPhone, from least to most setup:

1. **Chats in the Claude or ChatGPT app.** Paste a level block once (see [blocks/level-01.md](blocks/level-01.md)), or
   on a paid Claude plan use the chat skill (see "On claude.ai and the Claude apps" in [README.md](README.md)).
2. **A daily quiz and a progress page on the phone** that update your real progress on your Mac. This page explains
   them.
3. **Spanish on web pages in Safari** is not available yet: Safari on iPhone needs a separate app for that.

## The daily quiz and the progress page

Each day your Mac puts a quiz list in iCloud Drive: your due words first, then every other learning word for practice.
A Shortcut on your iPhone asks them, and your answers go back to the Mac through iCloud Drive, where they count like
answers to `/spanish-weave:quiz` (graded by you, without the quiz's el/la check). The Mac also writes a progress page,
which a second Shortcut opens, so you can watch words change from your phone.

**You need:** a Mac with the Spanish Weave plugin set up and iCloud Drive on, and an iPhone signed in to the same Apple
Account with the Shortcuts app. The Mac does the bookkeeping; with no Mac, use the pasted blocks instead.

**What goes into iCloud Drive:** today's quiz words with their meanings and sound hints, your stage, and on the progress
page every word you have in use (known, learning or shaky) with its meaning, sound hint and the last week's quiz
results. Never your Gemini key, your chats, or the words you haven't met yet. Apple can read iCloud Drive files unless
Advanced Data Protection is on (Settings > your name > iCloud > Advanced Data Protection).

### 1. Turn it on, on the Mac

In Claude Code, run `/spanish-weave:phone on`. (In Terminal it is `python3 ~/.spanish-weave/app/scripts/sw.py phone on`;
macOS may ask once whether it can use iCloud Drive. That copy is updated by `/spanish-weave:setup`, so after updating
the plugin run setup again first.) This creates the folder **iCloud Drive > Shortcuts > Spanish Weave** with
`snapshot.json` (today's words), `progress.html` (the progress page) and an `inbox` folder for your answers.

The Mac updates the list and the page in the background while you use Claude Code. `/spanish-weave:phone sync` does it
at once, and `/spanish-weave:phone status` says when it last ran. Turn it on on one Mac only.

Then keep the folder on your devices: in the iPhone's Files app, press and hold **iCloud Drive > Shortcuts > Spanish
Weave** and choose **Keep Downloaded**. If Optimize Mac Storage is on, do the same on the Mac in Finder.

### 2. Build the "Spanish Weave Quiz" shortcut

Open Shortcuts, tap **+**, name it **Spanish Weave Quiz**, and add these actions in order. Words in **bold** are action
names you can find with the search field; `[Name]` means "insert the variable Name".

**Read today's list**

1. **Get File from Folder**: Folder **Shortcuts**, Path `Spanish Weave/snapshot.json`.
2. **Get Text from Input** (the File), then **Get Dictionary from Input** (the Text), then **Set Variable** `List`.
3. **Get Dictionary Value**: Get Value for `made` in `List`, then **Set Variable** `Made`.
4. **Format Date** (Current Date): Custom, `yyyy-MM-dd`, then **Set Variable** `Today`.
5. **Format Date** (Current Date): Custom, `yyyyMMdd-HHmmss`, then **Set Variable** `Stamp`.
6. **Get Dictionary Value**: Get Value for `items` in `List`.

**The quiz**

7. **Repeat with Each** item in that Dictionary Value:
   1. **Get Dictionary Value**: Get Value for `ask` in Repeat Item, then **Set Variable** `Question`.
   2. **Ask for Input**: Text, Prompt `[Question]`, **Allow Multiple Lines** off (so Return answers).
   3. **Get Dictionary Value**: Get Value for `es` in Repeat Item, then **Set Variable** `Word`.
   4. **Get Dictionary Value**: Get Value for `en` in Repeat Item, then **Set Variable** `Meaning`.
   5. **List** with exactly three items, in lowercase: `right`, `wrong`, `known`.
   6. **Choose from List**: Prompt `[Word] = [Meaning]. Did you get it?`, then **Set Variable** `Result`.
   7. **Text** (type this exactly, with straight quotes; if they turn curly, the Mac straightens them):
      `{"word":"[Word]","kind":"quiz","result":"[Result]","day":"[Today]","snap":"[Made]"}`
      Your typed answer is never written down, only the choice you made.
   8. **Append to Text File**: append the Text to Shortcuts, File Path `Spanish Weave/inbox/iphone-[Stamp].jsonl`, Make
      New Line on.

   **End Repeat**.

**Wrap up**

8. **Show Notification** "Done. Your answers reach your Mac through iCloud."

Add the shortcut to your Home Screen, a widget or the Action button to start it with one tap.

**What the three choices do:**

- **right** counts the day. Three clean counted days make a learning word known.
- **wrong** is a slip: a learning word starts its three days over, and a known word you didn't recognize turns shaky.
- **known** means "I know this": the word becomes known at once, as with `/spanish-weave:known`, and comes back for a
  check in two weeks. On a word that's already known, it's a right answer.

**If it misbehaves:**

- **"Done" right away with no questions:** today's list is empty (you answered everything, or the Mac hasn't made a new
  list yet), or the Repeat isn't reading `items`.
- **A question shows the wrong thing:** each Get Dictionary Value inside the Repeat must read Repeat Item. Tap the blue
  word to check it; if a link turned red, pick the variable again.
- **A choice is blank:** the List has an empty item. Delete it.

### 3. Build the "Spanish Weave Progress" shortcut

Make a second shortcut named **Spanish Weave Progress** with two actions:

1. **Get File from Folder**: Folder **Shortcuts**, Path `Spanish Weave/progress.html`.
2. **Quick Look**.

Add it to your Home Screen too. (You can also open `progress.html` from the Files app.) The page shows your stage, your
known, learning and shaky counts, how close you are to the next stage, what changed on each of the last 7 days (up to
15 words a day, new changes first, with a count of the rest), a dot for each day a learning word has so far, and all
your known words.

The page changes when your Mac syncs: about every half hour while you use Claude Code, or right away with
`/spanish-weave:phone sync`. So after a quiz, your answers show up there once the Mac has read them.

### 4. Optional: a daily reminder

Build a third shortcut, **Spanish Weave Reminder**:

1. **Get File from Folder**: Folder **Shortcuts**, Path `Spanish Weave/snapshot.json`, Error If Not Found off.
2. **Get Text from Input**, then **Get Dictionary from Input**.
3. **Get Dictionary Value**: Get Value for `items` in that Dictionary, **Count**, then **Set Variable** `Due`.
4. **If** `Due` **is greater than** 0: **Show Notification**, title "Spanish Weave", body "[Due] words to quiz. Open
   Spanish Weave Quiz." **End If**.

The count comes from the Mac's last sync. If the Mac hasn't synced since yesterday's quiz, it may say 0 or stay quiet
even though words are waiting; a sync brings the new list.

Then make it run every morning:
- **iOS 26:** Automation tab > **+** > **Time of Day** > 8:00 AM, Daily > **Run Immediately** (turn off Notify When Run
  if you see it) > Next > choose Spanish Weave Reminder.
- **iOS 27:** open Spanish Weave Reminder > **Edit** > **Automation** > **Time of Day**, 8:00 AM, Daily. Then **Edit** >
  **Info** > **Privacy** > turn on **Allow Running When Locked**.

### Good to know

- **What has run on a real iPhone:** the quiz shortcut above. The Progress shortcut and the reminder are newer and
  follow Apple's Shortcuts guide; if an action name differs on your phone, search for the nearest match.
- **How long the quiz is:** up to 10 due words, plus up to 20 other learning words (shaky ones first), so at most 30
  questions a day.
- **New words** join the list the day after they arrive, so you meet them before you're asked.
- **The answer file's name:** iOS may add `.json` or `.txt` to it (`iphone-....jsonl.json`). That's fine: the Mac
  reads those too.
- **Answers are counted once.** The Mac reads each line once, and a word counts at most once a day, on the Mac or the
  phone. A known word counts only on a day it was due, so quizzing an old list never counts it early or twice. A
  learning word can be answered every day: that's the practice. A right practice answer is a counted day and leaves its
  review schedule's gap as it was; a wrong one is a slip. Only words the Mac offered count.
- **Nothing on the list?** You've answered everything for today, or there are no learning words and no known words due.
  Known words come back at growing gaps, as in `/spanish-weave:quiz`.
- **Same questions again?** The list stays as it is until the Mac reads your answers. Taking it twice before then is
  harmless: a word counts once a day.
- **The list didn't change?** The Mac updates it in the background while you use Claude Code (also while Spanish
  Weave is paused), about every half hour. `/spanish-weave:phone sync` updates it now, and `/spanish-weave:phone
  status` shows when it last synced, the last answers it got, and any answer file it had to skip.
- **Turn it off** with `/spanish-weave:phone off`. The folder stays in iCloud Drive, with the last list and page, until
  you delete it.
