# flowerascii

A bouquet that blooms in ASCII. An empty vase, white sprinkles dripping down on it,
and seven flowers that grow out of it one after the other, each in its own color and
size, while the whole bouquet turns. Every character is picked from a video frame by
`ascii_player.py`; below the picture a fake editor pane scrolls through that file.

## In the browser

`public/` is a static page: a big **Start** button, then the show. It plays a
recording of the terminal player (`public/bloom.bin`, 1.3 MB), so the page does no
video work of its own. After the last flower has opened, the bouquet keeps turning.

```
cd public && python3 -m http.server
```

Then open http://localhost:8000.

Vercel serves `public/` as it is (see `vercel.json`); nothing is built there.

## In the terminal

```
uv run ascii_player.py demo_bloom.mp4
```

`q` or Ctrl+C quits. The picture wants a big window, about 110 x 49 characters plus a
few rows for the editor pane; in a smaller one it shrinks, and the status bar says so.
The terminal needs 24-bit color. VS Code brightens dim text unless
`terminal.integrated.minimumContrastRatio` is 1.

Some options: `--once`, `--cols N`, `--flowers N` (1 to 7), `--no-sprinkles`,
`--no-vase`, `--vase-color RRGGBB`, `--bg`, `--no-crop`. `--help` lists them all.

Any video of one subject on a black backdrop works in place of `demo_bloom.mp4`.

## Recording the show again

After a change to `ascii_player.py` or to the video, write `public/bloom.bin` again:

```
uv run build_web.py
```

It runs the same code that draws in the terminal on a screen of 114 x 59 characters at
20 frames per second, and writes down the cells that change. The show ends with the
finished bouquet turning once, and the page goes on with that turn for ever, so one
more record follows the last frame: the cells that take it back to the first frame of
the turn.

The file is gzip, and the page unpacks it itself. Unpacked, all numbers little-endian:

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
