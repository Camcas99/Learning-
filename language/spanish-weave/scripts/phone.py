"""iPhone sync through iCloud Drive (opt-in, Mac only). Python 3.9+, standard library only.

The Mac and the phone share the folder iOS shows as iCloud Drive > Shortcuts > Spanish Weave:
  snapshot.json   written by the Mac only: today's due quiz items, with answers pre-folded for the phone's checks
  inbox/*.jsonl   written by the phone only, one new file per quiz run: {"word", "kind": "quiz", "result", "day", "snap"}
  phone/          the phone's own done markers
One writer per file, so iCloud never makes conflict copies. The Mac creates the folders; the phone only adds files.

What goes to iCloud: the due words (Spanish, gloss, sound hint, question) and the stage. Never the Gemini key,
exposure.json, chat transcripts or the rest of the word state. What comes back is only quiz results, and each one must
name a word the Mac offered in one of its recent snapshots; it is then recorded through the same checks as any other
outside event (swlib.apply_events).

Nothing here ever downloads an evicted (dataless) iCloud file in the calling process: reads run with dataless
materialization off for the thread (Apple TN3150, setiopolicy_np), so they fail fast and are retried on a later run
instead of hanging the hook. The file layer was sketched and tested by a research pass for this feature.
"""
import contextlib
import ctypes
import ctypes.util
import datetime as dt
import errno
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import stat
import subprocess
import sys
import tempfile
import time
import unicodedata

sys.path.insert(0, str(Path(__file__).resolve().parent))
import swlib  # noqa: E402

SF_DATALESS = getattr(stat, 'SF_DATALESS', 0x40000000)  # stat.SF_DATALESS is new in 3.13; value from <sys/stat.h>
CONTAINER = 'iCloud~is~workflow~my~workflows'          # iCloud Drive > Shortcuts is <container>/Documents
FOLDER, INBOX, MARKS, SNAPSHOT = 'Spanish Weave', 'inbox', 'phone', 'snapshot.json'
VERSION = 1             # snapshot format; the Shortcut stops on any other
ITEMS = 10              # quiz items per snapshot, as many as /spanish-weave:quiz asks
SNAPS_KEPT = 14         # recent snapshots whose words a phone answer may name
MAX_SNAPSHOT = 512 * 1024
MAX_INBOX_FILE = 256 * 1024
MAX_INBOX_FILES = 50    # files read per run (files already read don't count); the rest wait for the next one
MAX_LINE = 2048
MAX_NESTING = 8         # [ and { in one line; an answer line has one, and deep nesting can crash json on Python 3.9
KEEP_DAYS = 30          # a fully read inbox file is deleted this long after it was last changed
TEMP_PREFIX, TEMP_SUFFIX = '.snapshot-', '.tmp'          # hidden, and a name iCloud skips
STALE_TEMP_SECONDS = 3600
# <label>-<stamp>-<rand>.jsonl, plus the " 2" iCloud adds on a new-file name clash. The label may start with "-" (the
# Shortcut turns a leading Á or other non-ASCII letter into one). iOS's Append to Text File adds its own extension to
# a name it doesn't recognize (iphone-....jsonl.json), so .json and .txt endings count too.
INBOX_NAME = re.compile(r'[A-Za-z0-9_-]{1,101}(?: [0-9]{1,3})?\.(?:jsonl(?:\.json|\.txt)?|json|txt)\Z')
NOT_READY = frozenset({errno.EDEADLK, errno.ETIMEDOUT, errno.EAGAIN})

# <sys/resource.h>
_IOPOL_TYPE_VFS_MATERIALIZE_DATALESS_FILES = 3
_IOPOL_SCOPE_THREAD = 1
_IOPOL_MATERIALIZE_OFF = 1


class Unavailable(Exception):
    """Phone sync can't run on this machine; str(error) is a one-line reason for status and setup. retry: whether a
    later run may succeed (iCloud Drive turned on, access allowed); never off a Mac."""

    def __init__(self, message, retry=True):
        super().__init__(message)
        self.retry = retry


