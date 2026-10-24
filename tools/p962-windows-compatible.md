# P962 Windows client compatibility cohort

Base inspected4481a663, same P962 feature code as qualified1f442741. Restore ONLY
src/client/cl_friends.qc and cl_menu_friends.qc from inspected pre-P961
c31ebc973d3bf737aa072c46d3b8ce3ffce065ce. Retain all P962 component bytes and
already-approved P954/P958 Windows client features. No server/shared/menu/backend
source or native artifact changes. This source composition is an explicit clean
cohort, not a new product patch or a backwards merge over public main.

Reason: P961's CSQC publishes an eighth Friends snapshot field. The preserved
old MENU reader accepts exactly six/seven fields, so the earlier main-CSQC/old-
MENU delivery can drop its connected Friends snapshot despite passing viewmodel
checks. Native/MENU/backend P961 is not to be activated incidentally; do not ship
a mixed protocol pair, and do not roll Windows back to the older Pi/P957 client
(which lacks already-approved Windows client work). Main's full P961 source is
valid only with its matching delivery dependencies; it is not being rewritten.

Qualified artifact source7ebaca8b147509f6b4be6d602e115356ba544141: clean existing
src/build.ps1 -Jobs8 -NoDeploy,3VMs/0warnings. Relative to1f442741 ONLY the two
Friends CSQC components differ; both equal c31ebc973d exactly. Native8557e89af/
tag patch-962, shaders, installed server/MENU remain unchanged and qualified.

Actual identical preserved MENU in both installs: main eight-field publication
produced1/drew0. This cohort's real empty publication produces0/draws0; its real
seven-field row produces1/draws1. Talon/glove48/layer117/@lookat01 ready with no
QC/shader errors. Synthetic local probe profiles only: no owner/account/relationship
request, no claim of P961 presence, real-account or backend acceptance. An initial
GameCommand transport attempt and a wrongly quoted manual cvar setter were NOT
passes; use the real seven-field producer as acting control. The cvar-display
parser was corrected for escaped quotes and trailing default metadata.

Dual Windows correction read back2026-10-24T08:44:44Z, ONLY CSQC/lno/new cache
(six logical targets); no game running or owner process stopped at that boundary:
- CSQC/cache145a7654.dat:552790cb72146352994e5fb192eab01cf9ef7978e2f7d9882485430c66c6c457
- LNO:7d18b9bee2d73f0e1ba4db0ae636a82ec982fe208e6e4b15ed737ad933b5e1e7
1315protected hashes and last-GOOD.prev are unchanged. Superseded ec394 source/
bytes/receipts and prior predecessor history are preserved, not redated or called
social acceptance; the old content-addressed cache is retained. Synthetic fixture
menu cache restored, owned actors stopped, complete NoDeploy output retired only
after qualified copies/manifests captured. Main tools/p962-knife-workshop.md is the
overall native/source/delivery receipt; Pi remains separately coordinated. This
later documentation commit does not change or rebuild qualified7ebaca8b bytes.
