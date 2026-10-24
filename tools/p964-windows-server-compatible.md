# P964 Windows server-only compatibility cohort

Base: inspected public c31ebc973d3bf737aa072c46d3b8ce3ffce065ce. Its unchanged
server builds byte-exactly to BOTH installed Windows SSQC predecessors
27029d86f5af7166303e055d37e095d1ccb064f64386230c6d86655b6a8d1124.
The P957 control was a different older server, not a matching predecessor; no
install was touched to make that control pass.

Apply ONLY the already-reviewed P964 src/server/sv_saveloc.qc module from
published a6531a56d95066f87ec35fd5118fa8bfdfd7d985. The complete module must
hash 3c29f7b55ba783a0825b611661ad3e0c8f4f903f9ba73dd80507f7b1bf9585b6.
The restore, timer and caller source is otherwise identical to that reviewed
cohort; the sole server difference between this base and the current Pi/main
cohort is the preserved pre-P961 social-presence implementation.

This is a deployment composition, NOT a new product patch, native pin/tag,
Build or release. No P961/P963 server/menu/native activation. Keep the actual
installed compatible CSQC, MENU, native images, shaders, config and player data.
Do not deploy this branch's old client/menu/tools or use a default all-VM build
against a live install. Compile with existing src/build.ps1 -Jobs8 -NoDeploy;
only qualified qwprogs.dat and its matching debug metadata may be promoted to
BOTH Windows installs, with exact predecessor/protected-component checks and
ordinary .prev preservation. Deployment receipts are separate from this source
statement. Pi has a distinct byte-exact baseline and is not covered by this
Windows source composition.
