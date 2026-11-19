"""Focused source seams and offline catalogue refresh checks, not runtime UI proof."""
from pathlib import Path
import json
import unittest

from story_groups import calibrate, courses

ROOT = Path(__file__).resolve().parents[1]


class RemainingRequests(unittest.TestCase):
    def test_story_calibration_is_idempotent_and_keeps_course_identity(self):
        text = (ROOT / 'surfd/story.txt').read_text()
        snapshot = json.loads((ROOT / 'tools/story-groups.json').read_text())
        self.assertEqual(calibrate(text, snapshot), text)
        wanted = courses(text)
        self.assertIn(('surf_autumn_fix', 0), wanted)
        self.assertNotIn(('surf_autumn', 0), wanted)
        self.assertEqual(set(wanted), {(r['map'], r['track']) for r in snapshot['courses']})
        # No made-up distinction when G2 and G4 collapse on a small ladder.
        sample = 'list story "Story"\nchapter\nlevel surf_a\n  gold nofail\n'
        refs = {'courses': [dict(map='surf_a', track=0, src='ksf', x=12, ms=[1000] * 7)]}
        result = calibrate(sample, refs)
        self.assertIn('bronze finish', result)
        self.assertIn('silver time 0:01.001', result)
        self.assertIn('gold time 0:01.001', result)
        self.assertNotIn('nofail', result)

    def test_message_origin_is_frozen_by_sender_not_receiver(self):
        server = (ROOT / 'src/server/sv_social.qc').read_text()
        tag = server.split('string(entity e) Social_RoomTag =', 1)[1].split('float(string who)', 1)[0]
        self.assertIn('e.run_t_track', tag)
        self.assertIn('e.run_t_seg + 1', tag)
        self.assertIn('strcat("[", mapname, course, "] ")', tag)
        self.assertNotIn('sv_port', tag)
        self.assertIn('strcat(Social_RoomTag(e), uri_unescape(text))', server)
        menu = (ROOT / 'src/menu/m_chat.qc').read_text()
        self.assertIn('json_find_object_child(row, "text")', menu)
        self.assertNotIn('mapname', menu)  # saved origin is not rebuilt on receiving

    def test_stage_toast_uses_splits_editor_and_plain_hud_text(self):
        source = (ROOT / 'src/client/cl_results.qc').read_text()
        toast = source.split('void(vector scr) Results_DrawToast =', 1)[1].split('The card.', 1)[0]
        for key in ['hud_splits', 'hud_splits_x', 'hud_splits_y', 'hud_splits_size']:
            self.assertIn('"' + key + '"', toast)
        self.assertIn('strcmp(hude_id[i], "splits") == 0', toast)
        self.assertIn('HUD_Rect("splits"', toast)
        self.assertIn('ui_he_open', toast)
        self.assertIn('"#12 of 145"', toast)
        self.assertNotIn('_sui_round_draw', toast)
        self.assertNotIn('8 * u +', toast)
        self.assertNotIn('run_', toast)

    def test_normal_mode_label_reserves_fixed_width_in_both_boards(self):
        source = (ROOT / 'src/client/cl_scores.qc').read_text()
        self.assertIn('Scores_Mode() == 0 ? "Mode: Normal" : "Mode"', source)
        self.assertIn('x = x + ceil(stringwidth("Mode: Normal"', source)
        self.assertNotIn("THE ONLINE LIST'S FILTER -- a switch", source)
        menu = (ROOT / 'src/menu/m_board.qc').read_text()
        self.assertIn('on == 0 ? "Normal" : "Mode"', menu)
        self.assertIn('x = x + ceil(stringwidth("Normal"', menu)


if __name__ == '__main__':
    unittest.main()
