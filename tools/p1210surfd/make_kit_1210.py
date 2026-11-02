"""P1210 surfd kit: preflight_1210.py and prepare_1210.py from ac's P1206 kit (exact seams).

prepare_1206.py prepared P1206 over P1200's generated scripts; prepare_1210 prepares P1210 over
P1206's (ac's kit/prepared): OLD = ac's live root, NEW = this session's root, PRED = ac's P1200
root, FALLBACK = the live 470ab7c9, GEN = 470ab7c9 + P1210's converter (833c8c58). The
predecessor-owner checks keep ac's session id (OLD is ac's root); ROOT-owner checks name mine.
"""
from pathlib import Path

ACKIT = Path('C:/FTESurf-worktrees/lexlist4-20261102/kit')
HERE = Path(__file__).resolve().parent
ME = '37d486c9'
OLD, NEW = '/srv/nvme/agent-work/chatfair-1206-57e27fa4', '/srv/nvme/agent-work/ksfduck-1210-' + ME
PRED = '/srv/nvme/agent-work/chatsave-1200-57e27fa4'
GEN, FALLBACK = '833c8c58002540424b9f224376c1ccdb50777de4', '470ab7c99deb43e926c84fe05e578df597ba6374'


def seam(src, old, new, count=1):
    assert src.count(old) == count, (old[:90], src.count(old))
    return src.replace(old, new)


# ---- preflight: the read-only observation, written into the new root
s = (ACKIT / 'preflight_1206.py').read_text(encoding='utf-8')
s = seam(s, '"""P1206 read-only production observation (from preflight_1200.py)',
         '"""P1210 read-only production observation (from preflight_1206.py)')
s = seam(s, "R = Path('" + OLD + "')", "R = Path('" + NEW + "')")
s = seam(s, "assert '57e27fa4' in (R / 'OWNER.md').read_text()", "assert '" + ME + "' in (R / 'OWNER.md').read_text()")
(HERE / 'preflight_1210.py').write_bytes(s.encode('utf-8'))

# ---- prepare
s = (ACKIT / 'prepare_1206.py').read_text(encoding='utf-8')
s = seam(s, '"""Prepare the P1206 code-only generation from P1200\'s generated workflow (exact seams).',
         '"""Prepare the P1210 code-only generation from P1206\'s generated workflow (exact seams).')
s = seam(s, "Primary: GEN (live 0d72a27c + P1200 saved chat), 83 files, activity83-v1, schema 26; only\n"
            "social.py changes in the pinned closure. Fallback: the exact live P1189 primary (FALLBACK), on the\n"
            "same DB.",
         "Primary: GEN (live 470ab7c9 + P1210 KSF ducked inference), 83 files, activity83-v1, schema 26;\n"
         "only tools/ksfconvert.py changes in the pinned closure. Fallback: the exact live P1206 primary\n"
         "(FALLBACK), on the same DB.")
s = seam(s, "Templates are\nP1189's generated scripts (2b's kit)", "Templates are\nP1206's generated scripts (ac's kit)")
s = seam(s, "TEMPLATES = Path('C:/FTESurf-worktrees/profiles-20261102/kit/prepared')",
         "TEMPLATES = Path('C:/FTESurf-worktrees/lexlist4-20261102/kit/prepared')")
s = seam(s, "REPO = Path('C:/FTESurf-worktrees/lexlist4-20261102/surfd')",
         "REPO = Path('C:/FTESurf-worktrees/zonesnap-20261102T0534Z/surfd')")
s = seam(s, "OLD = '/srv/nvme/agent-work/chatsave-1200-57e27fa4'", "OLD = '" + OLD + "'")
s = seam(s, "NEW = '/srv/nvme/agent-work/chatfair-1206-57e27fa4'", "NEW = '" + NEW + "'")
s = seam(s, "PRED = '/srv/nvme/agent-work/mapsrescan-1189-2b'", "PRED = '" + PRED + "'")
s = seam(s, "GEN = '470ab7c99deb43e926c84fe05e578df597ba6374'", "GEN = '" + GEN + "'")
s = seam(s, "FALLBACK = 'ac28393421b323ef122a2425bdc2e07f5f96d1d2'", "FALLBACK = '" + FALLBACK + "'")
s = seam(s, "(OUT / 'OWNER.md').write_text('Owner ftesurf-ac, Claude Code session 57e27fa4. P1206 code-only package; '",
         "(OUT / 'OWNER.md').write_text('Owner ftesurf-48, Claude Code session " + ME + ". P1210 code-only package; '")