class NotReady(Exception):
    """The item is in iCloud but not on this Mac yet (dataless), or iCloud timed out: a later run tries again."""


class TooBig(Exception):
    pass


def _denied(path, error):
    """Unavailable saying what to do when permissions block path: EACCES is the folder's own permissions; EPERM is
    macOS privacy (Privacy & Security) or a sandbox such as Claude Code's, which a Terminal run asks about once."""
    if error.errno == errno.EACCES:
        return Unavailable(f'no permission to use {path}: check that it belongs to you (Finder > Get Info)')
    script = Path(__file__).resolve().with_name('sw.py')
    return Unavailable(f'macOS privacy settings or a sandbox blocked {path}. Run this once in Terminal and allow '
                       f'access to iCloud Drive: python3 "{script}" phone sync')


# ---- the iCloud folder ----

def is_dataless(st):
    return bool(getattr(st, 'st_flags', 0) & SF_DATALESS)


_libc = None


def _lib():
    global _libc
    if _libc is None:
        _libc = False
        if sys.platform == 'darwin':
            try:
                lib = ctypes.CDLL(ctypes.util.find_library('c') or None, use_errno=True)
                lib.getiopolicy_np.argtypes = (ctypes.c_int, ctypes.c_int)
                lib.getiopolicy_np.restype = ctypes.c_int
                lib.setiopolicy_np.argtypes = (ctypes.c_int, ctypes.c_int, ctypes.c_int)
                lib.setiopolicy_np.restype = ctypes.c_int
                _libc = lib
            except (OSError, AttributeError):
                pass
    return _libc or None


@contextlib.contextmanager
def no_downloads():
    """Inside the block, this thread gets EDEADLK instead of downloading a dataless file or folder (TN3150,
    setiopolicy_np(3)). A no-op off macOS."""
    lib = _lib()
    old = lib.getiopolicy_np(_IOPOL_TYPE_VFS_MATERIALIZE_DATALESS_FILES, _IOPOL_SCOPE_THREAD) if lib else -1
    ok = old >= 0 and lib.setiopolicy_np(_IOPOL_TYPE_VFS_MATERIALIZE_DATALESS_FILES, _IOPOL_SCOPE_THREAD,
                                         _IOPOL_MATERIALIZE_OFF) == 0
    try:
        yield ok
    finally:
        if ok:
            lib.setiopolicy_np(_IOPOL_TYPE_VFS_MATERIALIZE_DATALESS_FILES, _IOPOL_SCOPE_THREAD, old)


def _check_dir(path, what):
    st = os.lstat(path)
    if stat.S_ISLNK(st.st_mode) or not stat.S_ISDIR(st.st_mode):
        raise Unavailable(f'{path} is not a folder')
    if hasattr(os, 'getuid') and st.st_uid != os.getuid():
        raise Unavailable(f'{what} belongs to another user')
    if st.st_mode & 0o002:
        raise Unavailable(f'anyone can write to {what}')
    return st


def shortcuts_folder(environ=None):
    """The folder iOS shows as iCloud Drive > Shortcuts, or raises Unavailable with the reason. Never creates it:
    ~/Library/Mobile Documents and its containers belong to iCloud. SPANISH_WEAVE_PHONE_DIR replaces it (tests)."""
    environ = os.environ if environ is None else environ
    override = environ.get('SPANISH_WEAVE_PHONE_DIR')
    if override:
        root = Path(override).expanduser()
        try:
            _check_dir(root, 'SPANISH_WEAVE_PHONE_DIR')
        except FileNotFoundError:
            raise Unavailable(f'SPANISH_WEAVE_PHONE_DIR {root} does not exist') from None
        return root
    if sys.platform != 'darwin':
        raise Unavailable('iPhone sync needs a Mac with iCloud Drive', retry=False)
    mobile = Path.home() / 'Library' / 'Mobile Documents'
    root = mobile / CONTAINER / 'Documents'
    with no_downloads():
        try:
            _check_dir(root, 'the Shortcuts folder in iCloud Drive')
        except FileNotFoundError:
            if not os.path.isdir(mobile / 'com~apple~CloudDocs'):
                raise Unavailable('iCloud Drive is off on this Mac (System Settings > Apple Account > iCloud)') from None
            raise Unavailable('iCloud Drive has no Shortcuts folder yet: open the Shortcuts app on the iPhone once, '
                              'then try again') from None
        except PermissionError as error:
            raise _denied(root, error) from None
        except OSError as error:
            if error.errno in NOT_READY:
                raise NotReady('the Shortcuts folder is still downloading from iCloud') from None
            raise
    return root


