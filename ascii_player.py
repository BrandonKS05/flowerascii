#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = ["numpy", "opencv-python-headless"]
# ///
r"""ascii_player.py - play a video in the terminal as glowing, colored ASCII art.

    uv run ascii_player.py bloom.mp4        (Ctrl+C or q quits; --once = one pass)
    uv run ascii_player.py bloom.mp4 --cols 140 --bg    (wider picture, tinted cells)
    uv run ascii_player.py bloom.mp4 --vase-color c8d8f0    (or --no-vase, --no-crop)
    uv run ascii_player.py bloom.mp4 --flowers 1    (no bouquet: only the video's own)
    uv run ascii_player.py bloom.mp4 --no-sprinkles

(or any Python that has numpy and OpenCV: .venv/bin/python ascii_player.py bloom.mp4)

The video is a picture about 110 characters wide: along an edge a cell is a stroke
that follows it (- / | \ _ ( )), everywhere else a glyph picked by brightness, and
each is tinted with its pixel's 24-bit color, on pure black.  A subject on a black
backdrop is cropped to, so that it fills the picture, and made a bouquet: the same
flower seven times, standing all around a fluted vase and leaning out of it, each in
a color and of a size of its own (the leaves stay green; the pale one is the
biggest).  The show starts with the vase alone.  White specks drip down on it, and
one flower after the other grows out of it and blooms, slowly, each in its own time;
not all open as far.  All the while the bouquet turns, once in ten seconds.
Flowers and vase are painted into every frame before the conversion; the specks
are characters of their own, on top.
The rest of the screen is a fake editor pane that scrolls through this very file
while a highlighted "current line" walks through Renderer.convert() and draw(): it
is below the picture, or beside it where a low, wide window shows more that way.
The picture wants room, 110 x 49 characters for a bouquet in its vase: the status
bar says so when the window is too small to show all of it.

The terminal must know 24-bit color and show colors as they are sent: VS Code, for
one, brightens dim text unless "terminal.integrated.minimumContrastRatio" is 1.
A file with a variable frame rate is played at its average rate.
"""
import argparse
import builtins
import collections
import io
import keyword
import os
import random
import select
import signal
import struct
import sys
import time
import tokenize
import unicodedata

try:                                 # POSIX terminal control (absent on Windows)
    import fcntl
    import termios
except ImportError:
    termios = None

if __name__ == "__main__":           # until Terminal.enter() takes over, Ctrl+C simply
    signal.signal(signal.SIGINT, lambda *_: sys.exit())     # ends us: no traceback

os.environ.setdefault("OPENCV_LOG_LEVEL", "SILENT")     # no decoder chatter on screen
os.environ.setdefault("OPENCV_FFMPEG_LOGLEVEL", "-8")
try:
    import cv2  # noqa: E402
    import numpy as np  # noqa: E402
except ImportError as error:
    sys.exit(f"ascii_player: {error}.  Run `uv run ascii_player.py VIDEO`, or use a "
             "Python that has numpy and opencv-python-headless installed.")

TITLE = "ascii_player.py — Renderer.convert() + draw()"

# Fill ramp, sparse -> dense.  The order is measured, not guessed: every printable
# ASCII glyph was rendered into its cell in Menlo, SF Mono and Monaco, and its ink
# coverage averaged over the three.  Share of the cell that is ink:
#     .  3 %    :  6 %    ;  8 %    + 10 %    * 13 %    { 14 %    1 14 %
#     o 15 %    a 17 %    % 21 %    & 22 %    8 22 %    B 23 %    @ 24 %
# The ramp leaves out - / | \ _ ( ): those are strokes, drawn only along edges.
RAMP = " .:;+*{1oa%&8B@"

VIDEO_SHARE = 0.65      # fraction of the terminal height that shows the video,
PANE_ROWS = 8           # ...or more, if the picture is tall: the editor keeps this many
PANE_COLS = 48          # ...or all of it, in a low, wide window: the editor stands
                        # beside the picture then, and keeps this many columns
GRID_COLS = 110         # width of the picture in cells (--cols), if the window allows
TUNED = 70              # ...and the width that the edges and the sprinkles are tuned for
LIT = 0.15              # brightness (of 1.0) from which a pixel belongs to the subject
CROP_MARGIN = 0.03      # air left around the subject when the picture is cropped to it
VASE_COLOR = 0xF0EBE1   # --vase-color: pale off-white
VASE_HEIGHT = 0.33      # height of the vase, as a share of the subject's height
VASE_WIDTH = 0.33       # width of its rim, as a share of the subject's width
VASE_FOOT = 0.65        # width of its foot, as a share of the rim's
FLOWERS = 7             # --flowers: how many stand in the vase (1: only the film's own)
# Every flower is the film's own, and no two are alike.  Each has (where around the
# vase it stands, in degrees, 0 is in front;  how far it leans out, in degrees;  its
# size;  how far its hue is turned, in degrees;  how far it is washed toward white;
# when it comes up, in seconds;  how far it opens, as a share of the film).
BOUQUET = ((170.0, 12.0, 1.10, 0.0, 0.0, 1.0, 1.0),         # the film's own colors
           (20.0, 27.0, 1.55, -115.0, 0.75, 2.4, 1.0),      # the pale one: the biggest
           (250.0, 42.0, 0.96, -115.0, 0.0, 4.2, 0.80),
           (95.0, 55.0, 0.80, 45.0, 0.0, 6.0, 0.66),
           (310.0, 60.0, 0.72, -55.0, 0.0, 7.6, 0.56),
           (140.0, 38.0, 1.00, -62.0, 0.5, 5.0, 0.90),
           (205.0, 52.0, 0.84, 88.0, 0.0, 9.0, 0.70))
STEMS = 0.44            # ...and the stems are cut, a big flower's more than a small
                        # one's (by this share of the film's flower, times 1 - 0.5 /
                        # size), so that big flowers stand close together in the vase
HEAD = 0.2              # the middle of the film's flower head: this share of the
                        # subject's height below its top
PACE = 0.6              # speed of the film in a bouquet: its flowers bloom slowly
TURN = 10.0             # seconds in which the bouquet turns once about the vase's axis
LOOK = 12.0             # ...seen from this many degrees above: what is near is lower,
DEPTH = 0.12            # and bigger, by up to this share
FLUTES = 9              # ...and the vase is fluted all around: one sees it turn
SPROUT = 1.8            # seconds a flower of size 1 takes to grow out of the vase
ENCORE = TURN           # seconds the finished bouquet stays (one more turn)
MEMORY = 96             # film frames kept at most, for the flowers that come up late
SPRINKLES = 36.0        # white specks that start to fall, per second (--no-sprinkles)
SPECKS = "'*+."         # ...each drawn as one of these, by how far down its cell it is
TRAIL = ((ord(":"), 0xB4B4B4), (ord("."), 0x858585))    # ...and what some drag along
GLINT = 0.35            # seconds a cell stays white where a speck has soaked in
CELL_ASPECT = 2.0       # a terminal cell is about twice as tall as it is wide
SATURATION = 1.35       # > 1 pushes colors away from gray
CONTRAST = 1.15         # > 1 spreads brightness away from mid-gray
BACKDROP = 0.25         # --bg: a cell's background is this share of its own color
BLACK, KNEE = 0.06, 0.24    # below BLACK is pure black; shadows fade in up to KNEE
CLARITY = 0.7           # local contrast, so shapes survive the tiny resolution
GLYPH_GAMMA = 0.9       # < 1 picks denser glyphs for the mid-tones
INK_GAMMA = 0.5         # < 1 brightens the ink so the colors survive on black
NOISE_GATE = 0.025      # a cell's color must move this far (of 1.0) to count as new
INK_GATE = 2            # ...and its ink further than this (of 255) to be repainted
FAINT = 32              # ink (of 255) too dark to see: such a cell stays blank
EDGE_THRESHOLD = 0.2    # brightness step (of 1.0) between two cells that makes an edge
                        # (in a picture TUNED cells wide or wider; more in a smaller one)
EDGE_HOLD = 0.75        # ...and an edge already drawn stays down to this share of it
EDGE_STICK = 0.3        # head start (of 1.0) for the direction a stroke already has
EDGE_INK = 1.5          # strokes are thin: their ink is this much brighter
CURVE = 0.35            # bend (of 1.0) at which an upright stroke turns into ( or )
SCROLL_SPEED = 2.0      # editor pane: source lines per second

SPACE = ord(" ")
LUMA = np.array([0.2126, 0.7152, 0.0722], np.float32)   # Rec. 709 weights for R, G, B
GLYPHS = np.frombuffer(RAMP.encode("utf-32-le"), "<u4")
STROKES = np.frombuffer("-/|\\_()".encode("utf-32-le"), "<u4")     # the edge glyphs
SPECK = np.frombuffer(SPECKS.encode("utf-32-le"), "<u4")
WAYS = np.arange(4, dtype=np.int8)[:, None, None]       # an edge runs one of four ways
BESIDE = np.ones((3, 3), np.uint8)                      # a cell and its eight neighbors

