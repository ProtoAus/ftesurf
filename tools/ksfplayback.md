# KSF in-game playback (P702)

KSF CSS/66t v2/v3 binaries can now be converted to the existing imported replay
player. This is camera/path playback, **not native physics verification**.
It does not turn KSF board rows into native PBs or change their rankings.
Automatic leaderboard Watch/download/cache association is a separate feature.

## Watch the twelve supplied clips

The development installs have the converted clips in `ftesurf/cfg/ksfreplays/`
(outside player data) and the alias file `cfg/ksfplayback.cfg`:

```text
exec cfg/ksfplayback.cfg
map surf_null
```

Wait until you are in the map, then:

```text
ksf_null_farsh
```

Other main runs: `ksf_null_luco`, `ksf_null_proga`.
For bonus 4 load `surf_prosurf` and use `ksf_prosurf_hunter`,
`ksf_prosurf_megacutechicken`, `ksf_prosurf_ay`, `ksf_prosurf_liq` or
`ksf_prosurf_nate`. On `surf_monolith`: `ksf_monolith_lucokiller`,
`ksf_monolith_liq`, `ksf_monolith_nex`, `ksf_monolith_hunter`.
Aliases do not secretly change maps; the reader refuses a different map name.
These clips are generated runtime files, not checked-in raw replays.

Existing controls apply: Space pauses; arrows seek; drag the scrub bar;
Escape closes. Console controls:

```text
replay pause
replay seek 10
replay play
replay speed 0.5
replay seek end
replay status
replay stop
```

`hud_watch_info 1` opens the detailed panel. Chrome explicitly shows KSF style
and **map build unknown**; the info panel says imported/not verified and does
not interpret a hash-based run ID as a native date.

## Convert another public CSS/66t replay

Save the binary fetched by the KSF viewer, not the HTML viewer page. Its raw
endpoint is `/api/replays/<filename>?game=66t`. This tool intentionally works
on local files; it does not hammer the public host or follow arbitrary URLs.
From `C:\FTESurf`:

```text
python tools/ksfconvert.py C:/clips/replay_css_example.rec --map surf_null --style FW --owner "Display alias" --seconds 52.51738739013672 --out C:/FTESurf/ftesurf/cfg/ksfreplays/my_null.rec
```

Then load `surf_null`, wait for spawn, close the menu, and run:

```text
replay cfg/ksfreplays/my_null.rec noview
```

Use `--bonus N` for bonus N. **CSS/66t origin is an operator precondition:** the
binary prefix does not authenticate game/rate. Stage clips, CSS100t, CS:GO and
other undocumented layouts are not supported; they cannot universally be
distinguished from this prefix alone. `--map`, `--style` (FW/SW/HSW/BW), course and owner
come from the exact external board/viewer row. The binary header does not name
them; its kind and the filename's numeric fields are NOT identities. The owner
is only a display alias. No Steam/GUID binding or board filing is claimed.
`--seconds` is optional; when supplied it must agree within 2.5 CSS ticks, plus
one for each frame the file repeats while moving, plus one a 10,000 frames
(Patch 757: KSF's time is its timer's, not the frame count; tools/p757ksfconvert.md).
A new output file is required; existing recordings are never overwritten.
Conversion rejects malformed/HTML/nonfinite inputs, ambiguous or missing course
bookmarks, unsupported bounds and invalid bindings before creating the file.
Input is bounded at 64 MiB; converted playback is bounded at 200,000 frames.

## Format and limitations

- FTESURF-REC 5 sampled clock, source SHA256, `foreign ksf`, explicit map/course/
  style, no fabricated native integrity keys, journal, sidecar or warp evidence.
- Initial start-zone entry followed by its exit establishes start; a recording
  that begins inside the start zone (no entry before its one exit) is taken only
  with `--seconds` binding it (Patch 757). Main ends at
  zone99 entry. Bonus N uses zone30+N: named standard triggers disambiguate
  start/end; the unclassified-target-name fallback requires exactly one later
  entry (including nonempty names outside the documented numeric namespace). Stage N
  (`--stage N`, Patch 891; KSF records each stage as its own file) runs from its one
  exit of zone N to the one later entry into zone N+1. The last stage (`--last-stage`)
  ends at a zone99 entry when one is bookmarked; none of surf_kepler's 13 last-stage
  files has one, so the official time from the exit places the finish (`--seconds`
  required, `ksfstop timed` written), at most 2 ticks past the file's last frame,
  which it then takes. Multiple intervals or missing boundaries are refused, never
  full-file timed.
- Preserve pre-roll, rebase time to the start bookmark, include the finish
  sample, exclude post-roll. The displayed duration is the **bookmark clock**;
  the separately retained official time can differ by the bound above.
- Position, velocity, pitch/yaw come from source floats. Raw Source button masks
  are preserved in additive `ksfbuttons <source-frame> <mask>` records. Native
  FSI directional keys mean resolved movement direction, not raw buttons.
- v3's documented 18-cell layout preserves actual analog moves to six decimal
  places and ground bit0. Direction keys use those serialized values, so tiny
  analog commands rounded to zero cannot leave phantom directions.
  The shared `demodata` capability enables the existing imported ramp inference
  only with recorded ground and per-tick velocity. Old `momdemo` still works.
- v2 lacks recorded ground and analog move magnitudes. `moves buttons 1` is an
  explicit **unit direction proxy**, not measured input amplitude; opposing
  directions cancel without guessing SOCD order. Ramp contact is unavailable.
- The public viewer conflicts on v3 flag bit1 (ducked versus teleport). We do
  not translate it to native ducked state or warp evidence. Duck INPUT remains
  visible; ducked BODY/eye height is unknown and playback uses the existing
  standing-eye default. No native collision/ramp plane is invented.
- The binary contains no BSP digest. A matching map name is not proof of the
  same build; KSF playback always states build unknown. Visual alignment on the
  installed maps was sampled, not verified across every KSF map revision.
- Imports remain outside owner `data/runs`, native ranking and verifier inputs.
  A generated text `.rec` is not an authenticated source/native run.

## Tests / reproducibility

`python tools/test_ksfconvert.py` tests layout, fields, flags/buttons namespace,
bookends/bonus names, rejection, input sanitization, key/move consistency and
no overwrite. `python tools/test_ksfreplay_info.py` exercises the binary bounds.
`python tools/test_reccheck.py` is unchanged.

`tools/ksf_samples.json` records the twelve exact public sample bindings; it is
not a trusted player-identity manifest. `tools/p702ksf_smoke.py --help` describes
the owned dedicated runtime harness. It compares source bytes independently,
checks full on-tick camera traces, real render-frame playback, pause/seek/end,
source labels and absence of invented `.view` angles. Active-replay replacement
refusals prove immediate closed state/cursor release and actual restored body
movement; missing map bindings are refused too. Test overlays do not write
installed player data. Use a 600-second outer timeout for all three maps.
