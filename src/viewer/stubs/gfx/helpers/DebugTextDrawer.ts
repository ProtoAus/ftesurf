// FTESurf stub for noclip's DebugTextDrawer.ts, which draws debug text with a
// Wii font through the GameCube renderer. GfxRenderHelper imports it lazily and
// treats null as "no debug text".
import type { SceneContext } from '../../SceneBase.js';
import type { TextDrawer } from './DebugThumbnailHelpers.js';

export type DebugTextDrawer = TextDrawer;

export async function makeDebugTextDrawer(_context: SceneContext): Promise<DebugTextDrawer | null> {
    return null;
}
