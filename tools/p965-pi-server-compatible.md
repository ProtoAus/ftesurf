# P965 Pi server-only compatibility composition

Base: actually deployed public P964 Pi composition adecccc5
(deploy/p964-pi-server). The prepromotion live control still has the exact P964
server (3370e260 prefix) and unchanged compatible client (552790cb prefix), with
no foreign .new files. Full byte identities belong in the build/live receipts.

Apply only reviewed P965 save module from 8a86dc3d (main merge ebbb1aff).
Whole module SHA256 cbd2d25960de53e8572d2bb120dbeec7ef675c1f12da15c5ffa45b3457531535.
All other source stays unchanged, especially the actual compatible client.
No P966 client activation/rollback, native/menu/backend/config/data/capture,
profile, format, eligibility, pin/tag, Build or release change.

Qualify existing src/build.ps1 -Jobs8 -NoDeploy. Candidate QW must equal the
reviewed main production artifact and CS must remain byte-identical to current
fleet. Existing build-Pi must use an OWNED non-live -QuakeDir sink; never either
real Windows install. Do not use PiForce, a dirty canonical tree or superseded
backend transactions. Refresh actual canonical witness, all pinned native/reader
identities and real UDP/directory emptiness at the actual boundary. Preserve
ordinary .prev plus prior history in the same verified owned task root; this is
a new feature phase, not a renamed retry of a failed transaction.

P964 receipts remain historical. Source publication/qualification do not imply
P965 deployment, general malformed-save validation, actual cold/signed/posting
or human acceptance. Final artifact/live/protected-component checks and UTC
provenance remain separate delivery requirements.