def ensure_folders(root):
    """Makes Spanish Weave/, its inbox/ and phone/ inside the Shortcuts folder (only the Mac creates them; a folder made
    by a second device could get a renamed copy). Returns (folder, inbox, warnings)."""
    folder = root / FOLDER
    warnings = []
    with no_downloads():
        for path in (folder, folder / INBOX, folder / MARKS):
            try:
                os.mkdir(path, 0o700)
            except FileExistsError:
                pass
            except OSError as error:
                if error.errno in NOT_READY:
                    raise NotReady(f'{path.name} is still downloading from iCloud') from None
                if error.errno in (errno.EPERM, errno.EACCES):
                    raise _denied(path, error) from None
                if error.errno == errno.EROFS:
                    raise Unavailable(f'cannot create {path} ({error.strerror})') from None
                raise
            _check_dir(path, path.name)
        try:
            with os.scandir(root) as entries:
                clashes = sorted(e.name for e in entries if re.fullmatch(re.escape(FOLDER) + r' [0-9]{1,3}', e.name))
        except OSError:
            clashes = []
    if clashes:
        warnings.append(f'iCloud made {", ".join(clashes)} next to {FOLDER}: two devices created the folder; move '
                        'anything inside into Spanish Weave and delete the copies')
    return folder, folder / INBOX, warnings


def write_snapshot(folder, body):
    """Writes folder/snapshot.json atomically: a hidden temp file in the same folder, fsync, os.replace."""
    target = folder / SNAPSHOT
    with no_downloads():
        with contextlib.suppress(FileNotFoundError):
            st = os.lstat(target)
            if not stat.S_ISREG(st.st_mode):
                raise Unavailable(f'{target} is not a regular file; remove it')
        try:
            fd, temporary = tempfile.mkstemp(prefix=TEMP_PREFIX, suffix=TEMP_SUFFIX, dir=folder)  # 0600, O_EXCL
        except PermissionError as error:
            raise _denied(folder, error) from None
        try:
            with os.fdopen(fd, 'wb') as file:
                file.write(body)
                file.flush()
                os.fsync(file.fileno())  # plain fsync; F_FULLFSYNC can stall the whole system
            try:
                os.replace(temporary, target)
            except PermissionError as error:
                raise _denied(folder, error) from None
            temporary = None
        finally:
            if temporary is not None:
                with contextlib.suppress(OSError):
                    os.unlink(temporary)


def read_snapshot_writer(folder):
    """The writer id in an existing snapshot.json, '' when there is none, or None when it can't be read right now."""
    try:
        data = read_file(folder, SNAPSHOT, MAX_SNAPSHOT)
    except FileNotFoundError:
        return ''
    except (NotReady, TooBig, OSError):
        return None
    try:
        writer = json.loads(data.decode('utf-8')).get('writer')
    except (ValueError, UnicodeDecodeError, AttributeError):
        return None
    return writer if isinstance(writer, str) else ''


def remove_stale_temps(folder, now=None):
    """Deletes our own leftover temp files (a crash between mkstemp and os.replace) older than an hour."""
    now = time.time() if now is None else now
    with no_downloads():
        try:
            entries = list(os.scandir(folder))
        except OSError:
            return
        for entry in entries:
            if entry.name.startswith(TEMP_PREFIX) and entry.name.endswith(TEMP_SUFFIX):
                with contextlib.suppress(OSError):
                    st = entry.stat(follow_symlinks=False)
                    if stat.S_ISREG(st.st_mode) and now - st.st_mtime > STALE_TEMP_SECONDS:
                        os.unlink(entry.path)


