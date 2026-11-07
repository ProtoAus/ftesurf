# P1358: exact static-prop cube reuse

Engine `76876c82061be6a66840d61f4b6f16c239ebd31b`, tag `patch-1358`.
Client-native only; contains the previously delivered1357 empty-grid guard.
No lighting formula, ray/quality, renderer interface, physics, VM or Build change.
Claimed after both repository fetches and patch-heading/untracked-pNNN census;
max1357. Source/build/delivery are separate claims below.

## Confirmed cause and selected fix

Ceaseless's first-traversal PrepareFrame hitch is exact static-prop lighting:
a new231.444ms capture spent231.307ms in22 newly visible solves. Setup/PVS/world
costs are negligible. Off and forced-positive phase controls acted; repeated
route has no matching>=8ms stall. Earlier source-bound same-frame capture had
245.682ms PrepareFrame inside a249.052ms total frame; these are separate events.

The model-lighting caller solves the same raw ambient cube twice: once for the
level/direction and again for light_cube. The fix optionally returns the first
raw cube BEFORE encoding/folding/flooring. Reuse only for native VBSP lighting
with exact visibility and no baked-light suppression. Dynamic/approximate,
baked/suppressed, other callbacks and missing state keep the original paths.
No global last-sample memo or cached approximate answer. Ordinary Values remains
a wrapper with no cube output. Default hl2_lt_reusecube1;0 is the original
second-query control. A toggle invalidates the existing prop-light cache.

## Functional controls and source bridge

Prototype native72 raw-cube comparisons at72 unique sample points match the
original independent Cube query BIT FOR BIT, with exact1/suppress0 witnesses.
This is not screenshot/owner acceptance or universal map coverage. Actual caller
C controls cover64 eligibility/output combinations including baked/dynamic,
foreign callbacks, missing state, disabled/null controls; all4 gate/never-act
mutants fail at runtime. The producer is checked natively, not replaced with the
caller's stubbed unit-test producer. Clean source reruns the64/4 controls.

Clean selected caller and ValuesCube producer match the native-qualified source
code after removing ONLY comments/whitespace and the temporary independent
comparison block. No numerical body change. Source-bound bridge and immutable
full candidate source/DLLs are retained in the owned lowsfix task root. Temporary
phase/comparison probes and the unselected GPU shader candidate are EXCLUDED
from the clean committed product source.

## Prototype timing, not deployed performance

14s moving Ceaseless replay77 route, same1920x1200/scale2/normal64rays. No native
phase/comparison probes, profiling or file logging during timing windows; the
same ordinary budget collector runs in both arms. Assets/world warmed once;
EVERY arm forces a rendered opposite control state before the final value,
then5s settles, so on/on is lighting-cache-cold too. This is not first-ever load.
Runtime programs are frozen published b8b0cda, not an installed-VM timing claim.

| Arm | Average FPS | 1% low | 0.1% low | Worst frame ms |
| --- | --- | --- | --- | --- |
| Off-a |697 |124 |17 |249.46 |
| On-a |718 |195 |37 |67.22 |
| On-b |712 |182 |32 |66.91 |
| Off-b |706 |125 |17 |248.55 |

The hitch is reduced, NOT eliminated. The worst frame need not simply halve:
slower frames advance the replay farther, grouping later new-prop solves into
larger bursts. 0.1% tails here contain only9-10 frames. Do not extrapolate this
short partial route to whole-map, warmed/GPU, player-specific or installed FPS.

## Clean committed build / comparison / delivery

PENDING: exact committed native+three-VM build, clean native cold-lighting ABBA,
source publication and guarded dual-Windows native-only activation/hash/rollback
readback. No actual installed VM/config/cache/player-data replacement, Pi/backend
restart, release or QC Build bump is needed for this client-renderer-only change.
Human prop-lighting appearance/feel acceptance remains pending, not invented.
