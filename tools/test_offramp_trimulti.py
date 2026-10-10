#!/usr/bin/env python3
"""Multi-patch actors: fixture/installer units + ACTED native falsifiers on retained arms."""
import argparse
from contextlib import redirect_stderr
from copy import deepcopy
from fractions import Fraction as F
import io
import json
import math
from pathlib import Path
import re
import struct
import sys
import unittest
from unittest.mock import patch

import offramp_bevpm as pm
import offramp_trimulti as multi
import offramp_trimulti_smoke as installer
import offramp_trireach as walk
import offramp_trisupport as reach

ARMS = None
CASES = re.compile(r'OFFRAMPTRIMULTI_CASE [0-9]+ .*?(?=OFFRAMPTRIMULTI_CASE_END)', re.S)
SINGLE, ALONG, CREASE = multi.SINGLE, multi.ALONG, multi.CREASE
NEVER = 'NOT_ACTED_IN_THESE_ACTORS'
# What became of reach on a track: never lost, lost and back, lost for good.
KEPT, BACK, GONE = (dict(reached_at_start=True, reached_at_end=end, times_lost=lost, times_regained=back)
                    for end, lost, back in ((True, 0, 0), (True, 1, 1), (False, 1, 0)))
WHOLE, LOST = [[F(0), F(1)]], [F(0), F(7, 24)]
# Ramp-flag commands: riding to the end; riding, falling across a gap, landed; boarded and never back.
RODE, FELL, BOARDED = list(range(2, 32)), [*range(2, 10), *range(14, 32)], list(range(2, 10))
# The 1/32 collision bias along a 0.6-steep normal, measured straight down: the height a hull rides at.
RIDE = 1/32/.6
# Path and capture rows are mutated field by field on the recontact, lift, wall and trough actors.
FIELD_ACTORS, ROW_ACTORS = (2, 4, 6, 7), (2, 6, 7)


def bumped(line, column, step=None):
    """The same row with one field changed.

    An integer moves by one, so the MEANING behind it has to refuse and not
    merely the integer parser; another number moves by 1/8 (or `step`); a word
    becomes a foreign word.
    """
    words = line.split()
    try:
        words[column] = str(int(words[column])+1) if step is None else repr(float(words[column])+step)
    except ValueError:
        try:
            words[column] = repr(float(words[column])+(.125 if step is None else step))
        except ValueError:
            words[column] = 'x'
    return ' '.join(words)


def single(x):
    """The float32 nearest x: equal to x only when native stores it exactly."""
    return struct.unpack('f', struct.pack('f', x))[0]


def row(text, start):
    return next(l[l.find(start):] for l in text.splitlines() if start in l)


def forged(block, edits):
    """Several rows moved TOGETHER: {row start: {word: delta}}. A consistent lie only one gate can see."""
    for start, changes in edits.items():
        old = row(block, start)
        new = old
        for column, delta in changes.items():
            new = bumped(new, column, delta)
        block = block.replace(old, new, 1)
    return block


