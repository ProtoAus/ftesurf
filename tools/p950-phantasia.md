# P950 — Phantasia glass and material diagnostics

Development feature; not a release, Build bump or owner visual acceptance.

## Root cause and bounded fix

Both actually winning CSS and Momentum Phantasia BSPs embed the prop material
`models/propper/cdizzy2026/realworldtextures/glass/glass_06.vmt` with shader class
`Refract_DX90`. It has an authored normal map and tint, not a diffuse picture of
its own. Valve's Source SDK `materialsystem/stdshaders/refract.cpp` explicitly
aliases `Refract` to `Refract_DX90`. Our plugin instead treated the latter as an
unknown class, generated unlit output, and tried a nonexistent same-named diffuse
VTF. Static dependency resolution and a successful VMT lookup cannot detect that
renderer-support error. The closest-world shader ray hits an invisible collision
material in this scene, not the visible prop; do not misidentify it as the cause.

Normalize only this known alias before both parsing and generation. Keep all the
existing Refract rendering modes, normal/tint policy and legacy fallback behavior;
ignore the DX60 block rather than applying its keys to the active DX90 material.
No map rename, replacement BSP, Valve asset packaging or guessed mount is shipped.

`hl2_missing` now additionally lists unsupported material/class pairs observed
since world load, including later prop registrations, once per case-insensitive
bounded material name (256 entries; explicit overflow notice). These are renderer
support problems, not missing-pack advice. World changes reset that list and all
four legacy unknown-class name slots. A no-missing-VMT response explicitly does
not promise complete sampled-image coverage; `r_imagelist` remains the image-load
diagnostic. Genuine existing-VMT/absent-image census improvements remain open in
BACKLOG.md. Load-time HUD counts are not relabelled as complete runtime image counts.

## Acting controls

Pre-registered predictions and raw logs/images stay in the owned private fixture.
Original owner state was read only for map/CRC/pose/duck, then a new minimal
DEMOTED pose fixture was constructed. No original run, identity, timer, split,
receipt, journal or view file was copied. Owner save and original BSP stayed intact.

- Native945 control and changed native run the SAME explicit refract2 CFG, both
  CSS and Momentum. Both completed with exit0 and no command/VM errors. Four
  inspected PNGs show the large checker before and authored tinted glass/scene
  behind after. Native pass readbacks name the real normal image and refractflat
  with authored tint, rather than the invented diffuse image.
- Full1 and flat0 produced inspected screenshots and native program readbacks.
  Their combined wrapper later crashed in an unrelated shader-remap diagnostic;
  it is NOT a report/reset pass. That separate command remains a BACKLOG item.
- The report control changes exactly one embedded VMT class in an OWNED copy of
  the actual CSS BSP. Multiple prop registrations yield exactly one unsupported
  material/class entry, explicitly not an asset-pack mount. Changing to surf_ace
  clears that class. Wrapper exit0; source BSP unchanged; only the hash-verified
  owned synthetic BSP removed. No test map is a ship input.
- An initial verbose two-map diagnostic timed out after its acting CSS scene.
  Retain it as a failure; the same entrypoint with targeted output completed the
  subsequent matched pair. Do not count extra launcher attempts as feature work.
- Full Windows prototype build via src/build.ps1 -Engine -Full -NoDeploy:
  three VMs0warnings; 74 inherited native warnings, the exact normalized P939
  multiset, and no new warning site.
  The plugin's standalone clangd context lacks real include/define state; its
  false diagnostics are not substituted for an actual compiler result.

No physics, input/evidence API, native verifier, reader/backend, consent, retention
or account policy changes. No blanket graphics parity/performance claim.

## Delivery boundary

Native source `9f85d87875fe3c1338988c41f9be2ae2559ff5a4`, tag `patch-950`,
stamp `git-7757-patch-950-0-g9f85d8787`. Final exact-tag native also completed the
CSS+Momentum scene control with exit0. Clean Full compilation hit the same two
parallel ZIP packaging failures as P939; retain its failed log and available
failed output. Serial completion through the existing entrypoint rebuilt the
missing targets. All seven fresh AMD64 PEs qualify, both EXEs have the exact clean
stamp and all five appended plugin resource ZIPs validate. Full native warnings
are the same74 baseline; serial repeats3 inherited warnings,0new. Three VMs0.
No plugin Git stamp is invented; their provenance is clean source/Full compile,
freshness and exact hashes.

Installed delivery is held while the owner's primary Windows game is running;
no process is killed and no swap transaction has begun. Existing native945,
gameplay/menu programs and owner data are preserved. Owner check is in lextest.md.
This client-renderer feature needs no Pi/server-runtime or backend change.
Epiphany's black scene and all other original requests remain separate unfinished
work, not acceptance criteria silently dropped by this fix.
