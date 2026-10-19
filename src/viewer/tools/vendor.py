"""Copy the part of noclip.website the run viewer needs into vendor/noclip.

    python tools/vendor.py <noclip checkout>

Follows relative imports from ROOTS, reading a file from stubs/ instead of the
checkout wherever stubs/ has one, and copies exactly that closure. Rerun it to
move to a new upstream commit; vendor/noclip/UPSTREAM.txt records which.
"""
import hashlib
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STUBS = os.path.join(HERE, 'stubs')
OUT = os.path.join(HERE, 'vendor', 'noclip')

# Small edits to upstream files, applied after the copy, each matching exactly
# once (vendor.py stops otherwise). UPSTREAM.txt marks a patched file.
PATCHES = [
    # The run viewer draws its line, zones and players into the main view's
    # colour and depth targets (src/viewer/src/world.ts): keep the depth target...
    ('SourceEngine/Main.ts',
     '    public outputColorTargetID: GfxrRenderTargetID | null = null;\n',
     '    public outputColorTargetID: GfxrRenderTargetID | null = null;\n'
     '    public outputDepthTargetID: GfxrRenderTargetID | null = null; // FTESurf: world.ts draws into it\n'),
    ('SourceEngine/Main.ts',
     '        const mainDepthTargetID = builder.createRenderTargetID(mainDepthDesc, `${this.name} - Main Depth`);\n',
     '        const mainDepthTargetID = builder.createRenderTargetID(mainDepthDesc, `${this.name} - Main Depth`);\n'
     '        this.outputDepthTargetID = mainDepthTargetID;\n'),
    ('SourceEngine/Main.ts',
     '        this.outputColorTargetID = null;\n',
     '        this.outputColorTargetID = null;\n'
     '        this.outputDepthTargetID = null;\n'),
    # ...and give the renderer one hook, after the main view, before bloom and grading.
    ('SourceEngine/Main.ts',
     '    public bspRenderers: BSPRenderer[] = [];\n',
     '    public bspRenderers: BSPRenderer[] = [];\n'
     '    public onWorldPasses: ((builder: GfxrGraphBuilder, color: GfxrRenderTargetID, depth: GfxrRenderTargetID) => void) | null = null; // FTESurf\n'),
    ('SourceEngine/Main.ts',
     '        const mainColorTargetID = assertExists(this.mainViewRenderer.outputColorTargetID);\n',
     '        const mainColorTargetID = assertExists(this.mainViewRenderer.outputColorTargetID);\n'
     '        if (this.onWorldPasses !== null)\n'
     '            this.onWorldPasses(builder, mainColorTargetID, assertExists(this.mainViewRenderer.outputDepthTargetID));\n'),
    # An entity whose model failed to load (a prop from content nobody provided)
    # still spawns, and spawn() looked its default animation up in a null model:
    # a TypeError every frame, and a black view (surf_prosurf, run 21127).
    ('SourceEngine/EntitySystem.ts',
     '        return this.modelStudio!.modelData.seq.findIndex((seq) => seq.label === label);\n',
     '        if (this.modelStudio === null) return -1; // FTESurf: the model failed to load\n'
     '        return this.modelStudio.modelData.seq.findIndex((seq) => seq.label === label);\n'),
    # P835: the per-frame CPU of a big surf map (surf_demise 49-85 fps, CPU-bound on this PC).
    # Each change gives the same answer with less work; tools/p835 measured them.
    # 1. The world walk: per view, the nodes with a leaf of the view's PVS beneath them
    #    (rebuilt when the PVS words change) -- the rest the leaf test rejects anyway --
    #    and each face added to the live set once per walk: a surf map's leaves list a
    #    face hundreds of times (surf_demise at its start: 350k adds for 1,670 faces).
    ('SourceEngine/Main.ts',
     '    public gatherLiveSets(liveFaceSet: Set<number> | null, liveLeafSet: Set<number> | null, view: SourceEngineView, nodeid: number = 0, modelMatrix: ReadonlyMat4 | null = null): void {\n'
     '        if (nodeid >= 0) {\n'
     '            // node\n'
     '            const node = this.bsp.nodelist[nodeid];\n'
     '\n'
     '            if (!view.frustum.contains(transformAABB(node.bbox, modelMatrix)))\n'
     '                return;\n'
     '\n'
     '            this.gatherLiveSets(liveFaceSet, liveLeafSet, view, node.child0, modelMatrix);\n'
     '            this.gatherLiveSets(liveFaceSet, liveLeafSet, view, node.child1, modelMatrix);\n',
     '    public lastGatherView: SourceEngineView | null = null; // FTESurf: the view the live sets hold\n'
     '    private pvsNodeCache = new Map<SourceEngineView, { words: Uint32Array, live: Uint8Array }>();\n'
     '    private faceStamp: Uint32Array | null = null;\n'
     '    private faceGen = 0;\n'
     '\n'
     '    private pvsLiveNodes(view: SourceEngineView): Uint8Array {\n'
     '        const words = view.pvs.words;\n'
     '        let c = this.pvsNodeCache.get(view);\n'
     '        if (c !== undefined) {\n'
     '            let same = true;\n'
     '            for (let i = 0; i < words.length; i++)\n'
     '                if (c.words[i] !== words[i]) { same = false; break; }\n'
     '            if (same)\n'
     '                return c.live;\n'
     '        } else {\n'
     '            c = { words: new Uint32Array(words.length), live: new Uint8Array(this.bsp.nodelist.length) };\n'
     '            this.pvsNodeCache.set(view, c);\n'
     '        }\n'
     '        c.words.set(words);\n'
     '        const live = c.live, nodes = this.bsp.nodelist, leaves = this.bsp.leaflist, pvs = view.pvs;\n'
     '        const mark = (id: number): boolean => {\n'
     '            if (id < 0)\n'
     '                return pvs.getBit(leaves[-id - 1].cluster);\n'
     '            const node = nodes[id];\n'
     '            const a = mark(node.child0), b = mark(node.child1);\n'
     '            live[id] = (a || b) ? 1 : 0;\n'
     '            return a || b;\n'
     '        };\n'
     '        mark(0);\n'
     '        return live;\n'
     '    }\n'
     '\n'
     '    public gatherLiveSets(liveFaceSet: Set<number> | null, liveLeafSet: Set<number> | null, view: SourceEngineView, nodeid: number = 0, modelMatrix: ReadonlyMat4 | null = null, live: Uint8Array | null = null): void {\n'
     '        if (nodeid === 0 && live === null) {\n'
     '            live = this.pvsLiveNodes(view);\n'
     '            if (this.faceStamp === null)\n'
     '                this.faceStamp = new Uint32Array(this.bsp.faceInfos.length);\n'
     '            this.faceGen = (this.faceGen + 1) >>> 0;\n'
     '            if (this.faceGen === 0) { this.faceStamp.fill(0); this.faceGen = 1; }\n'
     '        }\n'
     '        if (nodeid >= 0) {\n'
     '            // node\n'
     '            if (live !== null && live[nodeid] === 0)\n'
     '                return;\n'
     '            const node = this.bsp.nodelist[nodeid];\n'
     '\n'
     '            if (!view.frustum.contains(transformAABB(node.bbox, modelMatrix)))\n'
     '                return;\n'
     '\n'
     '            this.gatherLiveSets(liveFaceSet, liveLeafSet, view, node.child0, modelMatrix, live);\n'
     '            this.gatherLiveSets(liveFaceSet, liveLeafSet, view, node.child1, modelMatrix, live);\n'),
    ('SourceEngine/Main.ts',
     '            if (liveFaceSet !== null)\n'
     '                for (let i = 0; i < leaf.faces.length; i++)\n'
     '                    liveFaceSet.add(leaf.faces[i]);\n',
     '            if (liveFaceSet !== null) {\n'
     '                const stamp = this.faceStamp, gen = this.faceGen;\n'
     '                for (let i = 0; i < leaf.faces.length; i++) {\n'
     '                    const f = leaf.faces[i];\n'
     '                    if (stamp === null) {\n'
     '                        liveFaceSet.add(f);\n'
     '                    } else if (stamp[f] !== gen) {\n'
     '                        stamp[f] = gen;\n'
     '                        liveFaceSet.add(f);\n'
     '                    }\n'
     '                }\n'
     '            }\n'),
    # 2. The water test walked the world again with the main view, straight after the
    #    main view's own walk had filled the same set; and searched every node for water.
    ('SourceEngine/Main.ts',
     '            this.liveLeafSet.clear();\n',
     '            this.liveLeafSet.clear();\n'
     '            this.lastGatherView = null;\n'),
    ('SourceEngine/Main.ts',
     '                this.gatherLiveSets(this.liveFaceSet, this.liveLeafSet, renderContext.currentView);\n',
     '                this.gatherLiveSets(this.liveFaceSet, this.liveLeafSet, renderContext.currentView);\n'
     '                this.lastGatherView = renderContext.currentView;\n'),
    ('SourceEngine/Main.ts',
     '            bspRenderer.gatherLiveSets(null, bspRenderer.liveLeafSet, this.mainViewRenderer.mainView);\n',
     '            if (bspRenderer.lastGatherView !== this.mainViewRenderer.mainView)\n'
     '                bspRenderer.gatherLiveSets(null, bspRenderer.liveLeafSet, this.mainViewRenderer.mainView);\n'),
    ('SourceEngine/BSPFile.ts',
     '    private findLeafWaterForPointR(p: ReadonlyVec3, liveLeafSet: Set<number>, nodeid: number): BSPLeafWaterData | null {\n'
     '        if (nodeid < 0) {\n',
     '    private waterBelow: Uint8Array | null = null; // FTESurf: nodes with a water leaf beneath\n'
     '\n'
     '    private markWaterBelow(): Uint8Array {\n'
     '        const below = new Uint8Array(this.nodelist.length);\n'
     '        const mark = (id: number): boolean => {\n'
     '            if (id < 0)\n'
     '                return this.leaflist[-id - 1].leafwaterdata !== -1;\n'
     '            const node = this.nodelist[id];\n'
     '            const a = mark(node.child0), b = mark(node.child1);\n'
     '            below[id] = (a || b) ? 1 : 0;\n'
     '            return a || b;\n'
     '        };\n'
     '        mark(0);\n'
     '        return below;\n'
     '    }\n'
     '\n'
     '    private findLeafWaterForPointR(p: ReadonlyVec3, liveLeafSet: Set<number>, nodeid: number): BSPLeafWaterData | null {\n'
     '        if (nodeid >= 0 && this.waterBelow !== null && this.waterBelow[nodeid] === 0)\n'
     '            return null;\n'
     '        if (nodeid < 0) {\n'),
    ('SourceEngine/BSPFile.ts',
     '        if (this.leafwaterdata.length === 0)\n'
     '            return null;\n'
     '\n'
     '        return this.findLeafWaterForPointR(p, liveLeafSet, 0);\n',
     '        if (this.leafwaterdata.length === 0)\n'
     '            return null;\n'
     '\n'
     '        if (this.waterBelow === null)\n'
     '            this.waterBelow = this.markWaterBelow();\n'
     '        return this.findLeafWaterForPointR(p, liveLeafSet, 0);\n'),
    # 3. An entity's PVS test walked the tree for its bounds every frame (206 a frame on
    #    surf_demise); bounds that held still since the last frame keep their clusters.
    ('SourceEngine/EntitySystem.ts',
     '    public checkVisible(renderContext: SourceRenderContext): boolean {\n',
     '    private visBox = new AABB(); // FTESurf: last frame\'s bounds, and the clusters under them\n'
     '    private visClusters: number[] | null = null;\n'
     '\n'
     '    public checkVisible(renderContext: SourceRenderContext): boolean {\n'),
    ('SourceEngine/EntitySystem.ts',
     '            const bsp = this.bspRenderer.bsp, pvs = renderContext.currentView.pvs;\n'
     '            let visible = false;\n',
     '            const bsp = this.bspRenderer.bsp, pvs = renderContext.currentView.pvs;\n'
     '            const b = this.visBox;\n'
     '            if (b.min[0] === scratchAABB.min[0] && b.min[1] === scratchAABB.min[1] && b.min[2] === scratchAABB.min[2] &&\n'
     '                b.max[0] === scratchAABB.max[0] && b.max[1] === scratchAABB.max[1] && b.max[2] === scratchAABB.max[2]) {\n'
     '                if (this.visClusters === null) {\n'
     '                    const clusters: number[] = [];\n'
     '                    bsp.queryAABB(scratchAABB, (leaf) => { clusters.push(leaf.cluster); return true; });\n'
     '                    this.visClusters = clusters;\n'
     '                }\n'
     '                const c = this.visClusters;\n'
     '                for (let i = 0; i < c.length; i++)\n'
     '                    if (pvs.getBit(c[i]))\n'
     '                        return true;\n'
     '                return false;\n'
     '            }\n'
     '            b.copy(scratchAABB);\n'
     '            this.visClusters = null;\n'
     '            let visible = false;\n'),
]

