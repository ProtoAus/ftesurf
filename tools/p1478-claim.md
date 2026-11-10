# P1478 claim — journal close must not shrink the recording limit

Owner pi.dev session 01a1c66e-34b2-747f-b389-a4e589d5d20c, 2026-11-10 UTC.
Scoped existing P1116 recorder-completeness fix: retain configured limit when the
terminal record crosses an allocation boundary; actual body truncation stays
announced. No capture/consent/format/enforcement change. Parent is sole writer.
Fetched both origins; max patch heading1476, tracked claim1477, all registered
worktrees' untracked pNNN test/claim paths inspected; reserve max+1=1478 only.
Control actual production append/close functions:628 checks,50 targeted failures.
Source baseline engine0b223e6148922c36687e6abc5aa4b5122df7634e,
QC6ec8be9f70f6140796a7ca0cdd0f4885f8749225. Product work is isolated.
