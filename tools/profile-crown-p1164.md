# P1164 — cylindrical paper party crown

The owner envisioned a cylindrical hat with upward points, not the cone.
The same inventory item now draws an open sixteen-sided paper band and eight
upward-pointing triangular tips. The slot icon is a matching three-point crown;
the label is Paper party crown. Item2, the saved colour/equipment, account grants,
backend/schema, movement and P1163 soft aura are unchanged.

## Source and verification

Actual clean lobby source: `69fdb328a7fea9c10ee22d4e8544e183d97ef4c0`, based on
previous fleet `471fa957`. No unrelated current-main/native work was activated.
Native pin/tag and qcbuild were not changed for this client-only correction.

- `src/build.ps1 -Jobs 8 -NoDeploy` under pwsh7: no new warnings (same two existing
  client F333 argument227 warnings; server/menu clean).
- Retained dedicated-socket fixture: actual OFF and ON snapshots, same supplied
  hat colour, both items selected. Inspected screenshot shows the cylindrical
  crown and matching inventory icon; the ice aura still renders. No raw player
  identity, forged owner account or production inventory change was used.
- Owner appearance acceptance received1Nov2026: "Yep, you did it exactly
  correct!" Recorded as manual confirmation of the intended crown design in
  `lextest.md`; another player's crown remains unconfirmed. This does not accept
  aura appearance, wall occlusion, numerical performance or local VM adoption.

## Actual delivery and limits

**Lobbies deployed; both Windows client caches seeded. Local Windows VM-file
adoption remains blocked, not claimed complete.**

At the mandatory preimage check, BOTH Windows installs' programs and native
executables no longer matched the last P1163 readback. The current source/owner
was not established. Refused that overwrite before any live write; no unknown
newer cohort was replaced or restored. The two Windows gamedirs, natives and
owner configs were subsequently verified unchanged across this scoped delivery.
Future local/offline adoption requires coordination with that writer and binding
its current cohort to approved source; do not blindly copy this older lobby
server/client cohort over those files.

Independent safe delivery used the existing entrypoint:

`src/build.ps1 -Jobs 8 -QuakeDir <this-owned-source-root> -Pi -PiForce`

The supported equal SurfDir/QuakeDir branch suppresses the second native-install
copy, so this writes only the clean source gamedir and the Pi. PiForce was used
with zero players at the actual boundary. No repeated deployment/restart or new
scratch overlay was needed to bypass the failed Windows check.

Destination/runtime readback: **2026-11-01T01:44:06Z**.

| Program | SHA256 |
| --- | --- |
| csprogs.dat | `9640f764c907bc486820582e372348d8a42b6e7839a91f67c3a8f4a2a42e26cc` |
| qwprogs.dat (unchanged) | `051557d568fce88a252ad1f960598990c6d90570b8160cfe4ddf4c526fa503db` |
| menu.dat (not a lobby ship item) | `6c9f9034ea348ead9874e5224b144751d39fd03d56bebca1d595aafe7bf2d938` |

Pi pair hashes and immediate `.prev` preimages match. All12 units are healthy,
all12 directory rows fresh, all12 UDP status sockets reply. Backend remains
schema25, primary OPEN / compatibility CLOSED; no grant/schema/data restore.
Both Windows installs have an additional exact content-addressed CSQC cache
entry `e1d884ef.dat`, without replacing their local gamedir programs or touching
unrelated partial downloads. Reconnect to an official lobby to load this new
CSQC; local/offline VM adoption is the separate blocked step above.

CSQC rollback preimage:
`39518177ac12597f133f5b5547c16e68a6d73b850a8cca6700d6a572bfd6712b`.
No inventory-data restore is needed for a client cosmetic rollback.
