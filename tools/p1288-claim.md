# P1288 claim

ftesurf-48, 20261105, Lex (4 Nov, surf_eternity stair room vs CS:S): Source brush materials (LightmappedGeneric, WorldVertexTransition) apply $color as a LINEAR multiplier (lightmappedgeneric_dx9_helper.cpp: raw, sRGB read/write); our gamma-space vmt shaders multiplied the gamma value, so $color < 1 drew ~3.5x too dark (eternity walls, $color .103).
State: installed 5 Nov (hl2 plugin b5ec1cc8, patch-1288).
