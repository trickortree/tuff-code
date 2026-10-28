"""tmusic: music from notes (1.5.0). A tune is written as notes in text, like "C4 E4 G4 C5*2", and Tuff's own synth
(plain Python, so there's nothing to install) turns it into a .wav: 22,050 samples a second, mono. Each tune is made
once and kept in a folder of its own (music_folder), under a name that comes from its notes, so the same notes never
take the time twice, in this run or the next one.

Where it plays:
- TuffCode's Run panel: tmusic sends a music;play message with the file (ide.js handleOsc), and the panel plays it.
- A terminal, and a Build exe app: winsound on Windows, afplay on a Mac (paplay or aplay on Linux).
- A pipe or a file (an agent's tuff_run, the tests), Tuff Engine's preview, and with TUFF_NO_SOUND=1: no sound at
  all, and play() goes on at once.
- A tgame game: game:music(song) and game:sound(song) play it in the game's own page (tuff_tgame.py).

The notes, which are part of the language now (change them only by adding to them):
- C D E F G A B, then # (sharp) or b (flat) if it needs one, then its octave from 0 to 8: C4 is middle C, A4 is 440 Hz.
- . is a rest. Each note and rest is one beat; *2 makes it twice as long and /2 half as long (*1.5 and *3/2 work too).
- C4+E4+G4 is a chord. | is a bar line, only there to make the notes easier to read.
- Drums are a track of their own ("drums"), with kick, snare, hat, clap, tom and crash in place of notes.
"""
import atexit
import base64
import difflib
import hashlib
import json
import math
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import wave
from array import array
from fractions import Fraction
from itertools import accumulate, repeat
from operator import add, mul, sub

RATE = 22050  # samples a second
SYNTH = 1  # the synth's version, part of every file's name: when the way it sounds changes, songs are made again
MAX_SECONDS = 300  # the longest song (5 minutes; a minute of sound is 2.6 MB)
KEEP = 40  # the songs kept in the folder: the newest ones
SPEEDS = (20, 400)  # beats a minute
INSTRUMENTS = ("piano", "chip", "bass", "pluck", "bell", "organ", "flute", "drums")
DRUMS = ("kick", "snare", "hat", "clap", "tom", "crash")
INSTRUMENT_LIST = "piano, chip, bass, pluck, bell, organ, flute and drums"
DRUM_LIST = "kick, snare, hat, clap, tom and crash"
# Instruments people ask for, and the one tmusic has that's closest.
GUESSES = {"guitar": "pluck", "harp": "pluck", "banjo": "pluck", "synth": "chip", "8bit": "chip", "8-bit": "chip",
           "retro": "chip", "square": "chip", "keys": "piano", "keyboard": "piano", "drum": "drums", "kit": "drums",
           "drumkit": "drums", "percussion": "drums", "beat": "drums", "beats": "drums", "chime": "bell", "chimes": "bell",
           "xylophone": "bell", "glockenspiel": "bell", "recorder": "flute", "whistle": "flute", "bass guitar": "bass"}
LETTERS = {"c": 0, "d": 2, "e": 4, "f": 5, "g": 7, "a": 9, "b": 11}
NOTE = re.compile(r"([A-Ga-g])([#b]?)(-?\d+)")
SHARP_AFTER = re.compile(r"([A-Ga-g])(-?\d+)([#b]+)")  # C4#: the sharp after the octave
LENGTH = re.compile(r"([*/])(\d+(?:\.\d+)?)")
NOTES_HELP = ("A note is a letter from A to G, then # (sharp) or b (flat) if it needs one, then its octave from 0 to 8, "
              "like C4 (middle C), F#3 or Bb5. A . is a rest.")


class MusicError(Exception):
    """A mistake in what a program asked tmusic for. at: where it starts in the notes' text, for the checker."""

    def __init__(self, msg, at=None):
        super().__init__(msg)
        self.msg, self.at = msg, at


def example(who, drums=False):
    notes = "kick hat snare hat" if drums else "C4 E4 G4"
    if who == "tmusic.play":
        return f'tmusic.play("{notes}"' + (', "drums")' if drums else ")")
    return f'{who}("{"drums" if drums else "piano"}", "{notes}")'


