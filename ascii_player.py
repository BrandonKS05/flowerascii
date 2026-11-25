#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = ["numpy", "opencv-python-headless"]
# ///
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

try:
    import fcntl
    import termios
except ImportError:
    termios = None

if __name__ == "__main__":
    signal.signal(signal.SIGINT, lambda *_: sys.exit())

os.environ.setdefault("OPENCV_LOG_LEVEL", "SILENT")
os.environ.setdefault("OPENCV_FFMPEG_LOGLEVEL", "-8")
try:
    import cv2
    import numpy as np
except ImportError as error:
    sys.exit(f"ascii_player: {error}.  Run `uv run ascii_player.py VIDEO`, or use a "
             "Python that has numpy and opencv-python-headless installed.")

TITLE = "ascii_player.py — Renderer.convert() + draw()"

RAMP = " .:;+*{1oa%&8B@"

VIDEO_SHARE = 0.58
PANE_ROWS = 12
PANE_HIGH = 18
PANE_SLIM = 30
PANE_COLS = 48
PANE_WIDE = 64
PANE_TALL = 0.7
PANE_SIDE = 0.75
GRID_COLS = 92
TUNED = 70
LIT = 0.15
CROP_MARGIN = 0.03
VASE_COLOR = 0xF0EBE1
VASE_HEIGHT = 0.33
VASE_WIDTH = 0.33
VASE_FOOT = 0.65
FLOWERS = 12
BOUQUET = ((170.0, 7.0, 0.81, 0.0, 0.0, 1.5, 1.0),
           (20.0, 15.0, 1.12, -115.0, 0.75, 3.6, 1.0),
           (250.0, 24.0, 0.69, -115.0, 0.0, 6.3, 0.80),
           (95.0, 31.0, 0.58, 45.0, 0.0, 9.0, 0.66),
           (310.0, 34.0, 0.53, -55.0, 0.0, 11.4, 0.56),
           (140.0, 22.0, 0.73, -62.0, 0.5, 7.5, 0.90),
           (205.0, 29.0, 0.62, 88.0, 0.0, 13.5, 0.70),
           (55.0, 27.0, 0.65, 65.0, 0.0, 4.8, 0.85),
           (285.0, 16.0, 0.87, -30.0, 0.3, 2.6, 1.0),
           (350.0, 36.0, 0.49, -85.0, 0.0, 10.2, 0.60),
           (120.0, 38.0, 0.47, -140.0, 0.0, 12.4, 0.50),
           (330.0, 26.0, 0.67, 0.0, 0.6, 8.2, 0.75))
STEMS = 0.2
LONG = 2.15
STALK = 0.2
STUB = 0.25
CLIMB = 0.9
HEAD = 0.2
PACE = 0.35
TURN = 10.0
LOOK = 12.0
DEPTH = 0.12
FLUTES = 9
SPROUT = 1.8
ENCORE = TURN
FINALE = 5.0
MEMORY = 96
SPRINKLES = 60.0
SOAK = 0.2
SPECKS = "'*+."
TRAIL = ((ord(":"), 0xB4B4B4), (ord("."), 0x858585))
GLINT = 0.35
DECODE = 1.3
SCRAMBLE = 0.35
SHEEN = 0.3
SWEEP = 1.2
RISE = 0.9
POP = 0.5
BEAT = 0.6
FLASH = 1.5
BURST = 24.0
DRAG = 3.0
PETALS = 2.5
HEARTS = 0.6
MARKS = "*+.", "('),", "<", "3", "'."
WINGS = "}{", ")(", "||", ")("
FLIGHT = ((0.40, 0.30, 0.15, 0xFFB347), (-0.30, 0.46, 0.20, 0x7FD8FF),
          (0.24, 0.20, 0.09, 0xFFE66D))
PINKS = 0xFF7AA8, 0xFF4D6D, 0xFFC2D6
CELL_ASPECT = 2.0
SATURATION = 1.35
CONTRAST = 1.15
BACKDROP = 0.25
BLACK, KNEE = 0.06, 0.24
CLARITY = 0.7
GLYPH_GAMMA = 0.9
INK_GAMMA = 0.5
NOISE_GATE = 0.025
INK_GATE = 2
FAINT = 32
EDGE_THRESHOLD = 0.2
EDGE_HOLD = 0.75
EDGE_STICK = 0.3
EDGE_INK = 1.5
CURVE = 0.35
SCROLL_SPEED = 2.0

