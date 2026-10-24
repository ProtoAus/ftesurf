# P966 — lit Character pieces and continuous held viewmodel

## Scope / predictions

Owner reports on surf_666: bare hands/FBI Gray ignore red light; default arms and
knife respond. Neutral Preview's subtler glove look is liked. +sl_hold hides the
model until release. Predict: targeted Character pieces respond to red/ordinary
lighting; neutral AO styling remains; actual held model stays visible without an
extra equip. Keep movement, hold and evidence behavior unchanged.

Original knife texture collision, linked-account preferences and watched-player
setup/shoot/inspect mirroring are still authorized follow-up work, NOT this
patch's delivered features. Track them in BACKLOG/ROADMAP and lextest.

## Change

- Installed metadata classifies Character materials with real local diffuse files.
 32piece rows gain bounded surface/texture pairs; all original row IDs remain.
- KCAT_PieceRules applies matte defaultskin materials after variant remaps. The
 existing bare-arm handling and neutral glove shader/AO pairs remain unchanged.
 No global material-class renderer changes, licensed assets or inventory claims.
- WP_Frame still clears queued motion/recoil/fire state while held, but no longer
 returns before scene submission for MOVETYPE_NONE. Other unsupported movement
 states remain hidden. No server/hold/movement/recording code changes.

## Acting evidence / limits

Three VMs compile through existing NoDeploy/Jobs8 entrypoint, zero warnings.
Real dedicated socket with qualified Windows OpenGL client, isolated owned rig:

- Old delivered7ebaca8b CSQC552790cb/cache145a7654 reproduces white Bare Hands35 /
 FBI Gray78 alongside a red-lit Original knife3, and no model during actual hold.
- Candidate CSQCc5bc20c7/cached74e2dc3 draws the parts red; after zone_goto to
 ordinary light they return to ordinary colour, not a fixed red tint.
- Actual +sl_hold HUD says held, movetype0; model remains visible. draw-starts1
 before/after proves no re-equip. Release acts. No QC/shader runtime errors.
- Neutral gloves48/layer117 retain their existing soft AO look/program. Only
 formerly unsupported Character skin/cloth surfaces receive the new lit mapping.

Screenshots/logs retained privately: lighting-before-red/lighting-after-red,
held before/after, neutral-after-red and ordinary-light control. This reproduces
the owner's red room near the read-only slot022 pose, NOT a pixel-exact camera
comparison: normal load/floor settlement changes free-view height. The old/new
held view coordinates agree and the knife is an acting lighting control in both.
Own ordinary game save/load/noclip commands generated the rig's save2; the owner's
save/data/config were never copied, loaded, altered or used as synthetic evidence.

Preserved setup failures are not passes: first attempted staging used the wrong
NoDeploy output path, so the unchanged old client became an explicitly verified
control; initial seeder --help and Python-version-only junction queries failed.
The actual compiler output directory was then read and the subject SHA/cache
verified. No weakened ownership/data/map/evidence guards or new harness chain.
QC LSP silence is not validation; fteqcc and actual rendered images are.

Candidate observations precede the descriptive KCAT helper rename/patch metadata;
final committed compatible artifact proof and destination hashes must be recorded
before claiming delivery. P961/P963 producer/menu/native work must not be shipped
merely because it is present on main. Human appearance/feel acceptance remains
pending in lextest.md; no physics, signed-evidence, performance or all-renderer
claim is made by these cosmetic checks.