# ---------------------------------------------------------------- reading notes

def read_notes(text, drums=False, who="tmusic.play"):
    """The notes in text, as (events, beats): each event is (start, beats, pitches), counted in beats (exact
    fractions), and pitches are MIDI numbers (60 is C4) or drum names. A rest takes time and makes no event."""
    words = [(m.start(), m.group()) for m in re.finditer(r"[^\s|]+", text)]
    if not words:
        raise MusicError(f"{who} needs some notes, like {example(who, drums)}.", 0)
    events, at = [], Fraction(0)
    for n, (pos, word) in enumerate(words, 1):
        label = f'"{word}"' + (f" (note {n})" if len(words) > 1 else "")
        try:
            beats, pitches = read_word(word, label, drums, who)
        except MusicError as err:
            err.at = pos
            raise
        if pitches:
            events.append((at, beats, pitches))
        at += beats
    return events, at


def read_word(word, label, drums, who):
    """One note, chord, rest or drum, with its length after it: (beats, pitches)."""
    if "," in word:
        raise MusicError(f'{label}: put spaces between notes, not commas, like "C4 E4 G4".')
    cut = re.search(r"[*/]", word)
    head, tail = (word[:cut.start()], word[cut.start():]) if cut else (word, "")
    beats, i = Fraction(1), 0
    while i < len(tail):
        if tail[i] not in "*/":
            if re.match(r"[A-Ga-g.]", tail[i:]):
                raise MusicError(f'{label}: put a space between two notes, like "{word[:cut.start() + i]} {tail[i:]}".')
            raise MusicError(f"{label} isn't a note. {NOTES_HELP}")
        m = LENGTH.match(tail, i)
        if not m:
            raise MusicError(f"{label}: put a number after the {tail[i]}, like C4*2 (twice as long) or C4/2 (half as long).")
        k = Fraction(m.group(2))
        if k == 0:
            raise MusicError(f"{label} would last 0 beats. Use a number above 0, like C4*2 or C4/2.")
        beats = beats * k if m.group(1) == "*" else beats / k
        i = m.end()
    if not head:
        raise MusicError(f"{label} needs a note before the {tail[0]}, like C4{tail[:2]} (or .{tail[:2]} for a rest).")
    if head == ".":
        return beats, ()
    parts = head.split("+")
    if len(parts) > 1 and not all(parts):
        raise MusicError(f"{label}: a chord needs a note on each side of its +, like C4+E4+G4.")
    if len(parts) > 1 and "." in parts:
        raise MusicError(f"{label}: a rest (.) can't be part of a chord.")
    return beats, tuple(read_pitch(p, label, drums, who) for p in parts)


def read_pitch(part, label, drums, who):
    """A note's MIDI number, or a drum's name."""
    low = part.lower()
    if drums:
        if low in DRUMS:
            return low
        if NOTE.fullmatch(part):
            raise MusicError(f"{label} is a note, but this is a drums track. Drums are {DRUM_LIST} (and . for a rest).")
        hint = difflib.get_close_matches(low, DRUMS, n=1, cutoff=0.6)
        raise MusicError(f"{label} isn't a drum." + (f' Did you mean "{hint[0]}"?' if hint else "") + f" Drums are {DRUM_LIST}.")
    if low in DRUMS:
        raise MusicError(f"{label} is a drum. Drums go in a track of their own, like {example(who, True)}.")
    m = NOTE.fullmatch(part)
    if m:
        octave = int(m.group(3))
        if not 0 <= octave <= 8:
            raise MusicError(f"{label}: octaves go from 0 to 8 (C4 is middle C), so there's no {part}.")
        return 12 * (octave + 1) + LETTERS[m.group(1).lower()] + {"#": 1, "b": -1, "": 0}[m.group(2)]
    m = SHARP_AFTER.fullmatch(part)
    if m and len(m.group(3)) == 1:
        octave = int(m.group(2))
        name = m.group(1) + m.group(3)
        if not 0 <= octave <= 8:
            raise MusicError(f"{label} has its {m.group(3)} after the octave (it goes before, like {name}4), and there's no "
                             f"octave {octave}: octaves go from 0 to 8 (C4 is middle C).")
        raise MusicError(f"{label} has its {m.group(3)} after the octave: write {name}{octave}.")
    if m or re.fullmatch(r"[A-Ga-g][#b]{2,}-?\d*", part):
        raise MusicError(f"{label} has more than one # or b. A note has one at most, like C#4 or Db4.")
    if re.fullmatch(r"[A-Ga-g][#b]?", part):
        raise MusicError(f"{label} needs its octave after it, like {part}4 (C4 is middle C).")
    if part.endswith(".") and NOTE.fullmatch(part[:-1]):
        raise MusicError(f"{label} isn't a note. For a note one and a half times as long, write {part[:-1]}*1.5.")
    raise MusicError(f"{label} isn't a note. {NOTES_HELP}")


