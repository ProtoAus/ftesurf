# P1366 — comparison bars, held-save travel and segmented local bests

Owner: pi.dev, 7 Nov 2026 UTC. Reserved after fetching both repositories and inspecting
patch headings plus untracked pNNN files; highest existing claim1365. Delivery is
recorded below separately from implementation and testing.

## Change

- `hud_compare_graph 1` adds center-zero bars to the existing comparison HUD.
  `hud_compare_sync 1` samples the displayed reference at the player's elapsed leg
  time; `hud_compare_point 1` retains nearest-route-point comparisons and the time
  gap. Both preserve numeric deltas, unavailable states and discontinuity guards.
- `cl_sl_leadin` controls0..2seconds of render-only travel into an acknowledged held
  save (existing preference retained;0 disables). Copy at most512consecutive rows
  from that slot's own local picture; shorten dense windows rather than dropping
  break markers. Missing pictures use the ordinary held position, not a failed line.
- A bounded pending snapshot waits for the actual hold and one seq/slot-bound loaded
  endpoint in stat117. Publish queued saved stance rather than stale movement flags.
  Keep the HUD on captured body feet, preserve queued prediction guards, and release
  only this hold's temporary visibility eye on cancellation, expiry or teardown.
- Store segmented local-best receipts independently from clean PBs. Class and
  certification remain independent for selection/pruning/rank; only clean certified
  results update the clean lobby PB. Receipts remain metadata with samples0, not
  movement evidence or ownership credentials.

## Verified

- Full product source independently reviewed in two lenses, with focused confirmation
  of the final queued-posture correction. No remaining source finding.
- Actual dedicated socket and installed native client/server:26 assertions, zero
  failures, plus real loaded-endpoint publication. Both graph sections inspected in
  the captured PNG. Assertions cover distinct same-time/closest sampling, no
  extrapolation or break interpolation, class/certification/prune/rank independence,
 512consecutive rows, late teleport/final-span correction, sampled/final stance,
  delayed/mismatched endpoint ownership, copied-source isolation and unpredicted HUD.
- Initial native setup/control failures were retained: missing output parent, missing
  raw-map suffix, unnormalized test command, missing held slot and incorrect rank
  denominator expectation. The corrected real helper controls ACTED; a successful
  process exit or a silent control was never treated as product acceptance.
- Reader regression949checks/0failed; unchanged reader on554REC/178VIEW, including10
  standalone views, retains351pre-existing faulty files (352fault messages).

## Deliberate exclusions and acceptance limits

The independently developed historical streamed-recorder repair is NOT included:
existing rewind arena and historical state writer remain byte-identical to the
public base. No native source/pin/tag, QC Build, recording grammar, physics, public
credit policy, backend or player-data change. No claim to fix the reported Fiellu
cursor placement or zero-clock problem, or to recover missing old cold-cut duration.
Those remain separate falsifiers/work. Synthetic helper checks do not prove natural
travel feel, arbitrary UI cursor fidelity or all network-delay cases. Owner acceptance
for one ordinary held save and graph readability is pending in lextest.md.

## Delivery

Installed and live-verified7Nov2026 09:52:30UTC. Source3414778fcddf9c24961c01676037a83bed1a319e;
engine documentationaea48d6b481746fd93e2d6035d3dfe875afcda9a. Both inspected SHAs
pushed to main. Clean commit built all3VMs/0warnings; production-entry rebuild was
byte-identical to the frozen artifacts. No native binaries were changed.

Both Windows installs have all6matching DAT/LNO hashes; protected owner cfg/native
bytes are unchanged. Pi used build.ps1 -Pi with the default10second warning, no force,
and all12restarts succeeded. Destination SHA256:

- qwprogs.dat:1eb112596714dd57ad3d5a7ece319e318229de91e431f224833700ec30efef93
- csprogs.dat:11b419936cb5255c8a86f599c576e26123e0281c3b03d8a9bf06e3292633db57

All12active services reappear in the directory. Full live serverinfo on EVERY lobby
advertises fs_savelead1 and the exact client folded-MD4 0x14cd41a1 / size0x720cd6.
The ordinary QW status packet truncates these trailing keys; its omission is not a
runtime absence, so the final proof used the existing bounded loopback rcon client.
The previous Pi pair is preserved as .prev and matches the preflight hashes. No
backend generation swap or release was needed. Human visual/feel acceptance remains
pending; the excluded historical recorder/cursor/clock work is NOT deployed.
