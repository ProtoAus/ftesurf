# P1079: one declared inherited-effect exclusion flag

## Contract

TF_BANKTAINT (8388608, bit23) is one derived status bit in the EXISTING flags word,
not another recording key, input stream, device or identifier. It implies practice
and excludes an inherited effect from all run tiers, including segmented/shadow.
Cheat/TAS precedence remains. Ordinary current eligible segmented/shadow play keeps
its prior tier, including map interactions. Map effects are not cancelled.

Existing VM-local source/admission/taint snapshots distinguish legacy practice
from actual across-tier exclusion; they are not new captured fields. Source and
recipient need not be the same player. Expired/missing source admissions or
otherwise ineligible causes mark only actual supported receiving bodies. The
existing level latch preserves the declared bit and stage flags; restoring a
declared flag re-latches it, while the original fresh-arm lifecycle clears it.
Notification severity places bank practice after segmented but before cheat/TAS,
without changing physics, clock, timer input acceptance or callback ownership.

Bits20/21 remain reserved for styles. Bit23 is the LAST exact float32 flag bit:
all24 bits total16777215 are exact; no bit24 addition without integer migration.
The existing fixed-width flags header is unchanged. The spectator pose stream is a
signed 24-bit field (Pose_W24), so it carries flags below bit23 only. Readers report `declared` or
`not declared`; legacy absence is NOT evidence of no inherited effect. Malformed
bank-without-practice metadata faults as malformed, not a cheating verdict.

This declares only the existing supported helper's exclusion. Persistent interval/
phase/logical/world/body/carrier contributors and complete Rule8 remain OPEN.
No historical destructive regrade, new sensor/input collection, new consent bypass,
Build/release or native pin change. Existing recording/collection gates remain.

## Qualification and delivery

PENDING complete corpus, stock build, three frozen independent source reviews and
consumer-first development delivery. Do NOT deploy producing progs before the
backend and its actual sealed reader dependency support this bit. Native synthetic
actors/direct helper calls and isolated Flask submissions are not genuine HID,
natural finish, signed receipt/ranking, human acceptance or full-bank proof.
Human-only normal segmented/shadow map acceptance belongs in lextest.md.
