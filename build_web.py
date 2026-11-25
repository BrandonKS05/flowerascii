#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = ["numpy", "opencv-python-headless"]
# ///
import argparse
import gzip
import hashlib
import json
import os
import struct

import cv2
import numpy as np

import ascii_player as player

HERE = os.path.dirname(os.path.abspath(__file__))
SHOWS = (("bloom-wide.bin", 161, 62), ("bloom-tall.bin", 92, 80))


class Page:
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
    video = player.Reel(path)
    frame, film = video.first, video.film
    if frame is None:
        raise SystemExit(f"build_web: could not read any video frames from {path!r}")
    rate = film.get(cv2.CAP_PROP_FPS)
    rate = rate if 0.0 < rate <= 240.0 else 30.0
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
    extras = player.Flourish(stage) if stage.blooms else None
    screen.layout(cols, rows, *stage.shape)
    yield round(player.ENCORE * fps) if stage.blooms and player.TURN else 0
    ok, frame = video.read()
    index = 0
    while ok:
        at = index / fps
        screen.convert(stage.cut(frame, at))
        if extras:
            extras.play(screen, at, at)
        info = [name, f"{fps:.4g} fps", player.clock(at) + length, count]
        info += screen.note
        pane.paint(screen, at, info)
        screen.draw()
        if index % max(round(fps / 4), 1) == 0:
            count = f"{screen.redrawn:4d} cells redrawn"
        ink = np.where(screen.glyph == player.SPACE, 0, screen.ink)
        bare = screen.shown, np.where(screen.shown == player.SPACE, 0, screen.colors)
        yield screen.glyph.copy(), ink, screen.paper.copy(), bare
        ok, following = video.read()
        if ok and following is not frame and stage.fit(following):
            screen.layout(cols, rows, *stage.shape)
        frame, index = following, index + 1


def pack(path, cols, rows, fps):
    if not 1 <= cols * rows <= 65535:
        raise SystemExit("build_web: the screen must have 1 to 65535 cells")
    show = record(path, cols, rows, fps)
    turn = next(show)
    glyphs, papers, frames, changed = [ord(" ")], [0], [], 0

    def index(values, known):
        known.extend(set(values.tolist()) - set(known))
        return np.array([known.index(value) for value in values.tolist()], np.uint8)

    def change(was, now):
        where = np.flatnonzero((now[0] != was[0]) | (now[1] != was[1])
                               | (now[2] != was[2]))
        glyph, ink, paper = (grid.ravel()[where] for grid in now)
        steps = bytearray()
        for step in np.diff(where, prepend=-1).tolist():
            steps += bytes([step]) if step < 255 else b"\xff" + struct.pack("<H", step)
        return (struct.pack("<H", where.size) + bytes(steps)
                + index(glyph, glyphs).tobytes() + ink.astype("<u2").tobytes()
                + index(paper, papers).tobytes())

    def coarse(ink):
        r, g, b = (((ink >> shift & 255) * 15 + 127) // 255 for shift in (16, 8, 0))
        return r << 8 | g << 4 | b

    states = [(np.full((rows, cols), player.SPACE, np.uint32),
               np.zeros((rows, cols), np.uint32),
               np.zeros((rows, cols), np.uint32))]
    bare = np.full((0, 0), player.SPACE, np.uint32), np.zeros((0, 0), np.uint32)
    for *now, bare in show:
        now = now[0], coarse(now[1]), now[2]
        frames.append(change(states[-1], now))
        changed += struct.unpack_from("<H", frames[-1])[0]
        states = states[-turn:] + [now]
    loop = max(len(frames) - turn, 0)
    back = change(states[-1], states[-turn] if 0 < turn < len(states) else states[-1])
    if len(glyphs) > 256 or len(papers) > 256:
        raise SystemExit("build_web: more than 256 different characters or backgrounds")
    head = json.dumps({"cols": cols, "rows": rows, "fps": fps,
                       "frames": len(frames), "loop": loop,
                       "glyphs": "".join(map(chr, glyphs)), "papers": papers}).encode()
    count = len(frames)
    frames.append(back)
    data = b"FLW2" + struct.pack("<I", len(head)) + head + b"".join(frames)
    packed = gzip.compress(data, 9, mtime=0)
    told = (f"{count} frames at {fps:.4g} fps ({count / fps:.1f} s, the last "
            f"{(count - loop) / fps:.1f} s go round for ever) on {cols}x{rows} cells, "
            f"{changed / max(count, 1):.0f} cells changed per frame, "
            f"{len(data) / 1e6:.2f} MB -> {len(packed) / 1e3:.0f} kB gzip")
    glyph, ink = bare[0], coarse(bare[1])
    lit = np.argwhere(glyph != player.SPACE)
    if lit.size:
        (top, left), (bottom, right) = lit.min(axis=0), lit.max(axis=0) + 1
        glyph, ink = glyph[top:bottom, left:right], ink[top:bottom, left:right]
    still = {"cols": glyph.shape[1], "rows": glyph.shape[0],
             "text": "".join(map(chr, glyph.ravel().tolist())),
             "ink": "".join(f"{value:03x}" for value in ink.ravel().tolist())}
    return packed, told, still


def main():
    parser = argparse.ArgumentParser(description="Record ascii_player's show for the "
                                                 "web page in public/.")
    parser.add_argument("video", nargs="?", default=os.path.join(HERE, "demo_bloom.mp4"))
    parser.add_argument("--fps", type=float, default=20.0, help="frames per second")
    parser.add_argument("--out", default=os.path.join(HERE, "public"), metavar="FOLDER",
                        help="where the recordings and shows.json go")
    args = parser.parse_args()
    os.makedirs(args.out, exist_ok=True)
    listed, cover = [], None
    for name, cols, rows in SHOWS:
        packed, told, still = pack(args.video, cols, rows, args.fps)
        cover = cover or still
        with open(os.path.join(args.out, name), "wb") as out:
            out.write(packed)
        stamp = hashlib.sha256(packed).hexdigest()[:10]
        listed.append({"file": f"{name}?v={stamp}", "cols": cols, "rows": rows})
        print(f"{os.path.join(args.out, name)}: {told}")
    with open(os.path.join(args.out, "shows.json"), "w", encoding="utf-8") as out:
        json.dump(listed, out, indent=2)
        out.write("\n")
    with open(os.path.join(args.out, "cover.json"), "w", encoding="utf-8") as out:
        json.dump(cover, out)
        out.write("\n")


if __name__ == "__main__":
    main()
