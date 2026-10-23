# P948 — Kvas sky-depth composition (in progress)

Claimed after fetching both repositories and inspecting patch headings/untracked
pNNN tests through947 on23Oct2026. No native change intended. The dedicated control below requires a small CSQC
map-identity timing repair as well as the render configuration.

Root cause: the current native default2 forces finite sky-brush depth on Source
maps. At Kvas bonus4 this rejects the top of the foreground trees. Existing auto1
keeps the Source sky distant, without disabling the server's sky-mask permission.
A real ghost/freecam 2/1/2 control at one stable camera reproduces the cut, restores
the tree crowns, and reproduces the cut again. Body remains at bonus4 start,
terms0/unranked; no owner saves/config/keys or evidence semantics changed.

Plan/predictions: use the EXISTING client per-map render layer, not a global sky
setting or native fork. Kvas override1; baseline restores current native default2
on the next world. Actual automatic map-load readback must be1 on Kvas and2 on an
ordinary map. Capture the affected trees under the layer and prove next-map reset.
Do not claim Boreas, Phantasia or Epiphany fixed. Preserve unrelated render values,
server sky permissions, content and progs; dual Windows config delivery only.

Listen automatic-layer control PASS: Kvas applies1 and restores2 on Autumnal,
with full crowns visible. Real dedicated socket control ACTED but FAILS feature:
client loads CSQC and reaches the same view, yet remains2 with clipped crowns and
no per-map application. Wrapper exit0 only means its generic scenario completed.
This is preserved as a product lifecycle failure, not a passing online test.

## Implemented and verified

World-load restores the baseline immediately. CL_RenderMapFrame keeps the layer
pending until serverkey("map") is nonempty and matches the normalized native
mapname global (maps/ and .bsp stripped). It applies once per world epoch,
including same-map reload; source gates reject empty/mismatched identities.
No new command/observer/network interface or evidence/body reads. The mismatch
branch was source-reviewed, not a forged-server-key runtime claim.

The corrected CSQC's REAL dedicated test connects, logs automatic Kvas application,
reads1, and screenshots render full crowns instead of the old client's clipped
crowns. Same body at bonus4 start; camera yaw270/pitch0 at the same affected
island. Runtime draws, not wrapper counts, establish the repair. Both owned
client/server stopped and waited; port released; content links removed.

Changed-CSQC reentry Kvas/Autumnal/Kvas/same-Kvas reload reads1/2/1/1, with THREE
actual Kvas layer applications. This closes baseline leakage and a same-map
no-op arm. Original direct2/1/2 and listen pair are retained, not replaced.
Three VMs compile0warnings; LSP does not parse QC and is not that proof.

## Pending delivery

Final clean-commit artifact qualification, dual Windows progs/config delivery,
ordinary Pi progs swap/readback and a cold client remain pending. No native
rebuild/tag/pin, release or qcbuild decision. Owner Save1 acceptance is pending
in lextest.md, not inferred from the controlled views. No claim for Boreas,
Phantasia or Epiphany. No persistent personal config, keys or saves are edited.
