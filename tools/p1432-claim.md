P1432 claimed by ftesurf-3a (Claude Code), 9 Nov 2026: point_template members that the client draws from the
lump (info_particle_system 13 on 10 maps, env_sprite 23 on 7, point_spotlight 1) -- not drawn where the
template holds them, drawn where ForceSpawn / an env_entity_maker puts each copy, until it is killed. Server:
the stash keeps the template capture (SV_LateStash, CheckSpawn); client: the effect walkers skip members and
draw instances from a wire. Root C:\FTESurf-worktrees\gfxmenu-20261108-3a (qc4).
