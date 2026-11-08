# P1425: point_template / env_entity_maker spawn their members, as in Source (8 Nov 2026, ftesurf-3a)

Lex: implement the gaps in tools/census/entgap-20261108.md; "fps performance is very important to me, ensure
the implementation is quick". 130 maps fire ForceSpawn (819 inputs), 33 ForceSpawnAtEntityOrigin (647).

## What Source does, what this does

Source (mapentities.cpp:440-485) keeps each template member's keyvalues and removes it before it spawns
(spawnflag 1 keeps it); ForceSpawn creates copies placed relative to the template, or to an
env_entity_maker / a target for ForceSpawnAtEntityOrigin; names members aim at among themselves get "&0001"
per instance (spawnflag 2 off, TemplateEntities.cpp:200-290); OnEntitySpawned fires. bhop_4muddz's per-player
teleporters (a filter -> maker at !activator -> trigger that Kills itself) existed here from the start and
were gone after one use.

- CheckSpawn captures each named entity's parsed fields (generateentitydata; outputs apart).
- First frame, after SV_LateSpawnAll (late spawns keep their numbering) and before any target resolve:
  one prototype per member (classname "tpl_proto", its name/parent/model/class in tpl_p*, outputs built
  once by SV_EntityIOBuild), then the members leave. Templates in lump order; a removing template takes the
  entity from later ones.
- Members are TRIGGERS, POINT ENTITIES, NON-SOLID PROPS (SV_TplTakes). Kept as they were: solid members
  (SV_RecSim_Run replays movement in a fresh map's physics world that has no runtime copies -- a solid
  copy would read as a physents fault), parented members and movers (follower/rider chains are built once),
  csprogs effects drawn from their wire.
- ForceSpawn: copyentity of each prototype and its output edicts, fixup, the class's spawn function
  (callfunction) with the member's real output text, brush render state, OnJump chain.
- env_entity_maker: AutoSpawn (first spawn at Activate, then CheckSpawnThink every 0.5 s: WaitForDestruction,
  HasRoomToSpawn always, IsPlayerLooking dot > 0 unless IgnoreFacing), ForceSpawn with flags 8/16,
  ForceSpawnAtEntityOrigin (!activator / !caller / !self folded). Live copies capped at 64 entities a maker
  (surf_classics3's func_movelinear cannot run here and so never Kills its copies).
- Kill (any entity): its output edicts leave after their delayed fires, unowned (SV_IOOrphan); the
  entity leaves the OnJump chain. Before, a Kill left them, and a template's Kill/ForceSpawn cycle grew edicts.
- SV_FindByName honours a trailing '*' (Source NamesMatch): 1,208 outputs on 54 maps (4muddz's
  "teleporter_1*" FireUser1).
- Client (cl_tplskip.qc): trigger prediction skips members the server takes out (surf_globalchaos'
  teleporter_07 x5 and teleporter_knife waited for a button / 120 s and were predicted from load).
- `cmd ent_named <name>` (sv_cheats): what carries a name, with edict, class, model, solid, origin.

## Measured (task root artifacts/p1425arm.py; hosted game, rig.lock)

- bhop_4muddz, ABAB against a control (main + ent_named only): control teleporter_1 present at load (#15),
  ForceSpawn adds nothing; P1425 absent at load, ForceSpawn x2 -> 2 copies, FireUser1 -> its OnUser1 Kill
  after 4 s -> 0, Kill by name -> 0; maker ForceSpawnAtEntityOrigin !Activator at the player -> one copy at
  the player (-15000 15000 283), the wildcard OnEntitySpawned FireUser1 kills it 4 s later.
- Edicts: nine Kill-then-ForceSpawn cycles reuse edict #1260 (the first cut leaked 5 a cycle).
- bhop_crash_egypt fruit: the trigger's outputs name all three members, so all three carry &0001, &0002.
- surf_globalchaos: server members absent at load; client trig_dump 21 -> 15 predicted teleports.
- Cost: build at the first frame under 1 ms on bhop_4muddz (61 ms before the captured-name prefilter).
  An instance: 0.4-0.6 ms for one trigger, 1.5-1.8 ms for crash_egypt's three entities; the engine's
  edict allocation is 70 us per spawn() (a linear scan of all edicts, qclib ED_Alloc) and dominates --
  re-parsing per instance and copying a prototype cost the same. Nothing runs per frame. An ED_Alloc
  start hint (engine) would cut every spawn, delayed outputs included; proposed separately.

## Reviews

Round 1 (two reviewers, code only: control flow; consequences): AutoSpawn stacking, Kill leaking output
edicts, the "outputs" marker breaking SV_SpRawSelfOnly/path_track, IsPlayerLooking, members of two templates,
!caller, filter members stashed into the next map, OnJump, client prediction of removed triggers, solid
copies vs SV_RecSim_Run, rotator riders, numbering -- all fixed in b4d5b065 (above). Kept: a member a class's
own spawn function removes (CS weapons) still counts for OnEntitySpawned, as Source's CreateInstance does.
Round 2: see below.

## Not done

- Freeze of solid members to runtime copies (kept static, see above); templates of movers stay static.
- The client draws lump effects (sprites, sprite trails) of template members from load; b8's effect walkers
  take Tpl_ClMember next (P1426/P1430).
