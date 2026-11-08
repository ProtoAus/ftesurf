// P1425: point_template / env_entity_maker -- declarations before sv_entities.qc (ED_ParseUnknownEpair,
// CheckSpawn, SV_EntityReset and SV_ApplyInput use them); the logic is sv_template.qc.

.string tpl_rec;            // a named entity's fields as parsed, kept from CheckSpawn until SV_TplBuild
.string tpl_io;             // ...and its outputs, apart: they can outgrow saveent's 64 KB
.string tpl_names;          // point_template: its Template01-16 values, "\n"-separated
.entity tpl_proto;          // point_template: its first member prototype
.entity tpl_pnext;          // a prototype: the template's next
.string tpl_pclass, tpl_pname, tpl_pparent, tpl_pmodel;    // a prototype's own, held off the walkers
.float  tpl_n;              // point_template: its member count
.float  tpl_hadio;          // a prototype: its member had outputs (spawn functions test .vbsp_io_raw)
.float  tpl_fix;            // point_template: 1 its group needs Source's "&0001" name fixup, -1 not, 0 unknown
.string tpl_refs, tpl_flds; // ...the member names referred to, and the string fields that refer
.vector tpl_torg, tpl_tang; // point_template: its pose when the members were taken (matEntityToTemplate)
.float  tpl_member;         // a member of some template: leaves the map at SV_TplBuild...
.float  tpl_keep;           // ...unless a template naming it sets "Don't remove template entities"
.string tpl_maker;          // env_entity_maker: EntityTemplate
.float  tpl_inst;           // env_entity_maker: the instance number it last spawned
.float  tpl_instof;         // a spawned entity: its instance number
.entity tpl_chain;          // an instance's members while it is built

float   tpl_built;          // SV_TplBuild ran: no more capture
float   tpl_count;          // Source's g_iCurrentTemplateInstance (&0001 ... &9999)

void(entity e) SV_TplCapture;
float(entity t, string in, string pm, entity act) SV_TplInput;
void() SV_TplBuild;
