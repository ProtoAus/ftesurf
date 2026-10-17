#!/usr/bin/env python3
"""Patch 763: the tempstring GC skips memnostrings' blocks, through the REAL qclib code.

Compiles initlib.c's allocator (PR_memalloc/memfree/memrealloc), the skip table
(PR_AddressableNoStrings, PR_NoStringsDrop, PR_QCGC_Segments, ...Info), the mark scan and the two
read paths cut out of PR_RunGC (the threaded copy and the same-thread scan). Random alloc, mark,
free, realloc and forged-header sequences run on a hunk of random words, a third of them
tempstring references. After each step the marks both paths set are compared with an oracle: a
plain word scan of the whole hunk that leaves out only the ranges an independent model says are
registered. No game, deployment or data access. --out must be under an owned task root.
The model restates the registration rules (an aligned header wholly inside the hunk, the used
marker, a size inside the hunk), so it checks the bookkeeping and the reads, not the rules.
Controls, each failing marks_ok: without the drop in PR_memfree a freed block's reuse is still
skipped; dropping only registrations that START in the freed block keeps a forged one from the
globals over it (review round 1); skips not cut to whole words shift the words read; unsorted
insertion overlaps the stretches.
"""
import argparse
import os
from pathlib import Path
import subprocess

PREFIX = r'''
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef unsigned int pbool;
#define false 0
#define true 1
#define PDECL
#define STRING_SPECMASK 0xc0000000
#define STRING_TEMP 0x80000000
#define NOSTR_MAX 128
#define smallbool char
typedef struct {unsigned int size; char value[4];} tempstr_t;
typedef struct pubprogfuncs_s {char *stringtable; size_t stringtablesize;} pubprogfuncs_t;
typedef struct {
 int mfreelist; char *addressablehunk; size_t addressableused, addressablesize;
 unsigned int maxtempstrings; tempstr_t **tempstrings; struct qcgccontext_s *gccontext;
 unsigned int numnostr, nostr_start[NOSTR_MAX], nostr_end[NOSTR_MAX];
} prinst_t;
typedef struct progfuncs_s {pubprogfuncs_t funcs; prinst_t inst;} progfuncs_t;
#define prinst progfuncs->inst
struct qcgccontext_s {int done; unsigned int clearedtemps; progfuncs_t *progfuncs; size_t maxtemps; tempstr_t **tempstrings; size_t memsize; unsigned int amem[1];};
static int errors;
static int report(const char *fmt, ...) {va_list a; va_start(a, fmt); errors++; fprintf(stderr, "qclib: "); vfprintf(stderr, fmt, a); va_end(a); return 0;}
static struct {int (*Printf)(const char *fmt, ...);} externs_s = {report}, *externs = &externs_s;
static void PR_StackTrace(pubprogfuncs_t *pf, int x) {(void)pf; (void)x;}
static void *PRAddressableExtend(progfuncs_t *progfuncs, void *src, size_t srcsize, int pad)
{	// initlib.c's arithmetic: rounded up to 4 past a trailing null, no relocation
	int ammount = (srcsize+pad + 4)&~3;
	(void)src;
	if (prinst.addressableused + ammount >= prinst.addressablesize) return NULL;
	prinst.addressableused += ammount;
	progfuncs->funcs.stringtablesize = prinst.addressableused;
	memset(&prinst.addressablehunk[prinst.addressableused-ammount]+srcsize, 0, ammount-srcsize);
	return &prinst.addressablehunk[prinst.addressableused-ammount];
}
static size_t last_malloc;
static void *test_malloc(size_t n) {last_malloc = n; return malloc(n);}
'''

