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
     '            if (this.bspRenderers.length > 1 || bspRenderer.lastGatherView !== this.mainViewRenderer.mainView) // FTESurf: one BSP only\n'
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
    # P839: static props with no material proxy move at the first view that draws them.
    ('SourceEngine/StaticDetailObject.ts',
     '    private lightingOrigin = vec3.create();\n\n    constructor(renderContext: SourceRenderContext, private bspRenderer: BSPRenderer, private staticProp: StaticProp) {\n',
     "    private lightingOrigin = vec3.create();\n    private moveView: SourceRenderContext['currentView'] | null = null; // FTESurf: see movement\n    private moveKind = 0;   // FTESurf: 0 a material still loading, 1 a proxy (moves every frame), 2 none\n\n    constructor(renderContext: SourceRenderContext, private bspRenderer: BSPRenderer, private staticProp: StaticProp) {\n"),
    ('SourceEngine/StaticDetailObject.ts',
     '    public movement(renderContext: SourceRenderContext): void {\n        if (this.studioModelInstance !== null)\n            this.studioModelInstance.movement(renderContext);\n    }\n',
     "    // FTESurf: for a prop with no material proxy, what movement sets ($color/$alpha, eyes)\n    // is read only when it is drawn and depends only on the view current here (the main\n    // view), so it runs at the first view that draws the prop, with this view put back. A\n    // proxy can keep state in its material's params between calls (an Add into its own\n    // source), so a prop with one, or with a material still loading, moves every frame.\n    public movement(renderContext: SourceRenderContext): void {\n        this.moveView = null;\n        if (this.studioModelInstance === null)\n            return;\n        if (this.moveKind === 0)\n            this.moveKind = this.proxyKind();\n        if (this.moveKind === 2)\n            this.moveView = renderContext.currentView;\n        else\n            this.studioModelInstance.movement(renderContext);\n    }\n\n    private proxyKind(): number {\n        for (const part of (this.studioModelInstance as any).bodyPartInstance) {\n            for (const mesh of part.getLODInstance(0).meshInstance) {\n                const m = mesh.materialInstance;\n                if (m === null || !m.isMaterialLoaded())\n                    return 0;\n                if (m.proxyDriver !== null)\n                    return 1;\n            }\n        }\n        return 2;\n    }\n"),
    ('SourceEngine/StaticDetailObject.ts',
     '        if (!visible)\n            return;\n\n        if ((this as any).debug)\n',
     '        if (!visible)\n            return;\n\n        if (this.moveView !== null) {\n            const view = renderContext.currentView;\n            renderContext.currentView = this.moveView;\n            this.moveView = null;\n            try {\n                this.studioModelInstance.movement(renderContext);\n            } catch {\n                // Not drawn this frame; from the next it moves where upstream does, and\n                // throws there, before anything of the frame is prepared.\n                this.moveKind = 1;\n                return;\n            } finally {\n                renderContext.currentView = view;\n            }\n        }\n\n        if ((this as any).debug)\n'),
    # P855: clientmaterial is a runtime pointer slot like `material` (whose assert upstream
    # already dropped); Propper writes 1, and the assert threw the model away: 46 of
    # surf_null's 81 static props never drew.
    ('SourceEngine/Studio.ts',
     '            assert(clientmaterial === 0);\n',
     '            // FTESurf: a stale pointer slot like material above (Propper writes 1); not checked.\n'),
    # P855: on an HDR map Chromium turns auto-exposure on, whose histogram asks for the debug
    # canvas; that reads noclip's own page (window.main), which the viewer has not, and the
    # 3D view failed on every frame of every HDR map.
    ('DebugJunk.ts',
     '        window.main.toplevel.insertBefore(canvas, window.main.canvas);\n',
     '        window.main?.toplevel.insertBefore(canvas, window.main.canvas); // FTESurf: no noclip page\n'),
]