class Units(unittest.TestCase):
    def test_authored_patches_are_upward_exact_on_their_plane_family_and_twins_match(self):
        count = len(multi.ACTORS)
        self.assertEqual((count, [len(multi.authored(i)) for i in range(count)]), (11, [4, 4, 4, 4, 2, 4, 4, 4, 2, 2, 2]))
        self.assertEqual(multi.authored(2), multi.authored(3))
        for actor in range(count):
            for j, triangle in enumerate(multi.authored(actor)):
                a, b, c = (reach.vector(v) for v in triangle)
                normal = reach.cross(reach.sub(a, b), reach.sub(c, b))
                # 0.8x+0.6z=const, and for the trough's far side its mirror image; wound so the front faces up.
                mirrored = actor == 7 and j > 1
                self.assertEqual((normal[0]*3, normal[1]), (normal[2]*(-4 if mirrored else 4), 0))
                self.assertGreater(normal[2], 0)
                self.assertTrue(all(single(x) == x for v in triangle for x in v))
            self.assertTrue(all(single(x) == x for x in multi.ACTORS[actor]['velocity']+multi.ORIGIN))
        low = multi.authored(2)[2]
        self.assertEqual(low, [[0, 114, -2], [0, 256, -2], [192, 256, -258]])
        self.assertEqual({F(4, 5)*x+F(3, 5)*z for x, _, z in low}, {F(-6, 5)})
        # The 2 x 2: gap width by neighbour height, every other parameter shared.
        cell = lambda i: (multi.ACTORS[i]['y2']-multi.ACTORS[i]['y1'], multi.ACTORS[i]['drop'])
        self.assertEqual([cell(i) for i in multi.GAP_DESIGN], [(16, 0), (50, 2), (16, 2), (50, 0)])
        self.assertEqual({(a['y1'], a['authored'], a['live'], tuple(a['velocity'])) for a in (multi.ACTORS[i] for i in multi.GAP_DESIGN)},
                         {(64, 4, 4, (0, 400, 0))})
        # The trough: both planes pass through its line x 72, z -96, and nothing else is shared.
        near, _, far, _ = multi.authored(7)
        exact = lambda triangle: [reach.vector(v) for v in triangle]
        self.assertEqual(({F(4, 5)*x+F(3, 5)*z for x, _, z in exact(near)}, {F(-4, 5)*x+F(3, 5)*z for x, _, z in exact(far)}),
                         ({0}, {F(-576, 5)}))
        self.assertEqual(sorted(v for v in near if v in far), [[72, 256, -96]])
        self.assertEqual(multi.authored(8)[0], [[0, 0, 0], [0, 8.0078125, 0], [192, 8.0078125, -256]])

    def test_unknown_malformed_duplicate_and_outside_rows_refuse(self):
        envelope = 'OFFRAMPTRIMULTI_BEGIN 3 0 0 11 32\nOFFRAMPTRIMULTI_END 11\n'
        self.assertEqual(multi.split('a\n'+envelope+'b\n'), ('a\nb\n', envelope))
        # Unknown and malformed rows sit INSIDE an envelope, so only the row gate can refuse them.
        for text, message in ((envelope.replace('OFFRAMPTRIMULTI_END 11', 'OFFRAMPTRIMULTI_UNKNOWN 1\nOFFRAMPTRIMULTI_END 11'), 'unknown/malformed'),
                              (envelope.replace(' 11 32\n', ' 11\n'), 'unknown/malformed'), (envelope+envelope, 'missing/duplicate'),
                              ('no envelope', 'missing/duplicate'), (envelope+'OFFRAMPTRIMULTI_LEAVES 0 4 0\n', 'outside envelope')):
            with self.subTest(text=text[-40:]), self.assertRaisesRegex(AssertionError, message): multi.split(text)
        self.assertEqual(multi.foreign('x OFFRAMPGEOM_BEGIN 2\nOFFRAMPTRIMULTI_TICK 0\nOFFRAMPTRIMULTIX_ROW 1'),
                         ['OFFRAMPGEOM_', 'OFFRAMPTRIMULTIX_'])

    def test_coplanar_bevel_ties_the_face_and_coplanar_neighbours_tie_each_other(self):
        first, second = multi.authored(0)[:2]
        start, end = [46, 24, -39.5], [46, 24, -41.5]
        found = multi.candidates(first, start, end)
        tags = [c['clipped']['entry_plane']['tag'] for c in found]
        # Tag 8 is the slope-direction edge crossed with y: the face plane again. A second such bevel (11)
        # is oriented by rounding alone, here and natively, because its off-vertex lies IN the plane.
        self.assertEqual((tags[:2], set(tags) <= {0, 8, 11}), ([0, 8], True))
        self.assertEqual(len({c['clipped']['enter'] for c in found}), 1)
        self.assertTrue(all(pm.close(c['clipped']['entry_plane']['normal'], [.8, 0, .6], 1e-12) and
                            abs(c['clipped']['entry_plane']['dist']) < 1e-12 for c in found))
        both = multi.native_prediction([first, second], start, end)
        self.assertEqual(len(both), len(found)+len(multi.candidates(second, start, end)))
        self.assertEqual({c['triangle'] for c in both}, {0, 1})
        self.assertEqual(multi.native_prediction([first, second], [46, 24, 50], [46, 24, 48]), [dict(expected=multi.MISS)])
        self.assertEqual(multi.native_prediction([], start, end), [dict(expected=multi.MISS)])
        with self.assertRaisesRegex(AssertionError, 'embedded'):
            multi.native_prediction([first], [46, 24, -41], [46, 24, -43])
        hit = [*both[0]['expected'], *[s+both[0]['expected'][0]*(e-s) for s, e in zip(start, end)]]
        self.assertEqual(multi.check_trace(hit, start, end, [first, second]), dict(triangles=2, candidates=len(both), planes=1))
        self.assertEqual(multi.check_trace(hit, start, end, [first]), dict(triangles=1, candidates=len(found), planes=1))
        self.assertEqual(multi.check_trace([*multi.MISS, 46, 24, 48], [46, 24, 50], [46, 24, 48], [first]),
                         dict(triangles=0, candidates=0, planes=0))
        # The second triangle's two face-plane bevels are turned to the BACK in this model. Native may turn
        # them the other way in float32 and then name one as its winner: that tag is the face, and only that.
        behind = multi.candidates(second, start, end)
        self.assertEqual([c['clipped']['entry_plane']['tag'] for c in behind], [0])
        for tag in (6, 11):
            (turned,) = multi.named_plane(behind, tag)
            self.assertEqual((turned['turned_bevel'], turned['clipped']['entry_plane']['tag'], turned['expected']), (True, 0, behind[0]['expected']))
        self.assertEqual(multi.named_plane(behind, 0), behind)
        # Not any other bevel, not a side or an axis, and not the back plane itself, though it too is the face turned.
        self.assertEqual([multi.named_plane(behind, tag) for tag in (5, 2, 100, 1)], [[]]*4)
        (direct,) = multi.named_plane(found, 8)
        self.assertEqual((direct['clipped']['entry_plane']['tag'], 'turned_bevel' in direct), (8, False))
        self.assertEqual(multi.named_plane([], 0), [])

    def test_a_box_wedged_in_the_trough_ties_two_planes_that_are_not_coplanar(self):
        trough = multi.authored(7)
        # Hull edges 1/32 off both planes: x-min edge over A at x 56, x-max edge over B at x 88.
        start = [72, 128, -56*4/3+(1/32)/.6]
        end = [72, 128, start[2]-.18]
        found = multi.native_prediction(trough, start, end)
        self.assertEqual({c['triangle'] for c in found}, {1, 2})
        normals = {tuple(round(x, 9) for x in c['expected'][5:8]) for c in found}
        self.assertEqual(normals, {(.8, 0, .6), (-.8, 0, .6)})
        self.assertLess(max(c['clipped']['enter'] for c in found)-min(c['clipped']['enter'] for c in found), 1e-9)
        for candidate in found:  # either plane may be the one native reports
            hit = [*candidate['expected'], *[s+candidate['expected'][0]*(e-s) for s, e in zip(start, end)]]
            self.assertEqual(multi.check_trace(hit, start, end, trough)['planes'], 2)
        self.assertEqual(multi.entry_planes(trough, start, end)[0][2], 'front')
        # A hull sunk 2/3 of a unit below the far strip's plane, swept at its edge, enters planes that are
        # one wall: the side, two bevels and the raw y axis. Level with the ride height it passes over instead.
        wide = multi.authored(6)
        start, end = [50, 96, -46], [50, 102, -46]
        wall = multi.entry_planes(wide, start, end)
        self.assertEqual(({w[0] for w in wall}, {w[2] for w in wall}), ({3}, {'side', 'bevel', 'raw-triangle-axial'}))
        near = 1/3-1/32/6
        self.assertEqual(multi.check_trace([near, 1/3, 0, 0, 0, 0, -1, 0, -114, 1, 50, 96+6*near, -46], start, end, wide)['planes'], 1)
        self.assertEqual(multi.entry_planes(wide, [50, 96, -44], [50, 102, -44]), [])

    def test_plane_list_clears_on_any_move_and_the_clip_rules_are_the_movers(self):
        a, b, wall = [.8, 0, .6], [-.8, 0, .6], [0, 1, 0]
        self.assertEqual(multi.plane_list([], a, .3), [a])
        self.assertEqual(multi.plane_list([a], b, 0), [a, b])
        self.assertEqual(multi.plane_list([a, b], wall, 0), [a, b, wall])
        # A hit after a positive move is the one-plane branch again, however small the move.
        self.assertEqual(multi.plane_list([a, b], wall, 1e-9), [wall])
        entered = [0, 400, -12]
        (along_a, rule), = multi.clip_rules(entered, [a], entered)
        self.assertTrue(pm.close(along_a, [5.76, 400, -7.68], 1e-12) and rule == SINGLE)
        self.assertEqual(multi.clip_velocity([1, 0, 0], [-1, 0, 0]), [0, 0, 0])
        # The corrective pass acts only when the normal is short of unit length; a long one leaves the result alone.
        self.assertTrue(pm.close(multi.clip_velocity([0, 0, -1], [0, 0, .9]), [0, 0, -.0361], 1e-12))
        self.assertTrue(pm.close(multi.clip_velocity([0, 0, -1], [0, 0, 1.1]), [0, 0, .21], 1e-12))
        # Along A heads into B, along B heads into A: the crease, the last clip projected on A x B.
        (crease, rule), = multi.clip_rules(along_a, [a, b], entered)
        self.assertTrue(pm.close(crease, [0, 400, 0], 1e-12) and rule == CREASE)
        self.assertEqual(multi.clip_rules(along_a, [b, a], entered)[0][1], CREASE)
        # The first plane whose clip heads into no other wins, and no later plane is tried.
        self.assertEqual(multi.clip_rules(entered, [a, wall], entered), [(multi.clip_velocity(entered, a), ALONG)])
        # The mover's clip removes the normal component even when it points AWAY from the plane, so the
        # wall's own clip heads into A and A wins whichever of the two was hit first.
        self.assertEqual(multi.clip_velocity(entered, wall), [0, 0, -12])
        self.assertEqual(multi.clip_rules(entered, [wall, a], entered), [(multi.clip_velocity(entered, a), ALONG)])
        # A sign test within 1e-3 u/s of zero keeps both outcomes; outside it there is one. A floor and a side
        # wall at right angles: the floor's clip leaves `lean` u/s towards (-) or away from (+) the wall.
        floor, side = [0, 0, 1], [0, 1, 0]
        rules = lambda lean: [rule for _, rule in multi.clip_rules([1, lean, -1], [floor, side], [1, lean, -1])]
        self.assertEqual([rules(lean) for lean in (5e-3, 5e-4, -5e-4, -5e-3)], [[ALONG], [ALONG, CREASE], [ALONG, CREASE], [CREASE]])
        # Both rules can leave ONE velocity, a wall joined to a ramp for one: the row cannot say which it was.
        tied = multi.clip_rules(along_a, [a, [0, -1, 0]], entered)
        self.assertEqual([rule for _, rule in tied], [ALONG, CREASE])
        self.assertTrue(pm.close(tied[0][0], tied[1][0], 1e-12) and pm.close(tied[0][0], [5.76, 0, -7.68], 1e-12))
        self.assertEqual(multi.clip_rule([5.76, 0, -7.68], along_a, [a, [0, -1, 0]], entered)[0], multi.EITHER)
        name, error = multi.clip_rule([0, 399.99994, 0], along_a, [a, b], entered)
        self.assertTrue(name == CREASE and 5e-5 < error < 7e-5)
        self.assertEqual(multi.clip_rule(along_a, entered, [a], entered), (SINGLE, 0))
        with self.assertRaisesRegex(AssertionError, 'differs from every native clip rule'):
            multi.clip_rule([0, 401, 0], along_a, [a, b], entered)
        # Three planes return nothing even when one of them alone would do. A choice: no capture reaches a third.
        self.assertEqual((multi.clip_rules(entered, [a, wall], entered)[0][1], multi.clip_rules(entered, [a, wall, [1, 0, 0]], entered)),
                         (ALONG, []))
        self.assertEqual(multi.clip_rules(along_a, [a, b, [0, -1, 0]], entered), [])
        # One plane hit twice is gone along; native's other answer there, the push, stops the body and is an outcome code.
        self.assertEqual({rule for _, rule in multi.clip_rules(along_a, [a, a], entered)}, {ALONG})
        # Planes facing each other have no crease: native's normalised cross product is zero and so is the result.
        self.assertEqual({rule for _, rule in multi.clip_rules(entered, [a, [-.8, 0, -.6]], entered)}, {ALONG})
        # Two walls 30 degrees apart met head-on (from the review). The second clip is acceptable to the first
        # wall but OPPOSES the velocity the command entered with, so in the multi-plane branch the mover stops
        # and nothing comes back. It is the ENTRY velocity that is asked: the current one would say go on.
        entry = [100, 0, 0]
        first, second = ([math.cos(math.radians(d)), math.sin(math.radians(d)), 0] for d in (200, 170))
        glanced = multi.clip_velocity(entry, first)
        back = multi.clip_velocity(glanced, second)
        self.assertTrue(pm.close(glanced, [11.6978, -32.1394, 0], 1e-4) and pm.close(back, [-5.1434, -29.1698, 0], 1e-4))
        self.assertTrue(multi.dot(back, entry) < -500 and multi.dot(back, glanced) > 800 and multi.dot(back, first) > 0)
        self.assertEqual(multi.clip_rules(glanced, [first, second], entry), [])
        # Native's test is d <= 0: a result of exactly nothing, here a head-on wall then a side wall, is a stop too.
        self.assertEqual(multi.clip_rules([100, 0, 0], [[-1, 0, 0], [0, 1, 0]], [100, 0, 0]), [])
        # The one-plane branch has no such bail: after a move the same clip is simply taken.
        self.assertEqual(multi.clip_rules(glanced, [second], entry), [(back, SINGLE)])
        self.assertEqual(multi.clip_rules([10, 0, 0], [[-1, 0, 0]], [10, 0, 0]), [([0, 0, 0], SINGLE)])
        # The tolerance is 8e-5 plus two float32 steps of the speed, for every rule: above 1,024 u/s one step is 1.2e-4.
        self.assertEqual(multi.clip_tolerance([0, 0, 0]), 8e-5)
        self.assertAlmostEqual(multi.clip_tolerance([0, 400, 0]), 8e-5+9.6e-5, delta=1e-12)
        self.assertGreater(multi.clip_tolerance([0, 1100, 0]), 2*2**-13)

    def test_the_clip_tolerance_grows_with_speed_for_one_plane_too(self):
        # An honest one-plane clip at 3,000 u/s on the captured ramp normal. Native's result is by a float32
        # transcription of the mover's clip that reproduces all 242 captured ones text for text; it sits 1.8e-4
        # from the rule, and a flat 8e-5 would refuse it.
        # (From the review: only the crease pinned the speed term, so a flat tolerance for one plane passed.)
        normal, velocity = [.800000012, 0, .600000024], [1773.55823, 489.838715, -2369.50586]
        native = [1775.84387, 489.838715, -2367.7915]
        rule, error = multi.clip_rule(native, velocity, [normal], velocity)
        self.assertTrue(rule == SINGLE and 2*8e-5 < error < 1.9e-4)
        self.assertAlmostEqual(multi.clip_tolerance(velocity), 8e-5+2.4e-7*3000.0015, delta=1e-9)
        # The room that leaves at this speed: a lie of 5e-4 u/s passes and one of 1.2e-3 does not.
        self.assertEqual(multi.clip_rule([native[0]+5e-4, *native[1:]], velocity, [normal], velocity)[0], SINGLE)
        with self.assertRaisesRegex(AssertionError, 'differs from every native clip rule'):
            multi.clip_rule([native[0]+1.2e-3, *native[1:]], velocity, [normal], velocity)

    def test_a_hit_plane_is_a_ramp_or_a_wall_and_anything_else_refuses(self):
        for normal, want in (([.8, 0, .6], 'RAMP'), ([.8, 0, -.6], 'RAMP'), ([0, .714, .7], 'RAMP'), ([.99, 0, .1], 'RAMP'),
                             ([0, -1, 0], 'WALL'), ([.6, .8, 1e-8], 'WALL'), ([1, 0, -0.0], 'WALL')):
            with self.subTest(normal=normal): self.assertEqual(multi.contact_class(normal), want)
        for normal in ([0, 0, 1], [.6, 0, .8], [0, .7, .714], [.99, 0, .05], [0, 0, -1], [1, 0, 1e-6]):
            with self.subTest(normal=normal), self.assertRaisesRegex(AssertionError, 'floor or neither ramp nor wall'):
                multi.contact_class(normal)

    def test_margins_are_exact_and_the_sharpest_tick_end_is_per_side(self):
        patch_ = multi.authored(4)
        self.assertEqual(multi.margins(patch_, [46, 24, -39.5]), dict(least_down_distance=F(1, 2), footprint_bounding_slack=32))
        self.assertEqual(multi.margins(patch_, [46, 24, -37.5])['least_down_distance'], F(5, 2))
        # Through the plane: the hull meets the front where it is. Beside the patch: nothing below, slack negative.
        self.assertEqual(multi.margins(patch_, [46, 24, -60])['least_down_distance'], 0)
        self.assertEqual(multi.margins(patch_, [46, 300, -39.5]), dict(least_down_distance=None, footprint_bounding_slack=-28))
        self.assertEqual(multi.margins(patch_, [46, 272.25, -39.5])['footprint_bounding_slack'], F(-1, 4))
        strip = multi.authored(8)
        self.assertEqual(multi.margins(strip, [46, 24.0078125, -39.5])['footprint_bounding_slack'], 0)
        self.assertEqual(multi.margins(strip, [46, 24.0078125, -39.5])['least_down_distance'], F(1, 2))
        self.assertIsNone(multi.margins(strip, [46, 24.015625, -39.5])['least_down_distance'])
        end = lambda tick, down, slack: dict(tick=tick, least_down_distance=down, footprint_bounding_slack=slack)
        cases = [dict(tick_ends=[end(0, F(1, 2), 32), end(1, F(21, 10), 30), end(2, F(199, 100), 1)]),
                 dict(tick_ends=[end(0, None, F(-1, 4)), end(1, None, -3), end(2, F(5, 2), F(1, 8))])]
        found = multi.sharpest(cases, 2)
        self.assertEqual([(found[k]['actor'], found[k]['tick']) for k in ('horizon_inside', 'horizon_outside', 'footprint_inside', 'footprint_outside')],
                         [(0, 2), (0, 1), (1, 2), (1, 0)])
        self.assertIsNone(multi.sharpest([dict(tick_ends=[end(0, F(1, 2), 32)])], 2)['horizon_outside'])
        # What became of reach: kept, lost and back, lost for good, a touch that is no regain, never there.
        half, third = F(1, 2), F(1, 3)
        self.assertEqual([multi.reach_outcome(c) for c in ([[0, 1]], [[0, third], [half, 1]], [[0, third]])], [KEPT, BACK, GONE])
        self.assertEqual(multi.reach_outcome([[0, third], [half, half]]), dict(GONE, times_lost=2))
        self.assertEqual(multi.reach_outcome([]), dict(reached_at_start=False, reached_at_end=False, times_lost=0, times_regained=0))
        self.assertEqual(multi.reach_outcome([[third, 1]]), dict(reached_at_start=False, reached_at_end=True, times_lost=0, times_regained=0))
        # A label is a claim: each is VERIFIED or GRADED only for a rule some hit took.
        none, refused = multi.exercised({SINGLE: 9, ALONG: 0, CREASE: 0}, 0), 'REFUSED_SO_NOT_EXERCISED'
        self.assertEqual(none, dict(multi_plane_clip=dict(two_plane_crease='NOT_EXERCISED', along_one_plane='NOT_EXERCISED',
                                                          three_or_more_planes=refused, stopping_outcomes=refused),
                                    wall_return='NOT_EXERCISED', floor_contact=refused))
        some = multi.exercised({SINGLE: 0, ALONG: 1, CREASE: 0}, 2)
        self.assertEqual((some['multi_plane_clip']['along_one_plane'], some['multi_plane_clip']['two_plane_crease'], some['wall_return']),
                         ('VERIFIED_ON_CAPTURED_HITS', 'NOT_EXERCISED', 'GRADED_ON_CAPTURED_HITS'))
        self.assertEqual(multi.exercised({SINGLE: 0, ALONG: 0, CREASE: 3}, 0)['multi_plane_clip']['two_plane_crease'], 'VERIFIED_ON_CAPTURED_HITS')
        # The horizon is the CLOSED range: a front exactly 2 down is reached, and is the nearest inside.
        on = multi.sharpest([dict(tick_ends=[end(0, F(2), 32), end(1, F(199, 100), 32), end(2, F(201, 100), 32)])], 2)
        self.assertEqual((on['horizon_inside']['tick'], on['horizon_outside']['tick']), (0, 2))

    def test_sat_only_sensitivity_equals_certified_coverage_and_nests(self):
        triangles = multi.authored(4)
        points = [[46, 24, -39.5], [47, 30, -36], [48, 36, -39]]
        shares = [F(1, 2), F(1, 2)]
        certified = walk.path_reach(triangles, points, shares, multi.MINS, multi.MAXS, 2)
        rational = [reach.vector(p) for p in points]
        found = [multi.sensitivity(triangles, rational, shares, h) for h in (2, 4, 8)]
        self.assertEqual(found[0]['coverage'], certified['coverage'])
        self.assertTrue(0 < len(found[0]['coverage']) and found[0]['coverage'] != found[2]['coverage'])
        for inner, outer in zip(found, found[1:]):
            self.assertTrue(all(any(a <= lo and hi <= b for a, b in outer['coverage']) for lo, hi in inner['coverage']))
        here, deep = (walk.path_reach(triangles, points, shares, multi.MINS, multi.MAXS, h)['segments'] for h in (0, 2))
        self.assertEqual(multi.edge_checks(here, deep, 2), dict(segments=2, domain_pairs=4, nonempty_segments=0, nonempty_domains=0))
        sunk = [[46, 24, -41], [46, 30, -41]]  # through the plane: both triangles under the hull edge
        here, deep = (walk.path_reach(triangles, sunk, [F(1)], multi.MINS, multi.MAXS, h)['segments'] for h in (0, 2))
        self.assertEqual(multi.edge_checks(here, deep, 2), dict(segments=1, domain_pairs=2, nonempty_segments=1, nonempty_domains=2))

    def test_removed_twin_must_share_a_prefix_then_part_and_have_fewer_leaves(self):
        tick = lambda x: [0]*10+[x, 0, 0, 0, 0, 0]
        kept = dict(ticks=[tick(1), tick(2), tick(3)], native_leaves=[0, 1, 2, 3])
        parted = dict(ticks=[tick(1), tick(2), tick(9)], native_leaves=[0, 1])
        self.assertEqual(multi.removal_acts(kept, parted), 2)
        for twin in (dict(parted, ticks=kept['ticks']), dict(parted, ticks=[tick(9), tick(2), tick(3)]),
                     dict(parted, native_leaves=kept['native_leaves'])):
            with self.assertRaisesRegex(AssertionError, 'did not ACT'): multi.removal_acts(kept, twin)
        self.assertEqual((multi.first_difference(kept, parted), multi.first_difference(kept, dict(parted, ticks=kept['ticks'])),
                          multi.first_difference(kept, dict(parted, ticks=[tick(9), tick(2), tick(3)]))), (2, None, 0))
        # A body is origin AND velocity: the same place at another speed already differs.
        faster = [tick(1), [0]*10+[2, 0, 0, 0, 7, 0], tick(3)]
        self.assertEqual(multi.first_difference(kept, dict(parted, ticks=faster)), 1)

    def test_predecessor_report_must_equal_a_retained_one_when_one_is_given(self):
        prior = dict(count=3, coverage=[[F(0), F(1, 2)]], nested=dict(flag='PASS'))
        retained = dict(count=3, coverage=[['0', '1/2']], nested=dict(flag='PASS'), arms='theirs')
        self.assertEqual(multi.same_prior(prior, retained), 'EQUAL_TO_RETAINED_REPORT')
        for bad in (dict(retained, count=4), dict(retained, coverage=[['0', '1/3']]), {k: v for k, v in retained.items() if k != 'nested'}):
            with self.assertRaisesRegex(AssertionError, 'differs from the retained one'): multi.same_prior(prior, bad)

    def test_installer_collision_and_missing_seam_write_nothing(self):
        root = Path('unpopulated-readonly-engine')
        prior = {root/'engine/common/pm_source.c': 'no forward declaration here', root/'engine/common/com_bih.c': ''}
        # Only THIS layer's includes exist, and the earlier layers are stubbed, so only this layer's check can refuse.
        mine = lambda self: self.name in installer.TARGETS
        with patch.object(installer, 'isolated'), patch.object(Path, 'exists', mine), \
                patch.object(installer, 'path_prepare', return_value=dict(prior)) as earlier, patch.object(Path, 'write_text') as write:
            with self.assertRaisesRegex(RuntimeError, 'multi-patch include'): installer.instrument(root)
            earlier.assert_not_called(); write.assert_not_called()
        with patch.object(installer, 'isolated'), patch.object(Path, 'exists', return_value=False), \
                patch.object(installer, 'path_prepare', return_value=dict(prior)), patch.object(Path, 'write_text') as write:
            with self.assertRaisesRegex(RuntimeError, 'seam mismatch'): installer.instrument(root)
            write.assert_not_called()

    def test_existing_report_refuses_before_read_or_write(self):
        with patch.object(sys, 'argv', ['multi', '--arms', 'absent', '--output', 'existing']), \
                patch.object(Path, 'exists', return_value=True), patch.object(multi, 'load_arms') as load, \
                patch.object(Path, 'open') as opened, redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as error: multi.main()
            self.assertEqual(error.exception.code, 2); load.assert_not_called(); opened.assert_not_called()