s = seam(s, "want = {'primary': ['social.py'], 'fallback': []}", "want = {'primary': ['tools/ksfconvert.py'], 'fallback': []}")
s = seam(s, "    assert OLD not in json.dumps(m), 'a route still names the P1200 root'",
         "    assert OLD not in json.dumps(m), 'a route still names the P1206 root'")
s = seam(s, "    assert OLD not in text.replace(\"'\" + OLD + \"'\", ''), name + ' names the P1200 root outside its OLD constant'\n"
            "    assert PRED not in text, name + ' still names the P1189 root'\n"
            "    assert '382effae' not in text, name + ' still names 2b'\n",
         "    assert OLD not in text.replace(\"'\" + OLD + \"'\", ''), name + ' names the P1206 root outside its OLD constant'\n"
         "    assert PRED not in text, name + ' still names the P1200 root'\n")
# the seams over P1206's generated scripts
old = s[s.index("root = (\"ROOT = Path('\" + OLD + \"')\""):s.index("(OUT / 'live-before.json').write_bytes")]
s = seam(s, old, '''root = ("ROOT = Path('" + OLD + "')", "ROOT = Path('" + NEW + "')")
mine = ("assert '57e27fa4' in (ROOT / 'OWNER.md').read_text()", "assert '%s' in (ROOT / 'OWNER.md').read_text()")
workflow('stage_runtime.py', [root, mine, ("old_root = '" + PRED + "'", "old_root = '" + OLD + "'")])
workflow('qualify_runtime.py', [root])
workflow('install_namespace.py', [root, mine,
    ("GENERATION = '" + FALLBACK + "'", "GENERATION = '" + GEN + "'"),
    ("h.expected(live.decode('ascii'), str(ROOT), GENERATION, 'P1206')",
     "h.expected(live.decode('ascii'), str(ROOT), GENERATION, 'P1210')"),
    ("predecessor = Path('" + PRED + "')", "predecessor = Path('" + OLD + "')"),
    ("prefix='.p1206-ingress-'", "prefix='.p1210-ingress-'")])
workflow('activate_backend.py', [
    ('"""P1206 code-only activation (schema 26 unchanged) using the unchanged guard/systemd contracts.',
     '"""P1210 code-only activation (schema 26 unchanged) using the unchanged guard/systemd contracts.'),
    ('On a failed primary acceptance, use the prepared fallback (the exact P1200 primary, ac283934);',
     'On a failed primary acceptance, use the prepared fallback (the exact P1206 primary, 470ab7c9);'),
    ("R = Path('" + OLD + "')", "R = Path('" + NEW + "')"),
    ("OLD = Path('" + PRED + "')", "OLD = Path('" + OLD + "')"),
    ("temp = target.with_name(target.name + '.p1206-57e27fa4-new')",
     "temp = target.with_name(target.name + '.p1210-%s-new')"),
    ("    assert '57e27fa4' in (R / 'OWNER.md').read_text()", "    assert '%s' in (R / 'OWNER.md').read_text()"),
    ("            # Fallback: the exact P1200 primary (ac283934), on the SAME DB.\\n",
     "            # Fallback: the exact P1206 primary (470ab7c9), on the SAME DB.\\n")])

''' % (ME, ME, ME))
s = seam(s, "print('PREPARED: 83 primary files (changed: %s), 83 fallback files (= live P1200); guard from GEN, live controls; schema 26'",
         "print('PREPARED: 83 primary files (changed: %s), 83 fallback files (= live P1206); guard from GEN, live controls; schema 26'")
(HERE / 'prepare_1210.py').write_bytes(s.encode('utf-8'))
print('kit ok')
