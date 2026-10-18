# World of Surf

A competitive **surf and bhop** game built on [FTEQW](https://www.fteqw.org/),
reproducing Counter-Strike: Source / [Momentum Mod](https://momentum-mod.org/)
movement — and playing the existing surf map library directly out of your own
Steam installs, rather than shipping any of it.

Roughly 48,000 lines of QuakeC: a per-map timing system with zones, stages and
bonuses; savelocs; ghosts and full run replays; a strafe-quality HUD you can lay
out yourself; and a browser over 1,300+ maps with tiers, thumbnails and
per-map asset resolution.

Movement is **engine-side**, not QC-side — see `pm_source.c` in the engine fork
below. The constants in `src/shared/sh_defs.qc` mirror it so the HUD can label
things correctly; they are documentation, not the implementation.

---

## Player profiles and leaderboards

Click a time's row in a player profile to open its map/track/leg, tier and style
leaderboard around that time. The selected player's exact time is highlighted
among its neighbors, including positions beyond the first thousand. **Earlier**
loads preceding ranks; **top** returns to the beginning. Normal paging continues
from that position. If the cached time has changed or disappeared, the board
says so rather than highlighting a same-name player.

## Friends, players and overhead labels

On an account-enabled lobby, link Steam and open your profile's **Friends** tab
(or run `hud_player friends`). Add someone from their in-game profile or the
scoreboard's **Players** tab. They can Accept or Decline; accepted friends show
whether they are online, their lobby/map, and **Join** / **Message** buttons.
Friendships belong to the Steam account and appear on every installation linked
to it, including separate keys. Pending requests can be cancelled and friends
removed. Presence covers the account-enabled lobby fleet, not unrelated Steam
games or third-party servers. It refreshes approximately every five seconds.

Message opens a **private chat draft** addressed to that friend. Enter sends it;
ESC cancels. Only that account's recipient connections see it, including friends
on another fleet lobby. Messages require an accepted friendship and live
presence; there is no offline mail/history service. Private means hidden from
other players, **not end-to-end encryption from server operators**.

The full-width **Players** scoreboard tab replaces the old sidebar. Names open
profiles; Spectate, Add friend, Mute chat and Mute voice are separate actions.
It scrolls through the server's slots and works without map zones. ESC on
another player's profile closes the entire window in one press, even when its
search field has focus.

Overhead labels use the existing display-picture cache and body poses. Nearby
players have a picture and name; the name fades between 256 and 1024 units,
leaving the picture centered. Range/view checks run locally; PVS plus a solid
line-of-sight check rescan at most every 0.5 seconds per admitted body. Wall
occlusion can therefore take up to half a second. No extra pose traffic is sent.
Use `hud_playerlabels 0` to disable, or `hud_playerlabels_far <units>` to adjust
the default 3000-unit limit (maximum 6000).

## Zone editor

On a locally hosted map, run `zone_edit` to open the editor.

- **Mouse2** switches between looking/flying and the window's mouse cursor.
  While placing a zone in look mode it still undoes a corner/step. Jump-bound
  keys (including the wheel) no longer switch the mouse; the wheel scrolls the
  zone list. Drag the title to move the window. V is the existing noclip toggle.
- Select **box** or **polygon**, then `+ start`, `+ stage`, `+ check` or `+ end`.
  For a polygon, aim at the floor and click its corners. Enter (or clicking the
  first corner again) closes the outline; look up to pull the height and click
  to finish. MOUSE2 undoes a corner/step. Simple concave outlines work; crossed
  outlines and holes do not. Up to 64 corners.
- Grid snaps X, Y and Z. **Snap XYZ** snaps an existing selected ring and both
  its floor and top; it refuses a grid that would collapse/cross the outline.
  **Edge snap** targets nearby existing zone corners/edges, not BSP mesh edges.
- Single-click a list row to select it; double-click to teleport to its server
  zone. A changed draft must be saved and the hosted map reloaded first.
- **Set spawn** uses your position; **Reset spawn** restores the zone-derived
  default, kept inside concave rings. Selection/spawn, construction/snap and
  file actions are grouped; the placement hint uses shared rounded UI styling.
- **Surface** means snap to the aimed surface instead of the grid; it does
  not select Surf movement.
- **Map properties** has **Surf/Bhop** presets, speed cap, gravity and optional
  air acceleration. Surf uses 66.67 Hz / AA150; Bhop uses 100 Hz / AA1000.
  A preset keeps your speed cap and gravity. Save then **reload the map**.
  This needs the Patch 673+ native engine; older binaries do not apply the new
  mode file. Previous settings stay in `.prev`. Ground rules remain map-authored,
  not editor fields. Dedicated/public lobbies ignore local properties.

Zones save under `ftesurf/data/maps/zones/local/`; settings under
`ftesurf/data/maps/settings/local/`. They stay on this machine. Steam-based
admin permissions and reviewed NanoPi uploads are **not enabled yet**; see
[ROADMAP.md](ROADMAP.md). No upload or admin access is granted by display name.

## Entity and clip-brush viewer

`ent_view` shows map entities without taking the mouse. With the Patch 693+
native client, teleport triggers have **red ordered-dither flat faces** at the
map entity's actual position/rotation, not just a wire box. The hovered brush
gets a denser fill. `ent_panel` opens the click-to-copy inspector.

While `ent_view` is on, **mouse1** pins the entity under the crosshair and
expands its card: every key, and the server's own answer (spawn function,
solidity, outputs). The card stays when you look away; mouse1 on it again, or on
nothing, closes it. **mouse2** copies the pinned (or hovered) entity to the
clipboard as entity-lump text, with the server's answer as `//` comments. Both
buttons stop ducking and jumping until `ent_view` is off (Patch 776).

Nearby world **player-clip and monster-clip brushes** also show dithered collision
faces. `ent_view_clips 0` hides that extra overlay; `ent_view_clips 1` restores it.
`ent_view_dist` controls its range. Turning off `ent_view` removes the overlay.
This needs retained brush collision data (including Source/VBSP); it does not
turn every nodraw surface or static-prop collision mesh into a clip brush.
Existing explicit `r_showbrushes` debug settings take precedence and are left
unchanged. Drawing never changes collision or movement.

## Surf view

`surf_view` toggles a visuals-only overlay (Patch 776, native client):
**dithered red** on every face you can surf (steeper than you can stand on, not
a wall: normal z from 0.1 to 0.7) and on every `trigger_*teleport*`, and
**dithered yellow** on faces that stop the player but are not drawn (player
clip, nodraw). It reads the map's collision, so an invisible ramp shows and a
non-solid decoration does not: world brushes, displacements, static props with
hull pieces, and solid brush entities. `surf_view_dist` (8192) sets its range
and `surf_view_fill` (0.25) its density. It is depth-tested, so it marks only
what you can see.

## Frame budget

`r_budget` shows where each frame's time goes (Patch 782, native client), at the
top left. **1** is compact: the frame time, how long the CPU and the GPU were busy
and how long the frame waited, two bars on one scale (the CPU's work by group, then
idle; the GPU's passes), and the three biggest items under each. **2** lists every
group with its milliseconds, its share of the frame and a bar; **3** adds every
timer inside each group. `r_budget_dump` prints the table as text and copies it to
the clipboard. `r_budget_window` (0.5 s) is the averaging window.

- **CPU groups:** server; game client code (CSQC); world; map vis and static props
  (the HL2 plugin on a Source map); draw calls; shadows; particles; post-processing;
  HUD and 2D (this panel included); display (swap, vsync, pacing); input, network
  and audio; loading; other. Each timer counts once, without the timers nested in it.
- **GPU passes** (GL timer queries, OpenGL 3.3 or later): world; models and props;
  sky; 3D sky; portals and reflections; shadows; RT lights; transparent and
  effects; post-processing; HUD and 2D; and "Waiting on the CPU", the stretches the
  GPU spends waiting for the CPU, which do not count as GPU busy.
- **CSQC by QC file** (`r_budget_csqc 1`, Patch 800): the game code's time by source
  file (cl_hud, cl_zones, ...), busiest first, on the QC total's scale; at 3 the
  busiest functions under the top four. It runs the QC profiler while shown, which
  slows QC (on the PC 0.57 to 0.67 ms); `r_budget_dump` lists sixteen files.
- `panel` in the header is its own cost: on the PC about 0.08 ms at 1, 0.17 at 2 and
  0.27 at 3 (0.4 with the CSQC breakdown at 3). Off (`r_budget 0`), each timer is one
  check of a flag and nothing is drawn or queried.

## Frame times and stutters

`r_frametime 1` (Patch 801) draws a frame-time graph at the top right: the last 10 seconds
(`r_frametime_seconds`), each column the slowest frame of its slice, so one spike is never
averaged away. Green is normal, yellow over 1.5x the median frame, red over 2.5x (a stutter).
Above it: average fps, the 1% and 0.1% lows (the average fps of the slowest 1% and 0.1% of
frames), the median and worst frame, and the stutter count, over the last 30 seconds
(`r_frametime_window`). `r_frametime_dump` prints the lows, the 50/90/99/99.9th percentile
frames and the eight slowest frames, each with a `setpos` (where you stood and looked) to paste
and go to the spot, and copies it all to the clipboard. `r_frametime_reset` starts the window
again, for example at a run's start. It costs about 0.03 ms a frame on, nothing off.

## What you need

**Windows x64, and Linux x86_64 as a beta** (`ftesurf.sh`). The build script is
Windows-only; nothing in the QC is.

**The engine.** [github.com/ProtoAus/ftequakers](https://github.com/ProtoAus/ftequakers),
branch `engine-patches`. See [ENGINE.txt](ENGINE.txt) for the exact commit this
QC build wants.

> **Stock FTEQW will not work.** The Source movement module
> (`engine/common/pm_source.c`) and the hl2 plugin's `.phy` collision, VTF/VMT
> material and static-prop lighting work only exist in that fork.

**Steam games, mounted — never redistributed.** World of Surf reads content out of
installs you already own, at runtime, via the engine's addon system. See
[`ftesurf/fs_addons.default.txt`](ftesurf/fs_addons.default.txt), which explains
the priority ordering and why it is what it is.

| Game | Why |
|---|---|
| Momentum Mod Playtest | The map library, plus its bundled HL2 base content, found automatically |
| Counter-Strike: Source | The materials and models most surf maps reference |
| Half-Life 2 | Optional when Momentum is installed: its bundled HL2 pack already supplies shared Source content |
| CS:GO *(CS2's `csgo_legacy` beta or standalone CS:GO Legacy)* and TF2 | Optional, mounted **per map** by `fs_automount`. Both CS:GO Source 1 install layouts are discovered automatically; modern CS2's Source 2 assets are not a replacement |

---

## Build

### 1. Engine, plugins and the QC compiler

From the `ftequakers` tree:

```sh
make -C engine  m-rel       FTE_TARGET=win64          # client
make -C engine  sv-rel      FTE_TARGET=win64          # dedicated server
make -C plugins/hl2                                   # regenerates mat_vmt_progs.h
make -C engine  plugins-rel FTE_TARGET=win64 NATIVE_PLUGINS="hl2 cod box3d ode"
make -C engine  qcc-rel     FTE_TARGET=win64          # -> engine/release/fteqcc64.exe
```

Copy `fteqw64.exe` to `ftesurf64.exe` and `fteplug_hl2_x64.dll` next to it, in
this directory.

Linux: `tools/linux/build.sh` (via `build-linux.ps1` on Windows, or as root on a
Linux box after `chroot-setup.sh`) builds a portable `fteqw64` and
`fteplug_hl2_amd64.so`; copy them here as `ftesurf64` and `fteplug_hl2_amd64.so`.

`FTE_TARGET=win64` is mandatory — msys2's gcc reports `mingw`, so the Makefile's
auto-detect picks win32. And **the `plugins/hl2` line is not optional**:
`plugins-rel` does not invoke that sub-makefile's default target, so the GLSL is
only regenerated by running make in that directory — and it fails *silently*,
leaving the plugin compiled against a stale header.

A full rebuild (clean object dir) is required after **any** engine header change.
The makefiles do not track header dependencies; `build.ps1 -Engine -Full` does
this for you and its header explains what goes wrong otherwise.

### 2. QuakeC

```powershell
.\src\build.ps1                # QC only -- what you want 95% of the time
.\src\build.ps1 -Engine        # + incremental engine/plugin rebuild and deploy
.\src\build.ps1 -Engine -Full  # + force a full recompile first
```

`build.ps1` finds fteqcc in `src\`, on `PATH`, or in `<engine>\release\`. Point
it at your engine tree with `-FteRoot` or `$env:FTESURF_FTEROOT`; the second
deploy target is `-QuakeDir` / `$env:FTESURF_QUAKEDIR` and is skipped if absent.

**No compiler binary is committed** — fteqcc is GPLv2 and this repository ships
no source offer to accompany a redistributed binary. Build it from the engine
tree (step 1) instead.

### 3. Map data (optional, but the browser is empty without it)

```sh
python tools/mapmeta.py     # tiers, stages, bonuses, thumbnail ids
python tools/mapdeps.py     # which maps need CS:GO or TF2 content
python tools/mapfetch.py    # map screenshots from Momentum's CDN
python tools/mapthumbs.py   # pack those into menu atlases
```

These need the Steam libraries mounted and take a while. Pre-built output is
attached to the matching [GitHub Release](../../releases) — unzip it into
`ftesurf/`.

### 4. Run

```
.\ftesurf.bat              # or ftesurf_debug.bat for a flushed console log
./ftesurf.sh               # Linux; ./ftesurf.sh --debug for the console log
```

---

## Source water and colour controls

Source water supports swimming input, drag, sinking and jump-to-rise. Underwater
appearance uses the map material's distance fog rather than Quake's orange tint;
water with no authored fog gets a subtle blue-green fallback. This works with
`r_waterwarp 0` and adds no blur or reflection capture. `r_sourcewater 0` restores
the legacy appearance without changing movement.

On **`surf_sidistic` only**, automatic settings rotate the red scene toward
blue-green, double Source fog distances and halve its maximum density. Other
maps keep their original hue and fog settings. The HUD is never colour-graded.
Console controls are live and archived:

| Cvar | Default | Meaning |
|---|---:|---|
| `hl2_colour_hue` | `-999` | Automatic map hue (150° on `surf_sidistic`, 0° elsewhere). An explicit degree value overrides it; `0` keeps the original hue. Applied after authored LUTs. |
| `hl2_colour_hue_strength` | `1` | Hue blend, 0..1; `0` disables the hue change. |
| `vbsp_fog_distance` | `-1` | Automatic distance multiplier (2 on `surf_sidistic`, 1 elsewhere). Explicit values scale fog start/end distances. |
| `vbsp_fog_density` | `-1` | Automatic maximum-opacity multiplier (0.5 on `surf_sidistic`, 1 elsewhere). Explicit 0..1 values reduce Source's fog maximum density. |

For the map's original look: `hl2_colour_hue 0`, `vbsp_fog_distance 1`,
`vbsp_fog_density 1`. Restore the automatic defaults with `-999`, `-1`, `-1`.
Hue uses the existing scene postprocess, not another LUT or an extra blur pass;
neutral maps with no authored LUT skip that pass entirely. OpenGL visuals.

---

## Momentum demos and run graphs (in game)

Open the leaderboard (`scores`) and select **imported**. A Momentum record
without a cached replay has **Get demo**: click its row to ask the NanoPi to
fetch, cache and convert the demo, then deliver the replay. **queued** is not
a completed download: the bounded downloader runs every five minutes, and
unavailable or unsupported demos report a failure. Closing the board cancels
automatic watching, not the NanoPi's durable request.

Tick the **line** boxes to load up to eight recorded runs together. While any
is drawn, a small **Run graph** sits on the HUD under the map info: their speed
against time. The board's **hud graph** chip switches it off, as does the same
chip in the graph panel or its square in `hud_edit`, where it can also be moved,
resized and set to show energy or both. Click **run graphs** in the board's left
column, or enter `linegraph`, for the comparison panel. Move the mouse across
either plot to read every run at that instant: its speed, how far behind the
fastest it is there, and its energy. The wheel zooms the time axis about the
cursor, a drag pans, the right button shows the whole run again. The coloured
chips above the plots hide and show a run's curves. Curve and visible world-path
labels use matching run names and slot numbers. Escape closes the panel. A
watched replay can be compared too, as slot 0, with its position marked on its
curve.

Where the `ui_imgui` plugin is beside the engine (development installs; no
release has it yet) it is loaded at boot, and the panel's two plots are drawn
by it instead, on ImPlot:
the same chips, readout and numbers, with curves at full sample resolution, a
labelled value axis that follows the view, a right-drag that selects a stretch
of time, a double click or the right button for the whole run, and a bar
between the two plots that drags. `ui_native_graphs 0` keeps the built-in
plots; without the plugin they are what you get.

Clocks align at each run/stage start. Energy includes vertical velocity and is
shown relative to that run's first sample, in equivalent-height units. Imported
or legacy recordings without a gravity pin say **g 800 assumed** on the energy
plot and are starred in the readout. Graph samples do not bridge teleports or
save-state stitches. `hud_linegraph 0` hides the HUD graph and
`hud_linegraph_labels 0` the world-path name labels; neither clears the loaded
run lines.

---

## UI style

The map picker, both leaderboards, the HUD editor, the save-lock and
Source-renderer menus and, since Patch 610, the strafe trainer and the run
graphs share one dark pastel look: rounded controls, clear interaction states
and delayed, wrapped tooltips. The rest of the gameplay HUD is unchanged. The
earlier look and its `ui_style` switch were removed in Patch 607; git has them
(562a6c9 and before).

`ui_tooltip_delay` defaults to 0.35 seconds. Editor text selects native
**physical-pixel** font bakes and
pixel-aligned positions; layout scale is not fractional glyph stretching.
The corrected physical-font path requires the Patch 570 engine as well as CSQC;
legacy virtual font slots remain unchanged. The matched gallery and falsifiers
are documented in [tools/font_quality.md](tools/font_quality.md).
This is SUI, not the planned native ImGui integration. Development status and
remaining gates are in [ROADMAP.md](ROADMAP.md), section 13.

The server must advertise the updated CSQC. After updating a local server,
reload/restart it and reconnect when convenient; swapping client files alone
cannot replace a connected server's old advertised code. No owner's running
client/server is automatically stopped to install it.

## Layout

| Path | |
|---|---|
| `src/client/` | CSQC — HUD, timer, replay, zones, portals, decals, fog, sprites, leaderboard, layout editor |
| `src/server/` | SSQC — entities, zones, timer, savelocs, player |
| `src/shared/` | constants, fonts, JSON, time, zones, portals, strafe maths |
| `src/defs/` | engine builtin declarations — **generated**, see Credits |
| `src/menu/` | the map browser |
| `src/sui_sys.qc` | immediate-mode UI, compiled into both `csprogs.dat` and `menu.dat` |
| `src/*.src` | fteqcc unit lists. **The ordering is load-bearing** and the comments say why |
| `tools/` | 13 Python tools: BSP dependency/metadata scanners, thumbnail packer, player-model builder, and the `.rec`/`.hid` recording validators |
| `ftesurf/cfg/default.cfg` | **the ruleset.** With `cvar_lockdefaults` on, every `set` here is the enforced default — changing a physics value here changes the game and invalidates times |
| `ftesurf/cfg/test/` | per-patch verification scripts, one per build, each opening with its hypothesis and expected values |
| `default.fmf` | FTE manifest. Carries the 66.667 Hz / 15 ms tick constants, forced with `set` so a stale config cannot desync the physics |

---

## Licence

**GPLv2 or later** — see [LICENSE](LICENSE).

World of Surf is not separable from a GPLv2 engine: it links FTEQW, compiles with
fteqcc, and `src/defs/*.qc` is generated by FTE's own `pr_dumpplatform` from
engine internals. One licence across the stack is the honest answer.

Exceptions:

- `ftesurf/gfx/fonts/*` — three fonts under **SIL OFL 1.1**, not the GPL. See
  [`ftesurf/gfx/fonts/FONTS.md`](ftesurf/gfx/fonts/FONTS.md).
- Everything else first-party — `ftesurf/models/`, `scripts/`, `glsl/`, `cfg/` —
  is offered under the same GPLv2-or-later.

---

## Credits

- **FTEQW** by Spike and the FTE team. World of Surf is a mod for it, and the engine
  fork it needs is a fork of theirs.
- **Momentum Mod** — the movement this reproduces, the map library, and the
  tiers. Their pre-2020 game code is archived publicly at
  [momentum-mod/game](https://github.com/momentum-mod/game) under the Source 1
  SDK Licence, and that archive is what the movement constants were checked
  against. **World of Surf contains no Valve or Momentum code and ships no Source
  assets** — mounted Steam content is read from your own installs at runtime.
- `src/defs/*.qc` — FTE `pr_dumpplatform` output. Seeded from my earlier project
  [ProtoAus/Nettest](https://github.com/ProtoAus/Nettest).
- `src/sui_sys.qc` and `src/shared/sh_strafe.qc` originate in my own earlier work
  published as **Shpuld** and **wrlines** respectively.
- Fonts: Roboto, Bebas Neue (Ryoichi Tsunekawa / Dharma Type), Google Sans Code —
  all OFL 1.1.
