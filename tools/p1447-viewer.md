# P1447 -- the web run viewer draws Strata maps, and builds maps faster (ftesurf-3a, 9 Nov 2026)

Lex: "a lot of maps don't build and throw an error, probably because they are Strata Source maps? it's also a bit
slow". Every change is a tools/vendor.py PATCH (or stubs/), re-vendored from noclip fd973ff2; watch.js rebuilt.

## What failed, measured (tools: src/viewer/tools/bspcensus.ts, the viewer's own BSPFile over a map folder)

- Library census before (partial, 429 maps): every v25 map failed (43/43), 2 of 385 others (bhop_anomalous v21:
  VERTNORMALINDICES v1; bhop_perspective v20: no lighting lumps at all). 1,240 maps have watchable runs (Pi DB).
- Per-lump versions of all 133 v25 maps (tmp census): NODES 1, FACES/FACES_HDR 2, LEAFS 2, EDGES/LEAFFACES/LEAFBRUSHES 1,
  DISPINFO 1, ENTITIES 1, VERTNORMALINDICES 1, PRIMITIVES/PRIMINDICES 1, LEAFWATERDATA 1, LEAF_AMBIENT_INDEX 1,
  WORLDLIGHTS 2, OVERLAYS 1-3, sprp 12/13, game lumps LZMA-flagged.

## Layouts (engine's plugins/hl2/mod_vbsp.c where it reads the lump; measured where it does not)

- strata_dnode_t 48 B, strata_dface_t 72 B, strata_dleaf_t 56 B, DISPINFO v1 232 B (mapFace u32 at +0x24), edges and
  leaffaces u32, sprp v12/13 (32-bit leaf refs, scale vec3 after a measured extra at +0x48) -- engine structs.
- Measured on real maps: VERTNORMALINDICES v1 = u32 (exactly 4 B per face vertex), LEAF_AMBIENT_INDEX v1 = 2 x u32
  (8 B per leaf), PRIMITIVES v1 = 5 x u32 (20 B), PRIMINDICES v1 = u32 (sum of index counts x 4 = bytes), Strata's
  prim word = EnableShadows in bit 0, count above it (raw>>>1 sums to the prim count), LEAFWATERDATA v1 = {f32,f32,i32}.
- Game lumps: a compressed sub-lump's region ends at the next entry's offset (or the lump end when that is 0); its
  size is the LZMA header's, because maps disagree about filelen (bhop_ancientcanals: compressed length;
  bhop_adventure: uncompressed); under 17 bytes is an empty stub. Engine VBSP_LoadGameLump's rules.
- Not drawn yet: OVERLAYS v1-v3 (Strata only: every v20/v21 overlay lump is v0), WORLDLIGHTS v2 (props light
  from ambient cubes), PRIMVERTS geometry: df_elco-gbparadise's faces have no edges, only primitive vertices, and
  it draws no world (the other six df_ maps with PRIMVERTS draw each face's polygon).

## Result

- All 133 v25 maps and both odd v20/v21 maps parse. Review 1 found that "parses" is not "draws": upstream skipped a
  face with primitive vertices by a `continue` after its vertices and indices were added and before dstIndexBase
  moved, so the seven df_ maps (the library's only PRIMVERTS) drew nothing or misplaced geometry. Such a face now
  draws its polygon's fan (and a face no model lists no longer throws, df_sdc-uk_26); the review's geometry probe
  (faces drawn, displacement vertices inside their boxes, no index past the vertices) is clean on six of seven.
  Shot in Chrome (tools/shot.mjs): bhop_2006isback and bhop_ahi
  draw (textures, lightmaps, sky, props), error "" and contextLost false.
- Library census after (all 2,204 maps of the Momentum library, 23 of them over 200 MB): every map parses.
  On the way, 12 v20/v21 maps that failed before P1447 too: optional data now degrades instead of failing the map
  (a face whose primitives are not one triangle list draws its fan; a short ambient index, a detail-prop lump that
  does not parse, an empty or non-'LZMA' game lump are skipped) -- surf_bossfight, surf_healthy, surf_fiellu, surf_eon,
  surf_boogie_woogie, surf_classics3, surf_bewatermyfriend, surf_sunnyhappylove and builds.

## Speed

- The parse profile (node --cpu-prof) was 71-73% `queryAABB`: each displacement face marked the leaves under its
  MERGED surface's box (up to the whole map), with a linear ensureInList per leaf. Querying the face's own box:
  ahop_coast 11.2 -> 2.4 s, bhop_canals 22.5 -> 6.0 s, bhop_matches 7.5 -> 1.8 s, bhop_odyssey 6.9 -> 3.4 s.
  tools/pixels.mjs on bhop_dunes (run 44878), the patch against a control without it: all six views (eye and chase
  at 1/15/30 s, clock pinned) hash identically, and the control matched itself on a second run. (Every second
  page of a pixels.mjs run timed out here -- a harness quirk; the comparison is across two runs.)
- LZMA is then 82-95% on Strata maps. A flattened decoder (stubs/rustlib.ts, same bytes as Python's lzma on 8,076
  entries of 6 maps, and as the old decoder) gains ~12% (bhop_canals 6.0 -> 5.8 s, surf_leesriize 20.3 -> 17.8 s).
  CORRECTION (review 1): surf_fiellu was not a decoder bug -- its 12-byte dprp stub was sliced to the end of the file
  (the next entry's offset is 0) and the pakfile's bytes decoded as LZMA; the game-lump rule above fixed it. surf_leesriize's HDR
  lightmaps alone are 867 MB unpacked (Python's C lzma: 7.6 s for its lumps): that map stays slow.
- Download: maps are served raw from R2 (68.6 MB for bhop_canals); gzip companions exist only where they save
  (Strata maps are LZMA inside), so a first view of a big map is its download. Kept copies (Cache Storage) skip it.
- Not changed: the track route (0.75-1.7 s, 6 cached), the per-frame cost (BACKLOG's static-prop LOD and proxies).