def list_inbox(inbox, limit=None):
    """(ready, waiting, skipped): ready is [(name, stat)] of downloaded inbox files, oldest first, at most limit (all
    by default: the caller limits how many it reads); waiting is names still only in iCloud; skipped is
    [(name, reason)]. Never downloads anything."""
    ready, waiting, skipped = [], [], []
    uid = os.getuid() if hasattr(os, 'getuid') else None
    with no_downloads():
        try:
            entries = list(os.scandir(inbox))
        except OSError as error:
            if error.errno in NOT_READY:
                return [], [INBOX + '/'], []
            if isinstance(error, PermissionError):
                raise _denied(inbox, error) from None
            raise
        for entry in entries:
            name = entry.name
            if name.startswith('.'):
                if name.endswith('.icloud'):  # older macOS shows evicted files as .name.icloud
                    waiting.append(name[1:-len('.icloud')])
                continue
            if not INBOX_NAME.match(name):
                skipped.append((name, 'unexpected name'))
                continue
            try:
                st = entry.stat(follow_symlinks=False)
            except OSError as error:
                (waiting.append(name) if error.errno in NOT_READY else skipped.append((name, error.strerror)))
                continue
            if not stat.S_ISREG(st.st_mode):
                skipped.append((name, 'not a regular file'))
            elif uid is not None and st.st_uid != uid:
                skipped.append((name, 'owned by another user'))
            elif is_dataless(st) or st.st_size == 0:
                waiting.append(name)
            elif st.st_size > MAX_INBOX_FILE:
                skipped.append((name, f'larger than {MAX_INBOX_FILE // 1024} KB'))
            else:
                ready.append((name, st))
    ready.sort(key=lambda item: (item[1].st_mtime_ns, item[0]))
    return (ready if limit is None else ready[:limit]), waiting, skipped


def read_file(folder, name, max_bytes):
    """Reads a whole file, refusing symlinks, non-regular, dataless and oversized files. Raises NotReady, TooBig or
    OSError (FileNotFoundError when it isn't there)."""
    flags = os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_CLOEXEC', 0) | getattr(os, 'O_NONBLOCK', 0)
    with no_downloads():
        try:
            fd = os.open(folder / name, flags)
        except OSError as error:
            if error.errno in NOT_READY:
                raise NotReady(name) from None
            raise
        try:
            st = os.fstat(fd)
            if not stat.S_ISREG(st.st_mode):
                raise OSError(errno.EINVAL, 'not a regular file', name)
            if is_dataless(st):
                raise NotReady(name)
            if st.st_size > max_bytes:
                raise TooBig(name)
            chunks, total = [], 0
            while True:
                try:
                    chunk = os.read(fd, 65536)
                except OSError as error:
                    if error.errno in NOT_READY:
                        raise NotReady(name) from None
                    raise
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    raise TooBig(name)
                chunks.append(chunk)
        finally:
            os.close(fd)
    return b''.join(chunks)


def _record(raw):
    """One JSON line as a dict, or None. Curly quotes (Smart Punctuation in the Shortcut's text action) are
    straightened first."""
    if len(raw) > MAX_LINE or raw.count(b'[') + raw.count(b'{') > MAX_NESTING:
        return None
    try:
        item = json.loads(raw.decode('utf-8').translate({0x201C: '"', 0x201D: '"', 0x2018: "'", 0x2019: "'"}))
    except (UnicodeDecodeError, ValueError, RecursionError):
        return None
    return item if isinstance(item, dict) else None