TEST = r'''
static smallbool *swept_marked;
static size_t PR_QCGC_Sweep(progfuncs_t *progfuncs, smallbool *marked, tempstr_t **t, unsigned int n)
{(void)progfuncs; (void)t; swept_marked = malloc(n); memcpy(swept_marked, marked, n); free(marked); return 0;}
static smallbool *samethread(progfuncs_t *progfuncs)
{
SAMETHREAD
	(void)swept;
	return swept_marked;
}
static struct qcgccontext_s *threaded(progfuncs_t *progfuncs)
{
THREADED
	return gc;
}

#undef malloc
#define NUMTEMPS 4096
#define HUNK (2u<<20)
static uint32_t rs, seed0;
static uint32_t rnd(void) {rs ^= rs << 13; rs ^= rs >> 17; rs ^= rs << 5; return rs;}
static progfuncs_t pfs, *pf = &pfs;
typedef struct {unsigned int hdr, size;} blk_t;	// header offset, the header's size field
static blk_t blks[2048]; static int nblks;
typedef struct {unsigned int s, e;} rng_t;		// the model of the engine's table
static rng_t mr[512]; static int nmr;
static long regs, dups, fulls, rejects, forged, drops, frees, reallocs, checks, skipbytes, refs_skipped, forged_globals;
static unsigned int globals;
static int fail(const char *what) {fprintf(stderr, "FAIL %s (seed %u, check %ld)\n", what, seed0, checks); exit(1);}

static void fill(char *p, size_t n)
{	// random words, a third of them tempstring references (some past NUMTEMPS)
	size_t i;
	for (i = 0; i + 4 <= n; i += 4)
	{
		uint32_t w = rnd();
		if (w % 3 == 0) w = STRING_TEMP | (rnd() % (NUMTEMPS + NUMTEMPS/8));
		memcpy(p + i, &w, 4);
	}
}
static int model_register(unsigned int hdr)
{	// the promise's rules restated: an aligned in-hunk header, its marker, a size inside the hunk
	unsigned int marker, size, s = hdr + 8; int i;
	if ((size_t)hdr + 8 > pf->inst.addressableused || (hdr & 3)) return 0;
	memcpy(&marker, pf->inst.addressablehunk + hdr, 4); memcpy(&size, pf->inst.addressablehunk + hdr + 4, 4);
	if (marker != 0xC2A4F5A6u || size <= 8 || (size_t)hdr + size > pf->inst.addressableused) return 0;
	for (i = 0; i < nmr; i++) if (mr[i].s == s) return 2;
	if (nmr == NOSTR_MAX) return 3;
	mr[nmr].s = s; mr[nmr].e = hdr + size; nmr++;
	return 1;
}
static void model_drop(unsigned int hdr, unsigned int size)
{	// a free forgets every registration overlapping the block, forged ones over it included
	int i, o;
	for (i = o = 0; i < nmr; i++) if (mr[i].e <= hdr || mr[i].s >= hdr + size) mr[o++] = mr[i]; else drops++;
	nmr = o;
}
static void check(void)
{
	size_t used = pf->inst.addressableused, p, excluded = 0;
	static smallbool want[NUMTEMPS]; static char skip[HUNK];
	smallbool *a, *b; struct qcgccontext_s *gc; unsigned int blocks; int i;
	checks++;
	memset(skip, 0, used);
	for (i = 0; i < nmr; i++)
	{
		size_t s = (mr[i].s + 3) & ~(size_t)3, e = (mr[i].e < used ? mr[i].e : used) & ~(size_t)3;
		if (s < e) memset(skip + s, 1, e - s);
	}
	memset(want, 0, sizeof(want));
	for (p = 0; p < used; p += 4)
	{
		uint32_t w; memcpy(&w, pf->inst.addressablehunk + p, 4);
		if (skip[p]) { excluded += 4; if ((w & STRING_SPECMASK) == STRING_TEMP) refs_skipped++; continue; }
		if ((w & STRING_SPECMASK) == STRING_TEMP && (w & ~STRING_SPECMASK) < NUMTEMPS) want[w & ~STRING_SPECMASK] = 1;
	}
	a = samethread(pf);
	if (memcmp(a, want, NUMTEMPS)) fail("marks_ok (same-thread)");
	free(a);
	gc = threaded(pf);
	if ((uintptr_t)gc->tempstrings & 7) fail("aligned_ok");
	if ((char*)(gc->tempstrings + pf->inst.maxtempstrings) > (char*)gc + last_malloc) fail("bounds_ok");
	b = PR_QCGC_Mark(gc->amem, gc->memsize, gc->maxtemps);
	if (memcmp(b, want, NUMTEMPS)) fail("marks_ok (threaded copy)");
	free(b); free(gc);
	if (excluded != PR_AddressableNoStringsInfo(&pf->funcs, &blocks) || blocks != (unsigned)nmr) fail("info_ok");
	skipbytes += excluded;
}
static void trial(uint32_t seed, int steps)
{
	static char hunk[HUNK + 64];
	int s, i;
	rs = seed0 = seed;
	memset(pf, 0, sizeof(*pf));
	pf->inst.addressablehunk = pf->funcs.stringtable = hunk + 8 - ((uintptr_t)hunk & 7);
	pf->inst.addressablesize = HUNK;
	pf->inst.maxtempstrings = NUMTEMPS;
	nblks = nmr = 0;
	globals = 1000 + rnd() % 4000;
	fill(PRAddressableExtend(pf, NULL, globals, 0), globals);	// globals, fields
	check();
	for (s = 0; s < steps; s++)
	{
		unsigned int op = rnd() % 100, k = nblks ? rnd() % nblks : 0;
		if (op < 30 || !nblks)
		{	// memalloc: fresh, or carved from a freed block whose range must be gone
			unsigned int n = 1 + rnd() % 3000;
			char *m = PR_memalloc(&pf->funcs, n);
			if (!m || nblks == 2048) continue;
			fill(m, n);
			blks[nblks].hdr = m - 8 - pf->funcs.stringtable;
			memcpy(&blks[nblks].size, m - 4, 4);
			nblks++;
		}
		else if (op < 55)
		{	// memnostrings on a real block
			int want = model_register(blks[k].hdr), got = PR_AddressableNoStrings(&pf->funcs, pf->funcs.stringtable + blks[k].hdr + 8);
			if (got != (want == 1 || want == 2)) fail("register_ok");
			regs += want == 1; dups += want == 2; fulls += want == 3;
		}
		else if (op < 75)
		{	// memfree
			model_drop(blks[k].hdr, blks[k].size);
			PR_memfree(&pf->funcs, pf->funcs.stringtable + blks[k].hdr + 8);
			blks[k] = blks[--nblks]; frees++;
		}
		else if (op < 85)
		{	// memrealloc: a new block; the old one's range goes with it
			unsigned int n = 1 + rnd() % 3000;
			char *m;
			model_drop(blks[k].hdr, blks[k].size);
			m = PR_memrealloc(&pf->funcs, pf->funcs.stringtable + blks[k].hdr + 8, n);
			if (!m) fail("realloc");
			blks[k].hdr = m - 8 - pf->funcs.stringtable; memcpy(&blks[k].size, m - 4, 4);
			reallocs++;
		}
		else
		{	// a forged header inside a block or in the globals (never freed, so its range can reach
			// over later blocks): any size, sometimes unaligned
			unsigned int at = blks[k].hdr + 8 + (rnd() % (blks[k].size > 24 ? blks[k].size - 16 : 1)), size = rnd() % 2 ? 9 + rnd() % 4000 : 0x7ffffff0u;
			unsigned int marker = 0xC2A4F5A6u; int want, got;
			if (rnd() % 3 == 0) at = rnd() % (globals - 8);
			if (rnd() % 4) at &= ~3u;
			if (at >= globals && at + 8 > blks[k].hdr + blks[k].size) continue;
			memcpy(pf->inst.addressablehunk + at, &marker, 4); memcpy(pf->inst.addressablehunk + at + 4, &size, 4);
			want = model_register(at);
			got = PR_AddressableNoStrings(&pf->funcs, pf->funcs.stringtable + at + 8);
			if (got != (want == 1 || want == 2)) fail("forged_ok");
			forged += want == 1; rejects += want == 0; fulls += want == 3;
			forged_globals += want == 1 && at < globals;
		}
		if (rnd() % 4 == 0) check();
	}
	for (i = 0; i < nblks; i++) model_drop(blks[i].hdr, blks[i].size), PR_memfree(&pf->funcs, pf->funcs.stringtable + blks[i].hdr + 8);
	nblks = 0;
	check();
	if (pf->inst.numnostr != (unsigned)nmr || nmr > forged_globals) fail("empty_ok");	// only globals forgeries may outlive the blocks
}
int main(void)
{
	uint32_t seed;
	for (seed = 1; seed <= 40; seed++) trial(seed * 2654435761u, 3000);
	if (errors) fail("errors_ok (allocator reports)");
	if (!regs || !dups || !fulls || !rejects || !forged || !forged_globals || !drops || !refs_skipped) fail("coverage_ok");
	printf("PASS %ld checks: marks equal the oracle on both paths; %ld registered, %ld again, %ld refused full, "
	       "%ld forged accepted (%ld in the globals), %ld refused, %ld dropped by %ld frees and %ld reallocs, %ld skipped refs\n",
	       checks, regs, dups, fulls, forged, forged_globals, rejects, drops, frees, reallocs, refs_skipped);
	return 0;
}
'''


