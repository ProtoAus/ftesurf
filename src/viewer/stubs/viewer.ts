// FTESurf stub for noclip's viewer.ts: the interfaces the renderer is written
// against, without noclip's Viewer class (its WebGPU, WebXR and UI imports).
// The run viewer's own frame loop is src/viewer/src/view.ts.
import * as UI from './ui.js';
import { CameraController, Camera } from './Camera.js';
import { GfxDevice, GfxTexture } from './gfx/platform/GfxPlatform.js';
import { AntialiasingMode } from './gfx/helpers/RenderGraphHelpers.js';
import { WebXRContext } from './WebXR.js';
import { mat4 } from 'gl-matrix';
import ArrayBufferSlice from './ArrayBufferSlice.js';

export interface ViewerUpdateInfo {
    time: number;
    webXRContext: WebXRContext | null;
}

export interface Texture {
    gfxTexture: GfxTexture;
    extraInfo?: Map<string, string> | null;
}

interface MouseLocation {
    mouseX: number;
    mouseY: number;
}

export interface DebugConsole {
    addInfoLine(line: string): void;
}

export interface ViewerRenderInput {
    camera: Camera;
    time: number;
    deltaTime: number;
    backbufferWidth: number;
    backbufferHeight: number;
    onscreenTexture: GfxTexture;
    antialiasingMode: AntialiasingMode;
    mouseLocation: MouseLocation;
    debugConsole: DebugConsole;
}

export interface SceneGfx {
    textureHolder?: UI.TextureListHolder;
    createPanels?(): UI.Panel[];
    createCameraController?(): CameraController;
    adjustCameraController?(c: CameraController): void;
    getDefaultWorldMatrix?(dst: mat4): void;
    serializeSaveState?(dst: ArrayBuffer, offs: number): number;
    deserializeSaveState?(src: ArrayBufferSlice): void;
    onstatechanged?: () => void;
    render(device: GfxDevice, renderInput: ViewerRenderInput): void;
    destroy(device: GfxDevice): void;
}
