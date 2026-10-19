// The frame loop around noclip's SourceRenderer: noclip's Viewer without its UI,
// WebGPU or WebXR, and a camera the run drives instead of the mouse.
import { mat4, vec3, vec4 } from 'gl-matrix';
import { Camera, FPSCameraController } from '../vendor/noclip/src/Camera.js';
import { DataShare } from '../vendor/noclip/src/DataShare.js';
import { AntialiasingMode } from '../vendor/noclip/src/gfx/helpers/RenderGraphHelpers.js';
import { GfxDevice, GfxSwapChain } from '../vendor/noclip/src/gfx/platform/GfxPlatform.js';
import { createSwapChainForWebGL2, GfxPlatformWebGL2Config } from '../vendor/noclip/src/gfx/platform/GfxPlatformWebGL2.js';
import InputManager from '../vendor/noclip/src/InputManager.js';
import { SceneContext } from '../vendor/noclip/src/SceneBase.js';
import { SceneGfx, ViewerRenderInput } from '../vendor/noclip/src/viewer.js';
import { DataFetcher } from '../vendor/noclip/src/DataFetcher.js';

// noclip's space from Source's (SourceEngine/Main.ts): Source is Z-up.
const noclipFromSource = mat4.fromValues(0, 0, -1, 0, -1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 1);
const DEG = Math.PI / 180;

export class View {
    public device: GfxDevice;
    public camera = new Camera();
    public input: InputManager;
    public scene: SceneGfx | null = null;
    public context: SceneContext;
    public free = new FPSCameraController();
    public freeOn = false;
    public fovY = 90 * DEG;   // set from the horizontal FOV each frame

    private swapChain: GfxSwapChain;
    private renderInput: ViewerRenderInput;
    private sceneTime = 0;
    private clipFromWorld = mat4.create();

    constructor(public canvas: HTMLCanvasElement, fetcher: DataFetcher) {
        const gl = canvas.getContext('webgl2', { antialias: false, preserveDrawingBuffer: false, depth: false, stencil: false });
        if (gl === null)
            throw new Error('This browser has no WebGL 2.');
        this.swapChain = createSwapChainForWebGL2(gl, new GfxPlatformWebGL2Config());
        this.device = this.swapChain.getDevice();
        this.input = new InputManager(canvas);
        this.renderInput = {
            camera: this.camera, time: 0, deltaTime: 0, backbufferWidth: 0, backbufferHeight: 0,
            onscreenTexture: null!, antialiasingMode: AntialiasingMode.FXAA, mouseLocation: this.input,
            debugConsole: { addInfoLine() {} },
        };
        this.context = {
            device: this.device, dataFetcher: fetcher, dataShare: new DataShare(),
            uiContainer: document.createElement('div'), destroyablePool: [], inputManager: this.input,
            viewerInput: this.renderInput, sceneLoader: { loadSceneById() {} }, initialSceneTime: 0,
        };
        this.free.camera = this.camera;
    }

    // Source origin + view angles (degrees) to the camera, as the game's
    // AngleVectors would place it: right = (sy, -cy, 0), up = (sp cy, sp sy, cp).
    public placeEye(x: number, y: number, z: number, pitch: number, yaw: number): void {
        const sp = Math.sin(pitch * DEG), cp = Math.cos(pitch * DEG);
        const sy = Math.sin(yaw * DEG), cy = Math.cos(yaw * DEG);
        const w = mat4.fromValues(
            sy, -cy, 0, 0,                  // camera +X: right
            sp * cy, sp * sy, cp, 0,        // camera +Y: up
            -cp * cy, -cp * sy, sp, 0,      // camera +Z: back
            x, y, z, 1);
        mat4.mul(this.camera.worldMatrix, noclipFromSource, w);
        this.camera.worldMatrixUpdated();
    }

    // Source-space point to CSS pixels, or null behind the camera.
    public project(x: number, y: number, z: number, out: vec3): vec3 | null {
        const p = vec4.fromValues(x, y, z, 1);
        vec4.transformMat4(p, p, this.clipFromWorld);
        if (p[3] <= 1) return null;
        const w = this.canvas.clientWidth, h = this.canvas.clientHeight;
        return vec3.set(out, (p[0] / p[3] * 0.5 + 0.5) * w, (0.5 - p[1] / p[3] * 0.5) * h, p[3]);
    }

    public frame(dtMs: number, hfovDeg: number): void {
        const dpr = Math.min(window.devicePixelRatio || 1, 2);
        const w = Math.max(1, Math.round(this.canvas.clientWidth * dpr));
        const h = Math.max(1, Math.round(this.canvas.clientHeight * dpr));
        if (this.canvas.width !== w || this.canvas.height !== h) {
            this.canvas.width = w;
            this.canvas.height = h;
        }
        const cam = this.camera;
        cam.clipSpaceNearZ = this.device.queryVendorInfo().clipSpaceNearZ;
        cam.newFrame();
        const aspect = w / h;
        // Source's fov is horizontal at 4:3; the game widens it with the screen.
        const vfov = 2 * Math.atan(Math.tan(hfovDeg * DEG / 2) * 0.75);
        cam.fovY = vfov;
        cam.aspect = aspect;
        cam.setClipPlanes(4);
        if (this.freeOn)
            this.free.update(this.input, dtMs);

        mat4.mul(this.clipFromWorld, cam.clipFromWorldMatrix, noclipFromSource);

        this.renderInput.deltaTime = dtMs;
        this.sceneTime += dtMs;
        this.renderInput.time = this.sceneTime;
        this.renderInput.backbufferWidth = w;
        this.renderInput.backbufferHeight = h;
        this.swapChain.configureSwapChain(w, h);
        this.device.beginFrame();
        this.renderInput.onscreenTexture = this.swapChain.getOnscreenTexture();
        if (this.scene !== null)
            this.scene.render(this.device, this.renderInput);
        this.device.endFrame();
        this.input.afterFrame();
    }
}