PATCHES += [
    # P1447: Strata (BSP v25) maps, and v20/v21 maps carrying the same wide lumps. Every layout
    # follows its lump's OWN version, as plugins/hl2/mod_vbsp.c does; the ones the engine does not
    # read were measured on the library's 133 v25 maps (tools/p1447-viewer.md).
    ('SourceEngine/BSPFile.ts',
     '        assert(this.version === 19 || this.version === 20 || this.version === 21  || this.version === 22);\n',
     '        assert(this.version === 19 || this.version === 20 || this.version === 21  || this.version === 22 || this.version === 25); // FTESurf P1447: Strata\n'),
    ('SourceEngine/BSPFile.ts',
     '''        function getLumpData(lumpType: LumpType, expectedVersion: number = 0): ArrayBufferSlice {
            const [buffer, version] = getLumpDataEx(lumpType);
            if (buffer.byteLength !== 0)
                assert(version === expectedVersion);
            return buffer;
        }
''',
     '''        function getLumpData(lumpType: LumpType, expectedVersion: number = 0): ArrayBufferSlice {
            const [buffer, version] = getLumpDataEx(lumpType);
            if (buffer.byteLength !== 0)
                assert(version === expectedVersion);
            return buffer;
        }

        // FTESurf P1447: a lump whose layout follows its own version. Any other version still asserts.
        function getLumpDataV(lumpType: LumpType, versions: number[]): [ArrayBufferSlice, number] {
            const [buffer, version] = getLumpDataEx(lumpType);
            if (buffer.byteLength !== 0)
                assert(versions.includes(version));
            return [buffer, buffer.byteLength !== 0 ? version : versions[0]];
        }
'''),
    ('SourceEngine/BSPFile.ts',
     '        const entitiesStr = decodeString(getLumpData(LumpType.ENTITIES));\n',
     '        const entitiesStr = decodeString(getLumpDataV(LumpType.ENTITIES, [0, 1])[0]); // FTESurf P1447: v1 is the same text\n'),
    ('SourceEngine/BSPFile.ts',
     '''        const nodes = getLumpData(LumpType.NODES).createDataView();

        const primindices = getLumpData(LumpType.PRIMINDICES).createTypedArray(Uint16Array);
        const primitives = getLumpData(LumpType.PRIMITIVES).createDataView();
''',
     '''        // FTESurf P1447: NODES v1, PRIMITIVES/PRIMINDICES v1, VERTNORMALINDICES v1 are 32-bit.
        const [nodesLump, nodesVersion] = getLumpDataV(LumpType.NODES, [0, 1]);
        const nodes = nodesLump.createDataView();

        const [primindicesLump, primindicesVersion] = getLumpDataV(LumpType.PRIMINDICES, [0, 1]);
        const primindices: Uint16Array | Uint32Array = primindicesVersion === 1 ?
            primindicesLump.createTypedArray(Uint32Array) : primindicesLump.createTypedArray(Uint16Array);
        const [primitivesLump, primitivesVersion] = getLumpDataV(LumpType.PRIMITIVES, [0, 1]);
        const primitives = primitivesLump.createDataView();
'''),
    ('SourceEngine/BSPFile.ts',
     '        const vertnormalindices = getLumpData(LumpType.VERTNORMALINDICES).createTypedArray(Uint16Array);\n',
     '''        const [vniLump, vniVersion] = getLumpDataV(LumpType.VERTNORMALINDICES, [0, 1]);
        const vertnormalindices: Uint16Array | Uint32Array = vniVersion === 1 ?
            vniLump.createTypedArray(Uint32Array) : vniLump.createTypedArray(Uint16Array);
'''),
    ('SourceEngine/BSPFile.ts',
     '        const worldlights = worldlightsLump.createDataView();\n',
     '''        // FTESurf P1447: Strata's v2 record is unverified; those props light from the ambient cubes alone.
        const worldlights = (worldlightsVersion <= 1 ? worldlightsLump : worldlightsLump.subarray(0, 0)).createDataView();
'''),
    ('SourceEngine/BSPFile.ts',
     '        for (let idx = 0x00; idx < nodes.byteLength; idx += 0x20) {\n',
     '        for (let idx = 0x00; idx < nodes.byteLength; idx += (nodesVersion === 1 ? 0x30 : 0x20)) { // FTESurf P1447: strata_dnode_t\n'),
    ('SourceEngine/BSPFile.ts',
     '''            const bboxMinX = nodes.getInt16(idx + 0x0C, true);
            const bboxMinY = nodes.getInt16(idx + 0x0E, true);
            const bboxMinZ = nodes.getInt16(idx + 0x10, true);
            const bboxMaxX = nodes.getInt16(idx + 0x12, true);
            const bboxMaxY = nodes.getInt16(idx + 0x14, true);
            const bboxMaxZ = nodes.getInt16(idx + 0x16, true);
            const bbox = new AABB(bboxMinX, bboxMinY, bboxMinZ, bboxMaxX, bboxMaxY, bboxMaxZ);
            const firstface = nodes.getUint16(idx + 0x18, true);
            const numfaces = nodes.getUint16(idx + 0x1A, true);
            const area = nodes.getInt16(idx + 0x1C, true);
''',
     '''            const nw = nodesVersion === 1;
            const rdn = (o16: number, o32: number) => nw ? nodes.getFloat32(idx + o32, true) : nodes.getInt16(idx + o16, true);
            const bboxMinX = rdn(0x0C, 0x0C);
            const bboxMinY = rdn(0x0E, 0x10);
            const bboxMinZ = rdn(0x10, 0x14);
            const bboxMaxX = rdn(0x12, 0x18);
            const bboxMaxY = rdn(0x14, 0x1C);
            const bboxMaxZ = rdn(0x16, 0x20);
            const bbox = new AABB(bboxMinX, bboxMinY, bboxMinZ, bboxMaxX, bboxMaxY, bboxMaxZ);
            const firstface = nw ? nodes.getUint32(idx + 0x24, true) : nodes.getUint16(idx + 0x18, true);
            const numfaces = nw ? nodes.getUint32(idx + 0x28, true) : nodes.getUint16(idx + 0x1A, true);
            const area = nodes.getInt16(idx + (nw ? 0x2C : 0x1C), true);
'''),
    ('SourceEngine/BSPFile.ts',
     '        const edges = getLumpData(LumpType.EDGES).createTypedArray(Uint16Array);\n',
     '''        const [edgesLump, edgesVersion] = getLumpDataV(LumpType.EDGES, [0, 1]); // FTESurf P1447: v1 is 32-bit
        const edges: Uint16Array | Uint32Array = edgesVersion === 1 ?
            edgesLump.createTypedArray(Uint32Array) : edgesLump.createTypedArray(Uint16Array);
'''),
    ('SourceEngine/BSPFile.ts',
     '''        let facelist: DataView | null = null;
        if (this.usingHDR)
            facelist = getLumpData(LumpType.FACES_HDR, 1).createDataView();
        if (facelist === null || facelist.byteLength === 0)
            facelist = getLumpData(LumpType.FACES, 1).createDataView();
''',
     '''        // FTESurf P1447: FACES v2 (Strata) is strata_dface_t, 72 bytes of 32-bit fields.
        let facelist: DataView | null = null;
        let facesVersion = 1;
        if (this.usingHDR) {
            const [l, v] = getLumpDataV(LumpType.FACES_HDR, [1, 2]);
            facelist = l.createDataView(); facesVersion = v;
        }
        if (facelist === null || facelist.byteLength === 0) {
            const [l, v] = getLumpDataV(LumpType.FACES, [1, 2]);
            facelist = l.createDataView(); facesVersion = v;
        }
        const fw = facesVersion === 2;
        const faceStride = fw ? 0x48 : 0x38;
'''),
    ('SourceEngine/BSPFile.ts',
     '''        for (let i = 0, idx = 0x00; idx < facelist.byteLength; i++, idx += 0x38, numfaces++) {
            const numedges = facelist.getUint16(idx + 0x08, true);
            const texinfo = facelist.getUint16(idx + 0x0A, true);
''',
     '''        for (let i = 0, idx = 0x00; idx < facelist.byteLength; i++, idx += faceStride, numfaces++) {
            const numedges = fw ? facelist.getUint32(idx + 0x0C, true) : facelist.getUint16(idx + 0x08, true);
            const texinfo = fw ? facelist.getUint32(idx + 0x10, true) : facelist.getUint16(idx + 0x0A, true);
'''),
    ('SourceEngine/BSPFile.ts',
     '''            const lightofs = facelist.getInt32(idx + 0x14, true);
            const m_LightmapTextureSizeInLuxels = nArray(2, (i) => facelist!.getUint32(idx + 0x24 + i * 4, true));
''',
     '''            const lightofs = facelist.getInt32(idx + (fw ? 0x20 : 0x14), true);
            const m_LightmapTextureSizeInLuxels = nArray(2, (i) => facelist!.getUint32(idx + (fw ? 0x30 : 0x24) + i * 4, true));
'''),
    ('SourceEngine/BSPFile.ts',
     '                const style = facelist.getUint8(idx + 0x10 + j);\n',
     '                const style = facelist.getUint8(idx + (fw ? 0x1C : 0x10) + j);\n'),
    ('SourceEngine/BSPFile.ts',
     '''            if (lightofs !== -1)
                samples = lighting.subarray(lightofs, srcLightmapSize).createTypedArray(Uint8Array);
''',
     '''            // FTESurf P1447: an unlit map (bhop_perspective) has no lighting lump at all.
            if (lightofs !== -1 && lighting !== null && lightofs + srcLightmapSize <= lighting.byteLength)
                samples = lighting.subarray(lightofs, srcLightmapSize).createTypedArray(Uint8Array);
'''),
    ('SourceEngine/BSPFile.ts',
     '''            const idx = face.index * 0x38;
            const planenum = facelist.getUint16(idx + 0x00, true);
            const side = facelist.getUint8(idx + 0x02);
            const onNode = !!facelist.getUint8(idx + 0x03);
            const firstedge = facelist.getUint32(idx + 0x04, true);
            const numedges = facelist.getUint16(idx + 0x08, true);
            const dispinfo = facelist.getInt16(idx + 0x0C, true);
            const surfaceFogVolumeID = facelist.getUint16(idx + 0x0E, true);

            const area = facelist.getFloat32(idx + 0x18, true);
            const m_LightmapTextureMinsInLuxels = nArray(2, (i) => facelist!.getInt32(idx + 0x1C + i * 4, true));
            const m_LightmapTextureSizeInLuxels = nArray(2, (i) => facelist!.getUint32(idx + 0x24 + i * 4, true));
            const origFace = facelist.getUint32(idx + 0x2C, true);
            const m_NumPrimsRaw = facelist.getUint16(idx + 0x30, true);
            const m_NumPrims = m_NumPrimsRaw & 0x7FFF;
            const firstPrimID = facelist.getUint16(idx + 0x32, true);
            const smoothingGroups = facelist.getUint32(idx + 0x34, true);
''',
     '''            // FTESurf P1447: strata_dface_t offsets (fw) beside dface_t's. Strata's prim word has
            // EnableShadows in bit 0 and the count above it (measured: raw >>> 1 sums to the prims).
            const idx = face.index * faceStride;
            const planenum = fw ? facelist.getUint32(idx + 0x00, true) : facelist.getUint16(idx + 0x00, true);
            const side = facelist.getUint8(idx + (fw ? 0x04 : 0x02));
            const onNode = !!facelist.getUint8(idx + (fw ? 0x05 : 0x03));
            const firstedge = facelist.getUint32(idx + (fw ? 0x08 : 0x04), true);
            const numedges = fw ? facelist.getUint32(idx + 0x0C, true) : facelist.getUint16(idx + 0x08, true);
            const dispinfo = fw ? facelist.getInt32(idx + 0x14, true) : facelist.getInt16(idx + 0x0C, true);
            const surfaceFogVolumeID = fw ? facelist.getInt32(idx + 0x18, true) : facelist.getUint16(idx + 0x0E, true);

            const area = facelist.getFloat32(idx + (fw ? 0x24 : 0x18), true);
            const m_LightmapTextureMinsInLuxels = nArray(2, (i) => facelist!.getInt32(idx + (fw ? 0x28 : 0x1C) + i * 4, true));
            const m_LightmapTextureSizeInLuxels = nArray(2, (i) => facelist!.getUint32(idx + (fw ? 0x30 : 0x24) + i * 4, true));
            const origFace = facelist.getUint32(idx + (fw ? 0x38 : 0x2C), true);
            const m_NumPrimsRaw = fw ? facelist.getUint32(idx + 0x3C, true) : facelist.getUint16(idx + 0x30, true);
            const m_NumPrims = fw ? m_NumPrimsRaw >>> 1 : m_NumPrimsRaw & 0x7FFF;
            const firstPrimID = fw ? facelist.getUint32(idx + 0x40, true) : facelist.getUint16(idx + 0x32, true);
            const smoothingGroups = facelist.getUint32(idx + (fw ? 0x44 : 0x34), true);
'''),
    ('SourceEngine/BSPFile.ts',
     '''                    if (this.version === 22) {
                        const primOffs = firstPrimID * 0x10;
''',
     '''                    if (primitivesVersion === 1) {
                        // FTESurf P1447: dprimitive_t v1, five u32 (measured: 20-byte records).
                        const primOffs = firstPrimID * 0x14;
                        primType = primitives.getUint32(primOffs + 0x00, true);
                        primFirstIndex = primitives.getUint32(primOffs + 0x04, true);
                        primIndexCount = primitives.getUint32(primOffs + 0x08, true);
                        primFirstVert = primitives.getUint32(primOffs + 0x0C, true);
                        primVertCount = primitives.getUint32(primOffs + 0x10, true);
                    } else if (this.version === 22) {
                        const primOffs = firstPrimID * 0x10;
'''),
    ('SourceEngine/BSPFile.ts',
     '''        const dispinfo = getLumpData(LumpType.DISPINFO).createDataView();
        const dispinfolist: DispInfo[] = [];
        for (let idx = 0x00; idx < dispinfo.byteLength; idx += 0xB0) {
''',
     '''        // FTESurf P1447: DISPINFO v1 (Strata) is 232 bytes with mapFace u32; the fields read here keep their offsets.
        const [dispinfoLump, dispinfoVersion] = getLumpDataV(LumpType.DISPINFO, [0, 1]);
        const dispinfo = dispinfoLump.createDataView();
        const dispinfolist: DispInfo[] = [];
        for (let idx = 0x00; idx < dispinfo.byteLength; idx += (dispinfoVersion === 1 ? 0xE8 : 0xB0)) {
'''),
    ('SourceEngine/BSPFile.ts',
     '            const mapFace = dispinfo.getUint16(idx + 0x24, true);\n',
     '            const mapFace = dispinfoVersion === 1 ? dispinfo.getUint32(idx + 0x24, true) : dispinfo.getUint16(idx + 0x24, true);\n'),
    ('SourceEngine/BSPFile.ts',
     '        const leafwaterdata = getLumpData(LumpType.LEAFWATERDATA).createDataView();\n',
     '''        const [lwdLump, lwdVersion] = getLumpDataV(LumpType.LEAFWATERDATA, [0, 1]); // FTESurf P1447: v1 texinfo is u32
        const leafwaterdata = lwdLump.createDataView();
'''),
    ('SourceEngine/BSPFile.ts',
     '            const surfaceTexInfoID = leafwaterdata.getUint16(idx + 0x08, true);\n',
     '            const surfaceTexInfoID = lwdVersion === 1 ? leafwaterdata.getUint32(idx + 0x08, true) : leafwaterdata.getUint16(idx + 0x08, true);\n'),
    ('SourceEngine/BSPFile.ts',
     '''        let leafambientindex: DataView | null = null;
        if (this.usingHDR)
            leafambientindex = getLumpData(LumpType.LEAF_AMBIENT_INDEX_HDR).createDataView();
        if (leafambientindex === null || leafambientindex.byteLength === 0)
            leafambientindex = getLumpData(LumpType.LEAF_AMBIENT_INDEX).createDataView();
''',
     '''        // FTESurf P1447: LEAF_AMBIENT_INDEX v1 is two u32 a leaf (measured: 8 bytes a leaf).
        let leafambientindex: DataView | null = null;
        let laiVersion = 0;
        if (this.usingHDR) {
            const [l, v] = getLumpDataV(LumpType.LEAF_AMBIENT_INDEX_HDR, [0, 1]);
            leafambientindex = l.createDataView(); laiVersion = v;
        }
        if (leafambientindex === null || leafambientindex.byteLength === 0) {
            const [l, v] = getLumpDataV(LumpType.LEAF_AMBIENT_INDEX, [0, 1]);
            leafambientindex = l.createDataView(); laiVersion = v;
        }
'''),
    ('SourceEngine/BSPFile.ts',
     '''                const ambientSampleCount = leafambientindex.getUint16(leafindex * 0x04 + 0x00, true);
                const firstAmbientSample = leafambientindex.getUint16(leafindex * 0x04 + 0x02, true);
''',
     '''                const ambientSampleCount = laiVersion === 1 ? leafambientindex.getUint32(leafindex * 0x08 + 0x00, true)
                                                            : leafambientindex.getUint16(leafindex * 0x04 + 0x00, true);
                const firstAmbientSample = laiVersion === 1 ? leafambientindex.getUint32(leafindex * 0x08 + 0x04, true)
                                                            : leafambientindex.getUint16(leafindex * 0x04 + 0x02, true);
'''),
    ('SourceEngine/BSPFile.ts',
     '        const leaffacelist = getLumpData(LumpType.LEAFFACES).createTypedArray(Uint16Array);\n',
     '''        const [lfLump, lfVersion] = getLumpDataV(LumpType.LEAFFACES, [0, 1]); // FTESurf P1447: v1 is 32-bit
        const leaffacelist: Uint16Array | Uint32Array = lfVersion === 1 ?
            lfLump.createTypedArray(Uint32Array) : lfLump.createTypedArray(Uint16Array);
'''),
    ('SourceEngine/BSPFile.ts',
     '''            const contents = leafs.getUint32(idx + 0x00, true);
            const cluster = leafs.getUint16(idx + 0x04, true);
            const areaAndFlags = leafs.getUint16(idx + 0x06, true);
            const area = areaAndFlags & 0x01FF;
            const flags = (areaAndFlags >>> 9) & 0x007F;
            const bboxMinX = leafs.getInt16(idx + 0x08, true);
            const bboxMinY = leafs.getInt16(idx + 0x0A, true);
            const bboxMinZ = leafs.getInt16(idx + 0x0C, true);
            const bboxMaxX = leafs.getInt16(idx + 0x0E, true);
            const bboxMaxY = leafs.getInt16(idx + 0x10, true);
            const bboxMaxZ = leafs.getInt16(idx + 0x12, true);
            const bbox = new AABB(bboxMinX, bboxMinY, bboxMinZ, bboxMaxX, bboxMaxY, bboxMaxZ);
            const firstleafface = leafs.getUint16(idx + 0x14, true);
            const numleaffaces = leafs.getUint16(idx + 0x16, true);
            const firstleafbrush = leafs.getUint16(idx + 0x18, true);
            const numleafbrushes = leafs.getUint16(idx + 0x1A, true);
            const leafwaterdata = leafs.getInt16(idx + 0x1C, true);
            const leafindex = this.leaflist.length;

            idx += 0x1E;
''',
     '''            // FTESurf P1447: LEAFS v2 (Strata) is strata_dleaf_t: 32-bit cluster and refs, float bounds,
            // 56 bytes, no inline ambient cube (the index and lighting lumps carry it, as for v1).
            const lw = leafsVersion === 2;
            const contents = leafs.getUint32(idx + 0x00, true);
            const clusterRaw = lw ? leafs.getInt32(idx + 0x04, true) : leafs.getUint16(idx + 0x04, true);
            const cluster = clusterRaw < 0 ? 0xFFFF : clusterRaw;
            const areaAndFlags = lw ? leafs.getUint32(idx + 0x08, true) : leafs.getUint16(idx + 0x06, true);
            const area = lw ? areaAndFlags & 0x1FFFF : areaAndFlags & 0x01FF;
            const flags = lw ? (areaAndFlags >>> 17) & 0x7FFF : (areaAndFlags >>> 9) & 0x007F;
            const rdl = (o16: number, o32: number) => lw ? leafs.getFloat32(idx + o32, true) : leafs.getInt16(idx + o16, true);
            const bboxMinX = rdl(0x08, 0x0C);
            const bboxMinY = rdl(0x0A, 0x10);
            const bboxMinZ = rdl(0x0C, 0x14);
            const bboxMaxX = rdl(0x0E, 0x18);
            const bboxMaxY = rdl(0x10, 0x1C);
            const bboxMaxZ = rdl(0x12, 0x20);
            const bbox = new AABB(bboxMinX, bboxMinY, bboxMinZ, bboxMaxX, bboxMaxY, bboxMaxZ);
            const firstleafface = lw ? leafs.getUint32(idx + 0x24, true) : leafs.getUint16(idx + 0x14, true);
            const numleaffaces = lw ? leafs.getUint32(idx + 0x28, true) : leafs.getUint16(idx + 0x16, true);
            const firstleafbrush = lw ? leafs.getUint32(idx + 0x2C, true) : leafs.getUint16(idx + 0x18, true);
            const numleafbrushes = lw ? leafs.getUint32(idx + 0x30, true) : leafs.getUint16(idx + 0x1A, true);
            const leafwaterdata = lw ? leafs.getInt32(idx + 0x34, true) : leafs.getInt16(idx + 0x1C, true);
            const leafindex = this.leaflist.length;

            idx += lw ? 0x36 : 0x1E;
'''),
    ('SourceEngine/BSPFile.ts',
     '        const overlays = getLumpData(LumpType.OVERLAYS).createDataView();\n',
     '''        // FTESurf P1447: only the v0 record is parsed; v1-v3 (some v20/v21 maps, Strata) draw no overlays yet.
        const [ovLump, ovVersion] = getLumpDataV(LumpType.OVERLAYS, [0, 1, 2, 3]);
        const overlays = (ovVersion === 0 ? ovLump : ovLump.subarray(0, 0)).createDataView();
'''),
    ('SourceEngine/StaticDetailObject.ts',
     '    leafList: Uint16Array;\n',
     '    leafList: Uint16Array | Uint32Array; // FTESurf P1447: Strata\'s are 32-bit\n'),
    ('SourceEngine/StaticDetailObject.ts',
     '''export function deserializeGameLump_sprp(buffer: ArrayBufferSlice, version: number, bspVersion: number): StaticObjects | null {
    assert(version === 4 || version === 5 || version === 6 || version === 9 || version === 10 || version === 11);
''',
     '''// FTESurf P1447: Strata's sprp v12/v13, after the engine's VBSP_LoadStaticProps (mod_vbsp.c): 32-bit
// leaf refs (16-bit tried too, by which divides), v10's fields to FlagsEx at +0x44, a measured stride
// whose extra bytes sit at +0x48, then a Vector scale whose X is taken, as the engine does.
function deserializeGameLump_sprpStrata(buffer: ArrayBufferSlice): StaticObjects {
    const sprp = buffer.createDataView();
    const staticModelDict: string[] = [];
    if (sprp.byteLength < 0x04)
        return { staticProps: [] };     // an empty lump (bhop_egyptian_balls, df_ash)
    const dictCount = sprp.getUint32(0x00, true);
    let idx = 0x04;
    for (let i = 0; i < dictCount; i++, idx += 0x80)
        staticModelDict.push(readString(buffer, idx, 0x80, true));
    const leafListCount = sprp.getUint32(idx, true);
    idx += 0x04;
    for (const width of [4, 2]) {
        const at = idx + leafListCount * width;
        if (at + 0x04 > sprp.byteLength)
            continue;
        const count = sprp.getUint32(at, true);
        const stride = count > 0 ? (sprp.byteLength - at - 0x04) / count : 0x54;
        if (stride < 0x54 || stride !== Math.floor(stride))
            continue;
        const leafList = width === 4 ? buffer.createTypedArray(Uint32Array, idx, leafListCount, Endianness.LITTLE_ENDIAN)
                                     : buffer.createTypedArray(Uint16Array, idx, leafListCount, Endianness.LITTLE_ENDIAN);
        const staticProps: StaticProp[] = [];
        for (let i = 0; i < count; i++) {
            const o = at + 0x04 + i * stride;
            const pos = vec3.fromValues(sprp.getFloat32(o + 0x00, true), sprp.getFloat32(o + 0x04, true), sprp.getFloat32(o + 0x08, true));
            const rot = vec3.fromValues(sprp.getFloat32(o + 0x0C, true), sprp.getFloat32(o + 0x10, true), sprp.getFloat32(o + 0x14, true));
            const propType = sprp.getUint16(o + 0x18, true);
            const firstLeaf = sprp.getUint16(o + 0x1A, true);
            const leafCount = sprp.getUint16(o + 0x1C, true);
            const flags: StaticPropFlags = sprp.getUint8(o + 0x1F);
            const skin = sprp.getInt32(o + 0x20, true);
            const fadeMinDist = sprp.getFloat32(o + 0x24, true);
            const fadeMaxDist = sprp.getFloat32(o + 0x28, true);
            const lightingOrigin = !!(flags & StaticPropFlags.USE_LIGHTING_ORIGIN) ?
                vec3.fromValues(sprp.getFloat32(o + 0x2C, true), sprp.getFloat32(o + 0x30, true), sprp.getFloat32(o + 0x34, true)) : null;
            let scale = sprp.getFloat32(o + 0x48 + (stride - 0x54), true);
            if (!(scale > 0 && scale <= 64))
                scale = 1.0;
            staticProps.push({ index: i, pos, rot, scale, flags, skin, propName: staticModelDict[propType],
                leafList: leafList.subarray(firstLeaf, firstLeaf + leafCount), fadeMinDist, fadeMaxDist, lightingOrigin });
        }
        return { staticProps };
    }
    return { staticProps: [] };
}

export function deserializeGameLump_sprp(buffer: ArrayBufferSlice, version: number, bspVersion: number): StaticObjects | null {
    if (version === 12 || version === 13)
        return deserializeGameLump_sprpStrata(buffer); // FTESurf P1447
    assert(version === 4 || version === 5 || version === 6 || version === 9 || version === 10 || version === 11);
'''),
]

