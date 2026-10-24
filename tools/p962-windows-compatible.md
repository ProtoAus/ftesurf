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

Build this clean cohort with existing src/build.ps1 -Jobs8 -NoDeploy. Native
8557e89af/tag patch-962, shaders and installed server/menu stay exactly as already
qualified. Check all P962 component paths byte-identical to1f442741. Controls:
real preserved old MENU, synthetic legacy seven-field row acts; old main eight-
field row rejected; this cohort publishes seven fields accepted by old MENU, plus
ready Legacy models. Synthetic probe profiles only, no owner/account/relationship
requests. Qualification and corrected dual CSQC/lno/cache hashes/UTC will be added
as a separate receipt after actual controls and destination readback. Preserve the
superseded ec394 cohort/receipts, never redate its earlier passing model checks as
social-protocol acceptance. Pi remains a separately coordinated predecessor.
