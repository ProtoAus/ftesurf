// FTESurf stub for noclip's DebugFloaters.ts: its decorators only feed noclip's
// debug panels (and need reflect-metadata), so here they decorate nothing.
type Decorator = (target: any, key: string) => void;
const none: Decorator = () => {};

export function dfShow(): Decorator { return none; }
export function dfHide(): Decorator { return none; }
export function dfRange(_min?: number, _max?: number, _step?: number): Decorator { return none; }
export function dfSigFigs(_v?: number): Decorator { return none; }
export function dfUsePercent(_v?: boolean): Decorator { return none; }
export function dfLabel(_v: string): Decorator { return none; }

export class FloatingPanel {
    [k: string]: any;
}
