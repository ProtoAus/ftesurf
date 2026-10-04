# ROADMAP.md — maps, downloads, boards and Momentum demos

Lex's requests of 4 Oct 2026, read against the code as it stands (three surveys
of the menu, the line and replay code, and the KSF/Momentum/Pi data paths), with
what to build, in what order, and what needs a decision. Work happens on branch
`feat-maps-demos`; Patches 477 (rewind) and 478 (ghost) ship first.

Each item: **Today** (what the code does, with pointers), **Build**, **Unknowns**
(measure before promising), **Size**.

---

## 1. Download and connect status under the map list

**Today.**
- A download starts in `ui_dl_start` (src/menu/m_main.qc:4986) through the
  engine's `downloadmap` builtin; progress is polled every frame from
  `serverkey("dlstate")` by `Dl_Tick` (m_main.qc:5023) into the `dl_*` globals.
  The only display is a 6 px bar in the map's own row (m_main.qc:5915-5928) --
  no percent, size or time left, nothing once the row scrolls away. There is no
  cancel: the engine's `curl --cancel` prints "not implemented"
  (engine client/cl_main.c:5321). One download at a time.
- Choosing a map runs `ui_launch` -> `Lob_JoinAsk` (`/api/join`) ->
  `Lob_JoinPoll` (8 s for an answer, up to 20 s for the lobby to switch) ->
  `ui_prejoin` (download first if missing) -> `connect`; any failure falls back
  to a local `map`. All of it reports to the console only, and ESC on the map
  screen does not cancel it (`ui_join_cancel` runs only from `m_close`).

**Build.**
- A status strip under the map list (the footer between start and back), one
  line per phase, each with **Cancel**: "Downloading surf_x -- 42% · 18.3 of
  43.5 MB · 2.1 MB/s · 12 s left", "Finding a lobby…", "Switching lobby 3 to
  surf_x…", "Waiting for surf_x on lobby 3 (12 s)", "Downloading surf_x before
  joining…", "Starting a local server…", and the failures ("lobby busy --
  playing locally", "download failed"). A small toast keeps it visible on other
  screens.
- Cancelling a join: ESC/Cancel calls `ui_join_cancel` and clears the held
  join (`pj_*`). Menu QC only.
- Cancelling a download: an engine patch that aborts the disconnected HTTP
  download (the Patch 465 path, client/cl_parse.c:2013-2032 -- close the
  handle, delete the .tmp) and a way for the menu to ask for it.
- The menu's shader: drive `MM_Camera` (src/menu/m_milk.qc:790-801) from
  `dl_pct` and the join phase -- the PLAY station's world charging with
  progress (zoom, decay, hue), a flash on completion, a stall pulse on an error.
  The `M_EVENT.z` uniform slot (src/milk_sys.qc:370) is free to carry it.
- Optional: a menu loading screen (`m_drawloading`, looked up at
  client/pr_menu.c:3495 and not defined today) so the status survives the
  map load.

**Size.** Medium in QC; the engine cancel is small.

## 2. Line thickness

**Today.** One cvar, `hud_watch_path_px` (pixels, default 1), sets every line
at once (src/client/cl_lines.qc:1213 -> `ln_wpx`), and hud_edit has no row
for it (src/client/cl_hudedit.qc:620-678, "Run lines" rows 0-24).

**Build.** Three thicknesses, one per kind of line: the replay you are
watching (slot 0, `Watch_Path2D`), the leaderboard runs you tick on to show
while you play (slots 1-8, `Scores_LinesDraw` in cl_scores.qc), and your own
live run line (slots 9-10, cl_trail.qc). `Line_Draw` takes a per-slot width
instead of the single `ln_wpx`. Three hud_edit rows under Run lines -- thin /
normal / thick / heavy. Client only.

**Size.** Small.

## 3. Momentum demos: real buttons and mouse, accurate marks and labels

**Today.** Momentum's replay files (`.mtv`) are never parsed in this repo. An
outside extractor wrote positions only, and `tools/momimport.py` derives pitch
and yaw from the direction of travel, takes velocity as a central difference of
positions, and writes zeros for keys, flags and moves -- in all 16.6 million
imported samples. So:
- the mouse pad (`MPad_Frame`, cl_mouse.qc) draws the velocity turning, not
  the player's hand;
