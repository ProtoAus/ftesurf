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
