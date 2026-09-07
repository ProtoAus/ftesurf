/*
===========================================================================
  sh_json.qc -- FTE's JSON parser, declared by hand.

  FTE has exposed a full JSON reader to QuakeC since 2022 -- to BOTH modules,
  SSQC (pr_cmds.c:11690-11702) and CSQC (pr_csqc.c:6937-6945), implemented in
  common/pr_bgcmd.c:784-920.  The defs dumps in src/defs/ predate it, and
  regenerating 158 KB of dumped platform defs to pick up seven builtins is a
  worse trade than declaring them here.

  They are all NAME-RESOLVED extension builtins (#0:name), which is how FTE
  ships anything that has no fixed number.  If the engine lacks one the QC
  still loads and the call is simply a no-op returning 0 -- which, given the
  handle rules below, degrades to "this map has no zones" rather than a crash.

  TWO PROPERTIES THIS CODE RELIES ON DELIBERATELY
  -----------------------------------------------
  1. HANDLE 0 IS A VALID NULL NODE.  Every accessor runs its argument through
     JSONFromQC (pr_bgcmd.c:699-700), which maps 0 to a static `json_null`
     node.  Reading a length from it gives 0, a child gives 0, a float gives
     0.  So a walk down a path that does not exist needs no null checks at any
     level -- it just produces 0 at the end.  The zone parser below is written
     to exploit that, and is much shorter for it.

  2. STRINGS ARE REFERENCE-TRACKED TEMPSTRINGS.  PF_json_parse is built with
     JSON_PERSIST_STRINGDATA and the engine has FTE_QC_PERSISTENTTEMPSTRINGS,
     so a string pulled out of a node stays valid without strzone().

  json_free maps to PF_memfree and MUST only be called on the root node.
===========================================================================
*/

int(string jsontext)      json_parse              = #0:json_parse;
void(int node)            json_free               = #0:json_free;
int(int node)             json_get_length         = #0:json_get_length;
int(int node, int idx)    json_get_child_at_index = #0:json_get_child_at_index;
int(int node, string key) json_find_object_child  = #0:json_find_object_child;
float(int node)           json_get_float          = #0:json_get_float;
string(int node)          json_get_string         = #0:json_get_string;