def find_instrument(name):
    """The instrument called name (in any case), or a MusicError that lists them."""
    low = " ".join(str(name).lower().split())
    if low in INSTRUMENTS:
        return low
    hint = GUESSES.get(low) or next(iter(difflib.get_close_matches(low, INSTRUMENTS, n=1, cutoff=0.6)), None)
    raise MusicError(f'tmusic doesn\'t have the instrument "{name}".' + (f' Did you mean "{hint}"?' if hint else "")
                     + f" Instruments: {INSTRUMENT_LIST}.")


def is_instrument(text):
    return isinstance(text, str) and " ".join(text.lower().split()) in INSTRUMENTS


def speed_problem(bpm, who):
    """What's wrong with a speed in beats a minute (a number), or None."""
    if not SPEEDS[0] <= bpm <= SPEEDS[1]:
        shown = int(bpm) if bpm == int(bpm) else bpm
        return (f"{who} can be from {SPEEDS[0]} to {SPEEDS[1]} beats a minute (120 is a usual speed), so {shown} is too "
                f"{'slow' if bpm < SPEEDS[0] else 'fast'}.")
    return None


def not_a_number(who, what, shown):
    """For a speed ("speed") or a track's volume that isn't a number; shown is what it is ("text", "a list"...)."""
    if what == "speed":
        fix = "tmusic.song(120)" if who == "tmusic.song" else 'tmusic.play("C4 E4 G4", "piano", 120)'
        return f"{who} needs a speed in beats a minute, as a number, like {fix}, not {shown}."
    return f'A track\'s volume is a number from 0 to 100, like song:track("piano", "C4 E4 G4", 50), not {shown}.'


def not_notes(who, shown):
    return f"{who} needs the notes as text, like {example(who)}, not {shown}."


def not_an_instrument(who, shown):
    if who == "tmusic.play":
        return f'tmusic.play\'s instrument is its name as text, like tmusic.play("C4 E4 G4", "piano"), not {shown}.'
    return f"{who} needs the instrument's name as text first, like {example(who)}, not {shown}."


def volume_problem(volume):
    if not 0 <= volume <= 100:
        shown = int(volume) if volume == int(volume) else volume
        return f"A track's volume goes from 0 to 100 (100 if you leave it out), not {shown}."
    return None


def save_problem(path):
    if not path.strip().lower().endswith(".wav"):
        return f'song:save makes a .wav file, like song:save("theme.wav"), not "{path}".'
    return None


def too_long(beats, bpm, who):
    seconds = float(beats * 60 / Fraction(bpm))
    if seconds > MAX_SECONDS:
        whole = round(seconds)
        shown = f"{whole // 60} minutes {whole % 60} seconds" if whole >= 60 else f"{whole} seconds"
        return f"These notes would play for {shown}: {who} makes songs up to {MAX_SECONDS // 60} minutes long."
    return None


# ---------------------------------------------------------------- the synth

TAU = 2 * math.pi
NOISE = None  # two seconds of noise for the drums, the same every time
DRUM_SECONDS = {"kick": 0.5, "snare": 0.35, "hat": 0.15, "clap": 0.4, "tom": 0.6, "crash": 1.5}
GAIN = {"piano": 0.55, "chip": 0.45, "bass": 0.65, "pluck": 0.6, "bell": 0.45, "organ": 0.3, "flute": 0.45,
        "kick": 0.9, "snare": 0.6, "hat": 0.3, "clap": 0.5, "tom": 0.7, "crash": 0.35}
