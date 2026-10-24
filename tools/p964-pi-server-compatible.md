# P964 Pi server-only compatibility composition

Base public 7ebaca8b147509f6b4be6d602e115356ba544141 reproduces BOTH actual Pi
predecessors byte-exact: QW236d6933b04d102e95f7710b3e44671c0cb4036b55e5becd3690ebefb36bbbd9,
CS552790cb72146352994e5fb192eab01cf9ef7978e2f7d9882485430c66c6c457.
Its server/shared/source order is identical to inspected task base1f442741.

Transfer ONLY reviewed P964 src/server/sv_saveloc.qc from published a6531a56.
Whole-module SHA256 must be 3c29f7b55ba783a0825b611661ad3e0c8f4f903f9ba73dd80507f7b1bf9585b6.
CSQC must remain byte-identical to the actual current predecessor; MENU, native,
backend, reader, config and player data are outside this promotion. No new
format, capture field, ranking policy, native pin/tag, Build or release.

Use existing src/build.ps1 -Jobs8 -NoDeploy for qualification. An eventual
build.ps1 -Pi must name an OWNED non-live -QuakeDir output sink, since the
script's primary output is already this isolated source root. This prevents
incidental Windows MENU/CSQC deployment. Do not run from a dirty canonical tree.
Normal atomic staged-hash/.prev/positively-empty-current-fleet/restart checks
remain mandatory, with no -PiForce. The pair promotes only a new server: client
bytes are identical. The actual serving backend witness pins eight native/reader
inputs, none progs; all those identities remain protected unchanged. No backend
apply/reinitialization or historical one-shot transaction is being reused.

Qualification, fresh occupancy and actual promotion/provenance are separate
receipts; this source statement alone does not claim deployment or human,
signed recording, cold-replay, ghost or HUD acceptance. Windows server source
has its own separately qualified/published composition and is not replaced by
this branch's broader social-presence source.