def new_records(data, start=0, final_line_ok=False, max_records=swlib.MAX_EVENTS):
    """Parses the JSON lines of data after byte start. Returns (records, end, bad): end is how far the ledger may mark
    the file read. A last line without a newline counts when it is a whole JSON object (Shortcuts may put the newline
    before each appended line, not after it); one that isn't yet waits for a later run, unless final_line_ok (the
    file's size hasn't changed since the last run, so it is finished, and a broken line is bad)."""
    records, bad, pos = [], 0, start
    while pos < len(data) and len(records) < max_records:
        newline = data.find(b'\n', pos)
        line_end = newline + 1 if newline >= 0 else len(data)
        raw = data[pos:line_end].strip()
        item = _record(raw) if raw else None
        if raw and item is None and newline < 0 and not final_line_ok:
            break  # still being written
        pos = line_end
        if item is not None:
            records.append(item)
        elif raw:
            bad += 1
    return records, pos, bad


def request_download(paths):
    """Asks iCloud for evicted inbox files without waiting: a detached child turns downloading on for itself and reads
    one byte of each, so the kernel fetches the whole file. The next run picks them up."""
    paths = [str(p) for p in paths if os.path.isabs(str(p))][:MAX_INBOX_FILES]
    if sys.platform != 'darwin' or not paths:
        return False
    script = ('import ctypes, os, signal, sys\nsignal.alarm(120)\ntry:\n'
              '    ctypes.CDLL(None, use_errno=True).setiopolicy_np(3, 0, 2)\nexcept Exception:\n    pass\n'
              'for path in sys.argv[1:]:\n    try:\n        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)\n'
              '        try:\n            os.read(fd, 1)\n        finally:\n            os.close(fd)\n'
              '    except OSError:\n        pass\n')
    try:
        subprocess.Popen([sys.executable, '-I', '-S', '-c', script, *paths], stdin=subprocess.DEVNULL,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, close_fds=True, start_new_session=True)
        return True
    except OSError:
        return False


# ---- what the phone gets ----

FOLD = str.maketrans({**dict.fromkeys('áàâäã', 'a'), **dict.fromkeys('éèêë', 'e'), **dict.fromkeys('íìîï', 'i'),
                      **dict.fromkeys('óòôöõ', 'o'), **dict.fromkeys('úùûü', 'u'), 'ñ': 'n', 'ç': 'c'})


def phone_fold(text):
    """The Shortcut's normalization, step for step: lowercase, accents and ñ off, apostrophes dropped, anything else
    that isn't a letter or digit becomes a space, trimmed. The accept and reject lists use it, so a typed answer
    compares as the Shortcut folds it."""
    text = str(text).lower().translate(FOLD)
    text = ''.join(c for c in text if not unicodedata.category(c).startswith('M'))  # the Shortcut's \p{M}
    text = re.sub(r"['’]", '', text)
    return re.sub(r'[^a-z0-9]+', ' ', text).strip()


def question(word, way):
    return f'What does "{word["es"]}" mean?' if way == 'recognize' else f'How do you say "{word["en"]}" in Spanish?'


def answers(word, way):
    """(accept, reject) for the phone, folded. Recognize: the gloss's meanings; the false friend a note warns about
    is rejected. Produce: the Spanish, with or without its el/la (un/una belong to a phrase like un poco)."""
    if way == 'recognize':
        accept = {phone_fold(m) for m in swlib.meanings(word['en'])}
        lookalike = re.match(r"not '([^']+)'", swlib.note(word['es']))
        reject = {phone_fold(m) for m in swlib.meanings(lookalike.group(1))} if lookalike else set()
    else:
        accept = {phone_fold(word['es'])}
        if re.match(swlib.ARTICLE, swlib.key(word['es'])):
            accept.add(phone_fold(swlib.bare_fold(word['es'])))
        reject = set()
    accept.discard('')
    return sorted(accept), sorted(reject - accept)


def snapshot(state, day=None):
    """The payload for snapshot.json, without its "made" and "writer" stamps: today's due words, as the quiz would ask
    them."""
    day = day or swlib.today()
    items = []
    for w in swlib.due_reviews(state, day=day, limit=ITEMS):
        way = swlib.direction(w)
        accept, reject = answers(w, way)
        items.append({'es': w['es'], 'en': w['en'], 'hint': w['hint'], 'way': way, 'ask': question(w, way),
                      'accept': accept, 'reject': reject})
    return {'version': VERSION, 'day': day, 'stage': swlib.stage_for(state), 'items': items}


