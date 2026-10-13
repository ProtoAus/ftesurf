# Soundsky sky seam falsifiers (registered before implementation)

Hold aim, audio, time and exposure fixed. Inspect output pixels, not draw counters.

- Stationary camera: repeated render identical at fixed time for parallax 0 and 1.
- Move camera laterally by 0.1 map diagonal, same aim/time: parallax 0 identical; parallax 1 changes landmarks, nearer layer changes more than distant layer. A uniform UV shift must not pass the depth test.
- Warm red vs cool blue atlas cells: sky chroma follows thumbnail; palette 0 ignores thumbnail. Grey cell stays neutral, missing/late atlas shows neutral fallback (not error texture), and loaded atlas replaces fallback.
- Parent steering extension: red-left/blue-right thumbnail retains distinct red and blue output regions (not a single averaged purple tint). Three independently normalized region tones colour separate depth landmarks and emission; bounded six texture taps.
- Teleport: no accumulated motion, finite intersections and no previous-map state. Map change resets center/scale/palette and landing ring. Renderer restart rebuilds palette RT without stale resource handles.
- Live integration (pending parent fixture agreement): sky off/on matched aim screenshot; terrain pixels/occlusion unchanged. Look up/down and across skybox seams. Thumbnail atlas neighbours must not bleed. Repeat after vid_restart and map switch. Record frame time for matched sky coverage.

Static/math tests do not certify live renderer pixels, thumbnail async lifecycle, terrain occlusion or performance. Any CPU preview is explicitly a geometry/palette falsifier, not an engine screenshot.
