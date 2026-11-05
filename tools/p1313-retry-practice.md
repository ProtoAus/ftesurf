# P1313 — preserve movement, not a fresh clean retry arm

## Boundary

Retry deliberately restores saved movement. It must not make a fast fresh armed
start clean merely because the world restarted. Apply the existing reset rule,
not a clamp or a guessed reconstruction of saved jump phase.

After successful `SV_RetryApply` placement ONLY, an ARMED player still within its
own box group uses `SV_TimerFast`: the existing horizontal reset-speed rule,
including any latched carrier. It goes through `SV_TimerPractice`, retaining the
body and old bits while setting standard dirty/practice state. Configured hull
bands and connected regions use the existing `SV_ZoneInBox` timer semantics.
Running retries, positions outside the armed box and direct Multi-Session-style
restores do not pass this wrapper-only guard.

Vertical motion alone is NOT prespeed. Existing reset protection intentionally
ignores saved falls and upward pushes and also covers bhop maps whose hop rule is
off. This does not turn a hop/strict-mode switch into a horizontal reset bypass,
or introduce a new vertical cap. `run_class 0` bisects class wording, not ranking
rules; an unsafe horizontal reset still gets its ordinary practice mark.

No movement/startok repair, new captured signal, native/API/format/flag/tier/
ranking-policy or QC Build. Native source/tag remain separately qualified P1312.

## Acting checks and correction

- Exact published untreated module, rejected initial candidate and corrected
  candidate use the actual writer/reader/retry wrapper, consumed latch and
  state-file deletion. **22** explicit cases preserve exact origin/velocity and
  old bits across walk boundaries, running/outside/direct restore, prior status,
  hull bands, connected regions, hop/strict modes and classification-word mode.
- The untouched module misses **nine** intended horizontal reset marks. The
  rejected load-forgiveness-based candidate makes **four** false vertical-only
  marks. The corrected candidate has **zero missing and zero false marks**.
  Original reviews, failed predictions and raw counterparts remain retained.
- Existing **five** normal-load and **fourteen** grant/EOF controls stay unchanged.
  The fleet-qualified `c24`/git-7809 compiler runs these arms; actual corrected
  `build.ps1 -NoDeploy` builds all three VMs with **zero warnings**. Historical
  `7ccb` results and the first external-module include refusal are not regraded.
- Corrected reader suite **949/0**. A fresh exact-domain byte/source check reuses
  earlier paired RUNS **544** classifications only after verifying ALL recording/
  view bytes and all three reader/helper/test blobs are identical: **344** faulted
  recording reports, **7** faulted views. This is valid unchanged-input evidence
  reuse, NOT a claimed new full reparse. No fault increase, clean-corpus or SAVES
  claim. Actual deployment-boundary observations remain separate.
- Synthetic explicit entities are NOT a real native map_restart, held-jump/dwell,
  ranked finish or human pass. Original private vectors/recipes and raw logs stay
  private, including the source-based adjudication of the first review concerns.

## Current state

Corrected code `94e37cf8` is committed; two independent bounded delta reviews,
source/state and recorded consequences, found no blocking issue. The source
reviewer explicitly clears the original BLOCK: the vertical finding is fixed,
the proposed mode gate is withdrawn under the verified existing reset contract,
and the original classification-off assertion is corrected. The evidence reviewer
withdraws acceptance of the old vertical predicate and approves only this delta.
Original reviews and failed predictions remain retained, not silently waived.
Actual program deployment is still pending and recorded separately. Pending human
check is in lextest.md; broader saved-phase/native-bank coverage stays partial.
