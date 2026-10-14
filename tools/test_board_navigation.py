"""Source seam guards; no engine process or runtime claim.

Subject: python tools/test_board_navigation.py
Control: python tools/test_board_navigation.py --root <pre-change checkout>
The control must fail owner/filter/browse guards. Runtime predictions remain:
pictureless duplicate-name owners resolve distinct player IDs, WATCH requests
replays, held TAB does neither; page-two matches retain original ranks; stale
or missing filter echoes show no matches; map picks browse exact scope without
connecting/downloading. These require the parent's serial runtime gate.
"""
import argparse
from pathlib import Path
import hashlib
import unittest

ROOT = Path(__file__).resolve().parents[1]


def source(path):
    return (ROOT / path).read_text(encoding="utf-8")


class BoardNavigation(unittest.TestCase):
    def test_scores_owner_identity_and_deferred_transition(self):
        s = source("src/client/cl_scores.qc")
        self.assertIn('strcat("sb_owner", ftos(idx))', s)
        finish = s[s.index('void(vector p, vector sz, float pad, vector scr, float pick) Scores_Finish'):]
        self.assertLess(finish.index('sui_end();'), finish.index('FS_GuidId(bufstr_get(ob_bplayer, sb_ownerpick))'))
        self.assertLess(finish.index('Scores_SearchPick()'), finish.index('if (sb_ownerpick >= 0)'))
        self.assertIn('else { Scores_Close(); Av_OpenAt(s); }', finish)
        self.assertIn('if (rec_sb_open)', finish)

    def test_online_first_next_echo_and_debounce(self):
        s = source("src/client/cl_online.qc")
        self.assertIn('uri_escape(ob_name)', s)
        self.assertIn('uri_escape(ob_have_name)', s)
        self.assertIn('strcmp(ob_q_name, Profile_BoardQuery())', s)
        self.assertIn('strcmp(ob_have_name, Profile_BoardQuery())', s)
        self.assertIn('json_find_object_child(root, "name")', s)
        self.assertIn('if (!Profile_BoardReady()) return FALSE;', s)
        p = source("src/client/cl_profile.qc")
        self.assertIn('cltime - pf_q_t >= PF_WAIT', p)
        self.assertIn('Profile_Paste', p)
        self.assertIn('strtolower(strtrim(strdecolorize(substring(pf_q, 0, 64))))', p)

    def test_native_owner_watch_and_authority(self):
        s = source("src/client/cl_scores_native.qc")
        self.assertIn('if (Scores_IsOnline()) sb_ownerpick = pick;', s)
        self.assertIn('if (role == 5) { scn_pick = pick; break; }', s)
        self.assertIn('strcmp(Scores_NativeKey(scn_page + r), bufstr_get(scn_keys, r)) == 0', s)
        self.assertIn('context = strcat(context, "|", ob_name);', s)

    def test_profile_row_styles_and_tier_hit_width(self):
        p = source("src/client/cl_profile.qc")
        self.assertIn('Profile_BoardPick(bufstr_get(pf_bmap, i), f[at + 2], f[at], f[at + 1], f[at + 7],', p)
        self.assertIn('r, pf_handle, pf_rms[i]);', p)
        self.assertIn('Profile_BoardPick(bufstr_get(pf_ct_bmap, i), f[at + 1], 0, 0, f[at + 3], 0, "", 0i)', p)
        self.assertIn('#define PF_RF       8', p)
        self.assertIn('#define PF_CF       4', p)
        self.assertIn('json_find_object_child(row, "style")', p)
        self.assertIn('json_find_object_child(row, "s")', p)
        # have means map availability, not completion. Finished unavailable
        # maps must still browse the style of the stored time.
        self.assertIn('f[at + 3] = (f[at] > 0 &&', p)
        self.assertNotIn('f[at + 3] = (f[at + 2] &&', p)
        self.assertIn('[mapw, rowh]', p)
        self.assertIn('Chat_Fit(bufstr_get(pf_ct_bmap, i), mapw, tsz)', p)

    def test_mailbox_deferred_publisher(self):
        p = source("src/client/cl_profile.qc")
        nav = p[p.index('float() Profile_BoardNavigate ='):p.index('// The maps of the tier on show')]
        self.assertIn('cvar_set("ui_board_request", pf_boardrequest);', nav)
        self.assertIn('strcmp(cvar_string("ui_board_request"), pf_boardrequest)', nav)
        self.assertNotIn('localcmd', nav)
        a = source("src/client/cl_avatar.qc")
        self.assertLess(a.index('sui_end();'), a.index('Profile_BoardNavigate()'))

    def test_menu_mailbox_validation_poll_and_all_scope(self):
        b = source("src/menu/m_board.qc")
        signature = 'float(string map, string source, string track, string leg, string style, string rank, string who, string time_ms) Mlb_Browse ='
        self.assertIn(signature, b)
        browse = b[b.index(signature):]
        for forbidden in ('changelevel', 'downloadmap', 'connect', 'ui_launch', 'localcmd'):
            self.assertNotIn(forbidden, browse)
        self.assertLess(browse.index('strzone(map)'), browse.index('ui_create_open();'))
        self.assertIn('Mlb_ScopeNumber(track, 64)', browse)
        self.assertIn('Mlb_ScopeNumber(leg, 256)', browse)
        poll = b[b.index('void() Mlb_PollRequest ='):b.index('// Trusted manual command')]
        self.assertLess(poll.index('cvar_set("ui_board_request", "")'), poll.index('tokenize(payload)'))
        self.assertIn('n == 5 || n == 8', poll)
        self.assertIn('strlen(payload) > 128', poll)
        main = source("src/menu/m_main.qc")
        self.assertIn('registercvar("ui_board_request", "", 0);', main)
        draw = main[main.index('void(vector screensize) m_draw ='):]
        self.assertLess(draw.index('Mlb_Poll();'), draw.index('if (!menu_active)'))
        self.assertIn('if (t == mlb_tab && mlb_source == "") return;', b)
        self.assertIn('if (!strcmp(mlb_source, "all")) return "combined";', b)
        counts = b[b.index('float(float t) Mlb_TabCount ='):b.index('// "KSF')]
        per_tab, active = counts.split('float() Mlb_BoardCount =', 1)
        self.assertNotIn('mlb_source', per_tab)
        self.assertIn('mlb_cksf + mlb_cmom + mlb_cours', active)
        self.assertIn('Mlb_TabCount(mlb_tab)', active)
        self.assertIn('All games: FTESurf, Momentum Mod, KSF', b)

    def test_profile_seek_offset_identity_and_paging(self):
        b = source('src/menu/m_board.qc')
        self.assertIn('off = max(0, pickedrank - 6);', b)
        self.assertIn('off = mlb_offset + mlb_n;', b)
        self.assertIn('off != mlb_offset + mlb_n', b)
        self.assertIn('substring(digest_hex("SHA256", json_get_string(json_find_object_child(row, "player"))), 0, strlen(mlb_focuswho))', b)
        self.assertIn('== mlb_focusms', b)
        self.assertIn('i == mlb_focus', b)
        self.assertIn('"mlb_earlier"', b)
        self.assertIn('"mlb_top"', b)
        p = source('src/client/cl_profile.qc')
        self.assertIn('sui_action_element(lp, [sz_x - tsz, rowh], strcat("pf_map", ftos(i))', p)
        s = source('src/client/cl_scores.qc')
        self.assertIn('f[i + 5], pf_on_handle, pf_on_ms[act - 3]);', s)

    def test_boundary_fixture_preserves_raw_milliseconds(self):
        from test_p693_ui import Fixture, HANDLE, rig
        fixture = Fixture()
        fixture.profile_ms = 2147483647
        fixture.neighbors[1499]['ms'] = 2147483646
        _, profile, _ = fixture.answer('/api/board?player=' + HANDLE[:8])
        self.assertEqual(profile['rows'][0]['ms'], 2147483647)
        _, board, _ = fixture.answer('/api/board?map=surf_result&offset=1494&limit=100')
        self.assertEqual(board['rows'][5]['ms'], 2147483646)
        fixture.on_ms = 16777217
        handle = hashlib.sha256(rig.SID[0].encode()).hexdigest()
        _, compact, _ = fixture.answer('/api/board?player=' + handle[:8] + '&on=' + rig.MAP)
        self.assertEqual(compact['rows'][0]['ms'], 16777217)
        self.assertEqual(compact['who'], handle[:12])

    def test_focus_milliseconds_stay_integer(self):
        p = source('src/client/cl_profile.qc')
        self.assertIn('int   *pf_rms;', p)
        self.assertIn('int   *pf_on_ms;', p)
        self.assertIn('pf_rms[pf_rn] = Profile_JsonInteger', p)
        self.assertIn('pf_on_ms[pf_on_n] = Profile_JsonInteger', p)
        self.assertIn('string who, int time_ms) Profile_BoardPick', p)
        self.assertIn('sprintf(" %.0f %s %s", rank, who, itos(time_ms))', p)
        b = source('src/menu/m_board.qc')
        self.assertIn('int    mlb_focusms;', b)
        self.assertIn('int(string value) Mlb_Stoi = #0:stoi;', b)
        self.assertIn('string(int value) Mlb_Itos = #0:itos;', b)
        self.assertNotIn('Mlb_Stoi = #259', b)
        self.assertNotIn('Mlb_Itos = #260', b)
        self.assertIn('json_get_integer(json_find_object_child(row, "ms")) == mlb_focusms', b)
        self.assertIn('pickedms = Mlb_Stoi(Mlb_Decimal(time_ms));', b)
        self.assertNotIn('pickedms = stof(time_ms)', b)
        validator = b[b.index('float(string value, int limit) Mlb_FocusNumber ='):b.index('float(string map, string source')]
        self.assertLess(validator.index('strcmp(value, bound) > 0'), validator.index('Mlb_Stoi(value)'))
        self.assertIn('Mlb_FocusNumber(time_ms, 2147483647i)', b)
        self.assertIn('value = Mlb_Decimal(value);', validator)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=ROOT)
    args, rest = parser.parse_known_args()
    ROOT = args.root
    unittest.main(argv=[__file__, *rest])
