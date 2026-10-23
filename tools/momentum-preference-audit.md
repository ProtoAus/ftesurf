# Requested global Momentum/build/demo audit — 22 Oct 2026

Read-only source/installed-metadata audit at23:35UTC, not a product patch or a
blanket map-replacement operation. No BSP, zone, recording, saved choice, cfg,
cron, policy or guard changed. Existing full archived suite evidence is reused;
no passed tests were rerun for a documentation-only audit.

## Preference is already the default, not an unconditional override

- `tools/maproster.py:140-181` models earlier mount wins, with gamedir first.
  Actual PRIMARY descriptor: ftesurf > momentum > cstrike > hl2. Surf/bhop
  winner metadata:1732Momentum,21gamedir,2CS:S (1755total). This enumerates loose
  BSP metadata; it is NOT a native all-package/mount tracing measurement.
- `mapwatch.py:1227-1306` gives new common names Momentum's build, waits rather
  than guessing when Momentum names are unavailable, and requires --updates for
  replacements. `:1552-1645` additionally gates idle state/zones, preserves the
  old build, then swaps. Active manifest's mapwatch has --updates enabled.
- `menu/m_main.qc:2459-2530,3238-3279`: blank pick uses the plain/Momentum row;
  persisted explicit CS:S choices survive. A disabled plain build can fall back
  to enabled CS:S. Primary has2explicit saved CSS picks; no picks were cleared.
- Secondary control install's descriptor/model is NOT equivalent: no direct
  fs_addons.txt mounts discovered, only3loose gamedir maps,0saved CSS picks.
  Its launch-time basedir/shared-asset configuration was not traced. This is NOT
  evidence that it has a full standalone Steam library or identical gameplay
  asset resolution; do not silently rewrite the control install.

## Two historical local shadow examples actually measured

SHA1 streamed over only these BSP pairs, no full library content-hash claim:

- surf_dune primary loose AND installed Momentum are
  25103e2582c37b5da8c24fce0b7721b7bbce1534. It is not currently a byte-distinct
  shadow, unlike the older historical note. Pi held/cached-published match too.
- surf_fantasy primary loose is f04171db504fe5b25e28f01a65110ba5f3173b64;
  installed Momentum is fd73ae1b0941b004ad032a45bc8a69b617b97e4c.
  Pi held BSP matches the latter and its cached Momentum catalogue hash.
  This is a concrete local override, not proof that renaming a replay converts it.
- Pi cache timestamp1792628582 is recorded as a CACHE observation, not a claim
  of a fresh authoritative Momentum API response. Both Pi BSPs were read with
  before/after size/mtime stability checks; no hash-cache write performed.
- The first Pi path assumption was wrong; the manifest has no --maps override.
  Actual mapwatch default comes from S.MAPS_DIR, with SURFD_MAPS override read
  inside the script without printing config/secrets. Failed read-only probes
  retained; no mapwatch --go/--updates operation was invoked.

Do not delete/replace the primary surf_fantasy override or reset explicit choices
without the owner's decision. A gamedir override may deliberately match a
server/old build. A replacement can strand old geometry-dependent observations;
existing native evidence is not relabeled. The narrow pending owner question is
whether that local override should be preserved or retired with its bytes kept.

## Cross-source demos: linked observation, not equivalence

- Live map list:2123rows,1081m/beta-source rows and424catalogue-declared links.
  These are metadata counts, NOT424geometry-equivalence proofs.
- `mapwatch.py:1056-1078` links real roster ports to held Momentum roots, one
  allowed port suffix; it does not strip arbitrary version suffixes. Zone
  transfer still needs independent zonefit geometry gates.
- `cl_mapports.qc` accepts exact names or a validated board family/bounded map
  list with unique source/loaded/root rows; a suffix alone grants nothing.
- `cl_watch.qc:4793-4836` preserves the imported header map. KSF on a configured
  linked build is allowed ONLY as observation and warns "geometry may differ";
  missing/unconfigured bindings refuse. Other observational playback can warn
  that a camera on another map flies through nothing. Neither transforms a BSP,
  rescales geometry or makes imported timing/native evidence interchangeable.
- Boards keep native rows build-bound while configured imported-family rows can
  be displayed together. Source/style/tier attribution remains distinct.

Conclusion: requested audit complete; no global-default code fix established.
One primary local byte-distinct override needs an owner decision, and standalone
secondary asset parity remains unmeasured. Different builds cannot be made
compatible by renaming alone; no timer/evidence/data migration attempted.
Evidence: owned artifacts/momentum-audit.json and momentum-audit-secondary.json,
source citations above, sanitized Pi cache/two-BSP measurement in session ledger.
