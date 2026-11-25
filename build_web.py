#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = ["numpy", "opencv-python-headless"]
# ///
"""build_web.py - record one pass of ascii_player's show for the web page.

    uv run build_web.py                      (demo_bloom.mp4 -> public/bloom.bin)
    uv run build_web.py bloom.mp4 --cols 114 --rows 59 --fps 20 -o public/bloom.bin

The page in public/ does no conversion of its own.  This script runs the very code
that draws in the terminal (Stage, Renderer, Sprinkles and CodePane of
ascii_player.py) on a screen of a fixed size, and writes down, for every frame, the
cells that changed: which character, in which color, on which background.
public/index.html plays that back on a canvas.  The show ends with the finished
bouquet turning once; the page goes on with that turn for ever, so one more record
follows the last frame: the cells that take the last frame back to the first of the
turn.

The file is gzip (the page unpacks it itself).  Unpacked, all numbers little-endian:

    "FLW2"  uint32 n  n bytes of JSON  {"cols", "rows", "fps", "frames", "loop",
                                        "glyphs", "papers"}
            ("loop": the turn's first frame; "papers": the background colors)
    then for every frame, and once more for the way back into the turn:
        uint16 k                 how many cells changed
        k steps                  which: each is this many cells after the one before
                                 (the first: after cell -1), as one byte, or as 255
                                 and then a uint16
        k x uint8                their characters, as indexes into "glyphs"
        k x uint16               their ink, 4 bits each of r g b: 0x0RGB
        k x uint8                their backgrounds, as indexes into "papers"

Ink in 16 levels per channel is all a glyph needs, and it keeps the file small: a cell
whose color moved by less is not a change.
"""
import argparse
import gzip
import json
import os
import struct

import cv2
import numpy as np

import ascii_player as player

HERE = os.path.dirname(os.path.abspath(__file__))


class Page:
    """Stands in for the terminal: it has a size, and nothing is written to it."""

    stop = fresh = False

    def __init__(self, cols, rows):
        self.cols, self.rows = cols, rows

    def size(self):
        return self.cols, self.rows

    def cell_aspect(self):
        return player.CELL_ASPECT

    def write(self, text):
        pass


def record(path, cols, rows, fps):
    """Play the show once, as play() does, but at `fps` frames per second and frame by
    frame.  Yields how many frames the last turn has, then for every frame the
    screen's three grids: characters, their ink, their backgrounds."""
    video = player.Reel(path)
    frame, film = video.first, video.film
    if frame is None:
        raise SystemExit(f"build_web: could not read any video frames from {path!r}")
    rate = film.get(cv2.CAP_PROP_FPS)
    rate = rate if 0.0 < rate <= 240.0 else 30.0        # the film's own frame rate
    total = max(int(film.get(cv2.CAP_PROP_FRAME_COUNT)), 0)
    white, lit, stem = player.survey(path)
    stage = player.Stage(frame.shape, white, lit, stem, length=total / rate)
    stage.fit(frame)
    video.lead, video.tail = round(stage.lead * fps), round(stage.tail * fps)
    video.step = stage.pace * rate / fps
    length = stage.lead + total / rate / stage.pace + stage.tail
    length = f" / {player.clock(length)}"
    name, count = player.cells(os.path.basename(path)), "   0 cells redrawn"
    screen = player.Renderer(Page(cols, rows), gain=1.0 / white)
    pane = player.CodePane(player.__file__)
    rain = player.Sprinkles() if stage.blooms else None
    screen.layout(cols, rows, *stage.shape)
    yield round(player.ENCORE * fps) if stage.blooms and player.TURN else 0
    ok, frame = video.read()
    index = 0
    while ok:
        at = index / fps
        screen.convert(stage.cut(frame, at))
        if rain:
            rain.fall(screen, at, stage.wet(at))
        info = [name, f"{fps:.4g} fps", player.clock(at) + length, count]
        info[3:3] = screen.note
        pane.paint(screen, at, info)
        screen.draw()
        if index % max(round(fps / 4), 1) == 0:         # the counter moves at ~4 Hz
            count = f"{screen.redrawn:4d} cells redrawn"
        ink = np.where(screen.glyph == player.SPACE, 0, screen.ink)
        yield screen.glyph.copy(), ink, screen.paper.copy()
        ok, following = video.read()
        if ok and following is not frame and stage.fit(following):
            screen.layout(cols, rows, *stage.shape)     # the subject outgrew the crop
        frame, index = following, index + 1


