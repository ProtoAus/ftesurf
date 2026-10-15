"""File-only readback proposal; no driver import, I/O, native authority or acceptance.

Policy provenance and limits: p721cache_readback.md (public sibling).
The six absent names are observed non-controls, not aliases for real controls.
"""
from decimal import Decimal, InvalidOperation
import re

# Exact failed-run membership, not a prefix/pattern exception. See p721cache_readback.md: historical scope.
EXPECTED_ABSENT = frozenset({
    'hud_timers', 'hud_pb', 'hud_spectators', 'hud_statusbar',
    'hud_lobby', 'hud_surfinfo',
})

# All real settings from the frozen driver remain mandatory, including PVS/input.
OBSERVED_REQUIRED = dict(item.split() for item in (
    'cfg_save_auto 0; cl_idlefps 0; cl_maxfps 100; r_wateralpha_extendpvs 0; '
    'r_novis 0; fov 100; vid_srgb 0; r_renderscale 2; r_fullbright 1; r_clear 0; '
    'r_dynamic 0; r_shadow_realtime_world 0; r_shadow_realtime_dlight 0; '
    'r_forceprogramify 0; con_notifylines 0; con_notifytime 0; con_savehistory 0; '
    'zone_draw 0; crosshair 0; hud_crosshair 0; hud_chat 0; hud_strafe 0; '
    'hud_keys 0; hud_speed 0; cl_netfps 0; cl_nopred 0; cl_predict_extrapolate 1; '
    'cl_predict_timenudge 0.5; in_rawinput 0; sensitivity 0; m_filter 0; '
    'm_pitch 0; m_yaw 0; vid_renderer gl; r_blendsort 1'
).split('; '))

# Source-identified real panels, NOT proof of all modal/event overlays being off.
# No existing witness contains these readbacks. See p721cache_readback.md: HUD sources and limitations.
OVERLAY_REQUIRED = dict.fromkeys((
    'hud_timer', 'hud_mapinfo', 'hud_mouse', 'hud_board', 'hud_seq',
    'hud_debug', 'hud_net', 'hud_trainer', 'hud_boarding', 'hud_specby',
    'hud_banner', 'hud_results_toast', 'hud_trail',
), '0')

_TIMESTAMP = re.compile(r'^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d ')
_VALUE = re.compile(r'^"([a-zA-Z0-9_]+)" is "([^"\r\n]*)"(?: \(default\))?$')
_UNKNOWN = re.compile(r'^Unknown command "([a-zA-Z0-9_]+)"$')
_EFFECTIVE = re.compile(r'^Effective value is "([^"\r\n]*)"$')
_DEFAULT = re.compile(r'^Default: "[^"\r\n]*"$')
# Fixed settings are nonnegative. This ASCII subset agrees with Q_atoi/Q_atof;
# Decimal alone also accepts +, exponent/underscore/Unicode spellings they do not.
_NUMBER = re.compile(r'[0-9]+(?:\.[0-9]+)?')


class ContractError(ValueError):
    """A missing, ambiguous, unexpected or wrong effective observation."""


def _require(condition, message):
    if not condition:
        raise ContractError(message)


def _equal(actual, wanted):
    if wanted == 'gl':
        return actual == wanted
    if _NUMBER.fullmatch(actual) is None:
        return False
    try:
        value = Decimal(actual)
        return value.is_finite() and value == Decimal(wanted)
    except InvalidOperation:
        return False


def parse_readback(text, required, expected_absent):
    """Parse a complete, bounded reply, never a cumulative console log.

    Required/absent sets must be explicitly supplied and disjoint. Each name
    occurs exactly once; absent means exactly one Unknown, never a value (even
    zero). Only an immediately following Effective line overrides a value;
    duplicate/orphan effective lines, pending-latch lines and all other output
    fail closed. Default lines are informational, never effective values.
    """
    _require(bool(required), 'empty required membership')
    _require(not set(required).intersection(expected_absent), 'overlapping membership')
    values, unknowns = {}, set()
    active = None
    overridden = set()
    for raw in text.splitlines():
        line = _TIMESTAMP.sub('', raw)
        if not line or line.startswith('sent to cl: '):
            active = None
            continue
        match = _VALUE.fullmatch(line)
        if match:
            name, value = match.groups()
            _require(name not in expected_absent, 'expected absent reappeared: ' + name)
            _require(name in required, 'unexpected cvar: ' + name)
            _require(name not in values and name not in unknowns, 'duplicate cvar: ' + name)
            values[name] = value
            active = name
            continue
        match = _UNKNOWN.fullmatch(line)
        if match:
            name = match[1]
            _require(name in expected_absent, 'unexpected unknown: ' + name)
            _require(name not in unknowns and name not in values, 'duplicate unknown: ' + name)
            unknowns.add(name)
            active = None
            continue
        match = _EFFECTIVE.fullmatch(line)
        if match:
            _require(active is not None, 'orphan effective value')
            _require(active not in overridden, 'duplicate effective value: ' + str(active))
            values[active] = match[1]
            overridden.add(active)
            continue
        if _DEFAULT.fullmatch(line):
            _require(active is not None, 'orphan default value')
            active = None
            continue
        raise ContractError('unrecognized readback line: ' + line)
    _require(unknowns == set(expected_absent),
             'missing expected-absent observation: ' + ','.join(sorted(set(expected_absent) - unknowns)))
    _require(set(values) == set(required),
             'missing mandatory cvar: ' + ','.join(sorted(set(required) - set(values))))
    for name, wanted in required.items():
        _require(_equal(values[name], wanted), 'wrong effective ' + name)
    return values


def audit_preserved_settings(text, cache=0):
    """Historical instrumentation diagnosis ONLY; cannot certify no-overlay."""
    _require(type(cache) is int and cache in (0, 1), 'invalid cache phase')
    return parse_readback(text, dict(OBSERVED_REQUIRED, r_temporalscenecache=str(cache)),
                          EXPECTED_ABSENT)


def proposed_settings(text, cache):
    """Stricter candidate settings gate; source-lineage/overlay acceptance external.

    Missing real controls in the preserved witness MUST fail this function.
    Renderer/model/material/actor/camera/worker/GPU gates remain separate mandatory
    future adapter checks, not replaced by this settings-only parser.
    """
    _require(type(cache) is int and cache in (0, 1), 'invalid cache phase')
    return parse_readback(text, dict(OBSERVED_REQUIRED, **OVERLAY_REQUIRED,
                                    r_temporalscenecache=str(cache)), EXPECTED_ABSENT)
