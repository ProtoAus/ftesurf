# P1327 — lit textured snow, Source footsteps, owner audio and flash bursts

## Acceptance and predictions

Owner reports fullbright/plain snow and no visible caps; that is real negative
native appearance acceptance of the prior version. Prediction: actual stored map
light must change production shader pixels; old shader is an acted fullbright
control. New cap geometry must have nonzero depth/exposed edges, correct stored
fronts and valid roof clipping. Native placement/look remains the small owner
check in lextest.md, not invented from offline data.

## Snow

Mounted `materials/nature/snowfloor001a.vtf` (wind-rippled grass snow) and
`snowfloor003a.vtf` (clumpy caps) are in Momentum's bundled HL2 pack. Source VTF7.6
AXC/Zstd/BC1 previews were decoded/inspected locally with the existing native
format contract. Valve textures are REFERENCED, not copied into public assets.
The current HL2 renderer already supports this encoding; no native change.

Sample actual Strata72-byte HDR faces/RGBExp32 lightmaps at the baked snow
vertices; preserve the legacy56-byte/LDR reader path and use restrained0.28
ambient only for absent samples. Store normalized UBYTE IQM_COLOR. The new shader
multiplies real snow albedo by map light and the reversible weather tint, not
`e_colourident`/fullbright. No per-frame traces or lighting readback. Textures
retain ordinary mips; roof data remains point sampled.

Caps are uneven2..5units above exposed non-steep surfaces, with skirts only on
unshared polygon edges (no doubled internal rims).344grass/11326cap triangles,
3774boundary skirts,8076actual light samples and12ambient fallbacks. Baked RGB
is genuinely variable. Strict versioned model paths/material names register
before model precache. Old media stays for prior clients/rollback. No collision.

Use mounted CS:S `player/footsteps/snow1.wav`..`snow6.wav`, odd/even variants for
left/right. If unavailable, use Momentum's12snow footsteps. Do not copy those
Valve recordings into the package. The override remains Colin snowy grass only,
including quiet walking, and is disabled by the existing map-theme opt-out.

## Owner audio

Original `sound/winter/rainloop.wav`, `snowloop.wav`, `thunder.wav` remain untouched
in the owner's install. The converter takes explicit source/output/ffmpeg/report
paths, refuses overwrite, binds source hashes and verifies they did not change.
4,825,180bytes become235,151bytes (about95.1%smaller) as mono44100Hz nominal64kbps
Ogg Vorbis. Disk Opus is not compiled in this FTE sound loader; voice Opus is a
separate path. Vorbis needs no new engine/plugin/DLL.

Decoded durations8.424/10.709/8.220s, peaks0.260/0.822/0.552, finite/no clipping.
No loudness normalization or original-file changes. Existing native loop/update/
stop channels are reused; the rain/snow choice changes audio only. Add the exact
winter Ogg release selector so the next package includes these files.

## Lightning controls

- `r_weather 1`: enable weather (Colin theme also enables its authored weather).
- `r_weather_test 1`: one immediate randomized burst.
- `r_weather_test 2`: repeating preview, about8seconds between burst starts.
- `r_weather_test 0`: stop preview; normal storms still happen.
- `r_weather_interval 10`: shorter ordinary timing; bounded5..900seconds with jitter.
- `r_weather_loop rain` / `snow`: choose supplied ambience, not precipitation.
- `r_weather_audio 0`: silence weather. `r_weather_flash 0`: no flash brightness.
- `weather_info`: loaded components and actual burst/flash/thunder counters.

Each burst has3..6strokes,50..150ms durations and60..340ms dark gaps. Thunder is
scheduled0.8..3.1seconds AFTER the final stroke ends. Cache a world direction
within35degrees of the current view at event start; it does not follow a moving
camera. The GPU no longer picks an unrelated time-based bolt axis. No dynamic
lights or per-frame lightstyle/lightmap updates. Missing audio cannot stall later
visual bursts. Preview is opt-in; it stops with test0, not by changing master audio.

## Actual evidence and limits

ThreeVM NoDeploy build0warnings after fixing a retained QC reserved-local error.
Actual production WGL stages: old V2 bright/dark0.97386/0.97386; lit V3
0.89804/0.18039; sky base/flash0.28105/1.0. Actual roofed/wrong-winding negative
pixels vanish. Native map meshes/colour arrays and PCM streams inspected. Shared
IQM-writer/render controls4pass; initial info-string expectation failure retained
and the product now prints the actual command spelling. Timeline tests are
SOURCE-STRUCTURAL only; no native event timing/listening/look/FPS pass claimed.

Broad `shipguard --release-policy` could not run in this source-only tree because
base `ftesurf/particles` is absent. That is not a feature/codec success or a broad
pass. Targeted new selector/signed-path checks are recorded separately. No release
was requested; ordinary build delivery is not a prepared/published release.

Deployment/source/artifact provenance will be appended after actual delivery.
Qualified build must preserve the inspected released native/API base; ship only
client and owned media, not newer peer native/server/menu work. No native pins,
QC Build, backend generation, player data/config or evidence semantics changed.
