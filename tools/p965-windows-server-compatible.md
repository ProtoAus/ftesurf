# P965 Windows server-only composition

Base is the actually deployed public P964 Windows server composition
b27a76f031baa874156ebbfd6037dac62b7577ad. Its qualified server artifact
765b4e75a0416dffbd4bef851dc251af1579c9d2fafa82b94ed52921b909a5ab is the
expected predecessor, not all-main Pi server or the older P957 control.

Only replace the legacy progress lookup with the reviewed P965 module from
8a86dc3dc040da8538dcff6c7344bc3642e9f606 (published via merge ebbb1aff).
Whole module SHA256 cbd2d25960de53e8572d2bb120dbeec7ef675c1f12da15c5ffa45b3457531535.
Preserve all other source, including the pre-presence social implementation.
This is a P965 deployment composition, not another feature/native pin/tag/Build
or release. Prior P964 notes remain historical evidence, not this module hash.

Build with existing src/build.ps1 -Jobs8 -NoDeploy. Promote only qualified
server DAT and matching LNO to BOTH Windows installs after checking the actual
P964 server predecessor at each target. Keep .prev and its earlier history.
Protect the ACTUAL current CSQC, MENU, native images, configuration and player
data at the promotion boundary; do not reset them to an earlier snapshot or
ship this branch's client/menu/tools. In particular, newer P966 client work
must neither be activated nor rolled back by this server update.

The reviewed native compatibility cases and code apply unchanged: save/timer/
callers are identical apart from unrelated social source; the entire repaired
module is byte-identical. Three-VM qualification and actual delivery receipts
are separate. This does not claim real signed/cold/posting or human acceptance.
