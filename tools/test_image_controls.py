#!/usr/bin/env python3
"""Execute the engine's actual exposure GLSL on an owned, hidden Windows GL context.

No game/install/player data, foreground window, or server is used. Requires numpy.
Tests the float intermediate, black toe, highlights, monotonic mean ramp, stable
spatial dither, strength bounds, gamma/brightness action, and colour preservation.
"""
import argparse
import ctypes as C
from ctypes import wintypes as W
import pathlib
import sys

import numpy as np


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--engine', type=pathlib.Path, required=True)
    args = ap.parse_args()
    if sys.platform != 'win32':
        ap.error('this falsifier requires Windows OpenGL')
    source = (args.engine / 'engine/shaders/glsl/defaultgammacb.glsl').read_text()
    chain = (args.engine / 'engine/gl/gl_rmain.c').read_text()
    stages = [chain.index(s) for s in [
        'RDF_WATERWARP, scenepp_waterwarp, "rt/$waterwarped"',
        'RDF_COLOURCORRECT, ccpostproc, "rt/$colourcorrected"',
        'RDF_SCENEGAMMA, scenepp_gamma, "rt/$gammaed"',
        'RDF_ANTIALIAS, scenepp_antialias, "rt/$antialiased"']]
    if stages != sorted(stages):
        raise AssertionError('exposure must see final map-graded blacks before AA')
    print('PASS native stage order: author grade before user exposure')
    fragment = '#version 120\n#define FRAGMENT_SHADER\nuniform sampler2D s_t0;\n' + '\n'.join(
        line for line in source.splitlines()
        if not line.startswith('!!') and line != '#include "sys/defs.h"')
    vertex = '''#version 120
varying vec2 tc;
varying vec4 vc;
uniform vec4 parameters;
void main() { gl_Position = gl_Vertex; tc = gl_MultiTexCoord0.xy; vc = parameters; }
'''
    user, gdi, gl = C.WinDLL('user32'), C.WinDLL('gdi32'), C.WinDLL('opengl32')
    user.CreateWindowExW.argtypes = [W.DWORD, W.LPCWSTR, W.LPCWSTR, W.DWORD,
                                    C.c_int, C.c_int, C.c_int, C.c_int,
                                    W.HWND, W.HMENU, W.HINSTANCE, W.LPVOID]
    user.CreateWindowExW.restype = W.HWND
    user.GetDC.argtypes, user.GetDC.restype = [W.HWND], W.HDC
    user.ReleaseDC.argtypes = [W.HWND, W.HDC]
    user.DestroyWindow.argtypes = [W.HWND]
    class PFD(C.Structure):
        _fields_ = [('size', W.WORD), ('version', W.WORD), ('flags', W.DWORD),
                    ('type', C.c_ubyte), ('color', C.c_ubyte),
                    ('red', C.c_ubyte), ('redshift', C.c_ubyte),
                    ('green', C.c_ubyte), ('greenshift', C.c_ubyte),
                    ('blue', C.c_ubyte), ('blueshift', C.c_ubyte),
                    ('alpha', C.c_ubyte), ('alphashift', C.c_ubyte),
                    ('accum', C.c_ubyte), ('accumred', C.c_ubyte),
                    ('accumgreen', C.c_ubyte), ('accumblue', C.c_ubyte),
                    ('accumalpha', C.c_ubyte), ('depth', C.c_ubyte),
                    ('stencil', C.c_ubyte), ('aux', C.c_ubyte),
                    ('layer', C.c_ubyte), ('reserved', C.c_ubyte),
                    ('layermask', W.DWORD), ('visiblemask', W.DWORD), ('damagemask', W.DWORD)]
    gdi.ChoosePixelFormat.argtypes = [W.HDC, C.POINTER(PFD)]
    gdi.SetPixelFormat.argtypes = [W.HDC, C.c_int, C.POINTER(PFD)]
    gl.wglCreateContext.argtypes, gl.wglCreateContext.restype = [W.HDC], C.c_void_p
    gl.wglMakeCurrent.argtypes = [W.HDC, C.c_void_p]
    gl.wglDeleteContext.argtypes = [C.c_void_p]
    gl.wglGetProcAddress.argtypes, gl.wglGetProcAddress.restype = [C.c_char_p], C.c_void_p
    hwnd = user.CreateWindowExW(0, 'STATIC', 'FTESurf image-control falsifier',
                                0x80000000, 0, 0, 32, 32, None, None, None, None)
    if not hwnd:
        raise OSError('hidden test window creation failed')
    dc, context = user.GetDC(hwnd), None
    try:
        pfd = PFD()
        pfd.size, pfd.version, pfd.flags, pfd.type, pfd.color, pfd.alpha = C.sizeof(PFD), 1, 0x24, 0, 32, 8
        pf = gdi.ChoosePixelFormat(dc, C.byref(pfd))
        if not pf or not gdi.SetPixelFormat(dc, pf, C.byref(pfd)):
            raise OSError('test pixel format unavailable')
        context = gl.wglCreateContext(dc)
        if not context or not gl.wglMakeCurrent(dc, context):
            raise OSError('test GL context unavailable')

        def proc(name, result, *types):
            address = gl.wglGetProcAddress(name.encode())
            if address not in (None, 0, 1, 2, 3, C.c_void_p(-1).value):
                return C.WINFUNCTYPE(result, *types)(address)
            fn = getattr(gl, name)
            fn.restype, fn.argtypes = result, list(types)
            return fn

        ui, integer, fp, ptr = C.c_uint, C.c_int, C.c_float, C.c_void_p
        create_shader = proc('glCreateShader', ui, ui)
        shader_source = proc('glShaderSource', None, ui, integer, C.POINTER(C.c_char_p), C.POINTER(integer))
        compile_shader = proc('glCompileShader', None, ui)
        shader_iv = proc('glGetShaderiv', None, ui, ui, C.POINTER(integer))
        shader_log = proc('glGetShaderInfoLog', None, ui, integer, C.POINTER(integer), ptr)
        create_program = proc('glCreateProgram', ui)
        attach = proc('glAttachShader', None, ui, ui)
        link = proc('glLinkProgram', None, ui)
        program_iv = proc('glGetProgramiv', None, ui, ui, C.POINTER(integer))
        program_log = proc('glGetProgramInfoLog', None, ui, integer, C.POINTER(integer), ptr)
        use = proc('glUseProgram', None, ui)
        location = proc('glGetUniformLocation', integer, ui, C.c_char_p)
        uniform1 = proc('glUniform1f', None, integer, fp)
        uniform4 = proc('glUniform4f', None, integer, fp, fp, fp, fp)
        uniformi = proc('glUniform1i', None, integer, integer)
        ids = proc('glGenTextures', None, integer, C.POINTER(ui))
        bind_tex = proc('glBindTexture', None, ui, ui)
        image = proc('glTexImage2D', None, ui, integer, integer, integer, integer, integer, ui, ui, ptr)
        texparam = proc('glTexParameteri', None, ui, ui, integer)
        gen_fbo = proc('glGenFramebuffers', None, integer, C.POINTER(ui))
        bind_fbo = proc('glBindFramebuffer', None, ui, ui)
        attach_tex = proc('glFramebufferTexture2D', None, ui, ui, ui, ui, integer)
        fbo_status = proc('glCheckFramebufferStatus', ui, ui)
        viewport = proc('glViewport', None, integer, integer, integer, integer)
        disable = proc('glDisable', None, ui)
        begin, end = proc('glBegin', None, ui), proc('glEnd', None)
        coord = proc('glTexCoord2f', None, fp, fp)
        position = proc('glVertex2f', None, fp, fp)
        read = proc('glReadPixels', None, integer, integer, integer, integer, ui, ui, ptr)

        program = create_program()
        for kind, text in [(0x8B31, vertex), (0x8B30, fragment)]:
            shader = create_shader(kind)
            encoded = C.c_char_p(text.encode())
            shader_source(shader, 1, C.byref(encoded), None)
            compile_shader(shader)
            ok = integer()
            shader_iv(shader, 0x8B81, C.byref(ok))
            if not ok.value:
                log = C.create_string_buffer(16384)
                shader_log(shader, len(log), None, log)
                raise AssertionError('actual shader failed to compile: ' + log.value.decode())
            attach(program, shader)
        link(program)
        ok = integer()
        program_iv(program, 0x8B82, C.byref(ok))
        if not ok.value:
            log = C.create_string_buffer(16384)
            program_log(program, len(log), None, log)
            raise AssertionError('actual shader failed to link: ' + log.value.decode())
        use(program)
        shadow_loc, parameters = location(program, b'cvar_shadows'), location(program, b'parameters')
        if shadow_loc < 0 or parameters < 0:
            raise AssertionError('acting uniforms must not be absent/optimized out')
        uniformi(location(program, b's_t0'), 0)
        width, height = 1024, 128
        pixels = np.ones((height, width, 4), dtype=np.float32)
        pixels[:, :, :3] = np.linspace(0, 1, width, dtype=np.float32)[None, :, None]
        textures = (ui * 2)()
        ids(2, textures)
        for texture in textures:
            bind_tex(0x0DE1, texture)
            texparam(0x0DE1, 0x2801, 0x2600)  # nearest
            texparam(0x0DE1, 0x2800, 0x2600)
            texparam(0x0DE1, 0x2802, 0x812F)
            texparam(0x0DE1, 0x2803, 0x812F)
        image(0x0DE1, 0, 0x881A, width, height, 0, 0x1908, 0x1406, None)  # output RGBA16F
        fbo = ui()
        gen_fbo(1, C.byref(fbo))
        bind_fbo(0x8D40, fbo)
        attach_tex(0x8D40, 0x8CE0, 0x0DE1, textures[1], 0)
        if fbo_status(0x8D40) != 0x8CD5:
            raise AssertionError('float target must actually be complete')
        viewport(0, 0, width, height)
        for flag in (0x0BD0, 0x0BE2, 0x0B71, 0x8DB9):  # fixed-function dither/blend/depth/sRGB
            disable(flag)
        checks = 0

        def check(condition, label):
            nonlocal checks
            if not condition:
                raise AssertionError(label)
            checks += 1
            print('PASS', label)

        def render(strength, gamma=1.0, brightness=0.0):
            bind_tex(0x0DE1, textures[0])
            image(0x0DE1, 0, 0x8814, width, height, 0, 0x1908, 0x1406, pixels.ctypes.data)  # input RGBA32F
            uniform1(shadow_loc, strength)
            uniform4(parameters, 1.0 / gamma, 1, brightness, 1)
            begin(0x0007)
            for s, t, x, y in [(0, 0, -1, -1), (1, 0, 1, -1), (1, 1, 1, 1), (0, 1, -1, 1)]:
                coord(s, t)
                position(x, y)
            end()
            output = np.empty_like(pixels)
            read(0, 0, width, height, 0x1908, 0x1406, output.ctypes.data)
            return output[:, :, :3].copy()

        neutral, lifted = render(0), render(1)
        check(np.max(np.abs(neutral - pixels[:, :, :3])) < 0.0005, 'neutral float path is identity within half-float precision')
        toe = pixels[0, :, 0] <= 2 / 255
        highlights = pixels[0, :, 0] >= 0.65
        check(np.array_equal(neutral[:, toe], lifted[:, toe]), 'deepest black toe unchanged')
        check(np.array_equal(neutral[:, highlights], lifted[:, highlights]), 'highlights unchanged')
        check(float((lifted - neutral)[:, 30:400].mean()) > 0.06, 'shadow lift positively acted')
        check(np.array_equal(lifted, render(1)), 'no temporal noise or shimmer')
        check(np.array_equal(neutral, render(-2)), 'negative strength clamps to neutral')
        check(np.array_equal(lifted, render(4)), 'high strength clamps to one')
        mean = lifted[:, :, 0].mean(axis=0)
        check(np.min(np.diff(mean)) >= -0.00001, 'spatial mean ramp remains monotonic')
        quantized = np.rint(np.clip(lifted[:, :, 0], 0, 1) * 255).mean(axis=0)
        check(len(np.unique(quantized[20:600])) > 450, 'spatial dither resolves over 450 mean levels in an 8-bit output ramp')
        check(np.array_equal(lifted[:, :, 0], lifted[:, :, 1]) and np.array_equal(lifted[:, :, 1], lifted[:, :, 2]), 'neutral grey stays neutral')
        bright = render(0, gamma=1.6, brightness=0.1)
        check(float((bright - neutral).mean()) > 0.15, 'gamma and brightness positively acted')
        pixels[:, :, 0], pixels[:, :, 1], pixels[:, :, 2] = 0.03, 0.06, 0.1
        colour = render(1)
        # The same sub-LSB dither is added to each channel. Average it away.
        ratio = colour.mean(axis=(0, 1)) / np.array([0.03, 0.06, 0.1])
        check(float(np.ptp(ratio)) < 0.01, 'colour lift retains RGB ratios within quantization tolerance')
        print(f'{checks} GPU checks passed using actual engine shader and RGBA16F intermediate')
    finally:
        if context:
            gl.wglMakeCurrent(None, None)
            gl.wglDeleteContext(context)
        user.ReleaseDC(hwnd, dc)
        user.DestroyWindow(hwnd)


if __name__ == '__main__':
    main()