# editor theme, 0xRRGGBB (dark and quiet, so the video stays the brightest thing)
PANE_BG, BAR_BG, LINE_BG = 0x0D0E14, 0x1A1C26, 0x342C14
BAR_FG, GUTTER_FG, MARK = 0x969CB0, 0x4B5263, 0xF0BE50
LIGHTS = 0xED6A5E, 0xF5BF4F, 0x62C554
TEXT, COMMENT, DOC = 0xABB2BF, 0x5C6373, 0x6E8A68
KEYWORD, STRING, NUMBER = 0xC678DD, 0x98C379, 0xD19A66
DEF, BUILTIN, SELF = 0x61AFEF, 0x56B6C2, 0xE06C75
CONST, OP = 0xE5C07B, 0x8C93A2


def highlight(source, color):
    """Syntax-color Python source into `color` (one row per line, one cell per
    character) and return the 0-based numbers of the lines that start a statement."""
    statements, fresh, prev = [], True, ""

    def paint(tok, ink):
        (r0, c0), (r1, c1) = tok.start, tok.end
        for r in range(r0, r1 + 1):                 # tokens may span several lines
            color[r - 1, (c0 if r == r0 else 0):(c1 if r == r1 else None)] = ink

    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(source).readline))
    except (tokenize.TokenError, SyntaxError):
        return statements                           # not valid Python: leave it plain
    for i, tok in enumerate(tokens):
        kind, text = tokenize.tok_name[tok.type], tok.string
        if kind == "NEWLINE":
            fresh = True                            # the next token starts a statement
        if kind in ("NEWLINE", "NL", "INDENT", "DEDENT", "ENDMARKER"):
            continue
        if kind == "COMMENT":
            paint(tok, COMMENT)
            continue
        after = tokens[i + 1]
        if fresh:
            fresh = False
            if kind == "STRING" and after.type == tokenize.NEWLINE:
                paint(tok, DOC)                     # a docstring is not executed
                continue
            if text not in ("else", "finally"):         # clause headers do not run
                statements.append(tok.start[0] - 1)
        if "STRING" in kind:                        # STRING and the FSTRING_* pieces
            paint(tok, STRING)
        elif kind == "NUMBER":
            paint(tok, NUMBER)
        elif kind == "OP":
            paint(tok, OP)
        elif text in ("True", "False", "None"):
            paint(tok, CONST)
        elif keyword.iskeyword(text):
            paint(tok, KEYWORD)
        elif text in ("self", "cls"):
            paint(tok, SELF)
        elif prev != "." and hasattr(builtins, text):
            paint(tok, BUILTIN)
        elif prev in ("def", "class") or after.string == "(":
            paint(tok, DEF)                         # a definition or a call
        elif text.isupper():
            paint(tok, CONST)
        prev = text
    return statements


def block_end(lines, start):
    """Index just past the indented block that begins at lines[start]."""
    indent = len(lines[start]) - len(lines[start].lstrip())
    end = start + 1
    for i in range(start + 1, len(lines)):
        if lines[i].strip():
            if len(lines[i]) - len(lines[i].lstrip()) <= indent:
                break
            end = i + 1
    return end


def cells(text):
    """Outside text (a file name) made safe for a grid of one character per cell:
    accents composed where Unicode can (other combining marks are dropped), nothing
    invisible or unprintable, wide characters given two cells."""
    out = []
    for c in unicodedata.normalize("NFC", text):
        kind = unicodedata.category(c)
        if c.isspace():
            out.append(" ")
        elif kind[0] == "M" or kind == "Cf":            # zero width: marks, joiners
            continue
        elif not c.isprintable():
            out.append("?")                             # e.g. an escape character
        elif unicodedata.east_asian_width(c) in "WF":
            out.append(c + " ")                         # it covers the next cell too
        else:
            out.append(c)
    return "".join(out)


class Terminal:
    """The real terminal: alternate screen, hidden cursor, and a clean way out."""

    def __init__(self):
        sys.stdout.flush()
        self.fd = sys.stdout.fileno()
        tty = termios and sys.stdin and sys.stdin.isatty()   # (closed stdin: None)
        self.keys = sys.stdin.fileno() if tty else None
        self.cooked = None              # tty settings to restore on the way out
        self.active = self.stop = self.pause = self.fresh = False

    def enter(self):
        """Take over the screen.  From here on signals only raise flags, so the
        frame in flight always finishes and leave() is never cut short."""
        for name in ("SIGINT", "SIGTERM", "SIGHUP", "SIGQUIT", "SIGTSTP", "SIGCONT",
                     "SIGWINCH"):
            if hasattr(signal, name):
                signal.signal(getattr(signal, name), self.on_signal)
                if termios:             # (a system call in progress - the tty restore
                    signal.siginterrupt(getattr(signal, name), False)   # - carries on)
        if self.keys is not None:
            self.cooked = self.cooked or termios.tcgetattr(self.keys)
            mode = termios.tcgetattr(self.keys)
            mode[0] &= ~termios.IXON                    # Ctrl+S must not freeze output
            # no echo, no line buffer, and no key that the terminal acts on by itself:
            # on macOS Ctrl+O would discard our output, and Ctrl+C, Ctrl+\ or Ctrl+Z
            # would kill or stop a wrapper (`uv run`, a shell script, find -exec)
            # before the screen is handed back.  They arrive as keys instead: see alive
            mode[3] &= ~(termios.ECHO | termios.ICANON | termios.IEXTEN | termios.ISIG)
            mode[6][termios.VMIN], mode[6][termios.VTIME] = 0, 0    # reads never block
            termios.tcsetattr(self.keys, termios.TCSAFLUSH, mode)
        self.active = self.fresh = True                 # everything needs painting
        self.write("\x1b[?1049h\x1b[?25l\x1b[?7l")     # alt screen, no cursor, no wrap

    def leave(self):
        """Give the terminal back exactly as we found it."""
        if not self.active:
            return
        self.active = False
        self.write("\x1b[?2026l\x1b[0m\x1b[?7h\x1b[?25h\x1b[?1049l")
        if self.cooked is not None:
            try:
                termios.tcsetattr(self.keys, termios.TCSAFLUSH, self.cooked)
            except termios.error:
                pass                                    # the terminal is already gone

    def on_signal(self, signum, _frame):
        if signum == getattr(signal, "SIGTSTP", None):
            self.pause = True                           # Ctrl+Z: suspend politely
        elif signum in (getattr(signal, "SIGCONT", None),
                        getattr(signal, "SIGWINCH", None)):
            self.fresh = True                           # resumed or resized: repaint
        else:
            self.stop = True                            # Ctrl+C, kill, closed window

    def alive(self):
        """Once-per-frame housekeeping; False as soon as it is time to quit."""
        key = b""
        if self.keys is not None and select.select([self.keys], [], [], 0)[0]:
            try:
                key = os.read(self.keys, 1024)
            except OSError:
                pass
        if key in (b"q", b"Q", b"\x1b"):
            self.stop = True
        elif key == b"\x0c":                            # Ctrl+L: repaint everything
            self.fresh = True
        # Ctrl+C, Ctrl+\ and Ctrl+Z: the screen is handed back first, and only then
        # does the whole job (a wrapper such as `uv run` too) get the signal that the
        # terminal would have sent
        if b"\x03" in key or b"\x1c" in key:
            self.leave()
            self.stop = True                            # (our handler just notes it)
            os.kill(0, signal.SIGQUIT if b"\x1c" in key else signal.SIGINT)
        elif self.pause or b"\x1a" in key:              # (or `kill -TSTP`)
            self.pause = False
            self.leave()
            signal.signal(signal.SIGTSTP, signal.SIG_DFL)       # we sleep in kill()
            os.kill(0, signal.SIGTSTP)                          # until `fg`
            if not self.stop:                           # (killed meanwhile: just go)
                self.enter()
        return not self.stop

    def nap(self, until):
        """Sleep until time.perf_counter() reaches `until`.  The OS wakes sleepers
        late (macOS by several ms), so sleep in shrinking steps and spin through
        the last half millisecond; a signal that asks us to stop ends the wait."""
        while not self.stop:
            left = until - time.perf_counter()
            if left <= 0:
                break
            time.sleep(min(left / 2, 0.05) if left > 0.0005 else 0)

    def size(self):
        """(columns, rows) of the terminal right now."""
        try:
            cols, rows = os.get_terminal_size(self.fd)
        except OSError:
            cols = rows = 0
        return (cols, rows) if cols > 0 and rows > 0 else (80, 24)

    def cell_aspect(self):
        """Height / width of one character cell: measured when the terminal
        reports its size in pixels, otherwise the usual 2:1."""
        if termios:
            try:
                packed = fcntl.ioctl(self.fd, termios.TIOCGWINSZ, bytes(8))
                rows, cols, width, height = struct.unpack("4H", packed)
                aspect = (height / rows) / (width / cols)
                if 1.4 <= aspect <= 3.0:
                    return aspect
            except (OSError, ZeroDivisionError):
                pass
        return CELL_ASPECT

    def write(self, text):
        """Send text to the terminal in full, even if the tty is slow to drain."""
        data = memoryview(text.encode("utf-8"))
        try:
            while data:
                try:
                    data = data[os.write(self.fd, data):]
                except BlockingIOError:                 # non-blocking tty is full
                    select.select([], [self.fd], [], 1.0)
        except OSError:
            self.stop = True                            # the terminal went away