ROOTS = [
    'SourceEngine/Main.ts',
    'SourceEngine/BSPFile.ts',
    'SourceEngine/VPK.ts',
    'gfx/platform/GfxPlatformWebGL2.ts',
    'gfx/helpers/RenderGraphHelpers.ts',
    'Camera.ts',
    'InputManager.ts',
    'DataFetcher.ts',
    'DataShare.ts',
    'SceneBase.ts',
]

IMPORT = re.compile(r"""(?:import|export)\s[^'";]*?from\s*['"]([^'"]+)['"]"""
                    r"""|import\s*\(\s*['"]([^'"]+)['"]\s*\)"""
                    r"""|import\s+['"]([^'"]+)['"]""", re.S)


def source(rel, src):
    stub = os.path.join(STUBS, rel)
    return stub if os.path.isfile(stub) else os.path.join(src, rel)


def resolve(rel_dir, spec, src):
    p = os.path.normpath(os.path.join(rel_dir, spec)).replace('\\', '/')
    cands = [p[:-3] + '.ts'] if p.endswith('.js') else []
    cands += [p, p + '.ts']
    for c in cands:
        if os.path.isfile(source(c, src)):
            return c
    raise SystemExit(f'unresolved import {spec!r} from {rel_dir}')


def main():
    src = os.path.join(sys.argv[1], 'src')
    commit = subprocess.run(['git', '-C', sys.argv[1], 'rev-parse', 'HEAD'],
                            capture_output=True, text=True, check=True).stdout.strip()
    seen, todo, bare = set(), list(ROOTS), set()
    while todo:
        rel = todo.pop()
        if rel in seen:
            continue
        seen.add(rel)
        if not rel.endswith('.ts'):
            continue
        with open(source(rel, src), encoding='utf-8') as fh:
            text = fh.read()
        for m in IMPORT.finditer(text):
            spec = m.group(1) or m.group(2) or m.group(3)
            if spec.startswith('.'):
                todo.append(resolve(os.path.dirname(rel), spec, src))
            else:
                bare.add(spec)

    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    lines = [f'noclip.website {commit}', 'https://github.com/magcius/noclip.website',
             'MIT licence: LICENSE beside this file.',
             'Files marked "stub" are FTESurf replacements from src/viewer/stubs/;',
             '"patched" ones carry the edits in tools/vendor.py PATCHES.', '']
    for rel in sorted(seen):
        frm = source(rel, src)
        dst = os.path.join(OUT, 'src', rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        # LF, as .gitattributes stores it: upstream has CRLF files, and a digest
        # of the CRLF copy would not match a checkout.
        with open(frm, 'rb') as fh:
            data = fh.read().replace(b'\r\n', b'\n')
        tag = 'stub' if frm.startswith(STUBS) else 'upstream'
        for prel, old, new in PATCHES:
            if prel == rel:
                n = data.count(old.encode())
                if n != 1:
                    raise SystemExit(f'patch for {rel} matches {n} times: {old[:60]!r}')
                data = data.replace(old.encode(), new.encode())
                tag = 'patched'
        with open(dst, 'wb') as fh:
            fh.write(data)
        digest = hashlib.sha256(data).hexdigest()[:16]
        lines.append(f'{digest} {tag:8} {rel}')
    with open(os.path.join(sys.argv[1], 'LICENSE'), 'rb') as fh:
        lic = fh.read().replace(b'\r\n', b'\n')
    with open(os.path.join(OUT, 'LICENSE'), 'wb') as fh:
        fh.write(lic)
    lines += ['', 'bare imports: ' + ', '.join(sorted(bare))]
    with open(os.path.join(OUT, 'UPSTREAM.txt'), 'w', encoding='utf-8', newline='\n') as fh:
        fh.write('\n'.join(lines) + '\n')
    print(f'{len(seen)} files from {commit[:12]}; bare imports: {sorted(bare)}')


if __name__ == '__main__':
    main()
