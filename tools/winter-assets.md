# Winter asset candidates — 4 Nov 2026

## Holiday props: licensed and converted; runtime acceptance pending

[Kenney Holiday Kit 2.0](https://kenney.nl/assets/holiday-kit), 100 assets.
The actual downloaded package's `License.txt` identifies Creative Commons Zero
(CC0) and expressly permits personal, educational and commercial use. Credit is
not required, but retain the source/license and credit Kenney voluntarily.

- `Models/GLB format/snowman.glb`: 46,492 bytes; corresponding OBJ has 892 triangles.
- `Models/GLB format/snowman-hat.glb`: 56,284 bytes; corresponding OBJ has 1,110 triangles.
- FBX and OBJ variants, palette texture and previews are in the same archive.
- Previews inspected: stylized white snowman, carrot nose, twig arms; optional
  black top hat. That hat is NOT a Santa hat and does not supply an inventory item.

The 4,482,244-byte archive is staged under the owned task root, not redistributed
as a whole. P1302's tools/holiday_assets.py now emits six small native IQMs under
ftesurf/models/christmas: these two snowmen, tree-decorated-snow (1620 triangles),
tree-snow-a (756), present-a-cube (330) and present-b-rectangle (330), total5038.
Bundled CC0 license/palette retained; only license trailing tabs/CRLF are
normalized for Git (legal text unchanged, original archive/hash preserved).
Material is uniquely namespaced. Provisional
flat-floor-validated sidecar records exist for Christmas/Frost/Bluewinter. Actual
renderer/placement/performance acceptance and deployment remain pending. For FTE's OBJ loader, a supplied .mtl alone
is NOT sufficient: it takes the shader name from usemtl and does not parse mtllib.
Use a uniquely namespaced material and validate orientation/scale; do not create a
world-global shader named simply colormap. Default mod_obj_orientation=1 accepts
Y-up, as these source meshes use; leave the owner's global cvar unchanged.

Provenance (archive bytes, not a newly generated/repacked download):

```
kenney-holiday-kit.zip
fde4d514d7297388d98058e8933ff614e071886f7ce57f9aea4b00d7698dd769
Models/GLB format/snowman.glb
9124463abc03ec477f35b478692ba06cf15c17420a86321a6e4deb72deac4ef4
Models/GLB format/snowman-hat.glb
3734abb86420eda3278012beccc7344afc39161415c10422a20a6ae5fa4e338f
License.txt
6010f677d95f3ab7935faf873d8f4eb96ad1e5f02fd0e4659c9d92852b768d6a
```

## Smoke reference: do not import under the current terms

[Admer456/halflife-smoke](https://github.com/Admer456/halflife-smoke) is a useful
visual reference. Its README's Valve SDK terms restrict the grant to modified
Valve games on the Half-Life engine. FTE is not that engine; no code/assets were
copied into this product. Build a small independent capped billboard/slice effect
or obtain a compatible license, rather than assuming public GitHub means reusable.

## Still needed

Santa-hat mesh/inventory entitlement, winter wind/sheltered ambience/thunder
assets with clear licenses, actual event dates and in-game appearance/performance
checks. Owner allows agent-chosen provisional maps and confirmed Santa is a
PERMANENT gift for event participants; those decisions are no longer blockers. ROADMAP.md tracks the complete request.
