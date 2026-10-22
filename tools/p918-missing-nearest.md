# P918 — nearest-filtered missing diffuse

Engine c958a3d3e9977954c41edca24ba652944255829a / annotated patch-918.
Only the shared missing_texture / no_texture diffuse receives IF_NEAREST at
R2D_Init. Its owner's missingtexture PNG replacement/alias is unchanged, as are
ordinary world images, mipmaps and gloss/normal fallback images. No global cvar.

Before edit: predict point minification/magnification and anisotropy 1 only for
the fallback, including after global mode changes; a normal image must still
honour global linear/aniso settings. Falsifiers used the actual extracted
GL_Texturemode_Apply compiled with GCC: acting linear/aniso16 control plus 10
nearest/global-mode cases all pass. An initial compiler environment failure was
fixed by supplying the same UCRT PATH as the native build, not by altering code.
Existing test_missing_assets.py passes all 8 controls (including exact 64x64
owner PNG bytes/alias and ship entries). Native client/server/plugin build passes
without new warnings; final clean stamped client artifact readback follows.

This is sampler/native/source evidence, not GPU screenshot/manual acceptance.
Owner: after the matching client update, view any missing checker close up and
confirm sharp texel boundaries without changing global texture filtering.
No release/Build bump, assets copied from Counter-Strike, server changes or
player-data writes are involved in this patch.
