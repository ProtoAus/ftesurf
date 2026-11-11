# P1498 — compiler include-path entry bounds

## Change

The existing include-path insertion must bound each operation to its selected
entry, not the surrounding aggregate. The two capacity expressions are corrected;
the entry limit, search order and existing warning/refusal remain unchanged.
This is compiler defensive hardening, not a new anti-cheat detector, permission,
input capture, evidence format, scoring rule or player setting.

## Qualified before publication

- 106 source-bound cases using the actual function and string helpers. Unsafe
  old operations were intercepted before writing. Both omitted-fix mutants and
  an overly restrictive boundary were discriminated; valid insertion still acts.
- Five real standalone-compiler cases: a successful include whose definition is
  otherwise absent, an acting missing-include refusal, and corrected invalid
  path refusal while the valid include still supplies the compiled definition.
- The unsafe malformed-input old compiler was not executed. Static reachability
  plus safe controls are not a measured exploit or a remote-dispatch claim.
- Existing supported `qcc-rel FTE_TARGET=win64` build succeeded. Full supported
  client/server/five-default-plugin build succeeded: the 74 native warning
  payloads exactly match the prior qualified full-build baseline, zero new.
  All three production QC VMs compiled with zero warnings.
- Initial missing native dependency headers and private fixture environment/
  declaration failures were retained, fixed at their input seams, not regraded.
  The previously working dependency input is shared read-only, not copied.

## Delivery status

Independent frozen review is **CLEAR** for the exact two-expression repair.
Published engine source: `78568494acf61956fd3f8683a1aa4420e3457433`, tag `patch-1498`.
Final clean linked build and dual Windows/native-tool promotion are **pending**.
Initial candidate outputs are not claimed as installed binaries. No owner process
is to be terminated to deploy.
The unrelated guarded backend promotion has its own execution boundary; this
compiler qualification does not install or qualify a backend generation.

Reader/recording semantics are unchanged; existing corpus evidence is reusable
only after checking its reader and member identities. No whole-native audit,
compiler sandbox or detector/calibration completion is claimed.