class Renderer:
    """Turns video frames into a grid of colored glyphs; repaints only what changed."""

    def __init__(self, term, gain=1.0, cols=GRID_COLS, backdrop=False):
        self.term = term
        self.gain = gain                # exposure: 1 / the video's white point
        self.want = max(cols, 1)        # --cols: how wide the picture should be
        self.backdrop = backdrop        # --bg: color the cells' backgrounds too
        self.size = None                # (cols, rows) the grids were built for
        self.redrawn = 0                # cells repainted by the last draw()

    def layout(self, cols, rows, frame_h, frame_w):
        """Build the cell grids for this terminal size and fit the picture, `want`
        columns wide if there is room, without distorting it: above the editor pane,
        or beside it if the window is so low and wide that the picture gains by it."""
        self.size, self.cols, self.rows = (cols, rows), cols, rows
        # cells are tall: a square picture needs `aspect` times more columns than rows
        aspect = self.term.cell_aspect()
        tall = frame_h / (frame_w * aspect)             # its rows, per column

        def fit(wide, high):                            # the biggest picture in there
            scale = min(wide / (frame_w * aspect), high / frame_h)
            return (max(1, min(wide, round(frame_w * aspect * scale))),
                    max(1, min(high, round(frame_h * scale))))

        # above: the video gets its share of the screen, and what a tall picture
        # needs on top of that, as long as the editor pane keeps a few rows
        wide = min(cols, self.want)
        need = min(round(wide * tall), rows - PANE_ROWS)
        self.video_rows = max(1, min(rows, max(round(rows * VIDEO_SHARE), need)))
        w, h = fit(wide, self.video_rows)
        top, left = (self.video_rows - h) // 2, (cols - w) // 2
        self.pane_top, self.pane_left = self.video_rows, 0
        # beside: the video gets every row, the pane the columns to its right
        if cols - PANE_COLS - 4 >= 1:
            beside = fit(min(self.want, cols - PANE_COLS - 4), rows)
            if beside[0] * beside[1] > 1.2 * w * h:
                (w, h), left, self.video_rows = beside, 2, rows
                top, self.pane_top, self.pane_left = (rows - h) // 2, 0, w + 4
        self.area = np.s_[top:top + h, left:left + w]   # where the picture goes
        # for the status bar: a picture this much smaller than asked for lacks detail
        self.note = []
        if w < 0.8 * self.want:
            full = f"{self.want}x{max(round(self.want * tall), 1)}"
            how = "taller" if h >= self.video_rows else "wider"
            self.note = [f"make the window {how}:", f"{w}x{h} of {full}"]
        # in a small picture every cell is a step from the next: only the bigger
        # steps, the outlines, are edges there
        self.step = EDGE_THRESHOLD * max(TUNED / w, 1.0)
        # what should be on screen: a character, its color and its background per cell
        self.glyph = np.full((rows, cols), SPACE, np.uint32)
        self.ink = np.zeros((rows, cols), np.uint32)
        self.paper = np.zeros((rows, cols), np.uint32)  # 0x000000: pure black
        self.seen = None                                # what the terminal shows now
        self.held = np.full((h, w, 3), -1.0, np.float32)    # the noise gate's memory
        self.inked = np.full((h, w, 3), -999.0, np.float32)     # the ink now on screen
        self.backed = np.full((h, w, 3), -999.0, np.float32)    # ...and the backgrounds
        self.cap = float("inf")         # the gain the previous frame asked for
        self.shown = np.full((h, w), SPACE, np.uint32)      # the picture alone: its
        self.colors = np.zeros((h, w), np.uint32)           # glyphs and their inks
        self.way = np.full((h, w), -1, np.int8)     # the stroke each cell shows: which
        self.curl = np.zeros((h, w), np.float32)    # way it runs (-1: none), its bend
        self.at = np.indices((h, w)) + 1            # each cell's place in a padded grid

    def put(self, y, x, text, ink):
        """Write text into the grid at row y, column x, clipped to the screen."""
        text = text[:max(self.cols - x, 0)]
        if text and 0 <= y < self.rows and x >= 0:
            span = slice(x, x + len(text))
            self.glyph[y, span] = np.frombuffer(text.encode("utf-32-le"), "<u4")
            self.ink[y, span] = ink

    def convert(self, frame):
        """BGR frame -> one colored glyph per terminal cell (numpy)."""
        h, w = self.held.shape[:2]
        # 1. shrink to one averaged pixel per cell; RGB floats in 0..1
        #    (a big frame is halved first: far cheaper than one big
        #    shrink, which is what keeps a 4K video at its frame rate)
        while frame.shape[0] >= 8 * h and frame.shape[1] >= 8 * w:
            even = frame[:frame.shape[0] & -2, :frame.shape[1] & -2]
            frame = cv2.resize(even, None, fx=0.5, fy=0.5,
                               interpolation=cv2.INTER_AREA)
        small = cv2.resize(frame, (w, h), interpolation=cv2.INTER_AREA)
        rgb = small[:, :, ::-1].astype(np.float32) / 255.0
        # 2. noise gate: a cell keeps its old value until it changes
        #    visibly, so film grain never shimmers and the still parts
        #    of the picture cost nothing to draw
        moved = np.abs(rgb - self.held).max(axis=2) > NOISE_GATE
        self.held[moved] = rgb[moved]
        rgb = self.held
        # 3. brightness = the strongest channel (a vivid petal is bright
        #    even when its luma is low), exposed for the video's white
        #    point and sharpened so shapes survive the tiny resolution
        peak = rgb.max(axis=2)
        lit = peak[peak > BLACK]
        #    (two frames in a row brighter than that white point move
        #    it, for good; a single flash frame does not)
        if lit.size:
            cap = 1.0 / float(np.percentile(lit, 99))
            self.gain = min(self.gain, max(cap, self.cap))
            self.cap = cap
        light = np.minimum(peak * self.gain, 1.0)
        value = light + CLARITY * (light - cv2.GaussianBlur(light, (0, 0), 1))
        # 4. moody grade: a little more contrast, the darkest pixels
        #    fade smoothly to pure black
        fade = np.clip((value - BLACK) / (KNEE - BLACK), 0.0, 1.0)
        value = np.clip(0.5 + (value - 0.5) * CONTRAST, 0.0, 1.0)
        value *= fade * fade * (3.0 - 2.0 * fade)
        #    ...and the colors are pushed away from gray: each cell
        #    keeps its own hue, at full strength (24-bit color)
        luma = rgb @ LUMA
        tint = luma[..., None] + (rgb - luma[..., None]) * SATURATION
        tint = np.maximum(tint, 0.0)
        tint /= np.maximum(tint.max(axis=2, keepdims=True), 1e-4)
        # 5. brightness picks the fill glyph: dark = blanks and dots,
        #    bright = dense characters like & 8 B @ (and how bright
        #    its ink is: lifted, so that dim colors survive on black)
        level = np.rint(value ** GLYPH_GAMMA * (len(RAMP) - 1))
        glyph = GLYPHS[level.astype(np.intp)]
        shade = value ** INK_GAMMA
        # 6. edges: where the brightness jumps from one cell to the
        #    next, a stroke that follows the edge replaces the fill.
        #    Sobel gives each cell a gradient; the edge runs across it,
        #    whichever way is nearest: level -  rising /  upright |
        #    falling \  (cells are tall, so / is one column per row)
        gx = cv2.Sobel(light, cv2.CV_32F, 1, 0, scale=0.25)
        gy = cv2.Sobel(light, cv2.CV_32F, 0, 1, scale=0.25)
        power = gx * gx + gy * gy
        flat, lean = gy * gy - gx * gx, 2.0 * gx * gy
        score = np.stack((flat, lean, -flat, -lean))
        #    (the stroke a cell already shows gets a head start, and
        #    its edge counts for more than a new one, so that it never
        #    flickers between two directions, or on and off)
        score += EDGE_STICK * power * (WAYS == self.way)
        way = score.argmax(axis=0).astype(np.int8)
        force = np.sqrt(power) / np.where(self.way < 0, 1.0, EDGE_HOLD)
        edge = force > self.step
        #    only the crest of an edge is drawn: the cell that beats
        #    both neighbors across the edge (the brighter one of an
        #    even pair; a cell too dark to show a stroke is no rival)
        force[shade * EDGE_INK * 255.0 < FAINT + 8] = 0.0
        force = np.pad(force, 1)
        here = force[1:-1, 1:-1]
        dy = np.where(way == 2, 0, np.sign(gy)).astype(np.intp)
        dx = np.where(way == 0, 0, np.sign(gx)).astype(np.intp)
        ys, xs = self.at
        edge &= here > force[ys + dy, xs + dx]
        edge &= here * 1.15 >= force[ys - dy, xs - dx]
        #    an upright edge that bends is a ( or a ); a level one
        #    with the bright side on top is the base of a shape: _
        tilt = np.pad(cv2.blur(gy, (3, 1)), ((1, 1), (0, 0)))
        turn = (tilt[:-2] - tilt[2:]) * np.sign(gx)
        turn += (1.0 - EDGE_HOLD) * CURVE * here * self.curl
        curl = np.sign(turn) * (np.abs(turn) > CURVE * here)
        curl *= edge & (way == 2)
        kind = way.astype(np.intp)
        kind[(way == 0) & (gy < 0)] = 4
        kind[curl > 0], kind[curl < 0] = 5, 6
        glyph = np.where(edge, STROKES[kind], glyph)
        self.way, self.curl = np.where(edge, way, -1), curl
        # 7. the pixel's own color is the ink (a stroke is thin, so
        #    its ink is lifted: up to, at most, that of the brightest
        #    cell beside it)
        glow = np.minimum(shade * EDGE_INK, cv2.dilate(shade, BESIDE))
        ink = np.where(edge, glow, shade)[..., None] * tint
        ink = np.rint(ink * 255.0)
        #    (a glyph too dark to see is left out: a terminal that
        #    brightens dim text would turn such haze into gray specks;
        #    to appear takes a little more ink than to stay, so that
        #    the dimmest dots do not blink)
        blank = self.shown == SPACE
        glyph[ink.max(axis=2) < FAINT + 8 * blank] = SPACE
        #    (a cell that keeps its glyph also keeps its ink until that
        #    has moved visibly: sharpening nudges every neighbor by +-1)
        same = np.abs(ink - self.inked).max(axis=2) <= INK_GATE
        same &= glyph == self.shown
        ink[same] = self.inked[same]
        self.inked, self.shown = ink, glyph
        r, g, b = np.moveaxis(ink.astype(np.uint32), 2, 0)
        self.colors = r << 16 | g << 8 | b
        self.glyph[self.area], self.ink[self.area] = glyph, self.colors
        # 8. --bg: a dim wash of the cell's color behind its glyph
        if self.backdrop:
            wash = shade * (glyph != SPACE) * BACKDROP
            wash = np.rint(tint * wash[..., None] * 255.0)
            same = np.abs(wash - self.backed).max(axis=2) <= INK_GATE
            wash[same] = self.backed[same]
            self.backed = wash
            r, g, b = np.moveaxis(wash.astype(np.uint32), 2, 0)
            self.paper[self.area] = r << 16 | g << 8 | b

    def draw(self):
        """Repaint only the cells that differ from what is on screen."""
        glyph, paper = self.glyph, self.paper
        ink = np.where(glyph == SPACE, 0, self.ink)     # blanks: no ink
        if self.seen is None:           # first frame, or a new size:
            dirty = np.ones(glyph.shape, bool)      # every cell is new
            out = ["\x1b[0;48;2;0;0;0m\x1b[2J"]     # plain black page
        else:
            was_glyph, was_ink, was_paper = self.seen
            dirty = (glyph != was_glyph) | (ink != was_ink)
            dirty |= paper != was_paper
            out = []
        ys, xs = np.nonzero(dirty)      # row-major, i.e. reading order
        # ...but glyphs of uncertain width go last: if the terminal draws
        # one two cells wide, it must land on top of the cell after it
        odd = np.argsort(glyph[ys, xs] > 126, kind="stable")
        ys, xs = ys[odd], xs[odd]
        n = self.redrawn = int(ys.size)
        if n:
            g, fg, bg = glyph[ys, xs], ink[ys, xs], paper[ys, xs]
            # blanks borrow the ink of the glyph before them: no code
            last = np.where(g != SPACE, np.arange(n), 0)
            fg = fg[np.maximum.accumulate(last)]
            # a run of text ends where the cursor must jump (over a gap,
            # or past a glyph of uncertain width) or a color changes
            jump, inked, papered = np.ones((3, n), bool)
            jump[1:] = (ys[1:] != ys[:-1]) | (xs[1:] != xs[:-1] + 1)
            jump[1:] |= g[:-1] > 126
            inked[1:] = fg[1:] != fg[:-1]
            papered[1:] = bg[1:] != bg[:-1]
            cut = np.flatnonzero(jump | inked | papered)
            text = g.astype("<u4").tobytes().decode("utf-32-le")
            runs = zip(cut.tolist(), cut[1:].tolist() + [n],
                       ys[cut].tolist(), xs[cut].tolist(),
                       fg[cut].tolist(), bg[cut].tolist(),
                       jump[cut].tolist(), inked[cut].tolist(),
                       papered[cut].tolist())
            add = out.append
            for a, b, y, x, f, k, move, new_fg, new_bg in runs:
                if move:
                    add(f"\x1b[{y + 1};{x + 1}H")
                if new_fg:
                    add(f"\x1b[38;2;{f >> 16};{f >> 8 & 255};{f & 255}m")
                if new_bg:
                    add(f"\x1b[48;2;{k >> 16};{k >> 8 & 255};{k & 255}m")
                add(text[a:b])
        if out:                     # one synchronized update: no tearing
            self.term.write("\x1b[?2026h" + "".join(out) + "\x1b[?2026l")
        self.seen = glyph.copy(), ink, paper.copy()


