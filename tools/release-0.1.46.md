# World of Surf 0.1.46 delivery

## Published

Published 15 Nov 2026, completing at **19:25:56 UTC**, from one successfully
previewed, sealed Windows/Linux candidate. Publication used that exact receipt
without rebuilding, repacking or resigning. Public page and metadata:
<https://proto.bar/ftesurf>.

- Game version: **0.1.46**, qcbuild **89** unchanged.
- Frozen QC source: `6f05369c6ca89bbe9c338b48e170f46fb25bfafe`.
- Frozen engine: `ca46327b755db85fdb2fc75b533e5863ee256e3d`, `patch-1571`.
- Bootstrap source: `8de13397d640b8b22ef2a9f2b0649ecfbf420ec7`.
- 33 player-facing patch entries. Work landing after this cut stays in `next`;
  in particular P1573 is not relabelled as part of these frozen archives.
- Public receipt SHA256:
  `a603fccd2de26e739109ab23799b555cebeb89b763594ea814b7c25921e4f1fc`.
- Signed default feed SHA256:
  `0b2468d59ebf55cc45a9b1360b034e06bea36e84820f0de9163f4f4399f0157b`.
- Receipt overrides: **none**. Player-data, signatures, predecessor locking,
  no-overwrite, object round trips and ownership checks were not bypassed.

## Exact public downloads

| Artifact | Bytes | SHA256 |
|---|---:|---|
| `ftesurf-0.1.46.7z` | 78,787,263 | `d71761f328c942737961a219d76c75e93428d43d6cc5e6facd9fccf94706382f` |
| `ftesurf-0.1.46-linux-x86_64.tar.xz` | 78,910,740 | `addd95c42564b74f58ea6302747717dfcca43a9f0f0ff225ac88e2ead94adc89` |

Both complete public HTTPS downloads were rehashed against the sealed candidate,
not trusted from newly downloaded website metadata. The page also matches the
frozen page byte for byte. Referenced update objects and standalone launchers
were published and round-trip verified by the normal release procedure.

## Qualification and acceptance

- Three release-version QC VMs compile with zero warnings. Public-default Windows
  client/server/five-plugin full build has no warning messages new to its control.
- Final Windows images use the complete prior published SDK, not development
  DLL fallbacks. PE imports and a fresh actual client/plugin smoke qualify those
  final static images. Both appearance scripts tables demonstrably act.
- Exact-pin Linux client/server/HL2 builds pass all four gates; the standalone
  Linux bootstrap is built in the supported baseline and passes its ELF/help
  checks. No private movement build flags or images enter the release.
- Actual new launchers use the ordinary default HTTPS feed in fresh synthetic
  Windows and WSL Linux installs, without launching a game. Windows rehashes
  1,139 managed files; Linux 1,138. Each preserves three protected sentinels:
  settings, player data and an edited local zone.
- The actual previously published 0.1.45 Windows launcher also accepts the new
  signed feed and files, updates a genuine old signed CSQC file, rehashes all
  1,139 managed files, and preserves the three sentinels. The old and new Linux
  launcher binaries are byte-identical; the already-acting Linux acceptance
  therefore directly covers that old reader without rerunning identical work.
- Normal build artifacts, the matching dedicated server/optional plugins and the
  two scripts tables were installed in both local Windows installations at
  19:47--19:50 UTC. All 12 target hashes per install were checked. Protected
  player/configuration files, existing tracked source edits and the shared index
  remained unchanged. This was not a public-release repair of a dirty development
  checkout: existing edited configuration assets were deliberately not replaced.
  No owner's game was terminated and install locks were released immediately.
- The generated release metadata retains all 3,291 map entries and 811 dependency
  entries, including existing downloadable CSS port aliases; no final row loss
  override was used. Existing legacy DATA appearance tables were left untouched.

## Scope and limits

The full requested HL1/AG and HL2 movement additions are unfinished and not
introduced as working features here. The requested 100/250/1000 presets apply
only to HL1/AG. Existing public P1542 limited GoldSrc practice remains explicitly
limited, as its patch notes say.

These automated checks are not full multiplayer, visual/feel or performance
acceptance. The small owner version/menu/map/knife visual check is **pending**
in `lextest.md`; no human pass is invented. The frozen release cut is distinct
from later independently published or deployed development work.
