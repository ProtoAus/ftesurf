# P1425 claim -- ftesurf-3a, 8 Nov 2026

Lex: implement the gaps in tools/census/entgap-20261108.md. This patch: point_template and env_entity_maker
(Source point_template.cpp, TemplateEntities.cpp, env_entity_maker.cpp) -- template members leave the map at
load and spawn on ForceSpawn / ForceSpawnAtEntityOrigin, with Source's "&0001" name fixup; OnEntitySpawned.
130 maps use ForceSpawn. Server QC (new sv_tpldefs.qc / sv_template.qc, sv_entities.qc hooks).
Root C:\FTESurf-worktrees\gfxmenu-20261108-3a.
