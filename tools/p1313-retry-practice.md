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
Reviewed publication: QQ `486e65bd911940b84dd8662e36af1e2650fc3e90`, engine journal
`fdaa28beac015173a2a66b61cfa12fb9fba3cd97`. Runtime code is identical to the corrected
`94e37cf8` build; later journal/declaration-only commits do not move native P1312.

### Actual deployment — 5 November 2026 UTC

- **04:22:03, BOTH Windows:** the four changed SSQC DAT/LNO destinations and `.prev`
  match the frozen corrected build and predecessors. Eight older predecessor/
  prior-prev files are archived and individually rehashed. **18,548** protected
  config/data/native/CSQC/menu/cache paths retain exact bytes. CSQC/menu/native
  bytes were already current and were not replaced; the public CSQC seeder keeps
  all existing cache bytes. No owner process killed or Windows server restarted.
- **04:48:48, NanoPi:** existing guarded paired promotion installs exactly native
  P1312 server/HL2 plus reviewed QQ `486e65bd` QW/CS, no menu/config/backend payload.
  Four installed hashes and `.prev` match; all **12** required empty lobbies restart
  to new verified executable epochs and mapped plugin inodes, zero skipped.
  All **46,488** protected current data files are unchanged, zero new/missing/
  changed files; backend generation, unit, OPEN descriptor/actor and **156** runtime
  files are unchanged. Later **04:53:05** checks find the same twelve responsive
  epochs and exact four hashes/backups. No force/player drop or retained gate.
- Before ANY canonical stage, **8** recorder parts AND **180 complete current
  resume files**, including metadata, were individually rehashed on-box/OFFBOX:
  **188** archive members, **229,091,723** source bytes. Fresh strict **13 declared
  native/backend actor** FD/birth/namespace checks run before staging and again
  under the activation sweep lock. Protected PAM/SSH NONactor limits remain
  explicit; this is NOT general file-writer closure or historical data recovery.
  Eight actual Pi generated predecessor/prior-prev files are also rehashed OFFBOX.
- **04:54:08**, after both deliveries: all **544** recording inputs/**712** paired
  raw record/view files (**192,188,256** bytes) and three parser/helper/test blobs
  at qualified AND canonical roots match the original paired classifications.
  Reuse prior **344 REC/7 VIEW** fault results explicitly; no new full reparse,
  clean-corpus, SAVES or human/ranked acceptance is claimed.

Pending small human check is in lextest.md and was requested after matching
Windows SSQC delivery. Lobby process restarts prove deployment, NOT the distinct
native map_restart/held-jump/dwell phase bank. Broader saved-phase/native-bank
coverage stays partial; original expiry/preservation failures remain unwaived.