@unittest.skipUnless(ARMS, 'Retained native arms not supplied; NOT runtime evidence')
class Native(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.texts, _ = multi.load_arms(ARMS)
        cls.result = multi.compare(*cls.texts)
        cls.cases, cls.native = cls.result['cases'], cls.result['native_cases']
        cls.blocks = {name: CASES.findall(multi.split(text)[1]) for name, text in zip(multi.NAMES, cls.texts)}
        real, cache = multi.candidates, {}
        def cached(triangle, start, end):
            key = (repr(triangle), repr(start), repr(end))
            if key not in cache:
                cache[key] = real(triangle, start, end)
            return cache[key]
        # One row changes per mutant; every other prediction is the same. Patched in as a plain function:
        # a Mock keeps every call it ever received, and that was 2.1 GB in the field tests.
        cls.cached = staticmethod(cached)

    def refusals(self, arm, capture, oracle, prefix, cases=range(len(multi.ACTORS)), keep=lambda words, column: True):
        acted = 0
        with patch.object(multi, 'candidates', self.cached):
            for case in cases:
                block = self.blocks[arm][case]
                multi.grade_case(block, case, capture, oracle)
                for line in [l[l.find(prefix):] for l in block.splitlines() if prefix in l]:
                    words = line.split()
                    for column in range(1, len(words)):
                        if not keep(words, column):
                            continue
                        mutated = block.replace(line, bumped(line, column), 1)
                        self.assertNotEqual(mutated, block)
                        with self.subTest(case=case, row=' '.join(words[:3]), column=column), self.assertRaises(AssertionError):
                            multi.grade_case(mutated, case, capture, oracle)
                        acted += 1
        return acted

    def test_registered_structure_and_measured_counts(self):
        r, each = self.result, lambda key: [c[key] for c in self.cases]
        path_counts = lambda key: [n['path'][key] for n in self.native]
        self.assertEqual(path_counts('attempt_count'), [62, 62, 58, 40, 50, 58, 41, 80, 47, 56, 56])
        self.assertEqual(path_counts('hit_count'), [30, 30, 26, 8, 18, 26, 8, 48, 15, 24, 24])
        self.assertEqual([len(n['path']['wall_hits']) for n in self.native], [0]*6+[1]+[0]*4)
        self.assertEqual((r['native_attempt_count'], r['accepted_copied_hit_count'], r['committed_segment_count'],
                          r['native_endpoint_validation_count'], r['wall_hit_count'], r['tick_end_count']), (610, 257, 610, 112, 1, 352))
        ramp = [[c['command_index'] for c in case['commands'] if c['native_ramp_return']] for case in self.cases]
        self.assertEqual(ramp, [RODE, RODE, FELL, BOARDED, list(range(14, 32)), FELL, BOARDED, RODE,
                                list(range(2, 17)), list(range(8, 32)), list(range(8, 32))])
        self.assertEqual([case['native_hits'][0]['command_index'] for case in self.cases], [2, 2, 2, 2, 14, 2, 2, 2, 2, 8, 8])
        self.assertTrue(all(case['native_hits'][0]['committed_fraction'] > .1 for case in self.cases))
        # How every hit was clipped, the 257 ramp contacts and the one wall; every other attempt was a clear move.
        self.assertEqual(r['clip_rule_counts'], {SINGLE: 242, ALONG: 0, CREASE: 16, multi.EITHER: 0})
        rules = [s['clip_rule'] for case in self.cases for c in case['commands'] for s in c['segments']]
        self.assertEqual((rules.count(None), len(rules)), (352, 610))
        self.assertEqual((r['second_plane_command_count'], r['down2_disagreement_count'], r['down2_disagreements']), (16, 0, []))
        # Per rule and from the counts: the crease was taken, "along one plane" never, and what refuses cannot be in a pass.
        self.assertEqual(r['multi_plane_clip'], dict(two_plane_crease='VERIFIED_ON_CAPTURED_HITS', along_one_plane='NOT_EXERCISED',
                                                     three_or_more_planes='REFUSED_SO_NOT_EXERCISED', stopping_outcomes='REFUSED_SO_NOT_EXERCISED'))
        self.assertEqual(each('second_plane_commands'), [[]]*7+[list(range(16, 32))]+[[]]*3)
        # Only the trough has a command of more than two attempts, or a hit that is not its command's first.
        self.assertEqual([sorted({len(c['segments']) for c in case['commands']}) for case in self.cases], [[1, 2]]*7+[[1, 2, 3, 4]]+[[1, 2]]*3)
        self.assertEqual((each('later_bump_hit_count'), r['later_bump_hit_count'], r['max_attempts_in_a_command']), ([0]*7+[18]+[0]*3, 18, 4))
        self.assertEqual(r['live_horizon2_reach_regained'], [NEVER, NEVER, 'OBSERVED', NEVER, 'OBSERVED', 'OBSERVED', NEVER, NEVER, NEVER, 'OBSERVED', NEVER])
        # "Not regained" alone hides whether reach was ever lost: four never lose it, three lose it for good.
        self.assertEqual(r['live_horizon2_reach_outcome'], [KEPT, KEPT, BACK, GONE, BACK, BACK, GONE, KEPT, GONE, BACK, KEPT])
        # Measured, not predicted: how much the gates had to compare, and how much of it is distinct.
        self.assertEqual(path_counts('validation_count'), [2, 2, 6, 24, 14, 6, 23, 2, 17, 8, 8])
        self.assertEqual(r['distinct'], dict(attempts=469, hits=200, tick_end_bodies=267, zero_length_segments=215))
        self.assertEqual((each('triangle_tie_trace_count'), each('plane_only_tie_trace_count'), each('different_plane_tie_trace_count')),
                         ([12, 10, 7, 0, 0, 5, 0, 20, 0, 0, 0], [18, 18, 15, 8, 18, 21, 9, 2, 15, 24, 24], [0]*7+[15]+[0]*3))
        self.assertEqual((r['triangle_tie_trace_count'], r['plane_only_tie_trace_count'], r['different_plane_tie_trace_count']), (54, 172, 15))
        self.assertEqual(r['common_point_probes'], dict(parameters=4817, inside_coverage=1949))
        self.assertEqual(r['in_place_edge'], dict(
            live=dict(segments=610, domain_pairs=1942, nonempty_segments=0, nonempty_domains=0),
            full_authored_set_counterfactual=dict(segments=40, domain_pairs=160, nonempty_segments=18, nonempty_domains=27)))
        self.assertEqual(r['predecessor_report'], 'NOT_COMPARED_WITH_A_RETAINED_REPORT')
        for key, want in (('general_triangle_support', 'ABSTAIN'), ('native_front_reach_equivalence', 'NOT_CLAIMED'),
                          ('discovered_neighborhood_topology', 'NOT_IMPLEMENTED'),
                          ('physical_exit_acceptance', 'NOT_TESTED'), ('standability_load_bearing_acceptance', 'NOT_TESTED'),
                          ('classifier_render_hold_clock', 'NOT_TESTED'),
                          ('wall_return', 'GRADED_ON_CAPTURED_HITS'), ('floor_contact', 'REFUSED_SO_NOT_EXERCISED')):
            self.assertEqual(r[key], want)

    def test_supplied_set_is_the_native_dump_and_winners_are_its_nodes(self):
        four, two = [(j+1, list(i)) for j, i in enumerate(multi.INDEXES)], [(j+1, list(i)) for j, i in enumerate(multi.INDEXES[:2])]
        self.assertEqual([[(x['node'], x['indexes']) for x in n['native_leaves']] for n in self.native], [four]*3+[two]*2+[four]*3+[two]*3)
        for index, (case, native) in enumerate(zip(self.cases, self.native)):
            dumped = [x['vertices'] for x in native['native_leaves']]
            self.assertEqual((case['supplied_patch_set']['triangles'], native['supplied']), (dumped, dumped))
            # Parsed floats, not the table's integers: what is supplied IS the dump, not the table it has to equal.
            self.assertTrue(all(type(x) is float for t in native['supplied'] for v in t for x in v))
            self.assertEqual(dumped, multi.authored(index)[:len(dumped)])
        order = [list(dict.fromkeys(c['winner_triangles_in_order'])) for c in self.cases]
        self.assertEqual(order, [[0, 3, 2]]*3+[[0], [0], [0, 3, 2], [0], [1, 2], [0], [0], [0]])
        # P1 before the gap, P2 after it, never interleaved.
        wide = self.cases[2]['native_hits']
        self.assertEqual({h['winner_triangle'] for h in wide if h['command_index'] < 10}, {0})
        self.assertEqual({h['winner_triangle'] for h in wide if h['command_index'] > 13}, {2, 3})
        hits = [h for c in self.cases for h in c['native_hits']]
        self.assertTrue(all(h['winner_horizon2_reachable_at_hit_body'] and h['winner_native_leaf_node'] == h['winner_triangle']+1
                            for h in hits))
        ties = [(i, h['command_index'], h['winner_plane_tag'], h['winner_plane_tag_tied_with_model_tag'])
                for i, c in enumerate(self.cases) for h in c['native_hits'] if h['winner_plane_tag'] != 0]
        self.assertEqual(ties, [(1, 27, 8, 0)])

    def test_seam_and_narrow_gap_never_lose_reach(self):
        for case in self.cases[:2]:
            t = case['track']['hypothetical_down']
            self.assertEqual((t['coverage'], t['regained'], case['live_horizon2_reach_regained']), (WHOLE, [], NEVER))
            self.assertEqual({tr['kind'] for tr in t['transitions']}, {'track-bound'})
            self.assertEqual(case['track']['in_place']['coverage'], [])
            self.assertEqual((case['live_native_ramp_without_reach_commands'], case['live_reach_without_native_ramp_commands']), ([], [0, 1]))
            self.assertEqual([w['coverage'] for w in case['horizon_sensitivity']], [WHOLE]*2)

    def test_wide_gap_loses_and_regains_reach_at_footprint_edges(self):
        case = self.cases[2]
        t = case['track']['hypothetical_down']
        self.assertEqual(t['coverage'], [LOST, [F(37, 96), F(1)]])
        self.assertEqual(t['regained'], [dict(lost_at=F(7, 24), regained_at=F(37, 96), regained_measure=F(59, 96))])
        _, leave, enter, _ = t['transitions']
        for transition, kind, command, y, triangles in ((leave, 'exit', 9, 80, [0]), (enter, 'enter', 12, 98, [3])):
            (site,) = transition['sites']
            self.assertEqual((transition['kind'], transition['strictly_inside_command'], transition['reachable_only_at_full_horizon']),
                             (kind, True, False))
            self.assertEqual((site['command_index'], site['local_t'], site['command_parameter'], site['origin'][1],
                              site['bounding_triangles'], site['down_range_at_boundary'][1]), (command, F(1, 3), F(1, 3), y, triangles, 2))
        self.assertAlmostEqual(float(leave['sites'][0]['down_range_at_boundary'][0]), RIDE, delta=2e-5)
        self.assertAlmostEqual(float(enter['sites'][0]['down_range_at_boundary'][0]), 1.33209, delta=5e-6)
        gap = next(g for g in t['gaps'] if g['length'] == F(3, 32))
        self.assertEqual((gap['start_included'], gap['end_included'], gap['nominal_seconds_not_exit_clock']), (False, False, F(9, 200)))
        self.assertEqual((case['live_partially_reached_commands'], case['live_reach_without_native_ramp_commands'],
                          case['live_native_ramp_without_reach_commands']), ([9, 12], [0, 1, 12, 13], []))
        self.assertEqual([c['command_index'] for c in case['commands'] if not c['hypothetical_down']['coverage']], [10, 11])
        self.assertEqual([w['coverage'] for w in case['horizon_sensitivity']], [t['coverage']]*2)
        landing = next(h for h in case['native_hits'] if h['command_index'] == 14)
        self.assertEqual((landing['winner_triangle'], landing['committed_fraction'] > .2), (3, True))

    def test_a_footprint_edge_holds_only_down_to_the_low_end_of_its_own_down_range(self):
        case = self.cases[2]
        owners = [s for c in case['commands'] for s in c['segments']]
        points = [reach.vector(multi.ORIGIN)]+[reach.vector(s['end']) for s in owners]
        shares = [s['track_share'] for s in owners]
        at = lambda horizon: multi.sensitivity(case['supplied_patch_set']['triangles'], points, shares, horizon)['coverage']
        # The regain is reachable from 1.332 down; a probe shorter than that turns it into a horizon cut.
        self.assertEqual((at(F(134, 100)), at(F(13, 10))[0]), (at(2), at(2)[0]))
        self.assertGreater(at(F(13, 10))[1][0], at(2)[1][0])
        self.assertEqual(at(F(52, 1000)), [])

    def test_width_and_drop_each_lose_reach_alone_and_differently(self):
        narrow, both, lowered, wide = self.result['gap_design']
        self.assertEqual([(d['actor'], d['gap_width'], d['neighbour_lowered']) for d in self.result['gap_design']],
                         [(1, 16, 0), (2, 50, 2), (5, 16, 2), (6, 50, 0)])
        # Coplanar and narrower than the footprint: no loss. Either cause alone loses reach at the SAME footprint edge.
        self.assertEqual((narrow['horizon2_coverage'], narrow['wider_horizon_coverage']), (WHOLE, [WHOLE, WHOLE]))
        self.assertEqual([d['horizon2_coverage'][0] for d in (both, lowered, wide)], [LOST]*3)
        # Drop alone: back at a horizon cut within a command, and no loss at all for a longer probe.
        self.assertEqual((lowered['horizon2_reach'], len(lowered['horizon2_coverage']), lowered['wider_horizon_coverage'],
                          lowered['wall_hit_commands']), (BACK, 2, [WHOLE, WHOLE], []))
        # Width alone: never back, whatever the probe, and the command that would have regained it returns a wall.
        self.assertEqual((wide['horizon2_reach'], wide['horizon2_coverage'], wide['wider_horizon_coverage'], wide['wall_hit_commands']),
                         (GONE, [LOST], [[LOST], [LOST]], [12]))
        # Both: back at the neighbour's footprint edge, which no longer probe moves.
        back = [LOST, [F(37, 96), F(1)]]
        self.assertEqual((both['horizon2_coverage'], both['wider_horizon_coverage'], both['wall_hit_commands'], both['horizon2_reach'],
                          narrow['horizon2_reach']), (back, [back, back], [], BACK, KEPT))
        self.assertEqual([d['native_ramp_commands'] for d in self.result['gap_design']], [RODE, FELL, FELL, BOARDED])
        # Against the wide lowered gap: the coplanar narrow one parts when it is still riding, the coplanar wide
        # one at the wall, and the lowered narrow one NEVER: only the supplied patch set tells those two apart.
        self.assertEqual(self.result['twin_first_differing_tick'], {'narrow-gap': 10, 'narrow-gap-lowered': None, 'wide-gap-coplanar': 12})

    def test_a_lowered_narrow_gap_regains_reach_at_a_horizon_cut_long_before_it_lands(self):
        case = self.cases[5]
        self.assertEqual([t[10:16] for t in self.native[5]['ticks']], [t[10:16] for t in self.native[2]['ticks']])
        t = case['track']['hypothetical_down']
        self.assertEqual((t['coverage'][0], len(t['coverage']), len(t['regained'])), (LOST, 2, 1))
        _, leave, enter, _ = t['transitions']
        (out,), (back,) = leave['sites'], enter['sites']
        self.assertEqual((leave['kind'], leave['reachable_only_at_full_horizon'], out['command_index'], out['command_parameter'],
                          out['origin'][1], out['bounding_triangles'], out['down_range_at_boundary'][1]), ('exit', False, 9, F(1, 3), 80, [0], 2))
        self.assertEqual((enter['kind'], enter['reachable_only_at_full_horizon'], back['command_index'], back['down_range_at_boundary'],
                          back['bounding_triangles']), ('enter', True, 10, [2, 2], [3]))
        # The ride height to lose, at 0.18 a command: the 0.2893 every re-contact reports as its truefraction.
        self.assertAlmostEqual(float(back['command_parameter']), RIDE/.18, delta=2e-5)
        self.assertEqual([w['coverage'] for w in case['horizon_sensitivity']], [WHOLE]*2)
        landing = next(h for h in case['native_hits'] if h['command_index'] > 9)
        self.assertEqual((landing['command_index'], landing['tied_triangles'], landing['committed_fraction'] > .2), (14, 2, True))
        self.assertGreater(14+landing['committed_fraction']-10-float(back['command_parameter']), 3.9)
        self.assertEqual((case['live_partially_reached_commands'], case['live_reach_without_native_ramp_commands']),
                         ([9, 10], [0, 1, 10, 11, 12, 13]))
        # Tick ends either side of that cut: 0.052 outside it after command 9, 0.128 inside after command 10.
        ends = case['tick_ends']
        self.assertEqual([(e['native_down2_hit'], e['exact_horizon2_reach']) for e in ends[8:11]], [(True, True), (False, False), (True, True)])
        self.assertAlmostEqual(float(ends[9]['least_down_distance']), 2+RIDE, delta=1e-5)
        self.assertAlmostEqual(float(ends[10]['least_down_distance']), 2+RIDE-.18, delta=2e-5)

    def test_a_coplanar_wide_gap_ends_at_the_neighbours_side_as_a_wall(self):
        case, native = self.cases[6], self.native[6]
        self.assertEqual([t[10:16] for t in native['ticks'][:12]], [t[10:16] for t in self.native[2]['ticks'][:12]])
        (wall,) = case['wall_hits']
        self.assertEqual((wall['command_index'], wall['bump'], wall['normal'], wall['dist'], wall['committed_fraction']),
                         (12, 0, [0, -1, 0], -114, 63/192))
        self.assertAlmostEqual(wall['truefraction'], 1/3, delta=1e-7)
        # In the model that wall is four planes of one triangle that coincide.
        self.assertEqual(sorted((p[0], p[2]) for p in wall['model_entry_planes']),
                         [(3, 'bevel'), (3, 'bevel'), (3, 'raw-triangle-axial'), (3, 'side')])
        # It has sunk 0.72 in the gap: 2/3 of a unit below the plane it would otherwise have ridden on.
        self.assertAlmostEqual(-4/3*(wall['hit_body'][0]-16)-wall['hit_body'][2], .665, delta=.005)
        # blocked is 2 in that command and 0 in every other command of every actor.
        self.assertEqual([(i, call['command_index'], call['returned'][1]) for i, n in enumerate(self.native) for call in n['path']['calls']
                          if call['returned'][1]], [(6, 12, 2)])
        # Not a ramp contact: no accepted copy, no ramp flag, and the y velocity is gone for good.
        self.assertEqual(([h['command_index'] for h in case['native_hits']], [c['command_index'] for c in case['commands'] if c['native_ramp_return']]),
                         (BOARDED, BOARDED))
        (segment,) = [s for c in case['commands'] for s in c['segments'] if s['contact_class'] == 'WALL']
        self.assertEqual((segment['command_index'], segment['clip_rule'], segment['clip_plane_count'], segment['winner_triangle'],
                          segment['velocity_after'][1]), (12, SINGLE, 1, None, 0))
        self.assertEqual({t[14] for t in native['ticks'][12:]}, {0})
        # The hull stops one bias short of the neighbour's footprint and falls there: reach never returns, at any horizon.
        self.assertEqual({t[11]+multi.MAXS[1] for t in native['ticks'][12:]}, {114-1/32})
        self.assertEqual(({e['footprint_bounding_slack'] for e in case['tick_ends'][12:]}, {e['least_down_distance'] for e in case['tick_ends'][9:]}),
                         ({F(-1, 32)}, {None}))
        t = case['track']['hypothetical_down']
        self.assertEqual((t['coverage'], t['regained'], case['live_horizon2_reach_regained'], [w['coverage'] for w in case['horizon_sensitivity']]),
                         ([LOST], [], NEVER, [[LOST]]*2))

    def test_removed_neighbour_is_counterfactual_only_and_changes_the_body_at_the_landing(self):
        gone, kept = self.cases[3], self.cases[2]
        self.assertEqual(self.result['removed_neighbour_first_differing_tick'], 14)
        self.assertEqual([t[10:16] for t in self.native[3]['ticks'][:14]], [t[10:16] for t in self.native[2]['ticks'][:14]])
        self.assertEqual((len(gone['supplied_patch_set']['triangles']), gone['authored_triangles_never_built']), (2, multi.authored(3)[2:]))
        live = gone['track']['hypothetical_down']
        self.assertEqual((live['coverage'], live['regained'], gone['live_horizon2_reach_regained']), ([LOST], [], NEVER))
        against = gone['full_authored_set_counterfactual']
        self.assertEqual(against['hypothetical_down']['coverage'], kept['track']['hypothetical_down']['coverage'])
        self.assertEqual(against['in_place_edge'], dict(segments=40, domain_pairs=160, nonempty_segments=18, nonempty_domains=27))
        # The removed body falls through where the live one landed: one landing, one comparison.
        (site,) = against['in_place']['transitions'][0]['sites']
        landing = next(h for h in kept['native_hits'] if h['command_index'] == 14)
        self.assertEqual(site['command_index'], 14)
        # 3.2e-6 of a sweep that closes about half a unit along the normal: under 2e-6 units.
        self.assertAlmostEqual(float(site['command_parameter']), landing['truefraction'], delta=5e-6)
        self.assertEqual([c for c in self.cases if c['full_authored_set_counterfactual']], [gone])

    def test_vertical_lift_boundaries_are_horizon_cuts_and_move_with_the_horizon(self):
        case = self.cases[4]
        t = case['track']['hypothetical_down']
        self.assertEqual((len(t['coverage']), len(t['regained']), case['live_horizon2_reach_regained']), (2, 1, 'OBSERVED'))
        _, leave, enter, _ = t['transitions']
        for transition, kind, command, local in ((leave, 'exit', 1, .346941), (enter, 'enter', 12, .539974)):
            (site,) = transition['sites']
            self.assertEqual((transition['kind'], transition['reachable_only_at_full_horizon'], site['command_index'],
                              site['down_range_at_boundary']), (kind, True, command, [2, 2]))
            self.assertAlmostEqual(float(site['local_t']), local, delta=1e-6)
        four, eight = case['horizon_sensitivity']
        self.assertEqual((len(four['regained']), eight['coverage'], eight['regained']), (1, WHOLE, []))
        self.assertTrue(t['coverage'][0][1] < four['coverage'][0][1] < four['coverage'][1][0] < t['coverage'][1][0])
        self.assertEqual((case['live_partially_reached_commands'], case['live_reach_without_native_ramp_commands']), ([1, 12], [0, 1, 12, 13]))

    def test_the_trough_takes_the_two_plane_crease_branch_in_every_command_from_the_crease_on(self):
        case, native = self.cases[7], self.native[7]
        hits = case['native_hits']
        at = lambda command: [h for h in hits if h['command_index'] == command]
        shape = lambda found: [(h['bump'], h['winner_triangle'], h['clip_plane_count'], h['clip_rule'], h['committed_fraction'] > 0) for h in found]
        # Sliding down A it re-contacts A, meets B after a real move (one plane again), and is back on A without moving.
        self.assertEqual(shape(at(16)), [(0, 1, 1, SINGLE, False), (1, 2, 1, SINGLE, True), (2, 1, 2, CREASE, False)])
        self.assertAlmostEqual(at(16)[1]['committed_fraction'], .325, delta=1e-3)
        # 258 u/s across the crease when it arrives; none of it leaves that command.
        self.assertTrue(pm.close(native['path']['calls'][16]['attempts'][1][11:14], [155.04, 400, -206.72], 1e-3) and
                        pm.close(at(16)[2]['velocity_after'], [0, 400, 0], 1e-4))
        # Command 17: the second hit moved 5.5e-5 of a command, and ANY move clears the plane list, so that hit is a
        # one-plane clip again and the crease is taken a hit later.
        self.assertEqual(shape(at(17)), [(0, 1, 1, SINGLE, False), (1, 2, 1, SINGLE, True), (2, 1, 2, CREASE, False)])
        self.assertTrue(0 < at(17)[1]['committed_fraction'] < 1e-4)
        # From 18 on: one plane, the other at fraction exactly 0, the crease, then a clear move along y.
        for command in range(18, 32):
            first, second = at(command)
            self.assertEqual((first['bump'], first['clip_rule'], first['committed_fraction'], second['bump'], second['clip_rule'],
                              second['committed_fraction'], {first['winner_triangle'] > 1, second['winner_triangle'] > 1},
                              len(case['commands'][command]['segments'])), (0, SINGLE, 0, 1, CREASE, 0, {False, True}, 3))
        crease = [h for h in hits if h['clip_plane_count'] == 2]
        self.assertEqual(([h['command_index'] for h in crease], {h['clip_rule'] for h in crease}, {h['committed_fraction'] for h in crease}),
                         (list(range(16, 32)), {CREASE}, {0}))
        speeds = [h['velocity_after'][1] for h in crease]
        self.assertTrue(all(h['velocity_after'][0] == 0 == h['velocity_after'][2] for h in crease))
        # The crease costs float32 a little speed every clip: 399.99994 after the first, 399.99902 after the sixteenth.
        self.assertTrue(all(a > b for a, b in zip([400]+speeds, speeds)) and abs(400-speeds[-1]-9.8e-4) < 1e-5)
        self.assertEqual((case['clip_velocity_error'][ALONG], case['clip_rule_counts']), (None, {SINGLE: 32, ALONG: 0, CREASE: 16, multi.EITHER: 0}))
        self.assertTrue(5e-5 < case['clip_velocity_error'][CREASE] < 7e-5 < 8e-5 < multi.clip_tolerance([0, 400, 0]))
        self.assertLess(self.result['clip_velocity_error'][SINGLE], 2e-5)
        # Wedged: x and z fixed, y at 6 a command; never ground, always ramp, never blocked.
        self.assertEqual(({(t[10], t[12]) for t in native['ticks'][17:]}, {round(b[11]-a[11], 3) for a, b in zip(native['ticks'][17:], native['ticks'][18:])},
                          {t[9] for t in native['ticks']}, {call['returned'][1] for call in native['path']['calls']}),
                         ({(72, -74.6146011)}, {6}, {0}, {0}))
        # Both planes are 1/32 away, so the first attempt ties two planes that are NOT coplanar, and native names either.
        self.assertEqual([c['segments'][0]['tied_planes'] for c in case['commands']], [0, 0]+[1]*15+[2]*15)
        self.assertEqual(({round(h['native_normal'][0], 6) for h in hits if h['command_index'] > 16}, {h['winner_triangle'] for h in hits}),
                         ({.8, -.8}, {1, 2}))
        self.assertEqual((case['track']['hypothetical_down']['coverage'], case['track']['in_place']['coverage'], case['down2_disagreement_ticks']),
                         (WHOLE, [], []))

    def test_tick_ends_at_a_footprint_edge_and_at_the_horizon_cut_agree_with_native_down2(self):
        ladder, out, inside = self.cases[8], self.cases[9], self.cases[10]
        # Edge ladder: the hull's y-min creeps over the strip's edge at 0.00047 a command.
        ends = ladder['tick_ends']
        self.assertEqual([e['footprint_bounding_slack'] for e in ends[14:18]], [F(121, 156250), F(763, 2500000), F(-41, 250000), F(-1583, 2500000)])
        self.assertEqual([(e['native_down2_hit'], e['exact_horizon2_reach'], e['least_down_distance'] is not None) for e in ends],
                         [(True, True, True)]*16+[(False, False, False)]*16)
        t = ladder['track']['hypothetical_down']
        (site,) = t['transitions'][1]['sites']
        self.assertEqual((t['coverage'], t['transitions'][1]['kind'], t['transitions'][1]['reachable_only_at_full_horizon'], site['command_index'],
                          site['command_parameter'], site['bounding_triangles'], [w['coverage'] for w in ladder['horizon_sensitivity']]),
                         ([[F(0), F(19531, 37536)]], 'exit', False, 16, F(763, 1173), [0], [[[F(0), F(19531, 37536)]]]*2))
        # Native still re-contacts at the start of the command in which the footprint leaves, and never after:
        # the ramp flag outlives reach by the rest of that command and no longer.
        self.assertEqual((ladder['native_hits'][-1]['command_index'], ladder['native_hits'][-1]['committed_fraction'],
                          ladder['live_partially_reached_commands'], ladder['live_native_ramp_without_reach_commands'],
                          [c['native_ramp_return'] for c in ladder['commands'][15:18]]), (16, 0, [16], [], [True, True, False]))
        # Horizon graze: the top of a hop puts one tick end 0.00125 beyond the 2-unit probe, or 0.00063 short of it.
        self.assertEqual([e['least_down_distance'] for e in out['tick_ends'][2:5]], [F(4739847, 2500000), F(60037537, 30000000), F(577969, 300000)])
        self.assertEqual(inside['tick_ends'][3]['least_down_distance'], F(59981233, 30000000))
        self.assertEqual(([e['tick'] for e in out['tick_ends'] if not e['native_down2_hit']],
                          [e['tick'] for e in inside['tick_ends'] if not e['native_down2_hit']]), ([3], []))
        t = out['track']['hypothetical_down']
        (gap,) = t['regained']
        # A loss of 0.029 command, both ends horizon cuts, with that one tick end inside it.
        self.assertTrue(gap['lost_at'] < F(4, 32) < gap['regained_at'] and F(28, 1000) < (gap['regained_at']-gap['lost_at'])*32 < F(29, 1000))
        _, leave, enter, _ = t['transitions']
        self.assertEqual([(x['kind'], x['reachable_only_at_full_horizon'], x['sites'][0]['down_range_at_boundary']) for x in (leave, enter)],
                         [('exit', True, [2, 2]), ('enter', True, [2, 2])])
        self.assertEqual(([w['coverage'] for w in out['horizon_sensitivity']], inside['track']['hypothetical_down']['coverage'],
                          out['live_partially_reached_commands']), ([WHOLE]*2, WHOLE, [3, 4]))
        # The nearest tick end on each side of each kind of boundary: native and the exact reach agree at all four.
        sharp = self.result['sharpest_tick_ends']
        sides = ('horizon_inside', 'horizon_outside', 'footprint_inside', 'footprint_outside')
        self.assertEqual([(sharp[k]['actor'], sharp[k]['tick'], sharp[k]['native_down2_hit'], sharp[k]['exact_horizon2_reach']) for k in sides],
                         [(10, 3, True, True), (9, 3, False, False), (8, 15, True, True), (8, 16, False, False)])
        self.assertEqual((2-sharp['horizon_inside']['least_down_distance'], sharp['horizon_outside']['least_down_distance']-2,
                          sharp['footprint_inside']['footprint_bounding_slack'], -sharp['footprint_outside']['footprint_bounding_slack']),
                         (F(18767, 30000000), F(37537, 30000000), F(763, 2500000), F(41, 250000)))

    def test_live_in_place_is_empty_and_down2_agrees_at_every_tick_end(self):
        for case in self.cases:
            self.assertEqual((case['track']['in_place']['coverage'], case['in_place_edge']['nonempty_domains'], case['down2_disagreement_ticks']),
                             ([], 0, []))
            self.assertEqual(len(case['tick_ends']), 32)
        hits = [sum(e['native_down2_hit'] for e in c['tick_ends']) for c in self.cases]
        self.assertEqual(hits, [32, 32, 29, 9, 21, 31, 9, 32, 16, 31, 32])

    def test_supplied_patch_set_decides_the_verdict(self):
        case = self.cases[2]
        owners = [s for c in case['commands'] for s in c['segments']]
        points = [multi.ORIGIN]+[s['end'] for s in owners]
        supplied = case['supplied_patch_set']['triangles']
        _, alone = multi.track(supplied[:2], [0, 1], points, owners, case['commands'], 2, None)
        self.assertEqual((alone['coverage'], alone['regained']), ([LOST], []))
        # The neighbour moved 13 units along y: the regain follows it, half-way through the landing command.
        moved = [[[x, 127 if y == 114 else y, z] for x, y, z in t] for t in supplied[2:]]
        _, later = multi.track(supplied[:2]+moved, [0, 1, 2, 3], points, owners, case['commands'], 2, None)
        self.assertEqual(later['coverage'][0], LOST)
        self.assertAlmostEqual(float(later['coverage'][1][0])*32, 14.5, delta=1e-5)
        # A removed triangle offered as live makes the native trace gate refuse a clear sweep it would have blocked.
        attempt = self.native[3]['path']['calls'][14]['attempts'][0]
        self.assertEqual(multi.check_trace(attempt[24:], attempt[5:8], attempt[14:17], self.native[3]['supplied']),
                         dict(triangles=0, candidates=0, planes=0))
        with self.assertRaisesRegex(AssertionError, 'every plane-set candidate'):
            multi.check_trace(attempt[24:], attempt[5:8], attempt[14:17], multi.authored(3))
        # The same body over two supplied sets: lowered narrow (5) and lowered wide (2) differ in nothing else.
        _, swapped = multi.track(self.cases[5]['supplied_patch_set']['triangles'], [0, 1, 2, 3], points, owners, case['commands'], 2, None)
        self.assertEqual(swapped['coverage'], self.cases[5]['track']['hypothetical_down']['coverage'])

    def test_every_fixture_leaf_seed_and_tick_field_fault_refuses(self):
        # A quiet arm binds neither a tick's body nor a leaf's node index: those are mutated where something does
        # (capture here and in the leaf test), and the rest of them only five-arm parity can see.
        quiet = lambda w, column: 'TICK' not in w[0] and not ('LEAF' in w[0] and 'LEAVES' not in w[0] and column == 3)
        acted = self.refusals('nooracle', 0, 0, 'OFFRAMPTRIMULTI_', keep=quiet)
        acted += self.refusals('on', 1, 1, 'OFFRAMPTRIMULTI_TICK')
        self.assertEqual(acted, 11*5+36*15+34*15+11*3+11*13+352*28)
        print(f'{acted} ACTED multi-patch fixture/leaf/seed/tick field refusals, 0 failed')

    def test_every_native_query_field_fault_refuses(self):
        acted = self.refusals('control', 0, 1, 'OFFRAMPTRIMULTI_QUERY')
        self.assertEqual(acted, 1056*19)
        print(f'{acted} ACTED multi-patch native query field refusals, 0 failed')

    def test_every_path_and_capture_field_fault_refuses_on_the_recontact_wall_and_crease_actors(self):
        acted = sum(self.refusals('on', 1, 1, prefix, cases=FIELD_ACTORS) for prefix in
                    ('OFFRAMPTRIPATH_', 'OFFRAMPBUF_TICK', 'OFFRAMPBUF_CONTACT', 'OFFRAMPORIGIN_CONTACT', 'OFFRAMPTRICOPY_CONTACT'))
        fields = lambda case: (6+32*28+self.native[case]['path']['attempt_count']*(37+10) +
                               self.native[case]['path']['validation_count']*18+32*11+1+32*16 +
                               self.native[case]['path']['hit_count']*(24+10+18))
        self.assertEqual(acted, sum(fields(case) for case in FIELD_ACTORS))
        print(f'{acted} ACTED path/buffer/origin/copy field refusals on the wide-gap, vertical-lift, wall and trough actors, 0 failed')

    def test_each_row_missing_duplicated_or_swapped_with_its_neighbour_refuses(self):
        acted = 0
        with patch.object(multi, 'candidates', self.cached):
            for case in ROW_ACTORS:
                block = self.blocks['on'][case]
                lines = block.splitlines()
                for prefix in (multi.OWN, 'OFFRAMPTRIPATH_', 'OFFRAMPBUF_'):
                    owned = [i for i, l in enumerate(lines) if prefix in l]
                    for at, i in enumerate(owned):
                        variants = [lines[:i]+lines[i+1:], lines[:i]+[lines[i]]+lines[i:]]
                        if at+1 < len(owned):
                            j = owned[at+1]
                            variants.append(lines[:i]+[lines[j]]+lines[i+1:j]+[lines[i]]+lines[j+1:])
                        for bad in variants:
                            with self.subTest(case=case, row=lines[i][lines[i].find(prefix):][:40]), self.assertRaises(AssertionError):
                                multi.grade_case('\n'.join(bad), case, 1, 1)
                            acted += 1
        rows = lambda case: sum(3*len([l for l in self.blocks['on'][case].splitlines() if p in l])-1
                                for p in (multi.OWN, 'OFFRAMPTRIPATH_', 'OFFRAMPBUF_'))
        self.assertEqual(acted, sum(rows(case) for case in ROW_ACTORS))
        print(f'{acted} ACTED row deletion/duplication/adjacent-swap refusals, 0 failed')

    def test_attempts_that_belong_to_no_command_and_truncated_envelopes_refuse(self):
        block = self.blocks['on'][2]
        begin, attempt, outcome = (row(block, s) for s in ('OFFRAMPTRIPATH_BEGIN ', 'OFFRAMPTRIPATH_ATTEMPT 57 ', 'OFFRAMPTRIPATH_OUTCOME 57 '))
        self.assertEqual(begin.split()[4], '58')
        extra = []
        for ordinal, call in ((58, 32), (59, -7)):
            a, o = attempt.split(), outcome.split()
            a[1:3], o[1] = [str(ordinal), str(call)], str(ordinal)
            extra += [' '.join(a), ' '.join(o)]
        first_return = row(block, 'OFFRAMPTRIPATH_RETURN 0 ')
        orphaned = block.replace(begin, begin.replace(' 58 0 ', ' 60 0 ', 1), 1).replace(first_return, '\n'.join(extra+[first_return]), 1)
        with self.assertRaisesRegex(AssertionError, 'belongs to no command'): multi.grade_case(orphaned, 2, 1, 1)
        lines = block.splitlines()
        cut = lambda keep: '\n'.join(l for l in lines if keep(l))
        for name, bad in (('no returns or end', cut(lambda l: 'OFFRAMPTRIPATH_RETURN' not in l and 'OFFRAMPTRIPATH_END' not in l)),
                          ('calls only', cut(lambda l: 'OFFRAMPTRIPATH_' not in l or 'OFFRAMPTRIPATH_BEGIN' in l or 'OFFRAMPTRIPATH_CALL' in l)),
                          ('begin only', cut(lambda l: 'OFFRAMPTRIPATH_' not in l or 'OFFRAMPTRIPATH_BEGIN' in l)),
                          ('nothing', cut(lambda l: 'OFFRAMPTRIPATH_' not in l))):
            with self.subTest(truncated=name), self.assertRaises(AssertionError): multi.grade_case(bad, 2, 1, 1)
        # An outcome the mover STOPS with is named as an unsupported route, not as a broken row: the stop on more
        # than two planes (8), the same-plane push (9), the entry-velocity stop (10), recovery (3).
        # (Found by the mutant sweep: the later per-attempt checks refuse these too, under a misleading name.)
        trough = self.blocks['on'][7]
        crease = row(trough, 'OFFRAMPTRIPATH_OUTCOME 78 ')
        self.assertEqual(crease.split()[2], '2')
        for code in (8, 9, 10, 3):
            stopped = ' '.join(str(code) if i == 2 else w for i, w in enumerate(crease.split()))
            with self.subTest(outcome=code), self.assertRaisesRegex(AssertionError, 'unsupported multi-patch path outcome/refusal'):
                multi.grade_case(trough.replace(crease, stopped, 1), 7, 1, 1)

    def test_rows_no_reader_owns_refuse_in_a_capture_case_too(self):
        block = self.blocks['on'][0]
        seed = row(block, 'OFFRAMPTRIMULTI_SEED ')
        for stray in ('OFFRAMPBEVPM_TICK 0 0', 'OFFRAMPMOTION_CASE 0 x', 'OFFRAMPZZZ_UNSUPPORTED recovery portal', 'OFFRAMPTRIMULTIX_ROW 1'):
            with self.subTest(stray=stray), self.assertRaisesRegex(AssertionError, 'rows no reader owns'):
                multi.grade_case(block.replace(seed, seed+'\n'+stray, 1), 0, 1, 1)

    def test_consistent_forgeries_refuse_at_the_gate_written_for_each(self):
        def moved(case, hit, clear, outcome):
            """The last command's final clear move shifted in y, body and speed alike, from one outcome on.

            y runs along both ramp planes, so a body or a velocity moved in y keeps its distance to each.
            """
            queries = {f'OFFRAMPTRIMULTI_QUERY {case} 31 {name} ': {5: .015, 8: .015} for name in pm.QUERIES}
            return {f'OFFRAMPTRIPATH_OUTCOME {hit} ': outcome, f'OFFRAMPTRIPATH_ATTEMPT {clear} ': {13: 1, 16: .015, 36: .015},
                    f'OFFRAMPTRIPATH_OUTCOME {clear} ': {5: .015, 8: 1}, 'OFFRAMPTRIPATH_RETURN 31 ': {6: .015, 9: 1},
                    f'OFFRAMPTRIMULTI_TICK {case} 31 ': {12: .015, 15: 1}, 'OFFRAMPBUF_TICK 31 ': {9: .015, 12: 1}, **queries}
        block = self.blocks['on'][0]
        self.assertEqual((self.native[0]['path']['calls'][31]['attempts'][1][0], row(block, 'OFFRAMPTRIPATH_ATTEMPT 61 ').split()[25]), (61, '1'))
        queries = [f'OFFRAMPTRIMULTI_QUERY 0 31 {name} ' for name in pm.QUERIES]
        body = {'OFFRAMPTRIPATH_ATTEMPT 61 ': {36: 1}, 'OFFRAMPTRIPATH_OUTCOME 61 ': {5: 1}, 'OFFRAMPTRIPATH_RETURN 31 ': {6: 1},
                'OFFRAMPTRIMULTI_TICK 0 31 ': {12: 1}, 'OFFRAMPBUF_TICK 31 ': {9: 1}, **{q: {5: 1, 8: 1} for q in queries}}
        with self.assertRaisesRegex(AssertionError, 'trace endpoint/fraction differs'):
            multi.grade_case(forged(block, body), 0, 1, 1)
        # The velocity a ONE-plane clip left, one unit faster along y.
        with self.assertRaisesRegex(AssertionError, 'clip velocity differs from every native clip rule'):
            multi.grade_case(forged(block, moved(0, 60, 61, {8: 1})), 0, 1, 1)
        # The velocity the CREASE left: the trough's last command is hit 77 (one plane), hit 78 (crease), clear 79.
        trough = self.blocks['on'][7]
        last = self.native[7]['path']['calls'][31]
        self.assertEqual(([a[0] for a in last['attempts']], [s['clip_rule'] for s in self.cases[7]['commands'][31]['segments']]),
                         ([77, 78, 79], [SINGLE, CREASE, None]))
        with self.assertRaisesRegex(AssertionError, 'clip velocity differs from every native clip rule'):
            multi.grade_case(forged(trough, moved(7, 78, 79, {8: 1})), 7, 1, 1)
        # How fine that gate is. Native's crease sits 6.1e-5 u/s under the rule; a result another 2e-4 slower,
        # carried through every later row, is refused, and one 1e-4 FASTER is not: at this speed nothing here
        # sees a consistent lie from about 1.1e-4 slower to 2.3e-4 faster than native.
        carried = lambda delta: {'OFFRAMPTRIPATH_OUTCOME 78 ': {8: delta}, 'OFFRAMPTRIPATH_ATTEMPT 79 ': {13: delta},
                                 'OFFRAMPTRIPATH_OUTCOME 79 ': {8: delta}, 'OFFRAMPTRIPATH_RETURN 31 ': {9: delta},
                                 'OFFRAMPTRIMULTI_TICK 7 31 ': {15: delta}, 'OFFRAMPBUF_TICK 31 ': {12: delta}}
        with self.assertRaisesRegex(AssertionError, 'clip velocity differs from every native clip rule'):
            multi.grade_case(forged(trough, carried(-2e-4)), 7, 1, 1)
        self.assertNotEqual(forged(trough, carried(1e-4)), trough)
        multi.grade_case(forged(trough, carried(1e-4)), 7, 1, 1)
        # The time a hit leaves over. That crease hit took none (fraction 0); say it left 3.75e-5 s MORE, and let
        # the clear move after it run that much longer along y, with every later row agreeing.
        # (Found by the mutant sweep: the next attempt repeats the outcome's time-left, so the two lie together.)
        longer, further = .015/400, .015
        stretched = {'OFFRAMPTRIPATH_OUTCOME 78 ': {3: longer}, 'OFFRAMPTRIPATH_ATTEMPT 79 ': {5: longer, 16: further, 36: further},
                     'OFFRAMPTRIPATH_OUTCOME 79 ': {3: longer, 5: further}, 'OFFRAMPTRIPATH_RETURN 31 ': {3: longer, 6: further},
                     'OFFRAMPTRIMULTI_TICK 7 31 ': {12: further}, 'OFFRAMPBUF_TICK 31 ': {9: further},
                     **{f'OFFRAMPTRIMULTI_QUERY 7 31 {name} ': {5: further, 8: further} for name in pm.QUERIES}}
        with self.assertRaisesRegex(AssertionError, 'hit not followed by a residual native attempt'):
            multi.grade_case(forged(trough, stretched), 7, 1, 1)
        # One accepted contact struck from every capture layer alike: the trough's last, with the four footers
        # and the tick's cached ramp normal made to agree. The path still has that hit; only the count can say so.
        # (Found by the mutant sweep: pairing hits with contacts stops silently at the shorter list.)
        lines = trough.splitlines()
        layers = ('OFFRAMPBUF', 'OFFRAMPORIGIN', 'OFFRAMPGEOM', 'OFFRAMPHULL', 'OFFRAMPTRICOPY')
        last = [next(i for i, l in enumerate(lines) if f'{layer}_CONTACT 47 31 ' in l) for layer in layers]
        struck = '\n'.join(l for i, l in enumerate(lines) if i not in last)
        for footer, fewer in (('OFFRAMPBUF_END 32 48 0', 'OFFRAMPBUF_END 32 47 0'), ('OFFRAMPGEOM_END 48 0 0 1', 'OFFRAMPGEOM_END 47 0 0 1'),
                              ('OFFRAMPHULL_END 32 48', 'OFFRAMPHULL_END 32 47'), ('OFFRAMPTRICOPY_END 48 48 0', 'OFFRAMPTRICOPY_END 47 47 0')):
            self.assertEqual(struck.count(footer), 1)
            struck = struck.replace(footer, fewer, 1)
        cached = row(struck, 'OFFRAMPBUF_TICK 31 ')
        self.assertEqual(cached.split()[14:], ['0.800000072', '0', '0.600000024'])
        struck = struck.replace(cached, ' '.join('-0.800000072' if i == 14 else w for i, w in enumerate(cached.split())), 1)
        with self.assertRaisesRegex(AssertionError, 'ramp hits/copied accepted contact count differs'):
            multi.grade_case(struck, 7, 1, 1)
        # The command's TICK row against what the path returned. The capture buffer repeats the tick's body,
        # velocity and flags, so the two rows have to lie together. The tick-return gate is then the first to
        # refuse; the reach assessment would refuse the body and the flag again, the velocity nothing else.
        # (Found by the mutant sweep: without these it had no falsifier.)
        tick, kept = row(block, 'OFFRAMPTRIMULTI_TICK 0 31 '), row(block, 'OFFRAMPBUF_TICK 31 ')
        self.assertEqual((tick.split()[9], kept.split()[6]), ('1', '1'))
        flag = lambda line, at: ' '.join('0' if i == at else w for i, w in enumerate(line.split()))
        for name, lie in (('body', forged(block, {'OFFRAMPTRIMULTI_TICK 0 31 ': {12: 1}, 'OFFRAMPBUF_TICK 31 ': {9: 1}, **{q: {5: 1, 8: 1} for q in queries}})),
                          ('velocity', forged(block, {'OFFRAMPTRIMULTI_TICK 0 31 ': {15: 1}, 'OFFRAMPBUF_TICK 31 ': {12: 1}})),
                          ('ramp flag', block.replace(tick, flag(tick, 9), 1).replace(kept, flag(kept, 6), 1))):
            self.assertNotEqual(lie, block)
            with self.subTest(lie=name), self.assertRaisesRegex(AssertionError, 'return not the actual command body'):
                multi.grade_case(lie, 0, 1, 1)
        # A wall the command does not report, and a report of a wall that was not hit.
        gap = self.blocks['on'][6]
        wall, clear = row(gap, 'OFFRAMPTRIPATH_RETURN 12 '), row(gap, 'OFFRAMPTRIPATH_RETURN 11 ')
        self.assertEqual((wall.split()[2], clear.split()[2]), ('2', '0'))
        for old, new in ((wall, wall.replace(' 12 2 ', ' 12 0 ', 1)), (clear, clear.replace(' 11 0 ', ' 11 2 ', 1))):
            with self.subTest(row=old[:28]), self.assertRaisesRegex(AssertionError, 'return/blocked'):
                multi.grade_case(gap.replace(old, new, 1), 6, 1, 1)

    def test_a_multi_plane_clip_is_asked_about_the_velocity_its_command_entered_with(self):
        # (From the review: a unit pins what clip_rules does with the entry velocity, not which one the path hands it.)
        asked, real = [], multi.clip_rule
        def recorded(observed, velocity, planes, primal):
            asked.append((velocity, len(planes), primal))
            return real(observed, velocity, planes, primal)
        with patch.object(multi, 'clip_rule', recorded):
            graded = multi.grade_case(self.blocks['on'][7], 7, 1, 1)
        # Every attempt of a command but its last is a hit, and each hit is one clip.
        entered = [call['call'][11:14] for call in graded['path']['calls'] for _ in call['attempts'][:-1]]
        self.assertEqual((len(asked), [primal for _, _, primal in asked]), (48, entered))
        # In all sixteen two-plane clips the body's velocity is no longer the one its command entered with.
        creased = [(velocity, primal) for velocity, planes, primal in asked if planes == 2]
        self.assertTrue(len(creased) == 16 and all(velocity != primal for velocity, primal in creased))

    def test_a_hit_carries_the_hit_outcome_and_is_never_the_last_attempt_of_its_command(self):
        # (From the mutant sweep and the review: this gate had one falsifier, for the time a hit leaves over.)
        trough = self.blocks['on'][7]
        crease = row(trough, 'OFFRAMPTRIPATH_OUTCOME 78 ')
        self.assertEqual(crease.split()[2], '2')
        # The crease hit given the outcome code of a clean move, and nothing else changed.
        clean = ' '.join('1' if i == 2 else w for i, w in enumerate(crease.split()))
        with self.assertRaisesRegex(AssertionError, 'hit not followed by a residual native attempt'):
            multi.grade_case(trough.replace(crease, clean, 1), 7, 1, 1)
        # The last command's clear move struck, attempt and outcome, and the count with them: the command now ends
        # on its crease hit, which the mover does only with no velocity left or its bumps spent. The return row is
        # left alone, so without this gate it is the return that refuses, under another name.
        begin, attempt, outcome = (row(trough, s) for s in ('OFFRAMPTRIPATH_BEGIN ', 'OFFRAMPTRIPATH_ATTEMPT 79 ', 'OFFRAMPTRIPATH_OUTCOME 79 '))
        self.assertIn(' 32 80 0 ', begin)
        lines = [l for l in trough.splitlines() if attempt not in l and outcome not in l]
        self.assertEqual(len(lines), len(trough.splitlines())-2)
        ended = '\n'.join(lines).replace(begin, begin.replace(' 32 80 0 ', ' 32 79 0 ', 1), 1)
        with self.assertRaisesRegex(AssertionError, 'hit not followed by a residual native attempt'):
            multi.grade_case(ended, 7, 1, 1)

    def test_native_leaf_must_be_the_dumped_node_and_the_winner_must_have_bevels_on(self):
        block = self.blocks['on'][0]
        origin, shape = row(block, 'OFFRAMPORIGIN_CONTACT 0 '), row(block, 'OFFRAMPGEOM_CONTACT 0 ')
        self.assertEqual((origin.split()[5:7], shape.split()[4:6]), (['1', '1'], ['1', '1']))
        # The shape layer already binds the origin's leaf to its own row, so the two move together here.
        with self.assertRaisesRegex(AssertionError, 'shape not bound to winning origin'):
            multi.grade_case(block.replace(origin, origin.replace(' 2 1 1 0 ', ' 2 3 3 0 ', 1), 1), 0, 1, 1)
        relabelled, renamed = block, 0
        for line in block.splitlines():
            for prefix, at in (('OFFRAMPORIGIN_CONTACT', 5), ('OFFRAMPGEOM_CONTACT', 4)):
                if prefix in line:
                    words = line[line.find(prefix):].split()
                    if words[at:at+2] == ['1', '1']:
                        words[at:at+2] = ['9', '9']
                        relabelled = relabelled.replace(line[line.find(prefix):], ' '.join(words), 1)
                        renamed += 1
        self.assertEqual(renamed, 16)
        # Every contact of triangle 0 renamed alike: consistent, and still not the node the walker dumped.
        with self.assertRaisesRegex(AssertionError, 'not the dumped node'): multi.grade_case(relabelled, 0, 1, 1)
        # And from the other side: the dumped node of any triangle that ever wins cannot move either.
        acted = 0
        for case, native in enumerate(self.native):
            for leaf in native['native_leaves']:
                if multi.INDEXES.index(leaf['indexes']) in {h['winner_triangle'] for h in self.cases[case]['native_hits']}:
                    line = row(self.blocks['on'][case], f"OFFRAMPTRIMULTI_LEAF {case} {native['native_leaves'].index(leaf)} ")
                    with self.subTest(case=case, node=leaf['node']), self.assertRaises(AssertionError):
                        multi.grade_case(self.blocks['on'][case].replace(line, bumped(line, 3), 1), case, 1, 1)
                    acted += 1
        self.assertEqual(acted, 20)
        # Two leaves cannot share a node. A never-winning leaf renamed to the winner's node is bound by nothing
        # else in its own arm. (Found by the mutant sweep: the distinctness check had no falsifier.)
        lift = self.blocks['on'][4]
        spare = row(lift, 'OFFRAMPTRIMULTI_LEAF 4 1 ')
        self.assertEqual((spare.split()[3], row(lift, 'OFFRAMPTRIMULTI_LEAF 4 0 ').split()[3]), ('2', '1'))
        with self.assertRaisesRegex(AssertionError, 'not the live authored set'):
            multi.grade_case(lift.replace(spare, ' '.join('1' if i == 3 else w for i, w in enumerate(spare.split())), 1), 4, 1, 1)
        copy = row(block, 'OFFRAMPTRICOPY_CONTACT 0 ')
        self.assertEqual(copy.split()[5], '1')
        with self.assertRaisesRegex(AssertionError, 'bevels on'):
            multi.grade_case(block.replace(copy, bumped(copy, 5, -1), 1), 0, 1, 1)

    def test_a_winner_tag_is_bound_only_up_to_the_planes_that_coincide_with_the_face(self):
        # 256 of 257 winners name the face and one a bevel the model ties with it; the turned-bevel alias has
        # accepted nothing natively. What the gate can see, and what it cannot, on one contact of each kind:
        self.assertEqual(self.result['winner_tag_match_counts'],
                         dict(MODEL_ENTRY_PLANE=256, COINCIDENT_MODEL_PLANE=1, FACE_PLANE_BEVEL_TURNED_IN_THE_MODEL=0))
        block, accepted = self.blocks['on'][0], self.native[0]['accepted']
        def retagged(ordinal, tag):
            line = row(block, f'OFFRAMPTRICOPY_CONTACT {ordinal} ')
            return block.replace(line, ' '.join(str(tag) if i == 4 else w for i, w in enumerate(line.split())), 1)
        for triangle, coincide, kind in ((0, (8, 11), 'COINCIDENT_MODEL_PLANE'), (3, (6, 11), 'FACE_PLANE_BEVEL_TURNED_IN_THE_MODEL')):
            ordinal = next(i for i, c in enumerate(accepted) if c['triangle'] == triangle)
            self.assertEqual((accepted[ordinal]['copied_winner']['native_plane_tag'], accepted[ordinal]['plane_tag_match']),
                             (0, 'MODEL_ENTRY_PLANE'))
            for tag in coincide:  # another name for the same plane: accepted, and said so
                self.assertEqual(multi.grade_case(retagged(ordinal, tag), 0, 1, 1)['accepted'][ordinal]['plane_tag_match'], kind)
            for tag in (1, 2, 5, 100):  # the back, a side, a bevel that is not the face, a raw axis: refused
                with self.subTest(triangle=triangle, tag=tag), self.assertRaisesRegex(AssertionError, 'not a latest-entry plane'):
                    multi.grade_case(retagged(ordinal, tag), 0, 1, 1)

    def test_quiet_capture_rows_outside_rows_and_arm_faults_refuse(self):
        on, quiet = self.blocks['on'][0], self.blocks['nooracle'][0]
        for prefix in ('OFFRAMPGEOM_', 'OFFRAMPBUF_', 'OFFRAMPTRIPATH_', 'OFFRAMPHULL_'):
            line = row(on, prefix)
            with self.subTest(prefix=prefix), self.assertRaisesRegex(AssertionError, 'quiet multi-patch arm has capture rows'):
                multi.grade_case(quiet+'\n'+line, 0, 0, 0)
        stray = row(on, 'OFFRAMPTRIPATH_CALL 0 ')
        envelope = multi.split(self.texts[3])[1]
        with self.assertRaisesRegex(AssertionError, 'capture outside cases'):
            multi.grade(envelope.replace('OFFRAMPTRIMULTI_END 11', stray+'\nOFFRAMPTRIMULTI_END 11'))
        for arm, change in ((3, lambda t: t+'\nOFFRAMPTRIMULTI_LEAVES 0 4 0'), (2, lambda t: t+'\n'+stray)):
            texts = list(self.texts); texts[arm] = change(texts[arm])
            with self.subTest(arm=arm), self.assertRaises(AssertionError): multi.compare(*texts)

    def test_faults_only_five_arm_parity_can_see_refuse_there(self):
        # Each fault passes its own arm's gates: a quiet body, a hit fraction and a truefraction inside tolerance.
        tick = row(self.texts[0], 'OFFRAMPTRIMULTI_TICK 2 9 ')
        down = row(self.texts[2], 'OFFRAMPTRIMULTI_QUERY 0 5 down2 ')
        hit = next(l[l.find('OFFRAMPTRIPATH_ATTEMPT'):] for l in self.blocks['repeat'][2].splitlines()
                   if 'OFFRAMPTRIPATH_ATTEMPT' in l and 0 < float(l[l.find('OFFRAMPTRIPATH_ATTEMPT'):].split()[25]) < 1)
        self.assertLess(float(down.split()[10]), 1)
        leaf = row(self.texts[0], 'OFFRAMPTRIMULTI_LEAF 4 1 ')  # a triangle that never wins: nothing else binds its node
        for arm, old, new, message in ((0, tick, bumped(tick, 11), 'body/leaf parity'), (0, leaf, bumped(leaf, 3), 'body/leaf parity'),
                                       (2, down, bumped(down, 10, 1e-9), 'query parity'),
                                       (4, hit, bumped(hit, 26, 1e-9), 'repeat capture differs')):
            texts = list(self.texts); texts[arm] = texts[arm].replace(old, new, 1)
            self.assertNotEqual(texts[arm], self.texts[arm])
            multi.grade(multi.split(texts[arm])[1])
            with self.subTest(arm=arm), self.assertRaisesRegex(AssertionError, message): multi.compare(*texts)
        texts = list(self.texts); texts[2] = texts[3]
        with self.assertRaisesRegex(AssertionError, 'arm modes differ'): multi.compare(*texts)

    def test_envelope_header_and_footer_faults_refuse(self):
        envelope = multi.split(self.texts[0])[1]
        multi.grade(envelope)
        acted = 0
        for start in ('OFFRAMPTRIMULTI_BEGIN ', 'OFFRAMPTRIMULTI_SOURCE ', 'OFFRAMPTRIMULTI_CASE_END 3 ', 'OFFRAMPTRIMULTI_END '):
            line = row(envelope, start)
            for column in range(1, len(line.split())):
                with self.subTest(row=start, column=column), self.assertRaises(AssertionError):
                    multi.grade(envelope.replace(line, bumped(line, column), 1))
                acted += 1
        self.assertEqual(acted, 5+3+2+1)

    def test_share_rule_horizon_nesting_containment_merged_horizons_and_margins_refuse(self):
        equal = lambda rows, duration: [F(1, len(rows))]*len(rows)
        with patch.object(walk, 'shares', equal), self.assertRaisesRegex(AssertionError, 'velocity x nominal share'):
            multi.assess_actor(4, self.native[4])
        shrunk = lambda triangles, points, shares, horizon: dict(horizon=horizon, coverage=[], regained=[], basis='mutant')
        with patch.object(multi, 'sensitivity', shrunk), self.assertRaisesRegex(AssertionError, 'does not nest'):
            multi.assess_actor(4, self.native[4])
        real = multi.track
        def blind(triangles, names, points, owners, commands, horizon, key):
            result, summary = real(triangles, names, points, owners, commands, horizon, key)
            return result, summary if key else dict(summary, coverage=[])
        with patch.object(multi, 'track', blind), self.assertRaisesRegex(AssertionError, 'does not contain live reach'):
            multi.assess_actor(3, self.native[3])
        with patch.object(multi, 'HORIZONS', (('in_place', 2), ('hypothetical_down', 2))), \
                self.assertRaisesRegex(AssertionError, 'zero-distance edge'):
            multi.assess_actor(3, self.native[3])
        # The track cut to a command against that command's own glue is checked for both horizons of an actor
        # (the check itself is falsified in the committed-reach suite; here, that it is still wired in).
        with patch.object(walk, 'consistent') as seen:
            multi.assess_actor(4, self.native[4])
        self.assertEqual([c.args[3:] for c in seen.call_args_list], [('in_place', 32), ('hypothetical_down', 32)])
        # The tick-end witness and the least distance are two computations of one thing.
        margins = multi.margins
        for wrong in (lambda t, o: dict(margins(t, o), least_down_distance=None),
                      lambda t, o: dict(margins(t, o), least_down_distance=F(201, 100))):
            with patch.object(multi, 'margins', wrong), self.assertRaisesRegex(AssertionError, 'least down distance'):
                multi.assess_actor(9, self.native[9])

    def test_this_capture_reproduces_its_own_predecessor_report_and_a_changed_one_refuses(self):
        prior = self.result['prior_committed_reach_report']
        retained = json.loads(json.dumps(reach.encoded(prior), allow_nan=False))
        self.assertEqual(multi.same_prior(prior, dict(retained, arms='theirs')), 'EQUAL_TO_RETAINED_REPORT')
        with self.assertRaisesRegex(AssertionError, 'differs from the retained one'):
            multi.same_prior(prior, dict(retained, committed_segment_count=retained['committed_segment_count']+1))

    def test_the_old_quiet_check_now_sees_the_shape_layer(self):
        text = multi.split(self.texts[0])[0]
        rest, block = pm.split(text)
        pm.grade(block)
        end = 'OFFRAMPBEVPM_CASE_END 0 32'
        with self.assertRaisesRegex(AssertionError, 'quiet bevel PM arm has capture rows'):
            pm.grade(block.replace(end, 'OFFRAMPGEOM_BEGIN 2 16 64\n'+end, 1))

    def test_manifest_source_and_mode_faults_refuse(self):
        arms = json.loads(ARMS.read_text())
        for field, value in (('trimulti_source_sha256', '0'*64), ('tripath_source_sha256', '0'*64), ('capture', True), ('oracle', 0)):
            bad = deepcopy(arms); bad['on'][field] = value
            with self.subTest(field=field), patch.object(Path, 'read_text', return_value=json.dumps(bad)), \
                    patch.object(multi.path.pm, 'load_arms', return_value=(self.texts, [])), self.assertRaises(AssertionError):
                multi.load_arms(ARMS)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__); ap.add_argument('--native-arms', type=Path)
    a, rest = ap.parse_known_args(); ARMS = a.native_arms
    Native.__unittest_skip__ = not bool(ARMS)
    unittest.main(argv=[__file__, *rest])
