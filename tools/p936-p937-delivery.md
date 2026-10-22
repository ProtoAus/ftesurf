# P936/P937 compatible development-fleet source

Base QC49a1078a (published REC13 P932/P933 fleet); backend basecc0b7ffa
(schema20). Backport only P936 portrait runtime/test hunks from9b31c300 and
P937 audio module/manifest/frame/default additions from7ae7a80e, with final
fixture from69b7e2a8. Native client floor5fd6c6790 / patch-937 fixes raw EOF
ownership. No lobby native, producer, recorder, reader, policy or schema change.
This is NOT promotion of mainline's held producer/native/evidence set.

Verified before source publication:
- Compatible NoDeploy f5cabc644735441b91e821a374d5bbac: all3VMs0 warnings.
- Compatible final native937 audio: all13 acted controls pass, no run/consent
  writes, all actors stopped. Runtime module/input delta exactly reviewed source.
- Compatible ranked/API suite passes. Matched compatible backend + client/menu
  64px native fixture passes response/upload dimensions, quadrant screenshots
  (inspected) and renderer reload. The first positive attempt FAILED because it
  loaded the unchanged32px backend from the QC checkout; retained, not relabeled
  as a planned control. Correct existing fixture runs from backend-compatible
  tools/p640pics.py against the QC progs, no altered expectations/new wrapper.
- Native full build0 NEW warnings (74 unchanged baseline); C ownership unit
  balances4096 cycles. Input and lifecycle independent reviews OK; P1/P2 closed.
- Listening, real-account appearance, latency/performance/RSS/concurrency remain
  unclaimed. No live deployment claimed by this source snapshot.

Only runtime backend files changed are steam.py, steamsync.py and surfd.py;
ranked/picture tests accompany them. Preserve serving predecessor and use the
existing immutable guarded successor transaction, backend BEFORE progs. New
CSQC self-registers all audio defaults; do not overwrite owner/peer configs.