def encode(payload):
    return (json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':')) + '\n').encode('utf-8')


# ---- sync ----

def settings(state):
    return (state.get('prefs') or {}).get('phone') or {}


def enable(state, on=True):
    """Turns phone sync on (with this Mac's writer id) or off. Returns the phone settings."""
    prefs = state.setdefault('prefs', {})
    phone = dict(prefs.get('phone') or {})
    phone['on'] = on
    phone.pop('problem', None)
    phone.setdefault('writer', secrets.token_hex(6))
    phone.pop('sha256', None)  # turning it back on always writes snapshot.json, even if its folder was deleted
    prefs['phone'] = phone
    return phone


def _answer(record, snaps):
    """A phone record as an apply_events event, or None: only a quiz result for a word one of the Mac's recent
    snapshots offered (the "snap" stamp names which). The event is due_only, so it counts only if the word was due on
    its day and has no answer from that day on (swlib.quiz_event): a list from yesterday can't add a second answer for
    a word the Mac quizzed since. A day the Mac can't use (missing, before that snapshot's day as a phone in an
    earlier time zone may write, or not a Gregorian date within OLDEST days up to today, as a phone set to another
    calendar may write) becomes that snapshot's day, the earliest the answer can have been given (this Mac's today
    when an old snapshot entry has no day), so a Mac answer from that day on still wins."""
    if record.get('kind') != 'quiz' or record.get('result') not in ('right', 'wrong'):
        return None
    word, snap, day = record.get('word'), record.get('snap'), record.get('day')
    offered = snaps.get(snap) if isinstance(snap, str) else None
    words, since = (offered.get('words') or (), offered.get('day')) if isinstance(offered, dict) else (offered or (), None)
    if not isinstance(word, str) or word not in words:
        return None
    usable = swlib.event_day(day, swlib.today())
    if usable != day or (isinstance(since, str) and usable < since):  # missing, unreal, too old or in the future
        day = since if isinstance(since, str) else None
    return {'word': word, 'kind': 'quiz', 'result': record['result'], 'day': day, 'due_only': True}


def _read_inbox(state, inbox, phone, report, now):
    ledger = state.setdefault('phone_inbox', {})
    snaps = phone.get('snaps') or {}
    ready, waiting, skipped = list_inbox(inbox)
    report['skipped_files'] += len(skipped)
    names = {name for name, _ in ready} | set(waiting)
    reads = 0
    for name, st in ready:
        entry = ledger.get(name) or {}
        if entry.get('size') == st.st_size and entry.get('mtime_ns') == st.st_mtime_ns and \
                (entry.get('read') == st.st_size or entry.get('rewritten') or entry.get('failed')):
            if entry.get('read') == st.st_size and now - st.st_mtime > KEEP_DAYS * 86400:
                with no_downloads(), contextlib.suppress(OSError):
                    os.unlink(inbox / name)  # read long ago: tidy the folder (iCloud keeps it in Recently Deleted)
                ledger.pop(name, None)
            continue
        if reads >= MAX_INBOX_FILES:
            report['later'] += 1  # read on a later run
            continue
        reads += 1
        try:
            data = read_file(inbox, name, MAX_INBOX_FILE)
        except NotReady:
            waiting.append(name)
            continue
        except PermissionError as error:  # the inbox lists but its files can't be opened: privacy or a sandbox
            raise _denied(inbox, error) from None
        except (TooBig, OSError):
            report['skipped_files'] += 1
            continue
        read = int(entry.get('read', 0))
        if read and (len(data) < read or hashlib.sha256(data[:read]).hexdigest() != entry.get('sha256')):
            # What was already applied changed under us: never apply anything from this file again.
            ledger[name] = dict(entry, size=len(data), mtime_ns=st.st_mtime_ns, rewritten=True)
            report['set_aside'] += 1
            continue
        try:
            records, end, bad = new_records(data, read, final_line_ok=entry.get('size') == len(data))
            events = [e for e in (_answer(r, snaps) for r in records) if e]
            applied, _ = swlib.apply_events(state, events, kinds=('quiz',))
        except Exception:  # input no check foresaw: set this file aside until it changes, and read the rest
            ledger[name] = dict(entry, size=len(data), mtime_ns=st.st_mtime_ns, failed=True)
            report['set_aside'] += 1
            continue
        report['answers'] += applied
        report['ignored'] += len(records) - applied + bad
        ledger[name] = {'size': len(data), 'mtime_ns': st.st_mtime_ns, 'read': end,
                        'sha256': hashlib.sha256(data[:end]).hexdigest()}
    for name in list(ledger):
        if name not in names and not (inbox / name).exists():
            ledger.pop(name)  # deleted on the phone or tidied above
    if waiting:
        request_download([inbox / n for n in waiting if n != INBOX + '/'])
        report['waiting'] = len(waiting)


