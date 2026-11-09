P1440 claimed by ftesurf-3a (Claude Code), 9 Nov 2026: Source model bodygroups and prop SetAnimation. Lex's
bhop_crash_egypt report: the crates (crate_generic.mdl, one bodypart of 16 models: whole box, 14 shatter frames,
blank) draw every model at once, and SetAnimation is not implemented. hl2 plugin mod_hl2.c tags each bodypart's
models as geomsets, the engine (gl_alias.c, model_t appended) draws the one the entity's body picks, QC sets
.body from the SetBodyGroup key and input and answers SetAnimation by sequence name. Root
C:\FTESurf-worktrees\gfxmenu-20261108-3a (engine worktree eng/).
