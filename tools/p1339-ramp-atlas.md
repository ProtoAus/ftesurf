# P1339 - on-request replay-baked ramp atlases

## Scope and current state

The actual Story/Event roster contains 114 unique maps. The completed bake
currently has 100 nonempty atlases, 10 maps with contacts not placed on the
supported static mesh, and four without available local inputs. Empty/error
results are NOT atlases or full-coverage passes. The 100 ready map triples are
published, both Windows client installs and all 12 lobby clients are updated.
The explicit 14 gaps remain; this is NOT a claim of complete 114-map coverage.

Use every available local recording/Momentum input, plus retained or downloaded
CSS66 KSF originals. Cosmetic readers preserve original bytes, bind map/game/hash,
accept legacy imported source tokens and ordinary line endings, retain distinct
partial clips, and prefer a readable complete KSF original over its covered
conversions. They do not create native evidence, verification or ranking credit.
The additional capture retained 4,799 unique KSF originals; nine were newly
fetched, including inputs for two formerly uncovered maps. Upstream HTTP500
stopped the bounded, shared-lock/paced fetch and established the normal park.
Uncrawled categories/tails and pending originals remain incomplete, not absent.
Final read-only check found the shared demo park active until6Nov11:16:49UTC;
no request/park modification was made. A future capture must recheck actual state,
not infer permission from that historical expiry.

## Client use

While in a game with online terms accepted:

```
rampwear_download                 // current map; leaves visual settings alone
rampwear_download surf_beginner   // prefetch a named map
rampwear_status
r_rampwear 1                      // optional wear/scratches
r_rampwear_dirt 1                 // optional dirt
```

Marks and dirt still default OFF. Enabling an effect can request missing assets;
explicit prefetch does not enable either effect. Download caches are under the
QC sandbox `data/gfx/rampwear/`. A strict geometry file names the immutable PNG
and its canonical base64 transport by hash. The existing online request counter,
consent gate and callback are reused. Decoding is bounded per frame, verifies
SHA256 and PNG dimensions, and never raises the native remote-picture limit.
The public route exposes only cosmetic map metadata and hashed atlas assets,
not arbitrary game/player files. No raw replay or private provenance is published.

## Verification so far

- Four offline cosmetic/KSF suites: 23 tests pass, including raw v2/v3 full-frame
  reads, acting map/game/byte binding refusals and full-original/partial-clip
  controls. Distinct partial captures are not merged by a shared foreign label.
- Standard isolated THREE-VM build from current published P1341 baseline plus
  this feature: zero warnings. No native API/pin/tag or QC Build change.
- Real dedicated-socket/native client with no local atlas: all 14 HTTPS/cache/
  material checks pass for surf_beginner. The 638,969-byte PNG is verified and
  loaded as the actual 2048x512 custom material with picture limit131072 unchanged.
  Consent refusal and malformed geometry both act; no QC error, natural exit0.
- Original wrong-cache-path and unflagged-texture-query failures are retained.
  QC fopen writes `data/`; shader texture lookup needs that physical prefix.
  RESTYPE_TEXTURE queries flags0 and misses no-sRGB/clamped images: inspect the
  actual custom material rather than deadlocking its first draw on that lookup.
- All 100 ready triples pass the ACTUAL client bounds and both content hashes.
  Largest PNG: 5,128,368 bytes; largest mesh: 17,833 triangles. A separate native
  surf_classics test passes all14 controls with its 5,007,077-byte2048x4096 PNG
  and that largest mesh. The absolute-largest PNG has destination/hash/bounds
  verification; do not relabel it as a separately observed native render.
- Authority readers are unchanged: reccheck949/0; explicit runs-only corpus
  548 recordings /351 existing REC+paired-VIEW faults, unchanged from baseline.
  No SAVES, new authenticity, evidence-format or clean-corpus claim.

## Remaining coverage

No local inputs: surf_kismet, surf_olivia, surf_sinister, surf_sirena. Additional
upstream work is blocked by the real HTTP500/normal park; do not bypass it.