def main():
    parser = argparse.ArgumentParser(description="Record ascii_player's show for the "
                                                 "web page in public/.")
    parser.add_argument("video", nargs="?", default=os.path.join(HERE, "demo_bloom.mp4"))
    parser.add_argument("--cols", type=int, default=114, help="width of the screen")
    parser.add_argument("--rows", type=int, default=59, help="height of the screen")
    parser.add_argument("--fps", type=float, default=20.0, help="frames per second")
    parser.add_argument("-o", "--out", default=os.path.join(HERE, "public", "bloom.bin"))
    args = parser.parse_args()
    if not 1 <= args.cols * args.rows <= 65535:
        parser.error("the screen must have 1 to 65535 cells")
    show = record(args.video, args.cols, args.rows, args.fps)
    turn = next(show)
    glyphs, papers, frames, changed = [ord(" ")], [0], [], 0

    def index(values, known):
        """Each value's place in the list `known`, which grows by the new ones."""
        known.extend(set(values.tolist()) - set(known))
        return np.array([known.index(value) for value in values.tolist()], np.uint8)

    def change(was, now):
        """The record that takes the screen from one state to another."""
        where = np.flatnonzero((now[0] != was[0]) | (now[1] != was[1])
                               | (now[2] != was[2]))
        glyph, ink, paper = (grid.ravel()[where] for grid in now)
        steps = bytearray()
        for step in np.diff(where, prepend=-1).tolist():
            steps += bytes([step]) if step < 255 else b"\xff" + struct.pack("<H", step)
        return (struct.pack("<H", where.size) + bytes(steps)
                + index(glyph, glyphs).tobytes() + ink.astype("<u2").tobytes()
                + index(paper, papers).tobytes())

    states = [(np.full((args.rows, args.cols), player.SPACE, np.uint32),
               np.zeros((args.rows, args.cols), np.uint32),
               np.zeros((args.rows, args.cols), np.uint32))]    # a black, empty page
    for now in show:
        # ink in 16 levels per channel, 0x0RGB
        r, g, b = (((now[1] >> shift & 255) * 15 + 127) // 255 for shift in (16, 8, 0))
        now = now[0], r << 8 | g << 4 | b, now[2]
        frames.append(change(states[-1], now))
        changed += struct.unpack_from("<H", frames[-1])[0]
        states = states[-turn:] + [now]         # (the turn's first frame is kept)
    loop = max(len(frames) - turn, 0)
    back = change(states[-1], states[-turn] if 0 < turn < len(states) else states[-1])
    if len(glyphs) > 256 or len(papers) > 256:
        raise SystemExit("build_web: more than 256 different characters or backgrounds")
    fps = args.fps
    head = json.dumps({"cols": args.cols, "rows": args.rows, "fps": fps,
                       "frames": len(frames), "loop": loop,
                       "glyphs": "".join(map(chr, glyphs)), "papers": papers}).encode()
    frames.append(back)
    data = b"FLW2" + struct.pack("<I", len(head)) + head + b"".join(frames)
    packed = gzip.compress(data, 9, mtime=0)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "wb") as out:
        out.write(packed)
    count = len(frames) - 1
    print(f"{args.out}: {count} frames at {fps:.4g} fps ({count / fps:.1f} s, the last "
          f"{(count - loop) / fps:.1f} s go round for ever) on {args.cols}x{args.rows} "
          f"cells, {changed / count:.0f} cells changed per frame, "
          f"{len(data) / 1e6:.2f} MB -> {len(packed) / 1e3:.0f} kB gzip")


if __name__ == "__main__":
    main()