class CodePane:
    """A fake editor showing this file, with a 'current line' stepping through it."""

    GUTTER = 7                          # marker, 4-digit line number, two blanks

    def __init__(self, path):
        try:
            with open(path, encoding="utf-8") as source_file:
                source = source_file.read().expandtabs(4)
        except (OSError, UnicodeDecodeError):           # missing, or not text (a .pyc)
            source = "# (source file not found)\n"
        # split where Python does (only at "\n"); nothing unprintable goes on screen
        lines = "".join(c if c.isprintable() or c == "\n" else " " for c in source)
        lines = lines.split("\n")[:-1] if lines.endswith("\n") else lines.split("\n")
        count, width = len(lines), self.GUTTER + max(map(len, lines))
        self.text = np.full((count, width), SPACE, np.uint32)
        self.color = np.full((count, width), TEXT, np.uint32)
        self.color[:, :self.GUTTER] = GUTTER_FG
        for i, line in enumerate(lines):
            row = f" {i + 1:>4}  {line}"
            self.text[i, :len(row)] = np.frombuffer(row.encode("utf-32-le"), "<u4")
        statements = np.array(highlight(source, self.color[:, self.GUTTER:]), np.intp)
        # the stretch of source that the title promises: convert() through draw()
        self.first = Renderer.convert.__code__.co_firstlineno - 1
        self.draw_at = Renderer.draw.__code__.co_firstlineno - 1
        if 0 <= self.first < self.draw_at < count:
            self.last = block_end(lines, self.draw_at)
        else:                                           # not our own source: show all
            self.first, self.draw_at, self.last = 0, 0, count
        # for every line, the nearest statement at or above it
        marks = np.zeros(count, np.intp)
        marks[statements] = statements
        self.statement = np.maximum.accumulate(marks)
        # ...and the furthest the read head ever gets from the start of its statement
        reach = np.arange(count) - self.statement
        self.reach = int(reach[self.first:self.last].max())

    def paint(self, screen, now, info):
        """Title bar, a window of source around the moving current line, status bar."""
        top, left = screen.pane_top, screen.pane_left   # below the picture: left = 0
        rows, cols = screen.rows - top, screen.cols - left
        if rows < 1 or cols < 1:
            return
        glyph, ink, paper = (grid[top:, left:]
                             for grid in (screen.glyph, screen.ink, screen.paper))
        glyph[:], ink[:], paper[:] = SPACE, TEXT, PANE_BG
        paper[0] = BAR_BG
        start = max((cols - len(TITLE)) // 2, 0)
        screen.put(top, left + start, TITLE, BAR_FG)
        if start >= 9:                                  # room for the window buttons
            for i, light in enumerate(LIGHTS):
                screen.put(top, left + 2 + 2 * i, "●", light)
        body = rows - 1 - (rows > 4)                    # code rows (status bar if room)
        # a read head glides down the source; the statement under it is "executing"
        head = self.first + int(now * SCROLL_SPEED) % (self.last - self.first)
        current = max(int(self.statement[head]), self.first)
        # the view keeps some lines above the head: at least its whole statement
        lead = min(max(body // 3, self.reach), max(body - 1, 0))
        view = min(max(head - lead, self.first), max(self.last - body, self.first))
        view = min(view, current)                       # (a tiny pane: keep it in view)
        shown = max(min(body, self.last - view), 0)
        width = min(cols, self.text.shape[1])
        glyph[1:1 + shown, :width] = self.text[view:view + shown, :width]
        ink[1:1 + shown, :width] = self.color[view:view + shown, :width]
        if view <= current < view + shown:
            row = 1 + current - view
            paper[row] = LINE_BG
            ink[row, :self.GUTTER] = MARK
            screen.put(top + row, left, "▎", MARK)
        if rows > 4:
            method = "convert" if head < self.draw_at else "draw"
            status = f"  Renderer.{method}()  Ln {current + 1}"
            paper[rows - 1] = BAR_BG
            screen.put(top + rows - 1, left, status, BAR_FG)
            # room beside the longest label, so that no field comes and goes with it
            room = cols - len(f"  Renderer.convert()  Ln {self.last}") - 4
            while info and len("  ".join(info)) > room:
                info = info[1:]                         # too narrow: drop a field
            stats = "  ".join(info)
            screen.put(top + rows - 1, left + cols - len(stats) - 2, stats, COMMENT)


class Sprinkles:
    """White specks that drip down the picture and soak into what they land on, which
    glints white for a moment.  They are not painted into the frame like the flowers
    but written over the finished picture, so that each is one crisp character."""

    def __init__(self, seed=7):
        self.rng = random.Random(seed)
        self.size, self.then, self.owed, self.drops = None, None, 0.0, []

    def fall(self, screen, now, wet):
        """Move every speck on to the time `now` (in seconds), let new ones start
        (`wet`, 0..1, of the full shower) and draw them all over the picture."""
        glyph, ink = screen.glyph[screen.area], screen.ink[screen.area]
        glyph[:], ink[:] = screen.shown, screen.colors      # (without the old ones)
        h, w = glyph.shape
        if self.size != (h, w):                         # a new picture: a new shower
            self.size, self.drops = (h, w), []
            self.glint = np.zeros((h, w), np.float32)
        past = 0.0 if self.then is None else min(max(now - self.then, 0.0), 0.1)
        self.then = now
        self.glint -= past / GLINT
        np.maximum(self.glint, 0.0, out=self.glint)
        # new ones start just above the picture, anywhere along it, each (column, row,
        # rows per second, how many lit cells it falls through before it soaks in,
        # how long a trail it drags along: the fast ones drip)
        self.owed += wet * SPRINKLES * w / TUNED * past
        while self.owed >= 1.0:
            self.owed -= 1.0
            speed = self.rng.uniform(0.35, 0.8)
            self.drops.append([self.rng.randrange(w), -self.rng.random(), h * speed,
                               self.rng.randrange(3), int(speed * 4.0 - 1.0)])
        lit, falling = screen.shown != SPACE, []
        for drop in self.drops:
            x, y, speed, deep = drop[:4]
            y, above = y + speed * past, int(y // 1)
            for row in range(above + 1, min(int(y // 1), h - 1) + 1):   # rows it enters
                if lit[row, x]:
                    if not deep:                        # it soaks in here
                        self.glint[row, x] = 1.0
                        break
                    deep -= 1
            else:
                if y < h:                               # (or it has fallen out)
                    drop[1], drop[3] = y, deep
                    falling.append(drop)
        self.drops = falling
        # where one has soaked in, the picture's own ink is white, and fades back
        ys, xs = np.nonzero((self.glint > 0.0) & lit)
        if ys.size:
            rgb = ink[ys, xs][:, None] >> np.array([16, 8, 0], np.uint32) & 255
            rgb = rgb + (255.0 - rgb) * self.glint[ys, xs][:, None]
            r, g, b = np.rint(rgb).astype(np.uint32).T
            ink[ys, xs] = r << 16 | g << 8 | b
        for x, y, _, _, trail in self.drops:
            for back, (mark, gray) in enumerate(TRAIL[:trail], 1):
                if y >= back and glyph[int(y) - back, x] == SPACE:  # (only in the dark)
                    glyph[int(y) - back, x], ink[int(y) - back, x] = mark, gray
        for x, y, _, _, _ in self.drops:
            if y >= 0.0:
                glyph[int(y), x] = SPECK[int(y % 1.0 * len(SPECK))]
                ink[int(y), x] = 0xFFFFFF


def clock(seconds):
    return f"{int(seconds) // 60}:{int(seconds) % 60:02d}"


def glance(frame):
    """A 160x90 map of a frame's brightness (its strongest channel): small enough to
    search at every frame, and averaged, so that one hot pixel is not a subject."""
    step = max(frame.shape[1] // 640, 1)
    small = np.ascontiguousarray(frame[::step, ::step])
    return cv2.resize(small, (160, 90), interpolation=cv2.INTER_AREA).max(axis=2)


def lit_box(top, level):
    """The box (left, top, right, bottom), in fractions of the frame, around everything
    brighter than `level` in the brightness map `top`; None if all of it is dark."""
    lit = top > level
    xs, ys = np.flatnonzero(lit.any(axis=0)), np.flatnonzero(lit.any(axis=1))
    if not xs.size:
        return None
    return (xs[0] / top.shape[1], ys[0] / top.shape[0],
            (xs[-1] + 1) / top.shape[1], (ys[-1] + 1) / top.shape[0])


def join(a, b):
    """The smallest box that holds both boxes (either may be None)."""
    if not (a and b):
        return a or b
    return min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3])


def survey(path, samples=4):
    """What the player must know about a video before it starts; (white, lit, stem).

    white  The brightest level the video really reaches: the 99th percentile of the
           strongest channel among the bright pixels (the subject, not a black or dark
           gray backdrop) of a few frames spread through the file.  Exposing for it
           lets even a dim clip use the bright end of the ramp, with one steady
           exposure instead of a jumpy per-frame one; convert() lowers it, for good,
           if the film outgrows it.
    lit    Where the picture is lit, in those frames or in the first second: a 160x90
           map, or None if nowhere.  That is the subject, which the picture is cropped
           to; Stage.fit() widens the crop if the film outgrows it.
    stem   Where the subject leaves the picture at the bottom, (x, y) in fractions:
           over the first second, the median x and the lowest y of the lit pixels in
           the bottom 15 % of the subject's box.  The vase stands there for the whole
           film, so it never jitters.  None if the first second is dark."""
    probe = cv2.VideoCapture(path)
    total = int(probe.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = probe.get(cv2.CAP_PROP_FPS)
    first, deadline = [], time.perf_counter() + 0.5
    while len(first) < (fps if 0.0 < fps <= 240.0 else 30.0):   # the first second
        ok, frame = probe.read()                        # (or half a second's work)
        if not ok or time.perf_counter() > deadline:
            break
        first.append(glance(frame))
    spread, peaks, deadline = [], [], time.perf_counter() + 0.5
    for i in (2, 3, 1, 0)[:max(min(total, samples), 0)]:        # later frames first
        began = time.perf_counter()
        probe.set(cv2.CAP_PROP_POS_FRAMES, total * (2 * i + 1) // (2 * samples))
        ok, frame = probe.read()
        if not ok:
            break
        top = glance(frame)
        spread.append(top)
        dark = max(BLACK * 255, np.percentile(top, 99) / 2)     # a gray backdrop too
        lit = top[top > dark]                           # only the subject, not the dark
        if lit.size:
            peaks.append(float(np.percentile(lit, 99)) / 255.0)
        now = time.perf_counter()
        if now + (now - began) > deadline:              # no time for one more seek
            break
    probe.release()
    white = min(max(max(peaks, default=1.0), 0.4), 1.0)
    level = LIT * 255.0 * white
    early = stem = None
    lit = np.zeros((90, 160), bool)
    for top in first:
        early = join(early, lit_box(top, level))
    for top in first + spread:
        lit |= top > level
    if early:
        band = early[3] - 0.15 * (early[3] - early[1])  # the lowest 15 % of the subject
        xs = [np.nonzero(top[int(band * 90):] > level)[1] for top in first]
        xs = np.concatenate(xs)
        if xs.size:
            stem = (float(np.median(xs)) + 0.5) / 160.0, early[3]
    return white, lit if lit.any() else None, stem


def hue_turn(degrees):
    """The 3x3 matrix that turns the hue of a (B, G, R) color by so many degrees: a
    rotation about the gray axis, which takes red toward yellow if positive."""
    cos, sin = np.cos(np.radians(degrees)), np.sin(np.radians(degrees)) / 3.0 ** 0.5
    turn = cos * np.eye(3) + (1.0 - cos) / 3.0                  # for (R, G, B)...
    turn += sin * np.array([[0.0, -1.0, 1.0], [1.0, 0.0, -1.0], [-1.0, 1.0, 0.0]])
    return np.ascontiguousarray(turn[::-1, ::-1], np.float32)   # ...and for (B, G, R)


def paint_vase(wide, high, color, white):
    """A pot of `wide` x `high` pixels, drawn with numpy alone: a rim band, the dark gap
    of its shadow, and a body that tapers to VASE_FOOT of the rim's width and stands on
    a flat foot.  It is lit like a cylinder, from the right, so the ramp turns its lit
    side into dense glyphs and its shaded side into thin ones, with a soft highlight
    in between; its color is `color` (0xRRGGBB) with a faint warm tint toward the
    edges, at the video's own white level.  Returns (BGR picture, coverage 0..1, and
    for the flutes: where around the pot each pixel of its body is, in radians, 0 in
    front; its rim, which has none, is marked with NaN)."""
    y, x = np.mgrid[0:high, 0:wide].astype(np.float32) + 0.5
    v, off = y / high, x - wide / 2.0               # 0 = rim .. 1 = foot; px from axis
    rim, gap = 0.13, 0.08                           # heights of the rim, of its shadow
    body = 0.9 - (0.9 - VASE_FOOT) * (v - rim) / (1.0 - rim)
    half = np.where(v < rim, 1.0, body) * wide / 2.0    # half the pot's width, per row
    cover = np.clip(half - np.abs(off) + 0.5, 0.0, 1.0)     # soft side edges
    u = np.clip(off / half, -1.0, 1.0)              # -1 = left edge .. 1 = right edge
    # a cylinder lit from the right, a soft highlight stripe, the rim's shadow
    lit = np.clip(0.8 * u + 0.6 * np.sqrt(1.0 - u * u), 0.0, 1.0)
    shade = 0.36 + 0.48 * lit + 0.16 * np.exp(-((u - 0.3) / 0.2) ** 2)
    shade *= 1.0 - 0.65 * np.clip(1.0 - (v - rim) / gap, 0.0, 1.0) * (v >= rim)
    base = np.array([color & 255, color >> 8 & 255, color >> 16], np.float32)   # B G R
    warm = np.abs(u)[..., None] ** 3 * 0.45 * np.array([0.30, 0.14, 0.0], np.float32)
    picture = base * (1.0 - warm) * (np.clip(shade, 0.0, 1.0) * white * 0.97)[..., None]
    return picture, cover, np.where(v < rim, np.nan, np.arcsin(u))


class Flower:
    """One flower of the bouquet: how it stands in the vase, its color, when it comes
    up and how far it opens - and the frame of the film that it shows right now."""

    def __init__(self, around, tilt, size, turn, pale, wait, opens, length):
        self.around, self.tilt = np.radians(around), np.radians(tilt)
        self.size, self.pale, self.wait = size, pale, wait
        self.turn = hue_turn(turn) if turn else None
        self.flip = around >= 180.0 and bool(turn or pale)  # some are mirrored
        self.sprout = SPROUT * size ** 0.5              # a big one takes longer to grow
        self.cut = STEMS * max(1.0 - 0.5 / size, 0.0)   # ...and has more stem cut off
        # the time of the film at which it stops opening (never, if it opens in full)
        self.last = opens * length if length and opens < 1.0 else float("inf")
        self.held = self.kept = None    # its frame; that frame in its color, to reuse


class Stage:
    """What the renderer gets to see of each frame: the part around the subject, so that
    a flower on a black backdrop fills the picture - as a bouquet: the film's flower
    several times over, standing all around a vase and leaning out of it, each in a
    color and of a size of its own.  The bouquet has a time line of its own.  At first
    the vase is empty; then one flower after the other grows out of it, each showing
    the film from its start (and slowly), so that those that come up late bloom late
    - and not all of them open as far.  All the while the bouquet turns about the
    axis of the vase: the flowers pass in front of each other and behind.  All of that
    is painted into the frame itself, before the ASCII conversion, so that it goes
    through the same ramp, color and repaint logic as the film.
    Boxes here are in pixels, (left, top, right, bottom); the stage may reach past
    the frame, where all is black."""

    def __init__(self, shape, white, lit, stem, crop=True, vase=VASE_COLOR,
                 flowers=FLOWERS, length=0.0):
        self.high, self.wide = shape[:2]
        self.level, self.dark = LIT * 255.0 * white, BLACK * 255.0 * white
        self.crop, self.vase, self.blooms, self.subject = crop, None, [], None
        self.box, self.shrink, self.painted = (0, 0, self.wide, self.high), 1, False
        self.lead = self.tail = self.clock = 0.0    # the time line, in seconds
        self.pace, self.lit = 1.0, lit              # the film's speed; where it is lit
        box = lit_box(lit, 0) if lit is not None else None
        if not box or (box[2] - box[0]) * (box[3] - box[1]) > 0.8:
            self.crop = False                       # no subject on black: show it all
            return
        self.painted = bool(stem) and (vase is not None or flowers > 1)
        if self.painted:        # painting costs time per pixel: a big frame is shrunk
            reach = max((box[2] - box[0]) * self.wide, (box[3] - box[1]) * self.high)
            self.shrink = max((int(reach) + 359) // 360, 1)     # (subject: <= 360 px)
            self.wide, self.high = self.wide // self.shrink, self.high // self.shrink
            self.box = (0, 0, self.wide, self.high)
        self.subject = subject = self.pixels(box)
        wide, high = subject[2] - subject[0], subject[3] - subject[1]
        if self.painted:
            # the mouth of the vase, where the stems enter it; the middle of the head
            # of the film's flower, straight above; how the viewer looks down on it
            self.mouth = np.array([stem[0] * self.wide, stem[1] * self.high])
            self.head = np.array([self.mouth[0], subject[1] + HEAD * high])
            self.look = np.cos(np.radians(LOOK)), np.sin(np.radians(LOOK))
            self.span, self.pace = wide, PACE if flowers > 1 else 1.0
            # (a flower alone stands upright, at its own size, in its own colors)
            picks = BOUQUET[:flowers] if flowers > 1 else ((0.0, 0.0, 1.0, 0.0, 0.0) +
                                                           BOUQUET[0][5:],)
            self.blooms = [Flower(*pick, length) for pick in picks]
            for flower in self.blooms:
                # its stem, from the middle of its head down to where it is cut
                flower.stem = self.mouth[1] - self.head[1] - flower.cut * high * (flowers > 1)
            # dark gaps this small inside a flower are part of it: nothing shows through
            self.gaps = cv2.getStructuringElement(cv2.MORPH_ELLIPSE,
                                                  (wide // 16 | 1, wide // 16 | 1))
            # the time line: the film starts with the first flower, and the show is
            # over ENCORE seconds after the last one has grown, and opened as far as
            # it will.  The sprinkles thin out once all have grown, and stop before.
            waits = [flower.wait for flower in self.blooms]
            self.lead, late = min(waits), max(waits)
            grown = max(flower.wait + flower.sprout for flower in self.blooms)
            over = max(flower.wait + min(flower.last, length) / self.pace
                       for flower in self.blooms)
            over = max(over, grown) if length else grown + 5.0  # (length not known)
            self.tail = max(over - length / self.pace if length else late, self.lead)
            self.tail += ENCORE - self.lead
            self.rain = grown, max(over - 3.0, grown + 1.0)
            # the frames of the film that the late flowers still have to show
            self.reel = collections.deque(maxlen=MEMORY)
            self.every = (late - self.lead) * self.pace / (MEMORY - 2)
            self.fed = self.fresh = None
        bunch = self.reach(lit)                     # all the flowers together
        hold = bunch if crop else join(bunch, self.box)
        # (a bunch takes a bigger vase than one flower, if not as much bigger as wider)
        grow = ((bunch[2] - bunch[0]) / wide) ** 0.75
        w, h = round(VASE_WIDTH * wide * grow), round(VASE_HEIGHT * high * grow)
        if self.painted and vase is not None and w >= 4 and h >= 4:
            picture, cover, around = paint_vase(w, h, vase, white)
            cover = np.rint(cover * 256.0).astype(np.uint16)[..., None]
            left = round(stem[0] * self.wide - w / 2)
            top = round(stem[1] * self.high - 0.05 * h)     # the stems end in the rim
            self.vase = left, top, picture, cover, around
            hold = join(hold, (left, top, left + w, top + h))
        self.front = 0.3 * w        # a flower that hangs out further hides the vase
        self.box = self.framed(hold)

    def pixels(self, box):
        """A box in fractions of the frame -> in pixels of the (shrunk) frame."""
        return (int(box[0] * self.wide), int(box[1] * self.high),
                round(box[2] * self.wide), round(box[3] * self.high))

    def place(self, flower, grown=1.0, turn=0.0):
        """Where a flower stands when it is `grown` (0..1) of its size and the bouquet
        has turned by `turn` (radians).  -> (the 2x3 matrix that takes the film's
        pixels there; how far in front of the vase's axis its head is, in pixels; the
        row of the film at which its stem is cut).
        Its head is a point in space: the stem's length away from the mouth of the
        vase, leaning out by its tilt (it comes up nearly upright), at its place
        around the axis.  Seen from the front and a little from above, the head is
        to the side by x and up by `up` (as shares of the stem's length); the film's
        flower is turned to point there, and its stem cut to the length it seems to
        have, since one that points at the viewer looks short."""
        tilt = flower.tilt * (0.5 + 0.5 * grown)
        x = np.sin(tilt) * np.sin(flower.around + turn)
        near = np.sin(tilt) * np.cos(flower.around + turn)
        up = np.cos(tilt) * self.look[0] - near * self.look[1]
        seems = np.hypot(x, up)
        size = flower.size * grown * (1.0 + DEPTH * near)
        lay = size / seems * np.array([[up, -x], [x, up]])
        if flower.flip:
            lay[:, 0] *= -1.0
        root = self.head + (0.0, flower.stem * seems)
        to = self.mouth + (0.1 * self.span * x, 0.0)    # (the stems: side by side)
        place = np.hstack((lay, (to - lay @ root)[:, None]))
        return place, near * flower.stem * flower.size * grown, root[1]

    def reach(self, lit):
        """The box around everything that is lit on the stage, given where the frame
        itself is lit (a 160x90 map): around the film's flower, or around all the
        flowers of the bouquet, each as far as it ever grows, all the way around."""
        box = self.pixels(lit_box(lit, 0))
        if not self.blooms:
            return box
        # the map of a room three frames wide and high, the frame in its middle
        fine = np.array([lit.shape[1] / self.wide, lit.shape[0] / self.high])
        room = np.zeros((3 * lit.shape[0], 3 * lit.shape[1]), np.uint8)
        for flower in self.blooms:
            for turn in np.arange(16) * np.pi / 8 if flower.tilt and TURN else (0.0,):
                place, _, cut = self.place(flower, 1.0, turn)
                here = lit.astype(np.uint8) * 255
                here[round(cut * fine[1]):] = 0     # (its stem is cut there)
                lay = place[:, :2] * fine[:, None] / fine[None, :]
                move = place[:, 2] * fine + lit.shape[::-1]
                cv2.max(room, cv2.warpAffine(here, np.hstack((lay, move[:, None])),
                                             room.shape[::-1]), room)
        far = lit_box(room, 64)
        if far is None:
            return box
        wide, high = 3 * self.wide, 3 * self.high
        air = 1.0 / lit.shape[1]                    # (the map is coarse: one cell more)
        return (int((far[0] - air) * wide) - self.wide,
                int((far[1] - air) * high) - self.high,
                round((far[2] + air) * wide) - self.wide,
                round((far[3] + air) * high) - self.high)

    def framed(self, box):
        """The box with some air around it: as far as there is picture, or anywhere
        if the stage is painted (past the frame it is black)."""
        air = round(CROP_MARGIN * max(box[2] - box[0], box[3] - box[1])) * self.crop
        box = box[0] - air, box[1] - air, box[2] + air, box[3] + air
        if self.subject and self.painted:
            return box
        return (max(box[0], 0), max(box[1], 0),
                min(box[2], self.wide), min(box[3], self.high))

    @property
    def shape(self):
        """(height, width) of the picture that cut() returns."""
        return self.box[3] - self.box[1], self.box[2] - self.box[0]

    def fit(self, frame):
        """Widen the crop, for good, if this frame is lit outside it; True if it was."""
        lit = glance(frame) > self.level if self.subject else None
        if lit is None or not (lit & ~self.lit).any():
            return False                            # (lit nowhere new)
        self.lit = self.lit | lit
        self.subject = join(self.subject, self.pixels(lit_box(lit, 0)))
        seen = self.reach(self.lit)
        if join(self.box, seen) == self.box:
            return False
        self.box = join(self.box, self.framed(seen))
        return True

    def wet(self, now):
        """How hard it sprinkles `now` seconds into the show, 0..1: in full until
        every flower has grown, then less and less; the finished bouquet is dry."""
        if not self.blooms:
            return 0.0
        grown, dry = self.rain
        return min(max((dry - now) / (dry - grown), 0.0), 1.0)

    def take(self, frame, seen):
        """What the flowers need of a frame of the film, `seen` seconds into it: the
        subject's picture, and of each of its pixels how solid it is, how green and
        how bright.  -> (seen, the picture's corner, picture, solid, leaf, peak)"""
        if self.shrink > 1:
            frame = cv2.resize(frame, (self.wide, self.high),
                               interpolation=cv2.INTER_AREA)
        sx0, sy0, sx1, sy1 = self.subject
        film = np.ascontiguousarray(frame[sy0:sy1, sx0:sx1])
        if not film.size:
            return None
        # how solid: 0 where the film is dark, 255 where it is lit, and in the small
        # dark gaps inside the flower.  (Measured on a smoothed picture, in soft
        # steps: hard ones on single pixels would turn film grain into flicker.)
        blue, green, red = cv2.split(film)
        other = cv2.max(blue, red)
        peak = cv2.max(other, green)
        solid = cv2.subtract(cv2.blur(peak, (5, 5)), self.level * 0.6)
        solid = cv2.multiply(solid, 255.0 / self.level)
        solid = cv2.morphologyEx(solid, cv2.MORPH_CLOSE, self.gaps)
        # ...and how green: leaves and stems keep their color in every flower
        leaf = cv2.subtract(cv2.blur(cv2.subtract(green, other), (5, 5)), 6)
        leaf = cv2.multiply(leaf, 8)
        return seen, (sx0, sy0), film, solid, leaf, peak

    def find(self, flower, want):
        """The frame that a flower shows when it is `want` seconds into the film: the
        newest one that is not past that (or the one it has, if that is long gone)."""
        for frame in (self.fresh, *reversed(self.reel)):
            if frame[0] <= want + 1e-6:
                if flower.held is None or frame[0] > flower.held[0]:
                    flower.held = frame
                break
        if flower.held is None:                     # (frames were dropped: the oldest)
            flower.held = self.reel[0] if self.reel else self.fresh
        return flower.held

    def tint(self, flower, frame):
        """A frame of the film in a flower's own color: the hue turned, washed toward
        white - but not the leaves.  (Kept for as long as the flower shows the same
        frame: one that has opened as far as it will is tinted just once.)"""
        if flower.kept and flower.kept[0] is frame:
            return flower.kept[1]
        _, _, film, cover, leaf, peak = frame
        tinted = film
        if flower.turn is not None or flower.pale:
            # of each pixel, the share that keeps its color (the greens) and the
            # share that turns
            thick = cv2.merge((cover,) * 3)
            greens = cv2.multiply(cv2.merge((leaf,) * 3), thick, scale=1.0 / 255.0)
            petals = cv2.subtract(thick, greens)
            greens = cv2.multiply(film, greens, scale=1.0 / 255.0)
            if flower.turn is not None:
                tinted = cv2.transform(film, flower.turn)
            if flower.pale:
                tinted = cv2.addWeighted(tinted, 1.0 - flower.pale,
                                         cv2.merge((peak,) * 3), flower.pale, 0.0)
            tinted = cv2.add(cv2.multiply(tinted, petals, scale=1.0 / 255.0), greens)
        flower.kept = frame, tinted
        return tinted

    def paint(self, flower, frame, grown, turn):
        """One flower as it stands on the stage.  -> (how far in front it is, left,
        top, its picture, how much it lets through of what is behind it), or None."""
        place, near, cut = self.place(flower, grown, turn)
        (sx0, sy0), cover = frame[1], frame[3]
        rows = min(max(round(cut) - sy0, 0), cover.shape[0])    # (down to the cut)
        ends = np.array([(x, y, 1) for y in (sy0, sy0 + rows)
                         for x in (sx0, sx0 + cover.shape[1])])
        ax, ay = np.floor((ends @ place.T).min(axis=0)).astype(int) - 1
        bx, by = np.ceil((ends @ place.T).max(axis=0)).astype(int) + 1
        ax, ay = max(int(ax), self.box[0]), max(int(ay), self.box[1])
        bx, by = min(int(bx), self.box[2]), min(int(by), self.box[3])
        if not rows or ax >= bx or ay >= by:
            return None
        move = place[:, :2] @ (sx0, sy0) + place[:, 2] - (ax, ay)
        move = np.hstack((place[:, :2], move[:, None]))
        clear = cv2.warpAffine(cover[:rows], move, (bx - ax, by - ay))
        clear = cv2.merge((cv2.bitwise_not(clear),) * 3)
        tinted = self.tint(flower, frame)[:rows]
        return near, ax, ay, cv2.warpAffine(tinted, move, (bx - ax, by - ay)), clear

    def cut(self, frame, now=0.0):
        """The picture to convert: this frame, cropped - or, of a bouquet, what stands
        in the vase `now` seconds into the show, of which `frame` is the film's part:
        the flowers that have come up, the furthest first, and the vase in front of
        all but those that hang out over it."""
        x0, y0, x1, y1 = self.box
        if not (self.subject and self.painted):
            return frame[y0:y1, x0:x1]
        if now < self.clock:                        # the show began again: all is new
            self.fed = self.fresh = None
            self.reel.clear()
            for flower in self.blooms:
                flower.held = flower.kept = None
        self.clock = now
        seen = (now - self.lead) * self.pace        # how far into the film that is
        if seen >= 0.0 and frame is not self.fed:
            self.fed, self.fresh = frame, self.take(frame, seen)
            if self.fresh and (not self.reel or seen - self.reel[-1][0] >= self.every):
                self.reel.append(self.fresh)
        turn = 2.0 * np.pi * now / TURN if TURN else 0.0
        layers = []
        for flower in self.blooms if self.fresh else ():
            age = now - flower.wait
            if age < 0.0:
                continue                            # it has yet to come up
            shown = self.find(flower, min(age * self.pace, flower.last))
            grown = min(age / flower.sprout, 1.0)
            grown *= grown * (3.0 - 2.0 * grown)    # slowly, faster, slowly
            layer = self.paint(flower, shown, grown, turn)
            if layer:
                layers.append(layer)
        if self.vase:
            # the flutes go around with the bouquet: darker bands on the vase's body
            left, top, picture, cover, around = self.vase
            flutes = 0.5 + 0.5 * np.cos(FLUTES * (around + turn))
            flutes = 1.0 - 0.34 * np.nan_to_num(flutes)
            paint = (picture * flutes[..., None] * cover).astype(np.uint16)
            layers.append((self.front, left, top, paint, 256 - cover))
        canvas = np.zeros((y1 - y0, x1 - x0, 3), np.uint8)
        for _, left, top, paint, clear in sorted(layers, key=lambda layer: layer[0]):
            back = canvas[top - y0:top - y0 + paint.shape[0],
                          left - x0:left - x0 + paint.shape[1]]
            if paint.dtype == np.uint16:            # the vase
                back[:] = (back * clear + paint) >> 8
            else:
                back[:] = cv2.add(paint, cv2.multiply(back, clear, scale=1.0 / 255.0))
        return canvas


class Reel:
    """The film as the show needs it: before its first frame, `lead` frames in which
    it does not move yet (the stage shows an empty vase then), and after its last,
    `tail` frames more of that one, while the late flowers finish.  In between, each
    frame of the show is `step` frames of the film further: less than one, if the
    film is shown slowly, and then the same frame is handed out again."""

    def __init__(self, path):
        self.path, self.film = path, cv2.VideoCapture(path)
        self.lead, self.tail, self.step = 0, 0, 1.0
        self.rewind(again=False)

    def rewind(self, again=True):
        """Back to the start of the show; False if the film cannot be read (again)."""
        if again:
            self.film.set(cv2.CAP_PROP_POS_FRAMES, 0)
        ok, first = self.film.read()
        if not ok and again:                        # no seeking: reopen the file
            self.film.release()
            self.film = cv2.VideoCapture(self.path)
            ok, first = self.film.read()
        self.first = self.final = first if ok else None
        self.at, self.got = 0, 0                    # frames handed out; the film's
        self.stale, self.spare = False, None        # (not decoded yet); of the tail
        return ok

    def read(self, skip=False):
        """(True, the next frame of the show), or (False, None) at its end.  A frame
        that is skipped is not decoded: (True, None)."""
        if self.first is None:
            return False, None
        at, self.at = self.at, self.at + 1
        want = int(max(at - self.lead, 0) * self.step)      # the film's frame for it
        while self.spare is None and self.got < want:
            if self.film.grab():
                self.got, self.stale = self.got + 1, True
            else:
                self.spare = self.tail              # the film is over: its last frame
        if self.stale and not (skip and self.spare is None):
            ok, frame = self.film.retrieve()        # (decoded only when it is shown)
            self.final, self.stale = frame if ok else self.final, False
        if self.spare is None:
            return True, None if skip else self.final
        self.spare -= 1
        return (True, self.final) if self.spare >= 0 else (False, None)

    def grab(self):
        """Skip a frame of the show; False at its end."""
        return self.read(skip=True)[0]

    def release(self):
        self.film.release()


def play(path, loop=True, cols=GRID_COLS, backdrop=False, crop=True, vase=VASE_COLOR,
         flowers=FLOWERS, sprinkles=True):
    """Decode, convert and draw at the video's own frame rate until told to stop."""
    video = Reel(path)
    frame, film = video.first, video.film
    if frame is None:
        sys.exit(f"ascii_player: could not read any video frames from {path!r}")
    fps = film.get(cv2.CAP_PROP_FPS)
    fps = fps if 0.0 < fps <= 240.0 else 30.0           # missing or absurd metadata
    wide = film.get(cv2.CAP_PROP_SAR_NUM) / (film.get(cv2.CAP_PROP_SAR_DEN) or 1.0)
    wide = wide if 0.1 < wide < 10.0 else 1.0           # anamorphic: pixels not square
    total = max(int(film.get(cv2.CAP_PROP_FRAME_COUNT)), 0)
    name, info, count = cells(os.path.basename(path)), [], "   0 cells redrawn"
    term = Terminal()
    white, lit, stem = survey(path)
    stage = Stage(frame.shape, white, lit, stem, crop, vase, flowers, total / fps)
    stage.fit(frame)
    # a bouquet's show is longer than the film: the vase is empty at first, and the
    # flowers that come up late need time after the film's end
    video.lead, video.tail = round(stage.lead * fps), round(stage.tail * fps)
    video.step = stage.pace                 # (and there the film is shown slowly)
    length = video.lead + total / stage.pace + video.tail
    length = f" / {clock(length / fps)}" if total else ""
    rain = Sprinkles() if sprinkles and stage.blooms else None
    screen = Renderer(term, gain=1.0 / white, cols=cols, backdrop=backdrop)
    pane = CodePane(os.path.abspath(__file__))
    try:
        term.enter()
        ok, frame = video.read()
        began = start = time.perf_counter()             # `start`: when this pass began
        index, shown, at = 0, frame, 0.0    # number of `frame`; the one now on screen
        told, slow = start, False           # last counter update; is decoding too slow?
        while term.alive():
            resized = term.fresh or term.size() != screen.size
            if resized:
                term.fresh = False
                high, across = stage.shape              # the picture's proportions
                screen.layout(*term.size(), high, across * wide)
            due = start + index / fps                   # when `frame` belongs on screen
            # wake up at least every 0.1 s (a slow video must not freeze the editor
            # pane or the keys; sprinkles fall twice as often), and at once to
            # repaint after a resize
            idle = 0.0 if resized else 0.05 if rain else 0.1
            wake = min(due, time.perf_counter() + idle)
            if wake == due:
                if frame is None:                       # --once: the last frame has
                    term.nap(due)                       # had its full time on screen
                    break
                shown, at = frame, index / fps          # `at`: seconds into the show
                info = [name, f"{fps:.4g} fps", clock(at) + length, count]
                info[3:3] = screen.note
            if wake == due or resized:
                screen.convert(stage.cut(shown, at))
            if rain:
                rain.fall(screen, wake - began, stage.wet(at))
            pane.paint(screen, wake - began, info)
            term.nap(wake)
            screen.draw()
            if wake < due:
                continue                                # only the pane moved
            # the counter shows a frame's own repaint (not a pane tick's, and not
            # the whole new page after a resize), at ~4 Hz
            if wake - told >= 0.25 and not resized:
                told, count = wake, f"{screen.redrawn:4d} cells redrawn"
            # pick the next frame by the clock, dropping frames if we fell behind
            index += 1
            now = time.perf_counter()
            late = int((now - start) * fps) - index     # whole frames behind schedule
            if now - start - (index - 1) / fps > 1.0:   # a long stall (suspend, sleep):
                start, late = now - (index - 1) / fps, 0    # carry on, do not race
            elif late > 0 and slow:                     # the decoder cannot keep up, so
                start, late = start + late / fps, 0     # skipping is no help: slow down
            while late > 0 and video.grab():
                index, late = index + 1, late - 1
            now = time.perf_counter()
            ok, following = video.read()
            slow = (time.perf_counter() - now) * fps > 0.5
            if not ok and loop:                         # the end of the show: again
                if not video.rewind():
                    break
                ok, following = video.read()
                start, index = start + index / fps, 0
            new = ok and following is not frame         # (not the same one, held)
            frame = following if ok else None           # None: --once, nothing follows
            if new and stage.fit(frame):                # the subject outgrew the crop:
                term.fresh = True                       # lay the screen out again
    finally:
        term.leave()
        video.release()


def main():
    parser = argparse.ArgumentParser(
        description="Play a video in the terminal as glowing, colored ASCII art.",
        epilog="Needs a terminal with 24-bit color.  VS Code brightens dim text unless "
               "terminal.integrated.minimumContrastRatio is set to 1.")
    parser.add_argument("video", help="path to a video file, e.g. bloom.mp4")
    parser.add_argument("--once", action="store_true",
                        help="stop at the end of the video instead of looping")
    parser.add_argument("--cols", type=int, default=GRID_COLS, metavar="N",
                        help="width of the picture in characters (default %(default)s; "
                             "it shrinks to fit the window)")
    parser.add_argument("--bg", action="store_true",
                        help="also tint each cell's background, dimly, with its color")
    parser.add_argument("--flowers", type=int, default=FLOWERS, metavar="N",
                        choices=range(1, len(BOUQUET) + 1),
                        help="how many flowers stand in the vase, 1 to "
                             f"{len(BOUQUET)}: the video's own and copies of it in "
                             "other colors and sizes (default %(default)s)")
    parser.add_argument("--no-sprinkles", action="store_true",
                        help="no white specks dripping down on the flowers")
    parser.add_argument("--no-crop", action="store_true",
                        help="show the whole frame, not just the subject on its black "
                             "backdrop")
    parser.add_argument("--no-vase", action="store_true",
                        help="do not paint a vase under the subject")
    parser.add_argument("--vase-color", default=f"{VASE_COLOR:06x}", metavar="RRGGBB",
                        help="color of the vase, in hex (default %(default)s)")
    args = parser.parse_args()
    if args.cols < 1:
        parser.error("--cols must be at least 1")
    color = args.vase_color.lstrip("#")
    if len(color) != 6 or set(color) - set("0123456789abcdefABCDEF"):
        parser.error(f"--vase-color must be six hex digits like f0ebe1, "
                     f"not {args.vase_color!r}")
    vase = None if args.no_vase else int(color, 16)
    if not os.path.isfile(args.video):
        parser.error(f"no such file: {args.video!r}")
    try:
        args.video.encode()                             # (OpenCV crashes on such names)
    except UnicodeEncodeError:
        parser.error("the file name is not valid UTF-8: rename the file or link to it")
    if not (sys.stdout and sys.stdout.isatty()):
        parser.error("this is a full-screen terminal app, but stdout is not a terminal")
    try:
        play(args.video, loop=not args.once, cols=args.cols, backdrop=args.bg,
             crop=not args.no_crop, vase=vase, flowers=args.flowers,
             sprinkles=not args.no_sprinkles)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
