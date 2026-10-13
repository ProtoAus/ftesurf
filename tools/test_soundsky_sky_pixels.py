"""Owned hidden WGL falsifier of production milk_sky.glsl; no game fixtures.

Run with --output under the task's owned artifacts directory. This tests shader
pixels using synthetic thumbnail colours/emission, not engine sky submission.
"""
import argparse
import ctypes as C
from ctypes import wintypes as W
from pathlib import Path
import json
import math
import numpy as np
from PIL import Image


class PixelFormat(C.Structure):
    _fields_ = [("size", W.WORD), ("version", W.WORD), ("flags", W.DWORD),
                ("type", C.c_ubyte), ("colour", C.c_ubyte)] + [
                    (n, C.c_ubyte) for n in ("red", "redshift", "green", "greenshift",
                    "blue", "blueshift", "alpha", "alphashift", "accum", "accumred",
                    "accumgreen", "accumblue", "accumalpha", "depth", "stencil",
                    "aux", "layer", "reserved")] + [
                    (n, W.DWORD) for n in ("layermask", "visiblemask", "damagemask")]


class GL:
    def __init__(self):
        self.user = C.WinDLL("user32")
        self.gdi = C.WinDLL("gdi32")
        self.dll = C.WinDLL("opengl32")
        self.user.CreateWindowExW.restype = W.HWND
        self.user.CreateWindowExW.argtypes = [W.DWORD, W.LPCWSTR, W.LPCWSTR, W.DWORD,
            C.c_int, C.c_int, C.c_int, C.c_int, W.HWND, W.HMENU, W.HINSTANCE, C.c_void_p]
        self.window = self.user.CreateWindowExW(0, "STATIC", "Soundsky pixel falsifier",
                                                0, 0, 0, 256, 256, None, None, None, None)
        assert self.window, "CreateWindow failed"
        self.user.GetDC.restype = W.HDC
        self.user.GetDC.argtypes = [W.HWND]
        self.dc = self.user.GetDC(self.window)
        self.gdi.ChoosePixelFormat.argtypes = [W.HDC, C.POINTER(PixelFormat)]
        self.gdi.SetPixelFormat.argtypes = [W.HDC, C.c_int, C.POINTER(PixelFormat)]
        p = PixelFormat()
        p.size, p.version, p.flags, p.colour = C.sizeof(p), 1, 0x24, 24
        fmt = self.gdi.ChoosePixelFormat(self.dc, C.byref(p))
        assert fmt and self.gdi.SetPixelFormat(self.dc, fmt, C.byref(p))
        self.dll.wglCreateContext.argtypes = [W.HDC]
        self.dll.wglCreateContext.restype = C.c_void_p
        self.rc = self.dll.wglCreateContext(self.dc)
        self.dll.wglMakeCurrent.argtypes = [W.HDC, C.c_void_p]
        assert self.rc and self.dll.wglMakeCurrent(self.dc, self.rc)
        self.dll.wglGetProcAddress.argtypes = [C.c_char_p]
        self.dll.wglGetProcAddress.restype = C.c_void_p
        self.cache = {}
        self.target = C.c_uint()
        self.fbo = C.c_uint()
        self.fn("glGenTextures", None, C.c_int, C.c_void_p)(1, C.byref(self.target))
        self.fn("glBindTexture", None, C.c_uint, C.c_uint)(0x0DE1, self.target.value)
        self.fn("glTexImage2D", None, C.c_uint, C.c_int, C.c_int, C.c_int,
                C.c_int, C.c_int, C.c_uint, C.c_uint, C.c_void_p)(
                    0x0DE1, 0, 0x8058, 256, 256, 0, 0x1908, 0x1401, None)
        self.fn("glGenFramebuffers", None, C.c_int, C.c_void_p)(1, C.byref(self.fbo))
        self.fn("glBindFramebuffer", None, C.c_uint, C.c_uint)(0x8D40, self.fbo.value)
        self.fn("glFramebufferTexture2D", None, C.c_uint, C.c_uint, C.c_uint,
                C.c_uint, C.c_int)(0x8D40, 0x8CE0, 0x0DE1, self.target.value, 0)
        assert self.fn("glCheckFramebufferStatus", C.c_uint, C.c_uint)(0x8D40) == 0x8CD5

    def fn(self, name, result, *args):
        if name not in self.cache:
            ptr = self.dll.wglGetProcAddress(name.encode())
            if ptr and ptr not in (1, 2, 3, C.c_void_p(-1).value):
                f = C.WINFUNCTYPE(result, *args)(ptr)
            else:
                f = getattr(self.dll, name)
                f.restype, f.argtypes = result, args
            self.cache[name] = f
        return self.cache[name]

    def shader(self, kind, source):
        sh = self.fn("glCreateShader", C.c_uint, C.c_uint)(kind)
        data = C.c_char_p(source.encode())
        self.fn("glShaderSource", None, C.c_uint, C.c_int,
                C.POINTER(C.c_char_p), C.c_void_p)(sh, 1, C.byref(data), None)
        self.fn("glCompileShader", None, C.c_uint)(sh)
        self.check(sh, False)
        return sh

    def check(self, obj, program):
        value = C.c_int()
        kind = "Program" if program else "Shader"
        self.fn("glGet" + kind + "iv", None, C.c_uint, C.c_uint,
                C.POINTER(C.c_int))(obj, 0x8B82 if program else 0x8B81, C.byref(value))
        log = C.create_string_buffer(16384)
        self.fn("glGet" + kind + "InfoLog", None, C.c_uint, C.c_int,
                C.c_void_p, C.c_void_p)(obj, len(log), None, log)
        assert value.value, log.value.decode(errors="replace")
        if log.value:
            print(kind + " log: " + log.value.decode(errors="replace"))

    def program(self, fragment):
        vertex = "#version 130\nuniform vec3 e_eyepos; varying vec3 pos; void main(){pos=vec3(gl_Vertex.xy,1.0)+e_eyepos;gl_Position=gl_Vertex;}"
        shaders = [self.shader(0x8B31, vertex), self.shader(0x8B30, fragment)]
        p = self.fn("glCreateProgram", C.c_uint)()
        for sh in shaders:
            self.fn("glAttachShader", None, C.c_uint, C.c_uint)(p, sh)
        self.fn("glLinkProgram", None, C.c_uint)(p)
        self.check(p, True)
        for sh in shaders:
            self.fn("glDeleteShader", None, C.c_uint)(sh)
        return p

    def render(self, program, eye, parallax, palette, colour):
        self.fn("glUseProgram", None, C.c_uint)(program)
        loc = self.fn("glGetUniformLocation", C.c_int, C.c_uint, C.c_char_p)
        ud = np.zeros((16, 4), dtype=np.float32)
        ud[12, 3] = 4096
        ud[13] = (*eye, parallax)
        ud[14, 0] = palette
        self.fn("glUniform4fv", None, C.c_int, C.c_int, C.c_void_p)(
            loc(program, b"w_user"), 15, ud.ctypes.data)
        assert self.fn("glGetError", C.c_uint)() == 0, "userdata"
        self.fn("glUniform3f", None, C.c_int, C.c_float, C.c_float, C.c_float)(
            loc(program, b"e_eyepos"), *eye)
        assert self.fn("glGetError", C.c_uint)() == 0, "eye"
        textures = (C.c_uint * 2)()
        self.fn("glGenTextures", None, C.c_int, C.c_void_p)(2, textures)
        for unit, name, rgb in [(0, b"s_milk", (55, 55, 55)), (1, b"s_palette", colour)]:
            self.fn("glActiveTexture", None, C.c_uint)(0x84C0 + unit)
            self.fn("glBindTexture", None, C.c_uint, C.c_uint)(0x0DE1, textures[unit])
            self.fn("glTexParameteri", None, C.c_uint, C.c_uint, C.c_int)(0x0DE1, 0x2801, 0x2601)
            self.fn("glTexParameteri", None, C.c_uint, C.c_uint, C.c_int)(0x0DE1, 0x2800, 0x2601)
            colours = np.asarray(rgb, dtype=np.uint8).reshape(-1, 3)
            pixel = np.concatenate((colours, np.full((len(colours), 1), 255, dtype=np.uint8)), axis=1)
            self.fn("glTexImage2D", None, C.c_uint, C.c_int, C.c_int, C.c_int,
                    C.c_int, C.c_int, C.c_uint, C.c_uint, C.c_void_p)(
                        0x0DE1, 0, 0x1908, len(colours), 1, 0, 0x1908, 0x1401, pixel.ctypes.data)
            self.fn("glUniform1i", None, C.c_int, C.c_int)(loc(program, name), unit)
        assert self.fn("glGetError", C.c_uint)() == 0, "textures"
        self.fn("glViewport", None, C.c_int, C.c_int, C.c_int, C.c_int)(0, 0, 256, 256)
        begin = self.fn("glBegin", None, C.c_uint)
        vertex = self.fn("glVertex2f", None, C.c_float, C.c_float)
        end = self.fn("glEnd", None)
        begin(7)
        for x, y in [(-1,-1), (1,-1), (1,1), (-1,1)]:
            vertex(x, y)
        end()
        assert self.fn("glGetError", C.c_uint)() == 0, "quad"
        pixels = np.zeros((256, 256, 4), dtype=np.uint8)
        self.fn("glReadPixels", None, C.c_int, C.c_int, C.c_int, C.c_int,
                C.c_uint, C.c_uint, C.c_void_p)(0, 0, 256, 256, 0x1908, 0x1401, pixels.ctypes.data)
        self.fn("glDeleteTextures", None, C.c_int, C.c_void_p)(2, textures)
        error = self.fn("glGetError", C.c_uint)()
        assert error == 0, hex(error)
        return pixels[::-1, :, :3].copy()

    def close(self):
        self.fn("glDeleteFramebuffers", None, C.c_int, C.c_void_p)(1, C.byref(self.fbo))
        self.fn("glDeleteTextures", None, C.c_int, C.c_void_p)(1, C.byref(self.target))
        self.dll.wglMakeCurrent(None, None)
        self.dll.wglDeleteContext.argtypes = [C.c_void_p]
        self.dll.wglDeleteContext(self.rc)
        self.user.ReleaseDC.argtypes = [W.HWND, W.HDC]
        self.user.ReleaseDC(self.window, self.dc)
        self.user.DestroyWindow.argtypes = [W.HWND]
        self.user.DestroyWindow(self.window)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    root = Path(__file__).resolve().parents[1]
    sky = (root / "ftesurf/glsl/milk_sky.glsl").read_text()
    common = (root / "ftesurf/glsl/milk_common.h").read_text()
    fragment = "#version 130\n#define FRAGMENT_SHADER\nuniform vec4 w_user[16]; uniform vec3 e_eyepos; uniform sampler2D s_milk,s_palette;\n"
    fragment += "\n".join(line for line in sky.splitlines() if not line.startswith("!!") and not line.startswith("#include"))
    fragment = fragment.replace("varying vec3 pos;", common + "\nvarying vec3 pos;")
    gl = GL()
    images = {}
    programs = []
    try:
        program = gl.program(fragment)
        programs.append(program)
        for name, eye, parallax, palette, colour in [
            ("still", (0,0,0), 1, 1, (190,45,25)),
            ("still_repeat", (0,0,0), 1, 1, (190,45,25)),
            ("moved", (409.6,0,0), 1, 1, (190,45,25)),
            ("off_still", (0,0,0), 0, 1, (190,45,25)),
            ("off_moved", (409.6,0,0), 0, 1, (190,45,25)),
            ("cool", (0,0,0), 1, 1, (25,45,190)),
            ("mixed", (0,0,0), 1, 1, ((190,25,25),(25,25,190))),
            ("grey", (0,0,0), 1, 1, (100,100,100)),
            ("missing", (0,0,0), 1, 1, (107,112,117)),
            ("palette_off_warm", (0,0,0), 1, 0, (190,45,25)),
            ("palette_off_cool", (0,0,0), 1, 0, (25,45,190)),
            ("teleport", (1e7,-1e7,1e7), 1, 1, (190,45,25)),
        ]:
            images[name] = gl.render(program, eye, parallax, palette, colour)
            Image.fromarray(images[name]).save(args.output / (name + ".png"))
        assert np.array_equal(images["still"], images["still_repeat"])
        assert np.array_equal(images["off_still"], images["off_moved"])
        assert np.array_equal(images["palette_off_warm"], images["palette_off_cool"])
        moved_fraction = np.mean(np.any(images["still"] != images["moved"], axis=2))
        assert moved_fraction > 0.05, moved_fraction
        warm, cool = images["still"].mean((0,1)), images["cool"].mean((0,1))
        assert warm[0] > warm[2] * 2 and cool[2] > cool[0] * 2
        mixed = images["mixed"].astype(float)
        red_fraction = np.mean(mixed[:,:,0] > mixed[:,:,2] * 1.25)
        blue_fraction = np.mean(mixed[:,:,2] > mixed[:,:,0] * 1.25)
        assert red_fraction > 0.02 and blue_fraction > 0.02, (red_fraction, blue_fraction)
        assert np.max(np.ptp(images["grey"], axis=2)) == 0
        assert images["missing"].mean() > 10
        average_fragment = fragment
        for region in ["vec2(0.25, 0.25), vec2(0.25, 0.65)",
                       "vec2(0.75, 0.25), vec2(0.75, 0.65)",
                       "vec2(0.4, 0.85), vec2(0.6, 0.85)"]:
            average_fragment = average_fragment.replace(region, "vec2(0.25, 0.25), vec2(0.75, 0.25)")
        averaged_program = gl.program(average_fragment)
        programs.append(averaged_program)
        averaged = gl.render(averaged_program, (0,0,0), 1, 1, ((190,25,25),(25,25,190))).astype(float)
        assert not np.any(averaged[:,:,0] > averaged[:,:,2] * 1.25)
        assert not np.any(averaged[:,:,2] > averaged[:,:,0] * 1.25)
        # A disabled/reference shader proves real framebuffer readback, not intent.
        reference = gl.program("#version 130\nvoid main(){gl_FragColor=vec4(0.0,1.0,0.0,1.0);}")
        programs.append(reference)
        ref = gl.render(reference, (0,0,0), 0, 0, (0,0,0))
        assert np.all(ref == (0,255,0))
        Image.fromarray(ref).save(args.output / "reference.png")
        mutant = gl.program(fragment.replace("eye *= min", "eye = vec3(0.0); eye *= min"))
        programs.append(mutant)
        a = gl.render(mutant, (0,0,0), 1, 1, (190,45,25))
        b = gl.render(mutant, (409.6,0,0), 1, 1, (190,45,25))
        mutant_fraction = np.mean(np.any(a != b, axis=2))
        assert mutant_fraction < 0.05, "no-parallax mutant must fail moved-pixel threshold"
        # Read production hit positions as RGB: the nearer shell must move more.
        start = fragment.rindex("void main(void)")
        end = fragment.index("\n\tvec2 uv =", start)
        diagnostic = fragment[:end] + "\n gl_FragColor=vec4(vec3(nearp.x,midp.x,farp.x)*0.5+0.5,1.0);\n}\n#endif\n"
        depth_program = gl.program(diagnostic)
        programs.append(depth_program)
        depth_a = gl.render(depth_program, (0,0,0), 1, 1, (100,100,100))
        depth_b = gl.render(depth_program, (1228.8,0,0), 1, 1, (100,100,100))
        shifts = depth_b[128,128].astype(float) - depth_a[128,128].astype(float)
        assert shifts[0] > shifts[1] * 1.6 and shifts[1] > shifts[2] * 1.6, shifts
        equal_depth = gl.program(diagnostic.replace("skyHit(eye, d, 6.0)", "skyHit(eye, d, 3.0)")
                                .replace("skyHit(eye, d, 12.0)", "skyHit(eye, d, 3.0)"))
        programs.append(equal_depth)
        equal_a = gl.render(equal_depth, (0,0,0), 1, 1, (100,100,100))
        equal_b = gl.render(equal_depth, (1228.8,0,0), 1, 1, (100,100,100))
        equal_shifts = equal_b[128,128].astype(float) - equal_a[128,128].astype(float)
        assert np.all(equal_shifts == equal_shifts[0]), "equal-depth mutant must fail depth ordering"
        angles = [math.asin(0.1 / radius) for radius in (3,6,12)]
        report = dict(moved_pixel_fraction=float(moved_fraction), warm_mean=warm.tolist(),
                      cool_mean=cool.tolist(), depth_angles_radians=angles,
                      production_depth_pixel_shifts=shifts.tolist(), equal_depth_mutant="rejected",
                      mixed_red_pixel_fraction=float(red_fraction), mixed_blue_pixel_fraction=float(blue_fraction),
                      averaged_palette_mutant="rejected by mixed-hue detector",
                      reference="acted green framebuffer", mutant="no-parallax rejected",
                      no_parallax_mutant_pixel_fraction=float(mutant_fraction),
                      scope="production fragment pixels; engine/live lifecycle not tested")
        (args.output / "results.json").write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report, indent=2))
    finally:
        for p in programs:
            gl.fn("glDeleteProgram", None, C.c_uint)(p)
        gl.close()


if __name__ == "__main__":
    main()
