# P945 — loaded recording byte attribution

## Scope and state

Implemented; Windows control verification is complete. Final committed-source
rebuild, ARM qualification and guarded development deployment are pending.

`pm_verify` now reports SHA-256 of the **complete buffer it loaded**, before
record parsing, with the current invocation challenge. The backend accepts only
one early matching report for each requested path, a successful subprocess exit,
and unchanged source observations. It strips untrusted normalized source lines
and validates the native report before producing the internal binding.

A missing, malformed, repeated, late or mismatched binding is retryable `ERROR`:
unknown ticks, no counts metrics, no verification badge. A unique companion and a
normal later retry remain independent. A legacy row without a filing-time hash
can use its freshly observed bytes without inventing historical filing identity.

This is not host attestation, historical-verdict provenance, automatic badge
revocation or a security-complete claim. No recording grammar, mover, collector,
database schema, retention, access or detection-threshold change. Existing
review, recheck, error-budget and abandoned-evidence rules are preserved.

## Acting controls

- Seven real-file/SQLite cases expose eleven pre-fix failing subcases. Missing
  or different source, ambiguous/malformed/late/wrong-path reports and unbound
  terminal outcomes do not select a trusted verdict or counts observation.
- The actual runner seam exercises a fresh challenge, wrong/old challenge,
  forged normalized text, failed exit, old native output and mixed reports.
  Every arm proves runner invocation; repeated invocations get different tokens.
- Input, identity, source, finish and counts suites: **47 tests, zero failures**.
  Reader regression: **864 checks, zero failures**. The unchanged corpus floor
  is **419 recordings / 283 faulted files**; no source recording changed.
  The three current-origin NoDeploy VMs compile with **zero warnings**.
- Windows NoDeploy native control: **74 inherited warnings, zero new**. All
  **60 named physics rows** match the unchanged native reference with the same
  current VM/content/profile, including acting prop and wrapped-hull branches.
- Real dedicated CLI: ordinary LF and CRLF recordings both **PASS 4418 ticks**,
  while their distinct full byte digests match independent SHA-256 calculations.
  The complete NUL-suffix input is reported and refused for invalid raw bytes.
- A retained REC15 file also reports its exact full digest and current challenge;
  its different stored context is refused. This is **not** new REC15 trajectory
  acceptance, physical-input evidence or a new capture.

The older retained physics matrix used another zone-overlay/profile fixture;
comparing it directly to the current rig was invalid. Its mismatch evidence is
retained, not relabelled. The paired unchanged-code control uses the same current
fixture and matches all sixty rows.

## Reproduction and delivery boundaries

From `surfd/`:

```text
python -m unittest test_verifier_input test_verifier_identity test_verifier_sources test_verifier_finish test_verifier_counts
```

Use the existing build entrypoint with `-NoDeploy` for isolation; a passing working-tree
control does not establish the identity of a final committed binary. Native and
backend must be qualified together before the new backend requires this report.
Neither Windows install, live backend nor lobby fleet has been changed by these
controls. Preserve exact source/artifact provenance, existing `.prev` files and
the prior runtime during the later guarded promotion. Detailed private evidence
and failed controls remain private.
