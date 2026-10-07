/*
  Viewer-local lobby-body shader. Embedded in CSQC so a fresh server download
  carries the effect too: a new glsl/ asset would silently fall back on clients
  that have not updated their install. Only Body_Predraw uses this material.

  The unbumped defaultskin path, including its signed diffuse lighting, player
  colour layers and additive glow. Survivors stay opaque and depth-writing;
  camera-to-body-centre distance selects 0..16 screen-space Bayer cells.
*/
float() Body_FadeShader =
{
	return shaderforname("ftesurf/playerfade",
		"{\nglslprogram\n{\n"
		"!!ver 100 150\n"
		"!!permu UPPERLOWER\n"
		"!!permu FULLBRIGHT\n"
		"!!permu SKELETAL\n"
		"!!permu FRAMEBLEND\n"
		"!!permu FOG\n"
		"!!samps diffuse upper lower fullbright\n"
		"!!cvarf cl_playerfade_near=32\n"
		"!!cvarf cl_playerfade_far=128\n"
		"#include \"sys/defs.h\"\n"
		"#include \"sys/fog.h\"\n"
		"varying vec2 tc;\n"
		"varying vec3 light;\n"
		"#ifdef VERTEX_SHADER\n"
		"#include \"sys/skeletal.h\"\n"
		"void main(void)\n{\n"
		" vec3 normal, tangent, bitangent, position;\n"
		" gl_Position = skeletaltransform_wnst(position, normal, tangent, bitangent);\n"
		" tc = v_texcoord;\n"
		" float diffuse = dot(normalize(normal), e_light_dir);\n"
		" if (diffuse < 0.0) diffuse *= 13.0/44.0;\n"
		" light = e_light_ambient + e_light_mul * diffuse;\n"
		"}\n#endif\n"
		"#ifdef FRAGMENT_SHADER\n"
		"uniform float cvar_cl_playerfade_near;\n"
		"uniform float cvar_cl_playerfade_far;\n"
		"float b2(float x, float y)\n{\n"
		" return mod(2.0*x + 3.0*y, 4.0);\n"
		"}\n"
		"float bayer4(vec2 p)\n{\n"
		" float lo = b2(mod(p.x, 2.0), mod(p.y, 2.0));\n"
		" float hi = b2(mod(floor(p.x*0.5), 2.0), mod(floor(p.y*0.5), 2.0));\n"
		" return (4.0*lo + hi + 0.5) / 16.0;\n"
		"}\n"
		"void main(void)\n{\n"
		" float nearDist = max(0.0, cvar_cl_playerfade_near);\n"
		" float farDist = max(nearDist + 1.0, cvar_cl_playerfade_far);\n"
		" float distance = length(e_eyepos - vec3(0.0, 0.0, 31.0));\n"
		" float coverage = smoothstep(nearDist, farDist, distance);\n"
		// Fragment centres are half-integers; Bayer cells need integer indices.
		" if (coverage < bayer4(floor(gl_FragCoord.xy))) discard;\n"
		" vec4 col = texture2D(s_diffuse, tc);\n"
		"#ifdef UPPER\n"
		" vec4 shirt = texture2D(s_upper, tc);\n"
		" col.rgb += shirt.rgb * e_uppercolour * shirt.a;\n"
		"#endif\n"
		"#ifdef LOWER\n"
		" vec4 pants = texture2D(s_lower, tc);\n"
		" col.rgb += pants.rgb * e_lowercolour * pants.a;\n"
		"#endif\n"
		" col *= factor_base;\n"
		" col *= vec4(light, 1.0) * e_colourident;\n"
		"#ifdef FULLBRIGHT\n"
		" vec4 fb = texture2D(s_fullbright, tc);\n"
		" col.rgb += fb.rgb * fb.a * e_glowmod.rgb * factor_emit.rgb;\n"
		"#endif\n"
		" gl_FragColor = fog4(col);\n"
		"}\n#endif\n"
		"}\ndiffusemap models/player\nfullbrightmap models/player_luma\n"
		"uppermap models/player_shirt\nlowermap models/player_pants\n"
		"{\nmap models/player\nrgbgen lightingdiffuse\n}\n}\n");
};
