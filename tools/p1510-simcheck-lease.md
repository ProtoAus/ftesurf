# P1510 — preserve the comparison worker's lifetime lease

## Problem

The contained comparison launch used Python's default `close_fds=True`. That
also closes the transition guard's deliberately inheritable admission/candidate
leases. A waiting parent normally retains its own lease, but loss of that
parent's descriptor must not make a still-running worker disappear from drain.

## Change

This Linux-only launch preserves already explicitly inheritable descriptors
through `prlimit` and Python exec. Ordinary close-on-exec descriptors remain
private; the helper does not mark any additional descriptor inheritable. Existing
resource limits, byte-bounded IPC, existing-only database admission, comparisons,
observations, ranking policy and the owned timeout/reap path are unchanged.

## Verified

Run the existing entrypoint on Linux:

```text
python surfd/test_simcheck_process.py
```

- Untouched published P1509 control: the actual comparison acts and blocks at a
  bounded fixture barrier. Once its parent closes its own shared-lock descriptor,
  an independent exclusive-lock probe succeeds prematurely. The new assertion
  fails on that control; no missing marker is accepted as a pass.
- Fixed ARM source: all 17 process/admission tests pass. While the acted child is
  blocked, its actual descriptor retains the original lease device/inode and is
  inheritable. After the parent releases its own descriptor, the independent
  exclusive probe remains contended. The worker does not inherit the original
  inode of a normal close-on-exec fixture descriptor. After release and worker
  exit, the exclusive probe succeeds.
- Windows: all 11 applicable controls pass; six actual-Linux arms are explicit
  skips. Python parsing and the owned diff checks pass. No reader/evidence
  semantics or bytes changed; P1509's reader/corpus and unrelated regression
  evidence remains applicable, not a new measurement campaign.

## Limits and delivery

This demonstrates actual descriptor and lock lifetime at the contained launch,
not an entire guarded-generation promotion or a parent-death recovery test.
A dead parent can leave a worker holding its lease: closure must fail closed,
not claim an unconditional orphan-reap or kernel-I/O deadline. No production
namespace, guard state, DATA, service, player file or config was touched.

Source publication is not deployment. Two independently scoped clean-source
reviews and the existing guarded-generation qualification remain required before
rollout. No native source/binary pin/tag, recording schema, capture, threshold,
verdict or QC Build change.
