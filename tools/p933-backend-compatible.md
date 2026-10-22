# P933 social-only compatible backend successor

Base is the inspected serving generation's published commit
9e168015b0d6a3259fb4e75a9ad05aa4aac89bea. Apply ONLY P933 mainline
f5826963's social.py and test_social.py hunks. Every other source/runtime/reader
file stays at the serving generation. This avoids implicitly promoting unrelated
mainline readers or changing the existing producer/reader qualification boundary.

The new activity field is optional, validated and volatile. SQL still decides
mutual visibility, blocked/account policy, session and heartbeat TTL, target
lobby and joining. Samples require matching SQL seen and lobby map; cache/worker
loss means no activity until a real poll. Memory is bounded and failed polls
clear affected samples. No schema migration, data rewrite, native binary,
evidence semantics, signing or consent change.

Local isolated `python -m unittest test_social`: 44 tests pass (5.622s), including
all existing private-list/DM/proof controls and new activity/hash/expiry/map-change/
worker-loss/bounds/invalid-label/rollback controls. The two changed Python files
must match published P933 exactly. No other surfd/tools runtime file may change.

Before promotion use the existing guarded successor route, not direct copying:
create an owned NanoPi root/OWNER.md, archive this pushed commit, build_gen.py
against the actual serving root, and check EXPECTED deltas. The only expected
runtime-content change is social.py. Run the mandatory complete staged suite.
Require the normal empty fleet and guarded handoff; never weaken admission,
writer/reader pins or freshness to pass. Keep the old root for rollback.

This source report is not a deployment claim. Record actual schema, runtime
manifest delta, test results, destination hashes, live process identity and UTC
after executing the guarded cutover. Pair it with the independently published
REC13-compatible P933 QC variant, not held mainline progs. Real-account
stage/bonus/card/profile/join owner acceptance remains pending in lextest.md.