- a mid-air crouch moves the origin 8.5 u, which the central difference turns
  into a +-283 u/s vertical spike and a 5-45 degree pitch jab -- 44,593
  two-sample spikes in the corpus, 95% of them an 8-9 u step;
- touching a ramp bends the velocity within a tick, so yaw and pitch jump there;
- the key display stays dark, there are no touchdown/take-off/jump marks,
  "colour by contact" is all grey, and the labels read the spiky velocity;
- stage imports read one stage late: momimport writes `startseg = leg`
  (momimport.py:297) where FTESurf writes `leg - 1`.

**Build.**
1. `tools/momreplay.py`: a parser for Momentum's replay format written from
   Momentum's open game source (header, then per tick: eye angles, position,
   view offset, buttons), checked against real files (the header's hash is
   the map build).
2. momimport writes the real columns: view angles; the key mask from Source's
   button bits (forward, back, strafes, jump, duck, turn -- the bit layout
   differs from FTESurf's); ducked from the duck button and view offset; the
   jump flag; velocity from position deltas with the duck offset taken out;
   ground and ramp contact inferred (vertical speed and jump presses, or a
   trace when the map is loaded).
3. Re-import the corpus from the `.mtv` files and re-index it on the Pi.
4. Fix the stage off-by-one.
5. The viewer then lights the keys, draws the real mouse, and places marks and
   labels as it does for our own runs.

**Unknowns.** Which `.mtv` versions the corpus holds, and whether every file
carries view offsets and buttons.

**Size.** Large but mechanical once the format is pinned.

## 4. Fetch a Momentum demo we do not have, through the Pi

**Today.** Every cached Momentum board row already carries its replay's
address (`https://cdn.momentum-mod.org/runs/<replayHash>`, momfetch.py:268);
nothing downloads it. The Pi serves replays as `/api/replay/<id>`
(surfd.py:3527) and the client fetches and caches them (cl_online.qc:969).

**Build.** A "Get demo" button on a Momentum board row that has none: the Pi
fetches the `.mtv` (one at a time, rate-limited, size-capped, kept for good,
its map-build hash checked), converts it with (3), indexes it, and answers with
a replay id; the client takes it from there as it does today.

**Unknowns.** Whether that CDN path needs a login (maps and images on the same
CDN do not). One request settles it.

**Size.** Medium, after (3).

## 5. KSF past 25 places

**Today.** Nothing in our boards stops at 25: the in-game board pages to
1,000 rows (cl_online.qc `OB_PAGE`/`OB_MAXROW`), the website pages 50 at a
time, and surfd's `/api/board` takes an offset. KSF's own pages are 20 rows;
the import reached ~40 ranks on most maps (the map path defaults to 100 rows a
board, the player-seeded path takes 25 per player). On the Momentum side
`momfetch.py --take` still defaults to 25 (the Pi's momwatch asks for 100).

**Build.** (a) A deeper import -- `ksfimport.py --from-maps --depth 500`, run
by hand as always. (b) Optionally, when a player scrolls past the KSF rows we
hold, the Pi fetches the next 20-row KSF page for that board on demand
(rate-limited, cached).

**Unknowns.** Which screen showed 25.

**Size.** (a) a command; (b) small-medium.

## 6. Which games a map needs, and which you have

**Today.** `data/mapdeps.txt` (545 `dep <map> steam:<game>` lines, from
`tools/mapdeps.py`, last built 12 Sep) is read only by the engine when a map
loads (`FS_AutoMountForMap`, common/fs.c). The menu knows only which install a
map came from (the MOM/CSS label), and no builtin says which Steam games are
installed or mounted.

**Build.** Rebuild mapdeps.txt over every map (the Pi-only ones too) and ship
it; the menu reads it; a small engine builtin answers per game -- not
installed, installed, mounted (from `FS_Addon_ResolveEx` /
`FS_Addon_IsMounted`). Each row shows the games it needs as badges, lit if you
have them; the detail line names them; a filter chip shows only maps you can
draw fully, or only the ones missing something.

**Size.** Medium, one small engine patch.

## 7. Every KSF and Momentum map, both tiers, every thumbnail

**Today.** Momentum maps, tiers and thumbnails come from the local Momentum
install's cache -- `approved_*.dat` and `submission_*.dat`, so beta and
unlisted submissions are already in (tools/mapmeta.py, tools/msml.py) -- with
images from `cdn.momentum-mod.org/img/<uuid>`. KSF maps come from the KSF
sheet (`data/ksf_roster.csv`) with their tier, but `maproster.txt` keeps one
tier (Momentum's, else KSF's), so the KSF tier is lost downstream: surf_whiteout
is Momentum 2 / KSF 1 and shows 2. Beta maps show unrated on the website.

**Build.**
- Keep `mtier` and `ktier` apart end to end (maproster, mapdl.txt, mapmeta,
  the website) and show both: "T3 · KSF T2".
- A completeness audit: the KSF sheet and Momentum's lists against what we
  list; fetch every missing thumbnail (Momentum's CDN; for KSF-only maps,
  ksf.surf's images if it has them); rebuild the atlases (`tools/mapthumbs.py`)
  and the website's shots.

**Unknowns.** Whether Momentum's public API lists maps the local cache does
not; whether ksf.surf exposes map screenshots.

**Size.** Medium-large, mostly data.

## 8. One row per map, with a Momentum / CS:S toggle

**Today.** Duplicates already merge into one "MOM CSS" row
(m_main.qc:2184-2250), but which BSP loads is decided by the mount order
(`ftesurf/maps` > Momentum > cstrike); the Pi serves one build per name; zones,
boards and the `mapbuild` hash key on the name.

**Build.** Per map, a list of builds with their hashes; a toggle on the row --
"Play: Momentum | CS:S", remembered per map; loading a chosen build needs a
variant path the engine loads under the map's own name (for example
`maps/variants/<name>@css.bsp`), zones per build (KSF's for the CS:S build,
Momentum's for theirs), boards keyed by build (the existing mapbuild hash), and
surfd's `/api/join` and the Pi's map store carrying the build.

**Size.** Large: engine, server, surfd and data.

## 9. Leaderboards on the map screen

**Today.** None in the menu; the in-game board needs a loaded map
(`serverkey("map")`). surfd's `/api/board?map=&tier=ksf|momentum|ranked|imported`
already serves paged rows.

**Build.** A "Leaderboard" button on the selected map opens a panel with KSF /
Momentum / FTESurf tabs -- rank, name, time, date -- loading more as you scroll.
The menu's web replies share one callback (src/menu/m_lobby.qc:885), so they are
told apart by request id.

**Size.** Medium, menu QC only.

## 10. Maps with full data first

**Today.** Sorted by tier only, untiered last, installed before downloadable
(`ui_refilter`, m_main.qc:2446).

**Build.** Rank by completeness first -- thumbnail, tier, zones, records --
then by tier; maps without a thumbnail sink to the bottom and show in full only
while searching or with a "show all" chip.

**Size.** Small.

## 11. Scanning Momentum demos

Once (3) gives real per-tick angles and buttons, Momentum demos can go through
the same input analysis our own runs get, as far as their data allows, and
flag records to look at. How it detects lives in the private anti-cheat plan,
not in this public file.

---

## Order

- **A -- client, no decisions needed:** 2 (thickness), 10 (sort), 1 without
  the engine cancel (status strip, join cancel, the shader), 9 (leaderboard).
- **B -- data:** 7 (both tiers, the audit, thumbnails), 6 (mapdeps, the menu,
  the engine builtin).
- **C -- Momentum demos:** 3 (parser, re-import, the stage fix), 4 (the Pi
  fetch), 11.
- **D -- engine and server:** 1's download cancel and loading screen, 8 (builds).
- 5 waits on the answer below.

## Decisions for Lex

1. **KSF on demand:** may a player scrolling past our KSF rows make the Pi
   fetch one more 20-row page (rate-limited, cached), or do KSF imports stay
   strictly by hand?
2. **Momentum demos on demand:** fetch from Momentum's CDN when a player asks
   (one at a time, kept for good) -- yes?
3. **Builds (8):** how a second build of a map is stored and named, and
   whether the lobbies offer both.
4. **Where you saw 25 KSF places** (which screen).