Contacts not placed by the current static-world-face/displacement baker:
surf_axiom, surf_board_this, surf_cyberwave, surf_dragon, surf_hunty,
surf_kitsune2, surf_lovetunnel, surf_lt_omnific, surf_progress, surf_spacemonkeys.
These are not proof of missing gameplay ramps. Check actual map build/mesh and
recorded coordinates before extending supported geometry; never fill them with
fake contacts or count an empty mask as complete coverage. Bounded diagnostic
Axiom375KSF/BoardThis483native poses still have zero world touches at tested
height offsets through +/-72; conservative unparented/enabled/untargeted brush
origin transforms also give zero. Those controls are NOT bakes or proof that all
unplaced ramps move. Open follow-up/falsifier is in BACKLOG.md.

## Snow model

The unchanged model moves from `models/snow/flakes.iqm` to
`models/christmas/flakes.iqm`; generator/default references and explicit release
allowlist follow it. New clients prefer the new path and can use the old path
with old content. Runtime old copies remain compatibility/rollback assets.

It is one IQM field, not 64,000 CPU particle entities: four meshes hold 64,000
seeded triangles. The GPU shader opens each seed into a camera-facing flake,
animates falling/sway/drift, and wraps the field around the eye. Map roof masks,
ambient lighting, density/size and near/height fades control its appearance.
Ground snow textures/caps are separate cosmetic geometry, not falling particles.
No snow appearance or measured FPS change is claimed by this byte-identical move.

## Deployment receipt

- Public cosmetic aliases and immutable files: 100maps/300files, all destination
  hashes verified; every target lobby BSP hash matches the bake's BSP. Atomic
  metadata aliases retain their preimages; old hashed media remain cache-safe.
- BOTH Windows: CS `ecb6d2c3d61254d931fb2a9ddc14f90efb072be283e3761c64edea8cabeb0d46`
  and matching symbols/new model. Protected originals18592/144 unchanged;
  no owner process stop or config/player-data write. Source `2d82c278` on the
  current main profile. This is intentionally NOT the Pi client profile.
- ALL12Pi: CS `445abb4cf43c32beb8b1e27dc78f2e09d77838bdb235c80ffb5baf9e365f6238`,
  compatible source `9debcfc9` on deployed P1341Pi base `68597668`. SSQC remains
  `5e8cd6d16538a60818bc1072fdd37a350c29324518b94602e03981d4228d6416`;
  native/plugin/menu/config/backend generation/files held. Activation receipt
  UTC2026-11-06T07:38:06Z: all12epochs replaced; 47848protected originals have
  zero changed/missing entries. ALL8recorder parts and ALL183resume entries
  independently archived/hashed offbox before stage/restart. Original lobby
  capacities restored, sweep lock released. Normal known-CS admission appended
  only the two qualified client hashes; no backend restart or policy change.
- Last transport wrapper timed out at180s while remote postflight continued.
  Its failure is retained. Later read-only observation found the actual successful
  activation receipt/all12new epochs; NO repeated swap/restart or downgrade.
  Earlier missing-input/source-registration refusals and restore-log collision
  remain history. Fixed exact seams, reused valid archives, kept safety gates.
- A fresh live-lobby client with NO local CS downloaded checksum1da02511 exactly
  matching445abb4c; board9cols/type14 drew, screenshot inspected, noQCerror,
  natural exit0. The fresh fixture had no local zone data and its screenshot
  does not accept world textures, populated board data or ramp/snow appearance.
  Local dedicated main and Pi-profile tests are separate evidence.
- New Christmas model is verified at BOTHWindows and Pi. Windows legacy copies
  retained; the old Pi legacy path was absent, not invented or deleted. Source
  rename is byte-identical. No human snow/marks/FPS acceptance is implied.

Known rollback: current Pi `.prev` plus immutable private preimages; revert only
this CS through the same actor/data-preservation gates, never restore player data
or downgrade a potentially generating fleet. Web aliases have CAS preimages;
retain their immutable media. No release, native pin/tag or QC Build move.