ATTACK = {"flute": 0.05, "organ": 0.01, "drums": 0.001}  # seconds to fade in (the rest: 0.003); every note fades out in 0.012


def sines(freq, n, parts):
    """n samples of sine waves at freq times each ratio, with their amplitudes: parts is [(ratio, amplitude)]."""
    sin, out = math.sin, None
    for ratio, amp in parts:
        w = TAU * freq * ratio / RATE
        if w >= math.pi * 0.95:  # above what 22,050 samples a second can hold: it would sound as another note
            continue
        wave_ = [amp * sin(w * i) for i in range(n)]
        out = wave_ if out is None else list(map(add, out, wave_))
    return out if out is not None else [0.0] * n


def decay(n, seconds):
    """1 fading to a third (1/e) after `seconds`, the way a struck string or a bell fades."""
    r = math.exp(-1.0 / (seconds * RATE))
    return list(accumulate(repeat(r, n - 1), mul, initial=1.0)) if n else []


def piano(freq, n):
    slow = min(2.5, max(0.25, 1.1 * math.sqrt(261.63 / freq)))  # low notes ring longer
    body = map(mul, sines(freq, n, ((1, 1.0), (2, 0.42))), decay(n, slow))
    ring = map(mul, sines(freq, n, ((3, 0.2), (4, 0.1), (5, 0.05))), decay(n, slow / 4))
    return list(map(add, body, ring))


def chip(freq, n):  # a square wave, like old game consoles
    k = freq / RATE
    return [0.5 if (i * k) % 1.0 < 0.5 else -0.5 for i in range(n)]


def bass(freq, n):
    return list(map(mul, sines(freq, n, ((1, 1.0), (2, 0.4), (3, 0.15))), decay(n, 0.9)))


def pluck(freq, n, seed):
    """A plucked string (Karplus-Strong): a burst of noise, played over and over and softened each time round. Each
    sample mixes two from a period ago, in the share that makes the period exactly RATE / freq long (in tune)."""
    length = RATE / freq
    period = max(2, int(length))
    late = length - period  # how much of the one before that goes in
    keep = 0.996 if freq < 600 else 0.99
    now, before = (1 - late) * keep, late * keep
    rnd = random.Random(seed)  # its own: the program's random() numbers stay as they were
    out = [rnd.uniform(-1.0, 1.0) for _ in range(period + 1)]
    for i in range(period + 1, n):
        out.append(out[i - period] * now + out[i - period - 1] * before)
    return out[:n]


def bell(freq, n):
    body = map(mul, sines(freq, n, ((1, 1.0), (2, 0.35))), decay(n, 1.6))
    ring = map(mul, sines(freq, n, ((2.76, 0.5), (5.4, 0.25), (8.93, 0.12))), decay(n, 0.35))
    return list(map(add, body, ring))


def organ(freq, n):
    return sines(freq, n, ((1, 1.0), (2, 0.55), (3, 0.3), (4, 0.15)))


def flute(freq, n):  # a soft tone with a gentle wobble (vibrato, 5 times a second)
    sin, w, v, d = math.sin, TAU * freq / RATE, TAU * 5.0 / RATE, 0.0012 * freq
    return [sin(w * i + d * sin(v * i)) + 0.1 * sin(2 * w * i) for i in range(n)]


def noise():
    global NOISE
    if NOISE is None:
        rnd = random.Random(1234)
        NOISE = [rnd.uniform(-1.0, 1.0) for _ in range(2 * RATE)]
    return NOISE


