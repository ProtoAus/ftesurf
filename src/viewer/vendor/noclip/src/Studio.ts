// FTESurf stub for noclip's Studio.ts (its camera-animation editor). Only
// Camera.ts's StudioCameraController names these, and the viewer never makes one.
import { vec3 } from 'gl-matrix';

export class InterpolationStep {
    public pos: vec3 = vec3.create();
    public lookAtPos: vec3 = vec3.create();
    public bank: number = 0;
}

export class CameraAnimationManager {
    [k: string]: any;
}

export class StudioPanel {
    [k: string]: any;
}
