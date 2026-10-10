#!/usr/bin/env python3
"""Mutations cannot turn inert finish/standing evidence into an accepted gate."""
from pathlib import Path
import sys
import unittest

import test_p603scores_unit as local


class FollowEvidenceControls(local.EvidenceControls):
    def test_no_finish_reveal(self): self.field('META', 'local_seek', 'page', 0); self.rejected()
    def test_no_finish_highlight(self): self.field('META', 'local_seek', 'selected', -1); self.rejected()
    def test_repeat_follow(self): self.field('META', 'local_once', 'page', 6); self.rejected()
    def test_finish_held_activation(self): self.field('SCROLL', 'local_held_finish', 'watch', 1); self.rejected()
    def test_wrong_leg_consumed(self): self.field('FOLLOW', 'wrongleg', 'seek', 0); self.rejected()
    def test_closed_seek_consumed(self): self.field('FOLLOW', 'closed_seek', 'seek', 0); self.rejected()
    def test_pending_answer_consumed(self): self.field('FOLLOW', 'online_wait', 'seek', 0); self.rejected()
    def test_stale_reply_consumed(self): self.field('FOLLOW', 'online_stale', 'seek', 0); self.rejected()
    def test_no_parsed_rows(self): self.field('FOLLOW', 'online_seek', 'online', 0); self.rejected()
    def test_missing_online_native(self): self.field('META', 'online_seek', 'painted', 0); self.rejected()
    def test_synthetic_standing_row(self): self.field('META', 'outside', 'count', 32); self.rejected()
    def test_wrong_standing(self):
        self.log('P603 STANDING outside: Your standing #99  0:03.150  P603Fixture',
                 'P603 STANDING outside: Your standing #99  0:01.605  P603Fixture'); self.rejected()
    def test_standing_on_wrong_leg(self):
        self.log('P603 STANDING outside_wrongleg: ',
                 'P603 STANDING outside_wrongleg: Your standing #99  0:03.150  P603Fixture'); self.rejected()
    def test_wrong_body_native(self): self.field('META', 'body_wrongleg', 'painted', 1); self.rejected()
    def test_missing_follow_completion(self): self.log('P603 FOLLOW FINISHED', 'not complete'); self.rejected()
    def test_duplicate_follow(self):
        self.log('P603 META online_seek', 'P603 META online_seek page=0\nP603 META online_seek'); self.rejected()
    def test_missing_follow_field(self):
        self.log('P603 META local_seek page=', 'P603 META local_seek missing='); self.rejected()
    def test_missing_follow_screenshot(self):
        for p in (self.copy / 'native1/ftesurf/screenshots').glob('follow_outside.*'): p.unlink()
        self.rejected()


if __name__ == '__main__':
    if len(sys.argv) != 2: raise SystemExit('usage: test_p603follow_unit.py <follow-runtime-rig>')
    FollowEvidenceControls.rig = Path(sys.argv.pop()).resolve()
    unittest.main()
