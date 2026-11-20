// Patch 1655: GoldSrc (BSP v30) map entities -- the gate and the names sv_entities.qc's hooks call.
// The logic is sv_goldsrc.qc, which no Source map reaches: every caller tests GS_Map() first.

// The engine answers from the loaded world model (pr_cmds.c PF_cvar), so it is valid while the
// lump is parsed and spawned.  1 on a Half-Life BSP, 0 on VBSP.
float() GS_Map = { return cvar("halflifebsp"); };

float() GS_Spawn;                               // CheckSpawn: TRUE when it took the entity
float(string key, string value) GS_UnknownKey;  // ED_ParseUnknownEpair: TRUE when the key was kept
void() GS_MapStart;                             // SV_EntityIOBuild: the lump is built
void(entity pl) GS_PlayerUse;                   // SV_UseFrame: the +use edge
void(entity t, entity att, float dmg) GS_Damage;    // SV_EntityDamageInner: the shot hit t

// Keys GoldSrc maps write that no QC field is named after (so Source parsing stays as it was).
.string gs_master;          // "master": a multisource that gates this entity
.string gs_killtarget;
.string gs_gstate;          // "globalstate"
.string gs_newtarget;       // trigger_changetarget's "m_iszNewTarget"
.string gs_raw;             // every other unknown key, "key\tvalue\n": a multi_manager's targets
.float  gs_delay;
.float  gs_dmg;
.float  gs_ut;              // "triggerstate" as a use type; absent is off, as the game's zeroed member
.float  gs_tmode;           // env_global "triggermode"
.float  gs_istate;          // env_global "initialstate"
.float  gs_mat;             // func_breakable "material"
.float  gs_kind;            // GS_K_*: which GoldSrc class this entity runs as; 0 is none of them
