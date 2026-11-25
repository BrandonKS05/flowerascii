# flowerascii

A bouquet that blooms in ASCII. An empty vase, white sprinkles dripping down on it,
and twelve flowers that grow out of it one after the other, each in its own color and
size, while the whole bouquet turns. Each flower starts as a bud at the mouth of the
vase and climbs on a leafy stem that gets longer while it opens; the bouquet takes
half a minute to grow, until it stands three times as high as its vase. The sprinkles
never stop. They rain from the top of the picture on the vase and the flowers, and
not into the black beside the bouquet. Every character is picked from a video frame
by `ascii_player.py`; beside the picture a fake editor pane scrolls through that file.

## In the browser

`public/` is a static page: a plain **Start** button, then two playlist cards. **For
Michelle** opens the show, with its song playing over it; **Cars** is coming soon and
does nothing yet. The show is a recording of the terminal player, so the page does no
video work of its own. After the last flower has opened, the bouquet keeps turning
and the sprinkles keep falling.

The song is "I Wanted to Leave" by SYML, in `public/for-michelle.m4a`. The page plays
that file, or `public/for-michelle.mp3` in its place, and runs silent when neither is
there.

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

`q` or Ctrl+C quits. The picture is 92 x 64 characters, higher than it is wide, and
the editor pane is a smaller window beside it, up to 64 x 45, so the show wants a big
terminal: 160 columns or more, and 64 rows. In a smaller one the picture shrinks, and
the pane's status bar says so where it has room; where the pane beside it would cost
the picture too much, as in a narrow, tall window, the pane goes below it.

The pane shows `Renderer.convert()` and `draw()` without the indentation the two
share, and those two are written so that no line is longer than a pane of 64 columns
can hold. A narrower pane indents no row by more than half its width, and it moves a
word that does not fit behind its indentation to the left. It folds the lines that
still do not fit and indents the rest of each where there is room. It folds at a
space, and inside a word only when the word alone is too long for the pane. From 8
columns up it never cuts a line off.
The terminal needs 24-bit color. VS Code brightens dim text unless
`terminal.integrated.minimumContrastRatio` is 1.

Some options: `--once`, `--cols N`, `--flowers N` (1 to 12), `--no-sprinkles`,
`--no-vase`, `--vase-color RRGGBB`, `--bg`, `--no-crop`. `--help` lists them all.

Any video of one subject on a black backdrop works in place of `demo_bloom.mp4`.

How tall the bouquet grows is set by a few numbers at the top of `ascii_player.py`.
`LONG` is how long a stem gets, in stems of the video's own flower: at 2.4 it is more
than the video shows, so the picture goes on below the end of the video's stem with
the lowest part of that stem, the share `STALK` of the subject's height, repeated:
once upside down, once upright, and so on. `STUB` is the stem a flower starts with,
as a share of the subject's height. `STEMS` says how much of the stem stays inside
the vase at the end: none at 0, and the bigger the flower, the more of it. `PACE` is
how fast the video plays for each flower, and `CLIMB` is the share of its opening
time a flower spends climbing: fast at first, then slower. In each line of `BOUQUET`
the second number is how far that flower leans out, in degrees, and the third is its
size.

`SPRINKLES` is how many specks are due each second on a picture 70 characters wide; a
wider picture gets more in proportion. A speck starts in the top row of the picture
and falls straight down. One whose column has no drawn character in it is left out,
so it rains on the bouquet and not beside it. On the bouquet a speck runs down over
drawn characters, at most the share `SOAK` of the picture's height of them, and soaks
into the next with a glint; where nothing drawn is left below it, it goes out. The
specks come by a list that is as long as one turn of the bouquet and starts again with
every turn, so the turn that the page repeats for ever shows no jump.

## Recording the show again

After a change to `ascii_player.py` or to the video, write the recordings again:

```
uv run build_web.py
```

It runs the same code that draws in the terminal at 20 frames per second, once on a
screen of 161 x 64 characters and once on one of 92 x 84, and writes down the cells
that change. It also writes `public/shows.json`, the list the page chooses from: each
recording's size, and its file name with a stamp of its contents, so that a browser
never plays an old copy. And it writes `public/cover.json`, the finished bouquet
without the sprinkles, as characters and colors, which the page draws on the For
Michelle card.

The show ends with the finished bouquet turning once in the sprinkles, and the page
goes on with that turn for ever, so one more record follows the last frame: the cells
that take it back to the first frame of the turn.

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
