# Spanish Weave on your iPhone

Three ways to use Spanish Weave on an iPhone, from least to most setup:

1. **Chats in the Claude or ChatGPT app.** Paste a level block once (see [blocks/level-01.md](blocks/level-01.md)), or
   on a paid Claude plan use the chat skill (see "On claude.ai and the Claude apps" in [README.md](README.md)).
2. **A daily quiz on the phone** that updates your real progress on your Mac. This page explains it.
3. **Spanish on web pages in Safari** is not available yet: Safari on iPhone needs a separate app for that.

## The daily quiz

Your Mac puts today's due quiz words in iCloud Drive. A Shortcut on your iPhone asks them, and your answers go back
to the Mac through iCloud Drive, where they count like answers to `/spanish-weave:quiz` (graded against the list's
answers or by you, without the quiz's el/la check).

**You need:** a Mac with the Spanish Weave plugin set up and iCloud Drive on, and an iPhone signed in to the same Apple
Account with the Shortcuts app. The Mac does the bookkeeping; with no Mac, use the pasted blocks instead.

**What goes into iCloud Drive:** only today's due words, their meanings and sound hints, and your stage. Never your
Gemini key, your chats, or the rest of your word list. Apple can read iCloud Drive files unless Advanced Data
Protection is on (Settings > your name > iCloud > Advanced Data Protection).

### 1. Turn it on, on the Mac

In Claude Code, run `/spanish-weave:phone on`. (In Terminal it is `python3 ~/.spanish-weave/app/scripts/sw.py phone on`;
macOS may ask once whether it can use iCloud Drive. That copy is updated by `/spanish-weave:setup`, so after updating
the plugin run setup again first.) This creates the folder **iCloud Drive > Shortcuts >
Spanish Weave** with `snapshot.json` (today's words) and an `inbox` folder for your answers.

The Mac updates the list in the background while you use Claude Code. `/spanish-weave:phone sync` does it at once, and
`/spanish-weave:phone status` says when it last ran. Turn it on on one Mac only.

Then keep the folder on your devices: in the iPhone's Files app, press and hold **iCloud Drive > Shortcuts > Spanish
Weave** and choose **Keep Downloaded**. If Optimize Mac Storage is on, do the same on the Mac in Finder.

### 2. Build the "Spanish Weave Quiz" shortcut

Open Shortcuts, tap **+**, name it **Spanish Weave Quiz**, and add these actions in order. Words in **bold** are action
names you can find with the search field; `[Name]` means "insert the variable Name". Where a step says Regular
Expression, turn that option on in the action.

**Setup**

1. **Text** `iphone`, then **Set Variable** `DeviceLabel`. (A short name for this device: plain letters a to z and
   digits, starting with a letter, such as `iphone` or `ipad2`. Give each device its own.)
2. **Replace Text**: in `DeviceLabel`, replace `[^A-Za-z0-9]+` with `-` (Regular Expression), then **Set Variable**
   `Label`. (This keeps file names safe if the name has spaces or accents.)
3. **Text** `off`, then **Set Variable** `Judge`. (Change it to `on` only on an iPhone with Apple Intelligence turned
   on, iPhone 15 Pro or later: Apple's on-device model then grades close answers. On other phones that step stops
   the shortcut.)

**Read today's list**

4. **Get File from Folder**: Folder **Shortcuts**, Path `Spanish Weave/snapshot.json`. Turn **Error If Not Found** off.
5. **If** File **does not have any value**: **Show Alert** "No word list yet. On your Mac run /spanish-weave:phone
   sync, then try again.", then **Stop This Shortcut**. **End If**.
6. **Get Dictionary from Input** (the File), then **Set Variable** `Snap`.
7. **Get Dictionary Value** for `version` in `Snap`. **If** it is not `1`: **Show Alert** "Update the Spanish Weave Quiz
   shortcut (see IPHONE.md).", then **Stop This Shortcut**. **End If**.
8. **Date** (Current Date), **Format Date**: Custom, `yyyy-MM-dd`, then **Set Variable** `Today`.
9. **Format Date** (Current Date): Custom, `yyyyMMdd-HHmmss`, then **Set Variable** `Stamp`.
10. **Get Dictionary Value** for `made` in `Snap`, then **Set Variable** `Made`.
11. **Get File from Folder**: Shortcuts, Path `Spanish Weave/phone/[Label]-done.txt`, Error If Not Found off.
    **If** File **has any value**: **Get Text from Input**; **If** Text **is** `[Made]`: **Show Alert** "You already did
    this list. Your Mac picks up your answers on its next sync.", then **Stop This Shortcut**. **End If**, **End If**.
12. **Get Dictionary Value** for `day` in `Snap`. **If** it is not `[Today]`: **Show Alert** "This list is from
    [Dictionary Value]: your Mac hasn't synced today. Quiz anyway?" with Show Cancel Button on. **End If**.
13. **Get Dictionary Value** for `items` in `Snap`, **Set Variable** `Items`, **Count** (Items). **If** Count **is** 0:
    **Show Alert** "Nothing due today.", then **Stop This Shortcut**. **End If**.

**Prepare the answer file**

14. **Random Number** between 1000 and 9999, then **Set Variable** `Rand`.
15. **Text** `Spanish Weave/inbox/[Label]-[Stamp]-[Rand].jsonl`, then **Set Variable** `InboxPath`.

**The quiz** (all of this goes inside one Repeat)

16. **Repeat with Each** item in `Items`:
    1. **Get Dictionary Value** for `es`, `en`, `hint` and `ask` in Repeat Item, setting variables `Word`, `Meaning`,
       `Hint` and `Ask`.
    2. **Get Dictionary Value** for `accept` in Repeat Item, **Combine Text** with Custom separator `|`, **Set
       Variable** `AcceptList`, then **Text** `|[AcceptList]|`, **Set Variable** `AcceptBar`. Do the same for `reject`:
       **Get Dictionary Value**, **Combine Text** with `|`, **Set Variable** `RejectList`, **Text** `|[RejectList]|`,
       **Set Variable** `RejectBar`.
    3. **Ask for Input**: Text, Prompt `[Ask]`, **Allow Multiple Lines** off (so Return answers). **Set Variable**
       `Typed`.
    4. Fold the answer the way the Mac folded the accepted answers: **Change Case** (lowercase) on `Typed`, then one
       **Replace Text** action for each of these, in order, each with Regular Expression on:
       `[áàâäã]` with `a`; `[éèêë]` with `e`; `[íìîï]` with `i`; `[óòôöõ]` with `o`; `[úùûü]` with `u`; `ñ` with `n`;
       `ç` with `c`; `\p{M}` with nothing; `['’]` with nothing; `[^a-z0-9]+` with a space; and `^ +| +$` with nothing.
       **Set Variable** `Norm`.
    5. **Text** `|[Norm]|`, **Set Variable** `NormBar`. **Text** `unsure`, **Set Variable** `Result`.
    6. **If** `Norm` **does not have any value**: **Text** `wrong`, **Set Variable** `Result`. **Otherwise**: **If**
       `AcceptBar` **contains** `[NormBar]`: **Text** `right`, **Set Variable** `Result`. **End If**. **If** `RejectBar`
       **contains** `[NormBar]`: **Text** `wrong`, **Set Variable** `Result`. **End If**. **End If**.
    7. Optional judge: **If** `Result` **is** `unsure` and `Judge` **is** `on`: **Use Model** (On-Device) with the prompt
       "You grade a Spanish vocabulary quiz. Question: [Ask]. Correct answers: [AcceptList]. Learner wrote: [Typed].
       Is it correct in meaning, ignoring spelling slips and accents? Answer only yes or no." **If** the response
       contains `yes`: **Text** `right`, **Set Variable** `Result`. **End If**. **End If**.
    8. **If** `Result` **is** `unsure`: **Choose from Menu** with the prompt "You wrote: [Typed]. Answer: [Word] =
       [Meaning] ([Hint])", options **I had it** (Text `right`, Set Variable `Result`) and **I missed it** (Text
       `wrong`, Set Variable `Result`). **End If**.
    9. **If** `Result` **is** `wrong`: **Add to Variable** `Missed` (Repeat Item), and **Show Alert** "[Word] = [Meaning]
       ([Hint])". **End If**.
    10. **Text** (type this exactly, with straight quotes; if they turn curly, the Mac straightens them):
        `{"word":"[Word]","kind":"quiz","result":"[Result]","day":"[Today]","snap":"[Made]"}`
        Your typed answer is never written down, only right or wrong.
    11. **Append to Text File**: append the Text to Shortcuts, File Path `[InboxPath]`, Make New Line on.

    **End Repeat**.

**Wrap up**

17. **If** `Missed` **has any value**: **Show Alert** "Once more, the ones you missed (practice, not recorded)", then
    **Repeat with Each** item in `Missed`: **Get Dictionary Value** for `ask`, **Ask for Input** with it, then **Show
    Alert** with the word, meaning and hint. **End Repeat**. **End If**.
18. **Text** `[Made]`, then **Save File** to Shortcuts: Ask Where to Save off, Subpath
    `Spanish Weave/phone/[Label]-done.txt`, Overwrite If File Exists on.
19. **Show Notification** "Done. Your answers reach your Mac through iCloud."

Add the shortcut to your Home Screen, a widget or the Action button to start it with one tap.

### 3. Optional: a daily reminder

Build a second shortcut, **Spanish Weave Reminder**:

1. **Text** with the same device name as in the quiz shortcut, **Replace Text** `[^A-Za-z0-9]+` with `-` (Regular
   Expression), then **Set Variable** `Label`.
2. **Get File from Folder**: Shortcuts, `Spanish Weave/snapshot.json`, Error If Not Found off. **If** File **does not
   have any value**: **Stop This Shortcut**. **End If**.
3. **Get Dictionary from Input**, **Set Variable** `Snap`. **Get Dictionary Value** for `made` in `Snap`, **Set
   Variable** `Made`.
4. **Get File from Folder**: Shortcuts, Path `Spanish Weave/phone/[Label]-done.txt`, Error If Not Found off. **If**
   File **has any value**: **Get Text from Input**; **If** Text **is** `[Made]`: **Stop This Shortcut** (today's quiz is
   done). **End If**, **End If**.
5. **Get Dictionary Value** for `items` in `Snap`, **Count**, **Set Variable** `Due`.
6. **If** `Due` **is greater than** 0: **Show Notification**, title "Spanish Weave", body "[Due] words to quiz. Open
   Spanish Weave Quiz." **End If**.

Then make it run every morning:
- **iOS 26:** Automation tab > **+** > **Time of Day** > 8:00 AM, Daily > **Run Immediately** (turn off Notify When Run
  if you see it) > Next > choose Spanish Weave Reminder.
- **iOS 27:** open Spanish Weave Reminder > **Edit** > **Automation** > **Time of Day**, 8:00 AM, Daily. Then **Edit** >
  **Info** > **Privacy** > turn on **Allow Running When Locked**.

### Good to know

- **Not tested on a real iPhone yet.** The steps follow Apple's Shortcuts guide; if an action name differs on your
  phone, search for the nearest match. Please report what you find.
- **Answers are counted once.** Each run writes its own answer file and the Mac reads each line once. A word counts
  at most once a day, on the Mac or the phone, and a phone answer counts only on a day the word was due, so quizzing
  an old list never counts a word early or twice. Only words the Mac offered count.
- **Nothing due?** Words come up the day after you first meet them, then at growing gaps, as in `/spanish-weave:quiz`.
- **The list didn't change?** The Mac updates it in the background while you use Claude Code (also while Spanish
  Weave is paused), about every half hour. `/spanish-weave:phone sync` updates it now, and `/spanish-weave:phone
  status` shows when it last synced, the last answers it got, and any answer file it had to skip.
- **Turn it off** with `/spanish-weave:phone off`. The folder stays in iCloud Drive until you delete it.
