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
Final clean tag-linked full build and promotion are **verified**.
At `2026-11-11T06:57:41Z`, the seven qualified native images in each Windows
install plus the existing developer compiler were promoted through the existing
build entrypoint's `Deploy` function. All 15 destination hashes and predecessor
preservation were checked. Both installed clients report the clean
`patch-1498-0-g78568494a` stamp; the actual installed compiler passes all five
acting include/refusal controls. Existing VMs and owner configuration hashes are
unchanged; no process was terminated and no backend/Pi swap occurred.

Artifact SHA256 (same qualified native images in both installs):

| Artifact | SHA256 |
|---|---|
| client | `f8eb34e94bb1c6e71a8ca8249e7025bf95aa86e556989b8634387bdd43f45a76` |
| server | `a2536333470d4973ff0f52652610af97c27b113fa194411e5db5a096f79faf97` |
| hl2 plugin | `1a7772a3c7969e6f9df22a3be5ec3f1b415d0ec3e86172a6d2dedbbc60f12be7` |
| cod plugin | `f6b76b012d93e3e6edecebe121091d29aaf81b61e3e9f285aee259846facbdd3` |
| box3d plugin | `8b6496ef73bd3d9336395dbbb499eeadef5d70bba6ba97507c04c5479110f73a` |
| ode plugin | `83a76eb95c22164534c660344c26f284d9ecbe1021d39c1455a1f0177aa67bd4` |
| ui_imgui plugin | `529a3ab3addfa9658e5871f23f42fb273124ab24bcdd6807fbd12ba7fb290215` |
| developer compiler | `55bfb4e3a82e3bc54643ec9e53f9f74ae94ac54291d9830365c2f357fb1fa410` |

An outer native-tool PATH initially caused a false dirty revision stamp despite
clean Windows Git status. That candidate was refused, not deployed. Restoring
the supported entrypoint's Windows-Git-before-native-PATH ordering and rebuilding
fully produced the verified clean stamp. Earlier failure evidence remains retained.
The unrelated guarded backend promotion has its own execution boundary; this
compiler qualification does not install or qualify a backend generation.

Reader/recording semantics are unchanged; existing corpus evidence is reusable
only after checking its reader and member identities. No whole-native audit,
compiler sandbox or detector/calibration completion is claimed.
