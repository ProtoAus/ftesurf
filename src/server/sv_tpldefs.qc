// P1425: point_template / env_entity_maker -- declarations before sv_entities.qc (ED_ParseUnknownEpair,
// CheckSpawn, SV_EntityReset and SV_ApplyInput use them); the logic is sv_template.qc.

.string tpl_rec;            // a named entity's fields as parsed, kept from CheckSpawn until SV_TplBuild
.string tpl_io;             // ...and its outputs, apart: they can outgrow saveent's 64 KB
.string tpl_names;          // point_template: its Template01-16 values, "\n"-separated
.entity tpl_proto;          // point_template: its first member prototype
.entity tpl_pnext;          // a prototype: the template's next
.string tpl_pclass, tpl_pname, tpl_pparent, tpl_pmodel;    // a prototype's own, held off the walkers
.float  tpl_n;              // point_template: its member count
.float  tpl_rawi;           // a prototype: 1 + its outputs' text in tpl_raws (spawn functions read it), 0 none
.float  tpl_fix;            // point_template: 1 its group needs Source's "&0001" name fixup, -1 not, 0 unknown
.string tpl_refs, tpl_flds; // ...the member names referred to, and the string fields that refer
.vector tpl_torg, tpl_tang; // point_template: its pose when the members were taken (matEntityToTemplate)
.float  tpl_member;         // a member of some template: leaves the map at SV_TplBuild...
.string tpl_maker;          // env_entity_maker: EntityTemplate
.float  tpl_inst;           // env_entity_maker: the instance number it last spawned
.entity tpl_cur;            // ...its first entity (Source's m_hCurrentInstance)
.vector tpl_vmin, tpl_vmax; // ...that entity's box about its origin, once (m_vecEntityMins/Maxs)
.entity tpl_blk;            // ...what last blocked HasRoomToSpawn, and where it was
.vector tpl_blkorg;
.float  tpl_instof;         // a spawned entity: its instance number
.entity tpl_chain;          // an instance's members while it is built
.entity tpl_by;             // a spawned entity: the env_entity_maker that made it

.float  tpl_fxi;            // P1432: a copy of a member the client draws from the lump (env_sprite)...
.vector tpl_morg;           // ...and that member's lump origin and name crc, which the client finds its keys by
.float  tpl_mtnc;
strbuf  tpl_lrec, tpl_lio;  // P1432: the captures of entities SV_LateStash set aside, by stash line

strbuf  tpl_raws;           // the members' outputs as the map wrote them, one per prototype
float   tpl_built;          // SV_TplBuild ran: no more capture
float   tpl_count;          // Source's g_iCurrentTemplateInstance (&0001 ... &9999)

void(entity e) SV_TplCapture;
float(entity t, string in, string pm, entity act, entity caller) SV_TplInput;
void(entity t) SV_IOOrphan;
void() SV_TplBuild;
float(entity to, float changed) SV_TplFxSend;