def drum(name, n):
    m = min(n, int(RATE * DRUM_SECONDS[name]))
    sin, exp, t = math.sin, math.exp, 1.0 / RATE
    if name in ("kick", "tom"):  # a thump that falls in pitch: 150 Hz to 45 (a tom: 200 to 110)
        low, drop, quick, fade = (45.0, 105.0, 0.03, 0.16) if name == "kick" else (110.0, 90.0, 0.06, 0.22)
        out = [sin(TAU * (low * i * t + drop * quick * (1 - exp(-i * t / quick)))) for i in range(m)]
        out = list(map(mul, out, decay(m, fade)))
    elif name == "snare":  # a rattle (noise) over a short tone
        tone = [sin(TAU * 185.0 * i * t) for i in range(m)]
        out = [0.75 * x * a + 0.45 * y * b for x, y, a, b in zip(noise(), tone, decay(m, 0.08), decay(m, 0.06))]
    else:  # hat, clap and crash: noise with its low sounds taken out
        hiss = list(map(sub, noise()[1:m + 1], noise()[:m]))
        if name == "clap":  # three quick claps, then the room
            shape = [exp(-((i * t) % 0.011) / 0.003) if i * t < 0.033 else 0.55 * exp(-(i * t - 0.033) / 0.08) for i in range(m)]
        else:
            shape = decay(m, 0.025 if name == "hat" else 0.5)
        out = [0.5 * x * s for x, s in zip(hiss, shape)]
    return out + [0.0] * (n - m)


VOICES = {"piano": piano, "chip": chip, "bass": bass, "bell": bell, "organ": organ, "flute": flute}