PATCHES += [
    # P1447: an empty game lump (bhop_anomalous) has no count to read.
    ('SourceEngine/BSPFile.ts',
     '            const lumpCount = game_lump.getUint32(0x00, true);\n',
     '            const lumpCount = game_lump.byteLength >= 0x04 ? game_lump.getUint32(0x00, true) : 0; // FTESurf P1447\n'),
    # P1447: a compressed game lump's region ends at the next entry's offset, or the lump's end
    # when that offset is 0 or before it (bhop_adventure's terminator); its size is the 'LZMA'
    # header's, because maps disagree about what filelen means; under 17 bytes is an empty stub
    # (Strata writes 12-byte ones) -- the engine's VBSP_LoadGameLump rules.
    ('SourceEngine/BSPFile.ts',
     '''                        let compressedEnd: number;
                        if (i + 1 < lumpCount)
                            compressedEnd = game_lump.getUint32(idx + 0x10 + 0x08, true);
                        else
                            compressedEnd = game_lump.byteOffset + game_lump.byteLength;
                        const compressed = buffer.slice(fileofs, compressedEnd);
                        const lump = decompressLZMA(compressed, filelen);
                        return [lump, version];
''',
     '''                        const lumpEnd = game_lump.byteOffset + game_lump.byteLength;
                        let compressedEnd = (i + 1 < lumpCount) ? game_lump.getUint32(idx + 0x10 + 0x08, true) : lumpEnd;
                        if (compressedEnd <= fileofs)
                            compressedEnd = lumpEnd;
                        if (compressedEnd - fileofs < 0x11)
                            return null;
                        const compressed = buffer.slice(fileofs, compressedEnd);
                        const lump = decompressLZMA(compressed, compressed.createDataView().getUint32(0x04, true));
                        return [lump, version];
'''),
    # P1447: a map with no ambient lighting at all (unlit, or compiled without it) has neither
    # lump; its leaves get no ambient sample instead of an assert.
    ('SourceEngine/BSPFile.ts',
     '''            } else if (leafambientindex.byteLength === 0) {
                // Intermediate leafambient version.
''',
     '''            } else if (leafambientindex.byteLength === 0 && leafambientlighting.byteLength === 0) {
                idx += 0x02; // FTESurf P1447: no ambient data in the map
            } else if (leafambientindex.byteLength === 0) {
                // Intermediate leafambient version.
'''),
    # P1447: a face with garbage extents (surf_huecomundo: INT_MIN) gets a 1x1 unlit lightmap
    # instead of failing the lightmap page allocation for the whole map.
    ('SourceEngine/BSPFile.ts',
     '            const width = m_LightmapTextureSizeInLuxels[0] + 1, height = m_LightmapTextureSizeInLuxels[1] + 1;\n',
     '''            const badExtents = !(m_LightmapTextureSizeInLuxels[0] < 2048 && m_LightmapTextureSizeInLuxels[1] < 2048); // FTESurf P1447
            const width = badExtents ? 1 : m_LightmapTextureSizeInLuxels[0] + 1, height = badExtents ? 1 : m_LightmapTextureSizeInLuxels[1] + 1;
'''),
    ('SourceEngine/BSPFile.ts',
     '            if (lightofs !== -1 && lighting !== null && lightofs + srcLightmapSize <= lighting.byteLength)\n',
     '            if (lightofs !== -1 && !badExtents && lighting !== null && lightofs + srcLightmapSize <= lighting.byteLength)\n'),
]

