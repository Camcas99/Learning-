#!/usr/bin/env python3
"""Chrome native messaging host for the Spanish Weave extension (Python 3.9+, standard library only).

Messages (JSON, 4-byte native-endian length prefix, one per line of conversation):
  {"type": "ping"}                      -> {"ok": true, "host": 1}
  {"type": "state"}                     -> {"ok": true, "version", "stage", "paused", "words": [{es, en, hint, status}],
                                            "prefs": {"extension_sites"?: "all" | "ask"} (absent means "all"),
                                            "geminiKey"?: stored key if setup saved one}
  {"type": "events", "events": [{"word", "kind": "seen"|"flip"|"peek", "day"?}]}
                                        -> {"ok": true, "applied": n, "skipped": m}
"""
import datetime as dt
import json
from pathlib import Path
import re
import struct
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import swlib  # noqa: E402

MAX_EVENTS = 500
MAX_WORD = 64       # longest word looked up (the longest listed phrase is far shorter)
OLDEST = 60         # days back an event's day may be; older ones are skipped
LOCK_TIMEOUT = 10   # seconds to wait for state.lock before replying with an error
DAY = re.compile(r'\d{4}-\d{2}-\d{2}', re.ASCII)


def event_day(value, today):
    """The day to apply an event on: today when it has none or one in the future, None (skip it) when it isn't a real
    YYYY-MM-DD date within OLDEST days, so a bad day is never saved to trip later batches."""
    if value is None:
        return today
    if not isinstance(value, str) or not DAY.fullmatch(value):
        return None
    try:
        age = (dt.date.fromisoformat(today) - dt.date.fromisoformat(value)).days
    except ValueError:
        return None
    return None if age > OLDEST else min(value, today)


def read_message(stream):
    header = stream.read(4)
    if len(header) < 4:
        return None
    size = struct.unpack('=I', header)[0]
    if size > 1024 * 1024:
        raise ValueError('message too large')
    return json.loads(stream.read(size).decode('utf-8'))


def write_message(stream, message):
    data = json.dumps(message, ensure_ascii=False).encode('utf-8')
    stream.write(struct.pack('=I', len(data)))
    stream.write(data)
    stream.flush()


def handle(message):
    kind = message.get('type') if isinstance(message, dict) else None
    if kind == 'ping':
        return {'ok': True, 'host': 1}
    if kind == 'state':
        with swlib.editing(timeout=LOCK_TIMEOUT) as state:
            pass  # applies today's promotion before answering
        reply = dict(swlib.public_state(state), ok=True, prefs=state.get('prefs') or {})
        key = swlib.home() / 'gemini_key'
        if key.exists():
            reply['geminiKey'] = key.read_text().strip()
        return reply
    if kind == 'events':
        events = message.get('events')
        if not isinstance(events, list):
            return {'ok': False, 'error': 'events must be a list'}
        today, valid = swlib.today(), []
        for event in events[:MAX_EVENTS]:
            if not isinstance(event, dict) or event.get('kind') not in ('seen', 'flip', 'peek'):
                continue
            word, day = event.get('word'), event_day(event.get('day'), today)
            if isinstance(word, str) and len(word) <= MAX_WORD and day:
                valid.append((day, word, event['kind']))
        applied = 0
        with swlib.editing(timeout=LOCK_TIMEOUT) as state:
            for day, word, kind in sorted(valid, key=lambda e: e[0]):  # oldest first, as they happened
                try:
                    applied += swlib.apply_event(state, word, kind, day)
                except (ValueError, TypeError, KeyError):
                    pass  # one bad word state never sinks the batch
        return {'ok': True, 'applied': applied, 'skipped': len(events) - applied}
    return {'ok': False, 'error': 'unknown message type'}


def main():
    stdin, stdout = sys.stdin.buffer, sys.stdout.buffer
    while True:
        try:
            message = read_message(stdin)
        except (ValueError, RecursionError) as error:  # not JSON, too big, or nested too deep to parse
            write_message(stdout, {'ok': False, 'error': str(error)})
            return
        if message is None:
            return
        try:
            reply = handle(message)
        except Exception as error:  # report, don't crash Chrome's port
            reply = {'ok': False, 'error': f'{error.__class__.__name__}: {error}'}
        write_message(stdout, reply)


if __name__ == '__main__':
    main()
