// FTESurf stub for noclip's WebGPU backend: the viewer is WebGL2 only, and
// upstream's backend compiles GLSL through the Rust crate this build drops.
// LuminanceHistogram calls this only on a WebGPU device.
import type { GfxDevice } from './GfxPlatform.js';

export function gfxDeviceGetImpl_WebGPU(_device: GfxDevice): { device: any } {
    throw new Error('WebGPU is not built into the run viewer');
}
