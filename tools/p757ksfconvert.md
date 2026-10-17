# P757 — KSF demos the converter refused (2026-10-17)

ftesurf-7c's targeted demo runs (05:2x-07:05Z, the live pinned ksfgrab ->
ksfconvert) linked 138 KSF demos and the converter refused 17. Lex asked for
"all Momentum and KSF demos compatible", so all 17 were fetched again from
`https://ksf.surf/api/replays/<file>?game=66t`, one at a time, 5 s apart, the
importer's User-Agent, no retries: 17 of 17 answered. Each official time is the
KSF board row that advertises that file, at the precision KSF's JSON gave it
(from 7c, matched by file name).

## Two shapes

**Recording starts inside the start zone (10 of 17, "course has no initial
start-zone entry").** Every one holds exactly two bookmarks: the start-zone exit
at frame 334 (a fixed 5 s lead-in) and the finish entry. The start entry happened
before the recording. Exit to finish against the official time: 0.00 to 0.13 tick
on all 10 (surf_kvas, facility, sanctuary b3, assail x2, bugs x2, goliath,
medley_fix, fiellu_ksf; fiellu is v3).

**Official time more than one tick from the bookmark interval (7 of 17).** Off by,
in ticks: fornax b4 +1.005, monolith main SW -1.017, FW +1.021, highlands b4 +1.040,
goliath b4 -2.034, monolith main BW -3.991 (57,053 frames), HSW +24.151 (24,692
frames, 23 of which repeat the frame before while the body moves). The three bonus
runs repeat or skip no frame. KSF's time is its timer's, not the frame count.
Against: the 12 P702 sample clips 0.01-0.87 tick, the 10 above 0.00-0.13.

## Change (tools/ksfconvert.py)

- `interval(..., lead_ok)`: no entry before the one exit is accepted when the
  caller has an official time (`convert` passes `seconds is not None`), which then
  binds the interval. Without a time it is refused as before; two exits still are.
- The time must be within 2.5 ticks or 0.2 % of the run, whichever is more (was one
  tick). A wrong course or run is seconds off, not ticks.

## Verified

- `tools/test_ksfconvert.py`: 11 tests pass; the converter before this patch fails
  6 of the new checks (lead-in with and without time, both tolerance edges, short
  and 4,000-frame runs).
- All 17 refused files convert with their exact official times.
- The 12 P702 sample clips convert to byte-identical .rec files.
- End to end: the refused surf_monolith main FW demo, converted and replayed on the
  deployed csprogs (41d2e086) with `replayhud_ksf.cfg`: splits for stages 1-9 at
  ticks 346, 781, 1410, 1864, 2466, 2948, 3590, 4144, 4915 from this map's zones,
  each exactly one tick before KSF's own stage-entry bookmark; 34 inferred boards,
  37 leaves, ground 405 of 405, the trainer with contact.

## Not live until the cutover

`tools/ksfconvert.py` is one of the eight files the sealed schema20 generation
(36697da) pins, so the crawler keeps refusing these until the next guarded
cutover, as P747. KSF stage demos: none was offered among the 17 and the converter
still refuses a stage course; no sample to design from (BACKLOG).