def voice(instrument, pitch, n, gain):
    """One note's samples (n of them) at this loudness, faded in and out so it doesn't click."""
    if instrument == "drums":
        s = drum(pitch, n)
    else:
        freq = 440.0 * 2 ** ((pitch - 69) / 12)
        s = pluck(freq, n, pitch) if instrument == "pluck" else VOICES[instrument](freq, n)
    a, f = min(n // 2, int(ATTACK.get(instrument, 0.003) * RATE)), min(n // 2, int(0.012 * RATE))
    for i in range(a):
        s[i] *= i / a
    for i in range(f):
        s[n - 1 - i] *= i / f
    g = gain * GAIN[pitch if instrument == "drums" else instrument]
    return array("f", [x * g for x in s])


def render(tracks, bpm):
    """A song's sound: 16-bit samples (an array of "h"). tracks are (instrument, loudness from 0 to 1, events), and
    every track starts at the beginning. The loudest moment is turned down to 85% of the most a .wav holds."""
    per_beat = Fraction(RATE * 60) / Fraction(bpm)
    total = max((round(beats * per_beat) for _i, _v, _e, beats in tracks), default=0)
    mix = array("f", [0.0]) * total
    made = {}  # (instrument, pitch, samples, loudness) -> the note's samples: tunes repeat their notes a lot
    for instrument, loud, events, _beats in tracks:
        for start, beats, pitches in events:
            a, b = round(start * per_beat), round((start + beats) * per_beat)
            if b <= a:
                continue
            gain = loud / math.sqrt(len(pitches))  # a chord as loud as one note, about
            for p in pitches:
                key = (instrument, p, b - a, gain)
                if key not in made:
                    made[key] = voice(instrument, p, b - a, gain)
                mix[a:b] = array("f", map(add, mix[a:b], made[key]))
    peak = max(map(abs, mix), default=0.0)
    k = 32767 * (0.85 / peak if peak > 0.85 else 1.0)
    return array("h", map(int, map(mul, mix, repeat(k))))  # (one sample at a time: a list of them all is big)


def wav_bytes(pcm):
    """A .wav file's bytes for these samples (16-bit, mono, 22,050 a second)."""
    import io
    if sys.byteorder == "big":  # a .wav's samples are little-endian
        pcm = array("h", pcm)
        pcm.byteswap()
    out = io.BytesIO()
    with wave.open(out, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(pcm.tobytes())
    return out.getvalue()


def music_folder():
    """Where songs' .wav files are kept: TUFF_MUSIC_DIR, or a tuff-music folder in the computer's temporary folder."""
    folder = os.path.abspath(os.environ.get("TUFF_MUSIC_DIR") or os.path.join(tempfile.gettempdir(), "tuff-music"))
    try:
        os.makedirs(folder, exist_ok=True)
    except OSError as exc:
        raise MusicError(f"tmusic couldn't make its folder for songs ({folder}): {exc.strerror or exc}.")
    return folder


def tidy(folder, keep):
    """Only the newest KEEP songs stay in the folder (and never the one just made or played)."""
    try:
        songs = [os.path.join(folder, f) for f in os.listdir(folder) if f.startswith("song-") and f.endswith(".wav")]
        songs.sort(key=os.path.getmtime, reverse=True)
        for old in songs[KEEP:]:
            if os.path.normcase(old) != os.path.normcase(keep):
                os.remove(old)
    except OSError:
        pass  # another program has one open, or it's gone already: next time


# ---------------------------------------------------------------- where the sound goes

class Player:
    """Plays songs' files: in TuffCode's Run panel, with the computer's own player, or nowhere (see where)."""

    def __init__(self, rt):
        self.rt = rt
        self.tuff = sys.modules.get(type(rt).__module__)  # tuff.py (__main__ when it's run directly)
        self.mode = self.where()
        self.loops = set()  # the songs playing over and over
        self.now = None  # winsound plays one sound at a time: this one
        self.looping = None  # ...and the loop it played last (its song's id and file), to bring back after a tune
        self.running = {}  # song id -> (its stop event, the afplay, paplay or aplay playing it now)
        if self.mode not in (None, "ide"):
            rt.on_finish(self.finish)
            atexit.register(self.stop_loops)

    def where(self):
        if os.environ.get("TUFF_SCENE") == "1" or os.environ.get("TUFF_NO_SOUND") == "1":
            return None
        if getattr(self.tuff, "IDE", False):
            return "ide"
        try:
            terminal = sys.stdout is not None and sys.stdout.isatty()
        except (AttributeError, ValueError, OSError):
            terminal = False
        if not terminal and not getattr(self.tuff, "WINDOWED", False):
            return None  # a pipe or a file: an agent's tuff_run, a test, > out.txt
        if sys.platform == "win32":
            return "winsound"
        for cmd in (("afplay",) if sys.platform == "darwin" else ("paplay", "aplay")):
            if shutil.which(cmd):
                return cmd
        return None

    def play(self, key, path, seconds, loop=False):
        """Plays the file (in place of what the song played before). Once through, it waits until it ends (wait()'s
        way, so windows keep drawing)."""
        if self.mode != "ide":  # (the Run panel does this itself)
            self.stop(key)
        if self.mode == "ide":
            shown = base64.b64encode(path.encode("utf-8")).decode("ascii")
            self.rt.interp.console.write(f"\x1b]tuff;music;play;{key};{shown};{1 if loop else 0}\x07")
        elif self.mode == "winsound":
            self.winsound(path, loop)
            self.now = key
            if loop:
                self.looping = (key, path)
        else:
            self.command(key, path, loop)
        if loop:
            self.loops.add(key)
            return
        self.rt.interp.b_wait(seconds)
        # winsound plays one sound at a time, so a tune played once cut a loop off: the loop comes back
        back = self.looping if self.mode == "winsound" and self.now == key else None
        if back and back[0] in self.loops:
            self.winsound(back[1], True)
            self.now = back[0]

    def winsound(self, path, loop):
        import winsound
        flags = winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT
        winsound.PlaySound(path, flags | (winsound.SND_LOOP if loop else 0))

    def command(self, key, path, loop):
        """afplay (or paplay, aplay) plays the file on a thread of its own, again and again for a loop."""
        stop = threading.Event()
        self.running[key] = (stop, None)

        def run():
            try:
                while not stop.is_set():
                    try:
                        p = subprocess.Popen([self.mode, path], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                             stderr=subprocess.DEVNULL)
                    except OSError:
                        return
                    self.running[key] = (stop, p)
                    if stop.is_set():  # stopped while it was starting
                        p.terminate()
                    p.wait()
                    if not loop:
                        return
            finally:
                if self.running.get(key, (None,))[0] is stop:  # (not the song's next play, started meanwhile)
                    self.running.pop(key, None)
        threading.Thread(target=run, name="tmusic", daemon=True).start()

    def stop(self, key=None):
        if self.mode == "ide":
            self.rt.interp.console.write(f"\x1b]tuff;music;stop;{key or 'all'}\x07")
        elif self.mode == "winsound":
            if key is None or self.now == key:
                import winsound
                winsound.PlaySound(None, 0)
                self.now = None
        else:
            for k in ([key] if key else list(self.running)):
                stop, p = self.running.get(k, (None, None))  # (its thread takes it out of running when it ends)
                if stop is not None:
                    stop.set()
                if p is not None and p.poll() is None:
                    p.terminate()
        if key:
            self.loops.discard(key)
        else:
            self.loops.clear()

    def stop_loops(self):
        for key in list(self.loops):
            self.stop(key)

    def finish(self):
        """At the end of the program the loops stop (a tune played once has ended already). Functions added to the
        program's end after this one (a game's window, which runs until it's closed) go first: this one goes to the
        end of the list again until it's the last."""
        hooks = self.rt.finish_hooks
        if hooks and hooks[-1] != self.finish:
            hooks.append(self.finish)
            return
        self.stop_loops()


# ---------------------------------------------------------------- what Tuff calls

class Song:
    """tmusic.song(120): tracks of notes, each with its instrument, that play together."""

    def __init__(self, lib, bpm, key=None):
        self.lib, self.bpm = lib, bpm
        self.tracks = []  # (instrument, loudness from 0 to 1, events, beats)
        self.key = key
        self.file = None  # its .wav, once it's made
        if lib is not None:
            self.native = lib.rt.native("song", self.methods(), self.show)
            self.native.song = self  # so tgame's game:music(song) can find it

    def methods(self):
        return {"track": self.track, "play": self.play, "loop": self.loop, "stop": self.stop, "save": self.save,
                "length": self.length}

    def show(self, nested=False):
        return f"<song: {len(self.tracks)} track{'' if len(self.tracks) == 1 else 's'}, {self.length()} seconds>"

    def error(self, msg):
        return self.lib.rt.error(msg)

    def add(self, who, instrument, notes, volume=100):
        rt = self.lib.rt
        instrument, notes = rt.plain(instrument), rt.plain(notes)
        if not isinstance(instrument, str):
            raise self.error(not_an_instrument(who, rt.what(instrument)))
        if not isinstance(notes, str):
            raise self.error(not_notes(who, rt.what(notes)))
        volume = rt.plain(volume)
        if isinstance(volume, bool) or not isinstance(volume, (int, float)):
            raise self.error(not_a_number(who, "volume", rt.what(volume)))
        try:
            name = find_instrument(instrument)
            events, beats = read_notes(notes, name == "drums", who)
        except MusicError as err:
            raise self.error(err.msg)
        problem = volume_problem(volume) or too_long(beats, self.bpm, who)
        if problem:
            raise self.error(problem)
        self.tracks.append((name, volume / 100, events, beats))
        self.file = None

    def track(self, instrument, notes, volume=100):
        rt = self.lib.rt
        if is_instrument(rt.plain(notes)) and not is_instrument(rt.plain(instrument)):
            raise self.error('song:track takes the instrument first, then the notes, like song:track("piano", "C4 E4 G4").')
        self.add("song:track", instrument, notes, volume)
        return self.native

    def beats(self):
        return max((t[3] for t in self.tracks), default=Fraction(0))

    def length(self):
        """How long the song plays, in seconds."""
        seconds = round(float(self.beats() * 60 / Fraction(self.bpm)), 3)
        return int(seconds) if seconds == int(seconds) else seconds

    def ready(self):
        if not self.tracks:
            raise self.error('This song has no tracks yet. Add one first, like song:track("piano", "C4 E4 G4").')

    def name(self):
        """The song's file name, from everything that makes its sound: the same notes always get the same file."""
        made = [SYNTH, RATE, str(Fraction(self.bpm)),
                [[i, v, [[str(s), str(b), list(p)] for s, b, p in e], str(beats)] for i, v, e, beats in self.tracks]]
        return "song-" + hashlib.sha256(json.dumps(made).encode("utf-8")).hexdigest()[:20] + ".wav"

    def wav(self):
        """The song's .wav file, made the first time it's needed (or found already made, by an earlier run)."""
        self.ready()
        if self.file and os.path.isfile(self.file):
            return self.file
        try:
            folder = music_folder()
        except MusicError as err:
            raise self.error(err.msg)
        path = os.path.join(folder, self.name())
        try:
            if os.path.isfile(path):
                os.utime(path)  # played again: one of the newest, so tidy keeps it
            else:
                data = wav_bytes(render(self.tracks, self.bpm))
                part = f"{path}.{os.getpid()}.part"
                with open(part, "wb") as f:
                    f.write(data)
                os.replace(part, path)
                tidy(folder, path)
        except OSError as exc:
            raise self.error(f"tmusic couldn't make the song's sound file: {exc.strerror or exc}.")
        self.file = path
        return path

    def play(self):
        """Plays the song once, and waits until it ends."""
        self.ready()
        out = self.lib.player()
        if out.mode is not None:  # (nowhere to play it: a pipe, a test, Tuff Engine's preview)
            out.play(self.key, self.wav(), self.length())
        return None

    def loop(self):
        """Plays the song over and over, and the program goes on: until song:stop() or the end of the program."""
        self.ready()
        out = self.lib.player()
        if out.mode is not None:
            out.play(self.key, self.wav(), self.length(), loop=True)
        return None

    def stop(self):
        out = self.lib.out
        if out is not None and out.mode is not None:
            out.stop(self.key)
        return None

    def save(self, file):
        rt = self.lib.rt
        file = rt.plain(file)
        if not isinstance(file, str) or not file.strip():
            raise self.error('song:save needs a file name, like song:save("theme.wav").')
        problem = save_problem(file)
        if problem:
            raise self.error(problem)
        self.ready()
        if getattr(rt.interp, "writes", True) is False:  # Tuff Engine's preview, and tuff_run for AI agents
            return None
        target = rt.save_path(file.strip())  # (a built app's own folder: see tuff.py's Runtime.save_path)
        try:
            folder = os.path.dirname(target)
            if folder:
                os.makedirs(folder, exist_ok=True)
            shutil.copyfile(self.wav(), target)
        except OSError as exc:
            raise self.error(f"Couldn't save {file.strip()}: {exc.strerror or exc}.")
        return None


class Lib:
    def __init__(self, rt):
        self.rt = rt
        self.songs = 0
        self.out = None  # the Player, made the first time something plays

    def player(self):
        if self.out is None:
            self.out = Player(self.rt)
        return self.out

    def speed(self, bpm, who):
        bpm = self.rt.plain(bpm)
        if isinstance(bpm, bool) or not isinstance(bpm, (int, float)):
            raise self.rt.error(not_a_number(who, "speed", self.rt.what(bpm)))
        problem = speed_problem(bpm, who)
        if problem:
            raise self.rt.error(problem)
        return bpm

    def new_song(self, bpm, who):
        self.songs += 1
        return Song(self, self.speed(bpm, who), f"s{self.songs}")

    def song(self, bpm=120):
        return self.new_song(bpm, "tmusic.song").native

    def play(self, notes, instrument="piano", bpm=120):
        """Plays some notes once, and waits until they end."""
        own = getattr(self.rt.plain(notes), "song", None)
        if own is not None:  # tmusic.play(song)
            return own.play()
        if is_instrument(self.rt.plain(notes)) and not is_instrument(self.rt.plain(instrument)):
            raise self.rt.error('tmusic.play takes the notes first, then the instrument, like tmusic.play("C4 E4 G4", "piano").')
        song = self.new_song(bpm, "tmusic.play")
        song.add("tmusic.play", instrument, notes)
        return song.play()


def make_library(rt):
    lib = Lib(rt)
    return {"play": rt.builtin("tmusic.play", lib.play), "song": rt.builtin("tmusic.song", lib.song)}


def tables():
    """For tuff.py --check, without making or playing a sound: tmusic's functions and a song's methods."""

    class FakeRt:
        def builtin(self, name, fn):
            return fn

    return {"lib": make_library(FakeRt()), "kinds": {"song": Song(None, 120).methods()}}
