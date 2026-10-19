// Builds surfd/web/watch.js, the board's 3D run viewer, from src/main.ts.
//   node build.mjs           minified, the file surfd serves
//   node build.mjs --dev     with an inline source map, for local debugging
import { build } from 'esbuild';
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const here = path.dirname(fileURLToPath(import.meta.url));
const out = path.join(here, '..', '..', 'surfd', 'web', 'watch.js');
const dev = process.argv.includes('--dev');

await build({
    entryPoints: [path.join(here, 'src', 'main.ts')],
    outfile: out,
    bundle: true,
    format: 'iife',
    target: 'es2022',
    minify: !dev,
    sourcemap: dev ? 'inline' : false,
    legalComments: 'eof',
    alias: { 'noclip-rust-support': path.join(here, 'vendor', 'noclip', 'src', 'rustlib.ts') },
    define: {
        'process.env.NODE_ENV': dev ? '"development"' : '"production"',
        // DataFetcher's base for relative paths; the viewer only fetches absolute URLs.
        'import.meta.env.PUBLIC_STORAGE_URL': '""',
    },
    logLevel: 'warning',
});

const bytes = readFileSync(out);
console.log(`${path.relative(process.cwd(), out)}: ${bytes.length} bytes, sha256 ${createHash('sha256').update(bytes).digest('hex').slice(0, 16)}`);
