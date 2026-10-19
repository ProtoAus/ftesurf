// FTESurf stub for noclip's ui.ts (3,036 lines of noclip's own interface).
// The run viewer draws its own controls; these names exist so the vendored
// renderer type-checks and SourceRenderer.createPanels(), never called, links.
import type * as Viewer from './viewer.js';

export const COOL_BLUE_COLOR = 'rgb(20, 105, 215)';
export const RENDER_HACKS_ICON = '';

export interface TextureListHolder {
    textureNames: string[];
    getViewerTexture(i: number): Promise<Viewer.Texture>;
    onnewtextures: (() => void) | null;
}

class Widget {
    [k: string]: any;
    public elem: HTMLElement = document.createElement('div');
}

export class Panel extends Widget {}
export class Checkbox extends Widget {
    constructor(_label?: string, public checked: boolean = false) { super(); }
}
export class Slider extends Widget {}