def function(text, signature):
    start = text.index(signature)
    return text[start:text.index('\n}', start) + 2] + '\n'


def between(text, first, last):
    """The lines from the one holding `first` through the one holding `last`."""
    s = text.index(first)
    s = text.rindex('\n', 0, s) + 1
    e = text.index('\n', text.index(last, s)) + 1
    return text[s:e]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--engine', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--cc', default='C:/msys64/ucrt64/bin/gcc.exe')
    a = ap.parse_args()
    lib = (a.engine/'engine'/'qclib'/'initlib.c').read_text(encoding='latin-1')
    code = PREFIX + between(lib, '#define MARKER_USED', '} qcmemusedblock_t;')
    for sig in ['static void PF_fmem_unlink(', 'void PR_memvalidate (', 'static void PR_NoStringsDrop(',
                'pbool PR_AddressableNoStrings(', 'static unsigned int PR_QCGC_Segments(',
                'size_t PR_AddressableNoStringsInfo(', 'static void *PDECL PR_memalloc (',
                'static void PDECL PR_memfree (', 'static void *PDECL PR_memrealloc (']:
        code += function(lib, sig)
    code += '#define malloc(n) test_malloc(n)\n'
    for sig in ['static void PR_QCGC_MarkWords(', 'static smallbool *PR_QCGC_Mark(']:
        code += function(lib, sig)
    same = between(lib, 'size_t ofs[NOSTR_MAX+1], len[NOSTR_MAX+1];\n',
                   'swept = PR_QCGC_Sweep(progfuncs, marked, prinst.tempstrings, prinst.maxtempstrings);')
    thr = between(lib, 'size_t ofs[NOSTR_MAX+1], len[NOSTR_MAX+1], memsize = 0, padded;',
                  'gc->tempstrings = (void*)((char*)gc->amem+padded);')
    test = TEST.replace('SAMETHREAD\n', same).replace('THREADED\n', thr)
    code += test
    drop = '\tPR_NoStringsDrop(progfuncs, ptr, ptr + size);'
    overlap = 'if (prinst.nostr_end[i] <= start || prinst.nostr_start[i] >= end)'
    words_s = 's = (prinst.nostr_start[i] + 3) & ~(size_t)3;'
    words_e = 'e = (prinst.nostr_end[i] < used ? prinst.nostr_end[i] : used) & ~(size_t)3;'
    sort = 'for (i = 0; i < prinst.numnostr && prinst.nostr_start[i] < start; i++)\n\t\t;\n'
    for needle in (drop, overlap, words_s, words_e, sort):
        assert code.count(needle) == 1, needle
    arms = {
        'subject': code,
        'negative_drop': code.replace(drop, '\t(void)0;'),
        'negative_overlap': code.replace(overlap, 'if (prinst.nostr_start[i] < start || prinst.nostr_start[i] >= end)'),
        'negative_words': code.replace(words_e, 'e = (prinst.nostr_end[i] < used ? prinst.nostr_end[i] : used);'),
        'negative_sort': code.replace(sort, 'i = prinst.numnostr;\n'
                                      '\tfor (unsigned int j = 0; j < prinst.numnostr; j++) if (prinst.nostr_start[j] == start) i = j;\n'),
    }
    a.out.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env['PATH'] = str(Path(a.cc).parent) + os.pathsep + env.get('PATH', '')
    for arm, armcode in arms.items():
        src = a.out/('qcgc_'+arm+'.c')
        src.write_text(armcode)
        exe = src.with_suffix('.exe')
        subprocess.run([a.cc, '-std=gnu99', '-O2', '-Wall', '-Wno-unused-function', '-Wno-unused-variable',
                        '-Wno-unused-but-set-variable', str(src), '-o', str(exe)], env=env, check=True)
        p = subprocess.run([str(exe)], env=env, capture_output=True)
        (a.out/(arm+'.log')).write_bytes(p.stdout+p.stderr)
        if arm == 'subject':
            assert p.returncode == 0, p.stdout+p.stderr
            print(p.stdout.decode().strip())
        else:
            assert p.returncode != 0 and b'marks_ok' in p.stderr, (arm, p.stdout+p.stderr)
            print('PASS control', arm, 'fails', p.stderr.decode().strip().splitlines()[-1])


if __name__ == '__main__':
    main()
