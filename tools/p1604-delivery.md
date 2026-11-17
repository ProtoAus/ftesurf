# Patch 1604 delivery -- LIVE on the 12 lobbies (18 Nov 2026, Claude Code worldofsurf-0e/-43, on Lex's "do it")

## Lobby server engine: patch-1568 -> patch-1604 (21:34:17Z)

- Built on the Pi in /srv/nvme/agent-work/eng1604-20261117T1912-0e from a git-blob tar of engine fe1ebfa3c (773 files, each
  checked against its git blob id), `sv-rel` and `plugins-rel NATIVE_PLUGINS=hl2`, FTE_TARGET=linux BITS=arm64, -j2,
  stamp git-8853-patch-1604-0-gfe1ebfa3c. fteqw-svarm64 189b33d55b8ad7ce..., fteplug_hl2_arm64.so efc72330db345878...
- It carries every engine patch since 1568 to the lobbies for the first time: 1571, 1572, 1576 (no server effect), 1581
  (pm_verify's content-skew hint), 1587, 1589, 1591, 1592, 1593, 1598, 1602 (client), 1604. Lobbies set no
  sv_movementprofile, so 1589/1591's client gates (GoldSrc/newer profiles only) do not apply.
- Gate, the live binary vs the new one through link overlays (ports 27791/27792), artifacts kept in the Pi root's gate/:
  pm_dettest on bhop_eazy, surf_ace, surf_boreas, surf_pantheon, surf_axil and surf_sedona (90 lines) and pm_verify of
  the 12 newest lobby runs on 12 maps (10 PASS, 1 HOLD, 1 REFUSE for a segmented run): 114 lines, identical. New only:
  surf_1969's hl2_sprpmiss names the 6 TF2 models the lobby logs name; a surf_fiellu run with one sample nudged and a
  `propmiss` header HOLDs on both, and only the new binary adds "lobby lacked 2 prop model file(s): ... (may be content
  skew)".
- Swap: .new copies hash-checked, lobby_announce warning on 12 ports, 10 s, `mv -f`, ftesurf@1..12 restarted one at a time
  (0 players). Readback: 12/12 new exe inode, plugin mapped (no deleted mapping), 0 restarts, 12 directory rows; lobby 6 on
  surf_1969 logged "6 solid static prop model file(s) are missing here". The sweeper's next ticks (21:35, 21:40) ran as before.
- Rollback: `cp -p fteqw-svarm64.pre1604-20261117T213417Z fteqw-svarm64.rb && mv -f fteqw-svarm64.rb fteqw-svarm64` and the
  same for fteplug_hl2_arm64.so, then restart every unit. Not below 889 (AGENT_NOTES, Pi engine paragraph).

## Lobby QC: qwprogs e911e974 (P1603, c6c9fe17) -> 3495dc51 (main 679da9d6) (21:41:25Z)

- The only source change since the live progs is P1604's three commits (9a4d61d4, b03ca407, eb9189c9); csprogs unchanged
  (6495ce80, checked on the Pi before the swap), so the pair agrees. Built by wos-build.sh from main 679da9d6, fteqcc 0 warnings.
- Swap: qwprogs.dat.new hash-checked, warning, 10 s, live copy kept as qwprogs.dat.pre1604-20261117T214125Z, `mv -f`, 12
  restarts. lex-90's qwprogs.dat.prev / csprogs.dat.prev (21ff074b / 83467981, the P1603 rollback) left as they were.
- Readback: every lobby's props line says "static props checked"; lobby 6 on surf_1969: "7 solid with a missing model file
  ... static props checked (6 missing)" (the TF2 entity prop P1581 found plus the six static ones). 12/12 active, 0 restarts.
- Rollback: `cp -p qwprogs.dat.pre1604-20261117T214125Z qwprogs.dat.rb && mv -f qwprogs.dat.rb qwprogs.dat`, restart all.

## Still pending

- The Pi's reccheck (8ab35f6d, gen1603) does not know `propstatic`: it notes "header key 'propstatic' is not part of v14" on
  new lobby runs until the next generation pins 059246f0... (backend-pending.md).
- P1603 step 3 (Lex's real Linux run, then sv_rank_linux 1) is unchanged by this delivery; it now runs on patch-1604.