def sync(state, now=None):
    """Reads the phone's answers into state, then writes a fresh snapshot.json when today's due words changed. The
    caller saves state (swlib.editing), so the answers and the record of which files were read land together. Returns
    a report dict. Raises Unavailable or NotReady when the folder can't be used right now."""
    now = time.time() if now is None else now
    phone = settings(state)
    report = {'answers': 0, 'ignored': 0, 'skipped_files': 0, 'set_aside': 0, 'waiting': 0, 'later': 0,
              'written': False, 'warnings': []}
    if not phone.get('on'):
        report['off'] = True
        return report
    folder, inbox, report['warnings'] = ensure_folders(shortcuts_folder())
    remove_stale_temps(folder, now)
    _read_inbox(state, inbox, phone, report, now)
    payload = snapshot(state)
    digest = hashlib.sha256(encode(payload)).hexdigest()
    stamp = dt.datetime.fromtimestamp(now, dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    if digest != phone.get('sha256') or not _exists(folder / SNAPSHOT):
        made = stamp
        write_snapshot(folder, encode(dict(payload, made=made, writer=phone.get('writer', ''))))
        snaps = dict(phone.get('snaps') or {})
        snaps[made] = {'day': payload['day'], 'words': [item['es'] for item in payload['items']]}
        phone['snaps'] = dict(sorted(snaps.items())[-SNAPS_KEPT:])
        phone['sha256'] = digest
        report['written'] = True
    phone['synced'] = stamp
    phone['last'] = {k: report[k] for k in ('answers', 'ignored', 'waiting', 'skipped_files', 'later')}
    if report['answers']:
        phone['got'] = {'at': stamp, 'answers': report['answers']}  # status keeps showing it after quiet syncs
    phone.pop('problem', None)
    state.setdefault('prefs', {})['phone'] = phone
    report['due'] = len(payload['items'])
    return report


def _exists(path):
    """False only when path is certainly not there; a dataless or unreadable entry counts as there."""
    with no_downloads():
        try:
            os.lstat(path)
        except FileNotFoundError:
            return False
        except OSError:
            pass
    return True


def background_sync():
    """For `sw.py refresh` (the hook's background job): a quiet sync when it is on, skipped when the state is busy. A
    reason it couldn't run is kept for `sw.py phone status`."""
    try:
        with swlib.editing(timeout=5) as state:
            if settings(state).get('on'):
                try:
                    sync(state)
                except (Unavailable, NotReady, TooBig, OSError) as error:
                    state.setdefault('prefs', {}).setdefault('phone', {})['problem'] = str(error)[:300]
                except Exception as error:  # a bug or input no check foresaw: status says so instead of staying quiet
                    state.setdefault('prefs', {}).setdefault('phone', {})['problem'] = (
                        f'sync stopped on an unexpected {type(error).__name__}; /spanish-weave:phone sync shows more')
    except Exception:  # a busy or unreadable state: never surface from a background job
        pass