SPACE = ord(" ")
LUMA = np.array([0.2126, 0.7152, 0.0722], np.float32)
GLYPHS = np.frombuffer(RAMP.encode("utf-32-le"), "<u4")
STROKES = np.frombuffer("-/|\\_()".encode("utf-32-le"), "<u4")
SPECK = np.frombuffer(SPECKS.encode("utf-32-le"), "<u4")
SHAPES = np.array([[ord(marks[i * len(marks) // 12]) for i in range(12)]
                   for marks in MARKS], np.uint32)
WING = np.array([[ord(c) for c in wings] for wings in WINGS], np.uint32)
SHIFTS = np.array([16, 8, 0], np.uint32)
X, Y, VX, VY, PULL, SLOW, AGE, LIFE, SWING, RATE, PHASE, KIND, TONE = range(13)
SPARK, PETAL, HEART, SPLASH = 0, 1, 2, 4
WAYS = np.arange(4, dtype=np.int8)[:, None, None]
BESIDE = np.ones((3, 3), np.uint8)

PANE_BG, BAR_BG, LINE_BG = 0x0D0E14, 0x1A1C26, 0x342C14
BAR_FG, GUTTER_FG, MARK = 0x969CB0, 0x4B5263, 0xF0BE50
LIGHTS = 0xED6A5E, 0xF5BF4F, 0x62C554
TEXT, COMMENT, DOC = 0xABB2BF, 0x5C6373, 0x6E8A68
KEYWORD, STRING, NUMBER = 0xC678DD, 0x98C379, 0xD19A66
DEF, BUILTIN, SELF = 0x61AFEF, 0x56B6C2, 0xE06C75
CONST, OP = 0xE5C07B, 0x8C93A2


def highlight(source, color):
    statements, fresh, prev = [], True, ""

    def paint(tok, ink):
        (r0, c0), (r1, c1) = tok.start, tok.end
        for r in range(r0, r1 + 1):
            color[r - 1, (c0 if r == r0 else 0):(c1 if r == r1 else None)] = ink

    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(source).readline))
    except (tokenize.TokenError, SyntaxError):
        return statements
    for i, tok in enumerate(tokens):
        kind, text = tokenize.tok_name[tok.type], tok.string
        if kind == "NEWLINE":
            fresh = True
        if kind in ("NEWLINE", "NL", "INDENT", "DEDENT", "ENDMARKER"):
            continue
        if kind == "COMMENT":
            paint(tok, COMMENT)
            continue
        after = tokens[i + 1]
        if fresh:
            fresh = False
            if kind == "STRING" and after.type == tokenize.NEWLINE:
                paint(tok, DOC)
                continue
            if text not in ("else", "finally"):
                statements.append(tok.start[0] - 1)
        if "STRING" in kind:
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
            paint(tok, DEF)
        elif text.isupper():
            paint(tok, CONST)
        prev = text
    return statements


def block_end(lines, start):
    indent = len(lines[start]) - len(lines[start].lstrip())
    end = start + 1
    for i in range(start + 1, len(lines)):
        if lines[i].strip():
            if len(lines[i]) - len(lines[i].lstrip()) <= indent:
                break
            end = i + 1
    return end


def cells(text):
    out = []
    for c in unicodedata.normalize("NFC", text):
        kind = unicodedata.category(c)
        if c.isspace():
            out.append(" ")
        elif kind[0] == "M" or kind == "Cf":
            continue
        elif not c.isprintable():
            out.append("?")
        elif unicodedata.east_asian_width(c) in "WF":
            out.append(c + " ")
        else:
            out.append(c)
    return "".join(out)


class Terminal:
    def __init__(self):
        sys.stdout.flush()
        self.fd = sys.stdout.fileno()
        tty = termios and sys.stdin and sys.stdin.isatty()
        self.keys = sys.stdin.fileno() if tty else None
        self.cooked = None
        self.active = self.stop = self.pause = self.fresh = False

    def enter(self):
        for name in ("SIGINT", "SIGTERM", "SIGHUP", "SIGQUIT", "SIGTSTP", "SIGCONT",
                     "SIGWINCH"):
            if hasattr(signal, name):
                signal.signal(getattr(signal, name), self.on_signal)
                if termios:
                    signal.siginterrupt(getattr(signal, name), False)
        if self.keys is not None:
            self.cooked = self.cooked or termios.tcgetattr(self.keys)
            mode = termios.tcgetattr(self.keys)
            mode[0] &= ~termios.IXON
            mode[3] &= ~(termios.ECHO | termios.ICANON | termios.IEXTEN | termios.ISIG)
            mode[6][termios.VMIN], mode[6][termios.VTIME] = 0, 0
            termios.tcsetattr(self.keys, termios.TCSAFLUSH, mode)
        self.active = self.fresh = True
        self.write("\x1b[?1049h\x1b[?25l\x1b[?7l")

    def leave(self):
        if not self.active:
            return
        self.active = False
        self.write("\x1b[?2026l\x1b[0m\x1b[?7h\x1b[?25h\x1b[?1049l")
        if self.cooked is not None:
            try:
                termios.tcsetattr(self.keys, termios.TCSAFLUSH, self.cooked)
            except termios.error:
                pass

    def on_signal(self, signum, _frame):
        if signum == getattr(signal, "SIGTSTP", None):
            self.pause = True
        elif signum in (getattr(signal, "SIGCONT", None),
                        getattr(signal, "SIGWINCH", None)):
            self.fresh = True
        else:
            self.stop = True

    def alive(self):
        key = b""
        if self.keys is not None and select.select([self.keys], [], [], 0)[0]:
            try:
                key = os.read(self.keys, 1024)
            except OSError:
                pass
        if key in (b"q", b"Q", b"\x1b"):
            self.stop = True
        elif key == b"\x0c":
            self.fresh = True
        if b"\x03" in key or b"\x1c" in key:
            self.leave()
            self.stop = True
            os.kill(0, signal.SIGQUIT if b"\x1c" in key else signal.SIGINT)
        elif self.pause or b"\x1a" in key:
            self.pause = False
            self.leave()
            signal.signal(signal.SIGTSTP, signal.SIG_DFL)
            os.kill(0, signal.SIGTSTP)
            if not self.stop:
                self.enter()
        return not self.stop

    def nap(self, until):
        while not self.stop:
            left = until - time.perf_counter()
            if left <= 0:
                break
            time.sleep(min(left / 2, 0.05) if left > 0.0005 else 0)

    def size(self):
        try:
            cols, rows = os.get_terminal_size(self.fd)
        except OSError:
            cols = rows = 0
        return (cols, rows) if cols > 0 and rows > 0 else (80, 24)

    def cell_aspect(self):
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
        data = memoryview(text.encode("utf-8"))
        try:
            while data:
                try:
                    data = data[os.write(self.fd, data):]
                except BlockingIOError:
                    select.select([], [self.fd], [], 1.0)
        except OSError:
            self.stop = True


class Renderer:
    def __init__(self, term, gain=1.0, cols=GRID_COLS, backdrop=False):
        self.term = term
        self.gain = gain
        self.want = max(cols, 1)
        self.backdrop = backdrop
        self.size = None
        self.redrawn = 0

    def layout(self, cols, rows, frame_h, frame_w):
        self.size, self.cols, self.rows = (cols, rows), cols, rows
        aspect = self.term.cell_aspect()
        tall = frame_h / (frame_w * aspect)

        def fit(wide, high):
            scale = min(wide / (frame_w * aspect), high / frame_h)
            return (max(1, min(wide, round(frame_w * aspect * scale))),
                    max(1, min(high, round(frame_h * scale))))

        wide = min(cols, self.want)
        need = min(round(wide * tall), rows - PANE_ROWS)
        self.video_rows = max(1, min(rows, max(round(rows * VIDEO_SHARE), need)))
        self.pane_rows, self.pane_cols = min(rows - self.video_rows, PANE_HIGH), cols
        self.video_rows = rows - self.pane_rows
        w, h = fit(wide, self.video_rows)
        top, left = (self.video_rows - h) // 2, (cols - w) // 2
        self.pane_top, self.pane_left = self.video_rows, 0
        snug = fit(min(cols, self.want), rows)[0]
        across = min(max(cols - snug - 4, min(PANE_COLS, cols * 2 // 5)), PANE_WIDE)
        if across >= PANE_SLIM and cols - across - 4 >= 1:
            beside = fit(min(self.want, cols - across - 4), rows)
            if beside[0] * beside[1] >= PANE_SIDE * w * h:
                (w, h), self.video_rows = beside, rows
                top, left = (rows - h) // 2, (cols - w - 3 - across) // 2
                self.pane_cols = across
                self.pane_rows = min(rows, max(PANE_ROWS, round(PANE_TALL * h)))
                self.pane_top, self.pane_left = (rows - self.pane_rows) // 2, left + w + 3
        self.area = np.s_[top:top + h, left:left + w]
        self.note = []
        if w < 0.8 * self.want:
            full = f"{self.want}x{max(round(self.want * tall), 1)}"
            how = "taller" if h >= self.video_rows else "wider"
            self.note = [f"make the window {how}:", f"{w}x{h} of {full}"]
        self.step = EDGE_THRESHOLD * max(TUNED / w, 1.0)
        self.glyph = np.full((rows, cols), SPACE, np.uint32)
        self.ink = np.zeros((rows, cols), np.uint32)
        self.paper = np.zeros((rows, cols), np.uint32)
        self.seen = None
        self.held = np.full((h, w, 3), -1.0, np.float32)
        self.inked = np.full((h, w, 3), -999.0, np.float32)
        self.backed = np.full((h, w, 3), -999.0, np.float32)
        self.cap = float("inf")
        self.shown = np.full((h, w), SPACE, np.uint32)
        self.colors = np.zeros((h, w), np.uint32)
        self.way = np.full((h, w), -1, np.int8)
        self.curl = np.zeros((h, w), np.float32)
        self.at = np.indices((h, w)) + 1

    def put(self, y, x, text, ink):
        text = text[:max(self.cols - x, 0)]
        if text and 0 <= y < self.rows and x >= 0:
            span = slice(x, x + len(text))
            self.glyph[y, span] = np.frombuffer(text.encode("utf-32-le"), "<u4")
            self.ink[y, span] = ink

    def convert(self, frame):
        h, w = self.held.shape[:2]
        tall, wide = frame.shape[:2]
        while tall >= 8 * h and wide >= 8 * w:
            even = frame[:tall & -2, :wide & -2]
            frame = cv2.resize(even, None, fx=0.5, fy=0.5,
                               interpolation=cv2.INTER_AREA)
            tall, wide = frame.shape[:2]
        small = cv2.resize(frame, (w, h),
                           interpolation=cv2.INTER_AREA)
        rgb = small[:, :, ::-1].astype(np.float32) / 255.0
        moved = np.abs(rgb - self.held).max(axis=2)
        moved = moved > NOISE_GATE
        self.held[moved] = rgb[moved]
        rgb = self.held
        peak = rgb.max(axis=2)
        lit = peak[peak > BLACK]
        if lit.size:
            cap = 1.0 / float(np.percentile(lit, 99))
            self.gain = min(self.gain, max(cap, self.cap))
            self.cap = cap
        light = np.minimum(peak * self.gain, 1.0)
        soft = cv2.GaussianBlur(light, (0, 0), 1)
        value = light + CLARITY * (light - soft)
        fade = (value - BLACK) / (KNEE - BLACK)
        fade = np.clip(fade, 0.0, 1.0)
        value = 0.5 + (value - 0.5) * CONTRAST
        value = np.clip(value, 0.0, 1.0)
        value *= fade * fade * (3.0 - 2.0 * fade)
        luma = rgb @ LUMA
        gray = luma[..., None]
        tint = gray + (rgb - gray) * SATURATION
        tint = np.maximum(tint, 0.0)
        top = tint.max(axis=2, keepdims=True)
        tint /= np.maximum(top, 1e-4)
        level = value ** GLYPH_GAMMA * (len(RAMP) - 1)
        glyph = GLYPHS[np.rint(level).astype(np.intp)]
        shade = value ** INK_GAMMA
        gx = cv2.Sobel(light, cv2.CV_32F, 1, 0, scale=0.25)
        gy = cv2.Sobel(light, cv2.CV_32F, 0, 1, scale=0.25)
        power = gx * gx + gy * gy
        flat, lean = gy * gy - gx * gx, 2.0 * gx * gy
        score = np.stack((flat, lean, -flat, -lean))
        score += EDGE_STICK * power * (WAYS == self.way)
        way = score.argmax(axis=0).astype(np.int8)
        hold = np.where(self.way < 0, 1.0, EDGE_HOLD)
        force = np.sqrt(power) / hold
        edge = force > self.step
        force[shade * EDGE_INK * 255.0 < FAINT + 8] = 0.0
        force = np.pad(force, 1)
        here = force[1:-1, 1:-1]
        dy = np.where(way == 2, 0, np.sign(gy))
        dx = np.where(way == 0, 0, np.sign(gx))
        dy, dx = dy.astype(np.intp), dx.astype(np.intp)
        ys, xs = self.at
        edge &= here > force[ys + dy, xs + dx]
        edge &= here * 1.15 >= force[ys - dy, xs - dx]
        tilt = cv2.blur(gy, (3, 1))
        tilt = np.pad(tilt, ((1, 1), (0, 0)))
        turn = (tilt[:-2] - tilt[2:]) * np.sign(gx)
        turn += (1.0 - EDGE_HOLD) * CURVE * here * self.curl
        curl = np.sign(turn) * (np.abs(turn) > CURVE * here)
        curl *= edge & (way == 2)
        kind = way.astype(np.intp)
        kind[(way == 0) & (gy < 0)] = 4
        kind[curl > 0], kind[curl < 0] = 5, 6
        glyph = np.where(edge, STROKES[kind], glyph)
        self.way, self.curl = np.where(edge, way, -1), curl
        glow = cv2.dilate(shade, BESIDE)
        glow = np.minimum(shade * EDGE_INK, glow)
        ink = np.where(edge, glow, shade)[..., None] * tint
        ink = np.rint(ink * 255.0)
        blank = self.shown == SPACE
        glyph[ink.max(axis=2) < FAINT + 8 * blank] = SPACE
        same = np.abs(ink - self.inked).max(axis=2)
        same = (same <= INK_GATE) & (glyph == self.shown)
        ink[same] = self.inked[same]
        self.inked, self.shown = ink, glyph
        r, g, b = np.moveaxis(ink.astype(np.uint32), 2, 0)
        self.colors = r << 16 | g << 8 | b
        self.glyph[self.area] = glyph
        self.ink[self.area] = self.colors
        if self.backdrop:
            wash = shade * (glyph != SPACE) * BACKDROP
            wash = np.rint(tint * wash[..., None] * 255.0)
            near = np.abs(wash - self.backed).max(axis=2)
            same = near <= INK_GATE
            wash[same] = self.backed[same]
            self.backed = wash
            wash = wash.astype(np.uint32)
            r, g, b = np.moveaxis(wash, 2, 0)
            self.paper[self.area] = r << 16 | g << 8 | b

    def draw(self):
        glyph, paper = self.glyph, self.paper
        ink = np.where(glyph == SPACE, 0, self.ink)
        if self.seen is None:
            dirty = np.ones(glyph.shape, bool)
            out = ["\x1b[0;48;2;0;0;0m\x1b[2J"]
        else:
            was_glyph, was_ink, was_paper = self.seen
            dirty = (glyph != was_glyph) | (ink != was_ink)
            dirty |= paper != was_paper
            out = []
        ys, xs = np.nonzero(dirty)
        odd = np.argsort(glyph[ys, xs] > 126, kind="stable")
        ys, xs = ys[odd], xs[odd]
        n = self.redrawn = int(ys.size)
        if n:
            g, fg = glyph[ys, xs], ink[ys, xs]
            bg = paper[ys, xs]
            last = np.where(g != SPACE, np.arange(n), 0)
            fg = fg[np.maximum.accumulate(last)]
            jump, inked, papered = np.ones((3, n), bool)
            jump[1:] = ys[1:] != ys[:-1]
            jump[1:] |= xs[1:] != xs[:-1] + 1
            jump[1:] |= g[:-1] > 126
            inked[1:] = fg[1:] != fg[:-1]
            papered[1:] = bg[1:] != bg[:-1]
            cut = np.flatnonzero(jump | inked | papered)
            text = g.astype("<u4").tobytes()
            text = text.decode("utf-32-le")
            runs = zip(cut.tolist(), cut[1:].tolist() + [n],
                       ys[cut].tolist(), xs[cut].tolist(),
                       fg[cut].tolist(), bg[cut].tolist(),
                       jump[cut].tolist(),
                       inked[cut].tolist(),
                       papered[cut].tolist())
            add = out.append
            for a, b, y, x, f, k, move, fore, back in runs:
                if move:
                    add(f"\x1b[{y + 1};{x + 1}H")
                if fore:
                    add("\x1b[38;2;%d;%d;%dm"
                        % (f >> 16, f >> 8 & 255, f & 255))
                if back:
                    add("\x1b[48;2;%d;%d;%dm"
                        % (k >> 16, k >> 8 & 255, k & 255))
                add(text[a:b])
        if out:
            out = "".join(out)
            self.term.write(f"\x1b[?2026h{out}\x1b[?2026l")
        self.seen = glyph.copy(), ink, paper.copy()


class CodePane:
    GUTTER = 7

    def __init__(self, path):
        try:
            with open(path, encoding="utf-8") as source_file:
                source = source_file.read().expandtabs(4)
        except (OSError, UnicodeDecodeError):
            source = "# (source file not found)\n"
        lines = "".join(c if c.isprintable() or c == "\n" else " " for c in source)
        lines = lines.split("\n")[:-1] if lines.endswith("\n") else lines.split("\n")
        count = len(lines)
        self.lines = lines
        self.color = np.full((count, max(map(len, lines)) + 1), TEXT, np.uint32)
        statements = np.array(highlight(source, self.color), np.intp)
        self.first = Renderer.convert.__code__.co_firstlineno - 1
        self.draw_at = Renderer.draw.__code__.co_firstlineno - 1
        if 0 <= self.first < self.draw_at < count:
            self.last = block_end(lines, self.draw_at)
        else:
            self.first, self.draw_at, self.last = 0, 0, count
        marks = np.zeros(count, np.intp)
        marks[statements] = statements
        self.statement = np.maximum.accumulate(marks)
        margins = [len(line) - len(line.lstrip())
                   for line in lines[self.first:self.last] if line.strip()]
        self.margin = min(margins, default=0)
        self.laid = {}

    def lay(self, room):
        if room in self.laid:
            return self.laid[room]
        rows, starts = [], []
        for i in range(self.first, self.last):
            line = self.lines[i]
            skip = len(line) - len(line.lstrip())
            dent = min(max(skip - self.margin, 0), room // 2)
            hang = min(dent + 4, room // 2)
            starts.append(len(rows))
            at, shift = skip, dent
            while True:
                cut = len(line)
                if cut - at > room - shift:
                    cut = line.rfind(" ", at + 1, at + room - shift + 1)
                if cut <= at:
                    word = line.find(" ", at + 1)
                    word = len(line) if word < 0 else word
                    shift = max(min(shift, room - word + at), 0)
                    cut = min(word, at + room - shift)
                rows.append((i, at, cut, shift))
                at, shift = cut + (line[cut:cut + 1] == " "), hang
                if at >= len(line):
                    break
        text = np.full((len(rows), self.GUTTER + room), SPACE, np.uint32)
        color = np.full(text.shape, TEXT, np.uint32)
        color[:, :self.GUTTER] = GUTTER_FG
        for row in starts:
            number = f" {rows[row][0] + 1:>4}"
            text[row, :len(number)] = np.frombuffer(number.encode("utf-32-le"), "<u4")
        for row, (i, at, cut, shift) in enumerate(rows):
            span = slice(self.GUTTER + shift, self.GUTTER + shift + cut - at)
            text[row, span] = np.frombuffer(self.lines[i][at:cut].encode("utf-32-le"),
                                            "<u4")
            color[row, span] = self.color[i, at:cut]
        starts = np.array(starts + [len(rows)], np.intp)
        opens = np.maximum(self.statement[self.first:self.last], self.first)
        opens = starts[opens - self.first]
        reach = int((starts[1:] - 1 - opens).max(initial=0))
        self.laid[room] = text, color, starts, reach
        return self.laid[room]

    def paint(self, screen, now, info):
        top, left = screen.pane_top, screen.pane_left
        rows, cols = screen.pane_rows, screen.pane_cols
        if rows < 1 or cols < 1:
            return
        glyph, ink, paper = (grid[top:top + rows, left:left + cols]
                             for grid in (screen.glyph, screen.ink, screen.paper))
        glyph[:], ink[:], paper[:] = SPACE, TEXT, PANE_BG
        paper[0] = BAR_BG
        title = TITLE if cols >= len(TITLE) + 18 else TITLE.split(" — ")[0]
        start = max((cols - len(title)) // 2, 0)
        screen.put(top, left + start, title[:cols - start], BAR_FG)
        if start >= 9:
            for i, light in enumerate(LIGHTS):
                screen.put(top, left + 2 + 2 * i, "●", light)
        text, color, starts, reach = self.lay(max(cols - self.GUTTER - 1, 1))
        body = rows - 1 - (rows > 4)
        head = self.first + int(now * SCROLL_SPEED) % (self.last - self.first)
        current = max(int(self.statement[head]), self.first)
        mark, below = starts[current - self.first], starts[current - self.first + 1]
        foot = starts[head - self.first + 1] - 1
        lead = min(max(body // 3, reach), max(body - 1, 0))
        view = min(max(foot - lead, 0), max(len(text) - body, 0))
        view = min(view, mark)
        shown = max(min(body, len(text) - view), 0)
        width = min(cols, text.shape[1])
        glyph[1:1 + shown, :width] = text[view:view + shown, :width]
        ink[1:1 + shown, :width] = color[view:view + shown, :width]
        for row in range(max(mark, view), min(below, view + shown)):
            paper[1 + row - view] = LINE_BG
            ink[1 + row - view, :self.GUTTER] = MARK
            screen.put(top + 1 + row - view, left, "▎", MARK)
        if rows > 4:
            method = "convert" if head < self.draw_at else "draw"
            status = f"  Renderer.{method}()  Ln {current + 1}"
            paper[rows - 1] = BAR_BG
            screen.put(top + rows - 1, left, status[:cols], BAR_FG)
            room = cols - len(f"  Renderer.convert()  Ln {self.last}") - 4
            while info and len("  ".join(info)) > room:
                info = info[1:]
            stats = "  ".join(info)
            screen.put(top + rows - 1, left + cols - len(stats) - 2, stats, COMMENT)


def brighten(ink, ys, xs, share):
    rgb = ink[ys, xs][:, None] >> SHIFTS & 255
    rgb = rgb + (255.0 - rgb) * np.clip(share, 0.0, 1.0)[:, None]
    r, g, b = np.rint(rgb).astype(np.uint32).T
    ink[ys, xs] = r << 16 | g << 8 | b


class Sprinkles:
    def __init__(self, seed=7):
        self.seed, self.lap = seed, TURN or 10.0
        self.size, self.then, self.drops, self.hits = None, None, [], []

    def fall(self, screen, now):
        glyph, ink = screen.glyph[screen.area], screen.ink[screen.area]
        h, w = glyph.shape
        if self.size != (h, w):
            self.size, self.drops = (h, w), []
            self.glint = np.zeros((h, w), np.float32)
            rng = random.Random(self.seed)
            self.cast = []
            for _ in range(round(SPRINKLES * w / TUNED * self.lap)):
                speed = rng.uniform(0.35, 0.8)
                self.cast.append((rng.random(), rng.randrange(w), rng.random(),
                                  h * speed, int(rng.random() * h * SOAK),
                                  int(speed * 4.0 - 1.0), True))
            self.due = np.array([drop[0] for drop in self.cast])
        past = 0.0 if self.then is None else min(max(now - self.then, 0.0), 0.1)
        self.then = now
        self.glint -= past / GLINT
        np.maximum(self.glint, 0.0, out=self.glint)
        lit, falling, self.hits = screen.shown != SPACE, [], []
        over = self.over = np.cumsum(lit[::-1], axis=0)[::-1] > 0
        laps = np.floor(now / self.lap - self.due)
        for i in np.flatnonzero(laps > np.floor((now - past) / self.lap - self.due)):
            if over[0, self.cast[i][1]]:
                self.drops.append(list(self.cast[i][1:]))
        for drop in self.drops:
            x, y, speed, deep = drop[:4]
            y, above = y + speed * past, int(y)
            for row in range(above + 1, min(int(y), h - 1) + 1):
                if lit[row, x]:
                    if drop[5]:
                        drop[5] = False
                        self.hits.append((x, row, speed))
                    if not deep:
                        self.glint[row, x] = 1.0
                        break
                    deep -= 1
                elif not over[row, x]:
                    break
            else:
                if y < h and over[int(y), x]:
                    drop[1], drop[3] = y, deep
                    falling.append(drop)
        self.drops = falling
        ys, xs = np.nonzero((self.glint > 0.0) & lit)
        if ys.size:
            brighten(ink, ys, xs, self.glint[ys, xs])
        for x, y, _, _, trail, _ in self.drops:
            for back, (mark, gray) in enumerate(TRAIL[:trail], 1):
                if y >= back and not lit[int(y) - back, x]:
                    glyph[int(y) - back, x], ink[int(y) - back, x] = mark, gray
        for x, y, _, _, _, _ in self.drops:
            glyph[int(y), x] = SPECK[int(y % 1.0 * len(SPECK))]
            ink[int(y), x] = 0xFFFFFF


class Flourish:
    def __init__(self, stage, rain=True, more=True, seed=3):
        self.stage, self.more, self.seed = stage, more, seed
        self.rain = Sprinkles() if rain else None
        self.lap = TURN or 10.0
        self.size = self.then = None

    def fit(self, h, w):
        self.size, self.bits, self.glows = (h, w), np.zeros((0, TONE + 1)), []
        rng = random.Random(self.seed)
        count = round((PETALS + HEARTS) * self.lap * w / TUNED)
        self.cast = [[rng.random() for _ in range(8)] for _ in range(count)]
        self.due = np.array([one[0] for one in self.cast])
        self.grain = np.random.RandomState(self.seed).random_sample((h, w))
        self.ys, self.xs = np.mgrid[0:h, 0:w].astype(np.float32)
        self.slant = self.xs / w + 0.5 * self.ys / h

    def play(self, screen, now, at):
        glyph, ink = screen.glyph[screen.area], screen.ink[screen.area]
        glyph[:], ink[:] = screen.shown, screen.colors
        if self.more:
            if self.size != glyph.shape:
                self.fit(*glyph.shape)
            if self.then is None or at < self.then:
                self.then, self.bits, self.glows = at - 1e-6, self.bits[:0], []
            (h, w), (high, across) = glyph.shape, self.stage.shape
            x0, y0 = self.stage.box[:2]
            self.squash = h * across / (w * high)
            self.mouth = ((self.stage.mouth[0] - x0) / across * w,
                          (self.stage.mouth[1] - y0) / high * h)
            self.shine(screen, glyph, ink, at)
        if self.rain:
            self.rain.fall(screen, now)
        if self.more:
            self.cue(screen, at)
            self.drift(screen, glyph, ink, at)
            self.then = at

    def shine(self, screen, glyph, ink, at):
        lit = screen.shown != SPACE
        glow = np.zeros(glyph.shape, np.float32)
        rows = np.flatnonzero(lit.any(axis=1))
        if at < DECODE and rows.size:
            rank = (self.ys - rows[0]) / (rows[-1] - rows[0] + 1.0)
            wait = DECODE * (0.3 + 0.45 * rank + 0.25 * self.grain) - at
            pick = (self.grain * 977.0 + int(at * 15.0) * 0.618) % 1.0
            pick = (pick * (len(RAMP) - 1)).astype(np.intp) + 1
            mixed = lit & (wait > 0.0)
            glyph[mixed] = GLYPHS[pick][mixed]
            ink[mixed] = ink[mixed] >> 1 & 0x7F7F7F
            glyph[lit & (wait > SCRAMBLE)] = SPACE
            glow = 0.6 * np.clip(1.0 + wait / 0.2, 0.0, 1.0) * (wait <= 0.0)
        sweep = (at + self.lap / 4.0) % (self.lap / 2.0) / SWEEP
        if sweep < 1.0:
            near = np.abs(self.slant + 0.15 - 1.8 * sweep)
            near = np.clip(1.0 - near / 0.1, 0.0, 1.0)
            glow = np.maximum(glow, SHEEN * near * near * (3.0 - 2.0 * near))
        for flower in self.stage.blooms:
            ahead = (flower.done - at) / RISE
            if 0.0 < ahead <= 1.0:
                x, y, reach = self.spot(flower, at)
                x, y = x + (self.mouth[0] - x) * ahead, y + (self.mouth[1] - y) * ahead
                far = np.hypot(self.xs - x, (self.ys - y) / self.squash) / reach
                glow = np.maximum(glow, 0.8 * np.clip(1.0 - 2.0 * far, 0.0, 1.0))
        for x, y, reach, born in self.glows:
            far = np.hypot(self.xs - x, (self.ys - y) / self.squash) / reach
            fade = 0.9 * (1.0 - (at - born) / POP)
            glow = np.maximum(glow, fade * np.clip(1.4 - far, 0.0, 1.0))
        self.glows = [one for one in self.glows if at - one[3] < POP]
        since = at - self.stage.over - BEAT
        if 0.0 <= since < FLASH:
            glow = np.maximum(glow, 0.6 * (1.0 - since / FLASH) ** 2)
        ys, xs = np.nonzero((glow > 0.01) & (glyph != SPACE))
        if ys.size:
            brighten(ink, ys, xs, glow[ys, xs])

    def spot(self, flower, at):
        x, y, reach = self.stage.spot(flower, at)
        return x * self.size[1], y * self.size[0], max(reach * self.size[1], 0.5)

    def tone(self, screen, x, y, reach):
        high, wide = 0.5 * reach * self.squash, 0.5 * reach
        patch = screen.colors[max(int(y - high), 0):max(int(y + high) + 1, 0),
                              max(int(x - wide), 0):max(int(x + wide) + 1, 0)]
        rgb = (patch.reshape(-1, 1) >> SHIFTS & 255).astype(np.int64)
        if not rgb.size or rgb.max() < 48:
            return 0xFFFFFF
        best = rgb[(2 * rgb.max(axis=1) - rgb.min(axis=1)).argmax()]
        r, g, b = (best * 255 // best.max()).tolist()
        return r << 16 | g << 8 | b

    def burst(self, x, y, reach, count, tone, life, fan=(0.0, 2.0), pull=0.0):
        order = np.arange(max(count, 1))
        turn = (order + (order * 0.618 + x) % 1.0) / len(order)
        turn = np.pi * (fan[0] + (fan[1] - fan[0]) * turn)
        far = reach * (0.45 + 0.55 * ((order * 0.755 + y) % 1.0))
        speed = far * DRAG / (1.0 - np.exp(-DRAG * life))
        bits = np.zeros((len(order), TONE + 1))
        bits[:, X], bits[:, Y] = x, y
        bits[:, VX] = np.cos(turn) * speed
        bits[:, VY] = np.sin(turn) * speed * self.squash
        bits[:, PULL], bits[:, SLOW] = pull, DRAG
        bits[:, LIFE], bits[:, TONE] = life * (0.7 + 0.3 * (order * 0.371 % 1.0)), tone
        return bits

    def cue(self, screen, at):
        h, w = self.size
        stage, then, squash, born = self.stage, self.then, self.squash, []
        sparks = round(BURST * w / TUNED)
        for flower in stage.blooms:
            if then < flower.wait <= at:
                born.append(self.burst(*self.mouth, 0.16 * w, sparks // 2, 0xD8FFD0, 0.8,
                                       (1.3, 1.7), 0.35 * h))
            if then < flower.done <= at:
                x, y, reach = self.spot(flower, at)
                self.glows.append((x, y, reach, at))
                born.append(self.burst(x, y, 2.3 * reach,
                                       round(sparks * (0.5 + 0.7 * flower.size)),
                                       self.tone(screen, x, y, reach), 1.2,
                                       pull=0.12 * h))
            if then < stage.over + BEAT <= at:
                x, y, reach = self.spot(flower, at)
                born.append(self.burst(x, y, 2.6 * reach, sparks, 0xFFE9A8, 1.6,
                                       pull=0.15 * h))
        laps = np.floor(at / self.lap - self.due)
        for i in np.flatnonzero(laps > np.floor(then / self.lap - self.due)):
            _, kind, pick, a, b, c, d, e = self.cast[i]
            flower = stage.blooms[int(pick * len(stage.blooms))]
            heart = kind * (PETALS + HEARTS) < HEARTS
            if at < (stage.over + BEAT if heart else flower.done):
                continue
            x, y, reach = self.spot(flower, at)
            if heart:
                x, y = x + (a - 0.5) * reach, y - 0.6 * reach * squash
                life, tone = FINALE * (0.45 + 0.2 * e), PINKS[int(c * len(PINKS))]
                for half in (0, 1):
                    born.append([x + half, y, 0.0, -(0.03 + 0.025 * d) * h, 0.0, 0.0, 0.0,
                                 life, 0.012 * w, 2.0 + d, 6.28 * b, HEART + half, tone])
            else:
                tone = self.tone(screen, x, y, reach)
                x, y = x + (a - 0.5) * 1.6 * reach, y + (b - 0.5) * 0.8 * reach * squash
                born.append([x, y, (c - 0.5) * 0.03 * w, (0.045 + 0.05 * d) * h, 0.0, 0.0,
                             0.0, FINALE * (0.6 + 0.3 * e), (0.012 + 0.02 * e) * w,
                             2.0 + 3.0 * d, 6.28 * a, PETAL, tone])
        for x, row, speed in self.rain.hits if self.rain else ():
            odd, more = speed * 7.919 % 1.0, speed * 3.317 % 1.0
            if odd < 0.5:
                way = (0.05 + 0.1 * more) * w * (1.0 if odd < 0.25 else -1.0)
                born.append([x + 0.5, row - 0.5, way, -(0.15 + 0.15 * more) * h, 1.5 * h,
                             0.0, 0.0, 0.35, 0.0, 0.0, 0.0, SPLASH, 0xD0D0D0])
        if born:
            self.bits = np.vstack((self.bits, *born))

    def drift(self, screen, glyph, ink, at):
        h, w = glyph.shape
        past, bits = min(at - self.then, 0.1), self.bits
        slow = np.exp(-bits[:, SLOW] * past)
        bits[:, VX] *= slow
        bits[:, VY] = bits[:, VY] * slow + bits[:, PULL] * past
        bits[:, X] += bits[:, VX] * past
        bits[:, Y] += bits[:, VY] * past
        bits[:, AGE] += past
        bits = self.bits = bits[(bits[:, AGE] < bits[:, LIFE]) & (bits[:, Y] < h)]
        aged, kind = bits[:, AGE] / bits[:, LIFE], bits[:, KIND].astype(np.intp)
        sway = bits[:, RATE] * bits[:, AGE] + bits[:, PHASE]
        col = np.floor(bits[:, X] + bits[:, SWING] * np.sin(sway)).astype(np.intp)
        row = np.floor(bits[:, Y]).astype(np.intp)
        seen = (col >= 0) & (col < w) & (row >= 0)
        dry = screen.shown[row[seen], col[seen]] == SPACE
        if self.rain:
            dry &= self.rain.over[row[seen], col[seen]]
        seen[seen] &= (kind[seen] != SPLASH) | dry
        col, row, kind, aged, sway = (each[seen] for each in (col, row, kind, aged, sway))
        step = np.where(kind == PETAL, sway / (2.0 * np.pi) % 1.0, aged) * 12.0
        glyph[row, col] = SHAPES[kind, step.astype(np.intp)]
        tone = bits[seen, TONE].astype(np.uint32)[:, None] >> SHIFTS & 255
        hot = np.clip(1.0 - 3.0 * aged, 0.0, 1.0) * (kind == SPARK)
        tone = tone + (255.0 - tone) * hot[:, None]
        tone = tone * np.clip(1.5 - 1.5 * aged, 0.2, 1.0)[:, None]
        r, g, b = tone.astype(np.uint32).T
        ink[row, col] = r << 16 | g << 8 | b
        lap, flaps = 2.0 * np.pi * at / self.lap, 4 * round(2.5 * self.lap)
        span = self.stage.over - self.stage.lead
        for k, (across, level, up, tone) in enumerate(FLIGHT):
            since = at - self.stage.lead - (0.45 + 0.17 * k) * span
            if since < 0.0:
                continue
            away = np.sign(across) * max(1.0 - since / 4.0, 0.0) ** 2
            x = w * (0.5 + across * np.sin(lap + 2.0 * k + 0.3) + away)
            y = level + up * np.sin(2.0 * lap + 1.3 * k) + 0.012 * np.sin(9.0 * lap + k)
            col, row = int(np.floor(x)), int(h * y)
            if 0 <= row < h and 0 <= col < w - 1:
                beat = int(at / self.lap * flaps + 2 * k + 0.25)
                glyph[row, col:col + 2] = WING[beat % 4]
                ink[row, col:col + 2] = tone


def clock(seconds):
    return f"{int(seconds) // 60}:{int(seconds) % 60:02d}"


def glance(frame):
    step = max(frame.shape[1] // 640, 1)
    small = np.ascontiguousarray(frame[::step, ::step])
    return cv2.resize(small, (160, 90), interpolation=cv2.INTER_AREA).max(axis=2)


def lit_box(top, level):
    lit = top > level
    xs, ys = np.flatnonzero(lit.any(axis=0)), np.flatnonzero(lit.any(axis=1))
    if not xs.size:
        return None
    return (xs[0] / top.shape[1], ys[0] / top.shape[0],
            (xs[-1] + 1) / top.shape[1], (ys[-1] + 1) / top.shape[0])


def join(a, b):
    if not (a and b):
        return a or b
    return min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3])


def survey(path, samples=4):
    probe = cv2.VideoCapture(path)
    total = int(probe.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = probe.get(cv2.CAP_PROP_FPS)
    first, deadline = [], time.perf_counter() + 0.5
    while len(first) < (fps if 0.0 < fps <= 240.0 else 30.0):
        ok, frame = probe.read()
        if not ok or time.perf_counter() > deadline:
            break
        first.append(glance(frame))
    spread, peaks, deadline = [], [], time.perf_counter() + 0.5
    for i in (2, 3, 1, 0)[:max(min(total, samples), 0)]:
        began = time.perf_counter()
        probe.set(cv2.CAP_PROP_POS_FRAMES, total * (2 * i + 1) // (2 * samples))
        ok, frame = probe.read()
        if not ok:
            break
        top = glance(frame)
        spread.append(top)
        dark = max(BLACK * 255, np.percentile(top, 99) / 2)
        lit = top[top > dark]
        if lit.size:
            peaks.append(float(np.percentile(lit, 99)) / 255.0)
        now = time.perf_counter()
        if now + (now - began) > deadline:
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
        band = early[3] - 0.15 * (early[3] - early[1])
        xs = [np.nonzero(top[int(band * 90):] > level)[1] for top in first]
        xs = np.concatenate(xs)
        if xs.size:
            stem = (float(np.median(xs)) + 0.5) / 160.0, early[3]
    return white, lit if lit.any() else None, stem


def lengthen(film, rows, more):
    stalk = film[-max(rows, 1):]
    if more < 1 or not len(stalk):
        return film
    turns = -(-more // (2 * len(stalk)))
    return np.vstack((film,) + (stalk[::-1], stalk) * turns)[:len(film) + more]


def hue_turn(degrees):
    cos, sin = np.cos(np.radians(degrees)), np.sin(np.radians(degrees)) / 3.0 ** 0.5
    turn = cos * np.eye(3) + (1.0 - cos) / 3.0
    turn += sin * np.array([[0.0, -1.0, 1.0], [1.0, 0.0, -1.0], [-1.0, 1.0, 0.0]])
    return np.ascontiguousarray(turn[::-1, ::-1], np.float32)


def paint_vase(wide, high, color, white):
    y, x = np.mgrid[0:high, 0:wide].astype(np.float32) + 0.5
    v, off = y / high, x - wide / 2.0
    rim, gap = 0.13, 0.08
    body = 0.9 - (0.9 - VASE_FOOT) * (v - rim) / (1.0 - rim)
    half = np.where(v < rim, 1.0, body) * wide / 2.0
    cover = np.clip(half - np.abs(off) + 0.5, 0.0, 1.0)
    u = np.clip(off / half, -1.0, 1.0)
    lit = np.clip(0.8 * u + 0.6 * np.sqrt(1.0 - u * u), 0.0, 1.0)
    shade = 0.36 + 0.48 * lit + 0.16 * np.exp(-((u - 0.3) / 0.2) ** 2)
    shade *= 1.0 - 0.65 * np.clip(1.0 - (v - rim) / gap, 0.0, 1.0) * (v >= rim)
    base = np.array([color & 255, color >> 8 & 255, color >> 16], np.float32)
    warm = np.abs(u)[..., None] ** 3 * 0.45 * np.array([0.30, 0.14, 0.0], np.float32)
    picture = base * (1.0 - warm) * (np.clip(shade, 0.0, 1.0) * white * 0.97)[..., None]
    return picture, cover, np.where(v < rim, np.nan, np.arcsin(u))


class Flower:
    def __init__(self, around, tilt, size, turn, pale, wait, opens, length):
        self.around, self.tilt = np.radians(around), np.radians(tilt)
        self.size, self.pale, self.wait = size, pale, wait
        self.turn = hue_turn(turn) if turn else None
        self.flip = around >= 180.0 and bool(turn or pale)
        self.sprout = SPROUT * size ** 0.5
        self.cut = STEMS * max(1.0 - 0.5 / size, 0.0)
        self.last = opens * length if length and opens < 1.0 else float("inf")
        self.held = self.kept = None


class Stage:
    def __init__(self, shape, white, lit, stem, crop=True, vase=VASE_COLOR,
                 flowers=FLOWERS, length=0.0):
        self.high, self.wide = shape[:2]
        self.level, self.dark = LIT * 255.0 * white, BLACK * 255.0 * white
        self.crop, self.vase, self.blooms, self.subject = crop, None, [], None
        self.box, self.shrink, self.painted = (0, 0, self.wide, self.high), 1, False
        self.lead = self.tail = self.clock = 0.0
        self.pace, self.lit = 1.0, lit
        box = lit_box(lit, 0) if lit is not None else None
        if not box or (box[2] - box[0]) * (box[3] - box[1]) > 0.8:
            self.crop = False
            return
        self.painted = bool(stem) and (vase is not None or flowers > 1)
        if self.painted:
            reach = max((box[2] - box[0]) * self.wide, (box[3] - box[1]) * self.high)
            self.shrink = max((int(reach) + 359) // 360, 1)
            self.wide, self.high = self.wide // self.shrink, self.high // self.shrink
            self.box = (0, 0, self.wide, self.high)
        self.subject = subject = self.pixels(box)
        wide, high = subject[2] - subject[0], subject[3] - subject[1]
        if self.painted:
            self.mouth = np.array([stem[0] * self.wide, stem[1] * self.high])
            self.head = np.array([self.mouth[0], subject[1] + HEAD * high])
            self.look = np.cos(np.radians(LOOK)), np.sin(np.radians(LOOK))
            self.span, self.pace = wide, PACE if flowers > 1 else 1.0
            picks = BOUQUET[:flowers] if flowers > 1 else ((0.0, 0.0, 1.0, 0.0, 0.0) +
                                                           BOUQUET[0][5:],)
            self.blooms = [Flower(*pick, length) for pick in picks]
            tall = (self.mouth[1] - self.head[1]) * (LONG if flowers > 1 else 1.0)
            for flower in self.blooms:
                flower.stem = tall - flower.cut * high * (flowers > 1)
                flower.stub = min(STUB * high, flower.stem)
                opening = min(flower.last, length) / self.pace if length else 5.0
                flower.climb = max(CLIMB * opening, flower.sprout)
                flower.done = flower.wait + max(opening, flower.sprout)
            self.deep = int(np.ceil(self.head[1] + tall))
            self.stalk = STALK * high
            self.gaps = cv2.getStructuringElement(cv2.MORPH_ELLIPSE,
                                                  (wide // 16 | 1, wide // 16 | 1))
            waits = [flower.wait for flower in self.blooms]
            self.lead, late = min(waits), max(waits)
            grown = max(flower.wait + flower.climb for flower in self.blooms)
            over = max(flower.wait + min(flower.last, length) / self.pace
                       for flower in self.blooms)
            self.over = over = max(over, grown)
            self.tail = max(over - length / self.pace, self.lead) + FINALE + ENCORE
            self.tail -= self.lead
            self.reel = collections.deque(maxlen=MEMORY)
            self.every = (late - self.lead) * self.pace / (MEMORY - 2)
            self.fed = self.fresh = None
        bunch = self.reach(lit)
        hold = bunch if crop else join(bunch, self.box)
        grow = ((bunch[2] - bunch[0]) / wide) ** 0.75
        w, h = round(VASE_WIDTH * wide * grow), round(VASE_HEIGHT * high * grow)
        if self.painted and vase is not None and w >= 4 and h >= 4:
            picture, cover, around = paint_vase(w, h, vase, white)
            cover = np.rint(cover * 256.0).astype(np.uint16)[..., None]
            left = round(stem[0] * self.wide - w / 2)
            top = round(stem[1] * self.high - 0.05 * h)
            self.vase = left, top, picture, cover, around
            hold = join(hold, (left, top, left + w, top + h))
        self.front = 0.3 * w
        self.box = self.framed(hold)

    def pixels(self, box):
        return (int(box[0] * self.wide), int(box[1] * self.high),
                round(box[2] * self.wide), round(box[3] * self.high))

    def place(self, flower, grown=1.0, turn=0.0, risen=1.0):
        tilt = flower.tilt * (0.5 + 0.5 * grown)
        x = np.sin(tilt) * np.sin(flower.around + turn)
        near = np.sin(tilt) * np.cos(flower.around + turn)
        up = np.cos(tilt) * self.look[0] - near * self.look[1]
        seems = np.hypot(x, up)
        size = flower.size * grown * (1.0 + DEPTH * near)
        lay = size / seems * np.array([[up, -x], [x, up]])
        if flower.flip:
            lay[:, 0] *= -1.0
        stem = flower.stub + (flower.stem - flower.stub) * risen
        root = self.head + (0.0, stem * seems)
        to = self.mouth + (0.1 * self.span * x, 0.0)
        place = np.hstack((lay, (to - lay @ root)[:, None]))
        return place, near * stem * flower.size * grown, root[1]

    def pose(self, flower, age):
        grown = min(age / flower.sprout, 1.0)
        grown *= grown * (3.0 - 2.0 * grown)
        risen = min(age / flower.climb, 1.0)
        return grown, risen * (2.0 - risen)

    def spot(self, flower, now):
        turn = 2.0 * np.pi * now / TURN if TURN else 0.0
        grown, risen = self.pose(flower, max(now - flower.wait, 0.0))
        place = self.place(flower, grown, turn, risen)[0]
        x, y = place @ (self.head[0], self.head[1], 1.0)
        x0, y0, x1, y1 = self.box
        reach = HEAD * (self.subject[3] - self.subject[1]) * np.hypot(*place[:, 1])
        return (x - x0) / (x1 - x0), (y - y0) / (y1 - y0), reach / (x1 - x0)

    def reach(self, lit):
        box = self.pixels(lit_box(lit, 0))
        if not self.blooms:
            return box
        fine = np.array([lit.shape[1] / self.wide, lit.shape[0] / self.high])
        room = np.zeros((3 * lit.shape[0], 3 * lit.shape[1]), np.uint8)
        foot = min(self.subject[3], round(self.mouth[1]))
        long = lengthen(lit[:round(foot * fine[1])].astype(np.uint8) * 255,
                        round(self.stalk * fine[1]),
                        round((self.deep - foot) * fine[1]))
        for flower in self.blooms:
            for turn in np.arange(16) * np.pi / 8 if flower.tilt and TURN else (0.0,):
                place, _, cut = self.place(flower, 1.0, turn)
                here = long.copy()
                here[round(cut * fine[1]):] = 0
                lay = place[:, :2] * fine[:, None] / fine[None, :]
                move = place[:, 2] * fine + lit.shape[::-1]
                cv2.max(room, cv2.warpAffine(here, np.hstack((lay, move[:, None])),
                                             room.shape[::-1]), room)
        far = lit_box(room, 64)
        if far is None:
            return box
        wide, high = 3 * self.wide, 3 * self.high
        air = 1.0 / lit.shape[1]
        return (int((far[0] - air) * wide) - self.wide,
                int((far[1] - air) * high) - self.high,
                round((far[2] + air) * wide) - self.wide,
                round((far[3] + air) * high) - self.high)

    def framed(self, box):
        air = round(CROP_MARGIN * max(box[2] - box[0], box[3] - box[1])) * self.crop
        box = box[0] - air, box[1] - air, box[2] + air, box[3] + air
        if self.subject and self.painted:
            return box
        return (max(box[0], 0), max(box[1], 0),
                min(box[2], self.wide), min(box[3], self.high))

    @property
    def shape(self):
        return self.box[3] - self.box[1], self.box[2] - self.box[0]

    def fit(self, frame):
        lit = glance(frame) > self.level if self.subject else None
        if lit is None or not (lit & ~self.lit).any():
            return False
        self.lit = self.lit | lit
        self.subject = join(self.subject, self.pixels(lit_box(lit, 0)))
        seen = self.reach(self.lit)
        if join(self.box, seen) == self.box:
            return False
        self.box = join(self.box, self.framed(seen))
        return True

    def take(self, frame, seen):
        if self.shrink > 1:
            frame = cv2.resize(frame, (self.wide, self.high),
                               interpolation=cv2.INTER_AREA)
        sx0, sy0, sx1, sy1 = self.subject
        film = frame[sy0:sy1, sx0:sx1]
        if not film.size:
            return None
        lit = film.max(axis=(1, 2)) > self.level
        foot = max(min(sy1, round(self.mouth[1])) - sy0, 1)
        rows = np.flatnonzero(lit[:foot])
        foot = int(rows[-1]) + 1 if rows.size else foot
        dark = np.flatnonzero(~lit[foot:])
        film = np.ascontiguousarray(film[:foot + int(dark[0])] if dark.size else film)
        film = lengthen(film, round(self.stalk), self.deep - sy0 - len(film))
        blue, green, red = cv2.split(film)
        other = cv2.max(blue, red)
        peak = cv2.max(other, green)
        solid = cv2.subtract(cv2.blur(peak, (5, 5)), self.level * 0.6)
        solid = cv2.multiply(solid, 255.0 / self.level)
        solid = cv2.morphologyEx(solid, cv2.MORPH_CLOSE, self.gaps)
        leaf = cv2.subtract(cv2.blur(cv2.subtract(green, other), (5, 5)), 6)
        leaf = cv2.multiply(leaf, 8)
        return seen, (sx0, sy0), film, solid, leaf, peak

    def find(self, flower, want):
        for frame in (self.fresh, *reversed(self.reel)):
            if frame[0] <= want + 1e-6:
                if flower.held is None or frame[0] > flower.held[0]:
                    flower.held = frame
                break
        if flower.held is None:
            flower.held = self.reel[0] if self.reel else self.fresh
        return flower.held

    def tint(self, flower, frame):
        if flower.kept and flower.kept[0] is frame:
            return flower.kept[1]
        _, _, film, cover, leaf, peak = frame
        tinted = film
        if flower.turn is not None or flower.pale:
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

    def paint(self, flower, frame, grown, turn, risen):
        place, near, cut = self.place(flower, grown, turn, risen)
        (sx0, sy0), cover = frame[1], frame[3]
        rows = min(max(round(cut) - sy0, 0), cover.shape[0])
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
        x0, y0, x1, y1 = self.box
        if not (self.subject and self.painted):
            return frame[y0:y1, x0:x1]
        if now < self.clock:
            self.fed = self.fresh = None
            self.reel.clear()
            for flower in self.blooms:
                flower.held = flower.kept = None
        self.clock = now
        seen = (now - self.lead) * self.pace
        if seen >= 0.0 and frame is not self.fed:
            self.fed, self.fresh = frame, self.take(frame, seen)
            if self.fresh and (not self.reel or seen - self.reel[-1][0] >= self.every):
                self.reel.append(self.fresh)
        turn = 2.0 * np.pi * now / TURN if TURN else 0.0
        layers = []
        for flower in self.blooms if self.fresh else ():
            age = now - flower.wait
            if age < 0.0:
                continue
            shown = self.find(flower, min(age * self.pace, flower.last))
            grown, risen = self.pose(flower, age)
            layer = self.paint(flower, shown, grown, turn, risen)
            if layer:
                layers.append(layer)
        if self.vase:
            left, top, picture, cover, around = self.vase
            flutes = 0.5 + 0.5 * np.cos(FLUTES * (around + turn))
            flutes = 1.0 - 0.34 * np.nan_to_num(flutes)
            paint = (picture * flutes[..., None] * cover).astype(np.uint16)
            layers.append((self.front, left, top, paint, 256 - cover))
        canvas = np.zeros((y1 - y0, x1 - x0, 3), np.uint8)
        for _, left, top, paint, clear in sorted(layers, key=lambda layer: layer[0]):
            back = canvas[top - y0:top - y0 + paint.shape[0],
                          left - x0:left - x0 + paint.shape[1]]
            if paint.dtype == np.uint16:
                back[:] = (back * clear + paint) >> 8
            else:
                back[:] = cv2.add(paint, cv2.multiply(back, clear, scale=1.0 / 255.0))
        return canvas


class Reel:
    def __init__(self, path):
        self.path, self.film = path, cv2.VideoCapture(path)
        self.lead, self.tail, self.step = 0, 0, 1.0
        self.rewind(again=False)

    def rewind(self, again=True):
        if again:
            self.film.set(cv2.CAP_PROP_POS_FRAMES, 0)
        ok, first = self.film.read()
        if not ok and again:
            self.film.release()
            self.film = cv2.VideoCapture(self.path)
            ok, first = self.film.read()
        self.first = self.final = first if ok else None
        self.at, self.got = 0, 0
        self.stale, self.spare = False, None
        return ok

    def read(self, skip=False):
        if self.first is None:
            return False, None
        at, self.at = self.at, self.at + 1
        want = int(max(at - self.lead, 0) * self.step)
        while self.spare is None and self.got < want:
            if self.film.grab():
                self.got, self.stale = self.got + 1, True
            else:
                self.spare = self.tail
        if self.stale and not (skip and self.spare is None):
            ok, frame = self.film.retrieve()
            self.final, self.stale = frame if ok else self.final, False
        if self.spare is None:
            return True, None if skip else self.final
        self.spare -= 1
        return (True, self.final) if self.spare >= 0 else (False, None)

    def grab(self):
        return self.read(skip=True)[0]

    def release(self):
        self.film.release()


def play(path, loop=True, cols=GRID_COLS, backdrop=False, crop=True, vase=VASE_COLOR,
         flowers=FLOWERS, sprinkles=True, plain=False):
    video = Reel(path)
    frame, film = video.first, video.film
    if frame is None:
        sys.exit(f"ascii_player: could not read any video frames from {path!r}")
    fps = film.get(cv2.CAP_PROP_FPS)
    fps = fps if 0.0 < fps <= 240.0 else 30.0
    wide = film.get(cv2.CAP_PROP_SAR_NUM) / (film.get(cv2.CAP_PROP_SAR_DEN) or 1.0)
    wide = wide if 0.1 < wide < 10.0 else 1.0
    total = max(int(film.get(cv2.CAP_PROP_FRAME_COUNT)), 0)
    name, info, count = cells(os.path.basename(path)), [], "   0 cells redrawn"
    term = Terminal()
    white, lit, stem = survey(path)
    stage = Stage(frame.shape, white, lit, stem, crop, vase, flowers, total / fps)
    stage.fit(frame)
    video.lead, video.tail = round(stage.lead * fps), round(stage.tail * fps)
    video.step = stage.pace
    length = video.lead + total / stage.pace + video.tail
    length = f" / {clock(length / fps)}" if total else ""
    extras = stage.blooms and (sprinkles or not plain)
    extras = Flourish(stage, sprinkles, not plain) if extras else None
    screen = Renderer(term, gain=1.0 / white, cols=cols, backdrop=backdrop)
    pane = CodePane(os.path.abspath(__file__))
    try:
        term.enter()
        ok, frame = video.read()
        began = start = time.perf_counter()
        index, shown, at = 0, frame, 0.0
        told, slow = start, False
        while term.alive():
            resized = term.fresh or term.size() != screen.size
            if resized:
                term.fresh = False
                high, across = stage.shape
                screen.layout(*term.size(), high, across * wide)
            due = start + index / fps
            idle = 0.0 if resized else 0.05 if extras else 0.1
            wake = min(due, time.perf_counter() + idle)
            if wake == due:
                if frame is None:
                    term.nap(due)
                    break
                shown, at = frame, index / fps
                info = [name, f"{fps:.4g} fps", clock(at) + length, count]
                info += screen.note
            if wake == due or resized:
                screen.convert(stage.cut(shown, at))
            if extras:
                extras.play(screen, wake - began, at)
            pane.paint(screen, wake - began, info)
            term.nap(wake)
            screen.draw()
            if wake < due:
                continue
            if wake - told >= 0.25 and not resized:
                told, count = wake, f"{screen.redrawn:4d} cells redrawn"
            index += 1
            now = time.perf_counter()
            late = int((now - start) * fps) - index
            if now - start - (index - 1) / fps > 1.0:
                start, late = now - (index - 1) / fps, 0
            elif late > 0 and slow:
                start, late = start + late / fps, 0
            while late > 0 and video.grab():
                index, late = index + 1, late - 1
            now = time.perf_counter()
            ok, following = video.read()
            slow = (time.perf_counter() - now) * fps > 0.5
            if not ok and loop:
                if not video.rewind():
                    break
                ok, following = video.read()
                start, index = start + index / fps, 0
            new = ok and following is not frame
            frame = following if ok else None
            if new and stage.fit(frame):
                term.fresh = True
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
    parser.add_argument("--plain", action="store_true",
                        help="no bursts, petals, hearts, butterflies or sheen: only "
                             "the bouquet and the sprinkles")
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
        args.video.encode()
    except UnicodeEncodeError:
        parser.error("the file name is not valid UTF-8: rename the file or link to it")
    if not (sys.stdout and sys.stdout.isatty()):
        parser.error("this is a full-screen terminal app, but stdout is not a terminal")
    try:
        play(args.video, loop=not args.once, cols=args.cols, backdrop=args.bg,
             crop=not args.no_crop, vase=vase, flowers=args.flowers,
             sprinkles=not args.no_sprinkles, plain=args.plain)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
