# flowerascii

A bouquet that blooms in ASCII. An empty vase, white sprinkles dripping down on it,
and seven flowers that grow out of it one after the other, each in its own color and
size, while the whole bouquet turns. Each flower starts as a bud at the mouth of the
vase and climbs on a stem that gets longer while it opens. Every character is picked
from a video frame by `ascii_player.py`; beside the picture a fake editor pane scrolls
through that file.

## In the browser

`public/` is a static page: a plain **Start** button, then two playlist cards. **For
Michelle** opens the show, with its song playing over it; **Cars** is coming soon and
does nothing yet. The show is a recording of the terminal player, so the page does no
video work of its own. After the last flower has opened, the bouquet keeps turning.

The song is "I Wanted to Leave" by SYML. Its audio file is not in this repository:
the page plays `public/for-michelle.mp3` (or `for-michelle.m4a`) when such a file is
there, and runs silent when it is not.

There are two recordings, and the page takes the one that shows bigger characters in
its window: `bloom-wide.bin` with the editor pane beside the picture, for a window
that is wider than it is high, and `bloom-tall.bin` with the pane below it, for a
phone held upright. It changes over when the window changes shape.

```
cd public && python3 -m http.server
```

Then open http://localhost:8000.

Vercel serves `public/` as it is (see `vercel.json`); nothing is built there.

## In the terminal

```
uv run ascii_player.py demo_bloom.mp4
```

`q` or Ctrl+C quits. The picture is 110 x 55 characters, and the editor pane is a
smaller window beside it, up to 64 x 38, so the show wants a wide terminal: 162
columns or more, and 55 rows. In a smaller one the picture shrinks, and the pane's
status bar says so where it has room; where the pane beside it would cost the picture
too much, as in a narrow, tall window, the pane goes below it.
The terminal needs 24-bit color. VS Code brightens dim text unless
`terminal.integrated.minimumContrastRatio` is 1.

Some options: `--once`, `--cols N`, `--flowers N` (1 to 7), `--no-sprinkles`,
`--no-vase`, `--vase-color RRGGBB`, `--bg`, `--no-crop`. `--help` lists them all.

Any video of one subject on a black backdrop works in place of `demo_bloom.mp4`.

How tall the bouquet grows is set by three numbers at the top of `ascii_player.py`.
`STUB` is the stem a flower starts with, as a share of the subject's height. `STEMS`
says how much of the stem stays inside the vase at the end: none at 0, and the bigger
the flower, the more of it. `CLIMB` is the share of its opening time a flower spends
climbing: fast at first, then slower. The second number of each line of `BOUQUET` is
how far that flower leans out, in degrees.

## Recording the show again

After a change to `ascii_player.py` or to the video, write the recordings again:

```
uv run build_web.py
```

It runs the same code that draws in the terminal at 20 frames per second, once on a
screen of 180 x 55 characters and once on one of 114 x 73, and writes down the cells
that change. It also writes `public/shows.json`, the list the page chooses from: each
recording's size, and its file name with a stamp of its contents, so that a browser
never plays an old copy. And it writes `public/cover.json`, the finished bouquet as
characters and colors, which the page draws on the For Michelle card.

The show ends with the finished bouquet turning once, and the page goes on with that
turn for ever, so one more record follows the last frame: the cells that take it back
to the first frame of the turn.

A recording is gzip, and the page unpacks it itself. Unpacked, all numbers
little-endian:

| Bytes | What |
| --- | --- |
| `"FLW2"` | marks the format |
| uint32 `n`, then `n` bytes | JSON: `cols`, `rows`, `fps`, `frames`, `loop` (the turn's first frame), `glyphs` (the characters), `papers` (the background colors) |

Then one record for every frame, and one more for the way back into the turn:

| Bytes | What |
| --- | --- |
| uint16 `k` | how many cells changed |
| `k` steps | which cells: each is so many cells after the one before (the first: after cell -1), as one byte, or as 255 and then a uint16 |
| `k` x uint8 | their characters, as indexes into `glyphs` |
| `k` x uint16 | their ink, 4 bits each of red, green and blue: `0x0RGB` |
| `k` x uint8 | their backgrounds, as indexes into `papers` |