PATCHES += [
    # P1447: a displacement is marked in the leaves under ITS box. The merged surface's box (which
    # can span the map) made every displacement walk thousands of leaves, each with a linear
    # ensureInList: 71-73% of the parse on ahop_coast (11.7 s) and bhop_canals (23.3 s).
    ('SourceEngine/BSPFile.ts',
     '                this.queryAABB(surface.bbox, (leaf) => {\n',
     '                this.queryAABB(bbox, (leaf) => { // FTESurf P1447: the face\'s own box\n'),
]

PATCHES += [
    # P1447: optional data degrades instead of failing the whole map (all 11 of the library's
    # remaining v20/v21 failures; each failed the same way before P1447).
    # A face whose primitives are not one triangle list (surf_bossfight, surf_healthy, surf_fiellu_ksf)
    # is drawn as its polygon's fan.
    ('SourceEngine/BSPFile.ts',
     '''                    // We should be in static mode, so we should have 1 prim maximum.
                    assert(m_NumPrims === 1);
                    assert(primIndexCount === indexCount);
                    assert(primType === 0x00 /* PRIM_TRILIST */);

                    for (let k = 0; k < indexCount; k++)
                        indexData[dstOffsIndex + k] = dstIndexBase + primindices[primFirstIndex + k];
''',
     '''                    // We should be in static mode, so we should have 1 prim maximum.
                    // FTESurf P1447: otherwise (several, a strip, a short list) draw the polygon's fan.
                    if (m_NumPrims === 1 && primIndexCount === indexCount && primType === 0x00 /* PRIM_TRILIST */
                        && primFirstIndex + indexCount <= primindices.length) {
                        for (let k = 0; k < indexCount; k++)
                            indexData[dstOffsIndex + k] = dstIndexBase + primindices[primFirstIndex + k];
                    } else {
                        convertToTrianglesRange(indexData, dstOffsIndex, GfxTopology.TriFans, dstIndexBase, numedges);
                    }
'''),
    # A compressed game lump that does not start with Valve's 'LZMA' header (surf_boogie_woogie) is skipped.
    ('SourceEngine/BSPFile.ts',
     '''                        const compressed = buffer.slice(fileofs, compressedEnd);
                        const lump = decompressLZMA(compressed, compressed.createDataView().getUint32(0x04, true));
''',
     '''                        const compressed = buffer.slice(fileofs, compressedEnd);
                        if (readString(compressed, 0x00, 0x04) !== 'LZMA')
                            return null; // FTESurf P1447: not Valve's framing; the map draws without it
                        const lump = decompressLZMA(compressed, compressed.createDataView().getUint32(0x04, true));
'''),
    # A detail-prop lump that does not parse (surf_bewatermyfriend, surf_classics3) costs the detail props only.
    ('SourceEngine/BSPFile.ts',
     '''        if (dprp !== null)
            this.detailObjects = deserializeGameLump_dprp(dprp[0], dprp[1]);
''',
     '''        if (dprp !== null) {
            try {
                this.detailObjects = deserializeGameLump_dprp(dprp[0], dprp[1]);
            } catch (e) {
                console.warn(`${mapname}: detail props skipped (${e})`); // FTESurf P1447
            }
        }
'''),
    # A leaf past the end of a short ambient index (surf_eon) gets no ambient sample.
    ('SourceEngine/BSPFile.ts',
     '''                const ambientSampleCount = laiVersion === 1 ? leafambientindex.getUint32(leafindex * 0x08 + 0x00, true)
                                                            : leafambientindex.getUint16(leafindex * 0x04 + 0x00, true);
                const firstAmbientSample = laiVersion === 1 ? leafambientindex.getUint32(leafindex * 0x08 + 0x04, true)
                                                            : leafambientindex.getUint16(leafindex * 0x04 + 0x02, true);
''',
     '''                const laiStride = laiVersion === 1 ? 0x08 : 0x04;
                const laiIn = (leafindex + 1) * laiStride <= leafambientindex.byteLength; // FTESurf P1447: a short index
                const ambientSampleCount = !laiIn ? 0 : laiVersion === 1 ? leafambientindex.getUint32(leafindex * 0x08 + 0x00, true)
                                                            : leafambientindex.getUint16(leafindex * 0x04 + 0x00, true);
                const firstAmbientSample = !laiIn ? 0 : laiVersion === 1 ? leafambientindex.getUint32(leafindex * 0x08 + 0x04, true)
                                                            : leafambientindex.getUint16(leafindex * 0x04 + 0x02, true);
'''),
]

PATCHES += [
    # P1447: an empty uncompressed game lump (surf_bewatermyfriend: sprp version 0, length 0) is absent.
    ('SourceEngine/BSPFile.ts',
     '                        const lump = buffer.subarray(fileofs, filelen);\n',
     '                        if (filelen === 0)\n'
     '                            return null; // FTESurf P1447: an empty stub\n'
     '                        const lump = buffer.subarray(fileofs, filelen);\n'),
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
