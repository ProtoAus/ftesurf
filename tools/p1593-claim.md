# P1593 claim -- the player's exe and game folder named World of Surf (ftesurf-63, 17 Nov 2026)

Lex, 17 Nov: rename the exe and the game folder (FTESurf -> World of Surf); yes to every player downloading the
new launcher once. Names: `WorldofSurf.exe` (Linux `worldofsurf`), gamedir `worldofsurf/`, config `worldofsurf.cfg`.
REBRANDING_PLAN.md section 8 is the frame.

Why not in place: old WOS-Launcher binaries and every shipped engine refuse a feed whose `game` is not `ftesurf`,
whose exec is not `ftesurf64(.exe)` or with a path outside `ftesurf/`; the launcher does not update itself.

Stages (each its own verified delivery):
1. Engine + QC accept both identities: updater game id / exec / allowlist, the GAME switch for the updater and
   install lock, a gamedir alias so `ftesurf` and `worldofsurf` are one game (lobbies keep announcing `ftesurf`),
   map downloads into the client's own folder, cl_zones' pack test.
2. Launcher (Quakers-Launcher): new exec and feed, and a one-time move of `ftesurf/` to `worldofsurf/` (and
   `ftesurf.cfg` to `worldofsurf.cfg`) before the first start; refuses a half-moved install; identity files stay.
3. Release: the package and a new feed carry the new names; the old feed's last release tells players to fetch
   the new launcher; download page.
Not renamed: the dev trees (C:\FTESurf, C:\FTEQuake, repo `ftesurf/`), the Pi's gamedir, PROTOCOLNAME's
`FTE-Quake` token, `.ftesurf-updater/`, cvars, recording formats.

Version line (review, 17 Nov): the first worldofsurf feed is built over the live legacy feed with a higher
version (updatefeed.py enforces it), and both identities share `.ftesurf-updater/state.json`'s floor. The legacy
feed is frozen after the bridge release: no later legacy release, or the two lines would overlap. Stage 3
enforces the freeze.

Stage 2 (review 3): the folder move rewrites `.ftesurf-updater/identity` together with the move of `ftesurf/`
to `worldofsurf/`, under the install lock and crash-safe: journal the move (intent, rename, marker, done) and
resume or refuse an interrupted journal at the next start. Today establish_identity refuses any rewrite; during
the move only, it may change exactly ftesurf -> worldofsurf, never the reverse or anything else.

Stage 2 as built (Quakers-Launcher branch p1593-stage2, src/ftesurf_migrate.rs): journal intent -> renamed ->
ledger -> marked (the marker last, as the commit point); the approved feed is staged and pinned by sha256 and
version; the legacy exes are parked until the new install verifies. What stage 3 owes it:
- The worldofsurf default.fmf holds exactly one GAME "WorldofSurf", BASEGAME "worldofsurf", DISABLEHOMEDIR 1 and
  MAINCONFIG `ftesurf` or `worldofsurf`, one value per line; anything else and the launcher moves nothing, so
  updatefeed.py refuses to build such a worldofsurf feed. `worldofsurf` renames the player's ftesurf.cfg to
  worldofsurf.cfg; `ftesurf` keeps it.
- That feed ships rewritten ftesurf.sh, ftesurf.bat and ftesurf_debug.bat: no `ftesurf/` path and no
  ftesurf64(.exe), which the move deletes. Root-file names cannot change under the disk policy, only contents.
- The launcher is in no feed (managed() refuses it; the feed never updates it). Players get the stage-2 launcher
  only by downloading it: the release archives and the standalone launchers release.ps1 builds from -LauncherRoot.
  The legacy feed's last (bridge) release carries a notices/*.txt saying so; until then old launchers keep
  updating from the frozen legacy feed.
- Flip FRESH_INSTALL (ftesurf_update.rs) to WorldOfSurf in that release's launcher.
- No legacy feed at or above the first worldofsurf version, ever: an older launcher gates only on the version
  floor and would reinstall into a new ftesurf/ beside the moved install. updatefeed.py should refuse it.
- Real-launcher acceptance with the production key: a move arm in tools/test_update_launcher.py (legacy fixture,
  `--move-manifest-url` at a loopback worldofsurf feed). Stage 2 ran none.
- Engine: release the install lock after the last cfg save. QKU_Shutdown (cl_main.c:8688) unlocks before
  CL_Disconnect's CL_ClearState runs cfg_save (:2593), so a launcher that wins the lock in that gap moves the
  folder under a still-writing game. Stage 2 never moves on `--wait-for-game` and reports a recreated ftesurf/.
  Also worth it: QKU_ConfigureProfile treating the other identity's feed URL as a default (a restored old cfg
  brings back the legacy update_manifest_url), and refusing to boot when the marker and BASEGAME disagree.

INSTALL text for stage 3 (the launcher forwards only an allowlist since P1593). Replace "Engine options are
forwarded" (Linux, release.ps1 ~1555) and "To forward engine options: WOS-Launcher.exe -- -window +map
<mapname>." (Windows, ~1193) with:
    Only these start options reach the game: +map <map>, +connect <host[:port]>, -window, -fullscreen,
    -width N, -height N (ftesurf.sh also takes --debug). Names use only letters, digits and _ . : -
    Anything else is refused; set it in the game's console or settings instead. Examples:
        ./ftesurf.sh -window +map <mapname>
        WOS-Launcher.exe -- -window +map <mapname>
