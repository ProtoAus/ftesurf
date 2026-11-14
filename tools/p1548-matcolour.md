# P1548 -- a missing texture draws its colour, not pink/black

Owner: ftesurf-e7 (Claude Code), 14 Nov 2026. Task root C:/FTESurf-worktrees/matcolour-20261114 (OWNER.md).
Engine 3eb32bafd, 13feed820, 1b1a4fd11, f7a07fe9a on ftequakers main, tag patch-1548. Game: tools/matcolours.py,
tools/test_matcolours.py, the release entry; ftesurf/data/matcolours.txt is tool output (gitignored like
mapmeta.txt), placed on the build box and shipped by the release.

## Report

Lex (14 Nov): "replace the pinkblack missing material texture when we have the colour data ... some sort
of index for all of the textures ... shade that surface that colour, with lightmap ... other things we
could do for when people don't have the Assets?" Then: "we're not doing the water? why not?"

P1191 (0.1.35) already drew a world material with NO VMT in the map's own dtexdata reflectivity. Left:
a VMT whose image is missing, model materials (no dtexdata), 0x0 texdata, water -- and, found here, the
sky after a map change.

## Change

- Colour index: tools/matcolours.py reads the games fs_addons.default.txt mounts (Momentum loose +
  bundled HL2, CS:S, HL2, episodes, TF2, Portal, CS:GO) in that precedence: per material the base
  texture's VTF reflectivity (else its DXT1 thumbnail) as sRGB, the $color tint separately, flags
  (translucent, alphatest, additive, Water = $fogcolor, unlit, sprite, Refract, decal). Cosmetics,
  weapon skins, UI art and names with whitespace are skipped. 24,919 lines, 1 MB, sorted for the
  plugin's binary search (tools/test_matcolours.py checks it).
- hl2 plugin (mat_vmt.c): a VMT whose $basetexture is not installed draws that colour through its own
  class times its $color (the map's reflectivity first, then the index), linear in the lightmapped
  classes (P1288's pow(COLOR, 1/2.2)) and gamma in the rest; decals, sprites and additive glows draw
  nothing; alpha-tested and translucent ones half see-through; $selfillum/$basealphaenvmapmask dropped.
  A material with no VMT that the index lists -- world textures and models/ only -- draws vertex-lit,
  unlit, or lightmapped (a world texture with 0x0 texdata); a world water texture with no VMT draws a
  see-through plane of its fog colour. mod_vbsp.c hands each world texture's reflectivity over before
  its shader loads. `hl2_missingtint 0` restores the checker.
- Engine (gl_warp.c R_TouchForcedSky, from Shader_TouchTextures): the sky in use's box faces are marked
  used each map. A sky shader kept from an earlier map (r_skybox_default, when a second map's own sky
  is missing too) had its faces freed by Image_Purge and drew the missing image across the whole sky.

## Measured (rig on the PC)

shots.py (task root): the exe and plugin under test copied beside the install's DLLs (plugins load from
the exe's folder first), content -basedir C:/FTESurf, a private -homedir, spawn-view screenshots.
Profiles: `momonly` = an fs_addons.txt with only Momentum (where the map library lives), fs_automount 0
-- a player without CS:S/TF2; `all` = the install's own.

- All games mounted, surf_utopia/beginner/aqua/bhop_eazy/heaven: the new plugin takes 0 colour actions
  and draws 0 checker pixels, as the installed one -- nothing changes for a player who has the assets.
- Water, momonly, surf_aqua (camera above liquids/inferno_water): installed build a purple/black checker
  floor; P1548 a see-through teal plane with the pool floor showing through.
- Sky, momonly, surf_utopia then bhop_eazy: installed exe 269,837 / 208,969 / 269,682 magenta pixels of
  sky in three runs (bhop_eazy alone: 0); P1548 exe 0, the default sky drawn.
- Momentum only, 16 maps (every 40th surf_ map, two clients of 8), after the review fixes: 40 VMTs with
  a missing image coloured -- mostly map-packed props textured from CS:S (housegamer huts, doors,
  norramp ramps, chateau/piranesi wood) plus dev/ and glass world materials -- 12 water planes, no
  crash. Installed build on the same 8 maps as control: surf_2012_beta12's distant lavender checker
  block draws in the wall colour; surf_calamity2's 213k changed pixels are the spawn camera's height,
  not a material.
- The stamped install build (exe 8aec53e8): sky case 0 magenta (sky region 123,129,137 against the
  control's 247,2,248), all games 0 colour actions; one git-8745 stamp (16 hits); check_tls_refptr
  10 thread-local symbols, 0 plain-address uses.
- Props: with a game missing, a prop's MDL is usually missing too and nothing draws at all; the colour
  path covers a model whose MDL is packed but whose material is not.

The magenta count (r>150, b>150, g<90) misses the tinted checker -- surf_aqua's purple one scored 0 --
so the "no change with all games" claim rests on the 0 colour actions, not on it.

Not measured: the particle case (Momentum ships HL2's particles, so it never occurred: read, not run);
the lightmapped gamma on screen (by construction against P1288); maps beyond the 21; the release build.

## Review

One independent reviewer (code, not conclusions). No crash or memory finding; checked the loader on
CRLF/empty/garbled input, key lengths against MAX_QPATH, the hash table bound, main-thread use, and
VMT_OwnImageExists against image.c's search. Fixed in 1b1a4fd11:
1. Lightmapped classes drew about a gamma step too bright (sRGB written where P1288 reads linear).
2. The no-VMT path took particle textures (p_script.c registers them by name expecting no material;
   233 of 402 are in the index): now world textures and models/ only, and an image under the
   material's own name wins.
3. Every visited sky's faces were kept all session: now only forcedsky's.
Also: $selfillum/env-from-base dropped on coloured VMTs, Refract half see-through, the help text, the
unused counter, whitespace keys. Left: a model sharing a world texture's name keeps the checker; WVT's
missing $basetexture2 still blends the checker; UnlitGeneric with $vertexcolor ignores the colour; the
map colour table survives into a non-VBSP map's prop lookups. Rendering only, not ranked: one round.

## Delivery

INSTALLED 14 Nov ~16:50 local: both installs exe 8aec53e8 (git-8745-patch-1548-0-gf7a07fe9a; .prev be8b03d4
P1543), fteplug_hl2 ff27c190 (.prev 79dda36a), ui_imgui ef9dbd1d; C:\FTEQuake also cod 92925284, box3d
1e131cec, ode 49fc0c84 (same build). fteqwsv64 not rebuilt (no server code changed). The exe links the
0.1.45 build's static libs (engine/libs-x86_64-w64-mingw32 copied from release0145-16), as the release
does; the P1543 install had linked msys2's DLLs. matcolours.txt
dd216825 in both installs' ftesurf/data. Client only: nothing for the lobbies. Players get it with the
next release (release.ps1 ships the index).
