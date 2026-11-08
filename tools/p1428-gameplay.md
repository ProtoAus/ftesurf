# P1428: trigger_look, game_ui, breakable health, prop skins (8 Nov 2026, ftesurf-3a)

From tools/census/entgap-20261108.md (Lex: "I would like to have all of these taken care of"). Server QC,
src/server/sv_gameui.qc. Nothing runs per frame unless a player is inside a look trigger or holds a game_ui.

- trigger_look (21 maps, 38 brushes; triggers.cpp CTriggerLook): trigger_multiple's set-up, its own touch.
  While a player touches it and looks within FieldOfView (dot) of its target -- or moves that way with
  spawnflag 256 -- for LookTime seconds, OnTrigger fires (with the player as activator) and the count
  restarts; Timeout seconds after a visit starts, OnTimeout fires once. Spawnflag 128 fires once per player
  (Patch 270's trigger_once rule; vbsp_mp is on offline too), out of the touch masks. A visit ends when touches
  stop for 0.1 s.
- game_ui (20 maps; game_ui.cpp CGameUI): Activate (activator, or a named player) / Deactivate; while held, a
  think each frame fires Pressed* / Unpressed* for the four move keys and both attacks, and XAxis / YAxis /
  AttackAxis / Attack2Axis as values when they change; PlayerOn / PlayerOff; it lets go when FieldOfView is
  left, the player dies, or a new +use / +jump with spawnflags 128 / 256. Its outputs are not "On" keys, so
  ED_ParseUnknownEpair now takes those 18 names as outputs too.
  NOT done: spawnflag 32, freezing the player (24 of the 26 set it). The movement has no predicted
  "commands ignored" state, and the run system's pin (MOVETYPE_NONE) means a held save or a replay.
- func_breakable SetHealth / AddHealth / RemoveHealth (13 maps): func_break.cpp UpdateHealth -- signed, only on
  a change, OnHealthChanged, at or below 0 it breaks. On players Momentum has no damage; not done.
- prop_* Skin (25 maps): sets the skin; csprogs riders resend on the input.
- game_score ApplyScore: skipped -- it adds to a score this game does not show.

## Measured (artifacts/p1428_look.txt, hosted game, developer 1 prints of the subject's own fires)

- bhop_4muddz look trigger *187 (FieldOfView 0.95, LookTime 0.5, target target1): standing in it facing
  away for 2 s -> no fire, the player keeps his name; facing target1 -> "OnTrigger after 0.5 s looking",
  repeating every 0.5 s while looking (Source's Trigger resets the count; flag 128 unset), and the map's
  output renamed the player filtername2 (cmd ent_named filtername2 lists him).
- bhop_vixen game_ui g0_p1: Activate -> PlayerOn; +moveleft -> PressedMoveLeft, XAxis -1; release ->
  UnpressedMoveLeft, XAxis 0; +attack -> PressedAttack.
- bhop_vixen again (final build): `cmd ent_io` delivered inputs 37 before Activate, 63 after PlayerOn, 133 after the
  key presses, and Deactivate fires PlayerOff and the four axes at 0.

## Review

One reviewer, code only. Fixed (7698c5f8): a disconnected holder kept a game_ui (QW progs keep the edict;
clienttype now), fires after an output deactivated it mid-think, fire-once look triggers left in the touch
masks (early OnEndTouch), UpdateHealth's sign / change guard / OnHealthChanged. Noted, as Source: one look
timer per trigger, so two players in one look trigger share it.

## Delivery

LIVE with P1425 (tools/p1425-templates.md, Delivery): lobbies + both installs, qw 53744f28 / cs 190d9980.
